"""LLM client service — orchestrate LLM calls with prompt building and response parsing."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Optional

from clients.llm_factory import LLMFactory
from config import ExplanationConfig
from models.explanation import (
    Citation,
    ExplanationPoint,
    ExplanationRequest,
    ExplanationResponse,
    ExplanationStatus,
    LLMRequest,
)
from utils.formatters import format_evidence, format_policies, format_signals

logger = logging.getLogger(__name__)

# System prompt for fraud explanation
_SYSTEM_PROMPT = """\
You are an AI fraud detection expert specializing in government procurement \
and financial fraud analysis. Analyze the provided data and return a JSON \
object with exactly this structure:
{
  "summary": "overall risk summary (>=20 chars)",
  "confidence": 0.0-1.0,
  "grounding_score": 0.0-1.0,
  "citations_used": <int>,
  "explanations": [
    {
      "point_number": 1,
      "detector_name": "<detector_type>",
      "sentence": "detailed explanation (>=10 chars)",
      "confidence": 0.0-1.0,
      "evidence_ids": ["EV-..."],
      "policy_references": ["GFR-..."],
      "citations": [
        {
          "citation_type": "evidence"|"policy",
          "reference_id": "...",
          "reference_text": "...",
          "relevance_score": 0.0-1.0
        }
      ]
    }
  ]
}
RULES:
- Every explanation point MUST reference at least one evidence ID or policy.
- Use only the evidence IDs and policy IDs provided in the input.
- Be specific and cite sources for every claim.
- Return ONLY valid JSON, no markdown fences."""


class LLMClientService:
    """Interact with LLM providers, build prompts, and parse responses."""

    def __init__(self, config: ExplanationConfig) -> None:
        self.config = config
        self.primary = LLMFactory.get_primary_client(config)
        self.fallback = LLMFactory.get_fallback_client(config)
        self._active_provider = config.LLM_PROVIDER

    async def generate_explanation(
        self,
        request: ExplanationRequest,
        custom_instructions: Optional[str] = None,
    ) -> ExplanationResponse:
        """Generate an explanation via the LLM with automatic fallback."""
        start = time.monotonic()

        user_prompt = self._build_user_prompt(request, custom_instructions)
        llm_req = LLMRequest(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=self.config.GROQ_TEMPERATURE,
            max_tokens=self.config.GROQ_MAX_TOKENS,
            top_p=self.config.GROQ_TOP_P,
        )

        # Try primary
        llm_resp = None
        if self.primary:
            try:
                llm_resp = await self.primary.generate(llm_req)
            except Exception as exc:
                logger.warning("Primary LLM failed: %s", exc)

        # Try fallback
        if llm_resp is None and self.fallback:
            try:
                llm_resp = await self.fallback.generate(llm_req)
                self._active_provider = "openai"
            except Exception as exc:
                logger.warning("Fallback LLM failed: %s", exc)

        if llm_resp is None:
            raise RuntimeError("All LLM providers failed")

        response = self._parse_response(llm_resp, request)
        response.generation_time_ms = (time.monotonic() - start) * 1000
        response.token_count = llm_resp.token_count
        return response

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    def _build_user_prompt(
        self,
        request: ExplanationRequest,
        custom_instructions: Optional[str] = None,
    ) -> str:
        parts = [
            f"CASE: {request.case_id}",
            f"TRANSACTION: {request.transaction_id}",
            f"RISK SCORE: {request.risk_score:.2%}",
            f"RISK TIER: {request.risk_tier}",
            "",
            "DETECTED SIGNALS:",
            format_signals(request.signals),
            "",
            "EVIDENCE:",
            format_evidence(request.evidence_bundle),
            "",
            "RELEVANT POLICIES:",
            format_policies(request.retrieved_policies),
        ]
        if custom_instructions:
            parts.extend(["", "ADDITIONAL INSTRUCTIONS:", custom_instructions])
        parts.extend([
            "",
            "Provide a JSON response with summary, confidence, grounding_score, "
            "citations_used, and explanations array.",
        ])
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_response(
        self,
        llm_resp,
        request: ExplanationRequest,
    ) -> ExplanationResponse:
        """Parse LLM JSON response into ExplanationResponse."""
        content = llm_resp.content

        # Try parsing
        data = self._extract_json(content)

        if data is not None:
            return self._from_json(data, request, llm_resp.provider, llm_resp.model)

        # Fallback: build from signals
        return self._from_signals(request, llm_resp.provider, llm_resp.model)

    def _extract_json(self, text: str) -> Optional[dict]:
        """Robustly extract a JSON object from *text*."""
        # Direct parse
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                return obj
        except (json.JSONDecodeError, TypeError):
            pass
        # Regex extraction
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                obj = json.loads(match.group())
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                pass
        return None

    def _from_json(
        self,
        data: dict,
        request: ExplanationRequest,
        provider: str,
        model: str,
    ) -> ExplanationResponse:
        explanations = []
        for idx, pt in enumerate(data.get("explanations", [])):
            citations = [
                Citation(
                    citation_type=c.get("citation_type", "evidence"),
                    reference_id=c.get("reference_id", ""),
                    reference_text=c.get("reference_text", ""),
                    relevance_score=c.get("relevance_score", 0.8),
                )
                for c in pt.get("citations", [])
            ]
            explanations.append(ExplanationPoint(
                point_number=pt.get("point_number", idx + 1),
                detector_name=pt.get("detector_name", "unknown"),
                sentence=pt.get("sentence", "No explanation available."),
                confidence=pt.get("confidence", 0.7),
                evidence_ids=pt.get("evidence_ids", []),
                policy_references=pt.get("policy_references", []),
                citations=citations,
                reasoning=pt.get("reasoning"),
            ))

        return ExplanationResponse(
            case_id=request.case_id,
            transaction_id=request.transaction_id,
            summary=data.get("summary", "No summary available."),
            confidence=data.get("confidence", 0.7),
            explanations=explanations,
            grounding_score=data.get("grounding_score", 0.7),
            citations_used=data.get("citations_used", 0),
            total_evidence=len(request.evidence_bundle.get("evidence", [])),
            total_policies=len(request.retrieved_policies),
            status=ExplanationStatus.COMPLETED,
            llm_model=model,
            llm_provider=provider,
        )

    def _from_signals(
        self,
        request: ExplanationRequest,
        provider: str,
        model: str,
    ) -> ExplanationResponse:
        """Build a best-effort response directly from signals."""
        explanations = []
        for idx, sig in enumerate(request.signals[:5]):
            dtype = sig.get("detector_type", "unknown")
            val = sig.get("signal_value", 0)
            explanations.append(ExplanationPoint(
                point_number=idx + 1,
                detector_name=dtype,
                sentence=f"The {dtype} signal (value: {val:.2%}) was detected and requires review.",
                confidence=sig.get("confidence", 0.5),
                evidence_ids=sig.get("evidence_ids", []),
            ))

        return ExplanationResponse(
            case_id=request.case_id,
            transaction_id=request.transaction_id,
            summary=f"Analysis of case {request.case_id} with risk score {request.risk_score:.2%}.",
            confidence=0.6,
            explanations=explanations,
            grounding_score=0.5,
            total_evidence=len(request.evidence_bundle.get("evidence", [])),
            total_policies=len(request.retrieved_policies),
            status=ExplanationStatus.COMPLETED,
            llm_model=model,
            llm_provider=provider,
        )

    async def close(self) -> None:
        if self.primary:
            await self.primary.close()
        if self.fallback:
            await self.fallback.close()
