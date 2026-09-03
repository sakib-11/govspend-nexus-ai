"""Vendor graph routes for the Detection Service."""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from datetime import datetime

from ..detectors.vendor_graph_risk import VendorGraphRiskDetector
from ..graph.graph_builder import GraphBuilder
from ..graph.graph_analyzer import GraphAnalyzer
from ..utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

# Initialize components
graph_detector = VendorGraphRiskDetector()
graph_builder = GraphBuilder()
graph_analyzer = GraphAnalyzer()

@router.post("/detect/vendor-graph-risk")
async def detect_vendor_graph_risk(transaction: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detect vendor graph risk for a transaction.

    Required fields:
    - department_id: str
    - vendor_id: str
    - amount: float
    - transaction_date: date

    Returns risk signal and detailed analysis
    """
    try:
        result = await graph_detector.detect(transaction)

        logger.info(
            f"Vendor graph risk detection: signal={result['signal_value']:.3f}, "
            f"risk_level={result['risk_level']}"
        )

        return result

    except Exception as e:
        logger.error(f"Vendor graph risk detection failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/graph/build")
async def build_graph(
    department_id: str,
    lookback_days: int = 365
) -> Dict[str, Any]:
    """Build vendor relationship graph for a department"""
    try:
        graph = await graph_builder.build_graph(
            department_id=department_id,
            lookback_days=lookback_days,
            include_officials=True
        )

        return {
            "department_id": department_id,
            "node_count": graph.node_count,
            "edge_count": graph.edge_count,
            "avg_degree": graph.avg_degree,
            "built_at": graph.built_at.isoformat()
        }

    except Exception as e:
        logger.error(f"Graph build failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/graph/analyze/hhi")
async def analyze_hhi(
    department_id: str,
    period: str = "last_12_months"
) -> Dict[str, Any]:
    """Calculate HHI for a department"""
    try:
        # Build graph
        graph = await graph_builder.build_graph(
            department_id=department_id,
            lookback_days=365,
            include_officials=True
        )

        # Analyze HHI
        hhi_result = await graph_analyzer.analyze_hhi(graph, department_id, period)

        return hhi_result.model_dump()

    except Exception as e:
        logger.error(f"HHI analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/graph/analyze/repeat-officials")
async def analyze_repeat_officials(department_id: str) -> List[Dict[str, Any]]:
    """Analyze repeat official-vendor relationships"""
    try:
        # Build graph
        graph = await graph_builder.build_graph(
            department_id=department_id,
            lookback_days=365,
            include_officials=True
        )

        # Analyze repeat officials
        results = await graph_analyzer.analyze_repeat_officials(graph, department_id)

        return [r.model_dump() for r in results]

    except Exception as e:
        logger.error(f"Repeat official analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/detectors/vendor-graph/stats")
async def get_vendor_graph_stats():
    """Get statistics about vendor graph detector"""
    return {
        "detector": "vendor_graph_risk",
        "weight": graph_detector.get_weight(),
        "required_fields": graph_detector.get_required_fields(),
        "lookback_days": graph_detector.lookback_days,
        "hhi_weight": graph_detector.hhi_weight,
        "repeat_weight": graph_detector.repeat_weight,
        "min_transactions": graph_detector.min_transactions,
        "min_vendors": graph_detector.min_vendors
    }