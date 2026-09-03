"""Models for benchmark storage."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BenchmarkPrice(BaseModel):
    """Stored benchmark price for a peer group."""
    id: str
    category: str
    region: str
    quantity_band: str
    benchmark_price: float
    upper_fence: float
    lower_fence: float
    sample_count: int
    sample_std: Optional[float] = None
    confidence: float
    computed_at: datetime
    expires_at: Optional[datetime] = None

    # Metadata
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True


class BenchmarkCacheEntry(BaseModel):
    """Cache entry for benchmark data."""
    peer_group: "PeerGroup"
    computed_at: datetime
    expires_at: datetime

    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at