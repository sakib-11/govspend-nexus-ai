"""Canonicalization API routes."""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
import logging
from datetime import datetime

from ..canonical.canonicalizer import Canonicalizer
from ..canonical.validator import TransactionValidator
from ..models.canonical import CanonicalTransaction

router = APIRouter(prefix="/canonical", tags=["Canonicalization"])
logger = logging.getLogger(__name__)

# Global canonicalizer instance
_canonicalizer = None

def get_canonicalizer() -> Canonicalizer:
    """Get or create canonicalizer instance."""
    global _canonicalizer
    if _canonicalizer is None:
        _canonicalizer = Canonicalizer(strict_mode=True)
    return _canonicalizer

@router.post("/canonicalize")
async def canonicalize_transaction(
    request: Request,
    data: Dict[str, Any],
    source_id: Optional[str] = None,
    canonicalizer: Canonicalizer = Depends(get_canonicalizer)
):
    """
    Canonicalize raw transaction data.
    
    Args:
        data: Raw transaction data
        source_id: Optional source upload ID
        
    Returns:
        Canonicalized transaction
    """
    try:
        # Use provided source_id or generate one
        source_id = source_id or f"manual_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Canonicalize the data
        result = await canonicalizer.canonicalize(
            raw_data=data,
            source_id=source_id
        )
        
        return JSONResponse(result)
        
    except Exception as e:
        logger.error(f"Canonicalization error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/validate")
async def validate_transaction(
    request: Request,
    data: Dict[str, Any]
):
    """
    Validate transaction data without canonicalizing.
    
    Args:
        data: Transaction data to validate
        
    Returns:
        Validation results
    """
    try:
        validator = TransactionValidator()
        transaction, errors, warnings = validator.validate(data)
        
        return JSONResponse({
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'transaction': transaction.to_dict() if transaction else None
        })
        
    except Exception as e:
        logger.error(f"Validation error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/schema")
async def get_canonical_schema():
    """Get the canonical transaction schema."""
    try:
        # Generate schema from model
        schema = CanonicalTransaction.schema()
        return JSONResponse(schema)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_canonicalization_stats(
    canonicalizer: Canonicalizer = Depends(get_canonicalizer)
):
    """Get canonicalization statistics."""
    return JSONResponse(canonicalizer.get_stats())

@router.post("/batch")
async def batch_canonicalize(
    request: Request,
    items: Dict[str, Any],
    canonicalizer: Canonicalizer = Depends(get_canonicalizer)
):
    """
    Batch canonicalize multiple transactions.
    
    Args:
        items: Dictionary with 'source_id' and 'data' for each transaction
              Format: {"transactions": [{"source_id": "id1", "data": {...}}]}
        
    Returns:
        Batch results
    """
    try:
        transactions = items.get('transactions', [])
        if not transactions:
            raise HTTPException(status_code=400, detail="No transactions provided")
        
        results = []
        for item in transactions:
            source_id = item.get('source_id', f"batch_{datetime.now().strftime('%Y%m%d%H%M%S')}")
            data = item.get('data', {})
            
            result = await canonicalizer.canonicalize(
                raw_data=data,
                source_id=source_id
            )
            results.append({
                'source_id': source_id,
                'result': result
            })
        
        return JSONResponse({
            'total': len(results),
            'successful': sum(1 for r in results if r['result']['success']),
            'failed': sum(1 for r in results if not r['result']['success']),
            'results': results,
            'timestamp': datetime.now().isoformat()
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch canonicalization error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

