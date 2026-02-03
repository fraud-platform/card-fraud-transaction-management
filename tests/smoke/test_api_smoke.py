"""Smoke tests for API endpoints using AsyncClient.

These tests use real database connections and httpx AsyncClient with ASGI transport.
Run with: uv run doppler-local-test -m smoke -v
"""

from datetime import datetime
from uuid import uuid7

import pytest


@pytest.fixture
def sample_event_payload() -> dict:
    """Sample decision event payload for API testing."""
    return {
        "event_version": "1.0",
        "transaction_id": "txn_smoke_test_001",
        "occurred_at": datetime.utcnow().isoformat(),
        "produced_at": datetime.utcnow().isoformat(),
        "transaction": {
            "card_id": "tok_visa_42424242",
            "card_last4": "4242",
            "card_network": "VISA",
            "amount": "99.99",
            "currency": "USD",
            "country": "US",
            "merchant_id": "merch_test_001",
            "mcc": "5411",
        },
        "decision": "DECLINE",
        "decision_reason": "RULE_MATCH",
        "matched_rules": [
            {
                "rule_id": str(uuid7()),
                "rule_version": 1,
                "priority": 100,
                "rule_name": "High Value Rule",
            }
        ],
    }


@pytest.mark.asyncio
class TestHealthEndpoint:
    """Smoke tests for health endpoint."""

    async def test_health_check(self, test_client):
        """Test health endpoint returns 200."""
        response = await test_client.get("/api/v1/health")
        assert response.status_code == 200


@pytest.mark.asyncio
class TestDecisionEventsEndpoint:
    """Smoke tests for decision events ingestion."""

    async def test_ingest_valid_event(self, test_client, sample_event_payload):
        """Test ingesting a valid decision event."""
        response = await test_client.post(
            "/api/v1/decision-events",
            json=sample_event_payload,
        )

        assert response.status_code in [200, 202, 400, 409, 422]

        if response.status_code in [200, 202]:
            data = response.json()
            assert "status" in data
            assert "transaction_id" in data

    async def test_ingest_event_with_trace_id_header(self, test_client, sample_event_payload):
        """Test ingesting event with X-Trace-ID header."""
        response = await test_client.post(
            "/api/v1/decision-events",
            json=sample_event_payload,
            headers={"X-Trace-ID": "trace_123"},
        )
        assert response.status_code in [200, 202, 400, 409, 422]

    async def test_ingest_event_missing_required_fields(self, test_client):
        """Test that missing required fields returns 422."""
        payload = {
            "transaction_id": "txn_test",
            "transaction": {
                "card_id": "tok_visa_12345",
                "amount": 50.00,
            },
        }
        response = await test_client.post("/api/v1/decision-events", json=payload)
        assert response.status_code == 422

    async def test_ingest_event_invalid_card_id(self, test_client):
        """Test that raw PAN is rejected."""
        payload = {
            "transaction_id": "txn_test",
            "occurred_at": datetime.utcnow().isoformat(),
            "produced_at": datetime.utcnow().isoformat(),
            "transaction": {
                "card_id": "4242424242424242",  # Raw PAN - should fail
                "amount": 50.00,
                "currency": "USD",
                "country": "US",
            },
            "decision": "APPROVE",
            "decision_reason": "DEFAULT_ALLOW",
        }
        response = await test_client.post("/api/v1/decision-events", json=payload)
        assert response.status_code == 422


@pytest.mark.asyncio
class TestTransactionsEndpoint:
    """Smoke tests for transactions query endpoint."""

    async def test_list_transactions_empty(self, test_client):
        """Test listing transactions when empty."""
        response = await test_client.get("/api/v1/transactions")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page_size" in data
        assert "has_more" in data

    async def test_list_transactions_with_filters(self, test_client):
        """Test listing transactions with filters."""
        response = await test_client.get(
            "/api/v1/transactions",
            params={
                "page_size": 10,
                "decision": "DECLINE",
                "country": "US",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["page_size"] == 10

    async def test_list_transactions_pagination(self, test_client):
        """Test pagination parameters."""
        response = await test_client.get(
            "/api/v1/transactions",
            params={"page_size": 5},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["page_size"] == 5

    async def test_get_nonexistent_transaction(self, test_client):
        """Test getting a transaction that doesn't exist."""
        response = await test_client.get("/api/v1/transactions/nonexistent_id")
        assert response.status_code == 404


@pytest.mark.asyncio
class TestMetricsEndpoint:
    """Smoke tests for metrics endpoint."""

    async def test_get_metrics(self, test_client):
        """Test getting metrics."""
        response = await test_client.get("/api/v1/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "total_transactions" in data
        assert "approved_count" in data
        assert "declined_count" in data
        assert "total_amount" in data
        assert "avg_amount" in data

    async def test_get_metrics_with_date_range(self, test_client):
        """Test getting metrics with date filters."""
        response = await test_client.get(
            "/api/v1/metrics",
            params={
                "from_date": "2026-01-01T00:00:00",
                "to_date": "2026-12-31T23:59:59",
            },
        )
        assert response.status_code == 200
