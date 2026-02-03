"""
Auth0 JWT token verification and authentication utilities.

This module handles JWT verification using Auth0's JWKS endpoint,
extracts user information and roles, and provides FastAPI dependencies
for authentication and authorization.
"""

import asyncio
import inspect
import logging
import threading
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import httpx
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.errors import ForbiddenError, UnauthorizedError

logger = logging.getLogger(__name__)

# Sync HTTP client - used by sync methods (tests only)
_http = httpx.Client(timeout=httpx.Timeout(10.0))

# =============================================================================
# Role Constants (this project's roles - see AUTH_MODEL.md)
# =============================================================================

PLATFORM_ADMIN = "PLATFORM_ADMIN"  # Full access across all projects
FRAUD_ANALYST = "FRAUD_ANALYST"  # Analyze, comment, recommend
FRAUD_SUPERVISOR = "FRAUD_SUPERVISOR"  # Final decision authority

# =============================================================================
# Permission Constants (this project's permissions)
# =============================================================================

TXN_VIEW = "txn:view"  # View transactions
TXN_COMMENT = "txn:comment"  # Add analyst comments
TXN_FLAG = "txn:flag"  # Flag suspicious activity
TXN_RECOMMEND = "txn:recommend"  # Recommend action
TXN_APPROVE = "txn:approve"  # Approve transaction
TXN_BLOCK = "txn:block"  # Block transaction
TXN_OVERRIDE = "txn:override"  # Override prior decision

INVALID_OR_EXPIRED_TOKEN_MSG = "Invalid or expired token"

_async_http: httpx.AsyncClient | None = None
_http = httpx.Client(timeout=httpx.Timeout(10.0))

# Security scheme for authenticated endpoints
security = HTTPBearer()

# Optional security scheme for bypass mode (Authorization header is optional)
_optional_security = HTTPBearer(auto_error=False)


class TokenPayload(BaseModel):
    """JWT token payload."""

    sub: str
    email: str | None = None
    name: str | None = None
    roles: list[str] = []
    exp: int


class AuthenticatedUser(BaseModel):
    """Authenticated user information."""

    user_id: str
    email: str | None = None
    name: str | None = None
    roles: list[str] = []
    permissions: list[str] = []

    @property
    def is_platform_admin(self) -> bool:
        """Check if user has platform admin role."""
        return PLATFORM_ADMIN in self.roles

    @property
    def is_fraud_analyst(self) -> bool:
        """Check if user has fraud analyst role."""
        return FRAUD_ANALYST in self.roles or self.is_platform_admin

    @property
    def is_fraud_supervisor(self) -> bool:
        """Check if user has fraud supervisor role."""
        return FRAUD_SUPERVISOR in self.roles or self.is_platform_admin

    # Legacy properties for backward compatibility
    @property
    def is_analyst(self) -> bool:
        """Check if user has analyst role (legacy, use is_fraud_analyst)."""
        return self.is_fraud_analyst

    @property
    def is_admin(self) -> bool:
        """Check if user has admin role (legacy, use is_platform_admin)."""
        return self.is_platform_admin

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        return permission in self.permissions or self.is_platform_admin

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role."""
        return role in self.roles


class CircuitBreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(RuntimeError):
    pass


class CircuitBreaker:
    """Async circuit breaker for resilient external calls.

    Only async operations are used in the application.
    Sync methods exist for test compatibility.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        expected_exception: type[Exception] = Exception,
    ):
        self._failure_threshold = failure_threshold
        self._timeout_seconds = timeout_seconds
        self._expected_exception = expected_exception
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time: datetime | None = None
        self._last_state_change: datetime | None = None
        self._lock = threading.RLock()
        self._async_lock = asyncio.Lock()

    def _should_attempt_reset(self) -> bool:
        if self._last_failure_time is None:
            return True
        elapsed = (datetime.now(UTC) - self._last_failure_time).total_seconds()
        return elapsed >= self._timeout_seconds

    def _record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = datetime.now(UTC)
        if self._failure_count >= self._failure_threshold:
            self._state = CircuitBreakerState.OPEN
            self._last_state_change = datetime.now(UTC)
            logger.error(
                f"Circuit breaker OPEN after {self._failure_count} consecutive failures. "
                f"Will allow retry after {self._timeout_seconds} seconds."
            )
        else:
            logger.warning(
                f"Circuit breaker failure count: {self._failure_count}/{self._failure_threshold}"
            )

    def _record_success(self) -> None:
        if self._state == CircuitBreakerState.HALF_OPEN:
            self._state = CircuitBreakerState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None
            self._last_state_change = datetime.now(UTC)
            logger.info("Circuit breaker CLOSED - service has recovered")
        elif self._state == CircuitBreakerState.CLOSED:
            self._failure_count = 0

    def call(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute a sync callable with circuit breaker protection (test compatibility)."""
        with self._lock:
            if self._state == CircuitBreakerState.OPEN and self._should_attempt_reset():
                self._state = CircuitBreakerState.HALF_OPEN
                self._last_state_change = datetime.now(UTC)
                logger.info("Circuit breaker HALF_OPEN - attempting recovery")

            if self._state == CircuitBreakerState.OPEN:
                retry_after = (
                    self._timeout_seconds
                    - (datetime.now(UTC) - self._last_failure_time).total_seconds()
                )
                logger.warning(
                    f"Circuit breaker is OPEN - failing fast. Retry after {retry_after:.1f} seconds"
                )
                raise CircuitBreakerOpenError("Circuit breaker is OPEN - service unavailable")

        try:
            result = func(*args, **kwargs)
            with self._lock:
                self._record_success()
            return result
        except self._expected_exception:
            with self._lock:
                self._record_failure()
            raise

    async def call_async(self, coro_or_func: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute an async callable with circuit breaker protection."""
        async with self._async_lock:
            if self._state == CircuitBreakerState.OPEN and self._should_attempt_reset():
                self._state = CircuitBreakerState.HALF_OPEN
                self._last_state_change = datetime.now(UTC)
                logger.info("Circuit breaker HALF_OPEN - attempting recovery")

            if self._state == CircuitBreakerState.OPEN:
                retry_after = (
                    self._timeout_seconds
                    - (datetime.now(UTC) - self._last_failure_time).total_seconds()
                )
                logger.warning(
                    f"Circuit breaker is OPEN - failing fast. Retry after {retry_after:.1f} seconds"
                )
                raise CircuitBreakerOpenError("Circuit breaker is OPEN - service unavailable")

        if callable(coro_or_func):
            awaitable = coro_or_func(*args, **kwargs)
        else:
            if args or kwargs:
                raise TypeError(
                    "call_async() received positional/keyword args but "
                    "the first argument is not callable"
                )
            awaitable = coro_or_func

        if not inspect.isawaitable(awaitable):
            raise TypeError(
                "call_async() expects an awaitable or a callable returning an awaitable"
            )

        try:
            result = await awaitable
            async with self._async_lock:
                self._record_success()
            return result
        except self._expected_exception:
            async with self._async_lock:
                self._record_failure()
            raise

    @property
    def state(self) -> CircuitBreakerState:
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    @property
    def is_open(self) -> bool:
        return self._state == CircuitBreakerState.OPEN

    def reset(self) -> None:
        """Reset circuit breaker to CLOSED state (thread-safe)."""
        with self._lock:
            self._state = CircuitBreakerState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None
            self._last_state_change = None
            logger.debug("Circuit breaker reset to CLOSED state")


def get_async_http_client() -> httpx.AsyncClient:
    global _async_http
    if _async_http is None or _async_http.is_closed:
        _async_http = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
    return _async_http


async def close_async_http_client() -> None:
    global _async_http
    if _async_http is not None:
        try:
            if not _async_http.is_closed:
                await _async_http.aclose()
        except RuntimeError:
            # Event loop is already closed or in an invalid state
            pass
        finally:
            _async_http = None


class JWKSCache:
    def __init__(self, ttl_seconds: int = 3600):
        self._cache: dict[str, Any] | None = None
        self._cache_time: datetime | None = None
        self._ttl_seconds = ttl_seconds
        self._lock = threading.RLock()
        self._async_lock = asyncio.Lock()
        self._circuit_breaker = CircuitBreaker()

    def _is_cache_valid(self, now: datetime) -> bool:
        return (
            self._cache is not None
            and self._cache_time is not None
            and (now - self._cache_time).total_seconds() < self._ttl_seconds
        )

    def _use_stale_cache_if_available(self, reason: str) -> dict[str, Any] | None:
        if self._cache is not None:
            logger.warning(f"Using stale JWKS cache as fallback ({reason})")
            return self._cache
        return None

    def _handle_fetch_error(self, error: Exception) -> dict[str, Any] | None:
        if "Circuit breaker is OPEN" in str(error):
            logger.error("Circuit breaker prevented JWKS fetch")
            stale = self._use_stale_cache_if_available("circuit open")
            if stale:
                return stale
            raise UnauthorizedError(
                "Unable to verify token: authentication service unavailable (circuit open)"
            )

        logger.error(f"Failed to fetch JWKS: {error}")
        logger.info(
            f"Circuit breaker state: {self._circuit_breaker.state.value}, "
            f"failures: {self._circuit_breaker.failure_count}"
        )

        stale = self._use_stale_cache_if_available("fetch failed")
        if stale:
            return stale

        raise UnauthorizedError("Unable to verify token: authentication service unavailable")

    def _check_circuit_breaker(self, now: datetime) -> dict[str, Any] | None:
        if self._circuit_breaker.is_open and self._cache is not None:
            logger.warning(
                f"Circuit breaker is OPEN - using stale JWKS cache. "
                f"State: {self._circuit_breaker.state.value}, "
                f"Failures: {self._circuit_breaker.failure_count}"
            )
            return self._cache
        return None

    def _log_cache_refreshed(self) -> None:
        logger.info(
            f"JWKS cache refreshed successfully. Circuit state: {self._circuit_breaker.state.value}"
        )

    def _log_fetch_attempt(self, jwks_url: str) -> None:
        logger.info(f"Fetching JWKS from {jwks_url}")

    async def get_jwks_async(self) -> dict[str, Any]:
        settings = get_settings()
        now = datetime.now(UTC)
        jwks_url = settings.auth0.jwks_url

        async with self._async_lock:
            if self._is_cache_valid(now):
                logger.debug("Using cached JWKS")
                return self._cache

            cached = self._check_circuit_breaker(now)
            if cached:
                return cached

            try:
                self._log_fetch_attempt(jwks_url)
                client = get_async_http_client()

                async def _fetch():
                    response = await client.get(jwks_url)
                    response.raise_for_status()
                    return response.json()

                self._cache = await self._circuit_breaker.call_async(_fetch())
                self._cache_time = now
                self._log_cache_refreshed()
                return self._cache

            except Exception as e:
                cached = self._handle_fetch_error(e)
                if cached:
                    return cached
                raise

    def get_jwks(self) -> dict[str, Any]:
        settings = get_settings()
        now = datetime.now(UTC)
        jwks_url = settings.auth0.jwks_url

        with self._lock:
            if self._is_cache_valid(now):
                logger.debug("Using cached JWKS")
                return self._cache

            cached = self._check_circuit_breaker(now)
            if cached:
                return cached

            try:
                self._log_fetch_attempt(jwks_url)

                def _fetch():
                    response = _http.get(jwks_url)
                    response.raise_for_status()
                    return response.json()

                self._cache = self._circuit_breaker.call(_fetch)
                self._cache_time = now
                self._log_cache_refreshed()
                return self._cache

            except Exception as e:
                cached = self._handle_fetch_error(e)
                if cached:
                    return cached
                raise

    def clear(self) -> None:
        with self._lock:
            self._cache = None
            self._cache_time = None
            self._circuit_breaker.reset()
        logger.debug("JWKS cache and circuit breaker cleared")


_jwks_cache = JWKSCache()


def get_jwks() -> dict[str, Any]:
    return _jwks_cache.get_jwks()


async def get_jwks_async() -> dict[str, Any]:
    return await _jwks_cache.get_jwks_async()


def _find_rsa_key(jwks: dict[str, Any], token: str) -> dict[str, Any]:
    """Extract RSA key from JWKS using token's key ID.

    Shared implementation for both sync and async code paths.
    """
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as e:
        logger.warning(f"Invalid JWT header: {e}")
        raise UnauthorizedError(INVALID_OR_EXPIRED_TOKEN_MSG) from None

    for key in jwks.get("keys", []):
        if key["kid"] == unverified_header["kid"]:
            return {
                "kty": key["kty"],
                "kid": key["kid"],
                "use": key["use"],
                "n": key["n"],
                "e": key["e"],
            }

    logger.error(f"Unable to find matching key for kid: {unverified_header.get('kid')}")
    raise UnauthorizedError(INVALID_OR_EXPIRED_TOKEN_MSG) from None


def get_rsa_key(token: str) -> dict[str, Any]:
    return _find_rsa_key(get_jwks(), token)


def _verify_token_with_key(token: str, rsa_key: dict[str, Any]) -> dict[str, Any]:
    """Verify JWT token with provided RSA key.

    Shared implementation for both sync and async code paths.
    """
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=settings.auth0.algorithms_list,
            audience=settings.auth0.audience,
            issuer=settings.auth0.issuer_url,
        )
        logger.debug(f"Token verified successfully for subject: {payload.get('sub')}")
        return payload

    except jwt.ExpiredSignatureError:
        logger.warning("Token has expired")
        raise UnauthorizedError(INVALID_OR_EXPIRED_TOKEN_MSG) from None

    except jwt.JWTClaimsError as e:
        logger.warning(f"Invalid token claims: {e}")
        raise UnauthorizedError(INVALID_OR_EXPIRED_TOKEN_MSG) from None

    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        raise UnauthorizedError(INVALID_OR_EXPIRED_TOKEN_MSG) from None

    except Exception as e:
        logger.error(f"Unexpected error during token verification: {e}")
        raise UnauthorizedError(INVALID_OR_EXPIRED_TOKEN_MSG) from None


def verify_token(token: str) -> dict[str, Any]:
    return _verify_token_with_key(token, get_rsa_key(token))


async def get_rsa_key_async(token: str) -> dict[str, Any]:
    return _find_rsa_key(await get_jwks_async(), token)


async def verify_token_async(token: str) -> dict[str, Any]:
    return _verify_token_with_key(token, await get_rsa_key_async(token))


def _create_bypass_user() -> AuthenticatedUser:
    """
    Create a mock user for local development when JWT validation is bypassed.

    Returns a user with PLATFORM_ADMIN role to allow all operations for local testing.
    This is ONLY used when SECURITY_SKIP_JWT_VALIDATION=True and APP_ENV=local.
    """
    return AuthenticatedUser(
        user_id="local-dev-user",
        email="local-dev@example.com",
        name="Local Development User",
        roles=[PLATFORM_ADMIN],
        permissions=[
            TXN_VIEW,
            TXN_COMMENT,
            TXN_FLAG,
            TXN_RECOMMEND,
            TXN_APPROVE,
            TXN_BLOCK,
            TXN_OVERRIDE,
        ],
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_security),
) -> AuthenticatedUser:
    """Extract and verify JWT token, returning AuthenticatedUser object.

    When JWT validation is bypassed (via SECURITY_SKIP_JWT_VALIDATION=true),
    returns a mock user with PLATFORM_ADMIN role.

    The returned object provides:
    - user_id, email, name fields
    - roles and permissions lists
    - Helper properties: is_platform_admin, is_fraud_analyst, is_fraud_supervisor
    - Helper methods: has_permission(), has_role()
    """
    settings = get_settings()

    # Local development bypass - ONLY allowed in development environment
    # Validation is enforced in config.py to prevent production use
    if settings.security.skip_jwt_validation is True:
        logger.info(
            "JWT validation bypassed - returning mock admin user for local development"
        )
        return _create_bypass_user()

    # Normal JWT validation flow
    if credentials is None:
        logger.warning("Missing Authorization header")
        raise UnauthorizedError("Missing authorization header")

    token = credentials.credentials
    payload = await verify_token_async(token)

    return AuthenticatedUser(
        user_id=payload.get("sub", ""),
        email=payload.get("email"),
        name=payload.get("name"),
        roles=get_user_roles(payload),
        permissions=get_user_permissions(payload),
    )


def get_user_sub(payload: dict[str, Any]) -> str:
    sub = payload.get("sub")
    if not sub:
        logger.error("JWT payload missing 'sub' claim")
        raise UnauthorizedError("Invalid token - missing user identifier")
    return sub


def get_user_roles(payload: dict[str, Any]) -> list[str]:
    settings = get_settings()
    roles_claim = f"{settings.auth0.audience}/roles"
    roles = payload.get(roles_claim, [])

    if not isinstance(roles, list):
        logger.warning(f"Roles claim is not a list: {type(roles)}")
        return []

    return roles


def get_user_permissions(payload: dict[str, Any]) -> list[str]:
    """Extract permissions from JWT payload.

    Auth0 adds permissions to the token when RBAC is enabled.
    The permissions claim is at the top level of the token.
    """
    permissions = payload.get("permissions", [])

    if not isinstance(permissions, list):
        logger.warning(f"Permissions claim is not a list: {type(permissions)}")
        return []

    return permissions


def require_permission(required_permission: str):
    """Dependency factory that enforces a specific permission.

    Usage:
        @router.post("/transactions/{id}/block")
        async def block_transaction(
            id: str,
            user: AuthenticatedUser = Depends(require_permission("txn:block"))
        ):
            ...
    """

    def permission_checker(  # noqa: E501
        user: AuthenticatedUser = Depends(get_current_user),
    ) -> AuthenticatedUser:
        # Platform admin has all permissions
        if user.is_platform_admin:
            logger.debug("Platform admin - permission check bypassed")
            return user

        if not user.has_permission(required_permission):
            logger.warning(
                "Access denied - user %s lacks required permission: %s. User permissions: %s",
                user.user_id,
                required_permission,
                user.permissions,
            )
            # Sanitize error details in production to prevent information leakage
            settings = get_settings()
            if settings.security.sanitize_errors:
                raise ForbiddenError("Insufficient permissions")
            else:
                # Development mode: include details for debugging
                raise ForbiddenError(
                    "Insufficient permissions",
                    details={
                        "required_permission": required_permission,
                        "user_permissions": user.permissions,
                    },
                )

        logger.debug("Permission check passed: user has %s permission", required_permission)
        return user

    return permission_checker


def require_roles(*allowed_roles: str):
    """Dependency factory that enforces one of the allowed roles.

    Usage:
        @router.post("/transactions/{id}/override")
        async def override_transaction(
            id: str,
            user: AuthenticatedUser = Depends(require_roles("FRAUD_SUPERVISOR", "PLATFORM_ADMIN"))
        ):
            ...
    """

    def role_checker(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if not any(user.has_role(role) for role in allowed_roles):
            logger.warning(
                "Access denied - user %s lacks required roles: %s. User roles: %s",
                user.user_id,
                allowed_roles,
                user.roles,
            )
            raise ForbiddenError(
                "Insufficient permissions",
                details={"required_roles": list(allowed_roles), "user_roles": user.roles},
            )

        logger.debug("Role check passed: user has one of %s roles", allowed_roles)
        return user

    return role_checker


def require_role(required_role: str):
    def role_checker(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if not user.has_role(required_role):
            logger.warning(
                "Access denied - user %s lacks required role: %s. User roles: %s",
                user.user_id,
                required_role,
                user.roles,
            )
            raise ForbiddenError(
                "Insufficient permissions",
                details={"required_role": required_role, "user_roles": user.roles},
            )

        logger.debug("Role check passed: user has %s role", required_role)
        return user

    return role_checker


def setup_authentication(settings: Any) -> None:
    """Initialize authentication subsystem.

    Currently a no-op, but kept as a hook for future initialization needs
    (e.g.,预热 JWKS cache, validating Auth0 configuration on startup).
    """


def clear_jwks_cache() -> None:
    _jwks_cache.clear()
    logger.info("JWKS cache cleared")
