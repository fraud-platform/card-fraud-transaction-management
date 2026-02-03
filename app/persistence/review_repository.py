"""Review repository using psycopg v3 and SQLAlchemy 2.0 async.

Table: fraud_gov.transaction_reviews

IMPORTANT: Understanding transaction IDs
----------------------------------------
The transaction_reviews table has a transaction_id column that REFERENCES transactions(id).

  transaction_reviews.transaction_id → transactions.id (PK)

  NOT: transaction_reviews.transaction_id → transactions.transaction_id

  CORRECT JOIN: FROM transaction_reviews r JOIN transactions t ON r.transaction_id = t.id

  # WRONG JOIN: Uses business key instead of PK (DO NOT USE)
  # FROM transaction_reviews r JOIN transactions t ON r.transaction_id = t.transaction_id
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.transaction import TransactionStatus
from app.persistence.base import BaseCursor

logger = logging.getLogger(__name__)

# Allowed status values for validation (matches TransactionStatus enum)
_ALLOWED_STATUSES = {s.value for s in TransactionStatus}


@dataclass
class ReviewCursor(BaseCursor):
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
            raise TypeError("ReviewCursor requires timestamp/id or created_at/id")
        super().__init__(timestamp=ts, id=uid)

    @property
    def created_at(self) -> datetime:
        return self.timestamp


class ReviewRepository:
    """Repository for fraud_gov.transaction_reviews data access."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, review_id: UUID) -> dict[str, Any] | None:
        """Get review by ID."""
        result = await self.session.execute(
            text("""
                SELECT r.id, r.transaction_id, r.status, r.priority,
                       r.assigned_analyst_id, r.assigned_at,
                       r.case_id, r.resolved_at, r.resolved_by,
                       r.resolution_code, r.resolution_notes,
                       r.escalated_at, r.escalated_to, r.escalation_reason,
                       r.first_reviewed_at, r.last_activity_at,
                       r.created_at, r.updated_at,
                       t.transaction_amount, t.transaction_currency, t.decision, t.risk_level
                FROM fraud_gov.transaction_reviews r
                LEFT JOIN fraud_gov.transactions t ON r.transaction_id = t.id
                WHERE r.id = :review_id
            """),
            {"review_id": review_id},
        )
        row = result.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    async def get_by_transaction_id(self, transaction_id: UUID) -> dict[str, Any] | None:
        """Get review by transaction ID."""
        result = await self.session.execute(
            text("""
                SELECT r.id, r.transaction_id, r.status, r.priority,
                       r.assigned_analyst_id, r.assigned_at,
                       r.case_id, r.resolved_at, r.resolved_by,
                       r.resolution_code, r.resolution_notes,
                       r.escalated_at, r.escalated_to, r.escalation_reason,
                       r.first_reviewed_at, r.last_activity_at,
                       r.created_at, r.updated_at,
                       t.transaction_amount, t.transaction_currency, t.decision, t.risk_level
                FROM fraud_gov.transaction_reviews r
                LEFT JOIN fraud_gov.transactions t ON r.transaction_id = t.id
                WHERE r.transaction_id = :transaction_id
            """),
            {"transaction_id": transaction_id},
        )
        row = result.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    async def get_worklist_item(self, review_id: UUID) -> dict[str, Any] | None:
        """Get review with full transaction details for worklist."""
        result = await self.session.execute(
            text(
                """
                SELECT r.id, r.transaction_id, r.status, r.priority,
                       r.assigned_analyst_id, r.assigned_at,
                       r.case_id, r.first_reviewed_at, r.last_activity_at,
                       r.created_at, r.updated_at,
                       t.transaction_amount, t.transaction_currency, t.decision,
                       t.decision_reason, t.risk_level,
                       t.card_id, t.card_last4, t.transaction_timestamp,
                       t.merchant_id, t.merchant_category_code, t.trace_id
                FROM fraud_gov.transaction_reviews r
                LEFT JOIN fraud_gov.transactions t ON r.transaction_id = t.id
                WHERE r.id = :review_id
            """
            ),
            {"review_id": review_id},
        )
        row = result.fetchone()
        if row is None:
            return None
        return self._row_to_dict_full(row)

    async def create(
        self,
        review_id: UUID,
        transaction_id: UUID,
        priority: int = 3,
        status: str = "PENDING",
    ) -> dict[str, Any] | None:
        """Create a new transaction review."""
        await self.session.execute(
            text("""
                INSERT INTO fraud_gov.transaction_reviews (
                    id, transaction_id, status, priority, created_at, updated_at
                ) VALUES (
                    :id, :transaction_id, :status, :priority, NOW(), NOW()
                )
                ON CONFLICT (transaction_id) DO NOTHING
            """),
            {
                "id": review_id,
                "transaction_id": transaction_id,
                "status": status,
                "priority": priority,
            },
        )
        return await self.get_by_id(review_id)

    async def update_status(
        self,
        review_id: UUID,
        status: str,
        resolution_code: str | None = None,
        resolution_notes: str | None = None,
        resolved_by: str | None = None,
    ) -> dict[str, Any] | None:
        """Update review status."""
        update_fields = ["status = :status"]
        params: dict[str, Any] = {"review_id": review_id, "status": status}

        if resolution_code is not None:
            update_fields.append("resolution_code = :resolution_code")
            params["resolution_code"] = resolution_code
        if resolution_notes is not None:
            update_fields.append("resolution_notes = :resolution_notes")
            params["resolution_notes"] = resolution_notes
        if status in ("RESOLVED", "CLOSED") and resolved_by is not None:
            update_fields.extend(["resolved_at = NOW()", "resolved_by = :resolved_by"])
            params["resolved_by"] = resolved_by

        await self.session.execute(
            text(f"""
                UPDATE fraud_gov.transaction_reviews
                SET {", ".join(update_fields)}
                WHERE id = :review_id
            """),
            params,
        )
        return await self.get_by_id(review_id)

    async def assign(
        self,
        review_id: UUID,
        analyst_id: str,
    ) -> dict[str, Any] | None:
        """Assign review to an analyst."""
        await self.session.execute(
            text("""
                UPDATE fraud_gov.transaction_reviews
                SET assigned_analyst_id = :analyst_id,
                    assigned_at = NOW(),
                    status = 'IN_REVIEW'
                WHERE id = :review_id
            """),
            {"review_id": review_id, "analyst_id": analyst_id},
        )
        return await self.get_by_id(review_id)

    async def resolve(
        self,
        review_id: UUID,
        resolution_code: str,
        resolution_notes: str,
        resolved_by: str,
    ) -> dict[str, Any] | None:
        """Resolve a transaction review."""
        await self.session.execute(
            text("""
                UPDATE fraud_gov.transaction_reviews
                SET status = 'RESOLVED',
                    resolution_code = :resolution_code,
                    resolution_notes = :resolution_notes,
                    resolved_by = :resolved_by,
                    resolved_at = NOW()
                WHERE id = :review_id
            """),
            {
                "review_id": review_id,
                "resolution_code": resolution_code,
                "resolution_notes": resolution_notes,
                "resolved_by": resolved_by,
            },
        )
        return await self.get_by_id(review_id)

    async def escalate(
        self,
        review_id: UUID,
        escalate_to: str,
        reason: str,
    ) -> dict[str, Any] | None:
        """Escalate a transaction review."""
        await self.session.execute(
            text("""
                UPDATE fraud_gov.transaction_reviews
                SET status = 'ESCALATED',
                    escalated_to = :escalate_to,
                    escalation_reason = :reason,
                    escalated_at = NOW()
                WHERE id = :review_id
            """),
            {"review_id": review_id, "escalate_to": escalate_to, "reason": reason},
        )
        return await self.get_by_id(review_id)

    async def list_by_analyst(
        self,
        analyst_id: str,
        status: str | None = None,
        priority_filter: int | None = None,
        risk_level_filter: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None, int]:
        """List reviews assigned to an analyst."""
        conditions = ["assigned_analyst_id = :analyst_id"]
        params: dict[str, Any] = {"analyst_id": analyst_id, "limit": limit + 1}

        if status:
            conditions.append("status = :status")
            params["status"] = status

        if priority_filter is not None:
            conditions.append("priority <= :priority")
            params["priority"] = priority_filter

        if risk_level_filter:
            conditions.append("t.risk_level = :risk_level")
            params["risk_level"] = risk_level_filter

        where_clause = " AND ".join(conditions)

        cursor_obj: ReviewCursor | None = None
        if cursor:
            cursor_obj = ReviewCursor.decode(cursor)
            if cursor_obj:
                conditions.append("(r.created_at, r.id) < (:cursor_ts, :cursor_tid)")
                params["cursor_ts"] = cursor_obj.created_at
                params["cursor_tid"] = cursor_obj.id
                where_clause = " AND ".join(conditions)

        # Count (need join for risk_level filter)
        count_from = (
            "fraud_gov.transaction_reviews r LEFT JOIN fraud_gov.transactions t "
            "ON r.transaction_id = t.id"
        )
        count_result = await self.session.execute(
            text(f"SELECT COUNT(*) FROM {count_from} WHERE {where_clause}"),
            params,
        )
        total = count_result.scalar() or 0

        # Data query
        data_query = f"""
            SELECT r.id, r.transaction_id, r.status, r.priority,
                   r.assigned_analyst_id, r.assigned_at,
                   r.case_id, r.first_reviewed_at, r.last_activity_at,
                   r.created_at, r.updated_at,
                   t.transaction_amount, t.transaction_currency, t.decision,
                   t.decision_reason, t.risk_level,
                   t.card_id, t.card_last4, t.transaction_timestamp,
                   t.merchant_id, t.merchant_category_code, t.trace_id
            FROM fraud_gov.transaction_reviews r
            LEFT JOIN fraud_gov.transactions t ON r.transaction_id = t.id
            WHERE {where_clause}
            ORDER BY r.created_at DESC, r.id DESC
            LIMIT :limit
        """
        result = await self.session.execute(text(data_query), params)

        reviews = [self._row_to_dict_full(row) for row in result.fetchall()]

        next_cursor: str | None = None
        if len(reviews) > limit:
            reviews = reviews[:limit]
            last_review = reviews[-1]
            next_cursor = ReviewCursor(
                timestamp=last_review["created_at"],
                id=last_review["review_id"],
            ).encode()

        return reviews, next_cursor, total or 0

    async def list_unassigned(
        self,
        status: list[str] | None = None,
        priority_filter: int | None = None,
        risk_level_filter: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None, int]:
        """List unassigned reviews for worklist."""
        if status is None:
            status = ["PENDING", "IN_REVIEW", "ESCALATED"]

        # Validate status values against allowed enum to prevent SQL injection
        invalid_statuses = set(status) - _ALLOWED_STATUSES
        if invalid_statuses:
            raise ValueError(
                f"Invalid status values: {invalid_statuses}. Allowed: {sorted(_ALLOWED_STATUSES)}"
            )

        conditions = ["assigned_analyst_id IS NULL"]
        params: dict[str, Any] = {"limit": limit + 1}

        placeholders = []
        for i, s in enumerate(status):
            placeholders.append(f":status_{i}")
            params[f"status_{i}"] = s
        conditions.append(f"status IN ({', '.join(placeholders)})")

        if priority_filter is not None:
            conditions.append("priority <= :priority")
            params["priority"] = priority_filter

        if risk_level_filter:
            conditions.append(
                "EXISTS ("
                "SELECT 1 FROM fraud_gov.transactions t "
                "WHERE t.id = r.transaction_id "
                "AND t.risk_level = :risk_level"
                ")"
            )
            params["risk_level"] = risk_level_filter

        where_clause = " AND ".join(conditions)

        cursor_obj: ReviewCursor | None = None
        if cursor:
            cursor_obj = ReviewCursor.decode(cursor)
            if cursor_obj:
                conditions.append("(r.created_at, r.id) < (:cursor_ts, :cursor_tid)")
                params["cursor_ts"] = cursor_obj.created_at
                params["cursor_tid"] = cursor_obj.id
                where_clause = " AND ".join(conditions)

        # Count
        count_result = await self.session.execute(
            text(f"SELECT COUNT(*) FROM fraud_gov.transaction_reviews r WHERE {where_clause}"),
            params,
        )
        total = count_result.scalar() or 0

        # Data query
        data_query = f"""
            SELECT r.id, r.transaction_id, r.status, r.priority,
                   r.assigned_analyst_id, r.assigned_at,
                   r.case_id, r.first_reviewed_at, r.last_activity_at,
                   r.created_at, r.updated_at,
                   t.transaction_amount, t.transaction_currency, t.decision,
                   t.decision_reason, t.risk_level,
                   t.card_id, t.card_last4, t.transaction_timestamp,
                   t.merchant_id, t.merchant_category_code, t.trace_id
            FROM fraud_gov.transaction_reviews r
            LEFT JOIN fraud_gov.transactions t ON r.transaction_id = t.id
            WHERE {where_clause}
            ORDER BY r.priority ASC, r.created_at ASC, r.id ASC
            LIMIT :limit
        """
        result = await self.session.execute(text(data_query), params)

        reviews = [self._row_to_dict_full(row) for row in result.fetchall()]

        next_cursor: str | None = None
        if len(reviews) > limit:
            reviews = reviews[:limit]
            last_review = reviews[-1]
            next_cursor = ReviewCursor(
                timestamp=last_review["created_at"],
                id=last_review["review_id"],
            ).encode()

        return reviews, next_cursor, total or 0

    async def get_stats(self, analyst_id: str | None = None) -> dict[str, Any]:
        """Get worklist statistics."""
        params: dict[str, Any] = {}
        if analyst_id:
            params["analyst_id"] = analyst_id

        # Unassigned stats
        unassigned_result = await self.session.execute(
            text("""
                SELECT
                    COUNT(*) FILTER (WHERE status = 'PENDING') AS pending,
                    COUNT(*) FILTER (WHERE status = 'IN_REVIEW') AS in_review,
                    COUNT(*) FILTER (WHERE status = 'ESCALATED') AS escalated
                FROM fraud_gov.transaction_reviews
                WHERE assigned_analyst_id IS NULL
            """),
        )
        unassigned_row = unassigned_result.fetchone()

        # My assigned stats
        my_stats: dict[str, Any] = {}
        if analyst_id:
            my_result = await self.session.execute(
                text("""
                    SELECT
                        COUNT(*) FILTER (WHERE status = 'PENDING') AS pending,
                        COUNT(*) FILTER (WHERE status = 'IN_REVIEW') AS in_review,
                        COUNT(*) FILTER (WHERE status = 'ESCALATED') AS escalated,
                        COUNT(*) FILTER (WHERE status = 'RESOLVED') AS resolved,
                        COUNT(*) FILTER (WHERE resolved_at >= CURRENT_DATE) AS resolved_today
                    FROM fraud_gov.transaction_reviews
                    WHERE assigned_analyst_id = :analyst_id
                """),
                {"analyst_id": analyst_id},
            )
            my_row = my_result.fetchone()
            my_stats = {
                "my_pending": my_row[0] or 0,
                "my_in_review": my_row[1] or 0,
                "my_escalated": my_row[2] or 0,
                "my_resolved": my_row[3] or 0,
                "my_resolved_today": my_row[4] or 0,
            }

            # Resolution codes breakdown for this analyst
            resolved_by_code_result = await self.session.execute(
                text("""
                    SELECT resolution_code, COUNT(*) as count
                    FROM fraud_gov.transaction_reviews
                    WHERE assigned_analyst_id = :analyst_id
                    AND status = 'RESOLVED'
                    AND resolution_code IS NOT NULL
                    GROUP BY resolution_code
                """),
                {"analyst_id": analyst_id},
            )
            resolved_by_code = {row[0]: row[1] for row in resolved_by_code_result.fetchall()}
            my_stats["resolved_by_code"] = resolved_by_code

        return {
            "unassigned_total": (unassigned_row[0] or 0)
            + (unassigned_row[1] or 0)
            + (unassigned_row[2] or 0),
            "unassigned_pending": unassigned_row[0] or 0,
            "unassigned_in_review": unassigned_row[1] or 0,
            "unassigned_escalated": unassigned_row[2] or 0,
            **my_stats,
        }

    def _row_to_dict(self, row) -> dict[str, Any]:
        """Convert a database row to a dictionary."""
        return {
            "id": row[0],
            "transaction_id": row[1],
            "status": row[2],
            "priority": row[3],
            "assigned_analyst_id": row[4],
            "assigned_at": row[5],
            "case_id": row[6],
            "resolved_at": row[7],
            "resolved_by": row[8],
            "resolution_code": row[9],
            "resolution_notes": row[10],
            "escalated_at": row[11],
            "escalated_to": row[12],
            "escalation_reason": row[13],
            "first_reviewed_at": row[14],
            "last_activity_at": row[15],
            "created_at": row[16],
            "updated_at": row[17],
            "transaction_amount": float(row[18]) if row[18] else None,
            "transaction_currency": row[19],
            "decision": row[20],
            "risk_level": row[21],
        }

    def _row_to_dict_full(self, row) -> dict[str, Any]:
        """Convert a full worklist row to dictionary matching WorklistItem schema."""
        return {
            "review_id": row[0],  # id -> review_id
            "transaction_id": row[1],
            "status": row[2],
            "priority": row[3],
            "assigned_analyst_id": row[4],
            "assigned_at": row[5],
            "case_id": row[6],
            "first_reviewed_at": row[7],
            "last_activity_at": row[8],
            "created_at": row[9],
            "updated_at": row[10],
            "transaction_amount": float(row[11]) if row[11] else None,
            "transaction_currency": row[12],
            "decision": row[13],
            "decision_reason": row[14],  # decision_reason added
            "risk_level": row[15],
            "card_id": row[16] if len(row) > 16 else None,
            "card_last4": row[17] if len(row) > 17 else None,
            "transaction_timestamp": row[18] if len(row) > 18 else None,
            "merchant_id": row[19] if len(row) > 19 else None,
            "merchant_category_code": row[20] if len(row) > 20 else None,
            "trace_id": row[21] if len(row) > 21 else None,
            "decision_score": None,  # Not selected in query
        }
