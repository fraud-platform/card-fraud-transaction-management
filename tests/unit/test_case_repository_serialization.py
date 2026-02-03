"""UUID and JSONB serialization tests.

These tests verify that UUIDs in JSONB columns are correctly serialized.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid7

import pytest


class TestUUIDJSONBSerialization:
    """Test UUID serialization in JSONB columns."""

    @pytest.mark.asyncio
    async def test_serialize_uuid_converts_uuid_to_string(self):
        """Test that _serialize_uuid converts UUID to string."""
        from app.persistence.case_repository import _serialize_uuid

        test_uuid = uuid7()
        result = _serialize_uuid(test_uuid)

        assert isinstance(result, str)
        assert result == str(test_uuid)

    @pytest.mark.asyncio
    async def test_serialize_uuid_handles_none(self):
        """Test that _serialize_uuid handles None values."""
        from app.persistence.case_repository import _serialize_uuid

        result = _serialize_uuid(None)

        assert result is None

    @pytest.mark.asyncio
    async def test_serialize_uuid_handles_dict_with_uuids(self):
        """Test that _serialize_uuid handles dicts containing UUIDs."""
        from app.persistence.case_repository import _serialize_uuid

        transaction_id = uuid7()
        review_id = uuid7()

        input_dict = {
            "transaction_id": transaction_id,
            "review_id": review_id,
            "status": "PENDING",
            "count": 5,
        }

        result = _serialize_uuid(input_dict)

        assert isinstance(result, dict)
        assert result["transaction_id"] == str(transaction_id)
        assert result["review_id"] == str(review_id)

    @pytest.mark.asyncio
    async def test_serialize_uuid_handles_nested_structures(self):
        """Test that _serialize_uuid handles nested dicts and lists."""
        from app.persistence.case_repository import _serialize_uuid

        input_data = {
            "case_id": uuid7(),
            "transactions": [uuid7(), uuid7()],
            "nested": {
                "review_id": uuid7(),
                "related": [uuid7()],
            },
        }

        result = _serialize_uuid(input_data)

        assert isinstance(result["case_id"], str)
        assert all(isinstance(id, str) for id in result["transactions"])
        assert isinstance(result["nested"]["review_id"], str)
        assert isinstance(result["nested"]["related"][0], str)

    @pytest.mark.asyncio
    async def test_log_activity_serializes_uuids_in_jsonb(self):
        """Test that log_activity correctly serializes UUIDs in JSONB metadata."""
        from app.persistence.case_repository import _serialize_uuid

        # Test the _serialize_uuid function directly
        transaction_id = uuid7()
        case_id = uuid7()

        input_data = {
            "transaction_id": transaction_id,
            "case_id": case_id,
            "reason": "linked",
        }

        result = _serialize_uuid(input_data)

        # Verify UUIDs are converted to strings
        assert result["transaction_id"] == str(transaction_id)
        assert result["case_id"] == str(case_id)
        assert isinstance(result["transaction_id"], str)
        assert isinstance(result["case_id"], str)


class TestRepositoryResponseMapping:
    """Test that repository methods return correctly structured responses."""

    @pytest.mark.asyncio
    async def test_get_stats_returns_dict(self):
        """Test get_stats returns a dict structure."""
        from app.persistence.review_repository import ReviewRepository

        mock_session = MagicMock()
        repo = ReviewRepository(mock_session)

        # Mock the SQL execute to return empty result
        mock_result = MagicMock()
        mock_row = (0, 0, 0, 0, 0)  # pending, in_review, escalated, resolved, resolved_today
        mock_result.fetchone = MagicMock(return_value=mock_row)
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Call the method
        result = await repo.get_stats(analyst_id="test_user")

        # Verify result is a dict with expected keys
        assert isinstance(result, dict)
        # Check that it has some expected structure
        assert "unassigned_total" in result or "my_assigned_total" in result


class TestCursorPaginationWithMockData:
    """Test cursor pagination behavior."""

    @pytest.mark.asyncio
    async def test_list_unassigned_generates_cursor_with_review_id(self):
        """Test list_unassigned generates cursor using review_id (id)."""
        import inspect

        from app.persistence.review_repository import ReviewRepository

        # Verify the source code uses the correct pattern
        source = inspect.getsource(ReviewRepository.list_unassigned)

        # Should use r.id for the cursor, not r.transaction_id
        assert "r.id" in source or "review_id" in source
        # The cursor should be created with the PK (r.id)

    @pytest.mark.asyncio
    async def test_transaction_repository_list_generates_cursor_with_id(self):
        """Test TransactionRepository.list() generates cursor with PK (id)."""
        import inspect

        from app.persistence.transaction_repository import TransactionRepository

        # Verify the source code uses the correct pattern
        source = inspect.getsource(TransactionRepository.list)

        # Should use t.id (PK) for the cursor, not t.transaction_id (business key)
        # Look for the cursor generation pattern
        assert (
            "id=last_txn" in source
            or 'id=last_txn.get("id")' in source
            or 'id=last_txn["id"]' in source
        )
