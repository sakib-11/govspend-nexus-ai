"""Masking service — production-grade PII masking with HMAC tokenization."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from config import MaskedEvidenceConfig
from models.masking import EntityType, MaskingLevel, MaskingRule, PIIField
from services.tokenization_service import TokenizationService
from utils.validation_utils import contains_pii, field_looks_like_pii

logger = logging.getLogger(__name__)

# Role -> masking level mapping
_LEVEL_MAP: dict[str, MaskingLevel] = {
    "auditor_level_1": MaskingLevel.MINIMAL,
    "auditor_level_2": MaskingLevel.PARTIAL,
    "auditor_level_3": MaskingLevel.FULL,
    "admin": MaskingLevel.FULL,
    "super_admin": MaskingLevel.FULL,
}

# Fields that are always safe (non-PII) in MINIMAL mode
_SAFE_FIELDS: frozenset[str] = frozenset({
    "amount", "date", "status", "risk_score", "category",
    "transaction_id", "case_id", "evidence_id", "created_at",
    "updated_at", "tier", "jurisdiction_id",
})


class MaskingService:
    """Apply role-based and field-level PII masking to evidence data.

    Supports three masking levels (FULL / PARTIAL / MINIMAL), automatic
    PII pattern detection, nested dict/list traversal, and HMAC-based
    tokenization for explicit fields.
    """

    def __init__(
        self,
        config: MaskedEvidenceConfig,
        tokenization_service: TokenizationService,
    ) -> None:
        self.config = config
        self.tokenization = tokenization_service

        # Build masking rules for each PII field type
        self._rules: dict[str, MaskingRule] = {
            PIIField.PAN.value: MaskingRule(
                field_type="pan", pattern=r"[A-Z]{5}[0-9]{4}[A-Z]",
                preserve_start=2, preserve_end=1,
            ),
            PIIField.GST.value: MaskingRule(
                field_type="gst",
                pattern=r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9][A-Z0-9][0-9]",
                preserve_start=2, preserve_end=1,
            ),
            PIIField.UPI.value: MaskingRule(
                field_type="upi", pattern=r"[a-zA-Z0-9._%+-]+@[a-zA-Z]{2,}",
                preserve_start=3, preserve_end=0,
            ),
            PIIField.BANK_ACCOUNT.value: MaskingRule(
                field_type="bank_account", preserve_start=4, preserve_end=4,
            ),
            PIIField.PHONE.value: MaskingRule(
                field_type="phone", preserve_start=2, preserve_end=2,
            ),
            PIIField.EMAIL.value: MaskingRule(
                field_type="email",
                pattern=r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                preserve_start=2, preserve_end=0,
            ),
            PIIField.AADHAAR.value: MaskingRule(
                field_type="aadhaar",
                pattern=r"[0-9]{4}\s?[0-9]{4}\s?[0-9]{4}",
                preserve_start=2, preserve_end=2,
            ),
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_masking_level(self, user_roles: List[str]) -> MaskingLevel:
        """Determine the effective masking level from *user_roles*."""
        best = MaskingLevel.MINIMAL
        for role in user_roles:
            mapped = _LEVEL_MAP.get(role)
            if mapped == MaskingLevel.FULL:
                return MaskingLevel.FULL
            if mapped == MaskingLevel.PARTIAL:
                best = MaskingLevel.PARTIAL
        return best

    async def mask_data(
        self,
        raw_data: Dict[str, Any],
        fields_to_mask: List[str],
        entity_type: str,
        *,
        preserve_fields: Optional[List[str]] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """Mask sensitive data while preserving structure.

        Returns ``(masked_data, tokens)`` where *tokens* maps each masked
        field name to its generated HMAC token.
        """
        preserve = set(preserve_fields or [])
        masked_data: Dict[str, Any] = {}
        tokens: Dict[str, str] = {}

        for key, value in raw_data.items():
            if key in preserve:
                masked_data[key] = value
                continue

            if key in fields_to_mask:
                if isinstance(value, list):
                    # Tokenize each element in the list
                    masked_list, list_tokens = await self._mask_list(
                        value, fields_to_mask, entity_type, preserve,
                        force_tokenize=True,
                    )
                    masked_data[key] = masked_list
                    tokens.update(list_tokens)
                else:
                    # Tokenize the scalar value
                    token = await self._tokenize_field(key, value, entity_type)
                    if token is not None:
                        tokens[key] = token
                        masked_data[key] = token
                    else:
                        masked_data[key] = value
            elif isinstance(value, str):
                # Auto-detect PII patterns in string values
                masked_data[key] = self._apply_field_masking(key, value)
            elif isinstance(value, dict):
                masked_sub, tokens_sub = await self._mask_dict(
                    value, fields_to_mask, entity_type, preserve,
                )
                masked_data[key] = masked_sub
                tokens.update(tokens_sub)
            elif isinstance(value, list):
                masked_list, tokens_sub = await self._mask_list(
                    value, fields_to_mask, entity_type, preserve,
                )
                masked_data[key] = masked_list
                tokens.update(tokens_sub)
            else:
                masked_data[key] = value

        return masked_data, tokens

    async def mask_for_level(
        self,
        data: Dict[str, Any],
        level: MaskingLevel,
        *,
        entity_type: str = "generic",
    ) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """Apply masking at the given *level* (role-based shortcut)."""
        if level == MaskingLevel.FULL:
            return dict(data), {}

        # PARTIAL: mask PII fields only
        if level == MaskingLevel.PARTIAL:
            pii_fields = [k for k in data if field_looks_like_pii(k)]
            return await self.mask_data(
                data, pii_fields, entity_type,
            )

        # MINIMAL: keep only safe fields
        result: Dict[str, Any] = {}
        for k, v in data.items():
            if k in _SAFE_FIELDS:
                result[k] = v
            else:
                result[k] = "***"
        return result, {}

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _tokenize_field(
        self, field_name: str, value: Any, entity_type: str,
    ) -> Optional[str]:
        """Tokenize a single field value."""
        if isinstance(value, str) and value.strip():
            return await self.tokenization.tokenize(value, entity_type)
        if isinstance(value, (int, float)):
            return await self.tokenization.tokenize(str(value), entity_type)
        return None

    async def _mask_dict(
        self,
        data: Dict[str, Any],
        fields_to_mask: List[str],
        entity_type: str,
        preserve: set,
    ) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """Recursively mask a nested dictionary."""
        masked: Dict[str, Any] = {}
        tokens: Dict[str, str] = {}

        for key, value in data.items():
            if key in preserve:
                masked[key] = value
                continue

            if key in fields_to_mask:
                token = await self._tokenize_field(key, value, entity_type)
                if token is not None:
                    tokens[key] = token
                    masked[key] = token
                else:
                    masked[key] = value
            elif isinstance(value, str):
                masked[key] = self._apply_field_masking(key, value)
            elif isinstance(value, dict):
                sub_masked, sub_tokens = await self._mask_dict(
                    value, fields_to_mask, entity_type, preserve,
                )
                masked[key] = sub_masked
                tokens.update(sub_tokens)
            elif isinstance(value, list):
                sub_list, sub_tokens = await self._mask_list(
                    value, fields_to_mask, entity_type, preserve,
                )
                masked[key] = sub_list
                tokens.update(sub_tokens)
            else:
                masked[key] = value

        return masked, tokens

    async def _mask_list(
        self,
        items: list,
        fields_to_mask: List[str],
        entity_type: str,
        preserve: set,
        *,
        force_tokenize: bool = False,
    ) -> Tuple[list, Dict[str, str]]:
        """Mask list items, tokenizing strings that appear in maskable fields.

        When *force_tokenize* is ``True`` (e.g. the list itself is in
        ``fields_to_mask``), every string element is tokenized regardless
        of content.
        """
        tokens: Dict[str, str] = {}
        result: list = []
        for item in items:
            if isinstance(item, str):
                should_tokenize = force_tokenize or any(
                    kw in item.lower() for kw in ("pan", "gst", "aadhaar")
                )
                if should_tokenize:
                    token = await self.tokenization.tokenize(item, entity_type)
                    if token:
                        tokens[item] = token
                        result.append(token)
                        continue
                result.append(self._apply_field_masking("", item))
            elif isinstance(item, dict):
                sub_masked, sub_tokens = await self._mask_dict(
                    item, fields_to_mask, entity_type, preserve,
                )
                result.append(sub_masked)
                tokens.update(sub_tokens)
            else:
                result.append(item)
        return result, tokens

    def _apply_field_masking(self, field_name: str, value: str) -> str:
        """Apply pattern-based masking to a string value."""
        if not value or not isinstance(value, str):
            return value

        # 1. Try matching by field name
        for pii_key, rule in self._rules.items():
            if pii_key in field_name.lower():
                return self._mask_value(value, rule)

        # 2. Try matching by content pattern
        for rule in self._rules.values():
            if rule.pattern and re.search(rule.pattern, value):
                return self._apply_pattern_mask(value, rule)

        # 3. Auto-detect generic PII patterns
        detected = contains_pii(value)
        if detected:
            pii_type = detected[0]
            rule = self._rules.get(pii_type)
            if rule:
                return self._apply_pattern_mask(value, rule)

        return value

    def _apply_pattern_mask(self, value: str, rule: MaskingRule) -> str:
        """Mask a value using a regex pattern — only the matched portion."""
        if not rule.pattern:
            return self._mask_value(value, rule)

        pattern = re.compile(rule.pattern)
        result = value
        offset = 0

        for match in pattern.finditer(value):
            matched_text = match.group()
            start = match.start() + offset
            end = match.end() + offset

            masked_part = self._mask_value(matched_text, rule)
            result = result[:start] + masked_part + result[end:]
            offset += len(masked_part) - len(matched_text)

        return result

    def _mask_value(self, value: str, rule: MaskingRule) -> str:
        """Apply a MaskingRule to a plain string value."""
        if not value:
            return value

        mc = rule.mask_character
        ps = min(rule.preserve_start, len(value))
        pe = min(rule.preserve_end, len(value) - ps)

        if ps + pe >= len(value):
            # Too short to meaningfully mask — mask everything
            return mc * len(value)

        middle = mc * (len(value) - ps - pe)
        if pe > 0:
            return value[:ps] + middle + value[-pe:]
        return value[:ps] + middle
