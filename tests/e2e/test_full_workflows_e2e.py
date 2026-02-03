"""E2E tests for complete end-to-end workflows.

These tests test full end-to-end workflows across multiple endpoints.
Run with: uv run doppler-local-test -m e2e_integration
"""

from datetime import datetime
from uuid import uuid7

import pytest
from httpx import AsyncClient


@pytest.mark.e2e_integration
@pytest.mark.asyncio
class TestFullWorkflowsE2E:
    """E2E tests for complete end-to-end workflows."""

    async def _create_transaction(self, http_client: AsyncClient) -> dict:
        """Helper to create a transaction and return both IDs."""
        txn_id = f"e2e_workflow_{uuid7()}"
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

    async def test_fraud_investigation_workflow(self, http_client: AsyncClient):
        """Test complete fraud investigation workflow.

        Workflow:
        1. Ingest suspicious transaction
        2. Get/create review
        3. Assign to analyst
        4. Add investigation notes
        5. Create case
        6. Resolve case
        7. Close review
        """
        # Step 1: Ingest suspicious transaction
        txn = await self._create_transaction(http_client)
        transaction_uuid = txn["id"]

        # Step 2: Get review
        response = await http_client.get(f"/api/v1/transactions/{transaction_uuid}/review")
        assert response.status_code == 200
        review = response.json()
        review_id = review["id"]

        # Step 3: Assign to analyst
        analyst_id = f"analyst_{uuid7()}"
        response = await http_client.patch(
            f"/api/v1/transactions/{transaction_uuid}/review/assign",
            json={"analyst_id": analyst_id},
        )
        assert response.status_code == 200

        # Step 4: Add investigation notes
        response = await http_client.post(
            f"/api/v1/transactions/{transaction_uuid}/notes",
            json={
                "note_type": "INITIAL_REVIEW",
                "note_content": "Transaction pattern matches known fraud indicators",
                "is_private": False,
            },
        )
        assert response.status_code == 201

        # Step 5: Create case
        response = await http_client.post(
            "/api/v1/cases",
            json={
                "case_type": "INVESTIGATION",
                "title": "Card compromise investigation",
                "description": "Customer confirmed unauthorized transaction",
                "transaction_ids": [transaction_uuid],
                "risk_level": "HIGH",
                "assigned_analyst_id": analyst_id,
            },
        )
        assert response.status_code == 201
        case = response.json()
        case_id = case["id"]

        # Step 6: Resolve case
        response = await http_client.post(
            f"/api/v1/cases/{case_id}/resolve",
            params={"resolution_summary": "Confirmed fraud - card blocked and reissued"},
        )
        assert response.status_code == 200

        # Step 7: Close review
        response = await http_client.patch(
            f"/api/v1/transactions/{transaction_uuid}/review/status",
            json={
                "status": "CLOSED",
                "resolution_code": "FRAUD_CONFIRMED",
                "resolution_notes": "Case resolved - fraud confirmed",
            },
        )
        assert response.status_code == 200
        final_review = response.json()
        assert final_review["status"] == "CLOSED"
        assert final_review["id"] == review_id

    async def test_multi_transaction_fraud_ring_workflow(self, http_client: AsyncClient):
        """Test workflow for investigating multiple transactions from fraud ring."""
        # Step 1: Create multiple related transactions
        transaction_ids = []
        for _ in range(5):
            txn = await self._create_transaction(http_client)
            if txn:
                transaction_ids.append(txn["id"])

        assert len(transaction_ids) == 5

        # Step 2: Create fraud ring case
        response = await http_client.post(
            "/api/v1/cases",
            json={
                "case_type": "FRAUD_RING",
                "title": "Organized fraud ring - multiple merchants",
                "description": "Pattern of coordinated fraudulent transactions",
                "transaction_ids": transaction_ids,
                "risk_level": "CRITICAL",
            },
        )
        assert response.status_code == 201
        case = response.json()
        case_id = case["id"]

        # Step 3: Verify case has all transactions
        response = await http_client.get(f"/api/v1/cases/{case_id}/transactions")
        assert response.status_code == 200
        case_transactions = response.json()
        assert len(case_transactions) == 5

        # Step 4: Add notes to the case
        for txn_uuid in transaction_ids[:2]:
            await http_client.post(
                f"/api/v1/transactions/{txn_uuid}/notes",
                json={
                    "note_type": "FRAUD_CONFIRMED",
                    "note_content": "Part of organized fraud ring pattern",
                    "is_private": False,
                },
            )

        # Step 5: Bulk resolve all reviews
        analyst_id = f"analyst_{uuid7()}"
        await http_client.post(
            "/api/v1/bulk/assign",
            json={"transaction_ids": transaction_ids, "analyst_id": analyst_id},
        )
        await http_client.post(
            "/api/v1/bulk/status",
            json={
                "transaction_ids": transaction_ids,
                "status": "RESOLVED",
                "resolution_code": "FRAUD_CONFIRMED",
                "resolution_notes": "Fraud ring case resolved",
            },
        )

        # Step 6: Resolve case
        await http_client.post(
            f"/api/v1/cases/{case_id}/resolve",
            params={"resolution_summary": "Fraud ring dismantled - accounts closed"},
        )

    async def test_worklist_claim_and_review_workflow(self, http_client: AsyncClient):
        """Test workflow: claim from worklist, review, and resolve."""
        # Create multiple pending transactions
        for _ in range(3):
            await self._create_transaction(http_client)

        # Step 2: Check worklist stats
        response = await http_client.get("/api/v1/worklist/stats")
        assert response.status_code == 200

        # Step 3: Claim first transaction
        response = await http_client.post(
            "/api/v1/worklist/claim",
            json={},
        )
        assert response.status_code == 200
        claimed = response.json()
        if claimed:
            claimed_transaction_uuid = claimed["transaction_id"]

            # Step 4: Review the transaction
            await http_client.patch(
                f"/api/v1/transactions/{claimed_transaction_uuid}/review/status",
                json={"status": "IN_REVIEW"},
            )

            # Add review note
            await http_client.post(
                f"/api/v1/transactions/{claimed_transaction_uuid}/notes",
                json={
                    "note_type": "GENERAL",
                    "note_content": "Reviewed transaction details",
                    "is_private": False,
                },
            )

            # Step 5: Resolve the review
            await http_client.post(
                f"/api/v1/transactions/{claimed_transaction_uuid}/review/resolve",
                json={
                    "resolution_code": "FALSE_POSITIVE",
                    "resolution_notes": "Verified with customer",
                },
            )

    async def test_escalation_workflow(self, http_client: AsyncClient):
        """Test workflow for escalating complex cases to supervisor."""
        # Create complex transaction
        txn = await self._create_transaction(http_client)
        transaction_uuid = txn["id"]

        # Step 1: Analyst starts review (assign sets status to IN_REVIEW)
        analyst_id = f"analyst_{uuid7()}"
        response = await http_client.patch(
            f"/api/v1/transactions/{transaction_uuid}/review/assign",
            json={"analyst_id": analyst_id},
        )
        assert response.status_code == 200

        # Step 2: Add note about complexity
        await http_client.post(
            f"/api/v1/transactions/{transaction_uuid}/notes",
            json={
                "note_type": "ESCALATION",
                "note_content": "High value transaction with unclear pattern - needs supervisor "
                "input",
                "is_private": False,
            },
        )

        # Step 3: Escalate to supervisor
        supervisor_id = f"supervisor_{uuid7()}"
        response = await http_client.post(
            f"/api/v1/transactions/{transaction_uuid}/review/escalate",
            json={
                "escalate_to": supervisor_id,
                "reason": "High value transaction requiring supervisor approval",
            },
        )
        assert response.status_code == 200
        escalated_review = response.json()
        assert escalated_review["status"] == "ESCALATED"

        # Step 4: Supervisor resolves the escalated review
        await http_client.post(
            f"/api/v1/transactions/{transaction_uuid}/review/resolve",
            json={
                "resolution_code": "FRAUD_CONFIRMED",
                "resolution_notes": "After escalation review, confirmed fraudulent activity",
            },
        )

    async def test_case_lifecycle_workflow(self, http_client: AsyncClient):
        """Test complete case lifecycle from open to close."""
        # Step 1: Create initial transaction
        txn = await self._create_transaction(http_client)
        transaction_uuid = txn["id"]

        # Step 2: Create case
        response = await http_client.post(
            "/api/v1/cases",
            json={
                "case_type": "DISPUTE",
                "title": "Customer dispute",
                "description": "Customer claims unauthorized transaction",
                "transaction_ids": [transaction_uuid],
            },
        )
        assert response.status_code == 201
        case = response.json()
        case_id = case["id"]

        # Step 3: Update case to IN_PROGRESS
        response = await http_client.patch(
            f"/api/v1/cases/{case_id}",
            json={"case_status": "IN_PROGRESS"},
        )
        assert response.status_code == 200

        # Step 4: Add more transactions to case
        txn2 = await self._create_transaction(http_client)
        if txn2:
            await http_client.post(
                f"/api/v1/cases/{case_id}/transactions",
                json={"transaction_id": txn2["id"]},
            )

        # Step 5: Resolve case
        response = await http_client.post(
            f"/api/v1/cases/{case_id}/resolve",
            params={"resolution_summary": "Dispute resolved in customer's favor"},
        )
        assert response.status_code == 200
        final_case = response.json()
        assert final_case["case_status"] == "RESOLVED"

    async def test_error_handling_workflow(self, http_client: AsyncClient):
        """Test workflow with various error conditions."""
        # Try to get non-existent transaction
        fake_id = uuid7()
        response = await http_client.get(f"/api/v1/transactions/{fake_id}")
        assert response.status_code == 404

        # Try to get non-existent case
        response = await http_client.get(f"/api/v1/cases/{fake_id}")
        assert response.status_code == 404

    async def test_pagination_workflow(self, http_client: AsyncClient):
        """Test pagination through large datasets."""
        # Create multiple transactions
        for _ in range(15):
            await self._create_transaction(http_client)

        # Test pagination on transactions list
        response = await http_client.get(
            "/api/v1/transactions",
            params={"page_size": 5},
        )
        assert response.status_code == 200
        page1 = response.json()
        assert page1["page_size"] == 5
        assert page1["has_more"] in [True, False]

        # Test worklist pagination
        response = await http_client.get(
            "/api/v1/worklist",
            params={"limit": 10},
        )
        assert response.status_code == 200
        worklist = response.json()
        assert worklist["page_size"] == 10
