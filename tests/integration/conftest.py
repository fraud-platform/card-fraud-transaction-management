"""Pytest configuration for integration and smoke tests.

These tests require DATABASE_URL_APP to be set.
"""

import os

# Set test environment variables before importing app
# IMPORTANT: Use Doppler for secrets management (preferred)
if "DATABASE_URL_APP" not in os.environ:
    raise RuntimeError(
        "DATABASE_URL_APP environment variable must be set for integration/smoke testing.\n\n"
        "Recommended options:\n"
        "1. Run with Doppler secrets (REQUIRED for CI/Production): uv run doppler-local-test\n"
        "2. For local dev without Doppler: Create .env.test file and set ENV_FILE=.env.test\n"
    )
os.environ.setdefault("AUTH0_DOMAIN", "test.local")
os.environ.setdefault("AUTH0_AUDIENCE", "test-audience")
os.environ.setdefault("AUTH0_ALGORITHMS", "RS256")
os.environ.setdefault("FEATURE_ENABLE_AUTO_REVIEW_CREATION", "false")


import pytest

from app.core.auth import get_current_user
from app.main import create_app


@pytest.fixture(scope="session")
def client_app():
    """Create FastAPI app with mocked dependencies (session scoped)."""
    app = create_app()

    # Mock authentication
    def mock_current_user() -> dict:
        return {
            "sub": "test_user_integration",
            "https://fraud-transaction-management-api/roles": ["FRAUD_ANALYST"],
            "permissions": ["txn:view", "txn:comment"],
        }

    app.dependency_overrides[get_current_user] = mock_current_user
    return app


@pytest.fixture(scope="session")
def client_app_no_auth():
    """Create FastAPI app without authentication override (for testing auth failures)."""
    # Create a fresh app without any auth overrides
    # This app will enforce real authentication
    return create_app()


@pytest.fixture(autouse=True)
async def reset_database_engine():
    """Reset database engine before each test for fresh connections."""
    from app.core.database import reset_engine

    await reset_engine()
    yield
