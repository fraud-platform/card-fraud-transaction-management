"""Field mapping tests for repositories.

These tests verify that repository _row_to_dict methods correctly map
database row columns to dictionaries that match Pydantic schemas.
"""

from datetime import datetime
from unittest.mock import MagicMock
from uuid import uuid7

import pytest

from app.persistence.review_repository import ReviewRepository
from app.schemas.worklist import RiskLevel, WorklistItem
from tests.utils.schema_validators import validate_response_schema


class TestReviewRepositoryFieldMapping:
    """Test field mapping in ReviewRepository._row_to_dict_full."""

    def test_row_to_dict_full_maps_id_to_review_id(self):
        """Test that _row_to_dict_full maps id column to review_id."""
        mock_session = MagicMock()
        repo = ReviewRepository(mock_session)

        review_id = uuid7()
        mock_row = MagicMock()

        # Mock row with correct column order matching the SQL SELECT
        # Must have at least 22 elements for all conditional checks
        values = [
            review_id,  # 0: r.id -> review_id
            uuid7(),  # 1: r.transaction_id
            "PENDING",  # 2: r.status
            3,  # 3: r.priority
            None,  # 4: r.assigned_analyst_id
            None,  # 5: r.assigned_at
            None,  # 6: r.case_id
            None,  # 7: r.first_reviewed_at
            None,  # 8: r.last_activity_at
            datetime.now(),  # 9: r.created_at
            datetime.now(),  # 10: r.updated_at
            100.00,  # 11: t.transaction_amount
            "USD",  # 12: t.transaction_currency
            "DECLINE",  # 13: t.decision
            "RULE_MATCH",  # 14: t.decision_reason
            "HIGH",  # 15: t.risk_level
            "tok_visa",  # 16: t.card_id
            "4242",  # 17: t.card_last4
            datetime.now(),  # 18: t.transaction_timestamp
            "merch_001",  # 19: t.merchant_id
            "5411",  # 20: t.merchant_category_code
            "trace_123",  # 21: t.trace_id
        ]
        # Use a list for __getitem__ and provide __len__
        mock_row.__getitem__.side_effect = lambda idx: values[idx] if idx < len(values) else None
        mock_row.__len__.side_effect = lambda: len(values)

        result = repo._row_to_dict_full(mock_row)

        # Verify id is mapped to review_id (critical for WorklistItem schema)
        assert "review_id" in result, "Result should have 'review_id' field"
        assert result["review_id"] == review_id, "review_id should match the id column"

    def test_row_to_dict_full_includes_decision_reason(self):
        """Test that decision_reason field is included (was missing in bug #4)."""
        mock_session = MagicMock()
        repo = ReviewRepository(mock_session)

        mock_row = MagicMock()
        values = [
            uuid7(),
            uuid7(),
            "PENDING",
            3,
            None,
            None,
            None,
            None,
            None,
            datetime.now(),
            datetime.now(),
            100.00,
            "USD",
            "DECLINE",
            "RULE_MATCH",  # decision_reason - this was missing
            "HIGH",
            "tok_visa",
            "4242",
            datetime.now(),
            "merch_001",
            "5411",
            "trace_123",
        ]
        mock_row.__getitem__.side_effect = lambda idx: values[idx] if idx < len(values) else None
        mock_row.__len__.side_effect = lambda: len(values)

        result = repo._row_to_dict_full(mock_row)

        # decision_reason should be present
        assert "decision_reason" in result
        assert result["decision_reason"] == "RULE_MATCH"

    def test_row_to_dict_full_has_required_worklist_item_fields(self):
        """Test _row_to_dict_full includes all required WorklistItem fields."""
        mock_session = MagicMock()
        repo = ReviewRepository(mock_session)

        review_id = uuid7()
        transaction_id = uuid7()

        mock_row = MagicMock()
        values = [
            review_id,
            transaction_id,
            "PENDING",
            3,
            None,
            None,
            None,
            None,
            None,
            datetime.now(),
            datetime.now(),
            100.00,
            "USD",
            "DECLINE",
            "RULE_MATCH",
            "HIGH",
            "tok_visa",
            "4242",
            datetime.now(),
            "merch_001",
            "5411",
            "trace_123",
        ]
        mock_row.__getitem__.side_effect = lambda idx: values[idx] if idx < len(values) else None
        mock_row.__len__.side_effect = lambda: len(values)

        result = repo._row_to_dict_full(mock_row)

        # Verify all required WorklistItem fields are present
        required_fields = [
            "review_id",
            "transaction_id",
            "status",
            "priority",
            "card_id",
            "transaction_amount",
            "transaction_currency",
            "transaction_timestamp",
            "decision",
            "decision_reason",
            "created_at",
        ]
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

    def test_row_to_dict_full_handles_missing_optional_fields(self):
        """Test that optional fields default to None when not in row."""
        mock_session = MagicMock()
        repo = ReviewRepository(mock_session)

        mock_row = MagicMock()
        # Only required fields - short row (15 elements instead of 22)
        values = [
            uuid7(),  # review_id
            uuid7(),  # transaction_id
            "PENDING",  # status
            3,  # priority
            None,
            None,
            None,
            None,
            None,
            datetime.now(),
            datetime.now(),
            100.00,
            "USD",
            "DECLINE",
            "RULE_MATCH",
            "HIGH",
            # Missing: card_id, card_last4, transaction_timestamp, merchant_id, etc.
        ]
        mock_row.__getitem__.side_effect = lambda idx: values[idx] if idx < len(values) else None
        mock_row.__len__.side_effect = lambda: len(values)

        result = repo._row_to_dict_full(mock_row)

        # Optional fields should be None when row is short
        assert result.get("card_id") is None
        assert result.get("card_last4") is None
        assert result.get("transaction_timestamp") is None


class TestSchemaValidation:
    """Test that response data matches Pydantic schemas."""

    def test_worklist_item_validation_with_valid_data(self):
        """Test WorklistItem schema validates with valid data."""
        review_id = uuid7()
        transaction_id = uuid7()

        valid_data = {
            "review_id": review_id,
            "transaction_id": transaction_id,
            "status": "PENDING",
            "priority": 3,
            "card_id": "tok_visa",
            "card_last4": "4242",
            "transaction_amount": 100.00,
            "transaction_currency": "USD",
            "transaction_timestamp": datetime.now(),
            "decision": "APPROVE",
            "decision_reason": "DEFAULT_ALLOW",
            "risk_level": RiskLevel.LOW,
            "created_at": datetime.now(),
        }

        # Should not raise
        validated = validate_response_schema(valid_data, WorklistItem)
        assert validated.review_id == review_id

    def test_worklist_item_validation_missing_required_field(self):
        """Test WorklistItem schema rejects missing required fields."""
        invalid_data = {
            "review_id": uuid7(),
            # Missing required fields
        }

        # Should raise AssertionError
        with pytest.raises(AssertionError):
            validate_response_schema(invalid_data, WorklistItem)

    def test_worklist_stats_validation_with_valid_data(self):
        """Test WorklistStats schema validates with valid data."""
        from app.schemas.worklist import WorklistStats

        valid_data = {
            "unassigned_total": 10,
            "unassigned_by_priority": {"1": 2, "2": 3, "3": 5},
            "unassigned_by_risk": {"CRITICAL": 1, "HIGH": 4, "MEDIUM": 5},
            "my_assigned_total": 5,
            "my_assigned_by_status": {"PENDING": 2, "IN_REVIEW": 3},
            "resolved_today": 8,
            "resolved_by_code": {"FRAUD_CONFIRMED": 5, "FALSE_POSITIVE": 3},
        }

        # Should not raise
        validated = validate_response_schema(valid_data, WorklistStats)
        assert validated.unassigned_total == 10
        assert validated.resolved_by_code == {"FRAUD_CONFIRMED": 5, "FALSE_POSITIVE": 3}

    def test_worklist_stats_includes_resolved_by_code(self):
        """Test that resolved_by_code is a required field in WorklistStats."""
        from app.schemas.worklist import WorklistStats

        # Check that resolved_by_code is in the schema fields (Pydantic v2 uses model_fields)
        field_names = list(WorklistStats.model_fields.keys())
        assert "resolved_by_code" in field_names, (
            "resolved_by_code should be in WorklistStats schema"
        )
