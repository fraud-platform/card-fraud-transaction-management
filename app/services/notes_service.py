"""Notes service for analyst notes on transactions."""

import logging
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, NotFoundError, ValidationError
from app.persistence.notes_repository import NotesRepository

logger = logging.getLogger(__name__)


class NotesService:
    """Service for analyst notes operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = NotesRepository(session)

    async def list_notes(
        self,
        transaction_id: UUID,
        include_private: bool = False,
        analyst_id: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """List notes for a transaction."""
        return await self.repo.list_by_transaction(
            transaction_id=transaction_id,
            include_private=include_private,
            analyst_id=analyst_id,
            limit=limit,
        )

    async def get_note(
        self,
        note_id: UUID,
        analyst_id: str | None = None,
    ) -> dict:
        """Get a note by ID."""
        note = await self.repo.get_by_id(note_id)
        if not note:
            raise NotFoundError("Note not found", details={"note_id": str(note_id)})

        # Check privacy
        if note["is_private"] and analyst_id != note["analyst_id"]:
            raise ForbiddenError(
                "Access denied to private note",
                details={"note_id": str(note_id)},
            )

        return note

    async def create_note(
        self,
        transaction_id: UUID,
        note_content: str,
        note_type: str,
        analyst_id: str,
        analyst_name: str | None = None,
        analyst_email: str | None = None,
        is_private: bool = False,
        is_system_generated: bool = False,
        case_id: UUID | None = None,
    ) -> dict:
        """Create a new note."""
        if not note_content or not note_content.strip():
            raise ValidationError(
                "Note content cannot be empty", details={"note_content": note_content}
            )

        return await self.repo.create(
            note_id=uuid4(),
            transaction_id=transaction_id,
            note_content=note_content,
            note_type=note_type,
            analyst_id=analyst_id,
            analyst_name=analyst_name,
            analyst_email=analyst_email,
            is_private=is_private,
            is_system_generated=is_system_generated,
            case_id=case_id,
        )

    async def update_note(
        self,
        note_id: UUID,
        note_content: str,
        analyst_id: str,
        note_type: str | None = None,
        is_private: bool | None = None,
    ) -> dict:
        """Update a note."""
        note = await self.repo.get_by_id(note_id)
        if not note:
            raise NotFoundError("Note not found", details={"note_id": str(note_id)})

        # Check ownership (only author can edit)
        if note["analyst_id"] != analyst_id:
            raise ForbiddenError(
                "Only the note author can edit it",
                details={"note_id": str(note_id), "author_id": note["analyst_id"]},
            )

        # System-generated notes cannot be edited
        if note.get("is_system_generated"):
            raise ValidationError(
                "System-generated notes cannot be edited",
                details={"note_id": str(note_id)},
            )

        if not note_content or not note_content.strip():
            raise ValidationError(
                "Note content cannot be empty", details={"note_content": note_content}
            )

        return await self.repo.update(
            note_id=note_id,
            note_content=note_content,
            note_type=note_type,
            is_private=is_private,
        )

    async def delete_note(
        self,
        note_id: UUID,
        analyst_id: str,
        is_supervisor: bool = False,
    ) -> bool:
        """Delete a note."""
        note = await self.repo.get_by_id(note_id)
        if not note:
            raise NotFoundError("Note not found", details={"note_id": str(note_id)})

        # Check ownership or supervisor status
        is_owner = note["analyst_id"] == analyst_id
        if not is_owner and not is_supervisor:
            raise ForbiddenError(
                "Only the note author or a supervisor can delete it",
                details={"note_id": str(note_id), "author_id": note["analyst_id"]},
            )

        # System-generated notes cannot be deleted
        if note.get("is_system_generated"):
            raise ValidationError(
                "System-generated notes cannot be deleted",
                details={"note_id": str(note_id)},
            )

        return await self.repo.delete(note_id=note_id)

    async def check_note_ownership(
        self,
        note_id: UUID,
        analyst_id: str,
    ) -> bool:
        """Check if a note belongs to an analyst."""
        return await self.repo.check_ownership(note_id=note_id, analyst_id=analyst_id)
