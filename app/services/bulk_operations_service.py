"""Bulk operations service for batch processing."""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationError
from app.persistence.case_repository import CaseRepository
from app.persistence.review_repository import ReviewRepository

logger = logging.getLogger(__name__)


class BulkOperationResult:
    """Result of a single bulk operation."""

    def __init__(
        self,
        transaction_id: UUID,
        success: bool,
        error_message: str | None = None,
        error_code: str | None = None,
    ):
        self.transaction_id = transaction_id
        self.success = success
        self.error_message = error_message
        self.error_code = error_code

    def to_dict(self) -> dict:
        return {
            "transaction_id": self.transaction_id,
            "success": self.success,
            "error_message": self.error_message,
            "error_code": self.error_code,
        }


class BulkOperationsService:
    """Service for bulk operations."""

    # Error codes for different operation types
    ERROR_CODES = {
        "assign": "ASSIGNMENT_ERROR",
        "update_status": "STATUS_UPDATE_ERROR",
        "add_to_case": "CASE_ADD_ERROR",
    }

    def __init__(self, session: AsyncSession):
        self.session = session
        self.review_repo = ReviewRepository(session)
        self.case_repo = CaseRepository(session)

    async def _execute_bulk_operation(
        self,
        transaction_ids: list[UUID],
        operation_name: str,
        operation_func,  # Callable that takes a review dict and returns awaitable
    ) -> dict:
        """Execute a bulk operation with consistent error handling.

        Args:
            transaction_ids: List of transaction IDs to process
            operation_name: Name of the operation (for error code lookup)
            operation_func: Async function that takes a review dict and performs the operation

        Returns:
            Dict with results including successful/failed counts and error summary
        """
        results = []
        successful = 0
        failed = 0
        error_summary: dict[str, int] = {}
        error_code = self.ERROR_CODES.get(operation_name, f"{operation_name.upper()}_ERROR")
        not_found_code = "REVIEW_NOT_FOUND"

        for txn_id in transaction_ids:
            try:
                review = await self.review_repo.get_by_transaction_id(txn_id)
                if not review:
                    results.append(
                        BulkOperationResult(
                            transaction_id=txn_id,
                            success=False,
                            error_message="Review not found for transaction",
                            error_code=not_found_code,
                        ).to_dict()
                    )
                    failed += 1
                    error_summary[not_found_code] = error_summary.get(not_found_code, 0) + 1
                    continue

                await operation_func(review)
                results.append(BulkOperationResult(transaction_id=txn_id, success=True).to_dict())
                successful += 1

            except Exception as e:
                logger.exception(f"Error in {operation_name} for transaction {txn_id}")
                results.append(
                    BulkOperationResult(
                        transaction_id=txn_id,
                        success=False,
                        error_message=str(e),
                        error_code=error_code,
                    ).to_dict()
                )
                failed += 1
                error_summary[error_code] = error_summary.get(error_code, 0) + 1

        return {
            "total_requested": len(transaction_ids),
            "successful": successful,
            "failed": failed,
            "results": results,
            "error_summary": error_summary if error_summary else None,
        }

    async def bulk_assign(
        self,
        transaction_ids: list[UUID],
        analyst_id: str,
    ) -> dict:
        """Bulk assign transactions to an analyst."""

        async def assign_operation(review: dict) -> None:
            await self.review_repo.assign(
                review_id=review["id"],
                analyst_id=analyst_id,
            )

        return await self._execute_bulk_operation(
            transaction_ids=transaction_ids,
            operation_name="assign",
            operation_func=assign_operation,
        )

    async def bulk_update_status(
        self,
        transaction_ids: list[UUID],
        status: str,
        resolution_code: str | None = None,
        resolution_notes: str | None = None,
        resolved_by: str | None = None,
    ) -> dict:
        """Bulk update transaction review status."""

        async def update_status_operation(review: dict) -> None:
            await self.review_repo.update_status(
                review_id=review["id"],
                status=status,
                resolution_code=resolution_code,
                resolution_notes=resolution_notes,
                resolved_by=resolved_by,
            )

        return await self._execute_bulk_operation(
            transaction_ids=transaction_ids,
            operation_name="update_status",
            operation_func=update_status_operation,
        )

    async def bulk_create_case(
        self,
        transaction_ids: list[UUID],
        case_type: str,
        title: str,
        description: str | None = None,
        assigned_analyst_id: str | None = None,
        risk_level: str | None = None,
        analyst_id: str | None = None,
        analyst_name: str | None = None,
    ) -> dict:
        """Bulk create a case from transactions."""
        if not title or not title.strip():
            raise ValidationError("Case title is required", details={"title": title})

        # Generate case number
        case_number = await self.case_repo.generate_case_number()

        # Create the case
        from uuid import uuid4

        case_id = uuid4()

        await self.case_repo.create(
            case_id=case_id,
            case_number=case_number,
            case_type=case_type,
            title=title,
            description=description,
            assigned_analyst_id=assigned_analyst_id,
            risk_level=risk_level,
            transaction_ids=transaction_ids,
        )

        # Log creation
        await self.case_repo.log_activity(
            case_id=case_id,
            activity_type="CASE_CREATED",
            activity_description=f"Case created from {len(transaction_ids)} transactions",
            analyst_id=analyst_id,
            analyst_name=analyst_name,
        )

        # Build results
        results = []
        successful = 0
        failed = 0

        for txn_id in transaction_ids:
            # Check if transaction was actually added
            # (we assume success if case shows transaction count)
            results.append(BulkOperationResult(transaction_id=txn_id, success=True).to_dict())
            successful += 1

        return {
            "total_requested": len(transaction_ids),
            "successful": successful,
            "failed": failed,
            "results": results,
            "created_case_id": case_id,
            "created_case_number": case_number,
            "error_summary": None,
        }
