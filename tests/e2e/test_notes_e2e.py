"""E2E tests for notes endpoints.

These tests test full end-to-end workflows across multiple endpoints.
Run with: uv run doppler-local-test -m e2e_integration
"""

from datetime import datetime
from uuid import uuid7

import pytest
from httpx import AsyncClient


@pytest.mark.e2e_integration
@pytest.mark.asyncio
class TestNotesE2E:
    """E2E tests for transaction notes endpoints."""

    async def _create_transaction(self, http_client: AsyncClient) -> dict:
        """Helper to create a transaction and return both IDs."""
        txn_id = f"e2e_notes_{uuid7()}"
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

    async def test_create_note(self, http_client: AsyncClient):
        """Test POST /transactions/{id}/notes."""
        txn = await self._create_transaction(http_client)
        transaction_uuid = txn["id"]

        # Create a note
        response = await http_client.post(
            f"/api/v1/transactions/{transaction_uuid}/notes",
            json={
                "note_type": "GENERAL",
                "note_content": "Customer confirmed this transaction was legitimate.",
                "is_private": False,
            },
        )
        assert response.status_code == 201
        note = response.json()
        assert note["transaction_id"] == transaction_uuid
        assert note["note_type"] == "GENERAL"
        assert "id" in note

    async def test_list_notes(self, http_client: AsyncClient):
        """Test GET /transactions/{id}/notes."""
        txn = await self._create_transaction(http_client)
        transaction_uuid = txn["id"]

        # Create multiple notes
        for i in range(3):
            await http_client.post(
                f"/api/v1/transactions/{transaction_uuid}/notes",
                json={
                    "note_type": "GENERAL",
                    "note_content": f"Note number {i + 1}",
                    "is_private": False,
                },
            )

        # List notes
        response = await http_client.get(f"/api/v1/transactions/{transaction_uuid}/notes")
        assert response.status_code == 200
        notes_list = response.json()
        assert "items" in notes_list
        assert "total" in notes_list
        assert len(notes_list["items"]) == 3

    async def test_get_specific_note(self, http_client: AsyncClient):
        """Test GET /transactions/{id}/notes/{note_id}."""
        txn = await self._create_transaction(http_client)
        transaction_uuid = txn["id"]

        # Create a note
        create_response = await http_client.post(
            f"/api/v1/transactions/{transaction_uuid}/notes",
            json={
                "note_type": "INITIAL_REVIEW",
                "note_content": "Initial review notes go here",
                "is_private": False,
            },
        )
        note = create_response.json()
        note_id = note["id"]

        # Get specific note
        response = await http_client.get(
            f"/api/v1/transactions/{transaction_uuid}/notes/{note_id}",
        )
        assert response.status_code == 200
        retrieved_note = response.json()
        assert retrieved_note["id"] == note_id
        assert retrieved_note["note_type"] == "INITIAL_REVIEW"

    async def test_update_note(self, http_client: AsyncClient):
        """Test PATCH /transactions/{id}/notes/{note_id}."""
        txn = await self._create_transaction(http_client)
        transaction_uuid = txn["id"]

        # Create a note
        create_response = await http_client.post(
            f"/api/v1/transactions/{transaction_uuid}/notes",
            json={
                "note_type": "GENERAL",
                "note_content": "Original content",
                "is_private": False,
            },
        )
        note = create_response.json()
        note_id = note["id"]

        # Update the note
        response = await http_client.patch(
            f"/api/v1/transactions/{transaction_uuid}/notes/{note_id}",
            json={
                "note_content": "Updated content with more details",
                "note_type": "RESOLUTION",
                "is_private": True,
            },
        )
        assert response.status_code == 200
        updated_note = response.json()
        assert updated_note["id"] == note_id
        assert updated_note["note_content"] == "Updated content with more details"
        assert updated_note["note_type"] == "RESOLUTION"

    async def test_delete_note(self, http_client: AsyncClient):
        """Test DELETE /transactions/{id}/notes/{note_id}."""
        txn = await self._create_transaction(http_client)
        transaction_uuid = txn["id"]

        # Create a note
        create_response = await http_client.post(
            f"/api/v1/transactions/{transaction_uuid}/notes",
            json={
                "note_type": "GENERAL",
                "note_content": "This note will be deleted",
                "is_private": False,
            },
        )
        note = create_response.json()
        note_id = note["id"]

        # Delete the note
        response = await http_client.delete(
            f"/api/v1/transactions/{transaction_uuid}/notes/{note_id}",
        )
        assert response.status_code == 204

        # Verify note is deleted
        response = await http_client.get(
            f"/api/v1/transactions/{transaction_uuid}/notes/{note_id}",
        )
        assert response.status_code == 404

    async def test_private_note_visibility(self, http_client: AsyncClient):
        """Test that private notes are properly marked."""
        txn = await self._create_transaction(http_client)
        transaction_uuid = txn["id"]

        # Create a private note
        response = await http_client.post(
            f"/api/v1/transactions/{transaction_uuid}/notes",
            json={
                "note_type": "INTERNAL_REVIEW",
                "note_content": "Sensitive internal notes",
                "is_private": True,
            },
        )
        assert response.status_code == 201
        note = response.json()
        assert note["is_private"] is True

    async def test_note_types(self, http_client: AsyncClient):
        """Test creating notes with different note types."""
        txn = await self._create_transaction(http_client)
        transaction_uuid = txn["id"]

        note_types = [
            "GENERAL",
            "INITIAL_REVIEW",
            "CUSTOMER_CONTACT",
            "MERCHANT_CONTACT",
            "BANK_CONTACT",
            "FRAUD_CONFIRMED",
            "FALSE_POSITIVE",
            "ESCALATION",
            "RESOLUTION",
            "LEGAL_HOLD",
            "INTERNAL_REVIEW",
        ]

        for note_type in note_types:
            response = await http_client.post(
                f"/api/v1/transactions/{transaction_uuid}/notes",
                json={
                    "note_type": note_type,
                    "note_content": f"Test note for {note_type}",
                    "is_private": False,
                },
            )
            assert response.status_code == 201
            note = response.json()
            assert note["note_type"] == note_type

    async def test_create_note_validation_errors(self, http_client: AsyncClient):
        """Test that creating notes with invalid data returns 422."""
        txn = await self._create_transaction(http_client)
        transaction_uuid = txn["id"]

        # Missing note_content
        response = await http_client.post(
            f"/api/v1/transactions/{transaction_uuid}/notes",
            json={"note_type": "GENERAL"},
        )
        assert response.status_code == 422

        # Empty note_content
        response = await http_client.post(
            f"/api/v1/transactions/{transaction_uuid}/notes",
            json={"note_type": "GENERAL", "note_content": ""},
        )
        assert response.status_code == 422

    async def test_get_nonexistent_note(self, http_client: AsyncClient):
        """Test getting a nonexistent note returns 404."""
        txn = await self._create_transaction(http_client)
        transaction_uuid = txn["id"]

        fake_note_id = uuid7()
        response = await http_client.get(
            f"/api/v1/transactions/{transaction_uuid}/notes/{fake_note_id}",
        )
        assert response.status_code == 404
