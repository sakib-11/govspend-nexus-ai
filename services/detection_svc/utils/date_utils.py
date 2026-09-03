"""Date and fiscal-year utility functions."""

import calendar
from datetime import date, datetime, timedelta
from typing import List, Tuple


class DateUtils:
    """Stateless helpers for date arithmetic and fiscal-year logic."""

    # ------------------------------------------------------------------
    # Fiscal year
    # ------------------------------------------------------------------

    @staticmethod
    def get_fiscal_year_end(date_obj: date, fiscal_year_end_month: int = 6) -> date:
        """Return the fiscal-year-end date that contains *date_obj*.

        Default: June 30 (US state/local pattern).
        """
        year = date_obj.year
        if date_obj.month > fiscal_year_end_month:
            return date(year + 1, fiscal_year_end_month, 30)
        return date(year, fiscal_year_end_month, 30)

    @staticmethod
    def get_fiscal_period(date_obj: date, fiscal_year_end_month: int = 6) -> str:
        """Return a label like ``FY2025-Q2``."""
        fy_end = DateUtils.get_fiscal_year_end(date_obj, fiscal_year_end_month)
        fy_year = fy_end.year
        month = date_obj.month

        if month <= 3:
            quarter = 3 if fy_year == date_obj.year else 1
        elif month <= 6:
            quarter = 4 if fy_year == date_obj.year else 2
        elif month <= 9:
            quarter = 1
        else:
            quarter = 2

        return f"FY{fy_year}-Q{quarter}"

    @staticmethod
    def days_to_fiscal_end(
        date_obj: date, fiscal_year_end_month: int = 6
    ) -> int:
        """Days remaining until the fiscal year end."""
        fy_end = DateUtils.get_fiscal_year_end(date_obj, fiscal_year_end_month)
        return (fy_end - date_obj).days

    @staticmethod
    def is_fiscal_year_end_period(
        date_obj: date,
        days_window: int = 14,
        fiscal_year_end_month: int = 6,
    ) -> Tuple[bool, int]:
        """Is *date_obj* within *days_window* of fiscal year end?

        Returns ``(is_fiscal_end, days_remaining)``.
        """
        remaining = DateUtils.days_to_fiscal_end(date_obj, fiscal_year_end_month)
        return (0 <= remaining <= days_window), remaining

    # ------------------------------------------------------------------
    # Holidays
    # ------------------------------------------------------------------

    @staticmethod
    def get_holidays(year: int, country: str = "US") -> List[date]:
        """Federal holidays for *year* (US)."""
        holidays: List[date] = [
            date(year, 1, 1),  # New Year
            DateUtils._nth_weekday(year, 1, 3, calendar.MONDAY),  # MLK
            DateUtils._nth_weekday(year, 2, 3, calendar.MONDAY),  # Presidents
            DateUtils._last_weekday(year, 5, calendar.MONDAY),  # Memorial
            date(year, 7, 4),  # Independence
            DateUtils._nth_weekday(year, 9, 1, calendar.MONDAY),  # Labor
            DateUtils._nth_weekday(year, 10, 2, calendar.MONDAY),  # Columbus
            date(year, 11, 11),  # Veterans
            DateUtils._nth_weekday(year, 11, 4, calendar.THURSDAY),  # Thanksgiving
            date(year, 12, 25),  # Christmas
        ]
        return holidays

    @staticmethod
    def _nth_weekday(year: int, month: int, nth: int, weekday: int) -> date:
        """Return the *n*-th occurrence of *weekday* in *month*/*year*."""
        first = date(year, month, 1)
        offset = (weekday - first.weekday()) % 7
        return date(year, month, 1 + offset + (nth - 1) * 7)

    @staticmethod
    def _get_last_weekday(year: int, month: int, weekday: int) -> date:
        """Return the last occurrence of *weekday* in *month*/*year*."""
        last_day = date(year, month, calendar.monthrange(year, month)[1])
        offset = (last_day.weekday() - weekday) % 7
        return date(year, month, last_day.day - offset)

    # keep alias for internal use
    _last_weekday = _get_last_weekday

    # ------------------------------------------------------------------
    # Business-day helpers
    # ------------------------------------------------------------------

    @staticmethod
    def is_weekend(d: date) -> bool:
        return d.weekday() >= 5

    @staticmethod
    def is_holiday(d: date, country: str = "US") -> bool:
        return d in DateUtils.get_holidays(d.year, country)

    @staticmethod
    def get_business_days(start: date, end: date) -> int:
        """Count weekdays (Mon–Fri) between *start* and *end* inclusive."""
        count = 0
        current = start
        while current <= end:
            if current.weekday() < 5:
                count += 1
            current += timedelta(days=1)
        return count

    @staticmethod
    def get_working_hours(
        start: date, end: date, hours_per_day: float = 8.0
    ) -> float:
        return DateUtils.get_business_days(start, end) * hours_per_day
