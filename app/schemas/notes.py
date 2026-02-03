"""Notes schemas for analyst notes on transactions."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class NoteType(str, Enum):
    """Type of analyst note for classification."""

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


class NoteCreate(BaseModel):
    """Schema for creating an analyst note."""

    note_type: NoteType = Field(default=NoteType.GENERAL, description="Type/classification of note")
    note_content: str = Field(..., min_length=1, max_length=10000, description="Note content")
    is_private: bool = Field(
        default=False,
        description="Whether note is private (only visible to author and supervisors)",
    )


class NoteUpdate(BaseModel):
    """Schema for updating an analyst note."""

    note_content: str = Field(
        ..., min_length=1, max_length=10000, description="Updated note content"
    )
    note_type: NoteType | None = Field(None, description="Updated note type")
    is_private: bool | None = Field(None, description="Updated privacy setting")


class NoteResponse(BaseModel):
    """Response schema for analyst note."""

    id: UUID
    transaction_id: UUID
    note_type: NoteType
    note_content: str

    # Author info
    analyst_id: str
    analyst_name: str | None = None
    analyst_email: str | None = None

    # Visibility
    is_private: bool
    is_system_generated: bool

    # Case linkage
    case_id: UUID | None = None

    # Timestamps
    created_at: datetime
    updated_at: datetime


class NoteListResponse(BaseModel):
    """Response schema for listing notes."""

    items: list[NoteResponse]
    total: int
    page_size: int
    has_more: bool
