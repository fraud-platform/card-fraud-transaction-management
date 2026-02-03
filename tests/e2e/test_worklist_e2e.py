"""E2E tests for worklist endpoints.

These tests test full end-to-end workflows across multiple endpoints.
Run with: uv run doppler-local-test -m e2e_integration
"""

from datetime import datetime
from uuid import uuid7

import pytest
from httpx import AsyncClient


@pytest.mark.e2e_integration
@pytest.mark.asyncio
class TestWorklistE2E:
    """E2E tests for worklist endpoints."""

    async def _create_transaction(self, http_client: AsyncClient) -> dict:
        """Helper to create a transaction and return both IDs."""
        txn_id = f"e2e_worklist_{uuid7()}"
        event = {
            "event_version": "1.0",
            "transaction_id": txn_id,
            "occurred_at": datetime.utcnow().isoformat(),
            "produced_at": datetime.utcnow().isoformat(),
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

        response = await http_client.post("/api/v1/decision-events", json=event)
        if response.status_code in (200, 202):
            list_response = await http_client.get(
                "/api/v1/transactions",
                params={"transaction_id": txn_id, "page_size": 1},
            )
            if list_response.status_code == 200:
                transactions = list_response.json().get("items", [])
                if transactions and transactions[0].get("id"):
                    return {"id": transactions[0]["id"], "transaction_id": txn_id}
        return None

    async def test_get_worklist(self, http_client: AsyncClient):
        """Test GET /worklist."""
        await self._create_transaction(http_client)

        # Get worklist
        response = await http_client.get("/api/v1/worklist")
        assert response.status_code == 200
        worklist = response.json()
        assert "items" in worklist
        assert "total" in worklist
        assert isinstance(worklist["items"], list)

    async def test_get_worklist_with_filters(self, http_client: AsyncClient):
        """Test GET /worklist with status filter."""
        await self._create_transaction(http_client)

        # Filter by status
        response = await http_client.get(
            "/api/v1/worklist",
            params={"status": "PENDING"},
        )
        assert response.status_code == 200
        worklist = response.json()
        assert "items" in worklist

        # Filter by assigned_only
        response = await http_client.get(
            "/api/v1/worklist",
            params={"assigned_only": True},
        )
        assert response.status_code == 200

    async def test_get_worklist_with_priority_filter(self, http_client: AsyncClient):
        """Test GET /worklist with priority_filter."""
        await self._create_transaction(http_client)

        # Filter by priority (1=highest priority)
        response = await http_client.get(
            "/api/v1/worklist",
            params={"priority_filter": 2},
        )
        assert response.status_code == 200
        worklist = response.json()
        assert "items" in worklist

    async def test_get_worklist_with_risk_filter(self, http_client: AsyncClient):
        """Test GET /worklist with risk_level_filter."""
        await self._create_transaction(http_client)

        # Filter by risk level
        response = await http_client.get(
            "/api/v1/worklist",
            params={"risk_level_filter": "HIGH"},
        )
        assert response.status_code == 200

    async def test_get_worklist_stats(self, http_client: AsyncClient):
        """Test GET /worklist/stats."""
        await self._create_transaction(http_client)

        # Get stats
        response = await http_client.get("/api/v1/worklist/stats")
        assert response.status_code == 200
        stats = response.json()
        assert "unassigned_total" in stats
        assert "unassigned_by_priority" in stats
        assert "my_assigned_total" in stats
        assert "my_assigned_by_status" in stats

    async def test_get_unassigned(self, http_client: AsyncClient):
        """Test GET /worklist/unassigned."""
        await self._create_transaction(http_client)

        # Get unassigned items
        response = await http_client.get("/api/v1/worklist/unassigned")
        assert response.status_code == 200
        unassigned = response.json()
        assert "items" in unassigned
        assert "total" in unassigned
        assert isinstance(unassigned["items"], list)

    async def test_get_unassigned_with_filters(self, http_client: AsyncClient):
        """Test GET /worklist/unassigned with filters."""
        await self._create_transaction(http_client)

        # Filter by status
        response = await http_client.get(
            "/api/v1/worklist/unassigned",
            params={"status": "PENDING"},
        )
        assert response.status_code == 200

        # Filter by priority
        response = await http_client.get(
            "/api/v1/worklist/unassigned",
            params={"priority_filter": 2},
        )
        assert response.status_code == 200

        # Filter by risk level
        response = await http_client.get(
            "/api/v1/worklist/unassigned",
            params={"risk_level_filter": "HIGH"},
        )
        assert response.status_code == 200

    async def test_claim_next_transaction(self, http_client: AsyncClient):
        """Test POST /worklist/claim."""
        await self._create_transaction(http_client)

        # Claim next unassigned transaction
        response = await http_client.post(
            "/api/v1/worklist/claim",
            json={},
        )
        assert response.status_code == 200
        claimed = response.json()
        if claimed:  # If there was something to claim
            assert claimed["assigned_analyst_id"] == "test_user_e2e"
            assert claimed["assigned_at"] is not None

    async def test_claim_with_priority_filter(self, http_client: AsyncClient):
        """Test POST /worklist/claim with priority_filter."""
        await self._create_transaction(http_client)

        # Claim high priority item only (created transaction has priority 3, so no match)
        response = await http_client.post(
            "/api/v1/worklist/claim",
            json={"priority_filter": 1},
        )
        # Should return 404 since no priority 1 items exist
        assert response.status_code == 404

    async def test_claim_with_risk_filter(self, http_client: AsyncClient):
        """Test POST /worklist/claim with risk_level_filter."""
        await self._create_transaction(http_client)

        # Claim high-risk item only (created transaction has NULL/LOW risk, so no match)
        response = await http_client.post(
            "/api/v1/worklist/claim",
            json={"risk_level_filter": "CRITICAL"},
        )
        # Should return 404 since no CRITICAL risk items exist
        assert response.status_code == 404

    async def test_worklist_item_structure(self, http_client: AsyncClient):
        """Test that worklist items have all required fields."""
        await self._create_transaction(http_client)

        # Get worklist
        response = await http_client.get("/api/v1/worklist")
        worklist = response.json()

        if worklist["items"]:
            item = worklist["items"][0]
            required_fields = [
                "review_id",
                "transaction_id",
                "status",
                "priority",
                "card_id",
                "transaction_amount",
                "transaction_currency",
                "decision",
                "created_at",
            ]
            for field in required_fields:
                assert field in item

    async def test_claim_workflow(self, http_client: AsyncClient):
        """Test complete claim workflow: claim → verify in worklist → update status."""
        await self._create_transaction(http_client)

        # Step 1: Claim next transaction
        claim_response = await http_client.post(
            "/api/v1/worklist/claim",
            json={},
        )
        # Should successfully claim (200) or return 404 if nothing available
        assert claim_response.status_code in [200, 404]
        if claim_response.status_code == 200:
            claimed = claim_response.json()
            if claimed:
                transaction_id = claimed["transaction_id"]

                # Step 2: Verify it appears in assigned worklist
                response = await http_client.get(
                    "/api/v1/worklist",
                    params={"assigned_only": True},
                )
                assert response.status_code == 200

                # Step 3: Update status to RESOLVED (valid transition from IN_REVIEW)
                response = await http_client.post(
                    f"/api/v1/transactions/{transaction_id}/review/resolve",
                    json={
                        "resolution_code": "FALSE_POSITIVE",
                        "resolution_notes": "Verified as legitimate",
                    },
                )
                assert response.status_code == 200
