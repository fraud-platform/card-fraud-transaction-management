"""Schemas package for request/response models."""

from app.schemas.bulk import (
    BulkAssignRequest,
    BulkCreateCaseRequest,
    BulkOperationResponse,
    BulkStatusRequest,
)
from app.schemas.case import (
    CaseActivityResponse,
    CaseCreate,
    CaseListResponse,
    CaseResponse,
    CaseTransactionLink,
    CaseUpdate,
)
from app.schemas.decision_event import (
    CombinedTransactionView,
    DecisionEventCreate,
    DecisionEventResponse,
    DecisionReason,
    DecisionType,
    TransactionDetails,
    TransactionListResponse,
    TransactionQueryResult,
)
from app.schemas.notes import (
    NoteCreate,
    NoteListResponse,
    NoteResponse,
    NoteUpdate,
)
from app.schemas.review import (
    AssignRequest,
    EscalateRequest,
    ResolveRequest,
    ReviewCreate,
    ReviewResponse,
    ReviewUpdate,
    StatusUpdateRequest,
)
from app.schemas.worklist import (
    ClaimRequest,
    WorklistItem,
    WorklistResponse,
    WorklistStats,
)

__all__ = [
    # Decision events
    "DecisionEventCreate",
    "DecisionEventResponse",
    "DecisionType",
    "DecisionReason",
    "TransactionDetails",
    "TransactionListResponse",
    "TransactionQueryResult",
    "CombinedTransactionView",
    # Reviews
    "ReviewCreate",
    "ReviewUpdate",
    "ReviewResponse",
    "StatusUpdateRequest",
    "AssignRequest",
    "ResolveRequest",
    "EscalateRequest",
    # Notes
    "NoteCreate",
    "NoteUpdate",
    "NoteResponse",
    "NoteListResponse",
    # Cases
    "CaseCreate",
    "CaseUpdate",
    "CaseResponse",
    "CaseListResponse",
    "CaseTransactionLink",
    "CaseActivityResponse",
    # Worklist
    "WorklistItem",
    "WorklistResponse",
    "WorklistStats",
    "ClaimRequest",
    # Bulk
    "BulkAssignRequest",
    "BulkStatusRequest",
    "BulkCreateCaseRequest",
    "BulkOperationResponse",
]
