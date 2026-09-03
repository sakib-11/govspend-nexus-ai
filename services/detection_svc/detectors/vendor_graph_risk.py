"""Vendor graph risk detector using HHI and repeat official analysis."""

import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import BaseDetector
from ..models.detection import DetectionType
from ..models.vendor_graph import VendorGraph, HHIResult, RepeatOfficialResult, VendorGraphRiskResult
from ..graph.graph_builder import GraphBuilder
from ..graph.graph_analyzer import GraphAnalyzer
from ..services.graph_cache import GraphCache
from ..config import settings
from ..utils.logging import get_logger

logger = get_logger(__name__)


class VendorGraphRiskDetector(BaseDetector):
    """
    Vendor graph risk detector using:
    1. HHI (Herfindahl-Hirschman Index) for market concentration
    2. Repeat official analysis
    3. Graph-based risk pattern detection
    """

    def __init__(
        self,
        graph_builder: Optional[GraphBuilder] = None,
        graph_analyzer: Optional[GraphAnalyzer] = None,
        graph_cache: Optional[GraphCache] = None
    ):
        super().__init__(DetectionType.VENDOR_RISK)
        self.graph_builder = graph_builder or GraphBuilder()
        self.graph_analyzer = graph_analyzer or GraphAnalyzer()
        self.graph_cache = graph_cache or GraphCache()

        # Configuration
        self.lookback_days = 365  # 1 year
        self.hhi_weight = 0.6
        self.repeat_weight = 0.4
        self.min_transactions = 10
        self.min_vendors = 3

        logger.info("VendorGraphRiskDetector initialized")

    async def detect(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect vendor graph risk for a transaction.
        """
        start_time = asyncio.get_event_loop().time()

        try:
            # Extract department context
            department_id = transaction.get("department_id")

            if not department_id:
                logger.warning("No department_id provided, skipping graph risk detection")
                return self._create_no_context_result(transaction)

            # Get or build graph
            graph = await self._get_graph(department_id)

            if not graph or graph.node_count == 0:
                logger.warning(f"No graph data for department {department_id}")
                return self._create_no_data_result(transaction, department_id)

            # Step 1: Calculate HHI
            hhi_result = await self.graph_analyzer.analyze_hhi(
                graph,
                department_id,
                period=f"last_{self.lookback_days}_days"
            )

            # Step 2: Analyze repeat officials
            repeat_results = await self.graph_analyzer.analyze_repeat_officials(
                graph,
                department_id
            )

            # Step 3: Detect risk patterns
            risk_patterns = await self.graph_analyzer.detect_risk_patterns(
                graph,
                department_id
            )

            # Step 4: Calculate combined signal
            result = self._calculate_risk_signal(
                transaction,
                hhi_result,
                repeat_results,
                risk_patterns
            )

            # Step 5: Add processing metadata
            processing_time = (asyncio.get_event_loop().time() - start_time) * 1000
            result["processing_time_ms"] = int(processing_time)
            result["computed_at"] = datetime.utcnow().isoformat()

            logger.info(
                f"Vendor graph risk detection completed: "
                f"signal={result['signal_value']:.3f}, "
                f"risk_level={result['risk_level']}"
            )

            return result

        except Exception as e:
            logger.error(f"Vendor graph risk detection failed: {e}", exc_info=True)
            return self._create_error_result(transaction, str(e))

    async def _get_graph(self, department_id: str) -> Optional[VendorGraph]:
        """Get graph from cache or build it."""
        # Check cache
        cached_graph = await self.graph_cache.get_graph(department_id)
        if cached_graph:
            logger.info(f"Using cached graph for department {department_id}")
            return cached_graph

        # Build graph
        try:
            graph = await self.graph_builder.build_graph(
                department_id=department_id,
                lookback_days=self.lookback_days,
                include_officials=True
            )

            # Cache graph
            await self.graph_cache.cache_graph(department_id, graph)

            return graph

        except Exception as e:
            logger.error(f"Failed to build graph for {department_id}: {e}")
            return None

    def _calculate_risk_signal(
        self,
        transaction: Dict[str, Any],
        hhi_result: HHIResult,
        repeat_results: List[RepeatOfficialResult],
        risk_patterns: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate combined risk signal from HHI and repeat scores.
        """
        # Normalize HHI (already normalized [0,1])
        normalized_hhi = hhi_result.normalized_hhi

        # Calculate repeat official score
        repeat_score = self._calculate_repeat_score(repeat_results)
        normalized_repeat = repeat_score  # Already normalized

        # Combined signal
        hhi_component = normalized_hhi * self.hhi_weight
        repeat_component = normalized_repeat * self.repeat_weight
        signal_value = hhi_component + repeat_component

        # Confidence based on data quality
        confidence = self._calculate_confidence(
            hhi_result.vendor_count,
            len(repeat_results),
            risk_patterns.get('pattern_count', 0)
        )

        # Determine risk level
        risk_level = self._determine_risk_level(signal_value, confidence)

        # Build evidence
        evidence = self._build_evidence(
            hhi_result,
            repeat_results,
            risk_patterns,
            signal_value
        )

        # Build recommendations
        recommendations = self._build_recommendations(
            signal_value,
            risk_level,
            risk_patterns
        )

        # Compile risk indicators
        risk_indicators = self._compile_risk_indicators(
            hhi_result,
            repeat_results,
            risk_patterns
        )

        return {
            "signal_value": signal_value,
            "confidence": confidence,
            "hhi_score": normalized_hhi,
            "normalized_hhi": normalized_hhi,
            "repeat_score": repeat_score,
            "normalized_repeat": normalized_repeat,
            "department_id": transaction.get("department_id"),
            "department_name": hhi_result.department_name,
            "risk_level": risk_level,
            "risk_indicators": risk_indicators,
            "evidence": evidence,
            "recommendations": recommendations,
            "hhi_details": hhi_result.model_dump(),
            "repeat_details": [r.model_dump() for r in repeat_results],
            "graph_stats": {
                "node_count": 0,  # Would need graph stats
                "edge_count": 0,
                "pattern_count": risk_patterns.get('pattern_count', 0),
                "high_severity_count": risk_patterns.get('high_severity_count', 0)
            }
        }

    def _calculate_repeat_score(self, repeat_results: List[RepeatOfficialResult]) -> float:
        """Calculate overall repeat official score."""
        if not repeat_results:
            return 0.0

        # Average repeat score across officials
        avg_score = sum(r.repeat_score for r in repeat_results) / len(repeat_results)

        # Boost if multiple officials have high scores
        high_scores = sum(1 for r in repeat_results if r.repeat_score > 0.7)
        if high_scores > 2:
            avg_score = min(1.0, avg_score * 1.2)

        return avg_score

    def _calculate_confidence(
        self,
        vendor_count: int,
        official_count: int,
        pattern_count: int
    ) -> float:
        """Calculate confidence in the detection."""
        # Base confidence from data availability
        if vendor_count >= 30:
            vendor_conf = 0.9
        elif vendor_count >= 15:
            vendor_conf = 0.7
        elif vendor_count >= 10:
            vendor_conf = 0.5
        elif vendor_count >= 5:
            vendor_conf = 0.3
        else:
            vendor_conf = 0.1

        # Official data confidence
        if official_count >= 10:
            official_conf = 0.9
        elif official_count >= 5:
            official_conf = 0.7
        elif official_count >= 3:
            official_conf = 0.5
        else:
            official_conf = 0.3

        # Pattern detection confidence
        if pattern_count >= 5:
            pattern_conf = 0.9
        elif pattern_count >= 3:
            pattern_conf = 0.7
        elif pattern_count >= 1:
            pattern_conf = 0.5
        else:
            pattern_conf = 0.3

        # Weighted combination
        confidence = (
            vendor_conf * 0.4 +
            official_conf * 0.3 +
            pattern_conf * 0.3
        )

        return min(1.0, max(0.0, confidence))

    def _determine_risk_level(self, signal_value: float, confidence: float) -> str:
        """Determine risk level based on signal and confidence."""
        effective_signal = signal_value * confidence

        if effective_signal >= 0.75:
            return "HIGH"
        elif effective_signal >= 0.50:
            return "MEDIUM"
        elif effective_signal >= 0.25:
            return "LOW"
        else:
            return "NEGLIGIBLE"

    def _compile_risk_indicators(
        self,
        hhi_result: HHIResult,
        repeat_results: List[RepeatOfficialResult],
        risk_patterns: Dict[str, Any]
    ) -> List[str]:
        """Compile list of risk indicators."""
        indicators = []

        # HHI-based indicators
        if hhi_result.normalized_hhi >= 0.75:
            indicators.append("HIGH_MARKET_CONCENTRATION")
        elif hhi_result.normalized_hhi >= 0.50:
            indicators.append("MODERATE_MARKET_CONCENTRATION")

        # Dominant vendors
        if hhi_result.dominant_vendors:
            indicators.append(f"DOMINANT_VENDORS:{len(hhi_result.dominant_vendors)}")

        # Repeat official indicators
        for result in repeat_results:
            if result.repeat_score >= 0.7:
                indicators.append(f"HIGH_REPEAT_OFFICIAL:{result.official_id}")
            elif result.repeat_score >= 0.5:
                indicators.append(f"MODERATE_REPEAT_OFFICIAL:{result.official_id}")

        # Risk pattern indicators
        for pattern in risk_patterns.get('risk_patterns', []):
            indicators.append(f"PATTERN:{pattern['pattern']}")

        return list(set(indicators))  # Remove duplicates

    def _build_evidence(
        self,
        hhi_result: HHIResult,
        repeat_results: List[RepeatOfficialResult],
        risk_patterns: Dict[str, Any],
        signal_value: float
    ) -> List[str]:
        """Build human-readable evidence."""
        evidence = []

        # HHI evidence
        evidence.append(
            f"Market concentration HHI: {hhi_result.normalized_hhi:.3f} "
            f"({hhi_result.market_concentration_level})"
        )

        if hhi_result.dominant_vendors:
            dominant_names = [
                f"{v['vendor_name']} ({v['share']:.1%})"
                for v in hhi_result.dominant_vendors[:3]
            ]
            evidence.append(
                f"Dominant vendors: {', '.join(dominant_names)}"
            )

        evidence.append(
            f"Department has {hhi_result.vendor_count} vendors "
            f"with total spend ${hhi_result.total_spend:,.2f}"
        )

        # Repeat official evidence
        if repeat_results:
            high_repeat = [r for r in repeat_results if r.repeat_score > 0.7]
            if high_repeat:
                evidence.append(
                    f"Found {len(high_repeat)} officials with high vendor repeat rates"
                )
                for r in high_repeat[:2]:
                    evidence.append(
                        f"Official {r.official_name} has repeated relationships "
                        f"with {r.total_vendor_connections} vendors"
                    )

        # Risk patterns
        if risk_patterns.get('pattern_count', 0) > 0:
            evidence.append(
                f"Detected {risk_patterns['pattern_count']} risk patterns"
            )
            high_severity = risk_patterns.get('high_severity_count', 0)
            if high_severity > 0:
                evidence.append(
                    f"Found {high_severity} high severity risk patterns"
                )

        # Overall risk
        if signal_value > 0.5:
            evidence.append("Vendor graph indicates elevated fraud risk")

        return evidence

    def _build_recommendations(
        self,
        signal_value: float,
        risk_level: str,
        risk_patterns: Dict[str, Any]
    ) -> List[str]:
        """Build actionable recommendations."""
        recommendations = []

        if risk_level == "HIGH":
            recommendations.append(
                "URGENT: High vendor concentration detected - initiate investigation"
            )
            recommendations.append(
                "Review vendor selection processes for this department"
            )
            recommendations.append(
                "Consider expanding vendor pool to reduce concentration risk"
            )

        if risk_level == "MEDIUM":
            recommendations.append(
                "Medium risk detected - recommend secondary review"
            )
            recommendations.append(
                "Review procurement practices and vendor relationships"
            )
            recommendations.append(
                "Monitor vendor concentration trends over time"
            )

        # Pattern-specific recommendations
        for pattern in risk_patterns.get('risk_patterns', []):
            if pattern['pattern'] == 'HIGH_VENDOR_CONCENTRATION':
                recommendations.append(
                    "Implement vendor diversity requirements "
                    "to reduce market concentration"
                )
            elif pattern['pattern'] == 'REPEAT_OFFICIAL_RISK':
                recommendations.append(
                    "Review official-vendor relationships for potential conflicts"
                )
            elif pattern['pattern'] == 'OFFICIAL_SHARING_RISK':
                recommendations.append(
                    "Investigate potential collusion between vendors sharing officials"
                )
            elif pattern['pattern'] == 'VENDOR_DOMINANCE':
                recommendations.append(
                    "Review vendor that supplies to multiple departments"
                )

        if signal_value < 0.5:
            recommendations.append(
                "No significant risk indicators found - continue monitoring"
            )

        return recommendations

    def _create_no_context_result(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Create result when no department context provided."""
        return {
            "signal_value": 0.0,
            "confidence": 0.0,
            "hhi_score": 0.0,
            "normalized_hhi": 0.0,
            "repeat_score": 0.0,
            "normalized_repeat": 0.0,
            "department_id": None,
            "department_name": "Unknown",
            "risk_level": "NEGLIGIBLE",
            "risk_indicators": ["NO_DEPARTMENT_CONTEXT"],
            "evidence": ["No department context provided for graph analysis"],
            "recommendations": ["Provide department_id for graph-based risk detection"],
            "hhi_details": None,
            "repeat_details": [],
            "graph_stats": {},
            "transaction_id": transaction.get("transaction_id", str(uuid.uuid4()))
        }

    def _create_no_data_result(
        self,
        transaction: Dict[str, Any],
        department_id: str
    ) -> Dict[str, Any]:
        """Create result when no graph data available."""
        return {
            "signal_value": 0.0,
            "confidence": 0.0,
            "hhi_score": 0.0,
            "normalized_hhi": 0.0,
            "repeat_score": 0.0,
            "normalized_repeat": 0.0,
            "department_id": department_id,
            "department_name": "Unknown",
            "risk_level": "NEGLIGIBLE",
            "risk_indicators": ["INSUFFICIENT_DATA"],
            "evidence": ["Insufficient transaction history for graph analysis"],
            "recommendations": [
                "Wait for more transactions to build reliable graph",
                f"Need at least {self.min_transactions} transactions"
            ],
            "hhi_details": None,
            "repeat_details": [],
            "graph_stats": {},
            "transaction_id": transaction.get("transaction_id", str(uuid.uuid4()))
        }

    def _create_error_result(self, transaction: Dict[str, Any], error: str) -> Dict[str, Any]:
        """Create error result."""
        return {
            "signal_value": 0.0,
            "confidence": 0.0,
            "hhi_score": 0.0,
            "normalized_hhi": 0.0,
            "repeat_score": 0.0,
            "normalized_repeat": 0.0,
            "department_id": transaction.get("department_id"),
            "department_name": "Unknown",
            "risk_level": "NEGLIGIBLE",
            "risk_indicators": ["DETECTION_ERROR"],
            "evidence": [f"Detection failed: {error}"],
            "recommendations": ["Retry detection or check graph data"],
            "hhi_details": None,
            "repeat_details": [],
            "graph_stats": {},
            "transaction_id": transaction.get("transaction_id", str(uuid.uuid4())),
            "error": error
        }

    def get_weight(self) -> float:
        """Get detector weight for scoring."""
        return 0.20  # As per architecture

    def get_required_fields(self) -> List[str]:
        """Get required transaction fields."""
        return [
            "department_id",
            "vendor_id",
            "amount",
            "transaction_date"
        ]