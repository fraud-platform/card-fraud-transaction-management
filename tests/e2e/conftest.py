"""Pytest configuration for E2E integration tests.

These tests test full end-to-end workflows across multiple endpoints.
Run with: uv run doppler-local-test -m e2e_integration

Key difference from other tests:
- Unit: Isolated component tests with mocks
- Integration: Single endpoint tests with real DB
- Smoke: Basic happy path tests
- E2E: Complete workflow tests spanning multiple endpoints

Note: Uses ASGI transport (same as smoke/integration) for reliability.
The "E2E" aspect comes from testing complete workflows, not the HTTP layer.
"""

from __future__ import annotations

import os

import httpx
import pytest

# Set test environment variables before importing app
if "DATABASE_URL_APP" not in os.environ:
    raise RuntimeError(
        "DATABASE_URL_APP environment variable must be set for E2E testing.\n\n"
        "Recommended options:\n"
        "1. Run with Doppler secrets (REQUIRED for CI/Production): "
        "uv run doppler-local-test -m e2e_integration\n"
        "2. For local dev without Doppler: Create .env.test file and set ENV_FILE=.env.test\n"
    )

os.environ.setdefault("AUTH0_DOMAIN", "test.local")
os.environ.setdefault("AUTH0_AUDIENCE", "test-audience")
os.environ.setdefault("AUTH0_ALGORITHMS", "RS256")
os.environ.setdefault("FEATURE_ENABLE_AUTO_REVIEW_CREATION", "true")  # Enable for E2E tests

from datetime import UTC
from typing import Any

from fastapi import FastAPI

from app.core.auth import AuthenticatedUser, get_current_user
from app.main import create_app


@pytest.fixture(scope="session")
def e2e_app() -> FastAPI:
    """Create FastAPI app with mocked dependencies for E2E tests (session scoped)."""
    app = create_app()

    # Mock authentication with full permissions for E2E workflow testing
    def mock_current_user() -> AuthenticatedUser:
        return AuthenticatedUser(
            user_id="test_user_e2e",
            email="test-e2e@fraud-platform.test",
            name="E2E Test User",
            roles=["FRAUD_ANALYST", "FRAUD_SUPERVISOR"],
            permissions=[
                "txn:view",
                "txn:comment",
                "txn:flag",
                "txn:recommend",
                "txn:approve",
                "txn:block",
                "txn:override",
            ],
        )

    app.dependency_overrides[get_current_user] = mock_current_user
    return app


@pytest.fixture
async def http_client(e2e_app):
    """Create httpx.AsyncClient for E2E tests.

    Uses ASGI transport for reliable testing. The E2E aspect
    comes from testing complete workflows across multiple endpoints.
    """
    transport = httpx.ASGITransport(app=e2e_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", timeout=30.0
    ) as client:
        yield client


@pytest.fixture(autouse=True)
async def reset_database_engine_e2e():
    """Reset database engine before each E2E test for fresh connections."""
    from app.core.database import reset_engine

    await reset_engine()
    yield


@pytest.fixture(autouse=True)
async def truncate_database_tables_e2e():
    """Delete all data from database tables before each E2E test.

    This ensures tests are isolated and don't see data from previous tests.
    Uses DELETE instead of TRUNCATE since test database user may lack
    TRUNCATE privileges.
    """
    from sqlalchemy import text

    from app.core.database import get_session_factory

    # Delete in correct order due to foreign key dependencies
    tables = [
        "fraud_gov.case_activity_log",
        "fraud_gov.transaction_reviews",
        "fraud_gov.analyst_notes",
        "fraud_gov.transaction_cases",
        "fraud_gov.transaction_rule_matches",
        "fraud_gov.transactions",
    ]

    factory = get_session_factory()
    async with factory() as session:
        for table in tables:
            await session.execute(text(f"DELETE FROM {table}"))
        await session.commit()
    yield


# =============================================================================
# E2E Sample Data Fixtures
# =============================================================================


@pytest.fixture
def e2e_sample_decision_event() -> dict[str, Any]:
    """Sample decision event payload for E2E testing."""
    from datetime import datetime
    from uuid import uuid7

    return {
        "event_version": "1.0",
        "transaction_id": "e2e_txn_001",
        "occurred_at": datetime.now(UTC).isoformat(),
        "produced_at": datetime.now(UTC).isoformat(),
        "evaluation_type": "AUTH",
        "transaction": {
            "card_id": "tok_visa_e2e_test",
            "card_last4": "4242",
            "card_network": "VISA",
            "amount": "150.00",
            "currency": "USD",
            "country": "US",
            "merchant_id": "merch_e2e_001",
            "mcc": "5411",
        },
        "decision": "DECLINE",
        "decision_reason": "RULE_MATCH",
        "matched_rules": [
            {
                "rule_id": str(uuid7()),
                "rule_version": 1,
                "priority": 100,
                "rule_name": "E2E High Value Rule",
            }
        ],
    }


@pytest.fixture
async def e2e_sample_transaction_id(
    http_client: httpx.AsyncClient, e2e_sample_decision_event: dict
):
    """Create a sample transaction and return its internal UUID for use in tests.

    Note: Returns the internal database UUID (id), not the string transaction_id.
    This is required for endpoints like /transactions/{id}/review that expect UUIDs.
    """
    from uuid import uuid7

    # Use unique transaction_id each time
    txn_id = f"e2e_txn_{uuid7()}"
    e2e_sample_decision_event["transaction_id"] = txn_id

    # Ingest a decision event to create a transaction
    response = await http_client.post(
        "/api/v1/decision-events",
        json=e2e_sample_decision_event,
    )
    if response.status_code in (200, 202):
        # Query transactions to get the internal UUID
        list_response = await http_client.get(
            "/api/v1/transactions",
            params={"transaction_id": txn_id, "page_size": 1},
        )
        if list_response.status_code == 200:
            transactions = list_response.json().get("items", [])
            if transactions and transactions[0].get("id"):
                return {"id": transactions[0]["id"], "transaction_id": txn_id}
    return None


@pytest.fixture
async def e2e_create_transaction(http_client: httpx.AsyncClient):
    """Helper fixture to create a transaction and return both IDs.

    Returns dict with:
    - id: internal database UUID
    - transaction_id: string transaction_id from the event
    """
    from datetime import datetime
    from uuid import uuid7

    async def _create(event_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        """Create a transaction with optional overrides."""
        txn_id = f"e2e_txn_{uuid7()}"
        event = {
            "event_version": "1.0",
            "transaction_id": txn_id,
            "occurred_at": datetime.now(UTC).isoformat(),
            "produced_at": datetime.now(UTC).isoformat(),
            "evaluation_type": "AUTH",
            "transaction": {
                "card_id": "tok_visa_e2e_test",
                "card_last4": "4242",
                "card_network": "VISA",
                "amount": "150.00",
                "currency": "USD",
                "country": "US",
                "merchant_id": "merch_e2e_001",
                "mcc": "5411",
            },
            "decision": "DECLINE",
            "decision_reason": "RULE_MATCH",
            "matched_rules": [
                {
                    "rule_id": str(uuid7()),
                    "rule_version": 1,
                    "priority": 100,
                    "rule_name": "E2E High Value Rule",
                }
            ],
        }
        if event_overrides:
            event.update(event_overrides)

        response = await http_client.post("/api/v1/decision-events", json=event)
        if response.status_code in (200, 202):
            # Query to get internal UUID
            list_response = await http_client.get(
                "/api/v1/transactions",
                params={"transaction_id": txn_id, "page_size": 1},
            )
            if list_response.status_code == 200:
                transactions = list_response.json().get("items", [])
                if transactions and transactions[0].get("id"):
                    return {"id": transactions[0]["id"], "transaction_id": txn_id}
        return None

    return _create


@pytest.fixture
def e2e_fraud_analyst_token():
    """E2E test token for fraud analyst role."""
    return "e2e_fraud_analyst_token"


@pytest.fixture
def e2e_fraud_supervisor_token():
    """E2E test token for fraud supervisor role."""
    return "e2e_fraud_supervisor_token"
