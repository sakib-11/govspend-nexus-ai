from fastapi import APIRouter, Request, HTTPException, status, Depends
from typing import Optional, List
from models.ledger import (
    LedgerCreateRequest, LedgerReadRequest, LedgerUpdateRequest,
    LedgerResponse, EntityType, LedgerAuditLog
)
from services.ledger_service import LedgerService
from middleware.auth_middleware import require_service_auth

router = APIRouter(prefix="/api/v1/ledger", tags=["ledger"])

@router.post("/entries")
@require_service_auth
async def create_ledger_entry(
    request: LedgerCreateRequest,
    req: Request,
    ledger_service: LedgerService
):
    """Create a ledger entry"""
    
    # Get service info from request state
    service_name = getattr(req.state, 'service_name', 'unknown')
    user_id = getattr(req.state, 'user_id', 'system')
    
    try:
        result = await ledger_service.create_entry(
            request=request,
            service_name=service_name,
            user_id=user_id,
            ip_address=req.client.host if req.client else None
        )
        return result
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/entries/read")
@require_service_auth
async def read_ledger_entry(
    request: LedgerReadRequest,
    req: Request,
    ledger_service: LedgerService
):
    """Read a ledger entry"""
    
    service_name = getattr(req.state, 'service_name', 'unknown')
    user_id = getattr(req.state, 'user_id', 'system')
    
    try:
        result = await ledger_service.read_entry(
            request=request,
            service_name=service_name,
            user_id=user_id,
            ip_address=req.client.host if req.client else None
        )
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Entry not found"
            )
        
        return result
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put("/entries")
@require_service_auth
async def update_ledger_entry(
    request: LedgerUpdateRequest,
    req: Request,
    ledger_service: LedgerService
):
    """Update a ledger entry"""
    
    service_name = getattr(req.state, 'service_name', 'unknown')
    user_id = getattr(req.state, 'user_id', 'system')
    
    try:
        result = await ledger_service.update_entry(
            request=request,
            service_name=service_name,
            user_id=user_id,
            ip_address=req.client.host if req.client else None
        )
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Entry not found"
            )
        
        return result
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete("/entries/{entity_type}/{entity_token}")
@require_service_auth
async def delete_ledger_entry(
    entity_type: EntityType,
    entity_token: str,
    req: Request,
    ledger_service: LedgerService
):
    """Delete a ledger entry"""
    
    service_name = getattr(req.state, 'service_name', 'unknown')
    user_id = getattr(req.state, 'user_id', 'system')
    
    try:
        result = await ledger_service.delete_entry(
            entity_type=entity_type,
            entity_token=entity_token,
            service_name=service_name,
            user_id=user_id,
            ip_address=req.client.host if req.client else None
        )
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Entry not found"
            )
        
        return {"status": "deleted", "entity_type": entity_type.value, "entity_token": entity_token}
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/entries/{entity_type}/{entity_token}")
@require_service_auth
async def get_ledger_entry(
    entity_type: EntityType,
    entity_token: str,
    req: Request,
    ledger_service: LedgerService,
    decrypt: bool = True
):
    """Get ledger entry"""
    
    service_name = getattr(req.state, 'service_name', 'unknown')
    user_id = getattr(req.state, 'user_id', 'system')
    
    request = LedgerReadRequest(
        entity_type=entity_type,
        entity_token=entity_token,
        decrypt=decrypt
    )
    
    try:
        result = await ledger_service.read_entry(
            request=request,
            service_name=service_name,
            user_id=user_id,
            ip_address=req.client.host if req.client else None
        )
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Entry not found"
            )
        
        return result
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/audit")
@require_service_auth
async def get_audit_logs(
    req: Request,
    ledger_service: LedgerService,
    entry_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """Get audit logs"""
    
    # Only admin services can access audit logs
    service_name = getattr(req.state, 'service_name', 'unknown')
    if service_name != 'admin-svc':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin services can access audit logs"
        )
    
    logs = await ledger_service.get_audit_logs(
        entry_id=UUID(entry_id) if entry_id else None,
        limit=limit,
        offset=offset
    )
    
    return {
        "logs": logs,
        "total": len(logs),
        "limit": limit,
        "offset": offset
    }

@router.post("/batch")
@require_service_auth
async def batch_read_entries(
    req: Request,
    entity_type: EntityType,
    entity_tokens: List[str],
    ledger_service: LedgerService,
    decrypt: bool = True
):
    """Batch read ledger entries"""
    
    service_name = getattr(req.state, 'service_name', 'unknown')
    user_id = getattr(req.state, 'user_id', 'system')
    
    try:
        results = await ledger_service.batch_read(
            entity_type=entity_type,
            entity_tokens=entity_tokens,
            service_name=service_name,
            user_id=user_id,
            decrypt=decrypt
        )
        
        return {
            "entity_type": entity_type.value,
            "results": results,
            "total": len(results),
            "decrypted": decrypt
        }
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
