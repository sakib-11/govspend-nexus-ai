from fastapi import APIRouter, Request, HTTPException, status, Depends
from typing import Optional, List
from datetime import datetime, date
from uuid import UUID
from models.audit import HashChainEntry, DailySnapshot
from services.hashchain_service import HashChainService
from services.snapshot_service import SnapshotService

router = APIRouter(prefix="/api/v1/hashchain", tags=["hashchain"])

@router.get("/latest")
async def get_latest_entry(
    request: Request,
    hashchain_service: HashChainService
):
    """Get the latest hash chain entry"""
    
    user = getattr(request.state, 'user', None)
    if not user or not user.is_super_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view hash chain"
        )
    
    entry = await hashchain_service.get_latest_entry()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No entries found"
        )
    
    return entry

@router.get("/entry/{entry_id}")
async def get_entry(
    entry_id: UUID,
    request: Request,
    hashchain_service: HashChainService
):
    """Get hash chain entry by ID"""
    
    user = getattr(request.state, 'user', None)
    if not user or not user.is_super_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view hash chain"
        )
    
    entry = await hashchain_service.get_entry(entry_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entry not found"
        )
    
    return entry

@router.get("/sequence/{sequence}")
async def get_entry_by_sequence(
    sequence: int,
    request: Request,
    hashchain_service: HashChainService
):
    """Get hash chain entry by sequence number"""
    
    user = getattr(request.state, 'user', None)
    if not user or not user.is_super_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view hash chain"
        )
    
    entry = await hashchain_service.get_entry_by_sequence(sequence)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entry not found"
        )
    
    return entry

@router.get("/snapshot/{snapshot_date}")
async def get_snapshot(
    snapshot_date: date,
    request: Request,
    hashchain_service: HashChainService
):
    """Get snapshot by date"""
    
    user = getattr(request.state, 'user', None)
    if not user or not user.is_super_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view snapshots"
        )
    
    snapshot = await hashchain_service.get_snapshot(snapshot_date)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Snapshot not found"
        )
    
    return snapshot

@router.post("/snapshot/force")
async def force_create_snapshot(
    request: Request,
    snapshot_service: SnapshotService,
    snapshot_date: date
):
    """Force create a snapshot for a specific date"""
    
    user = getattr(request.state, 'user', None)
    if not user or not user.is_super_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can force snapshots"
        )
    
    try:
        snapshot = await snapshot_service.force_create_snapshot(snapshot_date)
        if not snapshot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No entries found for this date"
            )
        
        return {"status": "created", "snapshot": snapshot}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/status")
async def get_chain_status(
    request: Request,
    hashchain_service: HashChainService
):
    """Get hash chain status"""
    
    user = getattr(request.state, 'user', None)
    if not user or not user.is_super_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view chain status"
        )
    
    latest = await hashchain_service.get_latest_entry()
    
    return {
        "total_entries": latest.sequence_number if latest else 0,
        "latest_sequence": latest.sequence_number if latest else 0,
        "latest_hash": latest.current_hash if latest else None,
        "status": "healthy",
        "verified": latest.verified if latest else False
    }
