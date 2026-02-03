"""Pytest configuration for smoke tests.

These tests require DATABASE_URL_APP to be set.
"""

import os

# Set test environment variables before importing app
# IMPORTANT: Use Doppler for secrets management (preferred)
if "DATABASE_URL_APP" not in os.environ:
    raise RuntimeError(
        "DATABASE_URL_APP environment variable must be set for smoke testing.\n\n"
        "Recommended options:\n"
        "1. Run with Doppler secrets (REQUIRED for CI/Production): uv run doppler-local-test\n"
        "2. For local dev without Doppler: Create .env.test file and set ENV_FILE=.env.test\n"
    )
os.environ.setdefault("AUTH0_DOMAIN", "test.local")
os.environ.setdefault("AUTH0_AUDIENCE", "test-audience")
os.environ.setdefault("AUTH0_ALGORITHMS", "RS256")

import httpx
import pytest

from app.core.auth import AuthenticatedUser, get_current_user
from app.main import create_app


@pytest.fixture(scope="session")
def _app():
    """Create FastAPI app with mocked dependencies (session scoped)."""
    app = create_app()

    # Mock authentication - return AuthenticatedUser object, not dict
    def mock_current_user() -> AuthenticatedUser:
        return AuthenticatedUser(
            user_id="test_user_123",
            email="test@example.com",
            name="Test User",
            roles=["FRAUD_ANALYST"],
            permissions=["txn:view", "txn:comment"],
        )

    app.dependency_overrides[get_current_user] = mock_current_user
    return app


@pytest.fixture
async def test_client(_app):
    """Create httpx.AsyncClient for testing async routes."""
    transport = httpx.ASGITransport(app=_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture(autouse=True)
async def reset_database_engine():
    """Reset database engine before each test for fresh connections."""
    from app.core.database import reset_engine

    await reset_engine()
    yield
