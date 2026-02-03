"""Case service for grouping related transactions."""

import logging
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.persistence.case_repository import CaseRepository

logger = logging.getLogger(__name__)


class CaseService:
    """Service for case operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CaseRepository(session)

    async def list_cases(
        self,
        case_status: str | None = None,
        case_type: str | None = None,
        assigned_analyst_id: str | None = None,
        risk_level: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[dict], str | None, int]:
        """List cases with filters."""
        return await self.repo.list(
            case_status=case_status,
            case_type=case_type,
            assigned_analyst_id=assigned_analyst_id,
            risk_level=risk_level,
            limit=limit,
            cursor=cursor,
        )

    async def get_case(self, case_id: UUID) -> dict:
        """Get a case by ID."""
        case = await self.repo.get_by_id(case_id)
        if not case:
            raise NotFoundError("Case not found", details={"case_id": str(case_id)})
        return case

    async def get_case_by_number(self, case_number: str) -> dict:
        """Get a case by its case number."""
        case = await self.repo.get_by_case_number(case_number)
        if not case:
            raise NotFoundError(
                "Case not found",
                details={"case_number": case_number},
            )
        return case

    async def create_case(
        self,
        case_type: str,
        title: str,
        description: str | None = None,
        transaction_ids: list[UUID] | None = None,
        assigned_analyst_id: str | None = None,
        risk_level: str | None = None,
        analyst_id: str | None = None,
        analyst_name: str | None = None,
    ) -> dict:
        """Create a new case."""
        if not title or not title.strip():
            raise ValidationError("Case title is required", details={"title": title})

        case_id = uuid4()
        case_number = await self.repo.generate_case_number()

        case = await self.repo.create(
            case_id=case_id,
            case_number=case_number,
            case_type=case_type,
            title=title,
            description=description,
            assigned_analyst_id=assigned_analyst_id,
            risk_level=risk_level,
            transaction_ids=transaction_ids,
        )

        # Log creation activity
        await self.repo.log_activity(
            case_id=case_id,
            activity_type="CASE_CREATED",
            activity_description=f"Case created: {title}",
            analyst_id=analyst_id,
            analyst_name=analyst_name,
        )

        return case

    async def update_case(
        self,
        case_id: UUID,
        case_status: str | None = None,
        case_type: str | None = None,
        title: str | None = None,
        description: str | None = None,
        assigned_analyst_id: str | None = None,
        risk_level: str | None = None,
        resolution_summary: str | None = None,
        analyst_id: str | None = None,
        analyst_name: str | None = None,
    ) -> dict:
        """Update a case."""
        case = await self.repo.get_by_id(case_id)
        if not case:
            raise NotFoundError("Case not found", details={"case_id": str(case_id)})

        # Track changes for activity log
        old_values: dict[str, object] = {}
        new_values: dict[str, object] = {}

        if case_status is not None and case_status != case["case_status"]:
            old_values["case_status"] = case["case_status"]
            new_values["case_status"] = case_status

        if assigned_analyst_id is not None and assigned_analyst_id != case.get(
            "assigned_analyst_id"
        ):
            old_values["assigned_analyst_id"] = case.get("assigned_analyst_id")
            new_values["assigned_analyst_id"] = assigned_analyst_id

        if resolution_summary is not None:
            new_values["resolution_summary"] = resolution_summary

        updated_case = await self.repo.update(
            case_id=case_id,
            case_status=case_status,
            case_type=case_type,
            title=title,
            description=description,
            assigned_analyst_id=assigned_analyst_id,
            risk_level=risk_level,
            resolution_summary=resolution_summary,
        )

        # Log activity if there were meaningful changes
        if old_values or new_values:
            await self.repo.log_activity(
                case_id=case_id,
                activity_type="CASE_UPDATED",
                activity_description="Case updated",
                analyst_id=analyst_id,
                analyst_name=analyst_name,
                old_values=old_values if old_values else None,
                new_values=new_values if new_values else None,
            )

        return updated_case

    async def add_transaction_to_case(
        self,
        case_id: UUID,
        transaction_id: UUID,
        analyst_id: str | None = None,
        analyst_name: str | None = None,
    ) -> dict:
        """Add a transaction to a case."""
        case = await self.repo.get_by_id(case_id)
        if not case:
            raise NotFoundError("Case not found", details={"case_id": str(case_id)})

        if case["case_status"] in ("RESOLVED", "CLOSED"):
            raise ValidationError(
                f"Cannot add transactions to a {case['case_status'].lower()} case",
                details={"case_status": case["case_status"]},
            )

        success = await self.repo.add_transaction(
            case_id=case_id,
            transaction_id=transaction_id,
        )

        if success:
            await self.repo.log_activity(
                case_id=case_id,
                activity_type="TRANSACTION_ADDED",
                activity_description=f"Transaction {transaction_id} added to case",
                analyst_id=analyst_id,
                analyst_name=analyst_name,
                transaction_id=transaction_id,
            )

        return await self.get_case(case_id)

    async def remove_transaction_from_case(
        self,
        case_id: UUID,
        transaction_id: UUID,
        analyst_id: str | None = None,
        analyst_name: str | None = None,
    ) -> dict:
        """Remove a transaction from a case."""
        case = await self.repo.get_by_id(case_id)
        if not case:
            raise NotFoundError("Case not found", details={"case_id": str(case_id)})

        if case["case_status"] in ("RESOLVED", "CLOSED"):
            raise ValidationError(
                f"Cannot remove transactions from a {case['case_status'].lower()} case",
                details={"case_status": case["case_status"]},
            )

        success = await self.repo.remove_transaction(
            case_id=case_id,
            transaction_id=transaction_id,
        )

        if success:
            await self.repo.log_activity(
                case_id=case_id,
                activity_type="TRANSACTION_REMOVED",
                activity_description=f"Transaction {transaction_id} removed from case",
                analyst_id=analyst_id,
                analyst_name=analyst_name,
                transaction_id=transaction_id,
            )

        return await self.get_case(case_id)

    async def resolve_case(
        self,
        case_id: UUID,
        resolution_summary: str,
        resolved_by: str,
        analyst_name: str | None = None,
    ) -> dict:
        """Resolve a case."""
        case = await self.repo.get_by_id(case_id)
        if not case:
            raise NotFoundError("Case not found", details={"case_id": str(case_id)})

        if case["case_status"] == "CLOSED":
            raise ValidationError(
                "Case is already closed",
                details={"case_status": case["case_status"]},
            )

        if not resolution_summary or not resolution_summary.strip():
            raise ValidationError(
                "Resolution summary is required",
                details={"resolution_summary": resolution_summary},
            )

        updated_case = await self.repo.update(
            case_id=case_id,
            case_status="RESOLVED",
            resolution_summary=resolution_summary,
        )

        await self.repo.log_activity(
            case_id=case_id,
            activity_type="CASE_RESOLVED",
            activity_description=f"Case resolved: {resolution_summary}",
            analyst_id=resolved_by,
            analyst_name=analyst_name,
        )

        return updated_case

    async def update_case_aggregates(self, case_id: UUID) -> dict:
        """Update case aggregates (transaction count and amount)."""
        # This is typically handled by database triggers
        return await self.get_case(case_id)

    async def get_case_transactions(
        self,
        case_id: UUID,
        limit: int = 100,
    ) -> list[dict]:
        """Get all transactions in a case."""
        case = await self.repo.get_by_id(case_id)
        if not case:
            raise NotFoundError("Case not found", details={"case_id": str(case_id)})

        return await self.repo.get_transactions(
            case_id=case_id,
            limit=limit,
        )

    async def get_case_activity(
        self,
        case_id: UUID,
        limit: int = 100,
    ) -> list[dict]:
        """Get activity log for a case."""
        case = await self.repo.get_by_id(case_id)
        if not case:
            raise NotFoundError("Case not found", details={"case_id": str(case_id)})

        return await self.repo.get_activity(
            case_id=case_id,
            limit=limit,
        )
