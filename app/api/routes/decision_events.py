"""Decision event ingestion API routes (aligned with locked design).

Endpoints:
- POST /v1/decision-events - Ingest via HTTP (dev/testing)
- GET /v1/transactions - Query transactions
- GET /v1/transactions/{id} - Get single transaction
- GET /v1/metrics - Get aggregate metrics
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import CurrentUser
from app.schemas.decision_event import (
    CombinedTransactionView,
    DecisionEventCreate,
    DecisionEventResponse,
    ErrorResponse,
    TransactionListResponse,
    TransactionOverview,
    TransactionQueryResult,
)
from app.services.ingestion_service import IngestionService, IngestionSource
from app.services.transaction_service import TransactionService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/decision-events",
    response_model=DecisionEventResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Ingestion"],
    summary="Ingest decision event",
    description="Ingest a fraud decision event (HTTP endpoint for dev/testing).",
    responses={
        202: {"description": "Event accepted for processing"},
        400: {"model": ErrorResponse, "description": "Validation error"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        409: {"model": ErrorResponse, "description": "Conflicting transaction"},
        422: {"model": ErrorResponse, "description": "PAN detected (PCI violation)"},
    },
)
async def ingest_decision_event(
    event: DecisionEventCreate,
    request: Request,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> DecisionEventResponse:
    """Ingest a decision event via HTTP (idempotent).

    This endpoint is for development/testing. Production uses Kafka.

    **Authentication**: Requires valid JWT token with appropriate permissions.

    **Idempotency**: Duplicate events with the same transaction_id
    will update metadata only (trace_id, raw_payload, ingestion_source).

    **PCI Compliance**: PAN-like patterns in card_id will be rejected.
    """
    trace_id = request.headers.get("X-Trace-ID") or request.headers.get("X-Request-ID")

    try:
        service = IngestionService(session)
        result = await service.ingest_event(
            event=event,
            source=IngestionSource.HTTP,
            trace_id=trace_id,
        )
        return DecisionEventResponse(**result)
    except ValueError as e:
        if "PAN" in str(e).upper():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": "PAN detection triggered", "message": str(e)},
            ) from None
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Validation error", "message": str(e)},
        ) from None


@router.get(
    "/transactions",
    response_model=TransactionListResponse,
    tags=["Query"],
    summary="List transactions",
    description="Get a paginated list of transactions with optional filtering.",
    responses={
        200: {"description": "List of transactions"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
async def list_transactions(
    current_user: CurrentUser,
    page_size: int = Query(50, ge=1, le=500, description="Items per page"),
    card_id: str | None = Query(None, description="Filter by card ID"),
    decision: str | None = Query(None, description="Filter by decision (APPROVE/DECLINE)"),
    country: str | None = Query(None, description="Filter by country code (not persisted)"),
    merchant_id: str | None = Query(None, description="Filter by merchant ID"),
    from_date: datetime | None = Query(None, description="Filter from date"),
    to_date: datetime | None = Query(None, description="Filter to date"),
    review_status: str | None = Query(
        None, description="Filter by review status (PENDING/IN_REVIEW/ESCALATED/RESOLVED/CLOSED)"
    ),
    risk_level: str | None = Query(
        None, description="Filter by risk level (LOW/MEDIUM/HIGH/CRITICAL)"
    ),
    case_id: str | None = Query(None, description="Filter by case ID"),
    rule_id: str | None = Query(None, description="Filter by rule ID (matched rules)"),
    ruleset_id: str | None = Query(None, description="Filter by ruleset ID"),
    assigned_to_me: bool = Query(False, description="Filter transactions assigned to current user"),
    min_amount: float | None = Query(None, ge=0, description="Minimum transaction amount"),
    max_amount: float | None = Query(None, ge=0, description="Maximum transaction amount"),
    cursor: str | None = Query(None, description="Pagination cursor from previous response"),
    session: AsyncSession = Depends(get_session),
) -> TransactionListResponse:
    """List transactions with keyset pagination and filtering."""
    from uuid import UUID

    service = TransactionService(session)
    result = await service.list_transactions(
        page_size=page_size,
        card_id=card_id,
        decision=decision,
        country=country,
        merchant_id=merchant_id,
        from_date=from_date,
        to_date=to_date,
        review_status=review_status,
        risk_level=risk_level,
        case_id=UUID(case_id) if case_id else None,
        rule_id=UUID(rule_id) if rule_id else None,
        ruleset_id=UUID(ruleset_id) if ruleset_id else None,
        assigned_to_me=assigned_to_me,
        assigned_analyst_id=current_user.user_id if assigned_to_me else None,
        min_amount=min_amount,
        max_amount=max_amount,
        cursor=cursor,
    )
    return TransactionListResponse(**result)


@router.get(
    "/transactions/{transaction_id}",
    response_model=TransactionQueryResult,
    tags=["Query"],
    summary="Get transaction",
    description="Get detailed information about a specific transaction.",
    responses={
        200: {"description": "Transaction details"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Transaction not found"},
    },
)
async def get_transaction(
    transaction_id: str,
    current_user: CurrentUser,
    include_rules: bool = Query(True, description="Include rule matches"),
    session: AsyncSession = Depends(get_session),
) -> TransactionQueryResult:
    """Get transaction by transaction_id."""
    service = TransactionService(session)
    transaction = await service.get_transaction(
        transaction_id,
        include_rules=include_rules,
    )

    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Transaction not found", "transaction_id": transaction_id},
        )

    return TransactionQueryResult(**transaction)


@router.get(
    "/transactions/{transaction_id}/combined",
    response_model=CombinedTransactionView,
    tags=["Query"],
    summary="Get combined transaction view",
    description="Get AUTH and MONITORING events (and matches) for a transaction_id.",
    responses={
        200: {"description": "Combined transaction view"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Transaction not found"},
    },
)
async def get_transaction_combined(
    transaction_id: str,
    current_user: CurrentUser,
    include_rules: bool = Query(True, description="Include rule matches"),
    session: AsyncSession = Depends(get_session),
) -> CombinedTransactionView:
    """Get combined AUTH + MONITORING view by transaction_id."""
    service = TransactionService(session)
    combined = await service.get_transaction_combined(
        transaction_id,
        include_rules=include_rules,
    )

    if combined is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Transaction not found", "transaction_id": transaction_id},
        )

    return CombinedTransactionView(**combined)


@router.get(
    "/transactions/{transaction_id}/overview",
    response_model=TransactionOverview,
    tags=["Query"],
    summary="Get transaction overview",
    description=(  # noqa: E501
        "Get combined view with transaction, review, notes, case, and optional matched rules."
    ),
    responses={
        200: {"description": "Transaction overview"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Transaction not found"},
    },
)
async def get_transaction_overview(
    transaction_id: str,
    current_user: CurrentUser,
    include_rules: bool = Query(False, description="Include matched rules"),
    session: AsyncSession = Depends(get_session),
) -> TransactionOverview:
    """Get transaction overview with all related data in a single call.

    Returns transaction details, review status, analyst notes, case linkage,
    and optionally matched rules. Optimized for analyst UI performance.
    """
    service = TransactionService(session)
    overview = await service.get_transaction_overview(
        transaction_id,
        include_rules=include_rules,
        analyst_id=current_user.user_id,
    )

    if overview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Transaction not found", "transaction_id": transaction_id},
        )

    return TransactionOverview(**overview)


@router.get(
    "/metrics",
    tags=["Query"],
    summary="Get metrics",
    description="Get aggregate transaction metrics.",
    responses={
        200: {"description": "Transaction metrics"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
async def get_metrics(
    current_user: CurrentUser,
    from_date: datetime | None = Query(None, description="Filter from date"),
    to_date: datetime | None = Query(None, description="Filter to date"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get transaction metrics."""
    service = TransactionService(session)
    return await service.get_metrics(from_date=from_date, to_date=to_date)
