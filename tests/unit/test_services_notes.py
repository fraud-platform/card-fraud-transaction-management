"""Unit tests for NotesService."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.errors import ForbiddenError, NotFoundError, ValidationError
from app.services.notes_service import NotesService


class TestNotesService:
    """Tests for NotesService."""

    @pytest.mark.asyncio
    async def test_list_notes_default(self, mock_session):
        """Test listing notes with default parameters."""
        transaction_id = uuid4()
        mock_repository = AsyncMock()
        mock_repository.list_by_transaction = AsyncMock(
            return_value=[
                {
                    "id": uuid4(),
                    "transaction_id": transaction_id,
                    "note_type": "ANALYST",
                    "note_content": "Test note",
                    "analyst_id": "analyst_1",
                    "analyst_name": "Test Analyst",
                    "analyst_email": "test@example.com",
                    "is_private": False,
                    "is_system_generated": False,
                    "case_id": None,
                    "created_at": "2024-01-01T00:00:00",
                    "updated_at": "2024-01-01T00:00:00",
                }
            ]
        )

        with patch.object(
            NotesService,
            "__init__",
            lambda self, session: setattr(self, "repo", mock_repository),
        ):
            service = NotesService(mock_session)
            service.repo = mock_repository

            result = await service.list_notes(transaction_id)

            assert len(result) == 1
            assert result[0]["note_content"] == "Test note"
            mock_repository.list_by_transaction.assert_called_once_with(
                transaction_id=transaction_id,
                include_private=False,
                analyst_id=None,
                limit=100,
            )

    @pytest.mark.asyncio
    async def test_list_notes_with_private_filtering(self, mock_session):
        """Test listing notes with private note filtering."""
        transaction_id = uuid4()
        analyst_id = "analyst_1"
        mock_repository = AsyncMock()
        mock_repository.list_by_transaction = AsyncMock(
            return_value=[
                {
                    "id": uuid4(),
                    "transaction_id": transaction_id,
                    "note_type": "ANALYST",
                    "note_content": "Private note",
                    "analyst_id": analyst_id,
                    "analyst_name": "Test Analyst",
                    "analyst_email": "test@example.com",
                    "is_private": True,
                    "is_system_generated": False,
                    "case_id": None,
                    "created_at": "2024-01-01T00:00:00",
                    "updated_at": "2024-01-01T00:00:00",
                }
            ]
        )

        with patch.object(
            NotesService,
            "__init__",
            lambda self, session: setattr(self, "repo", mock_repository),
        ):
            service = NotesService(mock_session)
            service.repo = mock_repository

            result = await service.list_notes(
                transaction_id=transaction_id,
                include_private=True,
                analyst_id=analyst_id,
                limit=50,
            )

            assert len(result) == 1
            mock_repository.list_by_transaction.assert_called_once_with(
                transaction_id=transaction_id,
                include_private=True,
                analyst_id=analyst_id,
                limit=50,
            )

    @pytest.mark.asyncio
    async def test_get_note_success(self, mock_session):
        """Test getting a note successfully."""
        note_id = uuid4()
        analyst_id = "analyst_1"
        mock_repository = AsyncMock()
        mock_repository.get_by_id = AsyncMock(
            return_value={
                "id": note_id,
                "transaction_id": uuid4(),
                "note_type": "ANALYST",
                "note_content": "Test note",
                "analyst_id": analyst_id,
                "analyst_name": "Test Analyst",
                "analyst_email": "test@example.com",
                "is_private": False,
                "is_system_generated": False,
                "case_id": None,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            }
        )

        with patch.object(
            NotesService,
            "__init__",
            lambda self, session: setattr(self, "repo", mock_repository),
        ):
            service = NotesService(mock_session)
            service.repo = mock_repository

            result = await service.get_note(note_id, analyst_id)

            assert result["note_content"] == "Test note"
            mock_repository.get_by_id.assert_called_once_with(note_id)

    @pytest.mark.asyncio
    async def test_get_note_not_found(self, mock_session):
        """Test getting a non-existent note raises NotFoundError."""
        note_id = uuid4()
        mock_repository = AsyncMock()
        mock_repository.get_by_id = AsyncMock(return_value=None)

        with patch.object(
            NotesService,
            "__init__",
            lambda self, session: setattr(self, "repo", mock_repository),
        ):
            service = NotesService(mock_session)
            service.repo = mock_repository

            with pytest.raises(NotFoundError) as exc_info:
                await service.get_note(note_id)

            assert "Note not found" in str(exc_info.value)
            assert exc_info.value.details["note_id"] == str(note_id)

    @pytest.mark.asyncio
    async def test_get_note_private_access_denied(self, mock_session):
        """Test accessing a private note by non-owner raises ForbiddenError."""
        note_id = uuid4()
        owner_id = "analyst_1"
        other_analyst_id = "analyst_2"
        mock_repository = AsyncMock()
        mock_repository.get_by_id = AsyncMock(
            return_value={
                "id": note_id,
                "transaction_id": uuid4(),
                "note_type": "ANALYST",
                "note_content": "Private note",
                "analyst_id": owner_id,
                "analyst_name": "Owner",
                "analyst_email": "owner@example.com",
                "is_private": True,
                "is_system_generated": False,
                "case_id": None,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            }
        )

        with patch.object(
            NotesService,
            "__init__",
            lambda self, session: setattr(self, "repo", mock_repository),
        ):
            service = NotesService(mock_session)
            service.repo = mock_repository

            with pytest.raises(ForbiddenError) as exc_info:
                await service.get_note(note_id, other_analyst_id)

            assert "Access denied to private note" in str(exc_info.value)
            assert exc_info.value.details["note_id"] == str(note_id)

    @pytest.mark.asyncio
    async def test_get_note_private_by_owner(self, mock_session):
        """Test that owner can access their private note."""
        note_id = uuid4()
        analyst_id = "analyst_1"
        mock_repository = AsyncMock()
        mock_repository.get_by_id = AsyncMock(
            return_value={
                "id": note_id,
                "transaction_id": uuid4(),
                "note_type": "ANALYST",
                "note_content": "My private note",
                "analyst_id": analyst_id,
                "analyst_name": "Test Analyst",
                "analyst_email": "test@example.com",
                "is_private": True,
                "is_system_generated": False,
                "case_id": None,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            }
        )

        with patch.object(
            NotesService,
            "__init__",
            lambda self, session: setattr(self, "repo", mock_repository),
        ):
            service = NotesService(mock_session)
            service.repo = mock_repository

            result = await service.get_note(note_id, analyst_id)

            assert result["note_content"] == "My private note"

    @pytest.mark.asyncio
    async def test_create_note_success(self, mock_session):
        """Test creating a note successfully."""
        transaction_id = uuid4()
        mock_repository = AsyncMock()
        created_note = {
            "id": uuid4(),
            "transaction_id": transaction_id,
            "note_type": "ANALYST",
            "note_content": "New note",
            "analyst_id": "analyst_1",
            "analyst_name": "Test Analyst",
            "analyst_email": "test@example.com",
            "is_private": False,
            "is_system_generated": False,
            "case_id": None,
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }
        mock_repository.create = AsyncMock(return_value=created_note)

        with patch.object(
            NotesService,
            "__init__",
            lambda self, session: setattr(self, "repo", mock_repository),
        ):
            service = NotesService(mock_session)
            service.repo = mock_repository

            result = await service.create_note(
                transaction_id=transaction_id,
                note_content="New note",
                note_type="ANALYST",
                analyst_id="analyst_1",
                analyst_name="Test Analyst",
                analyst_email="test@example.com",
            )

            assert result["note_content"] == "New note"
            mock_repository.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_note_empty_content(self, mock_session):
        """Test creating a note with empty content raises ValidationError."""
        transaction_id = uuid4()
        mock_repository = AsyncMock()

        with patch.object(
            NotesService,
            "__init__",
            lambda self, session: setattr(self, "repo", mock_repository),
        ):
            service = NotesService(mock_session)
            service.repo = mock_repository

            with pytest.raises(ValidationError) as exc_info:
                await service.create_note(
                    transaction_id=transaction_id,
                    note_content="",
                    note_type="ANALYST",
                    analyst_id="analyst_1",
                )

            assert "Note content cannot be empty" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_note_whitespace_only_content(self, mock_session):
        """Test creating a note with whitespace-only content raises ValidationError."""
        transaction_id = uuid4()
        mock_repository = AsyncMock()

        with patch.object(
            NotesService,
            "__init__",
            lambda self, session: setattr(self, "repo", mock_repository),
        ):
            service = NotesService(mock_session)
            service.repo = mock_repository

            with pytest.raises(ValidationError) as exc_info:
                await service.create_note(
                    transaction_id=transaction_id,
                    note_content="   ",
                    note_type="ANALYST",
                    analyst_id="analyst_1",
                )

            assert "Note content cannot be empty" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_note_private(self, mock_session):
        """Test creating a private note."""
        transaction_id = uuid4()
        mock_repository = AsyncMock()
        created_note = {
            "id": uuid4(),
            "transaction_id": transaction_id,
            "note_type": "ANALYST",
            "note_content": "Private note",
            "analyst_id": "analyst_1",
            "analyst_name": "Test Analyst",
            "analyst_email": "test@example.com",
            "is_private": True,
            "is_system_generated": False,
            "case_id": None,
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }
        mock_repository.create = AsyncMock(return_value=created_note)

        with patch.object(
            NotesService,
            "__init__",
            lambda self, session: setattr(self, "repo", mock_repository),
        ):
            service = NotesService(mock_session)
            service.repo = mock_repository

            result = await service.create_note(
                transaction_id=transaction_id,
                note_content="Private note",
                note_type="ANALYST",
                analyst_id="analyst_1",
                is_private=True,
            )

            assert result["is_private"] is True

    @pytest.mark.asyncio
    async def test_create_note_system_generated(self, mock_session):
        """Test creating a system-generated note."""
        transaction_id = uuid4()
        mock_repository = AsyncMock()
        created_note = {
            "id": uuid4(),
            "transaction_id": transaction_id,
            "note_type": "SYSTEM",
            "note_content": "Auto-generated note",
            "analyst_id": "system",
            "analyst_name": None,
            "analyst_email": None,
            "is_private": False,
            "is_system_generated": True,
            "case_id": None,
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }
        mock_repository.create = AsyncMock(return_value=created_note)

        with patch.object(
            NotesService,
            "__init__",
            lambda self, session: setattr(self, "repo", mock_repository),
        ):
            service = NotesService(mock_session)
            service.repo = mock_repository

            result = await service.create_note(
                transaction_id=transaction_id,
                note_content="Auto-generated note",
                note_type="SYSTEM",
                analyst_id="system",
                is_system_generated=True,
            )

            assert result["is_system_generated"] is True

    @pytest.mark.asyncio
    async def test_update_note_success(self, mock_session):
        """Test updating a note successfully."""
        note_id = uuid4()
        analyst_id = "analyst_1"
        mock_repository = AsyncMock()
        mock_repository.get_by_id = AsyncMock(
            return_value={
                "id": note_id,
                "transaction_id": uuid4(),
                "note_type": "ANALYST",
                "note_content": "Original note",
                "analyst_id": analyst_id,
                "analyst_name": "Test Analyst",
                "analyst_email": "test@example.com",
                "is_private": False,
                "is_system_generated": False,
                "case_id": None,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            }
        )
        updated_note = {
            "id": note_id,
            "transaction_id": uuid4(),
            "note_type": "ANALYST",
            "note_content": "Updated note",
            "analyst_id": analyst_id,
            "analyst_name": "Test Analyst",
            "analyst_email": "test@example.com",
            "is_private": False,
            "is_system_generated": False,
            "case_id": None,
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T01:00:00",
        }
        mock_repository.update = AsyncMock(return_value=updated_note)

        with patch.object(
            NotesService,
            "__init__",
            lambda self, session: setattr(self, "repo", mock_repository),
        ):
            service = NotesService(mock_session)
            service.repo = mock_repository

            result = await service.update_note(
                note_id=note_id,
                note_content="Updated note",
                analyst_id=analyst_id,
            )

            assert result["note_content"] == "Updated note"
            mock_repository.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_note_not_found(self, mock_session):
        """Test updating a non-existent note raises NotFoundError."""
        note_id = uuid4()
        mock_repository = AsyncMock()
        mock_repository.get_by_id = AsyncMock(return_value=None)

        with patch.object(
            NotesService,
            "__init__",
            lambda self, session: setattr(self, "repo", mock_repository),
        ):
            service = NotesService(mock_session)
            service.repo = mock_repository

            with pytest.raises(NotFoundError) as exc_info:
                await service.update_note(
                    note_id=note_id,
                    note_content="Updated content",
                    analyst_id="analyst_1",
                )

            assert "Note not found" in str(exc_info.value)
            assert exc_info.value.details["note_id"] == str(note_id)

    @pytest.mark.asyncio
    async def test_update_note_not_author(self, mock_session):
        """Test updating a note by non-author raises ForbiddenError."""
        note_id = uuid4()
        owner_id = "analyst_1"
        other_analyst_id = "analyst_2"
        mock_repository = AsyncMock()
        mock_repository.get_by_id = AsyncMock(
            return_value={
                "id": note_id,
                "transaction_id": uuid4(),
                "note_type": "ANALYST",
                "note_content": "Original note",
                "analyst_id": owner_id,
                "analyst_name": "Owner",
                "analyst_email": "owner@example.com",
                "is_private": False,
                "is_system_generated": False,
                "case_id": None,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            }
        )

        with patch.object(
            NotesService,
            "__init__",
            lambda self, session: setattr(self, "repo", mock_repository),
        ):
            service = NotesService(mock_session)
            service.repo = mock_repository

            with pytest.raises(ForbiddenError) as exc_info:
                await service.update_note(
                    note_id=note_id,
                    note_content="Updated content",
                    analyst_id=other_analyst_id,
                )

            assert "Only the note author can edit it" in str(exc_info.value)
            assert exc_info.value.details["note_id"] == str(note_id)
            assert exc_info.value.details["author_id"] == owner_id

    @pytest.mark.asyncio
    async def test_update_note_system_generated(self, mock_session):
        """Test updating a system-generated note raises ValidationError."""
        note_id = uuid4()
        system_analyst_id = "system"
        mock_repository = AsyncMock()
        mock_repository.get_by_id = AsyncMock(
            return_value={
                "id": note_id,
                "transaction_id": uuid4(),
                "note_type": "SYSTEM",
                "note_content": "System note",
                "analyst_id": system_analyst_id,
                "analyst_name": None,
                "analyst_email": None,
                "is_private": False,
                "is_system_generated": True,
                "case_id": None,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            }
        )

        with patch.object(
            NotesService,
            "__init__",
            lambda self, session: setattr(self, "repo", mock_repository),
        ):
            service = NotesService(mock_session)
            service.repo = mock_repository

            with pytest.raises(ValidationError) as exc_info:
                await service.update_note(
                    note_id=note_id,
                    note_content="Updated content",
                    analyst_id=system_analyst_id,
                )

            assert "System-generated notes cannot be edited" in str(exc_info.value)
            assert exc_info.value.details["note_id"] == str(note_id)

    @pytest.mark.asyncio
    async def test_update_note_empty_content(self, mock_session):
        """Test updating a note with empty content raises ValidationError."""
        note_id = uuid4()
        analyst_id = "analyst_1"
        mock_repository = AsyncMock()
        mock_repository.get_by_id = AsyncMock(
            return_value={
                "id": note_id,
                "transaction_id": uuid4(),
                "note_type": "ANALYST",
                "note_content": "Original note",
                "analyst_id": analyst_id,
                "analyst_name": "Test Analyst",
                "analyst_email": "test@example.com",
                "is_private": False,
                "is_system_generated": False,
                "case_id": None,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            }
        )

        with patch.object(
            NotesService,
            "__init__",
            lambda self, session: setattr(self, "repo", mock_repository),
        ):
            service = NotesService(mock_session)
            service.repo = mock_repository

            with pytest.raises(ValidationError) as exc_info:
                await service.update_note(
                    note_id=note_id,
                    note_content="",
                    analyst_id=analyst_id,
                )

            assert "Note content cannot be empty" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_note_with_optional_params(self, mock_session):
        """Test updating a note with optional parameters."""
        note_id = uuid4()
        analyst_id = "analyst_1"
        mock_repository = AsyncMock()
        mock_repository.get_by_id = AsyncMock(
            return_value={
                "id": note_id,
                "transaction_id": uuid4(),
                "note_type": "ANALYST",
                "note_content": "Original note",
                "analyst_id": analyst_id,
                "analyst_name": "Test Analyst",
                "analyst_email": "test@example.com",
                "is_private": False,
                "is_system_generated": False,
                "case_id": None,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            }
        )
        updated_note = {
            "id": note_id,
            "transaction_id": uuid4(),
            "note_type": "INVESTIGATION",
            "note_content": "Updated note",
            "analyst_id": analyst_id,
            "analyst_name": "Test Analyst",
            "analyst_email": "test@example.com",
            "is_private": True,
            "is_system_generated": False,
            "case_id": None,
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T01:00:00",
        }
        mock_repository.update = AsyncMock(return_value=updated_note)

        with patch.object(
            NotesService,
            "__init__",
            lambda self, session: setattr(self, "repo", mock_repository),
        ):
            service = NotesService(mock_session)
            service.repo = mock_repository

            result = await service.update_note(
                note_id=note_id,
                note_content="Updated note",
                analyst_id=analyst_id,
                note_type="INVESTIGATION",
                is_private=True,
            )

            assert result["note_type"] == "INVESTIGATION"
            assert result["is_private"] is True
            mock_repository.update.assert_called_once_with(
                note_id=note_id,
                note_content="Updated note",
                note_type="INVESTIGATION",
                is_private=True,
            )

    @pytest.mark.asyncio
    async def test_delete_note_success_as_owner(self, mock_session):
        """Test deleting a note successfully as owner."""
        note_id = uuid4()
        analyst_id = "analyst_1"
        mock_repository = AsyncMock()
        mock_repository.get_by_id = AsyncMock(
            return_value={
                "id": note_id,
                "transaction_id": uuid4(),
                "note_type": "ANALYST",
                "note_content": "Note to delete",
                "analyst_id": analyst_id,
                "analyst_name": "Test Analyst",
                "analyst_email": "test@example.com",
                "is_private": False,
                "is_system_generated": False,
                "case_id": None,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            }
        )
        mock_repository.delete = AsyncMock(return_value=True)

        with patch.object(
            NotesService,
            "__init__",
            lambda self, session: setattr(self, "repo", mock_repository),
        ):
            service = NotesService(mock_session)
            service.repo = mock_repository

            result = await service.delete_note(
                note_id=note_id,
                analyst_id=analyst_id,
                is_supervisor=False,
            )

            assert result is True
            mock_repository.delete.assert_called_once_with(note_id=note_id)

    @pytest.mark.asyncio
    async def test_delete_note_success_as_supervisor(self, mock_session):
        """Test deleting a note successfully as supervisor."""
        note_id = uuid4()
        owner_id = "analyst_1"
        supervisor_id = "supervisor_1"
        mock_repository = AsyncMock()
        mock_repository.get_by_id = AsyncMock(
            return_value={
                "id": note_id,
                "transaction_id": uuid4(),
                "note_type": "ANALYST",
                "note_content": "Note to delete",
                "analyst_id": owner_id,
                "analyst_name": "Test Analyst",
                "analyst_email": "test@example.com",
                "is_private": False,
                "is_system_generated": False,
                "case_id": None,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            }
        )
        mock_repository.delete = AsyncMock(return_value=True)

        with patch.object(
            NotesService,
            "__init__",
            lambda self, session: setattr(self, "repo", mock_repository),
        ):
            service = NotesService(mock_session)
            service.repo = mock_repository

            result = await service.delete_note(
                note_id=note_id,
                analyst_id=supervisor_id,
                is_supervisor=True,
            )

            assert result is True
            mock_repository.delete.assert_called_once_with(note_id=note_id)

    @pytest.mark.asyncio
    async def test_delete_note_not_found(self, mock_session):
        """Test deleting a non-existent note raises NotFoundError."""
        note_id = uuid4()
        mock_repository = AsyncMock()
        mock_repository.get_by_id = AsyncMock(return_value=None)

        with patch.object(
            NotesService,
            "__init__",
            lambda self, session: setattr(self, "repo", mock_repository),
        ):
            service = NotesService(mock_session)
            service.repo = mock_repository

            with pytest.raises(NotFoundError) as exc_info:
                await service.delete_note(
                    note_id=note_id,
                    analyst_id="analyst_1",
                    is_supervisor=False,
                )

            assert "Note not found" in str(exc_info.value)
            assert exc_info.value.details["note_id"] == str(note_id)

    @pytest.mark.asyncio
    async def test_delete_note_permission_denied_not_owner(self, mock_session):
        """Test deleting a note by non-owner non-supervisor raises ForbiddenError."""
        note_id = uuid4()
        owner_id = "analyst_1"
        other_analyst_id = "analyst_2"
        mock_repository = AsyncMock()
        mock_repository.get_by_id = AsyncMock(
            return_value={
                "id": note_id,
                "transaction_id": uuid4(),
                "note_type": "ANALYST",
                "note_content": "Note to delete",
                "analyst_id": owner_id,
                "analyst_name": "Owner",
                "analyst_email": "owner@example.com",
                "is_private": False,
                "is_system_generated": False,
                "case_id": None,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            }
        )

        with patch.object(
            NotesService,
            "__init__",
            lambda self, session: setattr(self, "repo", mock_repository),
        ):
            service = NotesService(mock_session)
            service.repo = mock_repository

            with pytest.raises(ForbiddenError) as exc_info:
                await service.delete_note(
                    note_id=note_id,
                    analyst_id=other_analyst_id,
                    is_supervisor=False,
                )

            assert "Only the note author or a supervisor can delete it" in str(exc_info.value)
            assert exc_info.value.details["note_id"] == str(note_id)
            assert exc_info.value.details["author_id"] == owner_id

    @pytest.mark.asyncio
    async def test_delete_note_system_generated(self, mock_session):
        """Test deleting a system-generated note raises ValidationError."""
        note_id = uuid4()
        analyst_id = "analyst_1"
        mock_repository = AsyncMock()
        mock_repository.get_by_id = AsyncMock(
            return_value={
                "id": note_id,
                "transaction_id": uuid4(),
                "note_type": "SYSTEM",
                "note_content": "System note",
                "analyst_id": "system",
                "analyst_name": None,
                "analyst_email": None,
                "is_private": False,
                "is_system_generated": True,
                "case_id": None,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            }
        )

        with patch.object(
            NotesService,
            "__init__",
            lambda self, session: setattr(self, "repo", mock_repository),
        ):
            service = NotesService(mock_session)
            service.repo = mock_repository

            with pytest.raises(ValidationError) as exc_info:
                await service.delete_note(
                    note_id=note_id,
                    analyst_id=analyst_id,
                    is_supervisor=True,
                )

            assert "System-generated notes cannot be deleted" in str(exc_info.value)
            assert exc_info.value.details["note_id"] == str(note_id)

    @pytest.mark.asyncio
    async def test_check_note_ownership_true(self, mock_session):
        """Test checking note ownership returns True when owner."""
        note_id = uuid4()
        analyst_id = "analyst_1"
        mock_repository = AsyncMock()
        mock_repository.check_ownership = AsyncMock(return_value=True)

        with patch.object(
            NotesService,
            "__init__",
            lambda self, session: setattr(self, "repo", mock_repository),
        ):
            service = NotesService(mock_session)
            service.repo = mock_repository

            result = await service.check_note_ownership(note_id, analyst_id)

            assert result is True
            mock_repository.check_ownership.assert_called_once_with(
                note_id=note_id, analyst_id=analyst_id
            )

    @pytest.mark.asyncio
    async def test_check_note_ownership_false(self, mock_session):
        """Test checking note ownership returns False when not owner."""
        note_id = uuid4()
        analyst_id = "analyst_1"
        mock_repository = AsyncMock()
        mock_repository.check_ownership = AsyncMock(return_value=False)

        with patch.object(
            NotesService,
            "__init__",
            lambda self, session: setattr(self, "repo", mock_repository),
        ):
            service = NotesService(mock_session)
            service.repo = mock_repository

            result = await service.check_note_ownership(note_id, analyst_id)

            assert result is False
            mock_repository.check_ownership.assert_called_once_with(
                note_id=note_id, analyst_id=analyst_id
            )
