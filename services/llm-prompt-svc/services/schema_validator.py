"""Schema validator — validate LLM inputs and outputs against JSON schemas."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from models.prompt import ValidationResult
from models.schemas import InputSchema, OutputSchema
from utils.validation_utils import (
    collect_evidence_ids,
    collect_policy_ids,
    compute_citation_coverage,
    validate_confidence,
    validate_explanations,
    validate_risk_score,
    validate_signals,
)

logger = logging.getLogger(__name__)

# Optional jsonschema dependency
try:
    from jsonschema import validate as js_validate, ValidationError

    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False


class SchemaValidator:
    """Validate LLM inputs and outputs against defined schemas."""

    def __init__(self) -> None:
        self.input_schema = InputSchema()
        self.output_schema = OutputSchema()

    # ------------------------------------------------------------------
    # Input validation
    # ------------------------------------------------------------------

    def validate_input(self, input_data: Dict[str, Any]) -> ValidationResult:
        """Validate input data against the input schema."""
        errors: List[str] = []
        warnings: List[str] = []

        # JSON schema validation
        if _HAS_JSONSCHEMA:
            try:
                js_validate(instance=input_data, schema=self.input_schema.to_dict())
            except ValidationError as exc:
                errors.append(exc.message)
        else:
            # Manual validation fallback
            errors.extend(self._manual_validate_input(input_data))

        # Semantic checks
        risk_err = validate_risk_score(input_data.get("risk_score"))
        if risk_err:
            errors.append(risk_err)

        if not input_data.get("signals"):
            warnings.append("No signals provided")

        if not input_data.get("evidence_bundle", {}).get("evidence"):
            warnings.append("No evidence items in bundle")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Output validation
    # ------------------------------------------------------------------

    def validate_output(
        self,
        output_data: Dict[str, Any],
        input_data: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        """Validate LLM output against schema and check grounding."""
        errors: List[str] = []
        warnings: List[str] = []
        suggestions: List[str] = []

        # JSON schema validation
        if _HAS_JSONSCHEMA:
            try:
                js_validate(instance=output_data, schema=self.output_schema.to_dict())
            except ValidationError as exc:
                errors.append(exc.message)
        else:
            errors.extend(self._manual_validate_output(output_data))

        # Semantic checks
        conf_err = validate_confidence(output_data.get("confidence"))
        if conf_err:
            errors.append(conf_err)

        explanations = output_data.get("explanations", [])
        exp_errors = validate_explanations(explanations)
        errors.extend(exp_errors)

        grounding_score = output_data.get("grounding_score", 0.0)
        if grounding_score < 0.5 and input_data:
            warnings.append(f"Low grounding score: {grounding_score:.2%}")

        # Citation grounding check
        missing_evidence: List[str] = []
        missing_policies: List[str] = []

        if input_data:
            evidence_ids = collect_evidence_ids(input_data)
            policy_ids = collect_policy_ids(input_data)

            for exp in explanations:
                for eid in exp.get("evidence_ids", []):
                    if eid not in evidence_ids:
                        missing_evidence.append(eid)
                for pref in exp.get("policy_references", []):
                    if pref not in policy_ids:
                        missing_policies.append(pref)

            if missing_evidence:
                warnings.append(
                    f"Ungrounded evidence citations: {', '.join(set(missing_evidence))}"
                )
            if missing_policies:
                warnings.append(
                    f"Unreferenced policy citations: {', '.join(set(missing_policies))}"
                )

        # Citation coverage
        if input_data and explanations:
            ev_ids = collect_evidence_ids(input_data)
            pol_ids = collect_policy_ids(input_data)
            citation_coverage = compute_citation_coverage(explanations, ev_ids, pol_ids)
        else:
            citation_coverage = 0.0

        # Suggestions
        suggestions = self._generate_suggestions(output_data)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            grounding_score=grounding_score,
            citation_coverage=citation_coverage,
            missing_evidence=list(set(missing_evidence)),
            missing_policies=list(set(missing_policies)),
            suggestions=suggestions,
        )

    # ------------------------------------------------------------------
    # Manual validation fallbacks
    # ------------------------------------------------------------------

    def _manual_validate_input(self, data: Dict[str, Any]) -> List[str]:
        errors: List[str] = []
        for field in ("case_id", "transaction_id", "risk_score", "risk_tier", "signals"):
            if field not in data:
                errors.append(f"Missing required field: {field}")
        if "risk_tier" in data and data["risk_tier"] not in ("HIGH", "BORDERLINE", "LOW"):
            errors.append(f"Invalid risk_tier: {data['risk_tier']}")
        if "signals" in data:
            errors.extend(validate_signals(data["signals"]))
        return errors

    def _manual_validate_output(self, data: Dict[str, Any]) -> List[str]:
        errors: List[str] = []
        for field in ("summary", "confidence", "explanations", "grounding_score"):
            if field not in data:
                errors.append(f"Missing required field: {field}")
        if "explanations" in data:
            errors.extend(validate_explanations(data["explanations"]))
        return errors

    def _generate_suggestions(self, output_data: Dict[str, Any]) -> List[str]:
        suggestions: List[str] = []
        explanations = output_data.get("explanations", [])

        if not explanations:
            suggestions.append("Add at least one explanation point")

        for exp in explanations:
            if not exp.get("evidence_ids"):
                suggestions.append(
                    f"Add evidence citations to explanation {exp.get('point_number', '?')}"
                )
            if not exp.get("policy_references"):
                suggestions.append(
                    f"Consider adding policy references to explanation {exp.get('point_number', '?')}"
                )

        if output_data.get("grounding_score", 0) < 0.7:
            suggestions.append("Improve grounding score by adding more citations")

        return suggestions
