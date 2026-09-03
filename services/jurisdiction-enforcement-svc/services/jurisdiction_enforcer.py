from typing import List, Optional, Dict, Any, Set, Tuple
from datetime import datetime, timedelta
import hashlib
from models.jurisdiction import (
    JurisdictionEnforcementRequest, JurisdictionEnforcementResult,
    JurisdictionAccess, CrossJurisdictionRequest, CrossJurisdictionApproval
)
from services.hierarchy_manager import HierarchyManager
from services.jurisdiction_cache import JurisdictionCache
from services.enforcement_audit import EnforcementAudit

class JurisdictionEnforcer:
    """Enforce jurisdiction-based access control"""
    
    def __init__(self, hierarchy_manager: HierarchyManager, 
                 jurisdiction_cache: JurisdictionCache,
                 audit_service: EnforcementAudit):
        self.hierarchy_manager = hierarchy_manager
        self.cache = jurisdiction_cache
        self.audit = audit_service
        
        # Cross-jurisdiction request cache
        self._cross_jurisdiction_requests = {}
    
    async def enforce(self, request: JurisdictionEnforcementRequest) -> JurisdictionEnforcementResult:
        """
        Enforce jurisdiction access for a request
        
        Checks:
        1. User has access to the jurisdiction
        2. Hierarchy allows access (ancestor/descendant relationships)
        3. Cross-jurisdiction approvals if applicable
        4. Resource-specific access rules
        """
        
        # Check cache first
        cache_key = self._get_cache_key(request)
        cached_result = await self.cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # Build result
        result = JurisdictionEnforcementResult(
            user_id=request.user_id,
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            resource_jurisdiction=request.resource_jurisdiction,
            allowed=False,
            reason="",
            timestamp=datetime.now()
        )
        
        try:
            # 1. Validate jurisdictions exist
            if not self.hierarchy_manager.is_jurisdiction_in_hierarchy(request.resource_jurisdiction):
                result.reason = f"Resource jurisdiction '{request.resource_jurisdiction}' not found in hierarchy"
                await self.audit.log_enforcement(request, result)
                return result
            
            # 2. Check if user has any jurisdiction access
            if not request.user_jurisdictions:
                result.reason = "User has no jurisdiction assignments"
                await self.audit.log_enforcement(request, result)
                return result
            
            # 3. Check direct access
            if request.resource_jurisdiction in request.user_jurisdictions:
                result.allowed = True
                result.reason = "Direct jurisdiction access granted"
                result.matching_jurisdictions = [request.resource_jurisdiction]
                await self.audit.log_enforcement(request, result)
                await self.cache.set(cache_key, result)
                return result
            
            # 4. Check hierarchical access (ancestor/descendant)
            hierarchy_result = await self._check_hierarchy_access(request)
            if hierarchy_result['allowed']:
                result.allowed = True
                result.reason = hierarchy_result['reason']
                result.matching_jurisdictions = hierarchy_result['matching_jurisdictions']
                result.hierarchy_check = hierarchy_result
                await self.audit.log_enforcement(request, result)
                await self.cache.set(cache_key, result)
                return result
            
            # 5. Check cross-jurisdiction approval
            cross_jurisdiction_result = await self._check_cross_jurisdiction(request)
            if cross_jurisdiction_result['allowed']:
                result.allowed = True
                result.reason = "Cross-jurisdiction access approved"
                result.matching_jurisdictions = request.user_jurisdictions
                await self.audit.log_enforcement(request, result)
                await self.cache.set(cache_key, result)
                return result
            
            # 6. Deny access
            result.reason = f"User does not have access to jurisdiction '{request.resource_jurisdiction}'"
            await self.audit.log_enforcement(request, result)
            await self.cache.set(cache_key, result, ttl=60)  # Cache denials for shorter time
            
            return result
            
        except Exception as e:
            result.reason = f"Jurisdiction enforcement error: {str(e)}"
            await self.audit.log_enforcement(request, result)
            return result
    
    async def _check_hierarchy_access(self, request: JurisdictionEnforcementRequest) -> Dict[str, Any]:
        """Check hierarchical access (ancestor/descendant permissions)"""
        
        result = {
            'allowed': False,
            'reason': '',
            'matching_jurisdictions': []
        }
        
        resource_jur_id = request.resource_jurisdiction
        
        for user_jur_id in request.user_jurisdictions:
            # Check if user's jurisdiction is an ancestor of resource
            if self.hierarchy_manager.is_ancestor(user_jur_id, resource_jur_id):
                result['allowed'] = True
                result['reason'] = f"User has access via ancestor jurisdiction '{user_jur_id}'"
                result['matching_jurisdictions'].append(user_jur_id)
                break
            
            # Check if user's jurisdiction is a descendant of resource
            if self.hierarchy_manager.is_descendant(user_jur_id, resource_jur_id):
                result['allowed'] = True
                result['reason'] = f"User has access via descendant jurisdiction '{user_jur_id}'"
                result['matching_jurisdictions'].append(user_jur_id)
                break
            
            # Check if they share a common ancestor
            common_ancestors = self.hierarchy_manager.get_common_ancestors([
                user_jur_id, resource_jur_id
            ])
            if common_ancestors:
                # Check if user has broad access at a higher level
                for ancestor in common_ancestors:
                    if self._has_high_level_access(request.user_id, ancestor):
                        result['allowed'] = True
                        result['reason'] = f"User has access via common ancestor '{ancestor}'"
                        result['matching_jurisdictions'].append(user_jur_id)
                        break
        
        return result
    
    def _has_high_level_access(self, user_id: str, jurisdiction_id: str) -> bool:
        """Check if user has high-level access to a jurisdiction"""
        
        # In production, this would check user's access level in the jurisdiction
        # For now, assume users with admin roles have high-level access
        return True
    
    async def _check_cross_jurisdiction(self, request: JurisdictionEnforcementRequest) -> Dict[str, Any]:
        """Check for cross-jurisdiction approval"""
        
        # Check if there's an active cross-jurisdiction request
        for req_id, cross_req in self._cross_jurisdiction_requests.items():
            if (cross_req.user_id == request.user_id and
                cross_req.target_jurisdiction == request.resource_jurisdiction):
                
                # Check if request is still valid
                if cross_req.expires_at and cross_req.expires_at < datetime.now():
                    continue
                
                # Check if approved
                approval = await self._get_cross_jurisdiction_approval(req_id)
                if approval and approval.approved:
                    return {
                        'allowed': True,
                        'reason': f"Cross-jurisdiction request {req_id} approved"
                    }
        
        return {'allowed': False, 'reason': 'No active cross-jurisdiction approval'}
    
    async def request_cross_jurisdiction_access(
        self, 
        request: CrossJurisdictionRequest
    ) -> CrossJurisdictionApproval:
        """Request cross-jurisdiction access"""
        
        # Store request
        request_id = f"cross-{hashlib.md5(request.user_id.encode()).hexdigest()[:8]}"
        self._cross_jurisdiction_requests[request_id] = request
        
        # Generate approval (in production, this would go to an approver)
        approval = CrossJurisdictionApproval(
            request_id=request_id,
            approved_by="system",  # In production, would be actual approver
            approved_at=datetime.now(),
            expires_at=datetime.now() + timedelta(days=7),
            approved=True,
            reason="Auto-approved for testing",
            conditions={
                "max_access_duration": 3600,  # 1 hour
                "audit_required": True
            }
        )
        
        return approval
    
    async def approve_cross_jurisdiction(
        self,
        request_id: str,
        approved_by: str,
        approved: bool,
        reason: Optional[str] = None
    ) -> CrossJurisdictionApproval:
        """Approve or reject cross-jurisdiction request"""
        
        if request_id not in self._cross_jurisdiction_requests:
            raise ValueError(f"Cross-jurisdiction request {request_id} not found")
        
        approval = CrossJurisdictionApproval(
            request_id=request_id,
            approved_by=approved_by,
            approved_at=datetime.now(),
            approved=approved,
            reason=reason
        )
        
        return approval
    
    async def _get_cross_jurisdiction_approval(self, request_id: str) -> Optional[CrossJurisdictionApproval]:
        """Get cross-jurisdiction approval"""
        
        # In production, this would fetch from database
        # For now, return a mock approval
        return CrossJurisdictionApproval(
            request_id=request_id,
            approved_by="system",
            approved_at=datetime.now(),
            approved=True,
            expires_at=datetime.now() + timedelta(days=7)
        )
    
    def _get_cache_key(self, request: JurisdictionEnforcementRequest) -> str:
        """Generate cache key for enforcement result"""
        
        components = [
            request.user_id,
            request.resource_id,
            request.resource_jurisdiction,
            request.action
        ]
        key_str = ":".join(components)
        return f"jurisdiction:enforcement:{hashlib.md5(key_str.encode()).hexdigest()}"
    
    async def check_jurisdiction_for_resource(
        self,
        user_jurisdictions: List[str],
        resource_jurisdiction: str,
        action: str = "read"
    ) -> Tuple[bool, str]:
        """Simple check if user can access resource jurisdiction"""
        
        # Direct access
        if resource_jurisdiction in user_jurisdictions:
            return True, "Direct access"
        
        # Hierarchical access
        for user_jur in user_jurisdictions:
            if (self.hierarchy_manager.is_ancestor(user_jur, resource_jurisdiction) or
                self.hierarchy_manager.is_descendant(user_jur, resource_jurisdiction)):
                return True, f"Hierarchical access via {user_jur}"
        
        return False, "No jurisdiction access"
    
    async def get_accessible_jurisdictions(
        self,
        user_jurisdictions: List[str],
        all_jurisdictions: List[str]
    ) -> List[str]:
        """Get all jurisdictions accessible to a user"""
        
        accessible = set()
        
        for user_jur in user_jurisdictions:
            # Add user's direct jurisdictions
            accessible.add(user_jur)
            
            # Add descendants (sub-jurisdictions)
            descendants = self.hierarchy_manager.get_descendants(user_jur)
            accessible.update(descendants)
            
            # Add ancestors (parent jurisdictions)
            ancestors = self.hierarchy_manager.get_ancestors(user_jur)
            accessible.update(ancestors)
        
        # Filter to only valid jurisdictions
        return [j for j in accessible if j in all_jurisdictions]
    
    async def validate_cross_jurisdiction_request(
        self,
        user_id: str,
        source_jurisdiction: str,
        target_jurisdiction: str
    ) -> bool:
        """Validate cross-jurisdiction request"""
        
        # Check if request already exists and is active
        for req in self._cross_jurisdiction_requests.values():
            if (req.user_id == user_id and
                req.source_jurisdiction == source_jurisdiction and
                req.target_jurisdiction == target_jurisdiction):
                
                # Check if request is still valid
                if req.expires_at and req.expires_at < datetime.now():
                    continue
                
                # Check if approved
                approval = await self._get_cross_jurisdiction_approval(req.request_id)
                if approval and approval.approved:
                    return True
        
        return False