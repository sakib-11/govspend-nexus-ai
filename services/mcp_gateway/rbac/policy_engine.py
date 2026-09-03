"""RBAC Policy Engine — evaluates roles, permissions, and jurisdiction access."""

from typing import List, Optional, Set

from ..models.auth import (
    DEFAULT_ROLE_PERMISSIONS,
    ROLE_HIERARCHY,
    Permission,
    User,
    UserRole,
    get_permissions_for_roles,
)
from ..utils.logging import get_logger

logger = get_logger(__name__)


class PolicyEngine:
    """Stateless policy evaluation engine for RBAC decisions.

    Design principles:
        • Super-admin bypasses every check.
        • Role hierarchy is implicit via ``DEFAULT_ROLE_PERMISSIONS`` — higher
          roles simply contain a superset of permissions.
        • Jurisdiction checks are opt-in per endpoint.
    """

    def __init__(self):
        # Pre-compute the full permission set for quick "is super_admin" tests
        self._all_permissions: frozenset[Permission] = frozenset(Permission)

    # ------------------------------------------------------------------
    # Permission checks
    # ------------------------------------------------------------------

    def check_permission(self, user: User, permission: Permission) -> bool:
        """True if *user* holds *permission*."""
        if user.is_super_admin():
            return True
        return user.has_permission(permission)

    def check_all_permissions(self, user: User, permissions: List[Permission]) -> bool:
        """True if *user* holds ALL listed permissions."""
        if user.is_super_admin():
            return True
        return all(user.has_permission(p) for p in permissions)

    def check_any_permission(self, user: User, permissions: List[Permission]) -> bool:
        """True if *user* holds at least one of the listed permissions."""
        if user.is_super_admin():
            return True
        return any(user.has_permission(p) for p in permissions)

    # ------------------------------------------------------------------
    # Role checks
    # ------------------------------------------------------------------

    def check_role(self, user: User, role: UserRole) -> bool:
        """True if *user* holds *role*."""
        if user.is_super_admin():
            return True
        return user.has_role(role)

    def check_any_role(self, user: User, roles: List[UserRole]) -> bool:
        """True if *user* holds at least one of the listed roles."""
        if user.is_super_admin():
            return True
        return user.has_any_role(roles)

    def check_role_level(self, user: User, min_level: int) -> bool:
        """True if the user's highest role meets or exceeds *min_level*."""
        if user.is_super_admin():
            return True
        return user.max_role_level() >= min_level

    # ------------------------------------------------------------------
    # Jurisdiction checks
    # ------------------------------------------------------------------

    def check_jurisdiction(self, user: User, jurisdictions: List[str]) -> bool:
        """True if *user* has access to ANY of the listed jurisdictions."""
        if user.is_super_admin():
            return True
        return any(j in user.jurisdictions for j in jurisdictions)

    def check_all_jurisdictions(self, user: User, jurisdictions: List[str]) -> bool:
        """True if *user* has access to ALL of the listed jurisdictions."""
        if user.is_super_admin():
            return True
        return all(j in user.jurisdictions for j in jurisdictions)

    # ------------------------------------------------------------------
    # Composite authorization helpers
    # ------------------------------------------------------------------

    def can_access_resource(
        self,
        user: User,
        resource_type: str,
        resource_jurisdiction: Optional[str] = None,
    ) -> bool:
        """True if *user* can view/access a resource of *resource_type*."""
        # Build the "view_" permission for this resource type
        perm_name = f"view_{resource_type}"
        try:
            perm = Permission(perm_name)
        except ValueError:
            perm = None

        # Also check a generic "access_" permission
        access_name = f"access_{resource_type}"
        try:
            access_perm = Permission(access_name)
        except ValueError:
            access_perm = None

        has_perm = False
        if perm and self.check_permission(user, perm):
            has_perm = True
        if access_perm and self.check_permission(user, access_perm):
            has_perm = True

        if not has_perm:
            return False

        if resource_jurisdiction:
            return self.check_jurisdiction(user, [resource_jurisdiction])
        return True

    def can_act_on_resource(
        self,
        user: User,
        action: str,
        resource_type: str,
        resource_jurisdiction: Optional[str] = None,
    ) -> bool:
        """True if *user* can perform *action* on *resource_type*."""
        perm_name = f"{action}_{resource_type}"
        try:
            perm = Permission(perm_name)
        except ValueError:
            return False

        if not self.check_permission(user, perm):
            return False

        if resource_jurisdiction:
            return self.check_jurisdiction(user, [resource_jurisdiction])
        return True

    def get_user_permissions(self, user: User) -> Set[Permission]:
        """Return the effective permission set for *user*."""
        if user.is_super_admin():
            return set(self._all_permissions)
        return user.effective_permissions()

    def get_effective_permissions(
        self, user: User, jurisdiction: Optional[str] = None
    ) -> Set[Permission]:
        """Permissions scoped to a specific jurisdiction."""
        if jurisdiction and not self.check_jurisdiction(user, [jurisdiction]):
            return set()
        return self.get_user_permissions(user)

    def is_authorized_for_operation(
        self,
        user: User,
        operation: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        jurisdiction: Optional[str] = None,
    ) -> bool:
        """Full authorization check for an arbitrary operation."""
        return self.can_act_on_resource(user, operation, resource_type, jurisdiction)
