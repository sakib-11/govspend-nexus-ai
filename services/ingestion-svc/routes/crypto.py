"""Crypto API routes for hashing and tokenization."""

from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

from ..crypto.hasher import DocumentHasher, get_hasher
from ..crypto.tokenizer import Tokenizer, get_tokenizer
from ..crypto.key_manager import KeyManager, get_key_manager
from ..models.crypto import TokenPrefix, DocumentHashResult, TokenResult

router = APIRouter(prefix="/crypto", tags=["Crypto"])
logger = logging.getLogger(__name__)

@router.post("/hash/document")
async def hash_document(
    request: Request,
    content: Dict[str, Any]
):
    """
    Hash a document or transaction.
    
    Args:
        content: Document content to hash
        
    Returns:
        Document hash result
    """
    try:
        hasher = get_hasher()
        
        # Check if this is a canonical transaction
        if 'document_number' in content and 'vendor' in content:
            result = hasher.hash_canonical_transaction(content)
        else:
            result = hasher.hash_document(content)
        
        return JSONResponse(result.dict())
        
    except Exception as e:
        logger.error(f"Hashing error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/hash/verify")
async def verify_hash(
    request: Request,
    content: Dict[str, Any],
    expected_hash: str = Query(..., description="Expected hash to verify against")
):
    """
    Verify a document against an expected hash.
    
    Args:
        content: Document content
        expected_hash: Expected hash
        
    Returns:
        Verification result
    """
    try:
        hasher = get_hasher()
        verified = hasher.verify_document(content, expected_hash)
        
        return JSONResponse({
            "verified": verified,
            "expected_hash": expected_hash,
            "actual_hash": hasher.hash_document(content).invoice_doc_hash,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Hash verification error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tokenize")
async def tokenize_identifier(
    request: Request,
    identifier: str = Query(..., description="Identifier to tokenize"),
    prefix: str = Query("VENDOR", description="Token prefix (VENDOR, TXN, DOC, USER, DEPT)"),
    salt: Optional[str] = Query(None, description="Optional salt for additional security")
):
    """
    Tokenize an identifier using HMAC-SHA256 + Base32.
    
    Args:
        identifier: Identifier to tokenize
        prefix: Token prefix
        salt: Optional salt
        
    Returns:
        Token result
    """
    try:
        tokenizer = get_tokenizer()
        
        # Convert prefix string to enum
        prefix_map = {
            "VENDOR": TokenPrefix.VENDOR,
            "TXN": TokenPrefix.TRANSACTION,
            "DOC": TokenPrefix.DOCUMENT,
            "USER": TokenPrefix.USER,
            "DEPT": TokenPrefix.DEPARTMENT
        }
        
        if prefix.upper() not in prefix_map:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid prefix: {prefix}. Allowed: {list(prefix_map.keys())}"
            )
        
        token_prefix = prefix_map[prefix.upper()]
        result = tokenizer.tokenize(identifier, token_prefix, salt)
        
        return JSONResponse(result.dict())
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Tokenization error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tokenize/batch")
async def batch_tokenize(
    request: Request,
    identifiers: List[str] = Query(..., description="List of identifiers to tokenize"),
    prefix: str = Query("VENDOR", description="Token prefix")
):
    """
    Batch tokenize multiple identifiers.
    
    Args:
        identifiers: List of identifiers
        prefix: Token prefix
        
    Returns:
        Batch tokenization results
    """
    try:
        tokenizer = get_tokenizer()
        
        # Convert prefix string to enum
        prefix_map = {
            "VENDOR": TokenPrefix.VENDOR,
            "TXN": TokenPrefix.TRANSACTION,
            "DOC": TokenPrefix.DOCUMENT,
            "USER": TokenPrefix.USER,
            "DEPT": TokenPrefix.DEPARTMENT
        }
        
        if prefix.upper() not in prefix_map:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid prefix: {prefix}. Allowed: {list(prefix_map.keys())}"
            )
        
        token_prefix = prefix_map[prefix.upper()]
        results = tokenizer.batch_tokenize(identifiers, token_prefix)
        
        return JSONResponse({
            "total": len(results),
            "successful": sum(1 for r in results.values() if r is not None),
            "failed": sum(1 for r in results.values() if r is None),
            "results": {
                k: v.dict() if v else None 
                for k, v in results.items()
            },
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Batch tokenization error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/token/verify")
async def verify_token(
    request: Request,
    original: str = Query(..., description="Original identifier"),
    token: str = Query(..., description="Token to verify"),
    prefix: str = Query("VENDOR", description="Token prefix")
):
    """
    Verify a token against an original identifier.
    
    Args:
        original: Original identifier
        token: Token to verify
        prefix: Token prefix
        
    Returns:
        Verification result
    """
    try:
        tokenizer = get_tokenizer()
        
        # Convert prefix string to enum
        prefix_map = {
            "VENDOR": TokenPrefix.VENDOR,
            "TXN": TokenPrefix.TRANSACTION,
            "DOC": TokenPrefix.DOCUMENT,
            "USER": TokenPrefix.USER,
            "DEPT": TokenPrefix.DEPARTMENT
        }
        
        if prefix.upper() not in prefix_map:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid prefix: {prefix}. Allowed: {list(prefix_map.keys())}"
            )
        
        token_prefix = prefix_map[prefix.upper()]
        verified = tokenizer.verify_token(original, token, token_prefix)
        
        return JSONResponse({
            "verified": verified,
            "original": original,
            "token": token,
            "prefix": prefix,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/keys/status")
async def get_key_status():
    """Get key management status."""
    try:
        key_manager = get_key_manager()
        return JSONResponse(key_manager.key_status())
    except Exception as e:
        logger.error(f"Key status error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/keys/rotate/hmac")
async def rotate_hmac_key():
    """Rotate the HMAC key."""
    try:
        key_manager = get_key_manager()
        result = key_manager.rotate_hmac_key()
        logger.info("HMAC key rotated successfully")
        return JSONResponse({
            "success": True,
            "key_id": result["id"],
            "created_at": result["created_at"],
            "expires_at": result["expires_at"],
            "message": "HMAC key rotated successfully. Old key kept for verification."
        })
    except Exception as e:
        logger.error(f"Key rotation error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/info")
async def get_crypto_info():
    """Get crypto service information."""
    return JSONResponse({
        "service": "Crypto Service",
        "hash_algorithm": "SHA-256",
        "token_algorithm": "HMAC-SHA256",
        "token_encoding": "Base32",
        "token_prefixes": [p.value for p in TokenPrefix],
        "key_rotation_days": 90,
        "timestamp": datetime.now().isoformat()
    })

