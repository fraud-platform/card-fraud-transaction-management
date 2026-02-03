"""API routes for case management."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import RequireTxnView
from app.schemas.case import (
    CaseActivityResponse,
    CaseCreate,
    CaseListResponse,
    CaseResponse,
    CaseTransactionLink,
    CaseUpdate,
)
from app.services.case_service import CaseService

router = APIRouter(prefix="/cases", tags=["cases"])


def get_case_service(session: AsyncSession = Depends(get_session)) -> CaseService:
    """Get case service instance."""
    return CaseService(session)


@router.get("", response_model=CaseListResponse)
async def list_cases(
    current_user: RequireTxnView,
    case_status: str | None = None,
    case_type: str | None = None,
    assigned_to_me: bool = False,
    risk_level: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = None,
    case_service: CaseService = Depends(get_case_service),
) -> dict:
    """List cases with optional filters.

    - Use `assigned_to_me=true` to only show cases assigned to current analyst
    """
    assigned_analyst_id = current_user.user_id if assigned_to_me else None
    cases, next_cursor, total = await case_service.list_cases(
        case_status=case_status,
        case_type=case_type,
        assigned_analyst_id=assigned_analyst_id,
        risk_level=risk_level,
        limit=limit,
        cursor=cursor,
    )
    return {
        "items": cases,
        "total": total,
        "page_size": limit,
        "has_more": next_cursor is not None,
        "next_cursor": next_cursor,
    }


@router.post("", response_model=CaseResponse, status_code=201)
async def create_case(
    request: CaseCreate,
    current_user: RequireTxnView,
    case_service: CaseService = Depends(get_case_service),
) -> dict:
    """Create a new case from transactions.

    Transactions are linked to the case via their review records.
    """
    return await case_service.create_case(
        case_type=request.case_type.value,
        title=request.title,
        description=request.description,
        transaction_ids=request.transaction_ids,
        assigned_analyst_id=request.assigned_analyst_id,
        risk_level=request.risk_level.value if request.risk_level else None,
        analyst_id=current_user.user_id,
        analyst_name=current_user.name,
    )


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: UUID,
    current_user: RequireTxnView,
    case_service: CaseService = Depends(get_case_service),
) -> dict:
    """Get a case by ID."""
    return await case_service.get_case(case_id)


@router.get("/number/{case_number}", response_model=CaseResponse)
async def get_case_by_number(
    case_number: str,
    current_user: RequireTxnView,
    case_service: CaseService = Depends(get_case_service),
) -> dict:
    """Get a case by its case number."""
    return await case_service.get_case_by_number(case_number)


@router.patch("/{case_id}", response_model=CaseResponse)
async def update_case(
    case_id: UUID,
    request: CaseUpdate,
    current_user: RequireTxnView,
    case_service: CaseService = Depends(get_case_service),
) -> dict:
    """Update a case.

    To resolve/close a case, include resolution_summary.
    """
    return await case_service.update_case(
        case_id=case_id,
        case_status=request.case_status.value if request.case_status else None,
        case_type=request.case_type.value if request.case_type else None,
        title=request.title,
        description=request.description,
        assigned_analyst_id=request.assigned_analyst_id,
        risk_level=request.risk_level.value if request.risk_level else None,
        resolution_summary=request.resolution_summary,
        analyst_id=current_user.user_id,
        analyst_name=current_user.name,
    )


@router.get("/{case_id}/transactions")
async def get_case_transactions(
    case_id: UUID,
    current_user: RequireTxnView,
    limit: int = Query(100, ge=1, le=500),
    case_service: CaseService = Depends(get_case_service),
) -> list[dict]:
    """Get all transactions associated with a case."""
    return await case_service.get_case_transactions(
        case_id=case_id,
        limit=limit,
    )


@router.post("/{case_id}/transactions", response_model=CaseResponse)
async def add_transaction_to_case(
    case_id: UUID,
    request: CaseTransactionLink,
    current_user: RequireTxnView,
    case_service: CaseService = Depends(get_case_service),
) -> dict:
    """Add a transaction to a case."""
    return await case_service.add_transaction_to_case(
        case_id=case_id,
        transaction_id=request.transaction_id,
        analyst_id=current_user.user_id,
        analyst_name=current_user.name,
    )


@router.delete("/{case_id}/transactions/{transaction_id}", response_model=CaseResponse)
async def remove_transaction_from_case(
    case_id: UUID,
    transaction_id: UUID,
    current_user: RequireTxnView,
    case_service: CaseService = Depends(get_case_service),
) -> dict:
    """Remove a transaction from a case."""
    return await case_service.remove_transaction_from_case(
        case_id=case_id,
        transaction_id=transaction_id,
        analyst_id=current_user.user_id,
        analyst_name=current_user.name,
    )


@router.get("/{case_id}/activity", response_model=list[CaseActivityResponse])
async def get_case_activity(
    case_id: UUID,
    current_user: RequireTxnView,
    limit: int = Query(100, ge=1, le=500),
    case_service: CaseService = Depends(get_case_service),
) -> list[dict]:
    """Get activity log for a case."""
    return await case_service.get_case_activity(
        case_id=case_id,
        limit=limit,
    )


@router.post("/{case_id}/resolve", response_model=CaseResponse)
async def resolve_case(
    case_id: UUID,
    current_user: RequireTxnView,
    resolution_summary: str = Query(..., description="Summary of how the case was resolved"),
    case_service: CaseService = Depends(get_case_service),
) -> dict:
    """Resolve a case."""
    return await case_service.resolve_case(
        case_id=case_id,
        resolution_summary=resolution_summary,
        resolved_by=current_user.user_id,
        analyst_name=current_user.name,
    )
