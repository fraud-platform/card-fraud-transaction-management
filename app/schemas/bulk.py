"""Bulk operation schemas for batch processing."""

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class TransactionStatus(str, Enum):
    """Transaction review status in workflow."""

    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class BulkAssignRequest(BaseModel):
    """Schema for bulk assigning transactions to an analyst."""

    transaction_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of transaction IDs to assign (max 100 per request)",
    )
    analyst_id: str = Field(..., description="Analyst ID to assign all transactions to")


class BulkStatusRequest(BaseModel):
    """Schema for bulk updating transaction status."""

    transaction_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of transaction IDs to update (max 100 per request)",
    )
    status: TransactionStatus = Field(..., description="New status to set")
    resolution_code: str | None = Field(
        None,
        max_length=64,
        description="Resolution code (required for RESOLVED/CLOSED status)",
    )
    resolution_notes: str | None = Field(None, description="Resolution notes")


class BulkCreateCaseRequest(BaseModel):
    """Schema for bulk creating a case from transactions."""

    transaction_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of transaction IDs to include in case (max 100 per request)",
    )
    case_type: str = Field(
        ...,
        description="Type of case (INVESTIGATION, DISPUTE, CHARGEBACK, etc.)",
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Case title",
    )
    description: str | None = Field(None, max_length=5000, description="Case description")
    assigned_analyst_id: str | None = Field(None, description="Analyst to assign case to")
    risk_level: str | None = Field(None, description="Initial risk level")


class BulkOperationResult(BaseModel):
    """Result of a single bulk operation item."""

    transaction_id: UUID
    success: bool
    error_message: str | None = None
    error_code: str | None = None


class BulkOperationResponse(BaseModel):
    """Response schema for bulk operations."""

    # Summary
    total_requested: int = Field(..., description="Total items in request")
    successful: int = Field(..., description="Number of successful operations")
    failed: int = Field(..., description="Number of failed operations")

    # Detailed results
    results: list[BulkOperationResult] = Field(
        ...,
        description="Individual result for each transaction",
    )

    # Created resources (for case creation)
    created_case_id: UUID | None = Field(None, description="ID of created case (if applicable)")
    created_case_number: str | None = Field(
        None, description="Case number of created case (if applicable)"
    )

    # Errors summary
    error_summary: dict[str, int] | None = Field(
        None,
        description="Summary of errors by error code",
    )
