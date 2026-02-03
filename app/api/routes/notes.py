"""API routes for analyst notes."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import RequireTxnView
from app.schemas.notes import (
    NoteCreate,
    NoteListResponse,
    NoteResponse,
    NoteUpdate,
)
from app.services.notes_service import NotesService

router = APIRouter(prefix="/transactions/{transaction_id}/notes", tags=["notes"])


def get_notes_service(session: AsyncSession = Depends(get_session)) -> NotesService:
    """Get notes service instance."""
    return NotesService(session)


def is_supervisor(current_user: RequireTxnView) -> bool:
    """Check if current user is a supervisor."""
    return current_user.is_fraud_supervisor


@router.get("", response_model=NoteListResponse)
async def list_notes(
    transaction_id: UUID,
    current_user: RequireTxnView,
    limit: int = 100,
    notes_service: NotesService = Depends(get_notes_service),
) -> dict:
    """List notes for a transaction.

    Private notes are only returned to their author or supervisors.
    """
    notes = await notes_service.list_notes(
        transaction_id=transaction_id,
        include_private=is_supervisor(current_user),
        analyst_id=current_user.user_id,
        limit=limit,
    )
    return {
        "items": notes,
        "total": len(notes),
        "page_size": limit,
        "has_more": False,
    }


@router.post("", response_model=NoteResponse, status_code=201)
async def create_note(
    transaction_id: UUID,
    request: NoteCreate,
    current_user: RequireTxnView,
    notes_service: NotesService = Depends(get_notes_service),
) -> dict:
    """Create a new note on a transaction."""
    return await notes_service.create_note(
        transaction_id=transaction_id,
        note_content=request.note_content,
        note_type=request.note_type.value,
        analyst_id=current_user.user_id,
        analyst_name=current_user.name,
        analyst_email=current_user.email,
        is_private=request.is_private,
    )


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(
    transaction_id: UUID,
    note_id: UUID,
    current_user: RequireTxnView,
    notes_service: NotesService = Depends(get_notes_service),
) -> dict:
    """Get a specific note."""
    return await notes_service.get_note(
        note_id=note_id,
        analyst_id=current_user.user_id,
    )


@router.patch("/{note_id}", response_model=NoteResponse)
async def update_note(
    transaction_id: UUID,
    note_id: UUID,
    request: NoteUpdate,
    current_user: RequireTxnView,
    notes_service: NotesService = Depends(get_notes_service),
) -> dict:
    """Update a note.

    Only the note author can update their own notes.
    System-generated notes cannot be edited.
    """
    return await notes_service.update_note(
        note_id=note_id,
        note_content=request.note_content,
        analyst_id=current_user.user_id,
        note_type=request.note_type.value if request.note_type else None,
        is_private=request.is_private if request.is_private is not None else None,
    )


@router.delete("/{note_id}", status_code=204)
async def delete_note(
    transaction_id: UUID,
    note_id: UUID,
    current_user: RequireTxnView,
    notes_service: NotesService = Depends(get_notes_service),
) -> None:
    """Delete a note.

    Only the note author or a supervisor can delete notes.
    System-generated notes cannot be deleted.
    """
    await notes_service.delete_note(
        note_id=note_id,
        analyst_id=current_user.user_id,
        is_supervisor=is_supervisor(current_user),
    )
