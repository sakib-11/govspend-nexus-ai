"""Tool: benchmark_price — price benchmarking for procurement categories."""

from __future__ import annotations

from typing import Any, Dict, Optional

from tools.base import BaseTool
from models.mcp import ToolExecutionContext


class BenchmarkPriceTool(BaseTool):
    """Fetch price benchmarks and deviation analysis for a category + region."""

    async def execute(self, context: ToolExecutionContext) -> Dict[str, Any]:
        category: str = context.parameters["category"]
        region: str = context.parameters["region"]
        quantity: int = context.parameters.get("quantity", 1)
        target_price: Optional[float] = context.parameters.get("target_price")

        benchmarks = self._compute_benchmarks(category, region)
        recommendations = self._recommend(benchmarks, quantity, target_price)

        return {
            "category": category,
            "region": region,
            "benchmarks": benchmarks,
            "recommendations": recommendations,
            "data_source": "Historical transactions (90 days)",
            "sample_size": benchmarks["sample_count"],
        }

    async def validate_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not params.get("category"):
            raise ValueError("category is required")
        if not params.get("region"):
            raise ValueError("region is required")
        return params

    # ------------------------------------------------------------------

    @staticmethod
    def _compute_benchmarks(category: str, region: str) -> Dict[str, Any]:
        """Replace with real aggregate query in production."""
        q1, q2, q3 = 1_200.0, 1_350.0, 1_500.0
        sample = 250
        confidence = "high" if sample >= 500 else "medium" if sample >= 100 else "low"
        return {
            "quartiles": {"q1": q1, "q2": q2, "q3": q3},
            "mean": q2,
            "median": q2,
            "std_dev": 150.0,
            "min": 1_000.0,
            "max": 1_800.0,
            "sample_count": sample,
            "percentile_95": 1_650.0,
            "percentile_5": 1_100.0,
            "confidence": confidence,
        }

    @staticmethod
    def _recommend(
        benchmarks: Dict[str, Any],
        quantity: int,
        target_price: Optional[float],
    ) -> Dict[str, Any]:
        q1 = benchmarks["quartiles"]["q1"]
        q3 = benchmarks["quartiles"]["q3"]
        median = benchmarks["median"]
        low = q1 * 0.9
        high = q3 * 1.1
        expected = median * (1 + (quantity - 1) * 0.05)

        rec: Dict[str, Any] = {
            "fair_price_range": {"low": low, "high": high},
            "expected_price": expected,
            "recommendation": "within_benchmark",
            "deviation": 0.0,
        }

        if target_price is not None:
            if target_price > high:
                rec["recommendation"] = "above_benchmark"
                rec["deviation"] = round(target_price / expected - 1, 4)
            elif target_price < low:
                rec["recommendation"] = "below_benchmark"
                rec["deviation"] = round(target_price / expected - 1, 4)

        return rec


async def benchmark_price(request, context):  # type: ignore[no-untyped-def]
    return await BenchmarkPriceTool().handle(request)
