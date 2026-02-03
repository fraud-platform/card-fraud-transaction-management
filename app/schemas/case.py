"""Case schemas for grouping related transactions."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    """Risk level classification."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CaseType(str, Enum):
    """Type of case for grouping related transactions."""

    INVESTIGATION = "INVESTIGATION"
    DISPUTE = "DISPUTE"
    CHARGEBACK = "CHARGEBACK"
    FRAUD_RING = "FRAUD_RING"
    ACCOUNT_TAKEOVER = "ACCOUNT_TAKEOVER"
    PATTERN_ANALYSIS = "PATTERN_ANALYSIS"
    MERCHANT_REVIEW = "MERCHANT_REVIEW"
    CARD_COMPROMISE = "CARD_COMPROMISE"
    OTHER = "OTHER"


class CaseStatus(str, Enum):
    """Status of case workflow."""

    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    PENDING_INFO = "PENDING_INFO"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class CaseCreate(BaseModel):
    """Schema for creating a case."""

    case_type: CaseType = Field(..., description="Type of case")
    title: str = Field(..., min_length=1, max_length=512, description="Case title")
    description: str | None = Field(None, max_length=5000, description="Case description")
    transaction_ids: list[UUID] = Field(
        default_factory=list,
        description="Transaction IDs to add to the case",
    )
    assigned_analyst_id: str | None = Field(None, description="Analyst to assign the case to")
    risk_level: RiskLevel | None = Field(None, description="Initial risk level assessment")


class CaseUpdate(BaseModel):
    """Schema for updating a case."""

    case_status: CaseStatus | None = Field(None, description="New case status")
    case_type: CaseType | None = Field(None, description="Updated case type")
    title: str | None = Field(None, min_length=1, max_length=512, description="Updated title")
    description: str | None = Field(None, max_length=5000, description="Updated description")
    assigned_analyst_id: str | None = Field(None, description="Reassign to different analyst")
    risk_level: RiskLevel | None = Field(None, description="Updated risk level")
    resolution_summary: str | None = Field(
        None,
        max_length=5000,
        description="Resolution summary (required when closing/resolving)",
    )


class CaseResponse(BaseModel):
    """Response schema for case."""

    id: UUID
    case_number: str
    case_type: CaseType
    case_status: CaseStatus

    # Assignment
    assigned_analyst_id: str | None = None
    assigned_at: datetime | None = None

    # Details
    title: str
    description: str | None = None

    # Aggregates
    total_transaction_count: int
    total_transaction_amount: float

    # Risk
    risk_level: RiskLevel | None = None

    # Resolution
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    resolution_summary: str | None = None

    # Timestamps
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None


class CaseTransactionLink(BaseModel):
    """Schema for linking a transaction to a case."""

    transaction_id: UUID = Field(..., description="Transaction to add/remove from case")


class CaseListResponse(BaseModel):
    """Response schema for listing cases."""

    items: list[CaseResponse]
    total: int
    page_size: int
    has_more: bool
    next_cursor: str | None = None


class CaseActivityResponse(BaseModel):
    """Response schema for case activity log entry."""

    id: int
    case_id: UUID
    activity_type: str
    activity_description: str

    # Actor
    analyst_id: str | None = None
    analyst_name: str | None = None

    # Change details
    old_values: dict[str, Any] | None = None
    new_values: dict[str, Any] | None = None

    # Related transaction
    transaction_id: UUID | None = None

    # Timestamp
    created_at: datetime
