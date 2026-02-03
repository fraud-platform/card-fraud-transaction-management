"""E2E tests for case management endpoints.

These tests test full end-to-end workflows across multiple endpoints.
Run with: uv run doppler-local-test -m e2e_integration
"""

from datetime import datetime
from uuid import uuid7

import pytest
from httpx import AsyncClient


@pytest.mark.e2e_integration
@pytest.mark.asyncio
class TestCasesE2E:
    """E2E tests for case management endpoints."""

    async def _create_transaction(self, http_client: AsyncClient) -> dict:
        """Helper to create a transaction and return both IDs."""
        txn_id = f"e2e_case_{uuid7()}"
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

    async def test_create_case(self, http_client: AsyncClient):
        """Test POST /cases."""
        # Create a transaction first
        txn = await self._create_transaction(http_client)
        transaction_uuid = txn["id"]

        # Create a case
        response = await http_client.post(
            "/api/v1/cases",
            json={
                "case_type": "INVESTIGATION",
                "title": "Suspicious pattern investigation",
                "description": "Multiple transactions from same IP",
                "transaction_ids": [transaction_uuid],
                "risk_level": "HIGH",
            },
        )
        assert response.status_code == 201
        case = response.json()
        assert "id" in case
        assert "case_number" in case
        assert case["case_type"] == "INVESTIGATION"
        assert case["total_transaction_count"] == 1

    async def test_list_cases(self, http_client: AsyncClient):
        """Test GET /cases."""
        # Create a transaction and case
        txn = await self._create_transaction(http_client)
        transaction_uuid = txn["id"]

        await http_client.post(
            "/api/v1/cases",
            json={
                "case_type": "DISPUTE",
                "title": "Customer dispute",
                "transaction_ids": [transaction_uuid],
            },
        )

        # List cases
        response = await http_client.get("/api/v1/cases")
        assert response.status_code == 200
        cases_list = response.json()
        assert "items" in cases_list
        assert "total" in cases_list

    async def test_list_cases_with_filters(self, http_client: AsyncClient):
        """Test GET /cases with filters."""
        txn = await self._create_transaction(http_client)
        transaction_uuid = txn["id"]

        # Create a case with specific status
        await http_client.post(
            "/api/v1/cases",
            json={
                "case_type": "FRAUD_RING",
                "title": "Fraud ring investigation",
                "transaction_ids": [transaction_uuid],
                "risk_level": "CRITICAL",
            },
        )

        # Filter by case_type
        response = await http_client.get(
            "/api/v1/cases",
            params={"case_type": "FRAUD_RING"},
        )
        assert response.status_code == 200
        cases_list = response.json()
        assert len(cases_list["items"]) >= 1

        # Filter by risk_level
        response = await http_client.get(
            "/api/v1/cases",
            params={"risk_level": "CRITICAL"},
        )
        assert response.status_code == 200

    async def test_get_case_by_id(self, http_client: AsyncClient):
        """Test GET /cases/{id}."""
        txn = await self._create_transaction(http_client)
        transaction_uuid = txn["id"]

        # Create a case
        create_response = await http_client.post(
            "/api/v1/cases",
            json={
                "case_type": "CHARGEBACK",
                "title": "Chargeback case",
                "transaction_ids": [transaction_uuid],
            },
        )
        case = create_response.json()
        case_id = case["id"]

        # Get case by ID
        response = await http_client.get(f"/api/v1/cases/{case_id}")
        assert response.status_code == 200
        retrieved_case = response.json()
        assert retrieved_case["id"] == case_id

    async def test_get_case_by_number(self, http_client: AsyncClient):
        """Test GET /cases/number/{case_number}."""
        txn = await self._create_transaction(http_client)
        transaction_uuid = txn["id"]

        # Create a case
        create_response = await http_client.post(
            "/api/v1/cases",
            json={
                "case_type": "ACCOUNT_TAKEOVER",
                "title": "Account takeover investigation",
                "transaction_ids": [transaction_uuid],
            },
        )
        case = create_response.json()
        case_number = case["case_number"]

        # Get case by number
        response = await http_client.get(f"/api/v1/cases/number/{case_number}")
        assert response.status_code == 200
        retrieved_case = response.json()
        assert retrieved_case["case_number"] == case_number

    async def test_update_case(self, http_client: AsyncClient):
        """Test PATCH /cases/{id}."""
        txn = await self._create_transaction(http_client)
        transaction_uuid = txn["id"]

        # Create a case
        create_response = await http_client.post(
            "/api/v1/cases",
            json={
                "case_type": "INVESTIGATION",
                "title": "Original title",
                "transaction_ids": [transaction_uuid],
            },
        )
        case = create_response.json()
        case_id = case["id"]

        # Update the case
        response = await http_client.patch(
            f"/api/v1/cases/{case_id}",
            json={
                "title": "Updated title",
                "description": "Updated description",
                "case_status": "IN_PROGRESS",
                "risk_level": "MEDIUM",
            },
        )
        assert response.status_code == 200
        updated_case = response.json()
        assert updated_case["id"] == case_id
        assert updated_case["title"] == "Updated title"
        assert updated_case["case_status"] == "IN_PROGRESS"

    async def test_add_transaction_to_case(self, http_client: AsyncClient):
        """Test POST /cases/{id}/transactions."""
        # Create two transactions
        txn1 = await self._create_transaction(http_client)
        txn2 = await self._create_transaction(http_client)

        # Create case with first transaction
        create_response = await http_client.post(
            "/api/v1/cases",
            json={
                "case_type": "INVESTIGATION",
                "title": "Test case",
                "transaction_ids": [txn1["id"]],
            },
        )
        case = create_response.json()
        case_id = case["id"]

        # Add second transaction to case
        response = await http_client.post(
            f"/api/v1/cases/{case_id}/transactions",
            json={"transaction_id": txn2["id"]},
        )
        assert response.status_code == 200
        updated_case = response.json()
        assert updated_case["total_transaction_count"] == 2

    async def test_remove_transaction_from_case(self, http_client: AsyncClient):
        """Test DELETE /cases/{id}/transactions/{transaction_id}."""
        txn = await self._create_transaction(http_client)
        transaction_uuid = txn["id"]

        # Create case with transaction
        create_response = await http_client.post(
            "/api/v1/cases",
            json={
                "case_type": "INVESTIGATION",
                "title": "Test case",
                "transaction_ids": [transaction_uuid],
            },
        )
        case = create_response.json()
        case_id = case["id"]

        # Remove transaction from case
        response = await http_client.delete(
            f"/api/v1/cases/{case_id}/transactions/{transaction_uuid}",
        )
        assert response.status_code == 200
        updated_case = response.json()
        assert updated_case["total_transaction_count"] == 0

    async def test_get_case_transactions(self, http_client: AsyncClient):
        """Test GET /cases/{id}/transactions."""
        txn = await self._create_transaction(http_client)
        transaction_uuid = txn["id"]

        # Create case with transaction
        create_response = await http_client.post(
            "/api/v1/cases",
            json={
                "case_type": "INVESTIGATION",
                "title": "Test case",
                "transaction_ids": [transaction_uuid],
            },
        )
        case = create_response.json()
        case_id = case["id"]

        # Get case transactions
        response = await http_client.get(f"/api/v1/cases/{case_id}/transactions")
        assert response.status_code == 200
        transactions = response.json()
        assert len(transactions) == 1

    async def test_get_case_activity(self, http_client: AsyncClient):
        """Test GET /cases/{id}/activity."""
        txn = await self._create_transaction(http_client)
        transaction_uuid = txn["id"]

        # Create case
        create_response = await http_client.post(
            "/api/v1/cases",
            json={
                "case_type": "INVESTIGATION",
                "title": "Test case",
                "transaction_ids": [transaction_uuid],
            },
        )
        case = create_response.json()
        case_id = case["id"]

        # Get case activity
        response = await http_client.get(f"/api/v1/cases/{case_id}/activity")
        assert response.status_code == 200
        activities = response.json()
        assert isinstance(activities, list)
        # There should be at least one activity (case creation)
        assert len(activities) >= 1

    async def test_resolve_case(self, http_client: AsyncClient):
        """Test POST /cases/{id}/resolve."""
        txn = await self._create_transaction(http_client)
        transaction_uuid = txn["id"]

        # Create case
        create_response = await http_client.post(
            "/api/v1/cases",
            json={
                "case_type": "INVESTIGATION",
                "title": "Test case",
                "transaction_ids": [transaction_uuid],
            },
        )
        case = create_response.json()
        case_id = case["id"]

        # Resolve the case
        response = await http_client.post(
            f"/api/v1/cases/{case_id}/resolve",
            params={"resolution_summary": "Investigation complete - confirmed fraud"},
        )
        assert response.status_code == 200
        resolved_case = response.json()
        assert resolved_case["case_status"] == "RESOLVED"
        assert resolved_case["resolution_summary"] == "Investigation complete - confirmed fraud"

    async def test_case_lifecycle(self, http_client: AsyncClient):
        """Test complete case lifecycle: create → update → add tx → resolve."""
        txn = await self._create_transaction(http_client)
        transaction_uuid = txn["id"]

        # Step 1: Create case
        create_response = await http_client.post(
            "/api/v1/cases",
            json={
                "case_type": "FRAUD_RING",
                "title": "Multi-transaction fraud ring",
                "description": "Related transactions from same fraud ring",
                "risk_level": "CRITICAL",
            },
        )
        case = create_response.json()
        case_id = case["id"]
        assert case["case_status"] == "OPEN"

        # Step 2: Add transaction
        await http_client.post(
            f"/api/v1/cases/{case_id}/transactions",
            json={"transaction_id": transaction_uuid},
        )

        # Step 3: Update to IN_PROGRESS
        response = await http_client.patch(
            f"/api/v1/cases/{case_id}",
            json={"case_status": "IN_PROGRESS"},
        )
        assert response.status_code == 200

        # Step 4: Resolve case
        response = await http_client.post(
            f"/api/v1/cases/{case_id}/resolve",
            params={"resolution_summary": "Fraud ring identified and blocked"},
        )
        assert response.status_code == 200
        final_case = response.json()
        assert final_case["case_status"] == "RESOLVED"

    async def test_get_nonexistent_case(self, http_client: AsyncClient):
        """Test getting nonexistent case returns 404."""
        fake_id = uuid7()
        response = await http_client.get(f"/api/v1/cases/{fake_id}")
        assert response.status_code == 404
