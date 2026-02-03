"""Review schemas for transaction analyst workflow."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class TransactionStatus(str, Enum):
    """Transaction review status in workflow."""

    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class ReviewCreate(BaseModel):
    """Schema for creating a transaction review (usually auto-created)."""

    transaction_id: UUID = Field(..., description="Transaction to create review for")
    priority: int = Field(default=3, ge=1, le=5, description="Priority level (1=highest, 5=lowest)")


class ReviewUpdate(BaseModel):
    """Schema for updating a transaction review."""

    status: TransactionStatus | None = None
    priority: int | None = Field(None, ge=1, le=5)
    resolution_code: str | None = Field(None, max_length=64)
    resolution_notes: str | None = None


class ReviewResponse(BaseModel):
    """Response schema for transaction review."""

    id: UUID
    transaction_id: UUID
    status: TransactionStatus
    priority: int
    case_id: UUID | None = None

    # Assignment
    assigned_analyst_id: str | None = None
    assigned_at: datetime | None = None

    # Resolution
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    resolution_code: str | None = None
    resolution_notes: str | None = None

    # Escalation
    escalated_at: datetime | None = None
    escalated_to: str | None = None
    escalation_reason: str | None = None

    # Timestamps
    first_reviewed_at: datetime | None = None
    last_activity_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    # Associated transaction data (summary)
    transaction_amount: float | None = None
    transaction_currency: str | None = None
    decision: str | None = None
    risk_level: str | None = None


class StatusUpdateRequest(BaseModel):
    """Schema for updating transaction review status."""

    status: TransactionStatus = Field(
        ...,
        description="New status (must follow valid state transitions)",
    )
    resolution_notes: str | None = Field(
        None, description="Required when status is RESOLVED or CLOSED"
    )
    resolution_code: str | None = Field(
        None,
        max_length=64,
        description="Standardized resolution code (e.g., FRAUD_CONFIRMED, FALSE_POSITIVE)",
    )

    @field_validator("status")
    @classmethod
    def validate_resolution_fields(
        cls, v: TransactionStatus, info: dict[str, Any]
    ) -> TransactionStatus:
        """Ensure resolution fields are provided when resolving."""
        if v in (TransactionStatus.RESOLVED, TransactionStatus.CLOSED):
            # Resolution notes should typically be provided
            pass
        return v


class AssignRequest(BaseModel):
    """Schema for assigning a transaction review to an analyst."""

    analyst_id: str = Field(..., description="ID of the analyst to assign to")


class ResolveRequest(BaseModel):
    """Schema for resolving a transaction review."""

    resolution_code: str = Field(
        ...,
        max_length=64,
        description="Standardized resolution code (e.g., FRAUD_CONFIRMED, FALSE_POSITIVE)",
    )
    resolution_notes: str = Field(
        ...,
        description="Detailed notes explaining the resolution",
    )


class EscalateRequest(BaseModel):
    """Schema for escalating a transaction review."""

    escalate_to: str = Field(..., description="ID of the analyst/supervisor to escalate to")
    reason: str = Field(..., description="Reason for escalation")
