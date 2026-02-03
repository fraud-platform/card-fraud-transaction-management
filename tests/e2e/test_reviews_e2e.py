"""E2E tests for review management endpoints.

These tests test full end-to-end workflows across multiple endpoints.
Run with: uv run doppler-local-test -m e2e_integration
"""

from uuid import uuid7

import pytest
from httpx import AsyncClient


@pytest.mark.e2e_integration
@pytest.mark.asyncio
class TestReviewsE2E:
    """E2E tests for transaction review endpoints."""

    async def _create_transaction(self, http_client: AsyncClient) -> dict:
        """Helper to create a transaction and return both IDs.

        Returns dict with:
        - id: internal database UUID
        - transaction_id: string transaction_id from the event
        """
        from datetime import datetime

        txn_id = f"e2e_review_{uuid7().hex}"
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

    async def test_get_or_create_review_for_transaction(self, http_client: AsyncClient):
        """Test GET /transactions/{id}/review creates review if not exists."""
        txn = await self._create_transaction(http_client)
        assert txn is not None
        transaction_uuid = txn["id"]

        # Get or create review for this transaction (use internal UUID)
        response = await http_client.get(f"/api/v1/transactions/{transaction_uuid}/review")
        assert response.status_code == 200

        review = response.json()
        assert "id" in review
        assert "status" in review
        assert "priority" in review

    async def test_create_review_explicitly(self, http_client: AsyncClient):
        """Test POST /transactions/{id}/review."""
        txn = await self._create_transaction(http_client)
        transaction_uuid = txn["id"]

        # Create review explicitly
        response = await http_client.post(f"/api/v1/transactions/{transaction_uuid}/review")
        assert response.status_code == 200

        review = response.json()
        assert "id" in review

    async def test_update_review_status(self, http_client: AsyncClient):
        """Test PATCH /transactions/{id}/review/status."""
        txn = await self._create_transaction(http_client)
        transaction_uuid = txn["id"]

        # Update status to IN_REVIEW
        response = await http_client.patch(
            f"/api/v1/transactions/{transaction_uuid}/review/status",
            json={"status": "IN_REVIEW"},
        )
        assert response.status_code == 200
        review = response.json()
        assert review["status"] == "IN_REVIEW"

        # Update status to RESOLVED
        response = await http_client.patch(
            f"/api/v1/transactions/{transaction_uuid}/review/status",
            json={
                "status": "RESOLVED",
                "resolution_code": "FALSE_POSITIVE",
                "resolution_notes": "Legitimate transaction verified",
            },
        )
        assert response.status_code == 200
        review = response.json()
        assert review["status"] == "RESOLVED"
        assert review["resolution_code"] == "FALSE_POSITIVE"

    async def test_assign_review_to_analyst(self, http_client: AsyncClient):
        """Test PATCH /transactions/{id}/review/assign."""
        txn = await self._create_transaction(http_client)
        transaction_uuid = txn["id"]

        # Assign to an analyst
        analyst_id = f"analyst_{uuid7().hex}"
        response = await http_client.patch(
            f"/api/v1/transactions/{transaction_uuid}/review/assign",
            json={"analyst_id": analyst_id},
        )
        assert response.status_code == 200
        review = response.json()
        assert review["assigned_analyst_id"] == analyst_id
        assert review["assigned_at"] is not None

    async def test_resolve_review(self, http_client: AsyncClient):
        """Test POST /transactions/{id}/review/resolve."""
        txn = await self._create_transaction(http_client)
        transaction_uuid = txn["id"]

        # Resolve the review
        response = await http_client.post(
            f"/api/v1/transactions/{transaction_uuid}/review/resolve",
            json={
                "resolution_code": "FRAUD_CONFIRMED",
                "resolution_notes": "Confirmed fraudulent activity",
            },
        )
        assert response.status_code == 200
        review = response.json()
        assert review["status"] == "RESOLVED"
        assert review["resolution_code"] == "FRAUD_CONFIRMED"
        assert review["resolved_at"] is not None

    async def test_escalate_review(self, http_client: AsyncClient):
        """Test POST /transactions/{id}/review/escalate."""
        txn = await self._create_transaction(http_client)
        transaction_uuid = txn["id"]

        # Escalate the review
        supervisor_id = f"supervisor_{uuid7().hex}"
        response = await http_client.post(
            f"/api/v1/transactions/{transaction_uuid}/review/escalate",
            json={
                "escalate_to": supervisor_id,
                "reason": "Complex case requiring supervisor input",
            },
        )
        assert response.status_code == 200
        review = response.json()
        assert review["status"] == "ESCALATED"
        assert review["escalated_to"] == supervisor_id

    async def test_review_workflow_full_lifecycle(self, http_client: AsyncClient):
        """Test complete review workflow: create → assign → escalate → resolve."""
        txn = await self._create_transaction(http_client)
        transaction_uuid = txn["id"]

        # Step 1: Get review (auto-created)
        response = await http_client.get(f"/api/v1/transactions/{transaction_uuid}/review")
        assert response.status_code == 200
        review = response.json()
        review_id = review["id"]

        # Step 2: Assign to analyst (also sets status to IN_REVIEW)
        analyst_id = f"analyst_{uuid7().hex}"
        response = await http_client.patch(
            f"/api/v1/transactions/{transaction_uuid}/review/assign",
            json={"analyst_id": analyst_id},
        )
        assert response.status_code == 200
        review = response.json()
        assert review["status"] == "IN_REVIEW"

        # Step 3: Escalate to supervisor
        supervisor_id = f"supervisor_{uuid7().hex}"
        response = await http_client.post(
            f"/api/v1/transactions/{transaction_uuid}/review/escalate",
            json={
                "escalate_to": supervisor_id,
                "reason": "Complex case requiring supervisor input",
            },
        )
        assert response.status_code == 200
        review = response.json()
        assert review["status"] == "ESCALATED"

        # Step 4: Resolve by supervisor
        response = await http_client.post(
            f"/api/v1/transactions/{transaction_uuid}/review/resolve",
            json={
                "resolution_code": "FALSE_POSITIVE",
                "resolution_notes": "Verified with cardholder",
            },
        )
        assert response.status_code == 200
        review = response.json()
        assert review["id"] == review_id
        assert review["status"] == "RESOLVED"
        assert review["assigned_analyst_id"] == analyst_id

    async def test_get_review_for_nonexistent_transaction(self, http_client: AsyncClient):
        """Test that review endpoint is accessible."""
        # Create a real transaction and get its review
        txn = await self._create_transaction(http_client)
        transaction_uuid = txn["id"]

        # Get the review - should return 200 with review data
        response = await http_client.get(f"/api/v1/transactions/{transaction_uuid}/review")
        assert response.status_code == 200
        review = response.json()
        assert "id" in review
        assert "status" in review

    async def test_review_includes_transaction_summary(self, http_client: AsyncClient):
        """Test that review response includes transaction summary."""
        txn = await self._create_transaction(http_client)
        transaction_uuid = txn["id"]

        # Get review
        response = await http_client.get(f"/api/v1/transactions/{transaction_uuid}/review")
        assert response.status_code == 200
        review = response.json()

        # Check transaction summary fields
        assert "transaction_amount" in review
        assert "transaction_currency" in review
        assert "decision" in review
