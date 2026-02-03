"""Cursor pagination tests for repositories.

These tests verify that cursor pagination uses the correct columns:
- TransactionCursor should use t.id (PK), not t.transaction_id
- ReviewCursor should use r.id (PK), not r.transaction_id
"""

from datetime import datetime, timedelta
from uuid import uuid7

from app.persistence.review_repository import ReviewCursor, ReviewRepository
from app.persistence.transaction_repository import TransactionCursor, TransactionRepository


class TestTransactionCursor:
    """Test TransactionCursor behavior."""

    def test_cursor_uses_id_for_primary_key(self):
        """Test that cursor uses id (PK) field, not transaction_id (business key)."""
        now = datetime.now()
        cursor_id = uuid7()

        # Cursor should use id parameter
        cursor = TransactionCursor(id=cursor_id, timestamp=now)

        assert cursor.id == cursor_id
        assert cursor.transaction_id == cursor_id  # Alias returns same value

    def test_cursor_encode_decode_roundtrip(self):
        """Test that cursor encode/decode preserves id correctly."""
        original_id = uuid7()
        original_ts = datetime(2026, 1, 15, 10, 30, 0)

        cursor = TransactionCursor(id=original_id, timestamp=original_ts)
        encoded = cursor.encode()
        decoded = TransactionCursor.decode(encoded)

        assert decoded.id == original_id
        assert decoded.transaction_timestamp == original_ts

    def test_cursor_transaction_id_is_alias_for_id(self):
        """Test that transaction_id is an alias for id in TransactionCursor."""
        test_id = uuid7()
        now = datetime.now()

        # Create with old parameter name
        cursor = TransactionCursor(transaction_id=test_id, transaction_timestamp=now)

        # Both should reference the same value
        assert cursor.id == test_id
        assert cursor.transaction_id == test_id

    def test_cursor_backwards_compatibility(self):
        """Test that cursor maintains backwards compatibility."""
        test_id = uuid7()
        test_ts = datetime.now()

        # Old parameter names
        cursor1 = TransactionCursor(transaction_id=test_id, transaction_timestamp=test_ts)

        # New parameter names
        cursor2 = TransactionCursor(id=test_id, timestamp=test_ts)

        # Should produce compatible cursors
        assert cursor1.id == cursor2.id
        assert ReviewCursor.decode(cursor1.encode()).id == test_id
        assert ReviewCursor.decode(cursor2.encode()).id == test_id


class TestReviewCursor:
    """Test ReviewCursor behavior."""

    def test_cursor_uses_id_for_primary_key(self):
        """Test that cursor uses id (PK) field."""
        now = datetime.now()
        cursor_id = uuid7()

        cursor = ReviewCursor(id=cursor_id, timestamp=now)

        assert cursor.id == cursor_id
        assert cursor.created_at == now

    def test_cursor_encode_decode_roundtrip(self):
        """Test that cursor encode/decode preserves id correctly."""
        original_id = uuid7()
        original_ts = datetime(2026, 1, 15, 10, 30, 0)

        cursor = ReviewCursor(id=original_id, timestamp=original_ts)
        encoded = cursor.encode()
        decoded = ReviewCursor.decode(encoded)

        assert decoded.id == original_id
        assert decoded.created_at == original_ts

    def test_cursor_backwards_compatibility(self):
        """Test that cursor maintains backwards compatibility."""
        test_id = uuid7()
        test_ts = datetime.now()

        cursor1 = ReviewCursor(created_at=test_ts, id=test_id)
        cursor2 = ReviewCursor(timestamp=test_ts, id=test_id)

        assert cursor1.id == cursor2.id
        assert cursor1.created_at == cursor2.created_at


class TestCursorEdgeCases:
    """Test cursor edge cases."""

    def test_cursor_decode_invalid_base64_returns_none(self):
        """Test that invalid base64 returns None."""
        assert TransactionCursor.decode("not-valid-base64!") is None
        assert ReviewCursor.decode("not-valid-base64!") is None

    def test_cursor_decode_invalid_json_returns_none(self):
        """Test that invalid JSON in cursor returns None."""
        import base64

        # Valid base64 but invalid JSON
        invalid_json = base64.urlsafe_b64encode(b"{not valid json}").decode()
        assert TransactionCursor.decode(invalid_json) is None
        assert ReviewCursor.decode(invalid_json) is None

    def test_cursor_decode_missing_parts_returns_none(self):
        """Test that cursor with missing parts returns None."""
        import base64

        # Only one part (timestamp or id)
        single_part = base64.urlsafe_b64encode(b"2024-01-01T00:00:00").decode()
        assert TransactionCursor.decode(single_part) is None
        assert ReviewCursor.decode(single_part) is None

    def test_cursor_with_future_timestamp(self):
        """Test that cursor works with future timestamps."""
        future_ts = datetime.now() + timedelta(days=1)
        cursor_id = uuid7()

        t_cursor = TransactionCursor(id=cursor_id, timestamp=future_ts)
        r_cursor = ReviewCursor(id=cursor_id, timestamp=future_ts)

        assert t_cursor.id == cursor_id
        assert r_cursor.id == cursor_id

    def test_cursor_with_old_timestamp(self):
        """Test that cursor works with old timestamps."""
        old_ts = datetime(2020, 1, 1, 0, 0, 0)
        cursor_id = uuid7()

        t_cursor = TransactionCursor(id=cursor_id, timestamp=old_ts)
        r_cursor = ReviewCursor(id=cursor_id, timestamp=old_ts)

        assert t_cursor.id == cursor_id
        assert r_cursor.id == cursor_id


class TestCursorCodePatterns:
    """Test that repository code uses correct cursor patterns."""

    def test_review_repository_list_unassigned_cursor_uses_id(self):
        """Verify list_unassigned generates cursor with r.id."""
        import inspect

        source = inspect.getsource(ReviewRepository.list_unassigned)

        # Cursor should use r.id, not r.transaction_id
        assert 'id=last_review["review_id"]' in source, (
            "Cursor should use last_review['review_id'] which maps to r.id"
        )

    def test_transaction_repository_list_cursor_uses_id(self):
        """Verify TransactionRepository.list() generates cursor with t.id."""
        import inspect

        source = inspect.getsource(TransactionRepository.list)

        # Cursor should use t.id, not t.transaction_id
        assert 'id=last_txn["id"]' in source or "id=last_txn.get('id')" in source, (
            "Cursor should use last_txn['id'] (PK), not last_txn['transaction_id'] (business key)"
        )
