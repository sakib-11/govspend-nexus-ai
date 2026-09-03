"""Utility functions for time calculations and velocity scoring."""

from datetime import date, datetime, timedelta


class TimeUtils:
    """Stateless helpers for time arithmetic and velocity metrics."""

    # ------------------------------------------------------------------
    # Business hours
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_business_hours(
        start_date: date,
        end_date: date,
        work_hours_per_day: float = 8.0,
    ) -> float:
        """Count business days (Mon–Fri) between *start* and *end*, then multiply."""
        if start_date > end_date:
            start_date, end_date = end_date, start_date
        business_days = 0
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:
                business_days += 1
            current += timedelta(days=1)
        return business_days * work_hours_per_day

    @staticmethod
    def calculate_calendar_hours(start_date: date, end_date: date) -> float:
        """Total calendar hours between two dates."""
        return (end_date - start_date).total_seconds() / 3600

    # ------------------------------------------------------------------
    # Buckets / labels
    # ------------------------------------------------------------------

    @staticmethod
    def get_time_of_day_bucket(hours: float) -> str:
        if hours < 6:
            return "night"
        if hours < 12:
            return "morning"
        if hours < 18:
            return "afternoon"
        return "evening"

    @staticmethod
    def get_day_of_week_bucket(d: date) -> str:
        return "weekend" if d.weekday() >= 5 else "weekday"

    @staticmethod
    def get_week_number(d: date) -> int:
        return d.isocalendar()[1]

    @staticmethod
    def get_month_name(d: date) -> str:
        return d.strftime("%B")

    # ------------------------------------------------------------------
    # Velocity metrics
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_velocity_ratio(approval_time: float, median_time: float) -> float:
        """``actual / median`` — values < 1.0 mean *faster* than median."""
        if median_time <= 0:
            return 0.0
        return approval_time / median_time

    @staticmethod
    def calculate_linear_score(
        approval_time: float,
        median_time: float,
        max_score: float = 1.0,
    ) -> float:
        """Linear velocity score: ``min(max_score, 0.5 / ratio)``.

        A ratio of 0.5 (half the median) → score 1.0.
        A ratio of 1.0 (same as median) → score 0.5.
        A ratio of 2.0 (double the median) → score 0.25.
        """
        if median_time <= 0:
            return 0.0
        ratio = approval_time / median_time
        if ratio == 0:
            return max_score
        return min(max_score, 0.5 / ratio)

    @staticmethod
    def calculate_acceleration_factor(
        approval_time: float, median_time: float
    ) -> float:
        """``median / actual`` — how many × faster than median."""
        if median_time <= 0 or approval_time <= 0:
            return 0.0
        return median_time / approval_time

    @staticmethod
    def get_velocity_band(approval_time: float, median_time: float) -> str:
        """Classify the approval speed into a named band."""
        if median_time <= 0:
            return "UNKNOWN"
        ratio = approval_time / median_time
        if ratio < 0.25:
            return "EXTREME_FAST"
        if ratio < 0.50:
            return "VERY_FAST"
        if ratio < 0.75:
            return "MODERATE_FAST"
        if ratio < 1.25:
            return "NORMAL"
        if ratio < 1.75:
            return "MODERATE_SLOW"
        if ratio < 2.50:
            return "VERY_SLOW"
        return "EXTREME_SLOW"
