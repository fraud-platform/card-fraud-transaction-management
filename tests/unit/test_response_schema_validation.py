"""Response schema validation tests.

These tests verify that responses match Pydantic schemas exactly.
"""

from datetime import datetime
from uuid import UUID, uuid7

import pytest

from app.schemas.worklist import RiskLevel, WorklistItem, WorklistStats
from tests.utils.schema_validators import validate_response_schema


class TestWorklistItemSchemaValidation:
    """Test WorklistItem schema validation."""

    def test_worklist_item_validates_with_all_fields(self):
        """Test WorklistItem validates with all required fields."""
        valid_data = {
            "review_id": uuid7(),
            "transaction_id": uuid7(),
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
        assert isinstance(validated.review_id, UUID)  # type: ignore[attr-defined]

    def test_worklist_item_requires_review_id_not_id(self):
        """Test that WorklistItem requires review_id field, not id."""
        invalid_data = {
            "id": uuid7(),  # Wrong field name
            "transaction_id": uuid7(),
            "status": "PENDING",
            "priority": 3,
            "card_id": "tok_visa",
            "transaction_amount": 100.00,
            "transaction_currency": "USD",
            "transaction_timestamp": datetime.now(),
            "decision": "APPROVE",
            "decision_reason": "DEFAULT_ALLOW",
            "created_at": datetime.now(),
        }

        # Should raise - field is called "review_id", not "id"
        with pytest.raises(AssertionError):
            validate_response_schema(invalid_data, WorklistItem)

    def test_worklist_item_requires_decision_reason(self):
        """Test that WorklistItem requires decision_reason field."""
        # Missing decision_reason field
        invalid_data = {
            "review_id": uuid7(),
            "transaction_id": uuid7(),
            "status": "PENDING",
            "priority": 3,
            "card_id": "tok_visa",
            "transaction_amount": 100.00,
            "transaction_currency": "USD",
            "transaction_timestamp": datetime.now(),
            "decision": "APPROVE",
            # Missing decision_reason
            "created_at": datetime.now(),
        }

        with pytest.raises(AssertionError):
            validate_response_schema(invalid_data, WorklistItem)

    def test_worklist_item_allows_optional_fields_to_be_null(self):
        """Test that optional fields can be None."""
        valid_data = {
            "review_id": uuid7(),
            "transaction_id": uuid7(),
            "status": "PENDING",
            "priority": 3,
            "card_id": "tok_visa",
            "card_last4": "4242",
            "transaction_amount": 100.00,
            "transaction_currency": "USD",
            "transaction_timestamp": datetime.now(),
            "decision": "APPROVE",
            "decision_reason": "DEFAULT_ALLOW",
            "risk_level": None,  # Optional
            "assigned_analyst_id": None,  # Optional
            "assigned_at": None,  # Optional
            "case_id": None,  # Optional
            "first_reviewed_at": None,  # Optional
            "last_activity_at": None,  # Optional
            "merchant_id": None,  # Optional
            "merchant_category_code": None,  # Optional
            "trace_id": None,  # Optional
            "created_at": datetime.now(),
        }

        # Should validate successfully
        validated = validate_response_schema(valid_data, WorklistItem)
        assert validated.risk_level is None  # type: ignore[attr-defined]
        assert validated.assigned_analyst_id is None  # type: ignore[attr-defined]


class TestWorklistStatsSchemaValidation:
    """Test WorklistStats schema validation."""

    def test_worklist_stats_requires_all_fields(self):
        """Test WorklistStats has specific required fields."""
        from app.schemas.worklist import WorklistStats

        # Check schema fields (Pydantic v2 uses model_fields)
        field_names = list(WorklistStats.model_fields.keys())

        required_fields = [
            "unassigned_total",
            "unassigned_by_priority",
            "unassigned_by_risk",
            "my_assigned_total",
            "my_assigned_by_status",
            "resolved_today",
            "resolved_by_code",
        ]

        for field in required_fields:
            assert field in field_names, f"Missing required field: {field}"

    def test_worklist_stats_validates_with_all_fields(self):
        """Test WorklistStats validates with all fields."""
        valid_data = {
            "unassigned_total": 10,
            "unassigned_by_priority": {"1": 2, "2": 3, "3": 5},
            "unassigned_by_risk": {"CRITICAL": 1, "HIGH": 4, "MEDIUM": 5},
            "my_assigned_total": 5,
            "my_assigned_by_status": {"PENDING": 2, "IN_REVIEW": 3},
            "resolved_today": 8,
            "resolved_by_code": {"FRAUD_CONFIRMED": 5, "FALSE_POSITIVE": 3},
            "avg_resolution_minutes": 15.5,
        }

        validated = validate_response_schema(valid_data, WorklistStats)
        assert validated.resolved_by_code == {"FRAUD_CONFIRMED": 5, "FALSE_POSITIVE": 3}  # type: ignore[attr-defined]

    def test_worklist_stats_allows_optional_fields_to_be_null(self):
        """Test that avg_resolution_minutes can be None."""
        valid_data = {
            "unassigned_total": 10,
            "unassigned_by_priority": {},
            "unassigned_by_risk": {},
            "my_assigned_total": 0,
            "my_assigned_by_status": {},
            "resolved_today": 0,
            "resolved_by_code": {},
            "avg_resolution_minutes": None,  # Optional
        }

        validated = validate_response_schema(valid_data, WorklistStats)
        assert validated.avg_resolution_minutes is None  # type: ignore[attr-defined]


class TestSchemaValidatorUtility:
    """Test the schema validator utility functions."""

    def test_validate_response_schema_with_valid_data(self):
        """Test validate_response_schema with valid data."""
        valid_data = {
            "review_id": uuid7(),
            "transaction_id": uuid7(),
            "status": "PENDING",
            "priority": 3,
            "card_id": "tok_visa",
            "transaction_amount": 100.00,
            "transaction_currency": "USD",
            "transaction_timestamp": datetime.now(),
            "decision": "APPROVE",
            "decision_reason": "DEFAULT_ALLOW",
            "created_at": datetime.now(),
        }

        validated = validate_response_schema(valid_data, WorklistItem)
        assert isinstance(validated.review_id, UUID)  # type: ignore[attr-defined]

    def test_validate_response_schema_with_invalid_data(self):
        """Test validate_response_schema raises with invalid data."""
        invalid_data = {
            "review_id": uuid7(),
            # Missing required fields
        }

        # validate_response_schema uses Pydantic validation which raises ValidationError
        # Our wrapper catches and re-raises as AssertionError
        with pytest.raises((AssertionError, Exception)):
            validate_response_schema(invalid_data, WorklistItem)
