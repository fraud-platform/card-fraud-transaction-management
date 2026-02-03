"""Decision event schemas (aligned with locked design).

These schemas match docs/12-decision-event-schema-v1.md and db/fraud_transactions_schema.sql.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class DecisionType(str, Enum):
    """Transaction decision type (engine decision outcome only)."""

    APPROVE = "APPROVE"
    DECLINE = "DECLINE"


class EvaluationType(str, Enum):
    """Evaluation type: AUTH (real-time) or MONITORING (analytics-only)."""

    AUTH = "AUTH"
    MONITORING = "MONITORING"


class DecisionReason(str, Enum):
    """Reason for the decision outcome."""

    RULE_MATCH = "RULE_MATCH"
    VELOCITY_MATCH = "VELOCITY_MATCH"
    SYSTEM_DECLINE = "SYSTEM_DECLINE"
    DEFAULT_ALLOW = "DEFAULT_ALLOW"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class CardNetwork(str, Enum):
    """Card network/brand."""

    VISA = "VISA"
    MASTERCARD = "MASTERCARD"
    AMEX = "AMEX"
    DISCOVER = "DISCOVER"
    OTHER = "OTHER"


class IngestionSource(str, Enum):
    """How the decision event was ingested."""

    HTTP = "HTTP"
    KAFKA = "KAFKA"


class RiskLevel(str, Enum):
    """Risk level classification."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RuleAction(str, Enum):
    """Action determined by a matched rule."""

    APPROVE = "APPROVE"
    DECLINE = "DECLINE"
    REVIEW = "REVIEW"


class TransactionDetails(BaseModel):
    """Transaction details from the decision event."""

    card_id: str = Field(..., description="Tokenized card identifier (never raw PAN)")
    card_last4: str | None = Field(
        None, max_length=4, description="Last 4 digits (only in TOKEN_PLUS_LAST4 mode)"
    )
    card_network: CardNetwork | None = None
    amount: Decimal = Field(..., gt=0, description="Transaction amount")
    currency: str = Field(..., min_length=3, max_length=3, description="ISO 4217 currency code")
    country: str = Field(
        ..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2 country code"
    )
    merchant_id: str | None = None
    mcc: str | None = Field(None, description="Merchant category code")
    ip_address: str | None = Field(None, description="Client IP address")

    @field_validator("card_id")
    @classmethod
    def validate_card_id(cls, v: str) -> str:
        """Ensure card_id is tokenized, not raw PAN."""
        if v.startswith("tok_") or v.startswith("pan_"):
            return v
        raise ValueError("card_id must be tokenized (tok_*) or pan_* for detection)")


class RuleMatch(BaseModel):
    """A rule that matched during fraud evaluation."""

    rule_id: str
    rule_version_id: UUID | None = Field(None, description="UUID of the rule version")
    rule_version: int | None = Field(None, ge=1, description="Rule version number (optional)")
    rule_name: str | None = None
    priority: int | None = Field(None, ge=0)
    matched_at: datetime | None = None
    rule_type: str | None = None
    match_reason_text: str | None = None

    # Enhanced fields for analyst workflow
    rule_action: RuleAction | None = Field(None, description="Action determined by the rule")
    conditions_met: list[str] | None = Field(
        None, description="Descriptions of conditions that matched"
    )
    condition_values: dict[str, Any] | None = Field(None, description="Actual values evaluated")


class DecisionEventCreate(BaseModel):
    """Decision event for ingestion (HTTP POST body)."""

    event_version: str = Field(default="1.0", description="Event schema version")
    transaction_id: str = Field(..., description="Business transaction ID (idempotency key)")
    evaluation_type: EvaluationType = Field(..., description="Evaluation type: AUTH or MONITORING")
    occurred_at: datetime = Field(..., description="When the transaction occurred")
    produced_at: datetime = Field(..., description="When the decision was produced")
    transaction: TransactionDetails
    decision: DecisionType
    decision_reason: DecisionReason
    matched_rules: list[RuleMatch] = Field(default_factory=list)

    # Ruleset metadata
    ruleset_key: str | None = Field(None, description="Ruleset key for identification")
    ruleset_id: UUID | None = Field(None, description="Ruleset UUID")
    ruleset_version: int | None = Field(None, description="Ruleset version number")

    # Enhanced fields for analyst workflow
    risk_level: RiskLevel | None = Field(None, description="Risk level classification")
    transaction_context: dict[str, Any] | None = Field(
        None, description="Full payload from rule engine with all evaluation context"
    )
    velocity_snapshot: dict[str, Any] | None = Field(
        None, description="All velocity states at decision time"
    )
    velocity_results: dict[str, Any] | None = Field(
        None, description="Per-rule velocity calculation results for matched rules"
    )
    engine_metadata: dict[str, Any] | None = Field(
        None, description="Engine mode, processing time, errors, and runtime metadata"
    )
    raw_payload: dict[str, Any] | None = Field(
        None, description="Allowlist of original fields (PCI-safe)"
    )

    model_config = {
        "json_encoders": {
            Decimal: lambda v: float(v),
        }
    }


class DecisionEventResponse(BaseModel):
    """Response after event ingestion."""

    status: str = "accepted"
    transaction_id: str
    ingestion_source: IngestionSource
    ingested_at: datetime


class TransactionQueryResult(BaseModel):
    """Transaction query result - matches fraud_gov.transactions table."""

    id: UUID | None = None
    transaction_id: str
    evaluation_type: EvaluationType | None = None
    card_id: str
    card_last4: str | None
    card_network: CardNetwork | None
    amount: Decimal
    currency: str
    merchant_id: str | None
    mcc: str | None
    decision: DecisionType
    decision_reason: DecisionReason
    decision_score: Decimal | None = None

    # Enhanced fields
    risk_level: RiskLevel | None = None

    ruleset_key: str | None = None
    ruleset_id: UUID | None = None
    ruleset_version: int | None = None
    transaction_context: dict[str, Any] | None = None
    velocity_snapshot: dict[str, Any] | None = None
    velocity_results: dict[str, Any] | None = None
    engine_metadata: dict[str, Any] | None = None
    transaction_timestamp: datetime
    ingestion_timestamp: datetime
    trace_id: str | None = None
    request_id: str | None = None
    session_id: str | None = None
    ingestion_source: IngestionSource
    created_at: datetime
    updated_at: datetime
    matched_rules: list[dict[str, Any]] = Field(default_factory=list)

    # Review status (when joined)
    review_status: str | None = None
    review_priority: int | None = None
    review_assigned_analyst_id: str | None = None
    review_case_id: UUID | None = None


class TransactionListResponse(BaseModel):
    """Paginated transaction list with keyset pagination."""

    items: list[TransactionQueryResult]
    total: int
    page_size: int
    has_more: bool = False
    next_cursor: str | None = Field(
        None, description="Cursor for next page (null if no more pages)"
    )


class CombinedTransactionView(BaseModel):
    """Combined AUTH + MONITORING view for a transaction_id."""

    transaction_id: str
    auth: TransactionQueryResult | None = None
    monitoring: TransactionQueryResult | None = None


class TransactionOverview(BaseModel):
    """Combined transaction overview for analyst UI (single call).

    Includes transaction, review, notes, case, and optional matched_rules.
    """

    transaction: TransactionQueryResult
    review: dict[str, Any] | None = Field(None, description="Transaction review details if exists")
    notes: list[dict[str, Any]] = Field(
        default_factory=list, description="Analyst notes on this transaction"
    )
    case: dict[str, Any] | None = Field(
        None, description="Case details if transaction is linked to a case"
    )
    matched_rules: list[dict[str, Any]] = Field(
        default_factory=list, description="Matched rules (only if include_rules=true)"
    )
    last_activity_at: datetime | None = Field(
        None, description="Last activity timestamp across review/notes/case"
    )


class ErrorResponse(BaseModel):
    """Error response."""

    error: str
    details: dict[str, Any] | None = None
