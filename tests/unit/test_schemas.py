"""Unit tests for decision event schemas."""

from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.decision_event import (
    CardNetwork,
    DecisionEventCreate,
    DecisionReason,
    DecisionType,
    EvaluationType,
    IngestionSource,
    RuleMatch,
    TransactionDetails,
)


class TestDecisionEventSchemas:
    """Tests for decision event Pydantic models."""

    def test_valid_decision_event(self, sample_decision_event):
        """Test creating a valid decision event."""
        assert sample_decision_event.event_version == "1.0"
        assert sample_decision_event.transaction_id == "txn_test_001"
        assert sample_decision_event.decision == DecisionType.DECLINE
        assert sample_decision_event.decision_reason == DecisionReason.RULE_MATCH
        assert len(sample_decision_event.matched_rules) == 1

    def test_transaction_details_minimal(self):
        """Test transaction details with minimal fields."""
        details = TransactionDetails(
            card_id="tok_visa_12345",
            amount=Decimal("50.00"),
            currency="USD",
            country="US",
        )
        assert details.card_id == "tok_visa_12345"
        assert details.amount == Decimal("50.00")
        assert details.card_last4 is None
        assert details.card_network is None

    def test_card_id_must_be_tokenized(self):
        """Test that card_id must be tokenized."""
        with pytest.raises(ValidationError) as exc_info:
            TransactionDetails(
                card_id="4242424242424242",  # Raw PAN - should fail
                amount=Decimal("50.00"),
                currency="USD",
                country="US",
            )
        assert "tokenized" in str(exc_info.value).lower()

    def test_card_id_pan_prefix_allowed(self):
        """Test that pan_ prefix is allowed (for detection)."""
        details = TransactionDetails(
            card_id="pan_4242424242424242",
            amount=Decimal("50.00"),
            currency="USD",
            country="US",
        )
        assert details.card_id == "pan_4242424242424242"

    def test_decision_types(self):
        """Test all decision types are valid."""
        for decision in DecisionType:
            assert decision.value in ["APPROVE", "DECLINE"]

    def test_decision_reasons(self):
        """Test all decision reasons are valid."""
        for reason in DecisionReason:
            assert reason.value in [
                "RULE_MATCH",
                "VELOCITY_MATCH",
                "SYSTEM_DECLINE",
                "DEFAULT_ALLOW",
                "MANUAL_REVIEW",
            ]

    def test_card_networks(self):
        """Test all card networks are valid."""
        for network in CardNetwork:
            assert network.value in ["VISA", "MASTERCARD", "AMEX", "DISCOVER", "OTHER"]

    def test_rule_match_minimal(self):
        """Test rule match with minimal fields."""
        rule = RuleMatch(
            rule_id="rule_001",
            rule_version=1,
        )
        assert rule.rule_id == "rule_001"
        assert rule.rule_version == 1
        assert rule.priority is None

    def test_rule_match_with_all_fields(self):
        """Test rule match with all fields."""
        now = datetime.utcnow()
        rule = RuleMatch(
            rule_id="rule_001",
            rule_version=5,
            priority=100,
            matched_at=now,
            rule_name="High Value Rule",
            rule_type="BLOCKLIST",
        )
        assert rule.rule_id == "rule_001"
        assert rule.rule_version == 5
        assert rule.priority == 100
        assert rule.matched_at == now
        assert rule.rule_name == "High Value Rule"
        assert rule.rule_type == "BLOCKLIST"

    def test_amount_must_be_positive(self):
        """Test that amount must be positive."""
        with pytest.raises(ValidationError):
            TransactionDetails(
                card_id="tok_visa_12345",
                amount=Decimal("-10.00"),
                currency="USD",
                country="US",
            )

    def test_currency_must_be_3_chars(self):
        """Test that currency must be 3 characters."""
        with pytest.raises(ValidationError):
            TransactionDetails(
                card_id="tok_visa_12345",
                amount=Decimal("50.00"),
                currency="USDD",  # 4 chars - should fail
                country="US",
            )

    def test_country_must_be_2_chars(self):
        """Test that country must be 2 characters."""
        with pytest.raises(ValidationError):
            TransactionDetails(
                card_id="tok_visa_12345",
                amount=Decimal("50.00"),
                currency="USD",
                country="USA",  # 3 chars - should fail
            )

    def test_empty_matched_rules(self):
        """Test decision event with no rule matches."""
        event = DecisionEventCreate(
            event_version="1.0",
            transaction_id="txn_no_rules",
            occurred_at=datetime.utcnow(),
            produced_at=datetime.utcnow(),
            evaluation_type=EvaluationType.AUTH,
            transaction=TransactionDetails(
                card_id="tok_visa_12345",
                amount=Decimal("25.00"),
                currency="USD",
                country="CA",
            ),
            decision=DecisionType.APPROVE,
            decision_reason=DecisionReason.DEFAULT_ALLOW,
            matched_rules=[],  # Empty list
        )
        assert len(event.matched_rules) == 0


class TestIngestionSource:
    """Tests for ingestion source enum."""

    def test_ingestion_sources(self):
        """Test ingestion source values."""
        assert IngestionSource.HTTP.value == "HTTP"
        assert IngestionSource.KAFKA.value == "KAFKA"
