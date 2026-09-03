"""Utility functions for review thresholds and fiscal adjustments."""

from datetime import date
from typing import Optional


class ThresholdUtils:
    """Stateless helpers for review-threshold logic."""

    # Default review thresholds by category
    DEFAULT_THRESHOLDS: dict[str, float] = {
        "IT_HARDWARE": 50_000,
        "SOFTWARE": 25_000,
        "SERVICES": 25_000,
        "CONSULTING": 50_000,
        "OFFICE_SUPPLIES": 10_000,
        "FACILITIES": 25_000,
        "TRANSPORTATION": 25_000,
        "OTHER": 25_000,
    }

    # Department-specific thresholds
    DEPARTMENT_THRESHOLDS: dict[str, float] = {
        "IT": 50_000,
        "FINANCE": 25_000,
        "HR": 25_000,
        "OPERATIONS": 50_000,
        "LEGAL": 25_000,
        "PROCUREMENT": 50_000,
        "FACILITIES": 25_000,
    }

    # ------------------------------------------------------------------
    # Threshold resolution
    # ------------------------------------------------------------------

    @classmethod
    def get_review_threshold(
        cls,
        category: Optional[str] = None,
        department_id: Optional[str] = None,
        vendor_risk: Optional[str] = None,
    ) -> float:
        """Return the applicable review threshold.

        Uses the *stricter* (lower) value across category and department,
        then adjusts downward for high-risk vendors.
        """
        base = 25_000.0

        # Category replaces the base (e.g. IT_HARDWARE → $50k)
        if category:
            base = cls.DEFAULT_THRESHOLDS.get(category.upper(), base)

        # Department may tighten (take the stricter/lower value)
        if department_id:
            dept = cls.DEPARTMENT_THRESHOLDS.get(department_id.upper(), base)
            base = min(base, dept)

        if vendor_risk:
            if vendor_risk == "HIGH":
                base *= 0.70
            elif vendor_risk == "MEDIUM":
                base *= 0.85

        return base

    @classmethod
    def get_fiscal_adjustment(
        cls,
        po_date: date,
        fiscal_year_end: Optional[date] = None,
    ) -> float:
        """Return a fiscal-year multiplier (< 1.0 near year-end → lower threshold)."""
        if not fiscal_year_end:
            return 1.0

        days = (fiscal_year_end - po_date).days
        if 0 <= days <= 14:
            return 0.80
        if 0 <= days <= 30:
            return 0.90
        return 1.0

    # ------------------------------------------------------------------
    # Threshold classification helpers
    # ------------------------------------------------------------------

    @classmethod
    def is_below_threshold(
        cls, amount: float, threshold: float, tolerance: float = 0.95
    ) -> bool:
        """Is *amount* at or below ``threshold × tolerance``?"""
        return amount <= threshold * tolerance

    @classmethod
    def is_suspicious_amount(
        cls, amount: float, threshold: float, tolerance: float = 0.05
    ) -> bool:
        """Is *amount* suspiciously close to (but below) *threshold*?

        Returns ``True`` when the amount falls in the 90–99 % band of
        the threshold — the classic split-just-under-the-limit signal.
        """
        if threshold == 0:
            return False
        ratio = amount / threshold
        return 0.90 <= ratio <= 0.99

    @classmethod
    def get_threshold_band(cls, amount: float, threshold: float) -> str:
        """Classify *amount* into a named band relative to *threshold*."""
        if threshold == 0:
            return "UNKNOWN"
        ratio = amount / threshold
        if ratio >= 0.95:
            return "NEAR_THRESHOLD"
        if ratio >= 0.75:
            return "HIGH_BAND"
        if ratio >= 0.50:
            return "MEDIUM_BAND"
        if ratio >= 0.25:
            return "LOW_BAND"
        return "VERY_LOW_BAND"
