"""Cross-group pattern analysis for contract-splitting detection."""

import math
from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Any, Dict, List

from ..models.contract_splitting import (
    ContractSplittingGroup,
    PurchaseOrder,
    SplittingPattern,
)
from ..utils.logging import get_logger

logger = get_logger(__name__)


class PatternDetector:
    """Detect patterns across multiple splitting groups and time-series."""

    def __init__(self) -> None:
        self.min_pattern_samples: int = 3
        self.time_clustering_threshold: int = 3  # days

    # ------------------------------------------------------------------
    # Cross-group analysis
    # ------------------------------------------------------------------

    def analyze_patterns(
        self, groups: List[ContractSplittingGroup]
    ) -> Dict[str, Any]:
        """Aggregate pattern statistics across all groups."""
        if not groups:
            return {
                "patterns": [],
                "pattern_counts": {},
                "high_risk_vendors": [],
                "seasonal_patterns": {},
                "total_groups": 0,
                "average_po_count": 0,
            }

        pattern_counts: Counter = Counter()
        for g in groups:
            for p in g.splitting_patterns:
                pattern_counts[p] += 1

        # Vendor concentration
        vendor_patterns: Dict[str, List] = defaultdict(list)
        for g in groups:
            vendor_patterns[g.vendor_id].extend(g.splitting_patterns)

        high_risk_vendors = [
            vid for vid, pats in vendor_patterns.items() if len(pats) >= 5
        ]

        seasonal = self._analyze_seasonal_patterns(groups)

        avg_po = sum(g.po_count for g in groups) / len(groups) if groups else 0

        return {
            "patterns": list(pattern_counts.keys()),
            "pattern_counts": dict(pattern_counts),
            "high_risk_vendors": high_risk_vendors,
            "seasonal_patterns": seasonal,
            "total_groups": len(groups),
            "average_po_count": avg_po,
        }

    # ------------------------------------------------------------------
    # Seasonal patterns
    # ------------------------------------------------------------------

    def _analyze_seasonal_patterns(
        self, groups: List[ContractSplittingGroup]
    ) -> Dict[str, Any]:
        if not groups:
            return {}

        monthly: Dict[str, List[ContractSplittingGroup]] = defaultdict(list)
        for g in groups:
            if g.purchase_orders:
                earliest = min(po.po_date for po in g.purchase_orders)
                monthly[earliest.strftime("%Y-%m")].append(g)

        counts = {m: len(gs) for m, gs in monthly.items()}
        vals = list(counts.values())
        if not vals:
            return {"monthly_counts": {}, "average": 0, "std": 0, "seasonal_peaks": [], "peak_count": 0}

        avg = sum(vals) / len(vals)
        variance = sum((c - avg) ** 2 for c in vals) / len(vals)
        std = math.sqrt(variance)

        peaks = []
        for m, c in counts.items():
            if std > 0 and c > avg + 1.5 * std:
                peaks.append({
                    "month": m,
                    "count": c,
                    "deviation": (c - avg) / std,
                })

        return {
            "monthly_counts": counts,
            "average": avg,
            "std": std,
            "seasonal_peaks": peaks,
            "peak_count": len(peaks),
        }

    # ------------------------------------------------------------------
    # Sequential splitting detection
    # ------------------------------------------------------------------

    def detect_sequential_splitting(
        self,
        purchase_orders: List[PurchaseOrder],
        vendor_id: str,
        department_id: str,
        threshold: float,
    ) -> List[ContractSplittingGroup]:
        """Detect consecutive-day splitting sequences."""
        if len(purchase_orders) < self.min_pattern_samples:
            return []

        sorted_pos = sorted(purchase_orders, key=lambda p: p.po_date)
        results: List[ContractSplittingGroup] = []
        current: List[PurchaseOrder] = []
        current_start: date | None = None

        for po in sorted_pos:
            if po.amount >= threshold:
                if current:
                    self._finalize_group(
                        current, vendor_id, department_id, threshold, results
                    )
                    current = []
                    current_start = None
                continue

            if not current:
                current = [po]
                current_start = po.po_date
            else:
                days_diff = (po.po_date - current_start).days
                if days_diff <= self.time_clustering_threshold:
                    current.append(po)
                else:
                    self._finalize_group(
                        current, vendor_id, department_id, threshold, results
                    )
                    current = [po]
                    current_start = po.po_date

        if current:
            self._finalize_group(
                current, vendor_id, department_id, threshold, results
            )

        return results

    def _finalize_group(
        self,
        pos: List[PurchaseOrder],
        vendor_id: str,
        department_id: str,
        threshold: float,
        results: List[ContractSplittingGroup],
    ) -> None:
        if len(pos) < self.min_pattern_samples:
            return

        group = ContractSplittingGroup(
            group_id=f"{vendor_id}_{department_id}_seq",
            vendor_id=vendor_id,
            vendor_name=pos[0].vendor_name,
            department_id=department_id,
            department_name=pos[0].department_name,
            window_start=min(p.po_date for p in pos),
            window_end=max(p.po_date for p in pos),
            purchase_orders=pos,
            review_threshold=threshold,
            po_count=len(pos),
            total_amount=0.0,
            average_amount=0.0,
            min_amount=0.0,
            max_amount=0.0,
            std_amount=0.0,
        )
        group.calculate_metrics()
        group.splitting_patterns = [SplittingPattern.SEQUENTIAL_SPLITTING]
        group.risk_score = self._sequential_risk(group)
        group.is_high_risk = group.risk_score > 0.7

        if group.threshold_exceeded or len(group.splitting_patterns) > 1:
            results.append(group)

    def _sequential_risk(self, group: ContractSplittingGroup) -> float:
        if not group.purchase_orders:
            return 0.0

        score = 0.0

        po_factor = min(1.0, (group.po_count - self.min_pattern_samples) / 5)
        score += po_factor * 0.30

        if group.average_days_between is not None:
            density = max(0.0, 1.0 - group.average_days_between / 7)
            score += density * 0.30

        if group.threshold_exceeded and group.review_threshold > 0:
            exceed = min(1.0, group.amount_exceeded_by / group.review_threshold)
            score += exceed * 0.40

        return min(1.0, score)
