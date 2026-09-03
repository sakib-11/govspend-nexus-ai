"""State machine model — defines valid transitions for unmask requests."""

from __future__ import annotations

from typing import Dict, FrozenSet, Set, Tuple

from models.unmask import UnmaskAction, UnmaskStatus


# ======================================================================
# Transition table: (current_status, action) -> set of allowed next states
# Each entry also carries a set of required role prefixes.
# ======================================================================

_TRANSITIONS: Dict[
    Tuple[UnmaskStatus, UnmaskAction],
    Tuple[UnmaskStatus, FrozenSet[str]],
] = {
    # Create
    (UnmaskStatus.PENDING, UnmaskAction.CREATE): (
        UnmaskStatus.PENDING,
        frozenset({"auditor_level_1", "auditor_level_2", "auditor_level_3"}),
    ),
    # Approve
    (UnmaskStatus.PENDING, UnmaskAction.APPROVE): (
        UnmaskStatus.APPROVED,
        frozenset({"auditor_level_2", "auditor_level_3", "admin", "super_admin"}),
    ),
    # Reject
    (UnmaskStatus.PENDING, UnmaskAction.REJECT): (
        UnmaskStatus.REJECTED,
        frozenset({"auditor_level_2", "auditor_level_3", "admin", "super_admin"}),
    ),
    # Unmask (retrieve data from ledger)
    (UnmaskStatus.APPROVED, UnmaskAction.UNMASK): (
        UnmaskStatus.UNMASKED,
        frozenset({"auditor_level_2", "auditor_level_3", "admin", "super_admin"}),
    ),
    # View unmasked data
    (UnmaskStatus.UNMASKED, UnmaskAction.VIEW): (
        UnmaskStatus.VIEWED,
        frozenset({"auditor_level_1", "auditor_level_2", "auditor_level_3", "admin"}),
    ),
    # Expire (system action)
    (UnmaskStatus.PENDING, UnmaskAction.EXPIRE): (
        UnmaskStatus.EXPIRED,
        frozenset({"system"}),
    ),
    (UnmaskStatus.APPROVED, UnmaskAction.EXPIRE): (
        UnmaskStatus.EXPIRED,
        frozenset({"system"}),
    ),
    (UnmaskStatus.UNMASKED, UnmaskAction.EXPIRE): (
        UnmaskStatus.EXPIRED,
        frozenset({"system"}),
    ),
    # Cancel (by requester)
    (UnmaskStatus.PENDING, UnmaskAction.CANCEL): (
        UnmaskStatus.CANCELLED,
        frozenset({"auditor_level_1", "auditor_level_2", "auditor_level_3"}),
    ),
}


def can_transition(
    current: UnmaskStatus,
    action: UnmaskAction,
    user_roles: list[str],
    *,
    mfa_verified: bool = False,
) -> bool:
    """Return True if *action* is allowed from *current* for *user_roles*.

    For APPROVE and UNMASK actions, *mfa_verified* must be ``True``.
    """
    key = (current, action)
    if key not in _TRANSITIONS:
        return False

    _, allowed_roles = _TRANSITIONS[key]

    # MFA gate for sensitive actions
    if action in (UnmaskAction.APPROVE, UnmaskAction.UNMASK) and not mfa_verified:
        return False

    # system user can always expire
    if "system" in user_roles:
        return True

    return bool(frozenset(user_roles) & allowed_roles)


def get_next_status(
    current: UnmaskStatus, action: UnmaskAction,
) -> UnmaskStatus | None:
    """Return the status after a valid transition, or ``None``."""
    key = (current, action)
    if key not in _TRANSITIONS:
        return None
    return _TRANSITIONS[key][0]


def allowed_actions(
    current: UnmaskStatus, user_roles: list[str], *, mfa_verified: bool = False,
) -> list[UnmaskAction]:
    """Return the list of actions a user can take from *current* status."""
    results: list[UnmaskAction] = []
    for (status, action), _ in _TRANSITIONS.items():
        if status == current:
            if can_transition(current, action, user_roles, mfa_verified=mfa_verified):
                results.append(action)
    return results
