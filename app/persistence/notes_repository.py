"""Notes repository using psycopg v3 and SQLAlchemy 2.0 async.

Table: fraud_gov.analyst_notes
"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class NotesRepository:
    """Repository for fraud_gov.analyst_notes data access."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, note_id: UUID) -> dict[str, Any] | None:
        """Get note by ID."""
        result = await self.session.execute(
            text("""
                SELECT id, transaction_id, note_type, note_content,
                       analyst_id, analyst_name, analyst_email,
                       is_private, is_system_generated, case_id,
                       created_at, updated_at
                FROM fraud_gov.analyst_notes
                WHERE id = :note_id
            """),
            {"note_id": note_id},
        )
        row = result.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    async def list_by_transaction(
        self,
        transaction_id: UUID,
        include_private: bool = False,
        analyst_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List notes for a transaction."""
        conditions = ["transaction_id = :transaction_id"]
        params: dict[str, Any] = {"transaction_id": transaction_id, "limit": limit}

        # Filter private notes unless explicitly requested or user is author
        if not include_private:
            conditions.append("(is_private = FALSE OR analyst_id = :analyst_id)")
            params["analyst_id"] = analyst_id or ""

        where_clause = " AND ".join(conditions)

        result = await self.session.execute(
            text(f"""
                SELECT id, transaction_id, note_type, note_content,
                       analyst_id, analyst_name, analyst_email,
                       is_private, is_system_generated, case_id,
                       created_at, updated_at
                FROM fraud_gov.analyst_notes
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            params,
        )

        return [self._row_to_dict(row) for row in result.fetchall()]

    async def create(
        self,
        note_id: UUID,
        transaction_id: UUID,
        note_content: str,
        note_type: str,
        analyst_id: str,
        analyst_name: str | None = None,
        analyst_email: str | None = None,
        is_private: bool = False,
        is_system_generated: bool = False,
        case_id: UUID | None = None,
    ) -> dict[str, Any] | None:
        """Create a new note."""
        await self.session.execute(
            text("""
                INSERT INTO fraud_gov.analyst_notes (
                    id, transaction_id, note_type, note_content,
                    analyst_id, analyst_name, analyst_email,
                    is_private, is_system_generated, case_id,
                    created_at, updated_at
                ) VALUES (
                    :id, :transaction_id, :note_type, :note_content,
                    :analyst_id, :analyst_name, :analyst_email,
                    :is_private, :is_system_generated, :case_id,
                    NOW(), NOW()
                )
            """),
            {
                "id": note_id,
                "transaction_id": transaction_id,
                "note_type": note_type,
                "note_content": note_content,
                "analyst_id": analyst_id,
                "analyst_name": analyst_name,
                "analyst_email": analyst_email,
                "is_private": is_private,
                "is_system_generated": is_system_generated,
                "case_id": case_id,
            },
        )
        return await self.get_by_id(note_id)

    async def update(
        self,
        note_id: UUID,
        note_content: str,
        note_type: str | None = None,
        is_private: bool | None = None,
    ) -> dict[str, Any] | None:
        """Update a note."""
        update_fields = ["note_content = :note_content"]
        params: dict[str, Any] = {"note_id": note_id, "note_content": note_content}

        if note_type is not None:
            update_fields.append("note_type = :note_type")
            params["note_type"] = note_type
        if is_private is not None:
            update_fields.append("is_private = :is_private")
            params["is_private"] = is_private

        await self.session.execute(
            text(f"""
                UPDATE fraud_gov.analyst_notes
                SET {", ".join(update_fields)}
                WHERE id = :note_id
            """),
            params,
        )
        return await self.get_by_id(note_id)

    async def delete(self, note_id: UUID) -> bool:
        """Delete a note."""
        result = await self.session.execute(
            text("DELETE FROM fraud_gov.analyst_notes WHERE id = :note_id"),
            {"note_id": note_id},
        )
        return result.rowcount > 0

    async def check_ownership(self, note_id: UUID, analyst_id: str) -> bool:
        """Check if a note belongs to an analyst."""
        result = await self.session.execute(
            text(
                "SELECT 1 FROM fraud_gov.analyst_notes "
                "WHERE id = :note_id AND analyst_id = :analyst_id"
            ),
            {"note_id": note_id, "analyst_id": analyst_id},
        )
        return result.fetchone() is not None

    def _row_to_dict(self, row) -> dict[str, Any]:
        """Convert a database row to a dictionary."""
        return {
            "id": row[0],
            "transaction_id": row[1],
            "note_type": row[2],
            "note_content": row[3],
            "analyst_id": row[4],
            "analyst_name": row[5],
            "analyst_email": row[6],
            "is_private": row[7],
            "is_system_generated": row[8],
            "case_id": row[9],
            "created_at": row[10],
            "updated_at": row[11],
        }
