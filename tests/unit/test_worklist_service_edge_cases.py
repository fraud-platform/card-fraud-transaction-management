"""Edge case tests for empty results and error states.

These tests verify that repositories and services handle edge cases correctly.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid7

import pytest

from app.persistence.review_repository import ReviewRepository


class TestReviewRepositoryEdgeCases:
    """Test edge cases in ReviewRepository."""

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_when_not_found(self):
        """Test get_by_id returns None for non-existent review ID."""
        mock_session = MagicMock()
        repo = ReviewRepository(mock_session)

        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_id(uuid7())

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_transaction_id_returns_none_when_not_found(self):
        """Test get_by_transaction_id returns None for non-existent transaction."""
        mock_session = MagicMock()
        repo = ReviewRepository(mock_session)

        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_transaction_id(uuid7())

        assert result is None

    @pytest.mark.asyncio
    async def test_get_worklist_item_returns_none_when_not_found(self):
        """Test get_worklist_item returns None for non-existent review."""
        mock_session = MagicMock()
        repo = ReviewRepository(mock_session)

        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_worklist_item(uuid7())

        assert result is None

    @pytest.mark.asyncio
    async def test_list_unassigned_returns_empty_list_when_no_unassigned(self):
        """Test list_unassigned returns empty list when no unassigned reviews exist."""
        mock_session = MagicMock()
        repo = ReviewRepository(mock_session)

        # Mock count query returning 0
        mock_count_result = MagicMock()
        mock_count_result.scalar = MagicMock(return_value=0)

        # Mock data query returning empty list
        mock_list_result = MagicMock()
        mock_list_result.fetchall = MagicMock(return_value=[])

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_list_result])

        items, next_cursor, total = await repo.list_unassigned(limit=10)

        assert items == []
        assert next_cursor is None
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_unassigned_with_filter_that_matches_nothing(self):
        """Test list_unassigned with priority_filter that matches nothing."""
        mock_session = MagicMock()
        repo = ReviewRepository(mock_session)

        mock_count_result = MagicMock()
        mock_count_result.scalar = MagicMock(return_value=0)

        mock_list_result = MagicMock()
        mock_list_result.fetchall = MagicMock(return_value=[])

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_list_result])

        # Filter for priority 1 (highest) when no items exist
        items, next_cursor, total = await repo.list_unassigned(priority_filter=1, limit=10)

        assert items == []
        assert next_cursor is None
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_unassigned_with_risk_filter_that_matches_nothing(self):
        """Test list_unassigned with risk_level_filter that matches nothing."""
        mock_session = MagicMock()
        repo = ReviewRepository(mock_session)

        mock_count_result = MagicMock()
        mock_count_result.scalar = MagicMock(return_value=0)

        mock_list_result = MagicMock()
        mock_list_result.fetchall = MagicMock(return_value=[])

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_list_result])

        items, next_cursor, total = await repo.list_unassigned(
            risk_level_filter="CRITICAL", limit=10
        )

        assert items == []
        assert next_cursor is None
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_unassigned_with_invalid_cursor(self):
        """Test list_unassigned with invalid cursor returns empty list."""
        mock_session = MagicMock()
        repo = ReviewRepository(mock_session)

        # Invalid cursor (ReviewCursor.decode returns None)
        mock_count_result = MagicMock()
        mock_count_result.scalar = MagicMock(return_value=0)

        mock_list_result = MagicMock()
        mock_list_result.fetchall = MagicMock(return_value=[])

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_list_result])

        # Invalid cursor should be handled gracefully
        items, next_cursor, total = await repo.list_unassigned(cursor="invalid_cursor", limit=10)

        # Should not raise, just return empty
        assert isinstance(items, list)
        assert total == 0


class TestRepositoryPaginationEdgeCases:
    """Test pagination edge cases."""

    @pytest.mark.asyncio
    async def test_list_unassigned_with_limit_zero(self):
        """Test list_unassigned with limit=0 returns empty list."""
        mock_session = MagicMock()
        repo = ReviewRepository(mock_session)

        mock_count_result = MagicMock()
        mock_count_result.scalar = MagicMock(return_value=5)

        mock_list_result = MagicMock()
        mock_list_result.fetchall = MagicMock(return_value=[])

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_list_result])

        items, next_cursor, total = await repo.list_unassigned(limit=0)

        assert items == []
        assert next_cursor is None
        assert total == 5  # Total should still be returned correctly
