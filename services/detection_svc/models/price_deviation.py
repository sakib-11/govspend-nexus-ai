"""Models for price deviation detection."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class PeerTransaction(BaseModel):
    """Historical transaction for peer comparison."""
    transaction_id: str
    vendor_id: str
    category: str
    subcategory: Optional[str] = None
    region: str
    quantity: float
    unit_price: float
    total_amount: float
    transaction_date: date
    document_number: Optional[str] = None

    # Derived fields
    quantity_band: Optional[str] = None
    unit_price_normalized: Optional[float] = None


class PeerGroup(BaseModel):
    """Group of peer transactions for benchmarking."""
    category: str
    region: str
    quantity_band: str
    transactions: List[PeerTransaction]

    # Statistical measures
    count: int = 0
    mean: Optional[float] = None
    median: Optional[float] = None
    q1: Optional[float] = None
    q3: Optional[float] = None
    iqr: Optional[float] = None
    lower_fence: Optional[float] = None
    upper_fence: Optional[float] = None
    std_dev: Optional[float] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None

    # Quality metrics
    confidence: float = 0.0
    is_reliable: bool = False
    outlier_count: int = 0

    def calculate_statistics(self) -> None:
        """Calculate statistical measures for the peer group."""
        if not self.transactions:
            return

        prices = [t.unit_price for t in self.transactions]
        self.count = len(prices)

        # Sort for percentile calculations
        sorted_prices = sorted(prices)

        # Basic statistics
        self.mean = sum(prices) / len(prices)
        self.median = self._median(sorted_prices)
        self.min_price = min(prices)
        self.max_price = max(prices)

        # Quartiles
        self.q1 = self._percentile(sorted_prices, 25)
        self.q3 = self._percentile(sorted_prices, 75)
        self.iqr = (self.q3 or 0) - (self.q1 or 0)

        # Fences
        fence_multiplier = 1.5  # Standard IQR multiplier
        self.lower_fence = (self.q1 or 0) - fence_multiplier * (self.iqr or 0)
        self.upper_fence = (self.q3 or 0) + fence_multiplier * (self.iqr or 0)

        # Standard deviation
        if self.mean:
            variance = sum((x - self.mean) ** 2 for x in prices) / len(prices)
            self.std_dev = variance ** 0.5

        # Count outliers
        self.outlier_count = sum(
            1 for p in prices
            if p < (self.lower_fence or float('-inf')) or p > (self.upper_fence or float('inf'))
        )

    def _median(self, sorted_list: List[float]) -> float:
        """Calculate median of sorted list."""
        n = len(sorted_list)
        if n == 0:
            return 0.0
        if n % 2 == 1:
            return sorted_list[n // 2]
        else:
            return (sorted_list[n // 2 - 1] + sorted_list[n // 2]) / 2

    def _percentile(self, sorted_list: List[float], percentile: int) -> float:
        """Calculate percentile of sorted list."""
        n = len(sorted_list)
        if n == 0:
            return 0.0

        index = (n - 1) * percentile / 100
        if index.is_integer():
            return sorted_list[int(index)]
        else:
            lower = sorted_list[int(index)]
            upper = sorted_list[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))

    def calculate_confidence(self) -> float:
        """Calculate confidence based on sample size and quality."""
        if self.count == 0:
            return 0.0

        # Base confidence from sample size
        if self.count >= 30:
            sample_confidence = 0.9
        elif self.count >= 15:
            sample_confidence = 0.7
        elif self.count >= 10:
            sample_confidence = 0.5
        elif self.count >= 5:
            sample_confidence = 0.3
        else:
            sample_confidence = 0.1

        # Penalty for high outlier ratio
        outlier_ratio = self.outlier_count / self.count if self.count > 0 else 0
        quality_penalty = min(0.3, outlier_ratio * 0.5)

        # Penalty for high variance (relative to mean)
        if self.mean and self.mean > 0 and self.std_dev:
            cv = self.std_dev / self.mean
            variance_penalty = min(0.2, cv * 0.5)
        else:
            variance_penalty = 0

        self.confidence = max(0.0, sample_confidence - quality_penalty - variance_penalty)
        self.is_reliable = self.confidence >= 0.5

        return self.confidence


class PriceDeviationInput(BaseModel):
    """Input for price deviation detector."""
    transaction_id: str
    vendor_id: str
    category: str
    subcategory: Optional[str] = None
    region: str
    quantity: float
    unit_price: float
    total_amount: float
    transaction_date: date

    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Quantity must be positive")
        return v

    @field_validator('unit_price')
    @classmethod
    def validate_unit_price(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Unit price must be positive")
        return v

    def get_quantity_band(self) -> str:
        """Determine quantity band for peer grouping."""
        if self.quantity <= 10:
            return "small"
        elif self.quantity <= 100:
            return "medium"
        elif self.quantity <= 1000:
            return "large"
        else:
            return "bulk"