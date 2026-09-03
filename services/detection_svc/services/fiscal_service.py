"""Service for fiscal-year calculations and context."""

from datetime import date
from typing import Any, Dict, Tuple

from ..utils.date_utils import DateUtils
from ..utils.logging import get_logger

logger = get_logger(__name__)


class FiscalService:
    """Provides fiscal-year context, amplification factors, and seasonal effects."""

    def __init__(self) -> None:
        self.fiscal_end_window: int = 14  # days

        # Configurable fiscal-year-end month per department type
        self.fiscal_configs: Dict[str, Dict[str, int]] = {
            "US_GOV": {"year_end_month": 9, "year_end_day": 30},
            "STATE": {"year_end_month": 6, "year_end_day": 30},
            "MUNICIPAL": {"year_end_month": 12, "year_end_day": 31},
        }

    # ------------------------------------------------------------------
    # Fiscal context
    # ------------------------------------------------------------------

    async def get_fiscal_context(
        self, date_obj: date, department_type: str = "STATE"
    ) -> Dict[str, Any]:
        """Return full fiscal context for *date_obj*."""
        cfg = self.fiscal_configs.get(
            department_type, {"year_end_month": 6, "year_end_day": 30}
        )
        fy_end_month = cfg["year_end_month"]
        fy_end_day = cfg["year_end_day"]

        # Determine the fiscal-year-end date that contains date_obj
        fy_year = date_obj.year
        if date_obj.month > fy_end_month or (
            date_obj.month == fy_end_month and date_obj.day > fy_end_day
        ):
            fy_end = date(fy_year + 1, fy_end_month, fy_end_day)
        else:
            fy_end = date(fy_year, fy_end_month, fy_end_day)

        days_to_end = (fy_end - date_obj).days
        quarter = self._get_quarter(date_obj, fy_end_month)
        fiscal_year = fy_end.year

        return {
            "fiscal_year": fiscal_year,
            "fiscal_year_start": date(fiscal_year - 1, fy_end_month + 1, 1),
            "fiscal_year_end": fy_end,
            "fiscal_period": f"FY{fiscal_year}-Q{quarter}",
            "days_to_end": days_to_end,
            "is_fiscal_end": 0 <= days_to_end <= self.fiscal_end_window,
            "quarter": quarter,
            "month": date_obj.month,
            "day_of_year": date_obj.timetuple().tm_yday,
            "week_of_year": date_obj.isocalendar()[1],
        }

    def _get_quarter(self, date_obj: date, fiscal_end_month: int) -> int:
        """Determine fiscal quarter (1–4) for *date_obj*."""
        month = date_obj.month
        adjusted = (
            month - fiscal_end_month
            if month > fiscal_end_month
            else month + (12 - fiscal_end_month)
        )
        if adjusted <= 3:
            return 1
        elif adjusted <= 6:
            return 2
        elif adjusted <= 9:
            return 3
        return 4

    # ------------------------------------------------------------------
    # Amplification factor
    # ------------------------------------------------------------------

    async def get_fiscal_amplification_factor(
        self, date_obj: date, days_window: int = 14
    ) -> Tuple[float, bool]:
        """Return ``(amplification_factor, is_fiscal_end)``.

        The factor increases as the fiscal year end approaches to amplify
        signals for transactions processed in the rush period.
        """
        context = await self.get_fiscal_context(date_obj)
        if not context["is_fiscal_end"]:
            return 1.0, False

        days_to_end = context["days_to_end"]
        if days_to_end <= 3:
            factor = 2.0
        elif days_to_end <= 7:
            factor = 1.7
        elif days_to_end <= 10:
            factor = 1.4
        elif days_to_end <= 14:
            factor = 1.2
        else:
            factor = 1.0

        return factor, True

    # ------------------------------------------------------------------
    # Historical stats (stub — queries DB in production)
    # ------------------------------------------------------------------

    async def get_historical_fiscal_stats(
        self, department_id: str, fiscal_period: str
    ) -> Dict[str, Any]:
        """Return simulated historical statistics for *department_id*.

        In production this queries the database; the stub uses a
        deterministic seed so that results are repeatable for the same
        inputs.
        """
        import random

        seed = hash(f"{department_id}:{fiscal_period}") % (2**32)
        rng = random.Random(seed)

        base_mean = 24 + rng.random() * 48  # 24–72 h
        base_std = 8 + rng.random() * 16  # 8–24 h

        return {
            "mean": base_mean,
            "std": base_std,
            "sample_count": 50 + rng.randint(0, 100),
            "min": base_mean - base_std * 2,
            "max": base_mean + base_std * 3,
            "median": base_mean + rng.uniform(-5, 5),
            "confidence": 0.7 + rng.random() * 0.25,
        }

    # ------------------------------------------------------------------
    # Seasonal effects
    # ------------------------------------------------------------------

    async def get_seasonal_effects(self, date_obj: date) -> Dict[str, Any]:
        """Seasonal / calendar metadata for *date_obj*."""
        month = date_obj.month
        day = date_obj.day
        weekday = date_obj.weekday()

        effects: Dict[str, Any] = {
            "month": month,
            "day": day,
            "weekday": weekday,
            "is_weekend": weekday >= 5,
            "month_name": date_obj.strftime("%B"),
            "weekday_name": date_obj.strftime("%A"),
        }

        effects["is_holiday"] = DateUtils.is_holiday(date_obj)

        if month in (12, 1, 2):
            effects["season"] = "winter"
        elif month in (3, 4, 5):
            effects["season"] = "spring"
        elif month in (6, 7, 8):
            effects["season"] = "summer"
        else:
            effects["season"] = "fall"

        days_in_month = 31 if month in (1, 3, 5, 7, 8, 10, 12) else 30
        if month == 2:
            days_in_month = 29 if date_obj.year % 4 == 0 else 28

        effects["days_to_month_end"] = days_in_month - day
        effects["is_month_end"] = day > days_in_month - 5

        return effects
