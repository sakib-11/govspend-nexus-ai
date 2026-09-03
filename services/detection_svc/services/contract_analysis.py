"""Service for analysing contract-splitting patterns."""

import asyncio
import math
from typing import Any, Dict, List

from ..analytics.pattern_detector import PatternDetector
from ..analytics.window_analyzer import WindowAnalyzer
from ..models.contract_splitting import (
    ContractSplittingGroup,
    ContractSplittingResult,
    PurchaseOrder,
    SplittingSeverity,
)
from ..utils.logging import get_logger

logger = get_logger(__name__)


class ContractAnalysisService:
    """Orchestrates window analysis, pattern detection, and result construction."""

    def __init__(self) -> None:
        self.window_analyzer = WindowAnalyzer()
        self.pattern_detector = PatternDetector()

        # Tuning knobs
        self.window_days: int = 14
        self.min_pos_for_splitting: int = 3
        self.max_groups_per_vendor: int = 20

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def analyze_vendor_department(
        self,
        vendor_id: str,
        department_id: str,
        purchase_orders: List[PurchaseOrder],
        review_threshold: float,
    ) -> ContractSplittingResult:
        """Full analysis for one vendor × department pair."""
        start = asyncio.get_event_loop().time()

        try:
            below = [po for po in purchase_orders if po.amount < review_threshold]

            if len(below) < self.min_pos_for_splitting:
                return self._empty_result(
                    vendor_id, department_id, review_threshold, purchase_orders
                )

            groups = self.window_analyzer.analyze_windows(
                below, vendor_id, department_id, review_threshold, self.window_days
            )

            if not groups:
                return self._empty_result(
                    vendor_id, department_id, review_threshold, purchase_orders
                )

            pattern_analysis = self.pattern_detector.analyze_patterns(groups)
            high_risk = [g for g in groups if g.is_high_risk]
            total_split_amount = sum(g.total_amount for g in high_risk)

            signal_value = self._calculate_signal(groups, review_threshold)
            confidence = self._calculate_confidence(groups)
            severity = self._determine_severity(signal_value)
            evidence = self._build_evidence(groups, pattern_analysis)
            recommendations = self._build_recommendations(groups, severity)

            # Aggregate detected patterns
            all_patterns: list = []
            for g in groups:
                for p in g.splitting_patterns:
                    if p not in all_patterns:
                        all_patterns.append(p)

            vendor_name = purchase_orders[0].vendor_name if purchase_orders else "Unknown"
            dept_name = purchase_orders[0].department_name if purchase_orders else "Unknown"

            elapsed = (asyncio.get_event_loop().time() - start) * 1000

            return ContractSplittingResult(
                signal_value=signal_value,
                confidence=confidence,
                vendor_id=vendor_id,
                vendor_name=vendor_name,
                department_id=department_id,
                department_name=dept_name,
                review_threshold=review_threshold,
                splitting_groups=groups,
                high_risk_groups=high_risk,
                total_split_amount=total_split_amount,
                total_splitting_groups=len(groups),
                total_purchase_orders=len(purchase_orders),
                total_po_count=len(purchase_orders),
                detected_patterns=all_patterns,
                severity=severity,
                evidence=evidence,
                recommendations=recommendations,
                window_analysis={
                    "window_days": self.window_days,
                    "groups_analyzed": len(groups),
                    "high_risk_groups": len(high_risk),
                },
                pattern_analysis=pattern_analysis,
                processing_time_ms=int(elapsed),
            )

        except Exception as exc:
            logger.error("Contract analysis failed: %s", exc, exc_info=True)
            raise

    # ------------------------------------------------------------------
    # Signal
    # ------------------------------------------------------------------

    def _calculate_signal(
        self, groups: List[ContractSplittingGroup], threshold: float
    ) -> float:
        high_risk = [g for g in groups if g.is_high_risk]
        if not high_risk or threshold <= 0:
            return 0.0

        total_exceeded = 0.0
        for g in high_risk[:5]:
            if g.threshold_exceeded:
                total_exceeded += max(0.0, (g.total_amount - threshold) / threshold)

        signal = min(1.0, total_exceeded / 5)

        bonus = sum(0.05 for g in high_risk if len(g.splitting_patterns) >= 2)
        return min(1.0, signal + bonus)

    # ------------------------------------------------------------------
    # Confidence
    # ------------------------------------------------------------------

    def _calculate_confidence(
        self, groups: List[ContractSplittingGroup]
    ) -> float:
        if not groups:
            return 0.0

        n = len(groups)
        if n >= 10:
            size_score = 0.90
        elif n >= 5:
            size_score = 0.70
        elif n >= 3:
            size_score = 0.50
        else:
            size_score = 0.30

        patterns_found: set = set()
        for g in groups:
            patterns_found.update(g.splitting_patterns)

        pf = len(patterns_found)
        if pf >= 3:
            pattern_score = 0.90
        elif pf >= 2:
            pattern_score = 0.70
        elif pf >= 1:
            pattern_score = 0.50
        else:
            pattern_score = 0.30

        evidence_score = min(
            1.0, 0.50 + 0.10 * sum(1 for g in groups if g.threshold_exceeded)
        )

        return min(
            1.0,
            max(0.0, size_score * 0.4 + pattern_score * 0.4 + evidence_score * 0.2),
        )

    # ------------------------------------------------------------------
    # Severity
    # ------------------------------------------------------------------

    @staticmethod
    def _determine_severity(signal_value: float) -> SplittingSeverity:
        if signal_value >= 0.90:
            return SplittingSeverity.CRITICAL
        if signal_value >= 0.70:
            return SplittingSeverity.HIGH
        if signal_value >= 0.40:
            return SplittingSeverity.MEDIUM
        if signal_value >= 0.20:
            return SplittingSeverity.LOW
        return SplittingSeverity.NONE

    # ------------------------------------------------------------------
    # Evidence
    # ------------------------------------------------------------------

    @staticmethod
    def _build_evidence(
        groups: List[ContractSplittingGroup],
        pattern_analysis: Dict[str, Any],
    ) -> List[str]:
        evidence: List[str] = []
        high_risk = [g for g in groups if g.is_high_risk]

        if high_risk:
            po_total = sum(g.po_count for g in high_risk)
            evidence.append(
                f"Found {len(high_risk)} high-risk splitting groups "
                f"involving {po_total} purchase orders"
            )

        exceeding = [g for g in groups if g.threshold_exceeded]
        if exceeding:
            total = sum(g.amount_exceeded_by for g in exceeding)
            evidence.append(
                f"{len(exceeding)} groups exceeded the review threshold "
                f"by a total of ${total:,.2f}"
            )

        patterns = pattern_analysis.get("patterns", [])
        if patterns:
            names = [p.value if hasattr(p, "value") else str(p) for p in patterns]
            evidence.append(f"Detected patterns: {', '.join(names)}")

        if pattern_analysis.get("high_risk_vendors"):
            evidence.append(
                f"Vendor has {len(pattern_analysis['high_risk_vendors'])} high-risk "
                "splitting patterns across departments"
            )

        seasonal = pattern_analysis.get("seasonal_patterns", {})
        if seasonal.get("peak_count", 0) > 0:
            peaks = seasonal.get("seasonal_peaks", [])
            peak_months = [p["month"] if isinstance(p, dict) else str(p) for p in peaks[:3]]
            evidence.append(f"Seasonal splitting peaks detected in {', '.join(peak_months)}")

        for i, g in enumerate(high_risk[:3]):
            pat_names = [p.value if hasattr(p, "value") else str(p) for p in g.splitting_patterns]
            evidence.append(
                f"Group {i + 1}: {g.po_count} POs totalling ${g.total_amount:,.2f} "
                f"({', '.join(pat_names)})"
            )

        return evidence

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------

    @staticmethod
    def _build_recommendations(
        groups: List[ContractSplittingGroup],
        severity: SplittingSeverity,
    ) -> List[str]:
        recs: List[str] = []

        if severity == SplittingSeverity.CRITICAL:
            recs.append("URGENT: Contract splitting detected — immediate investigation required")
            recs.append("Review all related purchase orders and contracts")
            recs.append("Consider consolidating contracts and expanding vendor due diligence")
        elif severity == SplittingSeverity.HIGH:
            recs.append("High-risk contract splitting detected — escalate to procurement review")
            recs.append("Analyze vendor relationships and approval patterns")
            recs.append("Review procurement policies for this department")
        elif severity == SplittingSeverity.MEDIUM:
            recs.append("Medium-risk contract splitting detected — recommend secondary review")
            recs.append("Monitor future purchase orders from this vendor")
            recs.append("Review threshold policies and vendor management")
        elif severity == SplittingSeverity.LOW:
            recs.append("Low-risk splitting pattern detected — continue monitoring")

        high_risk = [g for g in groups if g.is_high_risk]
        if high_risk:
            recs.append("Implement automated detection for future contract splitting")
            recs.append("Review vendor approval workflows for this department")

        return recs

    # ------------------------------------------------------------------
    # Empty result
    # ------------------------------------------------------------------

    def _empty_result(
        self,
        vendor_id: str,
        department_id: str,
        threshold: float,
        pos: List[PurchaseOrder],
    ) -> ContractSplittingResult:
        vendor_name = pos[0].vendor_name if pos else "Unknown"
        dept_name = pos[0].department_name if pos else "Unknown"

        return ContractSplittingResult(
            signal_value=0.0,
            confidence=0.0,
            vendor_id=vendor_id,
            vendor_name=vendor_name,
            department_id=department_id,
            department_name=dept_name,
            review_threshold=threshold,
            splitting_groups=[],
            high_risk_groups=[],
            total_split_amount=0.0,
            total_splitting_groups=0,
            total_purchase_orders=len(pos),
            total_po_count=len(pos),
            detected_patterns=[],
            severity=SplittingSeverity.NONE,
            evidence=["No contract splitting detected"],
            recommendations=["Continue monitoring"],
            window_analysis={},
            pattern_analysis={},
        )
