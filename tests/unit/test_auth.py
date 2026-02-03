"""Unit tests for auth module (JWT verification, roles, dependencies)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jose import JWTError, jwt
from jose.jwt import ExpiredSignatureError, JWTClaimsError

from app.core.auth import (
    # Role constants
    FRAUD_ANALYST,
    FRAUD_SUPERVISOR,
    PLATFORM_ADMIN,
    # Permission constants
    TXN_APPROVE,
    TXN_BLOCK,
    TXN_COMMENT,
    TXN_FLAG,
    TXN_OVERRIDE,
    TXN_RECOMMEND,
    TXN_VIEW,
    AuthenticatedUser,
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitBreakerState,
    JWKSCache,
    TokenPayload,
    get_current_user,
    get_rsa_key,
    get_rsa_key_async,
    get_user_permissions,
    get_user_roles,
    get_user_sub,
    require_permission,
    require_role,
    require_roles,
    verify_token,
    verify_token_async,
)
from app.core.errors import ForbiddenError, UnauthorizedError

# Import mock tokens from conftest
from tests.conftest import (
    MOCK_FRAUD_ANALYST_TOKEN,
    MOCK_FRAUD_SUPERVISOR_TOKEN,
    MOCK_NO_ROLE_TOKEN,
    MOCK_PLATFORM_ADMIN_TOKEN,
    MOCK_VIEW_ONLY_TOKEN,
    ROLES_CLAIM,
)


class TestTokenPayload:
    """Test TokenPayload model."""

    def test_token_payload_creation(self):
        """Test creating a TokenPayload with all fields."""
        payload = TokenPayload(
            sub="auth0|12345",
            email="test@example.com",
            name="Test User",
            roles=[FRAUD_ANALYST, PLATFORM_ADMIN],
            exp=1234567890,
        )
        assert payload.sub == "auth0|12345"
        assert payload.email == "test@example.com"
        assert payload.roles == [FRAUD_ANALYST, PLATFORM_ADMIN]

    def test_token_payload_minimal(self):
        """Test creating TokenPayload with minimal fields."""
        payload = TokenPayload(sub="auth0|12345", exp=1234567890)
        assert payload.sub == "auth0|12345"
        assert payload.email is None
        assert payload.roles == []


class TestAuthenticatedUser:
    """Test AuthenticatedUser model."""

    def test_authenticated_user_platform_admin(self):
        """Test user with platform admin role."""
        user = AuthenticatedUser(
            user_id="auth0|12345",
            email="test@example.com",
            name="Test User",
            roles=[PLATFORM_ADMIN],
            permissions=[TXN_VIEW, TXN_APPROVE, TXN_BLOCK],
        )
        assert user.is_platform_admin is True
        assert user.is_fraud_analyst is True  # Admin implies analyst
        assert user.is_fraud_supervisor is True  # Admin implies supervisor

    def test_authenticated_user_fraud_analyst(self):
        """Test user with fraud analyst role."""
        user = AuthenticatedUser(
            user_id="auth0|12345",
            roles=[FRAUD_ANALYST],
            permissions=[TXN_VIEW, TXN_COMMENT, TXN_FLAG, TXN_RECOMMEND],
        )
        assert user.is_fraud_analyst is True
        assert user.is_fraud_supervisor is False
        assert user.is_platform_admin is False

    def test_authenticated_user_fraud_supervisor(self):
        """Test user with fraud supervisor role."""
        user = AuthenticatedUser(
            user_id="auth0|12345",
            roles=[FRAUD_SUPERVISOR],
            permissions=[TXN_VIEW, TXN_APPROVE, TXN_BLOCK, TXN_OVERRIDE],
        )
        assert user.is_fraud_supervisor is True
        assert user.is_fraud_analyst is False
        assert user.is_platform_admin is False

    def test_no_roles(self):
        """Test user with no roles."""
        user = AuthenticatedUser(user_id="auth0|12345")
        assert user.is_fraud_analyst is False
        assert user.is_fraud_supervisor is False
        assert user.is_platform_admin is False

    def test_has_permission(self):
        """Test has_permission method."""
        user = AuthenticatedUser(
            user_id="auth0|12345",
            roles=[FRAUD_ANALYST],
            permissions=[TXN_VIEW, TXN_COMMENT],
        )
        assert user.has_permission(TXN_VIEW) is True
        assert user.has_permission(TXN_COMMENT) is True
        assert user.has_permission(TXN_APPROVE) is False
        assert user.has_permission(TXN_BLOCK) is False

    def test_platform_admin_has_all_permissions(self):
        """Test platform admin bypasses permission checks."""
        user = AuthenticatedUser(
            user_id="auth0|12345",
            roles=[PLATFORM_ADMIN],
            permissions=[],  # No explicit permissions
        )
        # Platform admin should have all permissions
        assert user.has_permission(TXN_VIEW) is True
        assert user.has_permission(TXN_APPROVE) is True
        assert user.has_permission(TXN_OVERRIDE) is True

    def test_has_role(self):
        """Test has_role method."""
        user = AuthenticatedUser(
            user_id="auth0|12345",
            roles=[FRAUD_ANALYST, FRAUD_SUPERVISOR],
        )
        assert user.has_role(FRAUD_ANALYST) is True
        assert user.has_role(FRAUD_SUPERVISOR) is True
        assert user.has_role(PLATFORM_ADMIN) is False

    # Legacy property tests (backward compatibility)
    def test_legacy_is_analyst_property(self):
        """Test legacy is_analyst property."""
        user = AuthenticatedUser(user_id="auth0|12345", roles=[FRAUD_ANALYST])
        assert user.is_analyst is True

    def test_legacy_is_admin_property(self):
        """Test legacy is_admin property."""
        user = AuthenticatedUser(user_id="auth0|12345", roles=[PLATFORM_ADMIN])
        assert user.is_admin is True


class TestCircuitBreaker:
    """Test CircuitBreaker pattern."""

    def test_initial_state_closed(self):
        """Test circuit breaker starts in CLOSED state."""
        cb = CircuitBreaker(failure_threshold=3, timeout_seconds=60)
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0
        assert cb.is_open is False

    def test_record_failure_opens_circuit(self):
        """Test circuit opens after threshold failures."""
        cb = CircuitBreaker(failure_threshold=2, timeout_seconds=60)
        cb._record_failure()
        assert cb.failure_count == 1
        assert cb.state == CircuitBreakerState.CLOSED

        cb._record_failure()
        assert cb.failure_count == 2
        assert cb.state == CircuitBreakerState.OPEN
        assert cb.is_open is True

    def test_record_success_resets_count(self):
        """Test success resets failure count in closed state."""
        cb = CircuitBreaker(failure_threshold=5, timeout_seconds=60)
        cb._record_failure()
        cb._record_failure()
        cb._record_success()
        assert cb.failure_count == 0
        assert cb.state == CircuitBreakerState.CLOSED

    def test_reset(self):
        """Test circuit breaker reset."""
        cb = CircuitBreaker(failure_threshold=2, timeout_seconds=60)
        cb._record_failure()
        cb._record_failure()
        assert cb.state == CircuitBreakerState.OPEN

        cb.reset()
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0

    def test_call_success(self):
        """Test successful function call through circuit breaker."""
        cb = CircuitBreaker(failure_threshold=5, timeout_seconds=60)
        result = cb.call(lambda: "success")
        assert result == "success"
        assert cb.failure_count == 0

    def test_call_failure_opens_circuit(self):
        """Test function failure increments count."""
        cb = CircuitBreaker(failure_threshold=2, timeout_seconds=60)

        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("test")))

        assert cb.failure_count == 1
        assert cb.state == CircuitBreakerState.CLOSED


class TestGetUserSub:
    """Test get_user_sub utility function."""

    def test_valid_sub(self):
        """Test extracting valid sub claim."""
        payload = {"sub": "auth0|12345", "email": "test@example.com"}
        result = get_user_sub(payload)
        assert result == "auth0|12345"

    def test_missing_sub_raises(self):
        """Test missing sub claim raises UnauthorizedError."""
        payload = {"email": "test@example.com"}
        with pytest.raises(Exception) as exc_info:
            get_user_sub(payload)
        assert "missing user identifier" in str(exc_info.value).lower()


class TestGetUserRoles:
    """Test get_user_roles utility function."""

    def test_valid_roles(self):
        """Test extracting roles from payload."""
        mock_settings = MagicMock()
        mock_settings.auth0.audience = "https://fraud-transaction-management-api"

        payload = {
            "sub": "auth0|12345",
            ROLES_CLAIM: [FRAUD_ANALYST, PLATFORM_ADMIN],
        }

        with patch("app.core.auth.get_settings", return_value=mock_settings):
            result = get_user_roles(payload)
            assert result == [FRAUD_ANALYST, PLATFORM_ADMIN]

    def test_empty_roles(self):
        """Test empty roles list."""
        mock_settings = MagicMock()
        mock_settings.auth0.audience = "https://fraud-transaction-management-api"

        payload = {"sub": "auth0|12345"}
        with patch("app.core.auth.get_settings", return_value=mock_settings):
            result = get_user_roles(payload)
            assert result == []

    def test_malformed_roles(self):
        """Test malformed roles claim returns empty list."""
        mock_settings = MagicMock()
        mock_settings.auth0.audience = "https://fraud-transaction-management-api"

        payload = {
            "sub": "auth0|12345",
            ROLES_CLAIM: "not-a-list",
        }
        with patch("app.core.auth.get_settings", return_value=mock_settings):
            result = get_user_roles(payload)
            assert result == []


class TestGetUserPermissions:
    """Test get_user_permissions utility function."""

    def test_valid_permissions(self):
        """Test extracting permissions from payload."""
        payload = {
            "sub": "auth0|12345",
            "permissions": [TXN_VIEW, TXN_COMMENT, TXN_FLAG],
        }
        result = get_user_permissions(payload)
        assert result == [TXN_VIEW, TXN_COMMENT, TXN_FLAG]

    def test_empty_permissions(self):
        """Test empty permissions list."""
        payload = {"sub": "auth0|12345"}
        result = get_user_permissions(payload)
        assert result == []

    def test_malformed_permissions(self):
        """Test malformed permissions claim returns empty list."""
        payload = {
            "sub": "auth0|12345",
            "permissions": "not-a-list",
        }
        result = get_user_permissions(payload)
        assert result == []

    def test_fraud_analyst_permissions(self):
        """Test fraud analyst has expected permissions."""
        result = get_user_permissions(MOCK_FRAUD_ANALYST_TOKEN)
        assert TXN_VIEW in result
        assert TXN_COMMENT in result
        assert TXN_FLAG in result
        assert TXN_RECOMMEND in result
        assert TXN_APPROVE not in result
        assert TXN_BLOCK not in result

    def test_fraud_supervisor_permissions(self):
        """Test fraud supervisor has expected permissions."""
        result = get_user_permissions(MOCK_FRAUD_SUPERVISOR_TOKEN)
        assert TXN_VIEW in result
        assert TXN_APPROVE in result
        assert TXN_BLOCK in result
        assert TXN_OVERRIDE in result


class TestRequirePermission:
    """Test require_permission dependency factory."""

    def test_require_permission_with_valid_permission(self):
        """Test require_permission passes for user with required permission."""
        user = AuthenticatedUser(
            user_id=MOCK_FRAUD_ANALYST_TOKEN["sub"],
            email=MOCK_FRAUD_ANALYST_TOKEN.get("email"),
            name=MOCK_FRAUD_ANALYST_TOKEN.get("name"),
            roles=[FRAUD_ANALYST],
            permissions=[TXN_VIEW, TXN_COMMENT],
        )

        dependency = require_permission(TXN_VIEW)
        result = dependency(user)
        assert result == user
        assert result.user_id == user.user_id

    def test_require_permission_without_permission_raises(self):
        """Test require_permission raises for user without required permission."""
        user = AuthenticatedUser(
            user_id=MOCK_FRAUD_ANALYST_TOKEN["sub"],
            email=MOCK_FRAUD_ANALYST_TOKEN.get("email"),
            name=MOCK_FRAUD_ANALYST_TOKEN.get("name"),
            roles=[FRAUD_ANALYST],
            permissions=[TXN_VIEW],  # Only VIEW, not APPROVE
        )

        dependency = require_permission(TXN_APPROVE)
        with pytest.raises(ForbiddenError) as exc_info:
            dependency(user)
        # When sanitize_errors is True (default), no details are returned
        # In test mode with sanitize_errors=False, details are included
        assert exc_info.value.message == "Insufficient permissions"

    def test_platform_admin_bypasses_permission_check(self):
        """Test platform admin bypasses permission requirements."""
        user = AuthenticatedUser(
            user_id=MOCK_PLATFORM_ADMIN_TOKEN["sub"],
            email=MOCK_PLATFORM_ADMIN_TOKEN.get("email"),
            name=MOCK_PLATFORM_ADMIN_TOKEN.get("name"),
            roles=[PLATFORM_ADMIN],
            permissions=[],  # No explicit permissions
        )

        dependency = require_permission(TXN_OVERRIDE)
        result = dependency(user)
        assert result == user
        assert result.user_id == user.user_id


class TestRequireRoles:
    """Test require_roles dependency factory (multiple roles)."""

    def test_require_roles_with_valid_role(self):
        """Test require_roles passes for user with one of allowed roles."""
        user = AuthenticatedUser(
            user_id=MOCK_FRAUD_ANALYST_TOKEN["sub"],
            email=MOCK_FRAUD_ANALYST_TOKEN.get("email"),
            name=MOCK_FRAUD_ANALYST_TOKEN.get("name"),
            roles=[FRAUD_ANALYST],
            permissions=MOCK_FRAUD_ANALYST_TOKEN["permissions"],
        )

        dependency = require_roles(FRAUD_ANALYST, PLATFORM_ADMIN)
        result = dependency(user)
        assert result == user
        assert result.user_id == user.user_id

    def test_require_roles_without_role_raises(self):
        """Test require_roles raises when user has none of allowed roles."""
        user = AuthenticatedUser(
            user_id=MOCK_FRAUD_ANALYST_TOKEN["sub"],
            email=MOCK_FRAUD_ANALYST_TOKEN.get("email"),
            name=MOCK_FRAUD_ANALYST_TOKEN.get("name"),
            roles=[FRAUD_ANALYST],  # Only ANALYST, not SUPERVISOR or ADMIN
            permissions=MOCK_FRAUD_ANALYST_TOKEN["permissions"],
        )

        dependency = require_roles(FRAUD_SUPERVISOR, PLATFORM_ADMIN)
        with pytest.raises(ForbiddenError) as exc_info:
            dependency(user)
        assert "required_roles" in exc_info.value.details


class TestRequireRole:
    """Test require_role dependency factory (single role)."""

    def test_require_fraud_analyst_with_valid_role(self):
        """Test require_role passes for user with fraud analyst role."""
        user = AuthenticatedUser(
            user_id=MOCK_FRAUD_ANALYST_TOKEN["sub"],
            email=MOCK_FRAUD_ANALYST_TOKEN.get("email"),
            name=MOCK_FRAUD_ANALYST_TOKEN.get("name"),
            roles=[FRAUD_ANALYST],
            permissions=MOCK_FRAUD_ANALYST_TOKEN["permissions"],
        )

        dependency = require_role(FRAUD_ANALYST)
        result = dependency(user)
        assert result == user
        assert result.user_id == user.user_id

    def test_require_fraud_analyst_without_role_raises(self):
        """Test require_role raises for user without required role."""
        user = AuthenticatedUser(
            user_id=MOCK_FRAUD_SUPERVISOR_TOKEN["sub"],
            email=MOCK_FRAUD_SUPERVISOR_TOKEN.get("email"),
            name=MOCK_FRAUD_SUPERVISOR_TOKEN.get("name"),
            roles=[FRAUD_SUPERVISOR],  # SUPERVISOR, not ANALYST
            permissions=MOCK_FRAUD_SUPERVISOR_TOKEN["permissions"],
        )

        dependency = require_role(FRAUD_ANALYST)
        with pytest.raises(ForbiddenError) as exc_info:
            dependency(user)
        assert FRAUD_ANALYST in str(exc_info.value.details.get("required_role", ""))


class TestJWKSCache:
    """Test JWKS cache functionality."""

    def test_cache_initial_state(self):
        """Test cache starts empty."""
        cache = JWKSCache(ttl_seconds=3600)
        assert cache._cache is None
        assert cache._cache_time is None

    def test_clear_cache(self):
        """Test clearing cache."""
        cache = JWKSCache(ttl_seconds=3600)
        cache._cache = {"keys": []}
        cache._cache_time = MagicMock()

        cache.clear()
        assert cache._cache is None
        assert cache._cache_time is None
        assert cache._circuit_breaker.state == CircuitBreakerState.CLOSED


class TestVerifyToken:
    """Test token verification (mocked)."""

    def test_verify_token_with_mocked_jwks(self):
        """Test token verification with mocked JWKS."""
        mock_rsa_key = {
            "kty": "RSA",
            "kid": "test-kid",
            "use": "sig",
            "n": "test-n",
            "e": "test-e",
        }

        mock_jwks = {"keys": [mock_rsa_key]}

        with patch("app.core.auth.get_rsa_key", return_value=mock_rsa_key):
            with patch("app.core.auth.get_jwks", return_value=mock_jwks):
                with patch("app.core.auth.jwt.decode") as mock_decode:
                    mock_decode.return_value = {
                        "sub": "auth0|12345",
                        "email": "test@example.com",
                    }
                    result = verify_token("test-token")
                    assert result["sub"] == "auth0|12345"


class TestGetCurrentUser:
    """Test get_current_user dependency."""

    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(self):
        """Test extracting user from valid token returns AuthenticatedUser."""
        mock_credentials = MagicMock()
        mock_credentials.credentials = "valid-jwt-token"

        mock_payload = {
            "sub": "auth0|12345",
            "email": "test@example.com",
            "name": "Test User",
        }

        mock_settings = MagicMock()
        mock_settings.auth0.audience = "https://fraud-transaction-management-api"

        with patch("app.core.auth.get_settings", return_value=mock_settings):
            with patch("app.core.auth.get_user_roles", return_value=[FRAUD_ANALYST]):
                with patch("app.core.auth.get_user_permissions", return_value=[TXN_VIEW]):
                    with patch(
                        "app.core.auth.verify_token_async",
                        new_callable=AsyncMock,
                        return_value=mock_payload,
                    ):
                        user = await get_current_user(mock_credentials)
                        assert isinstance(user, AuthenticatedUser)
                        assert user.user_id == "auth0|12345"
                        assert user.email == "test@example.com"
                        assert user.name == "Test User"
                        assert user.roles == [FRAUD_ANALYST]
                        assert user.permissions == [TXN_VIEW]


class TestAsyncHttpClient:
    """Test async HTTP client functions."""

    @pytest.mark.asyncio
    async def test_get_async_http_client_creates_new(self):
        """Test get_async_http_client creates a new client when None."""
        import app.core.auth as auth_module
        from app.core.auth import close_async_http_client, get_async_http_client

        # Ensure _async_http is None by directly resetting the module-level variable
        await close_async_http_client()
        auth_module._async_http = None

        client = get_async_http_client()
        assert client is not None

        # Cleanup
        await close_async_http_client()

    @pytest.mark.asyncio
    async def test_get_async_http_client_returns_same(self):
        """Test get_async_http_client returns same client."""
        from app.core.auth import close_async_http_client, get_async_http_client

        client1 = get_async_http_client()
        client2 = get_async_http_client()
        assert client1 is client2

        await close_async_http_client()


class TestJWKSCacheAsync:
    """Test JWKS cache async methods."""

    @pytest.mark.asyncio
    async def test_jwks_cache_get_jwks_async_with_valid_cache(self):
        """Test get_jwks_async returns cached value when valid."""
        cache = JWKSCache(ttl_seconds=3600)
        cache._cache = {"keys": []}
        cache._cache_time = datetime.now(UTC)

        result = await cache.get_jwks_async()
        assert result == {"keys": []}

    @pytest.mark.asyncio
    async def test_jwks_cache_clear(self):
        """Test JWKSCache clear method."""
        cache = JWKSCache(ttl_seconds=3600)
        cache._cache = {"keys": []}
        cache._cache_time = datetime.now(UTC)

        cache.clear()
        assert cache._cache is None
        assert cache._cache_time is None
        assert cache._circuit_breaker.state == CircuitBreakerState.CLOSED


class TestCircuitBreakerAsync:
    """Test CircuitBreaker async methods."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_call_async_success(self):
        """Test async call with success."""
        cb = CircuitBreaker(failure_threshold=3, timeout_seconds=60)

        async def success_func():
            return "success"

        result = await cb.call_async(success_func)
        assert result == "success"
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_call_async_failure(self):
        """Test async call with failure."""
        cb = CircuitBreaker(failure_threshold=2, timeout_seconds=60)

        async def fail_func():
            raise ValueError("test error")

        with pytest.raises(ValueError):
            await cb.call_async(fail_func)

        assert cb.failure_count == 1
        assert cb.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_breaker_call_async_opens_after_threshold(self):
        """Test circuit opens after threshold failures."""
        cb = CircuitBreaker(failure_threshold=2, timeout_seconds=60)

        async def fail_func():
            raise ValueError("test error")

        for _ in range(2):
            try:
                await cb.call_async(fail_func)
            except ValueError:
                pass

        assert cb.state == CircuitBreakerState.OPEN
        assert cb.is_open is True


class TestVerifyTokenAsync:
    """Test async token verification."""

    @pytest.mark.asyncio
    async def test_verify_token_async_success(self):
        """Test successful async token verification."""
        mock_rsa_key = {
            "kty": "RSA",
            "kid": "test-kid",
            "use": "sig",
            "n": "test-n",
            "e": "test-e",
        }

        mock_payload = {
            "sub": "auth0|12345",
            "email": "test@example.com",
            "exp": 9999999999,
        }

        with patch("app.core.auth.get_rsa_key_async", return_value=mock_rsa_key):
            with patch("app.core.auth.jwt.decode", return_value=mock_payload):
                result = await verify_token_async("test-token")
                assert result["sub"] == "auth0|12345"

    @pytest.mark.asyncio
    async def test_verify_token_async_expired_token(self):
        """Test async token verification with expired token."""
        mock_rsa_key = {
            "kty": "RSA",
            "kid": "test-kid",
            "use": "sig",
            "n": "test-n",
            "e": "test-e",
        }

        with patch("app.core.auth.get_rsa_key_async", return_value=mock_rsa_key):
            with patch("app.core.auth.jwt.decode", side_effect=ExpiredSignatureError()):
                with pytest.raises(UnauthorizedError) as exc_info:
                    await verify_token_async("expired-token")
                assert "Invalid or expired token" in str(exc_info.value)


class TestAuthModuleExports:
    """Test module-level exports and constants."""

    def test_security_constant_exists(self):
        """Test HTTPBearer security instance exists."""
        from app.core.auth import security

        assert security is not None

    def test_invalid_token_message_exists(self):
        """Test INVALID_OR_EXPIRED_TOKEN_MSG constant exists."""
        from app.core.auth import INVALID_OR_EXPIRED_TOKEN_MSG

        assert INVALID_OR_EXPIRED_TOKEN_MSG == "Invalid or expired token"

    def test_circuit_breaker_state_enum_values(self):
        """Test CircuitBreakerState enum values."""
        assert CircuitBreakerState.CLOSED.value == "closed"
        assert CircuitBreakerState.OPEN.value == "open"
        assert CircuitBreakerState.HALF_OPEN.value == "half_open"

    def test_circuit_breaker_open_error_exists(self):
        """Test CircuitBreakerOpenError class exists."""
        from app.core.auth import CircuitBreakerOpenError

        error = CircuitBreakerOpenError("test")
        assert str(error) == "test"


class TestCircuitBreakerReset:
    """Test CircuitBreaker reset and recovery."""

    def test_circuit_breaker_reset_resets_failure_count(self):
        """Test reset clears failure count."""
        cb = CircuitBreaker(failure_threshold=2, timeout_seconds=60)
        cb._record_failure()
        cb._record_failure()
        assert cb.state == CircuitBreakerState.OPEN
        assert cb.failure_count == 2

        cb.reset()
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0

    def test_circuit_breaker_half_open_to_closed_on_success(self):
        """Test circuit closes after success in half-open state."""
        cb = CircuitBreaker(failure_threshold=2, timeout_seconds=60)
        # Set to HALF_OPEN directly
        cb._state = CircuitBreakerState.HALF_OPEN

        result = cb.call(lambda: "success")
        assert result == "success"
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0

    def test_circuit_breaker_failure_in_half_open_increases_count(self):
        """Test circuit tracks failure count in half-open state."""
        cb = CircuitBreaker(failure_threshold=2, timeout_seconds=60)
        cb._state = CircuitBreakerState.HALF_OPEN
        cb._failure_count = 0

        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("test")))

        # In HALF_OPEN, failure increments count but doesn't immediately open
        # unless threshold is met
        assert cb.failure_count == 1
        assert cb.state == CircuitBreakerState.HALF_OPEN

    def test_circuit_breaker_failure_count_property(self):
        """Test failure_count property."""
        cb = CircuitBreaker(failure_threshold=3, timeout_seconds=60)
        assert cb.failure_count == 0

        cb._record_failure()
        assert cb.failure_count == 1

        cb._record_failure()
        assert cb.failure_count == 2

    def test_circuit_breaker_state_property(self):
        """Test state property returns correct enum."""
        cb = CircuitBreaker(failure_threshold=2, timeout_seconds=60)
        assert cb.state == CircuitBreakerState.CLOSED

        cb._record_failure()
        cb._record_failure()
        assert cb.state == CircuitBreakerState.OPEN


class TestJWKSCacheAdvanced:
    """Test JWKS cache advanced scenarios."""

    def test_jwks_cache_is_cache_valid_true(self):
        """Test _is_cache_valid returns True for fresh cache."""
        cache = JWKSCache(ttl_seconds=3600)
        cache._cache = {"keys": []}
        cache._cache_time = datetime.now(UTC)

        now = datetime.now(UTC)
        assert cache._is_cache_valid(now) is True

    def test_jwks_cache_is_cache_valid_false_expired(self):
        """Test _is_cache_valid returns False for expired cache."""
        cache = JWKSCache(ttl_seconds=3600)

        # Set cache time to 4000 seconds ago (past TTL)
        past_time = datetime.now(UTC).timestamp() - 4000
        cache._cache_time = datetime.fromtimestamp(past_time, tz=UTC)
        cache._cache = {"keys": []}

        now = datetime.now(UTC)
        assert cache._is_cache_valid(now) is False

    def test_jwks_cache_is_cache_valid_false_no_cache(self):
        """Test _is_cache_valid returns False when no cache."""
        cache = JWKSCache(ttl_seconds=3600)
        cache._cache = None
        cache._cache_time = datetime.now(UTC)

        now = datetime.now(UTC)
        assert cache._is_cache_valid(now) is False

    def test_jwks_cache_use_stale_cache_if_available(self):
        """Test _use_stale_cache_if_available returns cache when available."""
        cache = JWKSCache(ttl_seconds=3600)
        stale_cache = {"keys": [{"kid": "test"}]}
        cache._cache = stale_cache

        result = cache._use_stale_cache_if_available("test reason")
        assert result == stale_cache

    def test_jwks_cache_use_stale_cache_if_available_none(self):
        """Test _use_stale_cache_if_available returns None when no cache."""
        cache = JWKSCache(ttl_seconds=3600)
        cache._cache = None

        result = cache._use_stale_cache_if_available("test reason")
        assert result is None

    def test_jwks_cache_handle_fetch_error_circuit_open(self):
        """Test _handle_fetch_error with circuit open error."""
        cache = JWKSCache(ttl_seconds=3600)
        cache._cache = {"keys": []}

        error = CircuitBreakerOpenError("Circuit breaker is OPEN")
        result = cache._handle_fetch_error(error)
        assert result == {"keys": []}

    def test_jwks_cache_handle_fetch_error_with_stale_cache(self):
        """Test _handle_fetch_error returns stale cache on fetch error."""
        cache = JWKSCache(ttl_seconds=3600)
        cache._cache = {"keys": [{"kid": "stale"}]}

        error = ConnectionError("Failed to fetch")
        result = cache._handle_fetch_error(error)
        assert result == {"keys": [{"kid": "stale"}]}

    def test_jwks_cache_handle_fetch_error_no_cache_raises(self):
        """Test _handle_fetch_error raises when no stale cache."""
        cache = JWKSCache(ttl_seconds=3600)
        cache._cache = None

        error = ConnectionError("Failed to fetch")
        with pytest.raises(UnauthorizedError) as exc_info:
            cache._handle_fetch_error(error)
        assert "authentication service unavailable" in str(exc_info.value)

    def test_jwks_cache_check_circuit_breaker_with_cache(self):
        """Test _check_circuit_breaker returns cache when circuit open."""
        cache = JWKSCache(ttl_seconds=3600)
        cache._cache = {"keys": []}
        cache._circuit_breaker._state = CircuitBreakerState.OPEN

        now = datetime.now(UTC)
        result = cache._check_circuit_breaker(now)
        assert result == {"keys": []}

    def test_jwks_cache_check_circuit_breaker_closed(self):
        """Test _check_circuit_breaker returns None when circuit closed."""
        cache = JWKSCache(ttl_seconds=3600)
        cache._cache = {"keys": []}
        cache._circuit_breaker._state = CircuitBreakerState.CLOSED

        now = datetime.now(UTC)
        result = cache._check_circuit_breaker(now)
        assert result is None


class TestGetRSAKey:
    """Test RSA key extraction from JWKS."""

    def test_get_rsa_key_found(self):
        """Test get_rsa_key finds matching key."""
        mock_rsa_key = {
            "kty": "RSA",
            "kid": "test-kid",
            "use": "sig",
            "n": "test-n",
            "e": "test-e",
        }
        mock_jwks = {"keys": [mock_rsa_key]}

        with patch("app.core.auth.get_jwks", return_value=mock_jwks):
            with patch("app.core.auth.jwt.get_unverified_header", return_value={"kid": "test-kid"}):
                result = get_rsa_key("test-token")
                assert result["kid"] == "test-kid"
                assert result["kty"] == "RSA"

    def test_get_rsa_key_not_found(self):
        """Test get_rsa_key raises when key not found."""
        mock_jwks = {"keys": [{"kid": "other-kid"}]}

        with patch("app.core.auth.get_jwks", return_value=mock_jwks):
            with patch(
                "app.core.auth.jwt.get_unverified_header", return_value={"kid": "missing-kid"}
            ):
                with pytest.raises(UnauthorizedError) as exc_info:
                    get_rsa_key("test-token")
                assert "Invalid or expired token" in str(exc_info.value)

    def test_get_rsa_key_invalid_header(self):
        """Test get_rsa_key raises on invalid header."""
        with patch(
            "app.core.auth.jwt.get_unverified_header", side_effect=JWTError("Invalid header")
        ):
            with pytest.raises(UnauthorizedError) as exc_info:
                get_rsa_key("test-token")
                assert "Invalid or expired token" in str(exc_info.value)


class TestVerifyTokenErrors:
    """Test token verification error handling."""

    def test_verify_token_expired_signature(self):
        """Test verify_token raises on expired token."""
        mock_rsa_key = {
            "kty": "RSA",
            "kid": "test-kid",
            "use": "sig",
            "n": "test-n",
            "e": "test-e",
        }

        with patch("app.core.auth.get_rsa_key", return_value=mock_rsa_key):
            with patch("app.core.auth.jwt.decode", side_effect=ExpiredSignatureError()):
                with pytest.raises(UnauthorizedError) as exc_info:
                    verify_token("expired-token")
                assert "Invalid or expired token" in str(exc_info.value)

    def test_verify_token_claims_error(self):
        """Test verify_token raises on claims error."""
        mock_rsa_key = {
            "kty": "RSA",
            "kid": "test-kid",
            "use": "sig",
            "n": "test-n",
            "e": "test-e",
        }

        with patch("app.core.auth.get_rsa_key", return_value=mock_rsa_key):
            with patch("app.core.auth.jwt.decode", side_effect=JWTClaimsError("Invalid claims")):
                with pytest.raises(UnauthorizedError) as exc_info:
                    verify_token("invalid-claims-token")
                assert "Invalid or expired token" in str(exc_info.value)

    def test_verify_token_jwt_error(self):
        """Test verify_token raises on general JWT error."""
        mock_rsa_key = {
            "kty": "RSA",
            "kid": "test-kid",
            "use": "sig",
            "n": "test-n",
            "e": "test-e",
        }

        with patch("app.core.auth.get_rsa_key", return_value=mock_rsa_key):
            with patch("app.core.auth.jwt.decode", side_effect=JWTError("JWT error")):
                with pytest.raises(UnauthorizedError) as exc_info:
                    verify_token("jwt-error-token")
                assert "Invalid or expired token" in str(exc_info.value)


class TestVerifyTokenAsyncErrors:
    """Test async token verification error handling."""

    @pytest.mark.asyncio
    async def test_verify_token_async_claims_error(self):
        """Test async verify_token raises on claims error."""
        mock_rsa_key = {
            "kty": "RSA",
            "kid": "test-kid",
            "use": "sig",
            "n": "test-n",
            "e": "test-e",
        }

        with patch("app.core.auth.get_rsa_key_async", return_value=mock_rsa_key):
            with patch(
                "app.core.auth.jwt.decode", side_effect=jwt.JWTClaimsError("Invalid claims")
            ):
                with pytest.raises(UnauthorizedError) as exc_info:
                    await verify_token_async("invalid-claims-token")
                assert "Invalid or expired token" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_verify_token_async_jwt_error(self):
        """Test async verify_token raises on general JWT error."""
        mock_rsa_key = {
            "kty": "RSA",
            "kid": "test-kid",
            "use": "sig",
            "n": "test-n",
            "e": "test-e",
        }

        with patch("app.core.auth.get_rsa_key_async", return_value=mock_rsa_key):
            with patch("app.core.auth.jwt.decode", side_effect=JWTError("JWT error")):
                with pytest.raises(UnauthorizedError) as exc_info:
                    await verify_token_async("jwt-error-token")
                assert "Invalid or expired token" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_verify_token_async_unexpected_error(self):
        """Test async verify_token raises on unexpected error."""
        mock_rsa_key = {
            "kty": "RSA",
            "kid": "test-kid",
            "use": "sig",
            "n": "test-n",
            "e": "test-e",
        }

        with patch("app.core.auth.get_rsa_key_async", return_value=mock_rsa_key):
            with patch("app.core.auth.jwt.decode", side_effect=RuntimeError("Unexpected")):
                with pytest.raises(UnauthorizedError) as exc_info:
                    await verify_token_async("unexpected-error-token")
                assert "Invalid or expired token" in str(exc_info.value)


class TestJWKSCacheAsyncFetch:
    """Test JWKS async fetch scenarios."""

    @pytest.mark.asyncio
    async def test_jwks_cache_get_jwks_async_cache_miss(self):
        """Test get_jwks_async fetches when cache is empty."""
        cache = JWKSCache(ttl_seconds=3600)
        cache._cache = None
        cache._cache_time = None

        mock_response = MagicMock()
        mock_response.json.return_value = {"keys": [{"kid": "test"}]}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        settings = MagicMock()
        settings.auth0.jwks_url = "https://example.com/.well-known/jwks.json"

        with patch("app.core.auth.get_async_http_client", return_value=mock_client):
            with patch("app.core.auth.get_settings", return_value=settings):
                result = await cache.get_jwks_async()
                assert result == {"keys": [{"kid": "test"}]}
                mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_jwks_cache_get_jwks_async_circuit_breaker_open(self):
        """Test get_jwks_async uses stale cache when circuit is open."""
        cache = JWKSCache(ttl_seconds=3600)
        cache._cache = {"keys": [{"kid": "stale"}]}
        cache._cache_time = datetime.now(UTC)
        cache._circuit_breaker._state = CircuitBreakerState.OPEN

        result = await cache.get_jwks_async()
        assert result == {"keys": [{"kid": "stale"}]}


class TestJWKSCacheSyncFetch:
    """Test JWKS sync fetch scenarios."""

    def test_jwks_cache_get_jwks_cache_miss(self):
        """Test get_jwks fetches when cache is empty."""
        cache = JWKSCache(ttl_seconds=3600)
        cache._cache = None
        cache._cache_time = None

        mock_response = MagicMock()
        mock_response.json.return_value = {"keys": [{"kid": "test"}]}
        mock_response.raise_for_status = MagicMock()

        settings = MagicMock()
        settings.auth0.jwks_url = "https://example.com/.well-known/jwks.json"

        with patch("app.core.auth._http.get", return_value=mock_response):
            with patch("app.core.auth.get_settings", return_value=settings):
                result = cache.get_jwks()
                assert result == {"keys": [{"kid": "test"}]}

    def test_jwks_cache_get_jwks_circuit_breaker_open(self):
        """Test get_jwks uses stale cache when circuit is open."""
        cache = JWKSCache(ttl_seconds=3600)
        cache._cache = {"keys": [{"kid": "stale"}]}
        cache._cache_time = datetime.now(UTC)
        cache._circuit_breaker._state = CircuitBreakerState.OPEN

        result = cache.get_jwks()
        assert result == {"keys": [{"kid": "stale"}]}


class TestModuleFunctions:
    """Test module-level functions."""

    def test_get_jwks_module_function(self):
        """Test module-level get_jwks function."""
        from app.core.auth import _jwks_cache, get_jwks

        with patch.object(_jwks_cache, "get_jwks", return_value={"keys": []}) as mock_get:
            result = get_jwks()
            assert result == {"keys": []}
            mock_get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_jwks_async_module_function(self):
        """Test module-level get_jwks_async function."""
        from app.core.auth import _jwks_cache, get_jwks_async

        with patch.object(_jwks_cache, "get_jwks_async", return_value={"keys": []}) as mock_get:
            result = await get_jwks_async()
            assert result == {"keys": []}
            mock_get.assert_called_once()

    def test_clear_jwks_cache(self):
        """Test clear_jwks_cache function."""
        from app.core.auth import _jwks_cache, clear_jwks_cache

        with patch.object(_jwks_cache, "clear") as mock_clear:
            clear_jwks_cache()
            mock_clear.assert_called_once()

    def test_setup_authentication_does_nothing(self):
        """Test setup_authentication is a no-op."""
        from app.core.auth import setup_authentication

        setup_authentication(None)  # Should not raise

    def test_close_async_http_client(self):
        """Test close_async_http_client cleans up client."""
        from app.core.auth import _async_http, close_async_http_client, get_async_http_client

        # Create a client first
        get_async_http_client()

        # Close it
        import asyncio

        asyncio.run(close_async_http_client())

        # Verify it was closed
        assert _async_http is None


class TestCircuitBreakerHalfOpen:
    """Test CircuitBreaker half-open state transitions."""

    def test_circuit_breaker_half_open_call_with_args(self):
        """Test circuit breaker call with callable and args."""
        cb = CircuitBreaker(failure_threshold=5, timeout_seconds=60)

        def add(a, b):
            return a + b

        result = cb.call(add, 2, 3)
        assert result == 5

    def test_circuit_breaker_half_open_call_with_kwargs(self):
        """Test circuit breaker call with callable and kwargs."""
        cb = CircuitBreaker(failure_threshold=5, timeout_seconds=60)

        def greet(name, prefix="Hello"):
            return f"{prefix}, {name}!"

        result = cb.call(greet, "World", prefix="Hi")
        assert result == "Hi, World!"

    def test_circuit_breaker_half_open_non_callable_raises(self):
        """Test circuit breaker call with non-callable raises."""
        cb = CircuitBreaker(failure_threshold=5, timeout_seconds=60)

        with pytest.raises(TypeError):
            cb.call("not a function")


class TestGetRSAKeyAsync:
    """Test async RSA key extraction."""

    @pytest.mark.asyncio
    async def test_get_rsa_key_async_found(self):
        """Test get_rsa_key_async finds matching key."""
        mock_rsa_key = {
            "kty": "RSA",
            "kid": "test-kid",
            "use": "sig",
            "n": "test-n",
            "e": "test-e",
        }
        mock_jwks = {"keys": [mock_rsa_key]}

        with patch("app.core.auth.get_jwks_async", return_value=mock_jwks):
            with patch("app.core.auth.jwt.get_unverified_header", return_value={"kid": "test-kid"}):
                result = await get_rsa_key_async("test-token")
                assert result["kid"] == "test-kid"
                assert result["kty"] == "RSA"

    @pytest.mark.asyncio
    async def test_get_rsa_key_async_not_found(self):
        """Test get_rsa_key_async raises when key not found."""
        mock_jwks = {"keys": [{"kid": "other-kid"}]}

        with patch("app.core.auth.get_jwks_async", return_value=mock_jwks):
            with patch(
                "app.core.auth.jwt.get_unverified_header", return_value={"kid": "missing-kid"}
            ):
                with pytest.raises(UnauthorizedError) as exc_info:
                    await get_rsa_key_async("test-token")
                assert "Invalid or expired token" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_rsa_key_async_invalid_header(self):
        """Test get_rsa_key_async raises on invalid header."""
        with patch(
            "app.core.auth.jwt.get_unverified_header", side_effect=JWTError("Invalid header")
        ):
            with pytest.raises(UnauthorizedError) as exc_info:
                await get_rsa_key_async("test-token")
                assert "Invalid or expired token" in str(exc_info.value)


class TestVerifyTokenAsyncMoreErrors:
    """Additional async token verification error tests."""

    @pytest.mark.asyncio
    async def test_verify_token_async_key_not_found(self):
        """Test async verify_token raises when key not found."""
        mock_jwks = {"keys": [{"kid": "other-kid"}]}

        with patch("app.core.auth.get_jwks_async", return_value=mock_jwks):
            with patch(
                "app.core.auth.jwt.get_unverified_header", return_value={"kid": "missing-kid"}
            ):
                with pytest.raises(UnauthorizedError) as exc_info:
                    await verify_token_async("test-token")
                assert "Invalid or expired token" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_verify_token_async_invalid_header(self):
        """Test async verify_token raises on invalid header."""
        with patch(
            "app.core.auth.jwt.get_unverified_header", side_effect=JWTError("Invalid header")
        ):
            with pytest.raises(UnauthorizedError) as exc_info:
                await verify_token_async("test-token")
                assert "Invalid or expired token" in str(exc_info.value)


class TestJWKSModuleFunctions:
    """Test module-level JWKS functions."""

    def test_get_jwks_returns_cached(self):
        """Test get_jwks returns cached value."""
        from app.core.auth import _jwks_cache, get_jwks

        _jwks_cache._cache = {"keys": [{"kid": "cached"}]}
        _jwks_cache._cache_time = datetime.now(UTC)

        result = get_jwks()
        assert result == {"keys": [{"kid": "cached"}]}

        # Cleanup
        _jwks_cache.clear()

    @pytest.mark.asyncio
    async def test_get_jwks_async_returns_cached(self):
        """Test get_jwks_async returns cached value."""
        from app.core.auth import _jwks_cache, get_jwks_async

        _jwks_cache._cache = {"keys": [{"kid": "cached"}]}
        _jwks_cache._cache_time = datetime.now(UTC)

        result = await get_jwks_async()
        assert result == {"keys": [{"kid": "cached"}]}

        # Cleanup
        _jwks_cache.clear()


class TestCircuitBreakerAsyncAdvanced:
    """Advanced async circuit breaker tests."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_call_async_with_args(self):
        """Test async call with args."""
        cb = CircuitBreaker(failure_threshold=5, timeout_seconds=60)

        async def multiply(a, b):
            return a * b

        result = await cb.call_async(multiply, 3, 4)
        assert result == 12

    @pytest.mark.asyncio
    async def test_circuit_breaker_call_async_with_kwargs(self):
        """Test async call with kwargs."""
        cb = CircuitBreaker(failure_threshold=5, timeout_seconds=60)

        async def format_message(message, prefix="Hello"):
            return f"{prefix}: {message}"

        result = await cb.call_async(format_message, "World", prefix="Hi")
        assert result == "Hi: World"

    @pytest.mark.asyncio
    async def test_circuit_breaker_call_async_non_callable_raises(self):
        """Test async call with non-callable raises."""
        cb = CircuitBreaker(failure_threshold=5, timeout_seconds=60)

        with pytest.raises(TypeError) as exc_info:
            await cb.call_async("not a function")

        assert "callable" in str(exc_info.value).lower()


class TestRoleConstants:
    """Test role constant definitions (matching AUTH_MODEL.md)."""

    def test_platform_admin_constant(self):
        """Test PLATFORM_ADMIN constant value."""
        assert PLATFORM_ADMIN == "PLATFORM_ADMIN"

    def test_fraud_analyst_constant(self):
        """Test FRAUD_ANALYST constant value."""
        assert FRAUD_ANALYST == "FRAUD_ANALYST"

    def test_fraud_supervisor_constant(self):
        """Test FRAUD_SUPERVISOR constant value."""
        assert FRAUD_SUPERVISOR == "FRAUD_SUPERVISOR"


class TestPermissionConstants:
    """Test permission constant definitions (matching AUTH_MODEL.md)."""

    def test_txn_view_constant(self):
        """Test TXN_VIEW constant value."""
        assert TXN_VIEW == "txn:view"

    def test_txn_comment_constant(self):
        """Test TXN_COMMENT constant value."""
        assert TXN_COMMENT == "txn:comment"

    def test_txn_flag_constant(self):
        """Test TXN_FLAG constant value."""
        assert TXN_FLAG == "txn:flag"

    def test_txn_recommend_constant(self):
        """Test TXN_RECOMMEND constant value."""
        assert TXN_RECOMMEND == "txn:recommend"

    def test_txn_approve_constant(self):
        """Test TXN_APPROVE constant value."""
        assert TXN_APPROVE == "txn:approve"

    def test_txn_block_constant(self):
        """Test TXN_BLOCK constant value."""
        assert TXN_BLOCK == "txn:block"

    def test_txn_override_constant(self):
        """Test TXN_OVERRIDE constant value."""
        assert TXN_OVERRIDE == "txn:override"


class TestMockTokens:
    """Test mock token fixtures are correctly structured."""

    def test_platform_admin_token_structure(self):
        """Test platform admin token has all permissions."""
        assert "sub" in MOCK_PLATFORM_ADMIN_TOKEN
        assert ROLES_CLAIM in MOCK_PLATFORM_ADMIN_TOKEN
        assert PLATFORM_ADMIN in MOCK_PLATFORM_ADMIN_TOKEN[ROLES_CLAIM]
        assert "permissions" in MOCK_PLATFORM_ADMIN_TOKEN
        # Platform admin should have all txn permissions
        permissions = MOCK_PLATFORM_ADMIN_TOKEN["permissions"]
        assert TXN_VIEW in permissions
        assert TXN_APPROVE in permissions
        assert TXN_OVERRIDE in permissions

    def test_fraud_analyst_token_structure(self):
        """Test fraud analyst token has correct permissions."""
        assert FRAUD_ANALYST in MOCK_FRAUD_ANALYST_TOKEN[ROLES_CLAIM]
        permissions = MOCK_FRAUD_ANALYST_TOKEN["permissions"]
        assert TXN_VIEW in permissions
        assert TXN_COMMENT in permissions
        assert TXN_FLAG in permissions
        assert TXN_RECOMMEND in permissions
        # Should NOT have supervisor permissions
        assert TXN_APPROVE not in permissions
        assert TXN_BLOCK not in permissions

    def test_fraud_supervisor_token_structure(self):
        """Test fraud supervisor token has correct permissions."""
        assert FRAUD_SUPERVISOR in MOCK_FRAUD_SUPERVISOR_TOKEN[ROLES_CLAIM]
        permissions = MOCK_FRAUD_SUPERVISOR_TOKEN["permissions"]
        assert TXN_VIEW in permissions
        assert TXN_APPROVE in permissions
        assert TXN_BLOCK in permissions
        assert TXN_OVERRIDE in permissions

    def test_no_role_token_structure(self):
        """Test no-role token has no permissions."""
        assert MOCK_NO_ROLE_TOKEN[ROLES_CLAIM] == []
        assert MOCK_NO_ROLE_TOKEN["permissions"] == []

    def test_view_only_token_structure(self):
        """Test view-only token has only view permission."""
        assert MOCK_VIEW_ONLY_TOKEN["permissions"] == [TXN_VIEW]
