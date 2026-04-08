"""RBAC role catalogue.

Roles are kept as a fixed enum for Task 5. They are referenced by name
from `users.role` and from the `require_role` dependency.

Hierarchy (highest to lowest):
    admin > manager > operator > viewer

`role_rank()` lets dependencies enforce "at least manager" semantics
without writing per-endpoint role lists.
"""
from typing import Final, Tuple

ROLE_ADMIN: Final[str] = "admin"
ROLE_MANAGER: Final[str] = "manager"
ROLE_OPERATOR: Final[str] = "operator"
ROLE_VIEWER: Final[str] = "viewer"

ROLES: Final[Tuple[str, ...]] = (
    ROLE_ADMIN,
    ROLE_MANAGER,
    ROLE_OPERATOR,
    ROLE_VIEWER,
)

_RANK = {
    ROLE_ADMIN: 40,
    ROLE_MANAGER: 30,
    ROLE_OPERATOR: 20,
    ROLE_VIEWER: 10,
}


def role_rank(role: str) -> int:
    """Return the numeric rank of a role; unknown roles → 0."""
    return _RANK.get(role, 0)
