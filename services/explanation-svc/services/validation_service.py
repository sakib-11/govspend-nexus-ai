"""Validation service — validate LLM explanations against input data."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

from config import ExplanationConfig
from models.explanation import ExplanationResponse, ExplanationValidationResult
from utils.validators import collect_evidence_ids, collect_policy_ids

logger = logging.getLogger(__name__)


class ValidationService:
    """Validate explanation responses for grounding, citations, and structure."""

    def __init__(self, config: ExplanationConfig) -> None:
        self.config = config

    async def validate(
        self,
        explanation: ExplanationResponse,
        input_data: Dict[str, Any],
    ) -> ExplanationValidationResult:
        """Run all validation checks and return a result."""
        errors: List[str] = []
        warnings: List[str] = []
        suggestions: List[str] = []

        self._check_structure(explanation, errors, warnings)
        self._check_citations(explanation, input_data, errors, warnings)
        self._check_grounding(explanation, errors, warnings)

        grounding_score = self._calc_grounding(explanation)
        confidence_score = explanation.confidence

        if confidence_score < self.config.MIN_CONFIDENCE_THRESHOLD:
            errors.append(f"Confidence {confidence_score:.2%} below threshold {self.config.MIN_CONFIDENCE_THRESHOLD:.2%}")

        if grounding_score < self.config.MIN_GROUNDING_SCORE:
            errors.append(f"Grounding {grounding_score:.2%} below threshold {self.config.MIN_GROUNDING_SCORE:.2%}")

        uncited = self._uncited_points(explanation)
        if uncited:
            warnings.append(f"{len(uncited)} explanation point(s) have no citations")

        missing_ev = self._missing_evidence(explanation, input_data)
        missing_pol = self._missing_policies(explanation, input_data)
        if missing_ev:
            warnings.append(f"Ungrounded evidence refs: {', '.join(missing_ev)}")
        if missing_pol:
            warnings.append(f"Unreferenced policy refs: {', '.join(missing_pol)}")

        suggestions = self._suggest(explanation, errors, warnings)

        return ExplanationValidationResult(
            is_valid=len(errors) == 0,
            grounding_score=grounding_score,
            confidence_score=confidence_score,
            errors=errors,
            warnings=warnings,
            missing_evidence=missing_ev,
            missing_policies=missing_pol,
            uncited_sentences=uncited,
            suggestions=suggestions,
        )

    # ------------------------------------------------------------------
    # Internal checks
    # ------------------------------------------------------------------

    def _check_structure(self, exp: ExplanationResponse, errors: List[str], warnings: List[str]) -> None:
        if not exp.summary:
            errors.append("Missing summary")
        elif len(exp.summary) < 20:
            warnings.append("Summary is very short (<20 chars)")
        if not exp.explanations:
            errors.append("No explanation points provided")
        for pt in exp.explanations:
            if not pt.sentence:
                errors.append(f"Point {pt.point_number} has empty sentence")
            if not (0 <= pt.confidence <= 1):
                errors.append(f"Point {pt.point_number} has invalid confidence")

    def _check_citations(self, exp: ExplanationResponse, input_data: Dict[str, Any], errors: List[str], warnings: List[str]) -> None:
        available_ev = collect_evidence_ids(input_data)
        available_pol = collect_policy_ids(input_data)
        for pt in exp.explanations:
            for eid in pt.evidence_ids:
                if eid not in available_ev:
                    errors.append(f"Evidence '{eid}' not in input data")
            for pref in pt.policy_references:
                if pref not in available_pol:
                    errors.append(f"Policy '{pref}' not in input data")
            for cit in pt.citations:
                if cit.citation_type == "evidence" and cit.reference_id not in available_ev:
                    errors.append(f"Citation evidence '{cit.reference_id}' not in input")
                elif cit.citation_type == "policy" and cit.reference_id not in available_pol:
                    errors.append(f"Citation policy '{cit.reference_id}' not in input")

    def _check_grounding(self, exp: ExplanationResponse, errors: List[str], warnings: List[str]) -> None:
        if self.config.REQUIRE_CITATIONS:
            for pt in exp.explanations:
                if not pt.evidence_ids and not pt.policy_references and not pt.citations:
                    errors.append(f"Point {pt.point_number} has no citations")

    def _calc_grounding(self, exp: ExplanationResponse) -> float:
        if not exp.explanations:
            return 0.0
        grounded = sum(
            1 for pt in exp.explanations
            if pt.evidence_ids or pt.policy_references or pt.citations
        )
        return grounded / len(exp.explanations)

    def _uncited_points(self, exp: ExplanationResponse) -> List[int]:
        return [
            pt.point_number for pt in exp.explanations
            if not pt.evidence_ids and not pt.policy_references and not pt.citations
        ]

    def _missing_evidence(self, exp: ExplanationResponse, input_data: Dict[str, Any]) -> List[str]:
        available = collect_evidence_ids(input_data)
        referenced: Set[str] = set()
        for pt in exp.explanations:
            referenced.update(pt.evidence_ids)
            for c in pt.citations:
                if c.citation_type == "evidence":
                    referenced.add(c.reference_id)
        return sorted(referenced - available)

    def _missing_policies(self, exp: ExplanationResponse, input_data: Dict[str, Any]) -> List[str]:
        available = collect_policy_ids(input_data)
        referenced: Set[str] = set()
        for pt in exp.explanations:
            referenced.update(pt.policy_references)
            for c in pt.citations:
                if c.citation_type == "policy":
                    referenced.add(c.reference_id)
        return sorted(referenced - available)

    def _suggest(self, exp: ExplanationResponse, errors: List[str], warnings: List[str]) -> List[str]:
        s: List[str] = []
        if errors:
            s.append("Fix validation errors before proceeding")
        if not exp.explanations:
            s.append("Add at least one explanation point")
        for pt in exp.explanations:
            if not pt.evidence_ids and not pt.policy_references:
                s.append(f"Add citations to point {pt.point_number}")
        if exp.grounding_score < 0.8:
            s.append("Improve grounding by adding more citations")
        return s
