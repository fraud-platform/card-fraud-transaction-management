"""API routes for bulk operations."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import RequireTxnView
from app.schemas.bulk import (
    BulkAssignRequest,
    BulkCreateCaseRequest,
    BulkOperationResponse,
    BulkStatusRequest,
)
from app.services.bulk_operations_service import BulkOperationsService

router = APIRouter(prefix="/bulk", tags=["bulk"])


def get_bulk_service(session: AsyncSession = Depends(get_session)) -> BulkOperationsService:
    """Get bulk operations service instance."""
    return BulkOperationsService(session)


@router.post("/assign", response_model=BulkOperationResponse)
async def bulk_assign(
    request: BulkAssignRequest,
    current_user: RequireTxnView,
    bulk_service: BulkOperationsService = Depends(get_bulk_service),
) -> dict:
    """Bulk assign transactions to an analyst.

    Maximum 100 transactions per request.
    """
    return await bulk_service.bulk_assign(
        transaction_ids=request.transaction_ids,
        analyst_id=request.analyst_id,
    )


@router.post("/status", response_model=BulkOperationResponse)
async def bulk_update_status(
    request: BulkStatusRequest,
    current_user: RequireTxnView,
    bulk_service: BulkOperationsService = Depends(get_bulk_service),
) -> dict:
    """Bulk update transaction review status.

    Maximum 100 transactions per request.
    """
    return await bulk_service.bulk_update_status(
        transaction_ids=request.transaction_ids,
        status=request.status.value,
        resolution_code=request.resolution_code,
        resolution_notes=request.resolution_notes,
        resolved_by=current_user.user_id,
    )


@router.post("/create-case", response_model=BulkOperationResponse)
async def bulk_create_case(
    request: BulkCreateCaseRequest,
    current_user: RequireTxnView,
    bulk_service: BulkOperationsService = Depends(get_bulk_service),
) -> dict:
    """Bulk create a case from transactions.

    Creates a new case and adds all specified transactions to it.
    Maximum 100 transactions per request.

    Returns the created case ID and case number.
    """
    return await bulk_service.bulk_create_case(
        transaction_ids=request.transaction_ids,
        case_type=request.case_type,
        title=request.title,
        description=request.description,
        assigned_analyst_id=request.assigned_analyst_id,
        risk_level=request.risk_level,
        analyst_id=current_user.user_id,
        analyst_name=current_user.name,
    )
