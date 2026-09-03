from fastapi import APIRouter, Request, HTTPException, status, Depends
from typing import Optional
from datetime import date
from uuid import UUID
from models.audit import VerificationResult
from services.hashchain_service import HashChainService

router = APIRouter(prefix="/api/v1/verify", tags=["verification"])

@router.post("/chain")
async def verify_chain(
    request: Request,
    hashchain_service: HashChainService,
    start_sequence: Optional[int] = None,
    end_sequence: Optional[int] = None
):
    """Verify the hash chain integrity"""
    
    user = getattr(request.state, 'user', None)
    if not user or not user.is_super_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can verify hash chain"
        )
    
    result = await hashchain_service.verify_chain(start_sequence, end_sequence)
    return result

@router.post("/snapshot/{snapshot_date}")
async def verify_snapshot(
    snapshot_date: date,
    request: Request,
    hashchain_service: HashChainService
):
    """Verify a snapshot's integrity"""
    
    user = getattr(request.state, 'user', None)
    if not user or not user.is_super_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can verify snapshots"
        )
    
    snapshot = await hashchain_service.get_snapshot(snapshot_date)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Snapshot not found"
        )
    
    result = await hashchain_service.verify_snapshot(snapshot.snapshot_id)
    return result
