"""Unit tests for domain models (transaction models, enums, schemas)."""

from datetime import datetime
from decimal import Decimal
from uuid import uuid7

from app.domain.models.transaction import (
    AnalystNoteCreate,
    AssignmentUpdate,
    DeviceInfo,
    FinalDecision,
    FraudType,
    IngestionSource,
    LocationInfo,
    NoteType,
    RiskLevel,
    RuleMatch,
    RuleMatchResult,
    StatusUpdate,
    TransactionCreate,
    TransactionFilter,
    TransactionListResponse,
    TransactionResponse,
    TransactionStatus,
)


class TestEnums:
    """Test enum classes."""

    def test_transaction_status_values(self):
        """Test TransactionStatus enum has all expected values."""
        assert TransactionStatus.PENDING == "PENDING"
        assert TransactionStatus.IN_REVIEW == "IN_REVIEW"
        assert TransactionStatus.ESCALATED == "ESCALATED"
        assert TransactionStatus.RESOLVED == "RESOLVED"
        assert TransactionStatus.CLOSED == "CLOSED"

    def test_final_decision_values(self):
        """Test FinalDecision enum has all expected values."""
        assert FinalDecision.APPROVE == "APPROVE"
        assert FinalDecision.DECLINE == "DECLINE"
        assert FinalDecision.REVIEW == "REVIEW"
        assert FinalDecision.ERROR == "ERROR"

    def test_risk_level_values(self):
        """Test RiskLevel enum has all expected values."""
        assert RiskLevel.LOW == "LOW"
        assert RiskLevel.MEDIUM == "MEDIUM"
        assert RiskLevel.HIGH == "HIGH"
        assert RiskLevel.CRITICAL == "CRITICAL"

    def test_fraud_type_values(self):
        """Test FraudType enum has expected fraud types."""
        assert FraudType.UNKNOWN == "UNKNOWN"
        assert FraudType.VELOCITY == "VELOCITY"
        assert FraudType.GEOGRAPHIC_ANOMALY == "GEOGRAPHIC_ANOMALY"
        assert FraudType.LOST_STOLEN_CARD == "LOST_STOLEN_CARD"

    def test_rule_match_result_values(self):
        """Test RuleMatchResult enum has all expected values."""
        assert RuleMatchResult.APPROVE == "APPROVE"
        assert RuleMatchResult.DECLINE == "DECLINE"
        assert RuleMatchResult.REVIEW == "REVIEW"
        assert RuleMatchResult.ERROR == "ERROR"

    def test_ingestion_source_values(self):
        """Test IngestionSource enum has all expected values."""
        assert IngestionSource.KAFKA == "KAFKA"
        assert IngestionSource.HTTP == "HTTP"

    def test_note_type_values(self):
        """Test NoteType enum has all expected values."""
        assert NoteType.GENERAL == "GENERAL"
        assert NoteType.FRAUD_CONFIRMED == "FRAUD_CONFIRMED"
        assert NoteType.RESOLUTION == "RESOLUTION"


class TestLocationInfo:
    """Test LocationInfo model."""

    def test_location_info_empty(self):
        """Test creating empty LocationInfo."""
        location = LocationInfo()
        assert location.country_alpha3 is None
        assert location.city is None
        assert location.latitude is None

    def test_location_info_with_data(self):
        """Test creating LocationInfo with data."""
        location = LocationInfo(
            country_alpha3="USA",
            city="New York",
            state="NY",
            postal_code="10001",
            latitude=40.7128,
            longitude=-74.0060,
            ip_address="192.168.1.1",
            ip_country_alpha3="USA",
            ip_city="New York",
        )
        assert location.country_alpha3 == "USA"
        assert location.city == "New York"
        assert location.latitude == 40.7128

    def test_location_info_model_dump(self):
        """Test LocationInfo model_dump."""
        location = LocationInfo(country_alpha3="GBR", city="London")
        data = location.model_dump()
        assert data["country_alpha3"] == "GBR"
        assert data["city"] == "London"


class TestDeviceInfo:
    """Test DeviceInfo model."""

    def test_device_info_empty(self):
        """Test creating empty DeviceInfo."""
        device = DeviceInfo()
        assert device.device_id is None
        assert device.device_type is None

    def test_device_info_with_data(self):
        """Test creating DeviceInfo with data."""
        device = DeviceInfo(
            device_id="device_123",
            device_type="mobile",
            device_os="iOS",
            device_browser="Safari",
            device_fingerprint_hash="abc123hash",
        )
        assert device.device_id == "device_123"
        assert device.device_type == "mobile"
        assert device.device_fingerprint_hash == "abc123hash"


class TestRuleMatch:
    """Test RuleMatch model."""

    def test_rule_match_required_fields(self):
        """Test creating RuleMatch with required fields only."""
        rule_match = RuleMatch(
            rule_id=uuid7(),
            rule_version=1,
            rule_name="test_rule",
            match_result=RuleMatchResult.APPROVE,
            rule_conditions={},
            evaluated_at=datetime.now(),
        )
        assert rule_match.rule_id is not None
        assert rule_match.rule_version == 1
        assert rule_match.match_result == RuleMatchResult.APPROVE

    def test_rule_match_with_optional_fields(self):
        """Test creating RuleMatch with all fields."""
        rule_id = uuid7()
        now = datetime.now()
        rule_match = RuleMatch(
            rule_id=rule_id,
            rule_version=2,
            rule_name="full_rule",
            rule_namespace="fraud",
            rule_category="velocity",
            rule_priority=10,
            match_result=RuleMatchResult.REVIEW,
            match_reason_code="HIGH_VELOCITY",
            match_reason_text="Transaction velocity exceeded threshold",
            match_score=0.85,
            rule_conditions={"amount": {"$gt": 1000}},
            matched_conditions={"amount": 1500},
            evaluated_at=now,
            evaluation_duration_ms=50,
            trace_id="trace_123",
        )
        assert rule_match.rule_namespace == "fraud"
        assert rule_match.match_score == 0.85
        assert rule_match.evaluation_duration_ms == 50


class TestTransactionCreate:
    """Test TransactionCreate model."""

    def test_transaction_create_minimal(self):
        """Test creating TransactionCreate with minimal required fields."""
        txn = TransactionCreate(
            transaction_id="txn_001",
            card_id="tok_card123",
            account_id="acc_001",
            transaction_amount=Decimal("100.00"),
            final_decision=FinalDecision.APPROVE,
            event_timestamp=datetime.now(),
        )
        assert txn.transaction_id == "txn_001"
        assert txn.card_id == "tok_card123"
        assert txn.transaction_amount == Decimal("100.00")
        assert txn.transaction_currency == "USD"
        assert txn.rules_evaluated_count == 0

    def test_transaction_create_full(self):
        """Test creating TransactionCreate with all fields."""
        now = datetime.now()
        txn = TransactionCreate(
            transaction_id="txn_002",
            trace_id="trace_123",
            card_id="tok_card456",
            account_id="acc_002",
            card_number_last_four="1234",
            card_brand="VISA",
            card_type="CREDIT",
            card_country_alpha3="USA",
            transaction_amount=Decimal("2500.50"),
            transaction_currency="EUR",
            transaction_type="PURCHASE",
            merchant_id="merchant_001",
            merchant_name="Test Merchant",
            merchant_category_code="5411",
            final_decision=FinalDecision.DECLINE,
            final_decision_reason_code="HIGH_RISK",
            final_score=0.92,
            risk_level=RiskLevel.HIGH,
            fraud_types_detected=[FraudType.VELOCITY, FraudType.GEOGRAPHIC_ANOMALY],
            event_timestamp=now,
        )
        assert txn.final_decision == FinalDecision.DECLINE
        assert txn.risk_level == RiskLevel.HIGH
        assert len(txn.fraud_types_detected) == 2

    def test_transaction_create_with_location_and_device(self):
        """Test creating TransactionCreate with location and device."""
        location = LocationInfo(country_alpha3="CAN", city="Toronto")
        device = DeviceInfo(device_id="device_abc", device_type="desktop")
        txn = TransactionCreate(
            transaction_id="txn_003",
            card_id="tok_card789",
            account_id="acc_003",
            transaction_amount=Decimal("75.00"),
            final_decision=FinalDecision.APPROVE,
            location=location,
            device=device,
            event_timestamp=datetime.now(),
        )
        assert txn.location is not None
        assert txn.location.city == "Toronto"
        assert txn.device is not None
        assert txn.device.device_id == "device_abc"


class TestTransactionResponse:
    """Test TransactionResponse model."""

    def test_transaction_response_creation(self):
        """Test creating TransactionResponse."""
        txn_id = uuid7()
        now = datetime.now()
        response = TransactionResponse(
            id=txn_id,
            transaction_id="txn_response_001",
            card_id="tok_card111",
            account_id="acc_111",
            transaction_amount=150.00,
            transaction_currency="USD",
            final_decision=FinalDecision.APPROVE,
            status=TransactionStatus.PENDING,
            priority=1,
            event_timestamp=now,
            ingestion_timestamp=now,
        )
        assert response.id == txn_id
        assert response.transaction_id == "txn_response_001"
        assert response.transaction_amount == 150.00
        assert response.status == TransactionStatus.PENDING


class TestTransactionListResponse:
    """Test TransactionListResponse model."""

    def test_transaction_list_response(self):
        """Test creating TransactionListResponse."""
        response = TransactionListResponse(
            items=[],
            total=0,
            page_size=50,
            has_more=False,
        )
        assert response.items == []
        assert response.total == 0
        assert response.page_size == 50
        assert response.has_more is False

    def test_transaction_list_response_with_items(self):
        """Test TransactionListResponse with items."""
        now = datetime.now()
        items = [
            TransactionResponse(
                id=uuid7(),
                transaction_id=f"txn_{i}",
                card_id=f"tok_{i}",
                account_id="acc_001",
                transaction_amount=100.00,
                transaction_currency="USD",
                final_decision=FinalDecision.APPROVE,
                status=TransactionStatus.PENDING,
                priority=1,
                event_timestamp=now,
                ingestion_timestamp=now,
            )
            for i in range(3)
        ]
        response = TransactionListResponse(
            items=items,
            total=100,
            page_size=3,
            has_more=True,
        )
        assert len(response.items) == 3
        assert response.total == 100
        assert response.has_more is True


class TestAnalystNoteCreate:
    """Test AnalystNoteCreate model."""

    def test_analyst_note_create_default(self):
        """Test creating AnalystNoteCreate with defaults."""
        note = AnalystNoteCreate(note_content="Test note content")
        assert note.note_type == NoteType.GENERAL
        assert note.is_private is False

    def test_analyst_note_create_full(self):
        """Test creating AnalystNoteCreate with all fields."""
        note = AnalystNoteCreate(
            note_type=NoteType.FRAUD_CONFIRMED,
            note_content="Confirmed fraudulent activity",
            is_private=True,
        )
        assert note.note_type == NoteType.FRAUD_CONFIRMED
        assert note.is_private is True


class TestStatusUpdate:
    """Test StatusUpdate model."""

    def test_status_update(self):
        """Test creating StatusUpdate."""
        update = StatusUpdate(
            status=TransactionStatus.RESOLVED,
            resolution_notes="Transaction reviewed and cleared",
            resolution_code="FALSE_POSITIVE",
        )
        assert update.status == TransactionStatus.RESOLVED
        assert update.resolution_code == "FALSE_POSITIVE"


class TestAssignmentUpdate:
    """Test AssignmentUpdate model."""

    def test_assignment_update(self):
        """Test creating AssignmentUpdate."""
        update = AssignmentUpdate(assigned_analyst_id="analyst_001")
        assert update.assigned_analyst_id == "analyst_001"


class TestTransactionFilter:
    """Test TransactionFilter model."""

    def test_transaction_filter_empty(self):
        """Test creating empty TransactionFilter."""
        filter_obj = TransactionFilter()
        assert filter_obj.status is None
        assert filter_obj.card_id is None

    def test_transaction_filter_with_values(self):
        """Test creating TransactionFilter with values."""
        now = datetime.now()
        filter_obj = TransactionFilter(
            status=TransactionStatus.IN_REVIEW,
            final_decision=FinalDecision.REVIEW,
            risk_level=RiskLevel.HIGH,
            card_id="tok_card123",
            merchant_id="merchant_001",
            min_amount=100.0,
            max_amount=1000.0,
            from_date=now,
            to_date=now,
        )
        assert filter_obj.status == TransactionStatus.IN_REVIEW
        assert filter_obj.min_amount == 100.0
        assert filter_obj.max_amount == 1000.0
