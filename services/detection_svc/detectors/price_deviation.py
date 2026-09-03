"""Price Deviation Detector using IQR-based anomaly detection."""

import asyncio
import math
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import BaseDetector
from ..models.detection import DetectionType, PriceDeviationSignal
from ..models.price_deviation import PriceDeviationInput, PeerGroup, PeerTransaction
from ..services.peer_query_service import PeerQueryService
from ..services.benchmark_service import BenchmarkService
from ..services.cache_service import CacheService
from ..utils.statistics import StatisticsUtils
from ..config import settings
from ..utils.logging import get_logger

logger = get_logger(__name__)


class PriceDeviationDetector(BaseDetector):
    """
    Price deviation detector using IQR-based anomaly detection.

    Detects transactions where unit price significantly deviates from
    peer benchmarks based on category, region, and quantity band.
    """

    def __init__(
        self,
        peer_query_service: Optional[PeerQueryService] = None,
        benchmark_service: Optional[BenchmarkService] = None,
        cache_service: Optional[CacheService] = None
    ):
        super().__init__(DetectionType.PRICE_DEVIATION)
        self.peer_query_service = peer_query_service or PeerQueryService()
        self.benchmark_service = benchmark_service or BenchmarkService()
        self.cache_service = cache_service or CacheService()

        # Configuration
        self.lookback_days = settings.PRICE_DEVIATION_LOOKBACK_DAYS
        self.min_samples = settings.PRICE_DEVIATION_MIN_SAMPLES
        self.iqr_multiplier = settings.PRICE_DEVIATION_IQR_MULTIPLIER
        self.max_deviation = settings.PRICE_DEVIATION_MAX_DEVIATION

        # Cache TTL
        self.cache_ttl = settings.CACHE_TTL_SECONDS

        logger.info(f"PriceDeviationDetector initialized with lookback={self.lookback_days} days")

    async def detect(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect price deviation in transaction.
        """
        try:
            # Step 1: Validate and parse input
            input_data = self._parse_input(transaction)

            # Step 2: Get peer groups
            peer_groups = await self._get_peer_groups(input_data)

            if not peer_groups:
                return self._create_insufficient_peers_result(input_data)

            # Step 3: Calculate benchmark for each peer group
            benchmarks = await self._calculate_benchmarks(peer_groups)

            # Step 4: Find best matching benchmark
            best_benchmark = self._select_best_benchmark(benchmarks, input_data)

            if not best_benchmark:
                return self._create_insufficient_peers_result(input_data)

            # Step 5: Calculate deviation signal
            result = await self._calculate_deviation_signal(
                input_data,
                best_benchmark
            )

            # Step 6: Add confidence and metadata
            result = self._enhance_result(result, best_benchmark, input_data)

            logger.info(
                f"Price deviation detection completed for transaction {input_data.transaction_id}: "
                f"signal={result['signal_value']:.3f}, confidence={result['confidence']:.3f}"
            )

            return result

        except Exception as e:
            logger.error(f"Price deviation detection failed: {e}", exc_info=True)
            return self._create_error_result(transaction, str(e))

    def _parse_input(self, transaction: Dict[str, Any]) -> PriceDeviationInput:
        """Parse and validate transaction input."""
        return PriceDeviationInput(
            transaction_id=transaction.get("transaction_id", str(uuid.uuid4())),
            vendor_id=transaction.get("vendor_id", ""),
            category=transaction.get("category", ""),
            subcategory=transaction.get("subcategory"),
            region=transaction.get("region", ""),
            quantity=transaction.get("quantity", 1.0),
            unit_price=transaction.get("unit_price", 0.0),
            total_amount=transaction.get("total_amount", 0.0),
            transaction_date=transaction.get("transaction_date", datetime.utcnow().date())
        )

    async def _get_peer_groups(self, input_data: PriceDeviationInput) -> List[PeerGroup]:
        """Get peer groups from multiple dimensions."""
        peer_groups = []

        # Generate peer group configurations
        group_configs = self._generate_peer_group_configs(input_data)

        # Query peers for each configuration
        for config in group_configs:
            try:
                peers = await self.peer_query_service.query_peers(
                    category=config["category"],
                    region=config["region"],
                    quantity_band=config["quantity_band"],
                    lookback_days=self.lookback_days,
                    limit=1000  # Reasonable limit for performance
                )

                if peers and len(peers) >= self.min_samples:
                    peer_group = PeerGroup(
                        category=config["category"],
                        region=config["region"],
                        quantity_band=config["quantity_band"],
                        transactions=peers
                    )
                    peer_group.calculate_statistics()
                    peer_group.calculate_confidence()

                    if peer_group.is_reliable:
                        peer_groups.append(peer_group)

            except Exception as e:
                logger.warning(f"Failed to query peers for config {config}: {e}")

        # Sort by confidence (highest first)
        peer_groups.sort(key=lambda g: g.confidence, reverse=True)

        return peer_groups

    def _generate_peer_group_configs(self, input_data: PriceDeviationInput) -> List[Dict[str, str]]:
        """
        Generate peer group configurations with increasing specificity.
        """
        configs = []
        quantity_band = input_data.get_quantity_band()

        # Strategy 1: Most specific (category + region + quantity_band)
        configs.append({
            "category": input_data.category,
            "region": input_data.region,
            "quantity_band": quantity_band,
            "specificity": "high"
        })

        # Strategy 2: Category + region (broad quantity)
        if input_data.subcategory:
            configs.append({
                "category": input_data.subcategory,
                "region": input_data.region,
                "quantity_band": quantity_band,
                "specificity": "high_subcategory"
            })

        # Strategy 3: Category + quantity (broad region)
        configs.append({
            "category": input_data.category,
            "region": "national",
            "quantity_band": quantity_band,
            "specificity": "medium"
        })

        # Strategy 4: Category only
        configs.append({
            "category": input_data.category,
            "region": "national",
            "quantity_band": "all",
            "specificity": "low"
        })

        # Strategy 5: Category + broader region
        broader_region = self._get_broader_region(input_data.region)
        if broader_region:
            configs.append({
                "category": input_data.category,
                "region": broader_region,
                "quantity_band": quantity_band,
                "specificity": "medium_broad"
            })

        return configs

    def _get_broader_region(self, region: str) -> Optional[str]:
        """Get broader region category (e.g., state -> region -> national)."""
        # This would be configured based on your region hierarchy
        broader_regions = {
            "CA": "west",
            "OR": "west",
            "WA": "west",
            "NY": "east",
            "MA": "east",
            "TX": "south",
            "FL": "south",
            # Add more mappings as needed
        }

        # Check if it's a state code
        if len(region) == 2 and region in broader_regions:
            return broader_regions[region]

        # Check if it's already a broader region
        if region in ["west", "east", "south", "midwest", "national"]:
            return "national"

        return None

    async def _calculate_benchmarks(self, peer_groups: List[PeerGroup]) -> List[Dict[str, Any]]:
        """Calculate benchmarks for each peer group."""
        benchmarks = []

        for peer_group in peer_groups:
            try:
                # Calculate benchmark price (using median for robustness)
                benchmark_price = peer_group.median
                upper_fence = peer_group.upper_fence
                lower_fence = peer_group.lower_fence

                # Use robust metrics if available
                robust_metrics = StatisticsUtils.calculate_robust_metrics(
                    [t.unit_price for t in peer_group.transactions]
                )

                # Determine confidence
                confidence = StatisticsUtils.calculate_sample_confidence(
                    peer_group.count,
                    peer_group.std_dev or 0,
                    benchmark_price or 0
                )

                # Cache benchmark
                benchmark_entry = await self.benchmark_service.save_benchmark(
                    category=peer_group.category,
                    region=peer_group.region,
                    quantity_band=peer_group.quantity_band,
                    benchmark_price=benchmark_price or 0,
                    upper_fence=upper_fence or 0,
                    lower_fence=lower_fence or 0,
                    sample_count=peer_group.count,
                    sample_std=peer_group.std_dev,
                    confidence=confidence
                )

                benchmarks.append({
                    "peer_group": peer_group,
                    "benchmark_price": benchmark_price,
                    "upper_fence": upper_fence,
                    "lower_fence": lower_fence,
                    "confidence": confidence,
                    "sample_count": peer_group.count,
                    "sample_std": peer_group.std_dev,
                    "robust_metrics": robust_metrics,
                    "specificity": self._get_specificity_level(peer_group)
                })

            except Exception as e:
                logger.warning(f"Failed to calculate benchmark for peer group: {e}")
                continue

        return benchmarks

    def _select_best_benchmark(
        self,
        benchmarks: List[Dict[str, Any]],
        input_data: PriceDeviationInput
    ) -> Optional[Dict[str, Any]]:
        """Select the best benchmark based on quality and specificity."""
        if not benchmarks:
            return None

        # Score each benchmark
        scored_benchmarks = []
        for benchmark in benchmarks:
            score = self._calculate_benchmark_score(benchmark, input_data)
            scored_benchmarks.append((score, benchmark))

        # Sort by score (highest first)
        scored_benchmarks.sort(key=lambda x: x[0], reverse=True)

        # Return best benchmark if score is reasonable
        best_score, best_benchmark = scored_benchmarks[0]
        if best_score > 0.3:
            return best_benchmark
        else:
            return None

    def _calculate_benchmark_score(
        self,
        benchmark: Dict[str, Any],
        input_data: PriceDeviationInput
    ) -> float:
        """Calculate quality score for a benchmark."""
        score = 0.0

        # Confidence (0-1)
        confidence = benchmark.get("confidence", 0)
        score += confidence * 0.4

        # Sample count (diminishing returns)
        sample_count = benchmark.get("sample_count", 0)
        sample_score = min(1.0, math.log10(sample_count + 1) / 2)
        score += sample_score * 0.3

        # Specificity (1-3)
        specificity_weights = {
            "high": 0.3,
            "high_subcategory": 0.35,
            "medium": 0.2,
            "medium_broad": 0.15,
            "low": 0.1
        }
        specificity = benchmark.get("specificity", "low")
        score += specificity_weights.get(specificity, 0.1)

        # Penalty if category doesn't match perfectly
        if benchmark.get("peer_group", {}).category != input_data.category:
            score *= 0.8

        return min(1.0, score)

    async def _calculate_deviation_signal(
        self,
        input_data: PriceDeviationInput,
        benchmark: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate the price deviation signal."""

        price = input_data.unit_price
        benchmark_price = benchmark.get("benchmark_price", 0)
        upper_fence = benchmark.get("upper_fence", 0)
        confidence = benchmark.get("confidence", 0)

        # Basic deviation
        raw_deviation = price - benchmark_price if benchmark_price > 0 else 0

        # Normalized signal calculation
        if benchmark_price > 0 and upper_fence > 0:
            # Calculate how far above the upper fence
            if price > upper_fence:
                # Signal proportional to deviation beyond upper fence
                deviation_above_fence = price - upper_fence
                range_size = benchmark_price * 0.5  # 50% of benchmark as range
                signal_value = min(1.0, deviation_above_fence / range_size if range_size > 0 else 1.0)
            else:
                signal_value = 0.0
        else:
            # Fallback: use relative deviation
            if benchmark_price > 0:
                relative_deviation = (price - benchmark_price) / benchmark_price
                if relative_deviation > 0.3:  # More than 30% above benchmark
                    signal_value = min(1.0, relative_deviation / 3)  # Cap at 3x
                else:
                    signal_value = 0.0
            else:
                signal_value = 0.0

        # Apply confidence adjustment
        adjusted_signal = signal_value * confidence

        # Calculate percentile rank
        percentile_rank = self._calculate_percentile_rank(
            price,
            benchmark.get("peer_group", {})
        )

        return {
            "signal_value": adjusted_signal,
            "raw_deviation": raw_deviation,
            "benchmark_price": benchmark_price,
            "upper_fence": upper_fence,
            "percentile_rank": percentile_rank,
            "confidence": confidence,
            "sample_count": benchmark.get("sample_count", 0),
            "sample_std": benchmark.get("sample_std"),
            "peer_category": getattr(benchmark.get("peer_group"), "category", None),
            "peer_region": getattr(benchmark.get("peer_group"), "region", None),
            "peer_quantity_band": getattr(benchmark.get("peer_group"), "quantity_band", None),
            "detection_method": "iqr"
        }

    def _calculate_percentile_rank(self, price: float, peer_group: PeerGroup) -> float:
        """Calculate percentile rank of price within peer group."""
        if not peer_group or not peer_group.transactions:
            return 50.0

        prices = [t.unit_price for t in peer_group.transactions]
        below_count = sum(1 for p in prices if p <= price)

        return (below_count / len(prices)) * 100

    def _enhance_result(
        self,
        result: Dict[str, Any],
        benchmark: Dict[str, Any],
        input_data: PriceDeviationInput
    ) -> Dict[str, Any]:
        """Enhance result with additional metadata and recommendations."""

        # Add outlier indicators
        price = input_data.unit_price
        upper_fence = result.get("upper_fence", 0)
        benchmark_price = result.get("benchmark_price", 0)

        outlier_indicators = []

        if price > upper_fence and upper_fence > 0:
            deviation_ratio = price / upper_fence
            if deviation_ratio > 2:
                outlier_indicators.append("extreme_high_price")
            else:
                outlier_indicators.append("high_price_above_fence")

        if benchmark_price > 0:
            relative_deviation = (price - benchmark_price) / benchmark_price
            if relative_deviation > 0.5:
                outlier_indicators.append("significant_deviation")
            if relative_deviation > 1.0:
                outlier_indicators.append("double_benchmark")

        # Additional statistical indicators
        if result.get("sample_count", 0) < 10:
            outlier_indicators.append("low_sample_size")

        # Generate evidence
        evidence = self._generate_evidence(result, input_data, outlier_indicators)

        # Generate recommendations
        recommendations = self._generate_recommendations(result, input_data)

        # Determine severity
        severity = self.calculate_severity(
            result.get("signal_value", 0),
            result.get("confidence", 0)
        )

        # Add metadata
        result.update({
            "outlier_indicators": outlier_indicators,
            "evidence": evidence,
            "recommendations": recommendations,
            "severity": severity,
            "transaction_id": input_data.transaction_id,
            "vendor_id": input_data.vendor_id,
            "detection_type": "price_deviation",
            "computed_at": datetime.utcnow().isoformat()
        })

        return result

    def _generate_evidence(
        self,
        result: Dict[str, Any],
        input_data: PriceDeviationInput,
        outlier_indicators: List[str]
    ) -> List[str]:
        """Generate human-readable evidence."""
        evidence = []

        price = input_data.unit_price
        benchmark_price = result.get("benchmark_price", 0)
        upper_fence = result.get("upper_fence", 0)
        sample_count = result.get("sample_count", 0)

        if benchmark_price > 0:
            evidence.append(
                f"Unit price ${price:.2f} is ${(price - benchmark_price):.2f} "
                f"({((price - benchmark_price) / benchmark_price * 100):.1f}%) "
                f"higher than benchmark of ${benchmark_price:.2f}"
            )

        if upper_fence > 0 and price > upper_fence:
            evidence.append(
                f"Price exceeds IQR upper fence of ${upper_fence:.2f} "
                f"by ${(price - upper_fence):.2f}"
            )

        evidence.append(
            f"Based on {sample_count} peer transactions over {self.lookback_days} days"
        )

        if result.get("peer_category"):
            evidence.append(
                f"Peer group: {result['peer_category']} "
                f"({result.get('peer_region', '')}) - "
                f"{result.get('peer_quantity_band', '')} quantity"
            )

        if "extreme_high_price" in outlier_indicators:
            evidence.append("Price is more than double the peer upper fence")
        elif "significant_deviation" in outlier_indicators:
            evidence.append("Price shows significant deviation from peers")

        return evidence

    def _generate_recommendations(
        self,
        result: Dict[str, Any],
        input_data: PriceDeviationInput
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []

        signal_value = result.get("signal_value", 0)
        confidence = result.get("confidence", 0)

        if signal_value > 0.7 and confidence > 0.6:
            recommendations.append(
                "Flag for immediate review - significant price deviation detected"
            )
            recommendations.append(
                "Request supporting documentation for pricing justification"
            )
            recommendations.append(
                "Check if this transaction qualifies for special pricing or exceptions"
            )
        elif signal_value > 0.4 and confidence > 0.5:
            recommendations.append(
                "Recommend secondary review - price moderately above peers"
            )
            recommendations.append(
                "Verify category and quantity band classification"
            )
            recommendations.append(
                "Check if price includes additional services or deliverables"
            )

        if confidence < 0.5:
            recommendations.append(
                "Low confidence due to limited peer data - consider expanding peer group"
            )

        if result.get("sample_count", 0) < 15:
            recommendations.append(
                "Limited peer data available - this detection has reduced reliability"
            )

        return recommendations

    def _create_insufficient_peers_result(self, input_data: PriceDeviationInput) -> Dict[str, Any]:
        """Create result when insufficient peers are available."""
        return {
            "signal_value": 0.0,
            "confidence": 0.0,
            "detection_method": "iqr",
            "raw_deviation": 0.0,
            "benchmark_price": 0.0,
            "upper_fence": 0.0,
            "percentile_rank": 50.0,
            "sample_count": 0,
            "peer_category": None,
            "peer_region": None,
            "peer_quantity_band": None,
            "outlier_indicators": ["insufficient_peers"],
            "evidence": [
                f"Insufficient peer data found for category '{input_data.category}', "
                f"region '{input_data.region}', "
                f"quantity band '{input_data.get_quantity_band()}'"
            ],
            "recommendations": [
                "Expand peer search parameters",
                "Consider using broader category or regional benchmarks",
                "Wait for more transactions to establish reliable benchmarks"
            ],
            "severity": "low",
            "transaction_id": input_data.transaction_id,
            "vendor_id": input_data.vendor_id,
            "detection_type": "price_deviation",
            "computed_at": datetime.utcnow().isoformat()
        }

    def _create_error_result(self, transaction: Dict[str, Any], error: str) -> Dict[str, Any]:
        """Create error result."""
        return {
            "signal_value": 0.0,
            "confidence": 0.0,
            "detection_method": "error",
            "error": error,
            "transaction_id": transaction.get("transaction_id", str(uuid.uuid4())),
            "vendor_id": transaction.get("vendor_id", ""),
            "detection_type": "price_deviation",
            "severity": "low",
            "outlier_indicators": ["detection_error"],
            "computed_at": datetime.utcnow().isoformat()
        }

    def get_weight(self) -> float:
        """Get detector weight for scoring."""
        return 0.30  # As per architecture

    def get_required_fields(self) -> List[str]:
        """Get required transaction fields."""
        return [
            "category",
            "region",
            "quantity",
            "unit_price",
            "total_amount",
            "transaction_date"
        ]

    def _get_specificity_level(self, peer_group: PeerGroup) -> str:
        """Determine specificity level of a peer group."""
        if peer_group.region != "national":
            if peer_group.quantity_band != "all":
                return "high"
            else:
                return "medium"
        else:
            if peer_group.quantity_band != "all":
                return "medium"
            else:
                return "low"