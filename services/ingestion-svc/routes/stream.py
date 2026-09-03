"""Stream API routes."""

from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

from ..stream.publisher import StreamPublisher, get_publisher
from ..stream.config import StreamConfig
from ..models.canonical import CanonicalTransaction
from ..models.stream import PublishResult, StreamName

router = APIRouter(prefix="/stream", tags=["Stream"])
logger = logging.getLogger(__name__)

@router.post("/publish")
async def publish_transaction(
    request: Request,
    transaction: Dict[str, Any],
    stream_name: str = StreamConfig.STREAM_TX_INGESTED,
    publisher: StreamPublisher = Depends(get_publisher)
):
    """
    Publish a transaction to a stream.
    
    Args:
        transaction: Transaction data
        stream_name: Target stream name
        
    Returns:
        Publish result
    """
    try:
        # Validate stream name
        valid_streams = [
            StreamConfig.STREAM_TX_INGESTED,
            StreamConfig.STREAM_TX_VALIDATED,
            StreamConfig.STREAM_TX_DETECTED,
            StreamConfig.STREAM_TX_SCORED,
            StreamConfig.STREAM_TX_CANONICALIZED,
            StreamConfig.STREAM_TX_ERROR,
            StreamConfig.STREAM_TX_AUDIT
        ]
        
        if stream_name not in valid_streams:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid stream name: {stream_name}. Allowed: {valid_streams}"
            )
        
        # Convert to CanonicalTransaction
        try:
            canonical_tx = CanonicalTransaction(**transaction)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid transaction data: {str(e)}"
            )
        
        # Publish to stream
        result = await publisher.publish_transaction(
            transaction=canonical_tx,
            stream_name=stream_name,
            metadata={"source": "api"}
        )
        
        if result.success:
            return JSONResponse({
                "success": True,
                "message_id": result.message_id,
                "stream": stream_name,
                "timestamp": result.timestamp.isoformat()
            })
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to publish: {result.error}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Publish error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/publish/batch")
async def publish_batch(
    request: Request,
    transactions: List[Dict[str, Any]],
    stream_name: str = StreamConfig.STREAM_TX_INGESTED,
    publisher: StreamPublisher = Depends(get_publisher)
):
    """
    Publish multiple transactions in batch.
    
    Args:
        transactions: List of transactions
        stream_name: Target stream name
        
    Returns:
        Batch publish results
    """
    try:
        # Convert to CanonicalTransaction objects
        canonical_txs = []
        errors = []
        
        for i, tx_data in enumerate(transactions):
            try:
                canonical_txs.append(CanonicalTransaction(**tx_data))
            except Exception as e:
                errors.append({
                    "index": i,
                    "error": str(e)
                })
        
        if not canonical_txs:
            raise HTTPException(
                status_code=400,
                detail=f"No valid transactions found. Errors: {errors}"
            )
        
        # Publish batch
        results = await publisher.publish_batch(
            transactions=canonical_txs,
            stream_name=stream_name
        )
        
        return JSONResponse({
            "total": len(results),
            "successful": sum(1 for r in results if r.success),
            "failed": sum(1 for r in results if not r.success),
            "results": [
                {
                    "message_id": r.message_id,
                    "success": r.success,
                    "error": r.error
                }
                for r in results
            ],
            "errors": errors,
            "timestamp": datetime.now().isoformat()
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch publish error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/info/{stream_name}")
async def get_stream_info(
    stream_name: str,
    publisher: StreamPublisher = Depends(get_publisher)
):
    """Get information about a stream."""
    try:
        info = await publisher.get_stream_info(stream_name)
        metadata = StreamConfig.get_stream_info(stream_name)
        
        return JSONResponse({
            "stream": stream_name,
            "info": info,
            "metadata": metadata,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Get stream info error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/info")
async def list_streams():
    """List all available streams."""
    try:
        streams = []
        metadata = StreamConfig.get_stream_metadata()
        
        for stream_name in metadata.keys():
            streams.append({
                "name": stream_name,
                "description": metadata[stream_name]["description"],
                "consumers": metadata[stream_name]["consumers"],
                "retention_days": metadata[stream_name]["retention_days"]
            })
        
        return JSONResponse({
            "streams": streams,
            "total": len(streams),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"List streams error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def stream_health(
    publisher: StreamPublisher = Depends(get_publisher)
):
    """Check stream service health."""
    try:
        health = await publisher.health_check()
        return JSONResponse({
            "healthy": health,
            "service": "stream",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "healthy": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

