"""Authorization engine for GovSpend Nexus AI."""

from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime
import asyncio
from models.authorization import (
    AuthorizationRequest, AuthorizationResponse, AuthorizationDecision,
    AuthorizationReason, PermissionTag, ToolTag, ResourceType, ActionType,
    AuthorizationAuditLog, AuthorizationPolicy
)
from models.auth import User, UserRole, Permission
from config import get_config


class AuthorizationEngine:
    """Core authorization engine"""
    
    def __init__(self, db_pool, redis_client, config=None):
        self.db_pool = db_pool
        self.redis = redis_client
        self.config = config or get_config()
        self._policy_cache = {}
        self._permission_cache = {}
    
    async def authorize(self, request: AuthorizationRequest) -> AuthorizationResponse:
        """
        Main authorization function
        
        Checks:
        1. Permission tags against user permissions
        2. Jurisdiction scope against requested data
        3. Role requirements
        4. Resource ownership (if applicable)
        5. MFA requirements
        6. Policy overrides
        """
        
        start_time = datetime.now()
        
        # Initialize response
        response = AuthorizationResponse(
            request_id=request.request_id,
            decision=AuthorizationDecision.DENY,
            reason=AuthorizationReason.PERMISSION_DENIED,
            message="Authorization failed",
            permission_checks=[],
            jurisdiction_checks=[],
            role_checks=[]
        )
        
        try:
            # 1. Check if user exists and is active
            user = await self._get_user(request.user_id)
            if not user or not user.is_active:
                response.reason = AuthorizationReason.PERMISSION_DENIED
                response.message = "User not found or inactive"
                await self._log_authorization(request, response)
                return response
            
            # 2. Check MFA if required
            if self._mfa_required(request, user):
                if not request.mfa_verified:
                    response.reason = AuthorizationReason.MFA_NOT_VERIFIED
                    response.message = "MFA verification required"
                    await self._log_authorization(request, response)
                    return response
            
            # 3. Check session validity
            if not await self._validate_session(request):
                response.reason = AuthorizationReason.SESSION_EXPIRED
                response.message = "Invalid or expired session"
                await self._log_authorization(request, response)
                return response
            
            # 4. Check permission tags
            permission_result = await self._check_permissions(request, user)
            response.permission_checks = permission_result.get("checks", [])
            
            if not permission_result.get("allowed", False):
                response.reason = AuthorizationReason.PERMISSION_DENIED
                response.message = permission_result.get("message", "Insufficient permissions")
                response.decision = AuthorizationDecision.DENY
                await self._log_authorization(request, response)
                return response
            
            # 5. Check jurisdiction scope
            jurisdiction_result = await self._check_jurisdiction(request, user)
            response.jurisdiction_checks = jurisdiction_result.get("checks", [])
            
            if not jurisdiction_result.get("allowed", False):
                response.reason = AuthorizationReason.JURISDICTION_DENIED
                response.message = jurisdiction_result.get("message", "Access denied for jurisdiction")
                response.decision = AuthorizationDecision.DENY
                await self._log_authorization(request, response)
                return response
            
            # 6. Check role requirements
            role_result = await self._check_roles(request, user)
            response.role_checks = role_result.get("checks", [])
            
            if not role_result.get("allowed", False):
                response.reason = AuthorizationReason.ROLE_REQUIRED
                response.message = role_result.get("message", "Required role not found")
                response.decision = AuthorizationDecision.DENY
                await self._log_authorization(request, response)
                return response
            
            # 7. Check resource ownership (if applicable)
            ownership_result = await self._check_ownership(request, user)
            if not ownership_result.get("allowed", False):
                response.reason = AuthorizationReason.RESOURCE_OWNER_DENIED
                response.message = ownership_result.get("message", "Not authorized to access this resource")
                response.decision = AuthorizationDecision.DENY
                await self._log_authorization(request, response)
                return response
            
            # 8. Check policy overrides
            override_result = await self._check_policy_overrides(request, user)
            if override_result.get("denied", False):
                response.reason = AuthorizationReason.POLICY_DENIED
                response.message = override_result.get("message", "Policy override denied")
                response.decision = AuthorizationDecision.DENY
                await self._log_authorization(request, response)
                return response
            
            # 9. Check rate limits
            if not await self._check_rate_limit(request):
                response.reason = AuthorizationReason.RATE_LIMIT_EXCEEDED
                response.message = "Rate limit exceeded"
                response.decision = AuthorizationDecision.DENY
                await self._log_authorization(request, response)
                return response
            
            # 10. Check for partial permissions
            if permission_result.get("partial", False):
                response.decision = AuthorizationDecision.PARTIAL
                response.reason = AuthorizationReason.PERMISSION_GRANTED
                response.message = "Partial access granted"
                response.partial_grants = permission_result.get("grants", {})
            else:
                response.decision = AuthorizationDecision.ALLOW
                response.reason = AuthorizationReason.PERMISSION_GRANTED
                response.message = "Access granted"
                response.allowed_actions = [f"{request.action.value}:{request.resource_type.value}"]
            
            # Calculate response time
            response.evaluated_at = datetime.now()
            response.response_time_ms = (response.evaluated_at - start_time).total_seconds() * 1000
            
            # Log successful authorization
            await self._log_authorization(request, response)
            
            return response
            
        except Exception as e:
            # Log error
            response.reason = AuthorizationReason.PERMISSION_DENIED
            response.message = f"Authorization error: {str(e)}"
            await self._log_authorization(request, response)
            return response
    
    async def _check_permissions(
        self, 
        request: AuthorizationRequest, 
        user: User
    ) -> Dict[str, Any]:
        """Check if user has required permissions"""
        
        checks = []
        allowed = True
        partial = False
        grants = {}
        
        # Get user permissions
        user_permissions = set(user.permissions)
        
        # Check each tool's required permissions
        for tool_tag in request.tool_tags:
            required_perms = tool_tag.required_permissions
            
            if not required_perms:
                # No permissions required, allow
                continue
            
            for required_perm in required_perms:
                # Check if user has this permission
                has_permission = self._check_single_permission(
                    required_perm, 
                    user_permissions,
                    user
                )
                
                check = {
                    "permission": required_perm.to_string(),
                    "has_permission": has_permission,
                    "tool_id": tool_tag.tool_id
                }
                checks.append(check)
                
                if not has_permission:
                    allowed = False
                    # Check if we should allow partial access
                    if self._can_grant_partial(required_perm, user):
                        partial = True
                        grants[required_perm.to_string()] = True
                    else:
                        grants[required_perm.to_string()] = False
                else:
                    grants[required_perm.to_string()] = True
        
        # Super admin always allowed
        if user.is_super_admin():
            allowed = True
            partial = False
        
        return {
            "allowed": allowed,
            "partial": partial,
            "grants": grants,
            "checks": checks,
            "message": "Permissions check passed" if allowed else "Insufficient permissions"
        }
    
    def _check_single_permission(
        self, 
        required: PermissionTag, 
        user_permissions: Set[Permission],
        user: User
    ) -> bool:
        """Check a single permission"""
        
        # Super admin always has all permissions
        if user.is_super_admin():
            return True
        
        # Check exact match
        required_str = required.to_string()
        for user_perm in user_permissions:
            if user_perm.value == required_str:
                return True
            # Check wildcard permissions (e.g., "transaction:*")
            if required.resource.value in user_perm.value and ":" in user_perm.value:
                parts = user_perm.value.split(":")
                if parts[0] == required.resource.value and parts[1] == "*":
                    return True
        
        return False
    
    async def _check_jurisdiction(
        self, 
        request: AuthorizationRequest, 
        user: User
    ) -> Dict[str, Any]:
        """Check jurisdiction scope"""
        
        checks = []
        allowed = True
        
        # Super admin has all jurisdictions
        if user.is_super_admin():
            return {"allowed": True, "checks": [], "message": "Super admin jurisdiction access"}
        
        # If no jurisdiction required, allow
        if not request.resource_jurisdiction:
            return {"allowed": True, "checks": [], "message": "No jurisdiction required"}
        
        # Check if user has access to requested jurisdiction
        has_jurisdiction = request.resource_jurisdiction in user.jurisdictions
        
        check = {
            "jurisdiction": request.resource_jurisdiction,
            "has_access": has_jurisdiction,
            "user_jurisdictions": user.jurisdictions
        }
        checks.append(check)
        
        if not has_jurisdiction:
            allowed = False
        
        # Check cross-jurisdiction access
        if not has_jurisdiction and Permission.CROSS_JURISDICTION_VIEW in user.permissions:
            # Allow cross-jurisdiction view for specific roles
            cross_jurisdiction_roles = [UserRole.SUPER_ADMIN, UserRole.ADMIN]
            if any(role in user.roles for role in cross_jurisdiction_roles):
                allowed = True
                check["cross_jurisdiction_allowed"] = True
        
        return {
            "allowed": allowed,
            "checks": checks,
            "message": "Jurisdiction check passed" if allowed else "Jurisdiction access denied"
        }
    
    async def _check_roles(
        self, 
        request: AuthorizationRequest, 
        user: User
    ) -> Dict[str, Any]:
        """Check role requirements"""
        
        checks = []
        allowed = True
        
        # Super admin always allowed
        if user.is_super_admin():
            return {"allowed": True, "checks": [], "message": "Super admin role access"}
        
        # Check tool-specific role requirements
        for tool_tag in request.tool_tags:
            required_roles = tool_tag.allowed_roles
            
            if not required_roles:
                continue
            
            has_role = any(role in user.roles for role in required_roles)
            
            check = {
                "tool_id": tool_tag.tool_id,
                "required_roles": required_roles,
                "user_roles": [r.value for r in user.roles],
                "has_role": has_role
            }
            checks.append(check)
            
            if not has_role:
                allowed = False
        
        # General role check for the action
        if request.resource_type and request.action:
            required_role = self._get_role_for_action(request.resource_type, request.action)
            if required_role:
                has_role = required_role in user.roles
                check = {
                    "action": f"{request.action.value}:{request.resource_type.value}",
                    "required_role": required_role.value,
                    "has_role": has_role
                }
                checks.append(check)
                if not has_role:
                    allowed = False
        
        return {
            "allowed": allowed,
            "checks": checks,
            "message": "Role check passed" if allowed else "Required role not found"
        }
    
    async def _check_ownership(
        self, 
        request: AuthorizationRequest, 
        user: User
    ) -> Dict[str, Any]:
        """Check resource ownership"""
        
        # If no resource ID or owner, skip
        if not request.resource_id or not request.resource_owner_id:
            return {"allowed": True, "checks": [], "message": "No ownership check required"}
        
        # Super admin always allowed
        if user.is_super_admin():
            return {"allowed": True, "checks": [], "message": "Super admin ownership bypass"}
        
        # Check if user is the owner
        is_owner = request.resource_owner_id == user.user_id
        
        if is_owner:
            return {"allowed": True, "checks": [], "message": "User is resource owner"}
        
        # Check if user has manage permission for this resource type
        manage_permission = f"{request.resource_type.value}:manage"
        if manage_permission in [p.value for p in user.permissions]:
            return {"allowed": True, "checks": [], "message": "User has manage permission"}
        
        return {
            "allowed": False,
            "checks": [{
                "resource_id": request.resource_id,
                "owner_id": request.resource_owner_id,
                "user_id": user.user_id,
                "is_owner": is_owner
            }],
            "message": "User is not resource owner"
        }
    
    async def _check_policy_overrides(
        self, 
        request: AuthorizationRequest, 
        user: User
    ) -> Dict[str, Any]:
        """Check policy overrides"""
        
        # Get active policies
        policies = await self._get_active_policies()
        
        denied = False
        override_messages = []
        
        for policy in policies:
            # Check deny overrides
            for deny_override in policy.deny_overrides:
                if self._matches_override(deny_override, request, user):
                    denied = True
                    override_messages.append(deny_override.get("reason", "Policy override denied"))
            
            # Check allow overrides (can override deny)
            if denied:
                for allow_override in policy.allow_overrides:
                    if self._matches_override(allow_override, request, user):
                        denied = False
                        override_messages.append(allow_override.get("reason", "Policy override allowed"))
        
        return {
            "denied": denied,
            "message": "; ".join(override_messages) if override_messages else "No policy overrides"
        }
    
    def _matches_override(
        self, 
        override: Dict[str, Any], 
        request: AuthorizationRequest, 
        user: User
    ) -> bool:
        """Check if request matches an override rule"""
        
        # Check user match
        user_match = override.get("users", [])
        if user_match and user.user_id not in user_match:
            return False
        
        # Check role match
        role_match = override.get("roles", [])
        if role_match and not any(r in user.roles for r in role_match):
            return False
        
        # Check resource match
        resource_match = override.get("resource_type")
        if resource_match and resource_match != request.resource_type.value:
            return False
        
        # Check action match
        action_match = override.get("action")
        if action_match and action_match != request.action.value:
            return False
        
        # Check jurisdiction match
        jurisdiction_match = override.get("jurisdictions", [])
        if jurisdiction_match and request.resource_jurisdiction not in jurisdiction_match:
            return False
        
        return True
    
    async def _check_rate_limit(self, request: AuthorizationRequest) -> bool:
        """Check rate limits"""
        
        if not self.config.RATE_LIMIT_ENABLED:
            return True
        
        key = f"rate_limit:{request.user_id}:{request.resource_type.value}:{request.action.value}"
        
        # Get current count
        count = await self.redis.get(key)
        if count and int(count) >= self.config.RATE_LIMIT_REQUESTS:
            return False
        
        # Increment count
        pipeline = self.redis.pipeline()
        pipeline.incr(key)
        pipeline.expire(key, self.config.RATE_LIMIT_PERIOD_SECONDS)
        await pipeline.execute()
        
        return True
    
    def _mfa_required(self, request: AuthorizationRequest, user: User) -> bool:
        """Check if MFA is required"""
        
        # MFA required for sensitive actions
        sensitive_actions = [
            (ResourceType.TRANSACTION, ActionType.DELETE),
            (ResourceType.CASE, ActionType.CLOSE),
            (ResourceType.EVIDENCE, ActionType.EXPORT),
            (ResourceType.USER, ActionType.MANAGE),
            (ResourceType.POLICY, ActionType.UPDATE),
        ]
        
        for resource, action in sensitive_actions:
            if request.resource_type == resource and request.action == action:
                return user.mfa_enabled
        
        return False
    
    def _get_role_for_action(self, resource: ResourceType, action: ActionType) -> Optional[UserRole]:
        """Get required role for action"""
        
        # Define role requirements for actions
        role_map = {
            (ResourceType.TRANSACTION, ActionType.VIEW): UserRole.AUDITOR_LEVEL_1,
            (ResourceType.TRANSACTION, ActionType.CREATE): UserRole.AUDITOR_LEVEL_2,
            (ResourceType.TRANSACTION, ActionType.UPDATE): UserRole.AUDITOR_LEVEL_2,
            (ResourceType.TRANSACTION, ActionType.DELETE): UserRole.ADMIN,
            (ResourceType.CASE, ActionType.VIEW): UserRole.AUDITOR_LEVEL_1,
            (ResourceType.CASE, ActionType.CREATE): UserRole.AUDITOR_LEVEL_2,
            (ResourceType.CASE, ActionType.UPDATE): UserRole.AUDITOR_LEVEL_2,
            (ResourceType.CASE, ActionType.CLOSE): UserRole.APPROVER,
            (ResourceType.EVIDENCE, ActionType.VIEW): UserRole.AUDITOR_LEVEL_1,
            (ResourceType.EVIDENCE, ActionType.EXPORT): UserRole.AUDITOR_LEVEL_3,
            (ResourceType.USER, ActionType.MANAGE): UserRole.ADMIN,
            (ResourceType.POLICY, ActionType.UPDATE): UserRole.ADMIN,
        }
        
        return role_map.get((resource, action))
    
    def _can_grant_partial(self, required: PermissionTag, user: User) -> bool:
        """Check if partial access can be granted"""
        
        # Users with manage permission can get partial access
        manage_perm = f"{required.resource.value}:manage"
        return manage_perm in [p.value for p in user.permissions]
    
    async def _get_user(self, user_id: str) -> Optional[User]:
        """Get user from database"""
        
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
            
            if not row:
                return None
            
            from models.auth import UserRole
            return User(
                user_id=row['user_id'],
                username=row['username'],
                email=row['email'],
                full_name=row['full_name'],
                roles=[UserRole(r) for r in row['roles']],
                jurisdictions=row['jurisdictions'],
                permissions=set(),  # Will be loaded from role_permissions
                mfa_enabled=row['mfa_enabled'],
                is_active=row['is_active']
            )
    
    async def _validate_session(self, request: AuthorizationRequest) -> bool:
        """Validate session"""
        
        if not request.session_id:
            return True  # No session required for some operations
        
        key = f"session:{request.session_id}"
        session = await self.redis.get(key)
        
        if not session:
            # Check database
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT is_active, expires_at FROM sessions WHERE session_id = $1",
                    request.session_id
                )
                
                if not row:
                    return False
                
                is_valid = row['is_active'] and row['expires_at'] > datetime.now()
                if is_valid:
                    # Cache session
                    await self.redis.setex(key, 60, "active")
                return is_valid
        
        return session == "active"
    
    async def _get_active_policies(self) -> List[AuthorizationPolicy]:
        """Get active authorization policies"""
        
        # Check cache
        cache_key = "auth_policies:active"
        cached = await self.redis.get(cache_key)
        
        if cached:
            import json
            policy_data = json.loads(cached)
            return [AuthorizationPolicy(**p) for p in policy_data]
        
        # Get from database
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM authorization_policies WHERE is_active = TRUE"
            )
            
            policies = []
            for row in rows:
                policy = AuthorizationPolicy(
                    policy_id=row['policy_id'],
                    name=row['name'],
                    description=row['description'],
                    version=row['version'],
                    permission_rules=row['permission_rules'] or [],
                    jurisdiction_rules=row['jurisdiction_rules'] or [],
                    role_rules=row['role_rules'] or [],
                    allow_overrides=row['allow_overrides'] or [],
                    deny_overrides=row['deny_overrides'] or [],
                    is_active=row['is_active'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                    created_by=row['created_by']
                )
                policies.append(policy)
            
            # Cache policies
            import json
            await self.redis.setex(
                cache_key,
                300,  # 5 minutes
                json.dumps([p.model_dump() for p in policies], default=str)
            )
            
            return policies
    
    async def _log_authorization(
        self, 
        request: AuthorizationRequest, 
        response: AuthorizationResponse
    ):
        """Log authorization decision"""
        
        # Check if we should log
        if not self.config.AUDIT_ENABLED:
            return
        
        # Create audit log
        audit_log = AuthorizationAuditLog(
            request_id=request.request_id,
            user_id=request.user_id,
            decision=response.decision,
            reason=response.reason,
            resource_type=request.resource_type,
            action=request.action,
            resource_id=request.resource_id,
            resource_jurisdiction=request.resource_jurisdiction,
            user_roles=[r.value for r in request.user_roles] if request.user_roles else [],
            user_permissions=request.user_permissions,
            user_jurisdictions=request.user_jurisdictions,
            permission_checks_passed=sum(
                1 for c in response.permission_checks if c.get("has_permission", False)
            ),
            permission_checks_failed=sum(
                1 for c in response.permission_checks if not c.get("has_permission", False)
            ),
            jurisdiction_checks_passed=sum(
                1 for c in response.jurisdiction_checks if c.get("has_access", False)
            ),
            jurisdiction_checks_failed=sum(
                1 for c in response.jurisdiction_checks if not c.get("has_access", False)
            ),
            ip_address=request.ip_address,
            session_id=request.session_id,
            allowed=response.decision == AuthorizationDecision.ALLOW,
            message=response.message,
            details={
                "permission_checks": response.permission_checks,
                "jurisdiction_checks": response.jurisdiction_checks,
                "role_checks": response.role_checks,
                "response_time_ms": response.response_time_ms
            },
            response_time_ms=response.response_time_ms
        )
        
        # Store in database
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO authorization_audit_logs (
                    audit_id, request_id, user_id, decision, reason,
                    resource_type, action, resource_id, resource_jurisdiction,
                    user_roles, user_permissions, user_jurisdictions,
                    permission_checks_passed, permission_checks_failed,
                    jurisdiction_checks_passed, jurisdiction_checks_failed,
                    ip_address, session_id, allowed, message, details,
                    timestamp, response_time_ms
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12,
                    $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23
                )
            """,
                audit_log.audit_id,
                audit_log.request_id,
                audit_log.user_id,
                audit_log.decision.value,
                audit_log.reason.value,
                audit_log.resource_type.value,
                audit_log.action.value,
                audit_log.resource_id,
                audit_log.resource_jurisdiction,
                audit_log.user_roles,
                audit_log.user_permissions,
                audit_log.user_jurisdictions,
                audit_log.permission_checks_passed,
                audit_log.permission_checks_failed,
                audit_log.jurisdiction_checks_passed,
                audit_log.jurisdiction_checks_failed,
                audit_log.ip_address,
                audit_log.session_id,
                audit_log.allowed,
                audit_log.message,
                audit_log.details,
                audit_log.timestamp,
                audit_log.response_time_ms
            )
        
        # Also log to Redis for real-time monitoring
        await self.redis.xadd(
            "auth.audit",
            {
                "event": "authorization",
                "user_id": request.user_id,
                "decision": response.decision.value,
                "resource": f"{request.resource_type.value}:{request.action.value}",
                "timestamp": datetime.now().isoformat()
            },
            maxlen=10000
        )