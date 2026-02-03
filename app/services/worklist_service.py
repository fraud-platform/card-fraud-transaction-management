"""Worklist service for analyst transaction queue management."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.review_repository import ReviewRepository

logger = logging.getLogger(__name__)


class WorklistService:
    """Service for worklist operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ReviewRepository(session)

    async def get_worklist(
        self,
        analyst_id: str | None = None,
        status: str | None = None,
        assigned_only: bool = False,
        priority_filter: int | None = None,
        risk_level_filter: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[dict], str | None, int]:
        """Get worklist items."""
        if assigned_only and analyst_id:
            return await self.repo.list_by_analyst(
                analyst_id=analyst_id,
                status=status,
                priority_filter=priority_filter,
                risk_level_filter=risk_level_filter,
                limit=limit,
                cursor=cursor,
            )
        else:
            return await self.repo.list_unassigned(
                status=[status] if status else None,
                priority_filter=priority_filter,
                risk_level_filter=risk_level_filter,
                limit=limit,
                cursor=cursor,
            )

    async def get_worklist_stats(self, analyst_id: str | None = None) -> dict:
        """Get worklist statistics."""
        stats = await self.repo.get_stats(analyst_id=analyst_id)

        # Get unassigned breakdown by priority
        unassigned_reviews, _, _ = await self.repo.list_unassigned(limit=1000)
        priority_counts = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
        for review in unassigned_reviews:
            priority = str(review.get("priority", 3))
            if priority in priority_counts:
                priority_counts[priority] += 1

        # Get risk breakdown
        risk_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for review in unassigned_reviews:
            risk = review.get("risk_level")
            if risk and risk in risk_counts:
                risk_counts[risk] += 1

        return {
            "unassigned_total": stats.get("unassigned_total", 0),
            "unassigned_by_priority": priority_counts,
            "unassigned_by_risk": risk_counts,
            "my_assigned_total": stats.get("my_assigned_total", 0) if analyst_id else 0,
            "my_assigned_by_status": {
                "PENDING": stats.get("my_pending", 0),
                "IN_REVIEW": stats.get("my_in_review", 0),
                "ESCALATED": stats.get("my_escalated", 0),
                "RESOLVED": stats.get("my_resolved", 0),
            },
            "resolved_today": stats.get("my_resolved_today", 0) if analyst_id else 0,
            "resolved_by_code": stats.get("resolved_by_code", {}),
            "avg_resolution_minutes": None,  # TODO: Calculate from resolution data
        }

    async def get_unassigned(
        self,
        status: list[str] | None = None,
        priority_filter: int | None = None,
        risk_level_filter: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[dict], str | None, int]:
        """Get unassigned transactions."""
        return await self.repo.list_unassigned(
            status=status,
            priority_filter=priority_filter,
            risk_level_filter=risk_level_filter,
            limit=limit,
            cursor=cursor,
        )

    async def claim_next(
        self,
        analyst_id: str,
        priority_filter: int | None = None,
        risk_level_filter: str | None = None,
    ) -> dict | None:
        """Claim the next unassigned transaction."""
        # Get unassigned reviews with filters
        reviews, _, _ = await self.repo.list_unassigned(
            status=["PENDING", "ESCALATED"],
            priority_filter=priority_filter,
            risk_level_filter=risk_level_filter,
            limit=1,
        )

        if not reviews:
            return None

        review = reviews[0]
        review_id = review["review_id"]

        # Assign to analyst
        await self.repo.assign(
            review_id=review_id,
            analyst_id=analyst_id,
        )

        # Fetch the full worklist item data for the claimed review
        return await self.repo.get_worklist_item(review_id)
