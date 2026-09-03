"""State machine service — orchestrates state transitions with validation."""

from __future__ import annotations

import logging
from typing import List, Optional

from models.state_machine import allowed_actions, can_transition, get_next_status
from models.unmask import UnmaskAction, UnmaskRequest, UnmaskStatus

logger = logging.getLogger(__name__)


class StateMachineService:
    """Validate and execute state transitions for unmask requests."""

    def validate_transition(
        self,
        current_status: UnmaskStatus,
        action: UnmaskAction,
        user_roles: List[str],
        *,
        mfa_verified: bool = False,
        requested_by: Optional[str] = None,
        user_id: Optional[str] = None,
        self_approval_disallowed: bool = True,
    ) -> tuple[bool, Optional[str]]:
        """Validate whether a transition is allowed.

        Returns ``(is_valid, error_message)``.
        """
        # Self-approval check
        if (
            action == UnmaskAction.APPROVE
            and self_approval_disallowed
            and requested_by
            and user_id
            and requested_by == user_id
        ):
            return False, "Self-approval is not allowed"

        # Self-rejection check (same rule)
        if (
            action == UnmaskAction.REJECT
            and self_approval_disallowed
            and requested_by
            and user_id
            and requested_by == user_id
        ):
            return False, "Self-rejection is not allowed"

        # Terminal state check
        if current_status in (
            UnmaskStatus.REJECTED,
            UnmaskStatus.EXPIRED,
            UnmaskStatus.CANCELLED,
        ):
            return False, f"Request is in terminal state: {current_status.value}"

        # State machine check
        if not can_transition(
            current_status, action, user_roles, mfa_verified=mfa_verified,
        ):
            return False, (
                f"Cannot {action.value} from {current_status.value} "
                f"with roles {user_roles}"
            )

        return True, None

    def get_next_status(
        self, current_status: UnmaskStatus, action: UnmaskAction,
    ) -> Optional[UnmaskStatus]:
        """Return the resulting status after a valid transition."""
        return get_next_status(current_status, action)

    def get_allowed_actions(
        self, current_status: UnmaskStatus, user_roles: List[str], *,
        mfa_verified: bool = False,
    ) -> List[UnmaskAction]:
        """Return the list of actions a user can take from *current_status*."""
        return allowed_actions(current_status, user_roles, mfa_verified=mfa_verified)

    def can_view_data(
        self,
        request: UnmaskRequest,
        user_id: str,
        user_roles: List[str],
    ) -> tuple[bool, Optional[str]]:
        """Check whether a user is allowed to view unmasked data."""
        if request.status != UnmaskStatus.UNMASKED:
            return False, "Data is not unmasked yet"

        # Requester or approver can view
        if request.requested_by == user_id or request.approved_by == user_id:
            return True, None

        # Admin can always view
        if "admin" in user_roles or "super_admin" in user_roles:
            return True, None

        return False, "Not authorized to view this data"
