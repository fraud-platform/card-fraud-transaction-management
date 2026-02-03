"""Case repository using psycopg v3 and SQLAlchemy 2.0 async.

Table: fraud_gov.transaction_cases, fraud_gov.case_activity_log

IMPORTANT: Understanding transaction IDs
----------------------------------------
When linking reviews (which link to transactions), the reference pattern is:

  transaction_reviews.transaction_id → transactions.id (PK)

  NOT: transaction_reviews.transaction_id → transactions.transaction_id
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.base import BaseCursor

logger = logging.getLogger(__name__)


def _serialize_uuid(obj: Any) -> Any:
    """Convert UUID objects to strings for JSON serialization."""
    from uuid import UUID

    if isinstance(obj, UUID):
        return str(obj)
    elif isinstance(obj, dict):
        return {k: _serialize_uuid(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_serialize_uuid(item) for item in obj]
    return obj


@dataclass
class CaseCursor(BaseCursor):
    """Cursor for keyset pagination using created_at."""

    def __init__(
        self,
        *,
        timestamp: datetime | None = None,
        id: UUID | None = None,
        created_at: datetime | None = None,
    ):
        """Initialize cursor with backward-compatible parameter names."""
        ts = created_at or timestamp
        uid = id
        if ts is None or uid is None:
            raise TypeError("CaseCursor requires timestamp/id or created_at/id")
        super().__init__(timestamp=ts, id=uid)

    @property
    def created_at(self) -> datetime:
        return self.timestamp


class CaseRepository:
    """Repository for fraud_gov.transaction_cases data access."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, case_id: UUID) -> dict[str, Any] | None:
        """Get case by ID."""
        result = await self.session.execute(
            text("""
                SELECT id, case_number, case_type, case_status,
                       assigned_analyst_id, assigned_at,
                       title, description,
                       total_transaction_count, total_transaction_amount,
                       risk_level, resolved_at, resolved_by, resolution_summary,
                       created_at, updated_at, closed_at
                FROM fraud_gov.transaction_cases
                WHERE id = :case_id
            """),
            {"case_id": case_id},
        )
        row = result.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    async def get_by_case_number(self, case_number: str) -> dict[str, Any] | None:
        """Get case by case number."""
        result = await self.session.execute(
            text("""
                SELECT id, case_number, case_type, case_status,
                       assigned_analyst_id, assigned_at,
                       title, description,
                       total_transaction_count, total_transaction_amount,
                       risk_level, resolved_at, resolved_by, resolution_summary,
                       created_at, updated_at, closed_at
                FROM fraud_gov.transaction_cases
                WHERE case_number = :case_number
            """),
            {"case_number": case_number},
        )
        row = result.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    async def list(
        self,
        case_status: str | None = None,
        case_type: str | None = None,
        assigned_analyst_id: str | None = None,
        risk_level: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None, int]:
        """List cases with filters."""
        conditions = []
        params: dict[str, Any] = {"limit": limit + 1}

        if case_status:
            conditions.append("case_status = :case_status")
            params["case_status"] = case_status
        if case_type:
            conditions.append("case_type = :case_type")
            params["case_type"] = case_type
        if assigned_analyst_id:
            conditions.append("assigned_analyst_id = :assigned_analyst_id")
            params["assigned_analyst_id"] = assigned_analyst_id
        if risk_level:
            conditions.append("risk_level = :risk_level")
            params["risk_level"] = risk_level

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        cursor_obj: CaseCursor | None = None
        if cursor:
            cursor_obj = CaseCursor.decode(cursor)
            if cursor_obj:
                conditions.append("(created_at, id) < (:cursor_ts, :cursor_tid)")
                params["cursor_ts"] = cursor_obj.created_at
                params["cursor_tid"] = cursor_obj.id
                where_clause = " AND ".join(conditions)

        # Count
        count_result = await self.session.execute(
            text(f"SELECT COUNT(*) FROM fraud_gov.transaction_cases WHERE {where_clause}"),
            params,
        )
        total = count_result.scalar() or 0

        # Data query
        data_query = f"""
            SELECT id, case_number, case_type, case_status,
                   assigned_analyst_id, assigned_at,
                   title, description,
                   total_transaction_count, total_transaction_amount,
                   risk_level, resolved_at, resolved_by, resolution_summary,
                   created_at, updated_at, closed_at
            FROM fraud_gov.transaction_cases
            WHERE {where_clause}
            ORDER BY created_at DESC, id DESC
            LIMIT :limit
        """
        result = await self.session.execute(text(data_query), params)

        cases = [self._row_to_dict(row) for row in result.fetchall()]

        next_cursor: str | None = None
        if len(cases) > limit:
            cases = cases[:limit]
            last_case = cases[-1]
            next_cursor = CaseCursor(
                timestamp=last_case["created_at"],
                id=last_case["id"],
            ).encode()

        return cases, next_cursor, total or 0

    async def create(
        self,
        case_id: UUID,
        case_number: str,
        case_type: str,
        title: str,
        description: str | None = None,
        assigned_analyst_id: str | None = None,
        risk_level: str | None = None,
        transaction_ids: list[UUID] | None = None,
    ) -> dict[str, Any] | None:
        """Create a new case."""
        # Create the case
        await self.session.execute(
            text("""
                INSERT INTO fraud_gov.transaction_cases (
                    id, case_number, case_type, case_status,
                    title, description, assigned_analyst_id, risk_level,
                    created_at, updated_at
                ) VALUES (
                    :id, :case_number, :case_type, 'OPEN',
                    :title, :description, :assigned_analyst_id, :risk_level,
                    NOW(), NOW()
                )
            """),
            {
                "id": case_id,
                "case_number": case_number,
                "case_type": case_type,
                "title": title,
                "description": description,
                "assigned_analyst_id": assigned_analyst_id,
                "risk_level": risk_level,
            },
        )

        # Link transactions if provided
        if transaction_ids:
            for txn_id in transaction_ids:
                await self.add_transaction(case_id, txn_id)

        return await self.get_by_id(case_id)

    async def update(
        self,
        case_id: UUID,
        case_status: str | None = None,
        case_type: str | None = None,
        title: str | None = None,
        description: str | None = None,
        assigned_analyst_id: str | None = None,
        risk_level: str | None = None,
        resolution_summary: str | None = None,
    ) -> dict[str, Any] | None:
        """Update a case."""
        update_fields = []
        params: dict[str, Any] = {"case_id": case_id}

        if case_status is not None:
            update_fields.append("case_status = :case_status")
            params["case_status"] = case_status
            if case_status in ("RESOLVED", "CLOSED"):
                update_fields.append("closed_at = NOW()")
        if case_type is not None:
            update_fields.append("case_type = :case_type")
            params["case_type"] = case_type
        if title is not None:
            update_fields.append("title = :title")
            params["title"] = title
        if description is not None:
            update_fields.append("description = :description")
            params["description"] = description
        if assigned_analyst_id is not None:
            update_fields.extend(
                ["assigned_analyst_id = :assigned_analyst_id", "assigned_at = NOW()"]
            )
            params["assigned_analyst_id"] = assigned_analyst_id
        if risk_level is not None:
            update_fields.append("risk_level = :risk_level")
            params["risk_level"] = risk_level
        if resolution_summary is not None:
            update_fields.extend(
                ["resolution_summary = :resolution_summary", "resolved_at = NOW()"]
            )
            params["resolution_summary"] = resolution_summary

        if update_fields:
            await self.session.execute(
                text(f"""
                    UPDATE fraud_gov.transaction_cases
                    SET {", ".join(update_fields)}
                    WHERE id = :case_id
                """),
                params,
            )

        return await self.get_by_id(case_id)

    async def add_transaction(self, case_id: UUID, transaction_id: UUID) -> bool:
        """Add a transaction to a case by updating its review record."""
        result = await self.session.execute(
            text("""
                UPDATE fraud_gov.transaction_reviews
                SET case_id = :case_id
                WHERE transaction_id = :transaction_id
            """),
            {"case_id": case_id, "transaction_id": transaction_id},
        )
        return result.rowcount > 0

    async def remove_transaction(self, case_id: UUID, transaction_id: UUID) -> bool:
        """Remove a transaction from a case."""
        result = await self.session.execute(
            text("""
                UPDATE fraud_gov.transaction_reviews
                SET case_id = NULL
                WHERE transaction_id = :transaction_id AND case_id = :case_id
            """),
            {"case_id": case_id, "transaction_id": transaction_id},
        )
        return result.rowcount > 0

    async def get_transactions(
        self,
        case_id: UUID,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get all transactions in a case."""
        result = await self.session.execute(
            text("""
                SELECT t.id, t.transaction_id, t.card_id, t.card_last4,
                       t.transaction_amount, t.transaction_currency,
                       t.decision, t.decision_reason, t.risk_level,
                       t.transaction_timestamp
                FROM fraud_gov.transactions t
                INNER JOIN fraud_gov.transaction_reviews r ON r.transaction_id = t.id
                WHERE r.case_id = :case_id
                ORDER BY t.transaction_timestamp DESC
                LIMIT :limit
            """),
            {"case_id": case_id, "limit": limit},
        )

        return [
            {
                "id": row[0],
                "transaction_id": row[1],
                "card_id": row[2],
                "card_last4": row[3],
                "transaction_amount": float(row[4]) if row[4] else None,
                "transaction_currency": row[5],
                "decision": row[6],
                "decision_reason": row[7],
                "risk_level": row[8],
                "transaction_timestamp": row[9],
            }
            for row in result.fetchall()
        ]

    async def log_activity(
        self,
        case_id: UUID,
        activity_type: str,
        activity_description: str,
        analyst_id: str | None = None,
        analyst_name: str | None = None,
        old_values: dict[str, Any] | None = None,
        new_values: dict[str, Any] | None = None,
        transaction_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Log an activity to the case audit trail."""
        result = await self.session.execute(
            text("""
                INSERT INTO fraud_gov.case_activity_log (
                    case_id, activity_type, activity_description,
                    analyst_id, analyst_name, old_values, new_values, transaction_id,
                    created_at
                ) VALUES (
                    :case_id, :activity_type, :activity_description,
                    :analyst_id, :analyst_name, :old_values, :new_values, :transaction_id,
                    NOW()
                )
                RETURNING id, case_id, activity_type, activity_description,
                         analyst_id, analyst_name, old_values, new_values,
                         transaction_id, created_at
            """),
            {
                "case_id": case_id,
                "activity_type": activity_type,
                "activity_description": activity_description,
                "analyst_id": analyst_id,
                "analyst_name": analyst_name,
                "old_values": json.dumps(_serialize_uuid(old_values)) if old_values else None,
                "new_values": json.dumps(_serialize_uuid(new_values)) if new_values else None,
                "transaction_id": transaction_id,
            },
        )
        row = result.fetchone()
        return {
            "id": row[0],
            "case_id": row[1],
            "activity_type": row[2],
            "activity_description": row[3],
            "analyst_id": row[4],
            "analyst_name": row[5],
            "old_values": row[6],
            "new_values": row[7],
            "transaction_id": row[8],
            "created_at": row[9],
        }

    async def get_activity(
        self,
        case_id: UUID,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get activity log for a case."""
        result = await self.session.execute(
            text("""
                SELECT id, case_id, activity_type, activity_description,
                       analyst_id, analyst_name, old_values, new_values,
                       transaction_id, created_at
                FROM fraud_gov.case_activity_log
                WHERE case_id = :case_id
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            {"case_id": case_id, "limit": limit},
        )

        return [
            {
                "id": row[0],
                "case_id": row[1],
                "activity_type": row[2],
                "activity_description": row[3],
                "analyst_id": row[4],
                "analyst_name": row[5],
                "old_values": row[6],
                "new_values": row[7],
                "transaction_id": row[8],
                "created_at": row[9],
            }
            for row in result.fetchall()
        ]

    async def generate_case_number(self) -> str:
        """Generate the next case number using the database sequence."""
        result = await self.session.execute(text("SELECT fraud_gov.generate_case_number()"))
        return result.scalar()

    def _row_to_dict(self, row) -> dict[str, Any]:
        """Convert a database row to a dictionary."""
        return {
            "id": row[0],
            "case_number": row[1],
            "case_type": row[2],
            "case_status": row[3],
            "assigned_analyst_id": row[4],
            "assigned_at": row[5],
            "title": row[6],
            "description": row[7],
            "total_transaction_count": row[8],
            "total_transaction_amount": float(row[9]) if row[9] else 0,
            "risk_level": row[10],
            "resolved_at": row[11],
            "resolved_by": row[12],
            "resolution_summary": row[13],
            "created_at": row[14],
            "updated_at": row[15],
            "closed_at": row[16],
        }
