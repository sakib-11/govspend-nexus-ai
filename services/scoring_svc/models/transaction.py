"""Transaction models for the Scoring Service."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class CanonicalTransaction(BaseModel):
    """Canonical transaction from ingestion pipeline."""
    model_config = ConfigDict(from_attributes=True)

    transaction_id: str
    source_id: str
    vendor_id: str | None = None
    department_id: str | None = None
    amount: Decimal
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    category: str | None = None
    subcategory: str | None = None
    transaction_date: datetime
    document_number: str | None = None
    metadata: dict[str, Any] | None = None


class TransactionStatus(BaseModel):
    """Transaction processing status."""
    transaction_id: str
    status: str  # PENDING, PROCESSING, COMPLETED, FAILED
    signals_found: int = 0
    scored: bool = False
    risk_tier: str | None = None
    risk_score: float | None = None
    error: str | None = None