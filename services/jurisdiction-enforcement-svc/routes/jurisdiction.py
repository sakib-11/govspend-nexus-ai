from fastapi import APIRouter, Request, HTTPException, status, Depends
from typing import Optional, List
from models.jurisdiction import (
    Jurisdiction, UserJurisdiction, CrossJurisdictionRequest,
    CrossJurisdictionApproval
)
from services.jurisdiction_enforcer import JurisdictionEnforcer
from services.hierarchy_manager import HierarchyManager
from decorators.jurisdiction import require_jurisdiction, require_same_jurisdiction

router = APIRouter(prefix="/api/v1/jurisdiction", tags=["jurisdiction"])

@router.get("/hierarchy")
async def get_hierarchy(
    request: Request,
    hierarchy_manager: HierarchyManager
):
    """Get jurisdiction hierarchy"""
    
    # Only admins can view full hierarchy
    user = getattr(request.state, 'user', None)
    if not user or not user.is_super_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view full hierarchy"
        )
    
    levels = hierarchy_manager.get_hierarchy_levels()
    
    # Get all jurisdictions
    jurisdictions = {}
    for node_id in hierarchy_manager._graph.nodes():
        data = hierarchy_manager._graph.nodes[node_id]['data']
        jurisdictions[node_id] = {
            "id": data.jurisdiction_id,
            "code": data.code,
            "name": data.name,
            "level": data.level.value,
            "parent_id": data.parent_id,
            "depth": data.depth,
            "ancestors": data.ancestors,
            "descendants": data.descendants
        }
    
    return {
        "levels": levels,
        "jurisdictions": jurisdictions,
        "total": len(jurisdictions)
    }

@router.get("/my")
async def get_my_jurisdictions(
    request: Request
):
    """Get current user's jurisdictions"""
    
    user = getattr(request.state, 'user', None)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    return {
        "user_id": user.user_id,
        "jurisdictions": user.jurisdictions,
        "total": len(user.jurisdictions)
    }

@router.get("/resource/{resource_type}/{resource_id}")
async def get_resource_jurisdiction(
    resource_type: str,
    resource_id: str,
    request: Request,
    enforcer: JurisdictionEnforcer
):
    """Get jurisdiction for a resource"""
    
    user = getattr(request.state, 'user', None)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    # In production, fetch from database
    # For now, return mock jurisdiction
    return {
        "resource_type": resource_type,
        "resource_id": resource_id,
        "jurisdiction_id": "jur-002",
        "jurisdiction_name": "California"
    }

@router.post("/cross/request")
async def request_cross_jurisdiction(
    request: Request,
    cross_request: CrossJurisdictionRequest,
    enforcer: JurisdictionEnforcer
):
    """Request cross-jurisdiction access"""
    
    user = getattr(request.state, 'user', None)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    # Ensure user is requesting for themselves
    if cross_request.user_id != user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Users can only request cross-jurisdiction access for themselves"
        )
    
    # Request cross-jurisdiction access
    approval = await enforcer.request_cross_jurisdiction_access(cross_request)
    
    return approval

@router.post("/cross/approve/{request_id}")
async def approve_cross_jurisdiction(
    request_id: str,
    request: Request,
    enforcer: JurisdictionEnforcer,
    approved: bool = True,
    reason: Optional[str] = None
):
    """Approve or reject cross-jurisdiction request"""
    
    user = getattr(request.state, 'user', None)
    if not user or not user.is_super_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can approve cross-jurisdiction requests"
        )
    
    approval = await enforcer.approve_cross_jurisdiction(
        request_id=request_id,
        approved_by=user.user_id,
        approved=approved,
        reason=reason
    )
    
    return approval

@router.get("/audit")
async def get_jurisdiction_audit(
    request: Request,
    audit_service: EnforcementAudit,
    user_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """Get jurisdiction audit logs"""
    
    user = getattr(request.state, 'user', None)
    if not user or not user.is_super_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view audit logs"
        )
    
    logs = await audit_service.get_audit_logs(
        user_id=user_id,
        limit=limit,
        offset=offset
    )
    
    stats = await audit_service.get_stats(user_id=user_id)
    
    return {
        "logs": logs,
        "stats": stats,
        "limit": limit,
        "offset": offset,
        "total": len(logs)
    }

@router.get("/test")
@require_jurisdiction("jur-002")
async def test_jurisdiction(request: Request):
    """Test jurisdiction enforcement"""
    return {
        "status": "success",
        "message": "Jurisdiction access granted",
        "user": getattr(request.state, 'user', None)
    }

@router.get("/test/cross")
@require_jurisdiction("jur-004")
async def test_cross_jurisdiction(request: Request):
    """Test cross-jurisdiction access"""
    return {
        "status": "success", 
        "message": "Cross-jurisdiction access granted",
        "user": getattr(request.state, 'user', None)
    }