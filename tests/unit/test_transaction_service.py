"""Unit tests for transaction service."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid7

import pytest

from app.services.transaction_service import TransactionService


class TestTransactionService:
    """Test TransactionService class."""

    def test_service_creation(self):
        """Test creating TransactionService instance."""
        mock_session = MagicMock()
        service = TransactionService(mock_session)
        assert service.session == mock_session
        assert service.repository is not None

    def test_service_has_get_transaction_method(self):
        """Test TransactionService has get_transaction method."""
        assert hasattr(TransactionService, "get_transaction")
        assert callable(TransactionService.get_transaction)

    def test_service_has_list_transactions_method(self):
        """Test TransactionService has list_transactions method."""
        assert hasattr(TransactionService, "list_transactions")
        assert callable(TransactionService.list_transactions)

    def test_service_has_get_metrics_method(self):
        """Test TransactionService has get_metrics method."""
        assert hasattr(TransactionService, "get_metrics")
        assert callable(TransactionService.get_metrics)


class TestTransactionServiceAsyncMethods:
    """Test TransactionService async methods."""

    @pytest.mark.asyncio
    async def test_get_transaction_returns_transaction(self):
        """Test get_transaction returns transaction data."""
        mock_session = MagicMock()
        service = TransactionService(mock_session)

        test_uuid = uuid7()
        transaction_data = {
            "transaction_id": test_uuid,
            "card_id": "tok_card123",
            "amount": 100.00,
            "currency": "USD",
            "decision": "APPROVE",
            "decision_reason": "DEFAULT_ALLOW",
        }

        service.repository.get_by_transaction_id = AsyncMock(return_value=transaction_data)
        service.repository.get_rule_matches_for_event = AsyncMock(return_value=[])

        # Use UUID directly
        result = await service.get_transaction(test_uuid)
        assert result is not None
        assert result["transaction_id"] == test_uuid

    @pytest.mark.asyncio
    async def test_get_transaction_returns_none_for_missing(self):
        """Test get_transaction returns None for missing transaction."""
        mock_session = MagicMock()
        service = TransactionService(mock_session)

        service.repository.get_by_transaction_id = AsyncMock(return_value=None)

        result = await service.get_transaction(uuid7())
        assert result is None

    @pytest.mark.asyncio
    async def test_get_transaction_returns_none_for_invalid_uuid(self):
        """Test get_transaction returns None for invalid UUID string."""
        mock_session = MagicMock()
        service = TransactionService(mock_session)

        # Invalid UUID string should return None
        result = await service.get_transaction("not-a-valid-uuid")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_transaction_includes_rules_when_requested(self):
        """Test get_transaction includes rule matches when include_rules=True."""
        mock_session = MagicMock()
        service = TransactionService(mock_session)

        test_id = uuid7()
        test_uuid = uuid7()
        transaction_data = {
            "id": str(test_id),  # Required for fetching rule matches
            "transaction_id": test_uuid,
            "card_id": "tok_card456",
            "amount": 200.00,
            "currency": "USD",
            "decision": "DECLINE",
            "decision_reason": "RULE_MATCH",
            "matched_rules": [],  # Will be replaced when include_rules=True
        }
        rule_matches = [{"rule_id": "rule_001", "rule_version": 1, "rule_name": "Velocity Check"}]

        service.repository.get_by_transaction_id = AsyncMock(return_value=transaction_data)
        service.repository.get_rule_matches_for_event = AsyncMock(return_value=rule_matches)

        result = await service.get_transaction(test_uuid, include_rules=True)
        assert result is not None
        assert "matched_rules" in result
        assert len(result["matched_rules"]) == 1

    @pytest.mark.asyncio
    async def test_get_transaction_excludes_rules_when_not_requested(self):
        """Test get_transaction excludes rules when include_rules=False."""
        mock_session = MagicMock()
        service = TransactionService(mock_session)

        test_uuid = uuid7()
        transaction_data = {
            "transaction_id": test_uuid,
            "card_id": "tok_card789",
            "amount": 300.00,
            "currency": "USD",
            "decision": "APPROVE",
            "decision_reason": "DEFAULT_ALLOW",
        }

        service.repository.get_by_transaction_id = AsyncMock(return_value=transaction_data)
        # Note: When include_rules=False, get_rule_matches_for_event is not called
        service.repository.get_rule_matches_for_event = AsyncMock(
            return_value=[{"rule_id": "rule_002"}]
        )

        result = await service.get_transaction(test_uuid, include_rules=False)
        assert result is not None
        # When include_rules=False, get_rule_matches_for_event should NOT be called
        service.repository.get_rule_matches_for_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_transactions_returns_paginated_results(self):
        """Test list_transactions returns paginated results."""
        mock_session = MagicMock()
        service = TransactionService(mock_session)

        transactions = [
            {"transaction_id": uuid7(), "card_id": "tok_1", "amount": 100.00},
            {"transaction_id": uuid7(), "card_id": "tok_2", "amount": 200.00},
        ]

        service.repository.list = AsyncMock(return_value=(transactions, "next_cursor", 10))

        result = await service.list_transactions(page_size=50)
        assert result is not None
        assert "items" in result
        assert "total" in result
        assert "page_size" in result
        assert "next_cursor" in result
        assert len(result["items"]) == 2
        assert result["total"] == 10

    @pytest.mark.asyncio
    async def test_list_transactions_with_filters(self):
        """Test list_transactions passes supported filters to repository."""
        mock_session = MagicMock()
        service = TransactionService(mock_session)

        service.repository.list = AsyncMock(return_value=([], None, 0))

        from_date = datetime.now()
        to_date = datetime.now()

        await service.list_transactions(
            page_size=50,
            card_id="tok_card123",
            decision="APPROVE",
            from_date=from_date,
            to_date=to_date,
        )

        service.repository.list.assert_called_once()
        call_kwargs = service.repository.list.call_args[1]
        assert call_kwargs["card_id"] == "tok_card123"
        assert call_kwargs["decision"] == "APPROVE"
        assert call_kwargs["from_date"] == from_date
        assert call_kwargs["to_date"] == to_date

    @pytest.mark.asyncio
    async def test_get_metrics_returns_metrics(self):
        """Test get_metrics returns metrics data."""
        mock_session = MagicMock()
        service = TransactionService(mock_session)

        metrics = {
            "total_transactions": 100,
            "approved_count": 80,
            "declined_count": 15,
            "postauth_count": 5,
            "total_amount": 50000.00,
            "avg_amount": 500.00,
        }

        service.repository.get_metrics = AsyncMock(return_value=metrics)

        result = await service.get_metrics()
        assert result is not None
        assert result["total_transactions"] == 100
        assert result["approved_count"] == 80

    @pytest.mark.asyncio
    async def test_get_metrics_with_date_range(self):
        """Test get_metrics passes date range to repository."""
        mock_session = MagicMock()
        service = TransactionService(mock_session)

        service.repository.get_metrics = AsyncMock(return_value={"total_transactions": 0})

        from_date = datetime.now()
        to_date = datetime.now()

        await service.get_metrics(from_date=from_date, to_date=to_date)

        service.repository.get_metrics.assert_called_once_with(from_date, to_date)


class TestTransactionServiceMethodSignatures:
    """Test TransactionService method signatures."""

    @pytest.mark.asyncio
    async def test_get_transaction_is_async(self):
        """Test get_transaction is an async coroutine function."""
        import inspect

        assert inspect.iscoroutinefunction(TransactionService.get_transaction)

    @pytest.mark.asyncio
    async def test_list_transactions_is_async(self):
        """Test list_transactions is an async coroutine function."""
        import inspect

        assert inspect.iscoroutinefunction(TransactionService.list_transactions)

    @pytest.mark.asyncio
    async def test_get_metrics_is_async(self):
        """Test get_metrics is an async coroutine function."""
        import inspect

        assert inspect.iscoroutinefunction(TransactionService.get_metrics)

    @pytest.mark.asyncio
    async def test_get_transaction_accepts_parameters(self):
        """Test get_transaction accepts required parameters."""
        import inspect

        sig = inspect.signature(TransactionService.get_transaction)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "transaction_id" in params
        assert "include_rules" in params


class TestTransactionServiceRepositoryIntegration:
    """Test TransactionService integrates with repository."""

    def test_service_creates_repository_instance(self):
        """Test service creates TransactionRepository instance."""
        mock_session = MagicMock()
        service = TransactionService(mock_session)
        from app.persistence.transaction_repository import TransactionRepository

        assert isinstance(service.repository, TransactionRepository)

    def test_service_uses_same_session(self):
        """Test service uses same session for repository."""
        mock_session = MagicMock()
        service = TransactionService(mock_session)
        assert service.session is mock_session
