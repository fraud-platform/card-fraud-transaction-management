"""
FastAPI dependency injection utilities.

Provides reusable dependencies for database sessions, authentication,
and other cross-cutting concerns.
"""

from typing import Annotated

from fastapi import Depends

from app.core.auth import (
    FRAUD_ANALYST,
    FRAUD_SUPERVISOR,
    PLATFORM_ADMIN,
    TXN_APPROVE,
    TXN_BLOCK,
    TXN_COMMENT,
    TXN_FLAG,
    TXN_OVERRIDE,
    TXN_RECOMMEND,
    TXN_VIEW,
    AuthenticatedUser,
    get_current_user,
    require_permission,
    require_role,
    require_roles,
)


def get_current_user_dep(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    """
    Re-export of get_current_user from security module.

    Extracts and verifies the current user from the JWT token.
    Use this dependency for endpoints that require authentication
    but no specific role.

    Usage:
        @router.get("/profile")
        def get_profile(user: CurrentUser):
            return {"user_id": user.user_id}

    Returns:
        AuthenticatedUser object with user information and helper methods
    """
    return user


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user_dep)]


# =============================================================================
# Role-based Dependencies (New Auth0 Roles)
# =============================================================================


def require_fraud_analyst(
    user: AuthenticatedUser = Depends(require_roles(FRAUD_ANALYST, PLATFORM_ADMIN)),
) -> AuthenticatedUser:
    """
    Dependency that enforces fraud analyst role requirement.

    Use this for endpoints that should only be accessible to fraud analysts
    or platform admins.

    Returns:
        AuthenticatedUser if user has required role

    Raises:
        ForbiddenError: If user lacks required role
    """
    return user


def require_fraud_supervisor(
    user: AuthenticatedUser = Depends(require_roles(FRAUD_SUPERVISOR, PLATFORM_ADMIN)),
) -> AuthenticatedUser:
    """
    Dependency that enforces fraud supervisor role requirement.

    Use this for endpoints that require final decision authority
    (approve, block, override).

    Returns:
        AuthenticatedUser if user has required role

    Raises:
        ForbiddenError: If user lacks required role
    """
    return user


def require_platform_admin(
    user: AuthenticatedUser = Depends(require_role(PLATFORM_ADMIN)),
) -> AuthenticatedUser:
    """
    Dependency that enforces platform admin role requirement.

    Use this for endpoints that should only be accessible to platform admins.

    Returns:
        AuthenticatedUser if user has platform admin role

    Raises:
        ForbiddenError: If user lacks platform admin role
    """
    return user


# =============================================================================
# Permission-based Dependencies
# =============================================================================


def require_txn_view(
    user: AuthenticatedUser = Depends(require_permission(TXN_VIEW)),
) -> AuthenticatedUser:
    """Require txn:view permission to view transactions."""
    return user


def require_txn_comment(
    user: AuthenticatedUser = Depends(require_permission(TXN_COMMENT)),
) -> AuthenticatedUser:
    """Require txn:comment permission to add comments."""
    return user


def require_txn_flag(
    user: AuthenticatedUser = Depends(require_permission(TXN_FLAG)),
) -> AuthenticatedUser:
    """Require txn:flag permission to flag transactions."""
    return user


def require_txn_recommend(
    user: AuthenticatedUser = Depends(require_permission(TXN_RECOMMEND)),
) -> AuthenticatedUser:
    """Require txn:recommend permission to make recommendations."""
    return user


def require_txn_approve(
    user: AuthenticatedUser = Depends(require_permission(TXN_APPROVE)),
) -> AuthenticatedUser:
    """Require txn:approve permission to approve transactions."""
    return user


def require_txn_block(
    user: AuthenticatedUser = Depends(require_permission(TXN_BLOCK)),
) -> AuthenticatedUser:
    """Require txn:block permission to block transactions."""
    return user


def require_txn_override(
    user: AuthenticatedUser = Depends(require_permission(TXN_OVERRIDE)),
) -> AuthenticatedUser:
    """Require txn:override permission to override prior decisions."""
    return user


# =============================================================================
# Typed Annotated Dependencies
# =============================================================================

RequireFraudAnalyst = Annotated[AuthenticatedUser, Depends(require_fraud_analyst)]
RequireFraudSupervisor = Annotated[AuthenticatedUser, Depends(require_fraud_supervisor)]
RequirePlatformAdmin = Annotated[AuthenticatedUser, Depends(require_platform_admin)]

RequireTxnView = Annotated[AuthenticatedUser, Depends(require_txn_view)]
RequireTxnComment = Annotated[AuthenticatedUser, Depends(require_txn_comment)]
RequireTxnFlag = Annotated[AuthenticatedUser, Depends(require_txn_flag)]
RequireTxnRecommend = Annotated[AuthenticatedUser, Depends(require_txn_recommend)]
RequireTxnApprove = Annotated[AuthenticatedUser, Depends(require_txn_approve)]
RequireTxnBlock = Annotated[AuthenticatedUser, Depends(require_txn_block)]
RequireTxnOverride = Annotated[AuthenticatedUser, Depends(require_txn_override)]


# =============================================================================
# Legacy Dependencies (backward compatibility)
# =============================================================================


def require_analyst(
    user: AuthenticatedUser = Depends(require_roles(FRAUD_ANALYST, PLATFORM_ADMIN)),
) -> AuthenticatedUser:
    """
    Legacy dependency for analyst role (use require_fraud_analyst instead).

    Returns:
        AuthenticatedUser if user has analyst role

    Raises:
        ForbiddenError: If user lacks analyst role
    """
    return user


def require_admin(  # noqa: E501
    user: AuthenticatedUser = Depends(require_role(PLATFORM_ADMIN)),
) -> AuthenticatedUser:
    """
    Legacy dependency for admin role (use require_platform_admin instead).

    Returns:
        AuthenticatedUser if user has admin role

    Raises:
        ForbiddenError: If user lacks admin role
    """
    return user


RequireAnalyst = Annotated[AuthenticatedUser, Depends(require_analyst)]
RequireAdmin = Annotated[AuthenticatedUser, Depends(require_admin)]
