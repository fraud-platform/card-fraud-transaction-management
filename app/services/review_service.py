"""Review service for transaction analyst workflow."""

import logging
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.persistence.review_repository import ReviewRepository

logger = logging.getLogger(__name__)

# Valid status transitions for transaction reviews
VALID_STATUS_TRANSITIONS = {
    "PENDING": ["IN_REVIEW", "ESCALATED", "RESOLVED", "CLOSED"],
    "IN_REVIEW": ["PENDING", "ESCALATED", "RESOLVED", "CLOSED"],
    "ESCALATED": ["IN_REVIEW", "RESOLVED", "CLOSED"],
    "RESOLVED": ["CLOSED"],
    "CLOSED": [],
}


class ReviewService:
    """Service for transaction review operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ReviewRepository(session)

    async def get_review(self, review_id: UUID) -> dict:
        """Get a review by ID."""
        review = await self.repo.get_by_id(review_id)
        if not review:
            raise NotFoundError("Review not found", details={"review_id": str(review_id)})
        return review

    async def get_review_by_transaction(self, transaction_id: UUID) -> dict:
        """Get review for a transaction (auto-creates if not exists)."""
        review = await self.repo.get_by_transaction_id(transaction_id)
        if not review:
            # Auto-create review record
            review = await self.repo.create(
                review_id=uuid4(),
                transaction_id=transaction_id,
                priority=3,
                status="PENDING",
            )
        return review

    async def create_review(
        self,
        transaction_id: UUID,
        priority: int = 3,
    ) -> dict:
        """Create a new transaction review."""
        review = await self.repo.get_by_transaction_id(transaction_id)
        if review:
            raise ConflictError(
                "Review already exists for transaction",
                details={
                    "transaction_id": str(transaction_id),
                    "existing_review_id": str(review["id"]),
                },
            )

        return await self.repo.create(
            review_id=uuid4(),
            transaction_id=transaction_id,
            priority=priority,
            status="PENDING",
        )

    async def update_status(
        self,
        review_id: UUID,
        status: str,
        resolution_notes: str | None = None,
        resolution_code: str | None = None,
        resolved_by: str | None = None,
    ) -> dict:
        """Update review status with validation."""
        review = await self.repo.get_by_id(review_id)
        if not review:
            raise NotFoundError("Review not found", details={"review_id": str(review_id)})

        current_status = review["status"]

        # Validate status transition
        if status not in VALID_STATUS_TRANSITIONS.get(current_status, []):
            raise ValidationError(
                f"Invalid status transition from {current_status} to {status}",
                details={
                    "current_status": current_status,
                    "requested_status": status,
                    "valid_transitions": VALID_STATUS_TRANSITIONS.get(current_status, []),
                },
            )

        # Require resolution notes for RESOLVED or CLOSED status
        if status in ("RESOLVED", "CLOSED") and not resolution_notes:
            raise ValidationError(
                "Resolution notes are required when resolving or closing a review",
                details={"status": status},
            )

        return await self.repo.update_status(
            review_id=review_id,
            status=status,
            resolution_code=resolution_code,
            resolution_notes=resolution_notes,
            resolved_by=resolved_by,
        )

    async def assign_analyst(
        self,
        review_id: UUID,
        analyst_id: str,
    ) -> dict:
        """Assign a review to an analyst."""
        review = await self.repo.get_by_id(review_id)
        if not review:
            raise NotFoundError("Review not found", details={"review_id": str(review_id)})

        return await self.repo.assign(
            review_id=review_id,
            analyst_id=analyst_id,
        )

    async def resolve(
        self,
        review_id: UUID,
        resolution_code: str,
        resolution_notes: str,
        resolved_by: str,
    ) -> dict:
        """Resolve a transaction review."""
        review = await self.repo.get_by_id(review_id)
        if not review:
            raise NotFoundError("Review not found", details={"review_id": str(review_id)})

        # Validate current status allows resolution
        current_status = review["status"]
        if current_status == "CLOSED":
            raise ValidationError(
                "Cannot resolve a closed review",
                details={"current_status": current_status},
            )

        return await self.repo.resolve(
            review_id=review_id,
            resolution_code=resolution_code,
            resolution_notes=resolution_notes,
            resolved_by=resolved_by,
        )

    async def escalate(
        self,
        review_id: UUID,
        escalate_to: str,
        reason: str,
    ) -> dict:
        """Escalate a transaction review."""
        review = await self.repo.get_by_id(review_id)
        if not review:
            raise NotFoundError("Review not found", details={"review_id": str(review_id)})

        # Validate current status allows escalation
        current_status = review["status"]
        if current_status in ("RESOLVED", "CLOSED"):
            raise ValidationError(
                f"Cannot escalate a {current_status.lower()} review",
                details={"current_status": current_status},
            )

        return await self.repo.escalate(
            review_id=review_id,
            escalate_to=escalate_to,
            reason=reason,
        )

    def validate_status_transition(
        self,
        current_status: str,
        new_status: str,
    ) -> bool:
        """Validate if a status transition is allowed."""
        return new_status in VALID_STATUS_TRANSITIONS.get(current_status, [])

    async def list_by_analyst(
        self,
        analyst_id: str,
        status: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[dict], str | None, int]:
        """List reviews assigned to an analyst."""
        return await self.repo.list_by_analyst(
            analyst_id=analyst_id,
            status=status,
            limit=limit,
            cursor=cursor,
        )

    async def list_unassigned(
        self,
        status: list[str] | None = None,
        priority_filter: int | None = None,
        risk_level_filter: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[dict], str | None, int]:
        """List unassigned reviews."""
        return await self.repo.list_unassigned(
            status=status,
            priority_filter=priority_filter,
            risk_level_filter=risk_level_filter,
            limit=limit,
            cursor=cursor,
        )
