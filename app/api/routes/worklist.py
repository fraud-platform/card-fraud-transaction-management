"""API routes for analyst worklist management."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import RequireTxnView
from app.schemas.worklist import (
    ClaimRequest,
    WorklistItem,
    WorklistResponse,
    WorklistStats,
)
from app.services.worklist_service import WorklistService

router = APIRouter(prefix="/worklist", tags=["worklist"])


def get_worklist_service(session: AsyncSession = Depends(get_session)) -> WorklistService:
    """Get worklist service instance."""
    return WorklistService(session)


@router.get("", response_model=WorklistResponse)
async def get_worklist(
    current_user: RequireTxnView,
    status: str | None = None,
    assigned_only: bool = False,
    priority_filter: int | None = Query(
        None, ge=1, le=5, description="Only show items at or below this priority (1=highest)"
    ),
    risk_level_filter: str | None = Query(
        None, description="Only show items at this risk level (LOW|MEDIUM|HIGH|CRITICAL)"
    ),
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = None,
    worklist_service: WorklistService = Depends(get_worklist_service),
) -> dict:
    """Get worklist for the current analyst.

    - Use `assigned_only=true` to get only items assigned to you
    - Use `status` to filter by review status (PENDING, IN_REVIEW, ESCALATED, etc.)
    - Use `priority_filter` to only show high-priority items (1=highest, 5=lowest)
    - Use `risk_level_filter` to only show items at a specific risk level
    """
    analyst_id = current_user.user_id if assigned_only else None
    items, next_cursor, total = await worklist_service.get_worklist(
        analyst_id=analyst_id,
        status=status,
        assigned_only=assigned_only,
        priority_filter=priority_filter,
        risk_level_filter=risk_level_filter,
        limit=limit,
        cursor=cursor,
    )
    return {
        "items": items,
        "total": total,
        "page_size": limit,
        "has_more": next_cursor is not None,
        "next_cursor": next_cursor,
    }


@router.get("/stats", response_model=WorklistStats)
async def get_worklist_stats(
    current_user: RequireTxnView,
    worklist_service: WorklistService = Depends(get_worklist_service),
) -> dict:
    """Get worklist statistics.

    Returns unassigned counts and current analyst's assigned counts.
    """
    return await worklist_service.get_worklist_stats(analyst_id=current_user.user_id)


@router.get("/unassigned", response_model=WorklistResponse)
async def get_unassigned(
    current_user: RequireTxnView,
    status: str | None = None,
    priority_filter: int | None = Query(
        None, ge=1, le=5, description="Only show items at or below this priority (1=highest)"
    ),
    risk_level_filter: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = None,
    worklist_service: WorklistService = Depends(get_worklist_service),
) -> dict:
    """Get unassigned transactions available for claim.

    - Use `priority_filter` to only show high-priority items (1=highest, 5=lowest)
    - Use `risk_level_filter` to only show items at or above this risk level
    """
    status_filter = [status] if status else None
    items, next_cursor, total = await worklist_service.get_unassigned(
        status=status_filter,
        priority_filter=priority_filter,
        risk_level_filter=risk_level_filter,
        limit=limit,
        cursor=cursor,
    )
    return {
        "items": items,
        "total": total,
        "page_size": limit,
        "has_more": next_cursor is not None,
        "next_cursor": next_cursor,
    }


@router.post("/claim", response_model=WorklistItem)
async def claim_next(
    request: ClaimRequest,
    current_user: RequireTxnView,
    worklist_service: WorklistService = Depends(get_worklist_service),
):
    """Claim the next unassigned transaction.

    Automatically assigns the highest-priority unassigned transaction
    (matching any filters) to the current analyst.

    Returns the claimed worklist item, or 404 if no items are available.
    """
    result = await worklist_service.claim_next(
        analyst_id=current_user.user_id,
        priority_filter=request.priority_filter,
        risk_level_filter=request.risk_level_filter,
    )
    if result is None:
        from app.core.errors import NotFoundError

        raise NotFoundError("No unassigned transactions available to claim")
    return result
