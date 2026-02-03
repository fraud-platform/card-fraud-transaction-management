"""E2E tests for bulk operations endpoints.

These tests test full end-to-end workflows across multiple endpoints.
Run with: uv run doppler-local-test -m e2e_integration
"""

from datetime import datetime
from uuid import uuid7

import pytest
from httpx import AsyncClient


@pytest.mark.e2e_integration
@pytest.mark.asyncio
class TestBulkE2E:
    """E2E tests for bulk operations endpoints."""

    async def _create_transaction(self, http_client: AsyncClient) -> dict:
        """Helper to create a transaction and return both IDs."""
        txn_id = f"e2e_bulk_{uuid7()}"
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

    async def test_bulk_assign(self, http_client: AsyncClient):
        """Test POST /bulk/assign."""
        # Create multiple transactions
        transaction_ids = []
        for _ in range(3):
            txn = await self._create_transaction(http_client)
            if txn:
                transaction_ids.append(str(txn["id"]))

        assert len(transaction_ids) == 3

        # Bulk assign to analyst
        analyst_id = f"analyst_{uuid7()}"
        response = await http_client.post(
            "/api/v1/bulk/assign",
            json={
                "transaction_ids": transaction_ids,
                "analyst_id": analyst_id,
            },
        )
        assert response.status_code == 200
        result = response.json()
        assert result["total_requested"] == 3
        assert result["successful"] == 3

    async def test_bulk_update_status(self, http_client: AsyncClient):
        """Test POST /bulk/status."""
        # Create multiple transactions
        transaction_ids = []
        for _ in range(3):
            txn = await self._create_transaction(http_client)
            if txn:
                transaction_ids.append(str(txn["id"]))

        # Bulk update status to IN_REVIEW
        response = await http_client.post(
            "/api/v1/bulk/status",
            json={
                "transaction_ids": transaction_ids,
                "status": "IN_REVIEW",
            },
        )
        assert response.status_code == 200
        result = response.json()
        assert result["total_requested"] == 3

    async def test_bulk_update_status_with_resolution(self, http_client: AsyncClient):
        """Test POST /bulk/status with resolution details."""
        # Create transactions
        transaction_ids = []
        for _ in range(2):
            txn = await self._create_transaction(http_client)
            if txn:
                transaction_ids.append(str(txn["id"]))

        # Bulk resolve
        response = await http_client.post(
            "/api/v1/bulk/status",
            json={
                "transaction_ids": transaction_ids,
                "status": "RESOLVED",
                "resolution_code": "FALSE_POSITIVE",
                "resolution_notes": "Batch resolved as false positives",
            },
        )
        assert response.status_code == 200

    async def test_bulk_create_case(self, http_client: AsyncClient):
        """Test POST /bulk/create-case."""
        # Create multiple transactions
        transaction_ids = []
        for _ in range(3):
            txn = await self._create_transaction(http_client)
            if txn:
                transaction_ids.append(str(txn["id"]))

        # Bulk create case
        response = await http_client.post(
            "/api/v1/bulk/create-case",
            json={
                "transaction_ids": transaction_ids,
                "case_type": "FRAUD_RING",
                "title": "Bulk fraud ring case",
                "description": "Multiple transactions from same fraud ring",
                "risk_level": "HIGH",
            },
        )
        assert response.status_code == 200
        result = response.json()
        assert "created_case_id" in result
        assert result["total_requested"] == 3

    async def test_bulk_operations_with_partial_failure(self, http_client: AsyncClient):
        """Test bulk operations with some invalid transaction IDs."""
        # Create one valid transaction
        txn = await self._create_transaction(http_client)

        # Mix valid and invalid IDs - convert UUIDs to strings for JSON serialization
        transaction_ids = [str(txn["id"]), str(uuid7()), str(uuid7())]

        # Bulk assign should succeed for valid ID, fail for invalid ones
        response = await http_client.post(
            "/api/v1/bulk/assign",
            json={
                "transaction_ids": transaction_ids,
                "analyst_id": f"analyst_{uuid7()}",
            },
        )
        assert response.status_code == 200
        result = response.json()
        assert result["total_requested"] == 3
        assert result["successful"] >= 1

    async def test_bulk_assign_validation(self, http_client: AsyncClient):
        """Test that bulk assign validates input."""
        # Empty transaction list
        response = await http_client.post(
            "/api/v1/bulk/assign",
            json={
                "transaction_ids": [],
                "analyst_id": "analyst_123",
            },
        )
        assert response.status_code == 422

    async def test_bulk_status_validation(self, http_client: AsyncClient):
        """Test that bulk status update validates input."""
        # Empty transaction list
        response = await http_client.post(
            "/api/v1/bulk/status",
            json={
                "transaction_ids": [],
                "status": "RESOLVED",
            },
        )
        assert response.status_code == 422

    async def test_bulk_create_case_validation(self, http_client: AsyncClient):
        """Test that bulk create case validates input."""
        # Missing required field
        response = await http_client.post(
            "/api/v1/bulk/create-case",
            json={
                "transaction_ids": [str(uuid7())],
                "case_type": "INVESTIGATION",
            },
        )
        assert response.status_code == 422

    async def test_bulk_max_transaction_limit(self, http_client: AsyncClient):
        """Test that bulk operations enforce max limit of 100 transactions."""
        # Try to bulk assign 101 transaction IDs (should fail validation)
        transaction_ids = [str(uuid7()) for _ in range(101)]
        response = await http_client.post(
            "/api/v1/bulk/assign",
            json={
                "transaction_ids": transaction_ids,
                "analyst_id": "analyst_123",
            },
        )
        assert response.status_code == 422

    async def test_bulk_results_structure(self, http_client: AsyncClient):
        """Test that bulk operation results have expected structure."""
        # Create a transaction
        txn = await self._create_transaction(http_client)

        # Bulk assign
        response = await http_client.post(
            "/api/v1/bulk/assign",
            json={
                "transaction_ids": [str(txn["id"])],
                "analyst_id": f"analyst_{uuid7()}",
            },
        )
        assert response.status_code == 200
        result = response.json()

        # Check response structure
        assert "total_requested" in result
        assert "successful" in result
        assert "failed" in result
        assert "results" in result

    async def test_bulk_workflow_full_lifecycle(self, http_client: AsyncClient):
        """Test complete bulk workflow: create transactions → bulk assign → bulk resolve
        → bulk create case."""
        # Step 1: Create multiple transactions
        transaction_ids = []
        for _ in range(5):
            txn = await self._create_transaction(http_client)
            if txn:
                transaction_ids.append(txn["id"])

        # Step 2: Bulk assign
        analyst_id = f"analyst_{uuid7()}"
        response = await http_client.post(
            "/api/v1/bulk/assign",
            json={
                "transaction_ids": transaction_ids,
                "analyst_id": analyst_id,
            },
        )
        assert response.status_code == 200
        assert response.json()["successful"] == 5

        # Step 3: Bulk update status
        response = await http_client.post(
            "/api/v1/bulk/status",
            json={
                "transaction_ids": transaction_ids,
                "status": "IN_REVIEW",
            },
        )
        assert response.status_code == 200

        # Step 4: Bulk create case from these transactions
        response = await http_client.post(
            "/api/v1/bulk/create-case",
            json={
                "transaction_ids": transaction_ids,
                "case_type": "INVESTIGATION",
                "title": "Bulk case from workflow",
                "assigned_analyst_id": analyst_id,
            },
        )
        assert response.status_code == 200
        result = response.json()
        assert result["created_case_id"] is not None
