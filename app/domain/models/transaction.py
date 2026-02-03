"""Transaction models and schemas."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class TransactionStatus(str, Enum):
    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class FinalDecision(str, Enum):
    APPROVE = "APPROVE"
    DECLINE = "DECLINE"
    REVIEW = "REVIEW"
    ERROR = "ERROR"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FraudType(str, Enum):
    UNKNOWN = "UNKNOWN"
    AUTHENTICATION_FAILURE = "AUTHENTICATION_FAILURE"
    AVS_MISMATCH = "AVS_MISMATCH"
    CVV_FAILURE = "CVV_FAILURE"
    SPEED_PATTERN = "SPEED_PATTERN"
    VELOCITY = "VELOCITY"
    GEOGRAPHIC_ANOMALY = "GEOGRAPHIC_ANOMALY"
    BIN_COUNTRY_MISMATCH = "BIN_COUNTRY_MISMATCH"
    INTERNET_PHONE_MISMATCH = "INTERNET_PHONE_MISMATCH"
    ACCOUNT_TAKEOVER = "ACCOUNT_TAKEOVER"
    CARD_NOT_PRESENT_FRAUD = "CARD_NOT_PRESENT_FRAUD"
    IDENTITY_THEFT = "IDENTITY_THEFT"
    LOST_STOLEN_CARD = "LOST_STOLEN_CARD"
    COUNTERFEIT_CARD = "COUNTERFEIT_CARD"
    APPLICATION_FRAUD = "APPLICATION_FRAUD"
    FRAUD_REPORT = "FRAUD_REPORT"


class RuleMatchResult(str, Enum):
    APPROVE = "APPROVE"
    DECLINE = "DECLINE"
    REVIEW = "REVIEW"
    ERROR = "ERROR"


class IngestionSource(str, Enum):
    KAFKA = "KAFKA"
    HTTP = "HTTP"


class NoteType(str, Enum):
    GENERAL = "GENERAL"
    INITIAL_REVIEW = "INITIAL_REVIEW"
    CUSTOMER_CONTACT = "CUSTOMER_CONTACT"
    MERCHANT_CONTACT = "MERCHANT_CONTACT"
    BANK_CONTACT = "BANK_CONTACT"
    FRAUD_CONFIRMED = "FRAUD_CONFIRMED"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    ESCALATION = "ESCALATION"
    RESOLUTION = "RESOLUTION"
    LEGAL_HOLD = "LEGAL_HOLD"
    INTERNAL_REVIEW = "INTERNAL_REVIEW"


class LocationInfo(BaseModel):
    country_alpha3: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    ip_address: str | None = None
    ip_country_alpha3: str | None = None
    ip_city: str | None = None


class DeviceInfo(BaseModel):
    device_id: str | None = None
    device_type: str | None = None
    device_os: str | None = None
    device_browser: str | None = None
    device_fingerprint_hash: str | None = None


class RuleMatch(BaseModel):
    rule_id: UUID
    rule_version: int
    rule_name: str
    rule_namespace: str | None = None
    rule_category: str | None = None
    rule_priority: int | None = None
    match_result: RuleMatchResult
    match_reason_code: str | None = None
    match_reason_text: str | None = None
    match_score: float | None = None
    rule_conditions: dict[str, Any]
    matched_conditions: dict[str, Any] | None = None
    evaluated_at: datetime
    evaluation_duration_ms: int | None = None
    trace_id: str | None = None


class TransactionCreate(BaseModel):
    transaction_id: str = Field(..., description="Business transaction ID")
    trace_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None

    card_id: str
    account_id: str
    card_number_last_four: str | None = None
    card_brand: str | None = None
    card_type: str | None = None
    card_country_alpha3: str | None = None
    issuing_bank_name: str | None = None
    issuing_bank_id: str | None = None

    transaction_amount: Decimal
    transaction_currency: str = "USD"
    transaction_type: str | None = None
    merchant_id: str | None = None
    merchant_name: str | None = None
    merchant_category_code: str | None = None
    merchant_country_alpha3: str | None = None
    merchant_city: str | None = None
    merchant_state: str | None = None
    merchant_postal_code: str | None = None

    location: LocationInfo | None = None

    device: DeviceInfo | None = None

    final_decision: FinalDecision
    final_decision_reason_code: str | None = None
    final_score: float | None = None
    rules_evaluated_count: int = 0
    rules_approved_count: int = 0
    rules_declined_count: int = 0
    rules_review_count: int = 0

    risk_level: RiskLevel | None = None
    fraud_types_detected: list[FraudType] = []
    velocity_score: float | None = None
    velocity_window_minutes: int | None = None

    rule_matches: list[RuleMatch] = []

    event_timestamp: datetime

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
        }


class TransactionResponse(BaseModel):
    id: UUID
    transaction_id: str
    trace_id: str | None = None

    card_id: str
    account_id: str
    card_number_last_four: str | None = None
    card_brand: str | None = None
    card_type: str | None = None
    card_country_alpha3: str | None = None
    issuing_bank_name: str | None = None
    issuing_bank_id: str | None = None

    transaction_amount: float
    transaction_currency: str
    transaction_type: str | None = None
    merchant_id: str | None = None
    merchant_name: str | None = None
    merchant_category_code: str | None = None
    merchant_country_alpha3: str | None = None
    merchant_city: str | None = None
    merchant_state: str | None = None
    merchant_postal_code: str | None = None

    location: LocationInfo | None = None

    device: DeviceInfo | None = None

    final_decision: FinalDecision
    final_decision_reason_code: str | None = None
    final_score: float | None = None
    rules_evaluated_count: int = 0
    rules_approved_count: int = 0
    rules_declined_count: int = 0
    rules_review_count: int = 0

    risk_level: RiskLevel | None = None
    fraud_types_detected: list[FraudType] = []
    velocity_score: float | None = None
    velocity_window_minutes: int | None = None

    status: TransactionStatus
    priority: int
    assigned_analyst_id: str | None = None
    assigned_at: datetime | None = None
    first_reviewed_at: datetime | None = None
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    resolution_notes: str | None = None
    resolution_code: str | None = None

    rule_matches: list[RuleMatch] = []

    event_timestamp: datetime
    ingestion_timestamp: datetime

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
        }


class TransactionListResponse(BaseModel):
    items: list[TransactionResponse]
    total: int
    page_size: int
    has_more: bool


class AnalystNoteCreate(BaseModel):
    note_type: NoteType = NoteType.GENERAL
    note_content: str
    is_private: bool = False


class AnalystNoteResponse(BaseModel):
    id: UUID
    transaction_id: UUID
    analyst_id: str
    analyst_name: str | None = None
    analyst_email: str | None = None
    note_type: NoteType
    note_content: str
    is_private: bool
    is_system_generated: bool
    created_at: datetime
    updated_at: datetime


class StatusUpdate(BaseModel):
    status: TransactionStatus
    resolution_notes: str | None = None
    resolution_code: str | None = None


class AssignmentUpdate(BaseModel):
    assigned_analyst_id: str


class TransactionFilter(BaseModel):
    status: TransactionStatus | None = None
    final_decision: FinalDecision | None = None
    risk_level: RiskLevel | None = None
    assigned_analyst_id: str | None = None
    card_id: str | None = None
    merchant_id: str | None = None
    min_amount: float | None = None
    max_amount: float | None = None
    from_date: datetime | None = None
    to_date: datetime | None = None
    fraud_types: list[FraudType] | None = None
