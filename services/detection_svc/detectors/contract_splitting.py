"""Contract Splitting Detector.

Pipeline:
1. Parse & validate input (``SplittingDetectionInput``).
2. Check cache.
3. Fetch historical purchase orders (stub → simulated data).
4. Resolve review threshold.
5. Run ``ContractAnalysisService`` (window + pattern analysis).
6. Cache result and return.
"""

import asyncio
import random
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from .base import BaseDetector
from ..config import settings
from ..models.detection import DetectionType
from ..models.contract_splitting import (
    ContractSplittingResult,
    PurchaseOrder,
    SplittingDetectionInput,
)
from ..services.contract_analysis import ContractAnalysisService
from ..services.splitting_cache import SplittingCache
from ..utils.logging import get_logger
from ..utils.threshold_utils import ThresholdUtils

logger = get_logger(__name__)


class ContractSplittingDetector(BaseDetector):
    """Detect vendors splitting contracts to avoid review thresholds.

    Combines:
    * **Sliding window analysis** — groups nearby POs and checks whether
      their aggregate exceeds the threshold.
    * **Multi-pattern detection** — temporal clustering, amount alignment,
      sequential splitting, frequency spikes, and rounding patterns.
    * **Risk scoring** — weighted multi-factor score per group.
    """

    def __init__(
        self,
        contract_analysis: Optional[ContractAnalysisService] = None,
        splitting_cache: Optional[SplittingCache] = None,
    ) -> None:
        super().__init__(DetectionType.CONTRACT_SPLITTING)
        self.contract_analysis = contract_analysis or ContractAnalysisService()
        self.splitting_cache = splitting_cache or SplittingCache()
        self.threshold_utils = ThresholdUtils()

        # Tuning knobs
        self.window_days: int = 14
        self.min_pos_for_splitting: int = 3
        self.default_threshold: float = 25_000

        logger.info("ContractSplittingDetector initialised")

    # ------------------------------------------------------------------
    # BaseDetector interface
    # ------------------------------------------------------------------

    async def detect(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        start_time = asyncio.get_event_loop().time()

        try:
            input_data = self._parse_input(transaction)

            # Check cache
            cached = await self.splitting_cache.get_analysis(
                input_data.vendor_id, input_data.department_id
            )
            if cached and not self._is_expired(cached):
                return cached

            # Fetch POs
            purchase_orders = await self._get_purchase_orders(input_data)
            if not purchase_orders:
                return self._create_no_data_result(input_data)

            # Resolve threshold
            threshold = input_data.review_threshold or self._get_review_threshold(
                input_data.category, input_data.department_id
            )

            # Run analysis
            result = await self.contract_analysis.analyze_vendor_department(
                input_data.vendor_id,
                input_data.department_id,
                purchase_orders,
                threshold,
            )

            result_dict = result.model_dump(mode="json")

            # Cache
            await self.splitting_cache.cache_analysis(
                input_data.vendor_id, input_data.department_id, result_dict
            )

            elapsed = (asyncio.get_event_loop().time() - start_time) * 1000
            result_dict["processing_time_ms"] = int(elapsed)

            logger.info(
                "Contract splitting detection completed: signal=%.3f, groups=%d, severity=%s",
                result.signal_value,
                len(result.splitting_groups),
                result.severity,
            )
            return result_dict

        except Exception as exc:
            logger.error("Contract splitting detection failed: %s", exc, exc_info=True)
            return self._create_error_result(transaction, str(exc))

    def get_weight(self) -> float:
        return 0.15

    def get_required_fields(self) -> List[str]:
        return [
            "vendor_id",
            "vendor_name",
            "department_id",
            "department_name",
            "amount",
            "po_date",
            "po_id",
        ]

    # ------------------------------------------------------------------
    # Input parsing
    # ------------------------------------------------------------------

    def _parse_input(self, transaction: Dict[str, Any]) -> SplittingDetectionInput:
        return SplittingDetectionInput(
            transaction_id=transaction.get("transaction_id", str(uuid.uuid4())),
            vendor_id=transaction.get("vendor_id", ""),
            vendor_name=transaction.get("vendor_name", ""),
            department_id=transaction.get("department_id", ""),
            department_name=transaction.get("department_name", ""),
            amount=float(transaction.get("amount", 0)),
            po_date=transaction.get("po_date", date.today()),
            po_id=transaction.get("po_id", ""),
            description=transaction.get("description"),
            category=transaction.get("category"),
            approver_id=transaction.get("approver_id"),
            approver_name=transaction.get("approver_name"),
            review_threshold=transaction.get("review_threshold"),
            window_days=transaction.get("window_days", 14),
        )

    # ------------------------------------------------------------------
    # PO retrieval (stub — replace with DB query)
    # ------------------------------------------------------------------

    async def _get_purchase_orders(
        self, input_data: SplittingDetectionInput
    ) -> List[PurchaseOrder]:
        """Return historical POs for the vendor × department.

        In production this queries the database; the stub uses a
        deterministic seed so results are repeatable.
        """
        return self._simulate_purchase_orders(input_data)

    def _simulate_purchase_orders(
        self, input_data: SplittingDetectionInput
    ) -> List[PurchaseOrder]:
        seed = hash(f"{input_data.vendor_id}:{input_data.department_id}") % (2**32)
        rng = random.Random(seed)

        threshold = input_data.review_threshold or self.default_threshold
        n = rng.randint(20, 50)
        pos: List[PurchaseOrder] = []

        for i in range(n):
            if rng.random() < 0.3:
                amount = threshold * rng.uniform(1.1, 1.5)
            else:
                amount = threshold * rng.uniform(0.20, 0.95)

            po = PurchaseOrder(
                po_id=f"PO-{i:05d}",
                vendor_id=input_data.vendor_id,
                vendor_name=input_data.vendor_name,
                department_id=input_data.department_id,
                department_name=input_data.department_name,
                amount=round(amount, 2),
                po_date=date.today() - timedelta(days=rng.randint(0, 30)),
                description=f"PO {i}",
                category=input_data.category or "OTHER",
                review_threshold=threshold,
            )
            pos.append(po)

        return pos

    # ------------------------------------------------------------------
    # Threshold
    # ------------------------------------------------------------------

    def _get_review_threshold(
        self, category: Optional[str], department_id: Optional[str]
    ) -> float:
        return self.threshold_utils.get_review_threshold(
            category=category, department_id=department_id
        )

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_expired(cached: Dict[str, Any]) -> bool:
        raw = cached.get("computed_at")
        if not raw:
            return True
        try:
            computed = datetime.fromisoformat(str(raw))
            return (datetime.utcnow() - computed).days > 1
        except Exception:
            return True

    # ------------------------------------------------------------------
    # Fallback results
    # ------------------------------------------------------------------

    def _create_no_data_result(
        self, input_data: SplittingDetectionInput
    ) -> Dict[str, Any]:
        return {
            "signal_value": 0.0,
            "confidence": 0.0,
            "vendor_id": input_data.vendor_id,
            "vendor_name": input_data.vendor_name,
            "department_id": input_data.department_id,
            "department_name": input_data.department_name,
            "review_threshold": input_data.review_threshold or self.default_threshold,
            "splitting_groups": [],
            "high_risk_groups": [],
            "total_split_amount": 0.0,
            "total_splitting_groups": 0,
            "total_purchase_orders": 0,
            "total_po_count": 0,
            "detected_patterns": [],
            "severity": "none",
            "evidence": ["No historical purchase orders available"],
            "recommendations": ["Collect more data and retry"],
            "window_analysis": {},
            "pattern_analysis": {},
            "transaction_id": input_data.transaction_id,
        }

    def _create_error_result(
        self, transaction: Dict[str, Any], error: str
    ) -> Dict[str, Any]:
        return {
            "signal_value": 0.0,
            "confidence": 0.0,
            "vendor_id": transaction.get("vendor_id", ""),
            "vendor_name": transaction.get("vendor_name", "Unknown"),
            "department_id": transaction.get("department_id", ""),
            "department_name": transaction.get("department_name", "Unknown"),
            "review_threshold": self.default_threshold,
            "splitting_groups": [],
            "high_risk_groups": [],
            "total_split_amount": 0.0,
            "total_splitting_groups": 0,
            "total_purchase_orders": 0,
            "total_po_count": 0,
            "detected_patterns": [],
            "severity": "none",
            "evidence": [f"Detection failed: {error}"],
            "recommendations": ["Retry detection or check data"],
            "window_analysis": {},
            "pattern_analysis": {},
            "transaction_id": transaction.get("transaction_id", str(uuid.uuid4())),
            "error": error,
        }
