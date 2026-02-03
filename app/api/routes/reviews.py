"""API routes for transaction review management."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import RequireTxnView
from app.schemas.review import (
    AssignRequest,
    EscalateRequest,
    ResolveRequest,
    ReviewResponse,
    StatusUpdateRequest,
)
from app.services.review_service import ReviewService

router = APIRouter(prefix="/transactions", tags=["reviews"])


def get_review_service(session: AsyncSession = Depends(get_session)) -> ReviewService:
    """Get review service instance."""
    return ReviewService(session)


@router.get("/{transaction_id}/review", response_model=ReviewResponse)
async def get_review(
    transaction_id: UUID,
    current_user: RequireTxnView,
    review_service: ReviewService = Depends(get_review_service),
) -> dict:
    """Get or create review for a transaction."""
    return await review_service.get_review_by_transaction(transaction_id)


@router.post("/{transaction_id}/review", response_model=ReviewResponse)
async def create_review(
    transaction_id: UUID,
    current_user: RequireTxnView,
    review_service: ReviewService = Depends(get_review_service),
) -> dict:
    """Create a new review for a transaction (if not exists)."""
    return await review_service.get_review_by_transaction(transaction_id)


@router.patch(
    "/{transaction_id}/review/status",
    response_model=ReviewResponse,
)
async def update_review_status(
    transaction_id: UUID,
    request: StatusUpdateRequest,
    current_user: RequireTxnView,
    review_service: ReviewService = Depends(get_review_service),
) -> dict:
    """Update transaction review status.

    Valid status transitions:
    - PENDING → IN_REVIEW, ESCALATED, RESOLVED, CLOSED
    - IN_REVIEW → PENDING, ESCALATED, RESOLVED, CLOSED
    - ESCALATED → IN_REVIEW, RESOLVED, CLOSED
    - RESOLVED → CLOSED
    - CLOSED → (none)
    """
    review = await review_service.get_review_by_transaction(transaction_id)
    return await review_service.update_status(
        review_id=review["id"],
        status=request.status.value,
        resolution_notes=request.resolution_notes,
        resolution_code=request.resolution_code,
        resolved_by=current_user.user_id,
    )


@router.patch(
    "/{transaction_id}/review/assign",
    response_model=ReviewResponse,
)
async def assign_review(
    transaction_id: UUID,
    request: AssignRequest,
    current_user: RequireTxnView,
    review_service: ReviewService = Depends(get_review_service),
) -> dict:
    """Assign a transaction review to an analyst."""
    review = await review_service.get_review_by_transaction(transaction_id)
    return await review_service.assign_analyst(
        review_id=review["id"],
        analyst_id=request.analyst_id,
    )


@router.post("/{transaction_id}/review/resolve", response_model=ReviewResponse)
async def resolve_review(
    transaction_id: UUID,
    request: ResolveRequest,
    current_user: RequireTxnView,
    review_service: ReviewService = Depends(get_review_service),
) -> dict:
    """Resolve a transaction review."""
    review = await review_service.get_review_by_transaction(transaction_id)
    return await review_service.resolve(
        review_id=review["id"],
        resolution_code=request.resolution_code,
        resolution_notes=request.resolution_notes,
        resolved_by=current_user.user_id,
    )


@router.post("/{transaction_id}/review/escalate", response_model=ReviewResponse)
async def escalate_review(
    transaction_id: UUID,
    request: EscalateRequest,
    current_user: RequireTxnView,
    review_service: ReviewService = Depends(get_review_service),
) -> dict:
    """Escalate a transaction review to a supervisor."""
    review = await review_service.get_review_by_transaction(transaction_id)
    return await review_service.escalate(
        review_id=review["id"],
        escalate_to=request.escalate_to,
        reason=request.reason,
    )
