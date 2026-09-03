"""Sliding-window analysis for contract-splitting patterns."""

import math
from datetime import date, timedelta
from typing import List, Optional

from ..models.contract_splitting import (
    ContractSplittingGroup,
    PurchaseOrder,
    SplittingPattern,
)
from ..utils.logging import get_logger
from ..utils.threshold_utils import ThresholdUtils

logger = get_logger(__name__)


class WindowAnalyzer:
    """Analyze sliding time windows for contract-splitting behaviour."""

    def __init__(self) -> None:
        self.min_pos_for_splitting: int = 3
        self.default_window_days: int = 14

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_windows(
        self,
        purchase_orders: List[PurchaseOrder],
        vendor_id: str,
        department_id: str,
        threshold: float,
        window_days: int = 14,
    ) -> List[ContractSplittingGroup]:
        """Return splitting groups found by sliding a window over *purchase_orders*."""
        if not purchase_orders or len(purchase_orders) < self.min_pos_for_splitting:
            return []

        sorted_pos = sorted(purchase_orders, key=lambda p: p.po_date)
        windows: List[ContractSplittingGroup] = []

        for i in range(len(sorted_pos)):
            window_start = sorted_pos[i].po_date
            window_end = window_start + timedelta(days=window_days)

            # Collect POs inside (window_start, window_end]
            window_pos = [
                po
                for po in sorted_pos[i + 1 :]
                if window_start < po.po_date <= window_end
            ]

            # Include the anchor PO if below threshold
            if sorted_pos[i].amount < threshold:
                window_pos.append(sorted_pos[i])

            if len(window_pos) < self.min_pos_for_splitting:
                continue

            group = self._create_group(
                window_pos, vendor_id, department_id, threshold,
                window_start, window_end,
            )
            if group is None:
                continue

            merged = self._merge_with_existing(windows, group)
            if not merged:
                windows.append(group)

        valid = [g for g in windows if self._is_valid_splitting_group(g)]
        valid.sort(key=lambda g: g.risk_score, reverse=True)
        return valid

    # ------------------------------------------------------------------
    # Group creation
    # ------------------------------------------------------------------

    def _create_group(
        self,
        pos: List[PurchaseOrder],
        vendor_id: str,
        department_id: str,
        threshold: float,
        window_start: date,
        window_end: date,
    ) -> Optional[ContractSplittingGroup]:
        if not pos:
            return None

        group = ContractSplittingGroup(
            group_id=f"{vendor_id}_{department_id}_{window_start.isoformat()}",
            vendor_id=vendor_id,
            vendor_name=pos[0].vendor_name,
            department_id=department_id,
            department_name=pos[0].department_name,
            window_start=window_start,
            window_end=window_end,
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
        group.splitting_patterns = self._detect_patterns(group)
        group.risk_score = self._calculate_risk_score(group)
        group.is_high_risk = group.risk_score > 0.7
        return group

    # ------------------------------------------------------------------
    # Merging
    # ------------------------------------------------------------------

    def _merge_with_existing(
        self,
        existing: List[ContractSplittingGroup],
        new_group: ContractSplittingGroup,
    ) -> bool:
        for g in existing:
            if g.vendor_id != new_group.vendor_id:
                continue
            if g.department_id != new_group.department_id:
                continue
            if self._windows_overlap(
                g.window_start, g.window_end,
                new_group.window_start, new_group.window_end,
            ):
                self._merge_groups(g, new_group)
                return True
        return False

    @staticmethod
    def _windows_overlap(s1: date, e1: date, s2: date, e2: date) -> bool:
        return max(s1, s2) <= min(e1, e2)

    def _merge_groups(
        self,
        target: ContractSplittingGroup,
        source: ContractSplittingGroup,
    ) -> None:
        existing_ids = {po.po_id for po in target.purchase_orders}
        for po in source.purchase_orders:
            if po.po_id not in existing_ids:
                target.purchase_orders.append(po)
                existing_ids.add(po.po_id)

        if source.window_start < target.window_start:
            target.window_start = source.window_start
        if source.window_end > target.window_end:
            target.window_end = source.window_end

        target.calculate_metrics()
        target.splitting_patterns = list(
            set(target.splitting_patterns + source.splitting_patterns)
        )
        target.risk_score = self._calculate_risk_score(target)
        target.is_high_risk = target.risk_score > 0.7

    # ------------------------------------------------------------------
    # Pattern detection (per group)
    # ------------------------------------------------------------------

    def _detect_patterns(
        self, group: ContractSplittingGroup
    ) -> List[SplittingPattern]:
        patterns: List[SplittingPattern] = []

        if len(group.purchase_orders) < self.min_pos_for_splitting:
            return patterns

        # 1. Temporal clustering
        if group.average_days_between is not None and group.average_days_between <= 2:
            patterns.append(SplittingPattern.TEMPORAL_CLUSTERING)

        # 2. Amount alignment (low CV)
        if group.average_amount > 0 and group.std_amount > 0:
            cv = group.std_amount / group.average_amount
            if cv < 0.20:
                patterns.append(SplittingPattern.AMOUNT_ALIGNMENT)

        # 3. Sequential splitting
        if group.is_sequential:
            patterns.append(SplittingPattern.SEQUENTIAL_SPLITTING)

        # 4. Frequency spike
        if (
            group.po_count >= 5
            and group.average_days_between is not None
            and group.average_days_between <= 1
        ):
            patterns.append(SplittingPattern.FREQUENCY_SPIKE)

        # 5. Rounding pattern (many POs just below threshold)
        threshold = group.review_threshold
        near = sum(
            1
            for po in group.purchase_orders
            if po.amount < threshold
            and (threshold - po.amount) / threshold < 0.10
        )
        if near >= 2:
            patterns.append(SplittingPattern.ROUNDING_PATTERN)

        return patterns

    # ------------------------------------------------------------------
    # Risk scoring
    # ------------------------------------------------------------------

    def _calculate_risk_score(self, group: ContractSplittingGroup) -> float:
        if not group.purchase_orders:
            return 0.0

        score = 0.0

        # Factor 1: threshold exceedance (40 %)
        if group.threshold_exceeded and group.review_threshold > 0:
            ratio = min(1.0, group.amount_exceeded_by / group.review_threshold)
            score += ratio * 0.40

        # Factor 2: PO count (20 %)
        po_factor = min(1.0, (group.po_count - self.min_pos_for_splitting) / 5)
        score += po_factor * 0.20

        # Factor 3: pattern count (20 %)
        pattern_factor = min(1.0, len(group.splitting_patterns) / 3)
        score += pattern_factor * 0.20

        # Factor 4: temporal proximity (10 %)
        if group.average_days_between is not None:
            temporal = max(0.0, 1.0 - group.average_days_between / 14)
            score += temporal * 0.10

        # Factor 5: amount consistency (10 %)
        if group.average_amount > 0 and group.std_amount > 0:
            consistency = max(0.0, 1.0 - group.std_amount / group.average_amount)
            score += consistency * 0.10

        return min(1.0, score)

    def _is_valid_splitting_group(
        self, group: ContractSplittingGroup
    ) -> bool:
        if len(group.purchase_orders) < self.min_pos_for_splitting:
            return False
        if group.threshold_exceeded:
            return True
        if len(group.splitting_patterns) >= 2:
            return True
        for po in group.purchase_orders:
            if po.review_threshold and ThresholdUtils.is_suspicious_amount(
                po.amount, po.review_threshold
            ):
                return True
        return False
