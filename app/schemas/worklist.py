"""Worklist schemas for analyst transaction queue management."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    """Risk level classification."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TransactionStatus(str, Enum):
    """Transaction review status in workflow."""

    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class WorklistItem(BaseModel):
    """A single item in the analyst worklist."""

    # Review info
    review_id: UUID
    transaction_id: UUID
    status: TransactionStatus
    priority: int

    # Transaction summary
    card_id: str
    card_last4: str | None = None
    transaction_amount: float
    transaction_currency: str
    transaction_timestamp: datetime

    # Decision info
    decision: str
    decision_reason: str
    decision_score: float | None = None
    risk_level: RiskLevel | None = None

    # Assignment
    assigned_analyst_id: str | None = None
    assigned_at: datetime | None = None

    # Case linkage
    case_id: UUID | None = None
    case_number: str | None = None

    # Timestamps
    first_reviewed_at: datetime | None = None
    last_activity_at: datetime | None = None
    created_at: datetime

    # Additional metadata
    merchant_id: str | None = None
    merchant_category_code: str | None = None
    trace_id: str | None = None


class WorklistResponse(BaseModel):
    """Response schema for worklist queries."""

    items: list[WorklistItem]
    total: int
    page_size: int
    has_more: bool
    next_cursor: str | None = None


class WorklistStats(BaseModel):
    """Statistics for analyst worklist."""

    # Unassigned counts
    unassigned_total: int
    unassigned_by_priority: dict[str, int]  # {"1": 10, "2": 5, ...}
    unassigned_by_risk: dict[str, int]  # {"CRITICAL": 5, "HIGH": 10, ...}

    # Assigned to current analyst
    my_assigned_total: int
    my_assigned_by_status: dict[str, int]  # {"PENDING": 2, "IN_REVIEW": 5, ...}

    # Resolution stats (today)
    resolved_today: int
    resolved_by_code: dict[str, int]  # {"FRAUD_CONFIRMED": 5, "FALSE_POSITIVE": 3, ...}

    # Average resolution time (in minutes)
    avg_resolution_minutes: float | None = None


class ClaimRequest(BaseModel):
    """Schema for claiming the next unassigned transaction."""

    priority_filter: int | None = Field(
        None,
        ge=1,
        le=5,
        description="Only claim transactions at or below this priority (lower = higher priority)",
    )
    risk_level_filter: RiskLevel | None = Field(
        None, description="Only claim transactions at this risk level or higher"
    )
