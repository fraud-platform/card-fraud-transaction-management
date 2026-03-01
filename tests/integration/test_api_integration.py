"""Integration tests for API endpoints.

These tests require:
- Doppler secrets configured (uv run doppler-local-test)
- Local Docker infrastructure running (uv run infra-local-up)

Run with:
    uv run doppler-local-test -m integration
    uv run doppler-test -m integration
"""

from datetime import datetime
from uuid import uuid7

import httpx
import pytest


@pytest.mark.asyncio
class TestDecisionEventsIntegration:
    """Integration tests for decision events ingestion."""

    async def test_ingest_valid_decision_event(self, client_app):
        """Test ingesting a valid decision event."""
        transport = httpx.ASGITransport(app=client_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/decision-events",
                json={
                    "transaction_id": f"txn_integration_{uuid7().hex[:8]}",
                    "occurred_at": datetime.utcnow().isoformat() + "Z",
                    "produced_at": datetime.utcnow().isoformat() + "Z",
                    "evaluation_type": "AUTH",
                    "transaction": {
                        "card_id": "tok_visa_test",
                        "card_last4": "4242",
                        "card_network": "VISA",
                        "amount": "100.00",
                        "currency": "USD",
                        "country": "US",
                        "merchant_id": "merchant_001",
                        "mcc": "5411",
                    },
                    "decision": "APPROVE",
                    "decision_reason": "DEFAULT_ALLOW",
                },
                headers={"X-Trace-ID": "test-trace-123"},
            )
            assert response.status_code in [200, 202, 409], (
                f"Unexpected status: {response.status_code}"
            )

    async def test_ingest_event_with_matched_rules(self, client_app):
        """Test ingesting event with matched rules."""
        transaction_id = f"txn_rules_{uuid7().hex[:8]}"
        transport = httpx.ASGITransport(app=client_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/decision-events",
                json={
                    "transaction_id": transaction_id,
                    "occurred_at": datetime.utcnow().isoformat() + "Z",
                    "produced_at": datetime.utcnow().isoformat() + "Z",
                    "evaluation_type": "AUTH",
                    "transaction": {
                        "card_id": "tok_test_card",
                        "amount": "250.00",
                        "currency": "USD",
                        "country": "US",
                    },
                    "decision": "DECLINE",
                    "decision_reason": "RULE_MATCH",
                    "matched_rules": [
                        {
                            "rule_id": str(uuid7()),
                            "rule_version": 1,
                            "rule_name": "High Velocity Check",
                            "rule_type": "velocity",
                            "priority": 10,
                        }
                    ],
                },
            )
            assert response.status_code in [200, 202, 409]

    async def test_reject_pan_like_pattern(self, client_app):
        """Test that raw PAN patterns are rejected."""
        transport = httpx.ASGITransport(app=client_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/decision-events",
                json={
                    "transaction_id": f"txn_pan_test_{uuid7().hex[:8]}",
                    "occurred_at": datetime.utcnow().isoformat() + "Z",
                    "produced_at": datetime.utcnow().isoformat() + "Z",
                    "evaluation_type": "AUTH",
                    "transaction": {
                        "card_id": "4111111111111111",  # Raw PAN - should be rejected
                        "amount": "100.00",
                        "currency": "USD",
                        "country": "US",
                    },
                    "decision": "APPROVE",
                    "decision_reason": "DEFAULT_ALLOW",
                },
            )
            assert response.status_code == 422


@pytest.mark.asyncio
class TestTransactionQueriesIntegration:
    """Integration tests for transaction query endpoints."""

    async def test_list_transactions_empty(self, client_app):
        """Test listing transactions when empty."""
        transport = httpx.ASGITransport(app=client_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/transactions")
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert "total" in data
            assert "page_size" in data

    async def test_list_transactions_with_filters(self, client_app):
        """Test listing transactions with filters."""
        transport = httpx.ASGITransport(app=client_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/transactions",
                params={
                    "card_id": "tok_nonexistent",
                    "decision": "APPROVE",
                    "country": "US",
                    "page_size": 10,
                },
            )
            assert response.status_code == 200

    async def test_list_transactions_filter_by_ip_and_device_context(self, client_app):
        """Test listing transactions filtered by transaction_context IP and device fields."""
        transaction_id = str(uuid7())
        ip_address = "203.0.113.10"
        device_id = f"device_{uuid7().hex[:10]}"
        device_fingerprint_hash = f"fp_{uuid7().hex}"

        transport = httpx.ASGITransport(app=client_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            ingest_response = await client.post(
                "/api/v1/decision-events",
                json={
                    "transaction_id": transaction_id,
                    "occurred_at": datetime.utcnow().isoformat() + "Z",
                    "produced_at": datetime.utcnow().isoformat() + "Z",
                    "evaluation_type": "AUTH",
                    "transaction": {
                        "card_id": "tok_visa_test_ip_device",
                        "card_last4": "1234",
                        "card_network": "VISA",
                        "amount": "150.00",
                        "currency": "USD",
                        "country": "US",
                        "merchant_id": "merchant_ip_device_001",
                        "mcc": "5411",
                        "ip_address": ip_address,
                    },
                    "transaction_context": {
                        "device": {
                            "device_id": device_id,
                            "device_fingerprint_hash": device_fingerprint_hash,
                        }
                    },
                    "decision": "APPROVE",
                    "decision_reason": "DEFAULT_ALLOW",
                },
            )
            assert ingest_response.status_code in [200, 202, 409]

            by_ip = await client.get("/api/v1/transactions", params={"ip_address": ip_address})
            assert by_ip.status_code == 200
            by_ip_data = by_ip.json()
            assert len(by_ip_data["items"]) >= 1
            assert all(
                (item.get("transaction_context") or {}).get("ip_address") == ip_address
                for item in by_ip_data["items"]
            )

            by_device = await client.get("/api/v1/transactions", params={"device_id": device_id})
            assert by_device.status_code == 200
            by_device_data = by_device.json()
            assert len(by_device_data["items"]) >= 1
            assert all(
                ((item.get("transaction_context") or {}).get("device") or {}).get("device_id")
                == device_id
                for item in by_device_data["items"]
            )

            by_fingerprint = await client.get(
                "/api/v1/transactions",
                params={"device_fingerprint_hash": device_fingerprint_hash},
            )
            assert by_fingerprint.status_code == 200
            by_fingerprint_data = by_fingerprint.json()
            assert len(by_fingerprint_data["items"]) >= 1
            assert all(
                ((item.get("transaction_context") or {}).get("device") or {}).get(
                    "device_fingerprint_hash"
                )
                == device_fingerprint_hash
                for item in by_fingerprint_data["items"]
            )

    async def test_get_nonexistent_transaction(self, client_app):
        """Test getting a transaction that doesn't exist."""
        transport = httpx.ASGITransport(app=client_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/transactions/txn_nonexistent_12345")
            assert response.status_code == 404

    async def test_get_metrics_endpoint(self, client_app):
        """Test getting transaction metrics."""
        transport = httpx.ASGITransport(app=client_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/metrics")
            assert response.status_code == 200
            data = response.json()
            assert "total_transactions" in data


@pytest.mark.asyncio
class TestHealthEndpointsIntegration:
    """Integration tests for health check endpoints."""

    async def test_health_check(self, client_app):
        """Test health check endpoint."""
        transport = httpx.ASGITransport(app=client_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/health")
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"

    async def test_readiness_check(self, client_app):
        """Test readiness check endpoint."""
        transport = httpx.ASGITransport(app=client_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/health/ready")
            assert response.status_code == 200

    async def test_liveness_check(self, client_app):
        """Test liveness check endpoint."""
        transport = httpx.ASGITransport(app=client_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/health/live")
            assert response.status_code == 200
            assert response.json()["status"] == "alive"


@pytest.mark.asyncio
class TestAuthenticationIntegration:
    """Integration tests for authentication."""

    async def test_reject_unauthenticated_request(self, client_app_no_auth):
        """Test that unauthenticated requests are rejected."""
        transport = httpx.ASGITransport(app=client_app_no_auth)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/transactions")
            assert response.status_code in [401, 403]

    async def test_reject_invalid_token(self, client_app_no_auth):
        """Test that invalid tokens are rejected."""
        transport = httpx.ASGITransport(app=client_app_no_auth)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/transactions",
                headers={"Authorization": "Bearer invalid_token_here"},
            )
            assert response.status_code in [401, 403]
