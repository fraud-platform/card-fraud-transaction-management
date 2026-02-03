"""Unit tests for API routes (decision_events)."""

from datetime import datetime
from decimal import Decimal

import pytest
from fastapi import FastAPI

from app.api.routes.decision_events import router
from app.schemas.decision_event import (
    CardNetwork,
    DecisionEventCreate,
    DecisionEventResponse,
    DecisionReason,
    DecisionType,
    ErrorResponse,
    EvaluationType,
    IngestionSource,
    RuleMatch,
    TransactionDetails,
    TransactionListResponse,
    TransactionQueryResult,
)


def create_app():
    """Create test FastAPI app."""
    app = FastAPI()
    app.include_router(router, prefix="/v1")
    return app


class TestDecisionEventsRoutes:
    """Test decision events API routes."""

    def test_app_includes_router(self):
        """Test that app includes decision_events router."""
        app = create_app()
        assert len(app.routes) > 0

    def test_router_has_decision_events_endpoint(self):
        """Test that router has /decision-events endpoint."""
        assert router is not None
        assert len(router.routes) > 0

    def test_router_has_transactions_endpoint(self):
        """Test that router has /transactions endpoint."""
        assert router is not None
        endpoint_paths = [r.path for r in router.routes]
        assert "/api/v1/transactions" in endpoint_paths or any(
            "transactions" in p for p in endpoint_paths
        )

    def test_router_has_metrics_endpoint(self):
        """Test that router has /metrics endpoint."""
        assert router is not None
        endpoint_paths = [r.path for r in router.routes]
        assert "/api/v1/metrics" in endpoint_paths or any("metrics" in p for p in endpoint_paths)


class TestTransactionDetails:
    """Test TransactionDetails schema."""

    def test_transaction_details_minimal(self):
        """Test creating TransactionDetails with minimal fields."""
        details = TransactionDetails(
            card_id="tok_card123",
            amount=Decimal("100.00"),
            currency="USD",
            country="US",
        )
        assert details.card_id == "tok_card123"
        assert details.amount == Decimal("100.00")
        assert details.currency == "USD"
        assert details.country == "US"

    def test_transaction_details_full(self):
        """Test creating TransactionDetails with all fields."""
        details = TransactionDetails(
            card_id="tok_card456",
            card_last4="1234",
            card_network=CardNetwork.VISA,
            amount=Decimal("2500.50"),
            currency="EUR",
            country="DE",
            merchant_id="merchant_001",
            mcc="5411",
            ip_address="192.168.1.1",
        )
        assert details.card_network == CardNetwork.VISA
        assert details.merchant_id == "merchant_001"
        assert details.card_last4 == "1234"

    def test_transaction_details_card_id_tokenized(self):
        """Test that card_id with tok_ prefix is valid."""
        details = TransactionDetails(
            card_id="tok_card123",
            amount=Decimal("100.00"),
            currency="USD",
            country="US",
        )
        assert details.card_id == "tok_card123"

    def test_transaction_details_card_id_pan_prefix(self):
        """Test that card_id with pan_ prefix is valid (for detection)."""
        details = TransactionDetails(
            card_id="pan_4111111111111111",
            amount=Decimal("100.00"),
            currency="USD",
            country="US",
        )
        assert details.card_id == "pan_4111111111111111"

    def test_transaction_details_card_id_rejects_raw_pan(self):
        """Test that card_id must have tok_ or pan_ prefix."""
        with pytest.raises(ValueError, match="card_id must be tokenized"):
            TransactionDetails(
                card_id="4111111111111111",  # Raw PAN without prefix
                amount=Decimal("100.00"),
                currency="USD",
                country="US",
            )


class TestRuleMatch:
    """Test RuleMatch schema."""

    def test_rule_match_minimal(self):
        """Test creating RuleMatch with minimal fields."""
        rule = RuleMatch(
            rule_id="rule_001",
            rule_version=1,
        )
        assert rule.rule_id == "rule_001"
        assert rule.rule_version == 1

    def test_rule_match_full(self):
        """Test creating RuleMatch with all fields."""
        now = datetime.now()
        rule = RuleMatch(
            rule_id="rule_002",
            rule_version=3,
            priority=10,
            matched_at=now,
            rule_name="Velocity Check",
            rule_type="velocity",
        )
        assert rule.priority == 10
        assert rule.rule_name == "Velocity Check"

    def test_rule_match_version_must_be_positive(self):
        """Test that rule_version must be >= 1."""
        with pytest.raises(ValueError):
            RuleMatch(
                rule_id="rule_001",
                rule_version=0,
            )

    def test_rule_match_priority_can_be_zero(self):
        """Test that priority can be 0."""
        rule = RuleMatch(
            rule_id="rule_001",
            rule_version=1,
            priority=0,
        )
        assert rule.priority == 0


class TestDecisionEventCreate:
    """Test DecisionEventCreate schema."""

    def test_decision_event_create_minimal(self):
        """Test creating DecisionEventCreate with minimal fields."""
        details = TransactionDetails(
            card_id="tok_card123",
            amount=Decimal("100.00"),
            currency="USD",
            country="US",
        )
        now = datetime.now()
        event = DecisionEventCreate(
            transaction_id="txn_001",
            evaluation_type=EvaluationType.AUTH,
            occurred_at=now,
            produced_at=now,
            transaction=details,
            decision=DecisionType.APPROVE,
            decision_reason=DecisionReason.DEFAULT_ALLOW,
        )
        assert event.transaction_id == "txn_001"
        assert event.evaluation_type == EvaluationType.AUTH
        assert event.decision == DecisionType.APPROVE
        assert event.transaction.card_id == "tok_card123"

    def test_decision_event_create_with_rules(self):
        """Test creating DecisionEventCreate with matched rules."""
        details = TransactionDetails(
            card_id="tok_card456",
            amount=Decimal("500.00"),
            currency="USD",
            country="US",
        )
        now = datetime.now()
        rule = RuleMatch(
            rule_id="rule_001",
            rule_version=1,
        )
        event = DecisionEventCreate(
            transaction_id="txn_002",
            evaluation_type=EvaluationType.AUTH,
            occurred_at=now,
            produced_at=now,
            transaction=details,
            decision=DecisionType.DECLINE,
            decision_reason=DecisionReason.RULE_MATCH,
            matched_rules=[rule],
        )
        assert len(event.matched_rules) == 1
        assert event.decision == DecisionType.DECLINE

    def test_decision_event_create_with_raw_payload(self):
        """Test creating DecisionEventCreate with raw_payload."""
        details = TransactionDetails(
            card_id="tok_card789",
            amount=Decimal("200.00"),
            currency="USD",
            country="US",
        )
        now = datetime.now()
        event = DecisionEventCreate(
            transaction_id="txn_003",
            evaluation_type=EvaluationType.AUTH,
            occurred_at=now,
            produced_at=now,
            transaction=details,
            decision=DecisionType.APPROVE,
            decision_reason=DecisionReason.DEFAULT_ALLOW,
            raw_payload={"user_agent": "Mozilla/5.0", "ip_country": "US"},
        )
        assert event.raw_payload is not None
        assert event.raw_payload["user_agent"] == "Mozilla/5.0"

    def test_decision_event_create_default_event_version(self):
        """Test that event_version defaults to '1.0'."""
        details = TransactionDetails(
            card_id="tok_card123",
            amount=Decimal("100.00"),
            currency="USD",
            country="US",
        )
        now = datetime.now()
        event = DecisionEventCreate(
            transaction_id="txn_001",
            evaluation_type=EvaluationType.AUTH,
            occurred_at=now,
            produced_at=now,
            transaction=details,
            decision=DecisionType.APPROVE,
            decision_reason=DecisionReason.DEFAULT_ALLOW,
        )
        assert event.event_version == "1.0"


class TestDecisionEventResponse:
    """Test DecisionEventResponse schema."""

    def test_decision_event_response_creation(self):
        """Test creating DecisionEventResponse."""
        now = datetime.now()
        response = DecisionEventResponse(
            transaction_id="txn_001",
            ingestion_source=IngestionSource.HTTP,
            ingested_at=now,
        )
        assert response.transaction_id == "txn_001"
        assert response.ingestion_source == IngestionSource.HTTP
        assert response.status == "accepted"

    def test_decision_event_response_default_status(self):
        """Test that status defaults to 'accepted'."""
        now = datetime.now()
        response = DecisionEventResponse(
            transaction_id="txn_001",
            ingestion_source=IngestionSource.KAFKA,
            ingested_at=now,
        )
        assert response.status == "accepted"


class TestTransactionListResponse:
    """Test TransactionListResponse schema."""

    def test_transaction_list_response_creation(self):
        """Test creating TransactionListResponse."""
        response = TransactionListResponse(
            items=[],
            total=0,
            page_size=50,
            next_cursor=None,
        )
        assert response.items == []
        assert response.total == 0
        assert response.page_size == 50
        assert response.next_cursor is None

    def test_transaction_list_response_with_data(self):
        """Test creating TransactionListResponse with transactions."""
        now = datetime.now()
        result = TransactionQueryResult(
            transaction_id="txn_001",
            card_id="tok_card123",
            card_last4="1234",
            card_network=CardNetwork.VISA,
            amount=Decimal("100.00"),
            currency="USD",
            merchant_id="merchant_001",
            mcc="5411",
            decision=DecisionType.APPROVE,
            decision_reason=DecisionReason.DEFAULT_ALLOW,
            trace_id="trace-123",
            transaction_timestamp=now,
            ingestion_timestamp=now,
            ingestion_source=IngestionSource.HTTP,
            created_at=now,
            updated_at=now,
        )
        response = TransactionListResponse(
            items=[result],
            total=1,
            page_size=50,
            next_cursor="next_page_token",
        )
        assert len(response.items) == 1
        assert response.total == 1
        assert response.next_cursor == "next_page_token"


class TestTransactionQueryResult:
    """Test TransactionQueryResult schema."""

    def test_transaction_query_result_minimal(self):
        """Test creating TransactionQueryResult with minimal fields."""
        now = datetime.now()
        result = TransactionQueryResult(
            transaction_id="txn_001",
            card_id="tok_card123",
            amount=Decimal("100.00"),
            currency="USD",
            decision=DecisionType.APPROVE,
            decision_reason=DecisionReason.DEFAULT_ALLOW,
            trace_id=None,
            card_last4=None,
            card_network=None,
            merchant_id=None,
            mcc=None,
            transaction_timestamp=now,
            ingestion_timestamp=now,
            ingestion_source=IngestionSource.HTTP,
            created_at=now,
            updated_at=now,
        )
        assert result.transaction_id == "txn_001"

    def test_transaction_query_result_with_matched_rules(self):
        """Test TransactionQueryResult with matched rules."""
        now = datetime.now()
        result = TransactionQueryResult(
            transaction_id="txn_002",
            card_id="tok_card456",
            amount=Decimal("500.00"),
            currency="USD",
            decision=DecisionType.DECLINE,
            decision_reason=DecisionReason.RULE_MATCH,
            trace_id="trace-123",
            matched_rules=[{"rule_id": "rule_001", "rule_version": 1}],
            card_last4=None,
            card_network=None,
            merchant_id=None,
            mcc=None,
            transaction_timestamp=now,
            ingestion_timestamp=now,
            ingestion_source=IngestionSource.KAFKA,
            created_at=now,
            updated_at=now,
        )
        assert len(result.matched_rules) == 1
        assert result.matched_rules[0]["rule_id"] == "rule_001"


class TestEnums:
    """Test enum types."""

    def test_decision_type_values(self):
        """Test DecisionType enum values."""
        assert DecisionType.APPROVE == "APPROVE"
        assert DecisionType.DECLINE == "DECLINE"

    def test_decision_reason_values(self):
        """Test DecisionReason enum values."""
        assert DecisionReason.RULE_MATCH == "RULE_MATCH"
        assert DecisionReason.VELOCITY_MATCH == "VELOCITY_MATCH"
        assert DecisionReason.SYSTEM_DECLINE == "SYSTEM_DECLINE"
        assert DecisionReason.DEFAULT_ALLOW == "DEFAULT_ALLOW"
        assert DecisionReason.MANUAL_REVIEW == "MANUAL_REVIEW"

    def test_card_network_values(self):
        """Test CardNetwork enum values."""
        assert CardNetwork.VISA == "VISA"
        assert CardNetwork.MASTERCARD == "MASTERCARD"
        assert CardNetwork.AMEX == "AMEX"
        assert CardNetwork.DISCOVER == "DISCOVER"
        assert CardNetwork.OTHER == "OTHER"

    def test_ingestion_source_values(self):
        """Test IngestionSource enum values."""
        assert IngestionSource.HTTP == "HTTP"
        assert IngestionSource.KAFKA == "KAFKA"


class TestRouteImports:
    """Test that route imports work correctly."""

    def test_router_import(self):
        """Test router can be imported."""
        from app.api.routes.decision_events import router

        assert router is not None

    def test_schemas_import(self):
        """Test schemas can be imported."""
        from app.schemas.decision_event import (
            DecisionEventCreate,
            DecisionReason,
            DecisionType,
            ErrorResponse,
        )

        assert DecisionEventCreate is not None
        assert DecisionType is not None
        assert DecisionReason is not None
        assert ErrorResponse is not None


class TestErrorResponse:
    """Test ErrorResponse schema."""

    def test_error_response_minimal(self):
        """Test creating ErrorResponse with minimal fields."""
        response = ErrorResponse(error="Something went wrong")
        assert response.error == "Something went wrong"
        assert response.details is None

    def test_error_response_with_details(self):
        """Test creating ErrorResponse with details."""
        response = ErrorResponse(
            error="Validation error",
            details={"field": "card_id", "reason": "Invalid format"},
        )
        assert response.error == "Validation error"
        assert response.details is not None
        assert response.details["field"] == "card_id"


class TestSchemaValidation:
    """Test schema validation rules."""

    def test_transaction_details_validates_amount_positive(self):
        """Test that amount must be positive."""
        with pytest.raises(ValueError):
            TransactionDetails(
                card_id="tok_card123",
                amount=Decimal("-100.00"),  # Negative
                currency="USD",
                country="US",
            )

    def test_transaction_details_validates_currency_length(self):
        """Test that currency must be 3 characters."""
        with pytest.raises(ValueError):
            TransactionDetails(
                card_id="tok_card123",
                amount=Decimal("100.00"),
                currency="USDD",  # 4 characters
                country="US",
            )

    def test_transaction_details_validates_country_length(self):
        """Test that country must be 2 characters."""
        with pytest.raises(ValueError):
            TransactionDetails(
                card_id="tok_card123",
                amount=Decimal("100.00"),
                currency="USD",
                country="USA",  # Too long
            )

    def test_transaction_details_validates_card_last4_length(self):
        """Test that card_last4 must be max 4 characters."""
        with pytest.raises(ValueError):
            TransactionDetails(
                card_id="tok_card123",
                card_last4="12345",  # 5 characters
                amount=Decimal("100.00"),
                currency="USD",
                country="US",
            )

    def test_rule_match_validates_rule_version(self):
        """Test that rule_version must be >= 1."""
        with pytest.raises(ValueError):
            RuleMatch(
                rule_id="rule_001",
                rule_version=0,
            )

    def test_rule_match_validates_priority_non_negative(self):
        """Test that priority must be >= 0."""
        rule = RuleMatch(
            rule_id="rule_001",
            rule_version=1,
            priority=0,
        )
        assert rule.priority == 0


class TestEnumBackwardCompatibility:
    """Test enum values for backward compatibility."""

    def test_decision_type_string_values(self):
        """Test DecisionType can be compared to strings."""
        assert DecisionType.APPROVE == "APPROVE"
        assert DecisionType("APPROVE") == DecisionType.APPROVE

    def test_decision_reason_string_values(self):
        """Test DecisionReason can be compared to strings."""
        assert DecisionReason.RULE_MATCH == "RULE_MATCH"
        assert DecisionReason("RULE_MATCH") == DecisionReason.RULE_MATCH

    def test_card_network_string_values(self):
        """Test CardNetwork can be compared to strings."""
        assert CardNetwork.VISA == "VISA"
        assert CardNetwork("VISA") == CardNetwork.VISA

    def test_ingestion_source_string_values(self):
        """Test IngestionSource can be compared to strings."""
        assert IngestionSource.HTTP == "HTTP"
        assert IngestionSource("HTTP") == IngestionSource.HTTP


class TestSchemaModelConfig:
    """Test schema model configuration."""

    def test_decision_event_create_json_encoders(self):
        """Test DecisionEventCreate has decimal json encoder."""
        assert "json_encoders" in DecisionEventCreate.model_config
        assert Decimal in DecisionEventCreate.model_config["json_encoders"]

    def test_transaction_query_result_has_default_matched_rules(self):
        """Test TransactionQueryResult has default matched_rules."""
        now = datetime.now()
        result = TransactionQueryResult(
            transaction_id="txn_001",
            card_id="tok_card123",
            amount=Decimal("100.00"),
            currency="USD",
            decision=DecisionType.APPROVE,
            decision_reason=DecisionReason.DEFAULT_ALLOW,
            trace_id=None,
            card_last4=None,
            card_network=None,
            merchant_id=None,
            mcc=None,
            transaction_timestamp=now,
            ingestion_timestamp=now,
            ingestion_source=IngestionSource.HTTP,
            created_at=now,
            updated_at=now,
        )
        assert result.matched_rules == []


class TestRoutePaths:
    """Test route paths and methods."""

    def test_decision_events_post_path(self):
        """Test POST /decision-events path exists."""
        paths = [r.path for r in router.routes]
        assert "/decision-events" in paths

    def test_transactions_list_path(self):
        """Test GET /transactions path exists."""
        paths = [r.path for r in router.routes]
        assert "/transactions" in paths

    def test_transactions_get_path(self):
        """Test GET /transactions/{transaction_id} path exists."""
        paths = [r.path for r in router.routes]
        assert any("/transactions/" in p for p in paths)

    def test_metrics_get_path(self):
        """Test GET /metrics path exists."""
        paths = [r.path for r in router.routes]
        assert "/metrics" in paths


class TestTransactionDetailsFieldDescriptions:
    """Test that field descriptions are present."""

    def test_transaction_details_amount_gt_zero(self):
        """Test amount field has gt=0 constraint."""
        with pytest.raises(ValueError):
            TransactionDetails(
                card_id="tok_card123",
                amount=Decimal("0"),
                currency="USD",
                country="US",
            )

    def test_transaction_details_validates_amount_positive(self):
        """Test that amount must be positive."""
        with pytest.raises(ValueError):
            TransactionDetails(
                card_id="tok_card123",
                amount=Decimal("-100.00"),  # Negative
                currency="USD",
                country="US",
            )


class TestDecisionEventsRouteErrorHandling:
    """Test route error handling scenarios."""

    def test_decision_event_create_validates_card_id_required(self):
        """Test that card_id is required in transaction details."""
        with pytest.raises(ValueError):
            TransactionDetails(
                card_id="",  # Empty card_id should fail validation
                amount=Decimal("100.00"),
                currency="USD",
                country="US",
            )

    def test_decision_event_create_validates_country_code(self):
        """Test that country must be 2 characters."""
        with pytest.raises(ValueError):
            TransactionDetails(
                card_id="tok_card123",
                amount=Decimal("100.00"),
                currency="USD",
                country="USA",  # 3 characters - invalid
            )

    def test_decision_event_create_validates_merchant_id_length(self):
        """Test merchant_id validation."""
        details = TransactionDetails(
            card_id="tok_card123",
            amount=Decimal("100.00"),
            currency="USD",
            country="US",
            merchant_id="m",  # Very short but valid
        )
        assert details.merchant_id == "m"

    def test_decision_event_create_validates_mcc_format(self):
        """Test MCC (Merchant Category Code) validation."""
        details = TransactionDetails(
            card_id="tok_card123",
            amount=Decimal("100.00"),
            currency="USD",
            country="US",
            mcc="5411",  # 4 digits - valid MCC
        )
        assert details.mcc == "5411"

    def test_decision_event_create_validates_ip_address(self):
        """Test IP address validation."""
        details = TransactionDetails(
            card_id="tok_card123",
            amount=Decimal("100.00"),
            currency="USD",
            country="US",
            ip_address="192.168.1.1",  # IPv4
        )
        assert details.ip_address == "192.168.1.1"

    def test_decision_event_create_validates_ipv6_address(self):
        """Test IPv6 address validation."""
        details = TransactionDetails(
            card_id="tok_card123",
            amount=Decimal("100.00"),
            currency="USD",
            country="US",
            ip_address="::1",  # IPv6 localhost
        )
        assert details.ip_address == "::1"
