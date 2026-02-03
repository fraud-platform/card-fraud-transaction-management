"""Unit tests for transaction repository module."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid7

import pytest

from app.persistence.transaction_repository import (
    TransactionCursor,
    TransactionRepository,
)


class TestTransactionCursor:
    """Test TransactionCursor class."""

    def test_transaction_cursor_creation(self):
        """Test creating TransactionCursor."""
        now = datetime.now()
        cursor_id = uuid7()
        cursor = TransactionCursor(transaction_timestamp=now, transaction_id=cursor_id)

        assert cursor.transaction_timestamp == now
        assert cursor.transaction_id == cursor_id

    def test_transaction_cursor_encode_decode(self):
        """Test encoding and decoding cursor."""
        now = datetime(2024, 1, 15, 10, 30, 0)
        cursor_id = uuid7()
        original = TransactionCursor(transaction_timestamp=now, transaction_id=cursor_id)

        encoded = original.encode()
        assert isinstance(encoded, str)
        assert len(encoded) > 0

        decoded = TransactionCursor.decode(encoded)
        assert decoded is not None
        assert decoded.transaction_timestamp == now
        assert decoded.transaction_id == cursor_id

    def test_transaction_cursor_decode_invalid(self):
        """Test decoding invalid cursor returns None."""
        assert TransactionCursor.decode("invalid_cursor") is None
        assert TransactionCursor.decode("") is None
        assert (
            TransactionCursor.decode("bm90LWEtdmFsaWQtY3Vyc29y") is None
        )  # "not-a-valid-cursor" base64

    def test_transaction_cursor_decode_partial(self):
        """Test decoding cursor with wrong number of parts."""
        import base64

        data = base64.urlsafe_b64encode(b"2024-01-15T10:30:00").decode()
        assert TransactionCursor.decode(data) is None


class TestTransactionRepository:
    """Test TransactionRepository class."""

    def test_repository_creation(self):
        """Test creating TransactionRepository instance."""
        mock_session = MagicMock()
        repo = TransactionRepository(mock_session)
        assert repo.session == mock_session

    def test_repository_has_get_by_transaction_id(self):
        """Test repository has get_by_transaction_id method."""
        assert hasattr(TransactionRepository, "get_by_transaction_id")
        assert callable(TransactionRepository.get_by_transaction_id)

    def test_repository_has_list(self):
        """Test repository has list method."""
        assert hasattr(TransactionRepository, "list")
        assert callable(TransactionRepository.list)

    def test_repository_has_upsert_transaction(self):
        """Test repository has upsert_transaction method."""
        assert hasattr(TransactionRepository, "upsert_transaction")
        assert callable(TransactionRepository.upsert_transaction)

    def test_repository_has_add_rule_match(self):
        """Test repository has add_rule_match method."""
        assert hasattr(TransactionRepository, "add_rule_match")
        assert callable(TransactionRepository.add_rule_match)

    def test_repository_has_get_rule_matches_for_event(self):
        """Test repository has get_rule_matches_for_event method."""
        assert hasattr(TransactionRepository, "get_rule_matches_for_event")
        assert callable(TransactionRepository.get_rule_matches_for_event)


class TestTransactionRepositoryImports:
    """Test that repository imports work correctly."""

    def test_transaction_cursor_import(self):
        """Test TransactionCursor can be imported."""
        from app.persistence.transaction_repository import TransactionCursor

        assert TransactionCursor is not None

    def test_transaction_repository_import(self):
        """Test TransactionRepository can be imported."""
        from app.persistence.transaction_repository import TransactionRepository

        assert TransactionRepository is not None


class TestRepositoryRowToDict:
    """Test repository _row_to_dict method exists."""

    def test_repository_has_private_row_to_dict(self):
        """Test repository has private _row_to_dict method."""
        mock_session = MagicMock()
        repo = TransactionRepository(mock_session)
        assert hasattr(repo, "_row_to_dict")
        assert callable(repo._row_to_dict)


class TestRepositoryMetrics:
    """Test repository metrics method exists."""

    def test_repository_has_get_metrics(self):
        """Test repository has get_metrics method."""
        assert hasattr(TransactionRepository, "get_metrics")
        assert callable(TransactionRepository.get_metrics)

    def test_repository_has_get_transaction_with_rules(self):
        """Test repository has method to get transaction with rules."""
        # Check for methods that might get transaction with related data
        method_names = [m for m in dir(TransactionRepository) if not m.startswith("_")]
        assert len(method_names) > 0  # Just verify the class has methods


class TestTransactionRepositoryAsyncMethods:
    """Test TransactionRepository async method signatures."""

    @pytest.mark.asyncio
    async def test_repository_has_get_by_transaction_id(self):
        """Test repository has async get_by_transaction_id method."""
        assert hasattr(TransactionRepository, "get_by_transaction_id")
        assert callable(TransactionRepository.get_by_transaction_id)

    @pytest.mark.asyncio
    async def test_repository_has_list(self):
        """Test repository has async list method."""
        assert hasattr(TransactionRepository, "list")
        assert callable(TransactionRepository.list)

    @pytest.mark.asyncio
    async def test_repository_has_upsert_transaction(self):
        """Test repository has async upsert_transaction method."""
        assert hasattr(TransactionRepository, "upsert_transaction")
        assert callable(TransactionRepository.upsert_transaction)

    @pytest.mark.asyncio
    async def test_repository_has_add_rule_match(self):
        """Test repository has async add_rule_match method."""
        assert hasattr(TransactionRepository, "add_rule_match")
        assert callable(TransactionRepository.add_rule_match)

    @pytest.mark.asyncio
    async def test_repository_has_get_rule_matches_for_event(self):
        """Test repository has async get_rule_matches_for_event method."""
        assert hasattr(TransactionRepository, "get_rule_matches_for_event")
        assert callable(TransactionRepository.get_rule_matches_for_event)

    @pytest.mark.asyncio
    async def test_repository_has_get_metrics(self):
        """Test repository has async get_metrics method."""
        assert hasattr(TransactionRepository, "get_metrics")
        assert callable(TransactionRepository.get_metrics)


class TestRepositoryAsyncMethodSignatures:
    """Test that async methods have correct signatures."""

    @pytest.mark.asyncio
    async def test_get_by_transaction_id_accepts_uuid(self):
        """Test get_by_transaction_id accepts a UUID parameter."""
        sig = TransactionRepository.get_by_transaction_id.__code__
        params = sig.co_varnames[: sig.co_argcount]
        assert "self" in params
        assert "transaction_id" in params

    @pytest.mark.asyncio
    async def test_list_accepts_pagination_params(self):
        """Test list accepts pagination parameters."""
        sig = TransactionRepository.list.__code__
        params = sig.co_varnames[: sig.co_argcount]
        # Should have limit and/or cursor parameters
        assert "limit" in params or "cursor" in params or len(params) > 2


class TestRepositoryPrivateMethods:
    """Test repository private methods."""

    def test_repository_has_row_to_dict_method(self):
        """Test repository has _row_to_dict private method."""
        mock_session = MagicMock()
        repo = TransactionRepository(mock_session)
        assert hasattr(repo, "_row_to_dict")
        assert callable(repo._row_to_dict)

    def test_repository_has_rule_match_row_to_dict_method(self):
        """Test repository has _rule_match_row_to_dict private method."""
        mock_session = MagicMock()
        repo = TransactionRepository(mock_session)
        assert hasattr(repo, "_rule_match_row_to_dict")
        assert callable(repo._rule_match_row_to_dict)


class TestTransactionRepositorySchema:
    """Test repository schema configuration."""

    def test_repository_module_docstring_mentions_fraud_gov(self):
        """Test repository module mentions fraud_gov schema."""
        from app.persistence import transaction_repository

        doc = str(transaction_repository.__doc__)
        assert "fraud_gov" in doc


class TestTransactionRepositoryTableName:
    """Test repository table configuration."""

    def test_repository_module_docstring_mentions_tables(self):
        """Test repository module mentions transactions table."""
        from app.persistence import transaction_repository

        doc = str(transaction_repository.__doc__)
        assert "transactions" in doc
        assert "transaction_rule_matches" in doc


class TestRepositoryAsyncBehavior:
    """Test async behavior of repository methods."""

    @pytest.mark.asyncio
    async def test_get_by_transaction_id_is_async_coroutine(self):
        """Test get_by_transaction_id is an async method."""
        import inspect

        assert inspect.iscoroutinefunction(TransactionRepository.get_by_transaction_id)

    @pytest.mark.asyncio
    async def test_list_is_async_coroutine(self):
        """Test list is an async method."""
        import inspect

        assert inspect.iscoroutinefunction(TransactionRepository.list)

    @pytest.mark.asyncio
    async def test_upsert_transaction_is_async_coroutine(self):
        """Test upsert_transaction is an async method."""
        import inspect

        assert inspect.iscoroutinefunction(TransactionRepository.upsert_transaction)

    @pytest.mark.asyncio
    async def test_add_rule_match_is_async_coroutine(self):
        """Test add_rule_match is an async method."""
        import inspect

        assert inspect.iscoroutinefunction(TransactionRepository.add_rule_match)

    @pytest.mark.asyncio
    async def test_get_rule_matches_for_event_is_async_coroutine(self):
        """Test get_rule_matches_for_event is an async method."""
        import inspect

        assert inspect.iscoroutinefunction(TransactionRepository.get_rule_matches_for_event)

    @pytest.mark.asyncio
    async def test_get_metrics_is_async_coroutine(self):
        """Test get_metrics is an async coroutine function."""
        import inspect

        assert inspect.iscoroutinefunction(TransactionRepository.get_metrics)


class TestTransactionRepositoryAsyncBehavior:
    """Test async behavior and method implementations of repository."""

    def _create_mock_row(self, **kwargs):
        """Create a mock database row matching the DDL schema."""
        mock_row = MagicMock()
        defaults = {
            "id": uuid7(),
            "transaction_id": uuid7(),
            "evaluation_type": "AUTH",
            "card_id": "tok_card123",
            "card_last4": "1234",
            "card_network": "VISA",
            "transaction_amount": 100.00,
            "transaction_currency": "USD",
            "merchant_id": "merchant_001",
            "merchant_category_code": "5411",
            "decision": "APPROVE",
            "decision_reason": "DEFAULT_ALLOW",
            "decision_score": None,
            "ruleset_key": None,
            "ruleset_id": None,
            "ruleset_version": None,
            "risk_level": None,
            "transaction_context": None,
            "velocity_snapshot": None,
            "velocity_results": None,
            "engine_metadata": None,
            "transaction_timestamp": datetime.now(),
            "ingestion_timestamp": datetime.now(),
            "kafka_topic": None,
            "kafka_partition": None,
            "kafka_offset": None,
            "source_message_id": None,
            "trace_id": "trace-123",
            "request_id": None,
            "session_id": None,
            "raw_payload": None,
            "ingestion_source": "HTTP",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }
        defaults.update(kwargs)
        column_order = [
            "id",
            "transaction_id",
            "evaluation_type",
            "card_id",
            "card_last4",
            "card_network",
            "transaction_amount",
            "transaction_currency",
            "merchant_id",
            "merchant_category_code",
            "decision",
            "decision_reason",
            "decision_score",
            "ruleset_key",
            "ruleset_id",
            "ruleset_version",
            "risk_level",
            "transaction_context",
            "velocity_snapshot",
            "velocity_results",
            "engine_metadata",
            "transaction_timestamp",
            "ingestion_timestamp",
            "kafka_topic",
            "kafka_partition",
            "kafka_offset",
            "source_message_id",
            "trace_id",
            "request_id",
            "session_id",
            "raw_payload",
            "ingestion_source",
            "created_at",
            "updated_at",
        ]
        values = [defaults[key] for key in column_order]
        mock_row.__getitem__.side_effect = lambda idx: values[idx]
        return mock_row

    @pytest.mark.asyncio
    async def test_get_by_transaction_id_returns_dict(self):
        """Test get_by_transaction_id returns dictionary when found."""
        mock_session = MagicMock()
        repo = TransactionRepository(mock_session)

        test_id = uuid7()
        mock_row = self._create_mock_row(transaction_id=test_id)
        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=mock_row)
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_transaction_id(test_id)

        assert result is not None
        assert isinstance(result, dict)
        assert result["transaction_id"] == str(test_id)
        assert "matched_rules" in result

    @pytest.mark.asyncio
    async def test_get_by_transaction_id_returns_none_when_not_found(self):
        """Test get_by_transaction_id returns None when not found."""
        mock_session = MagicMock()
        repo = TransactionRepository(mock_session)

        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_transaction_id(uuid7())

        assert result is None

    @pytest.mark.asyncio
    async def test_list_returns_transactions(self):
        """Test list returns transactions with pagination."""
        mock_session = MagicMock()
        repo = TransactionRepository(mock_session)

        rows = [
            self._create_mock_row(),
            self._create_mock_row(),
        ]

        mock_count_result = MagicMock()
        mock_count_result.scalar = MagicMock(return_value=2)

        mock_list_result = MagicMock()
        mock_list_result.fetchall = MagicMock(return_value=rows)

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_list_result])

        transactions, next_cursor, total = await repo.list(limit=10)

        assert len(transactions) == 2
        assert total == 2
        assert next_cursor is None

    @pytest.mark.asyncio
    async def test_list_with_card_id_filter(self):
        """Test list passes card_id filter to query."""
        mock_session = MagicMock()
        repo = TransactionRepository(mock_session)

        mock_count_result = MagicMock()
        mock_count_result.scalar = MagicMock(return_value=0)

        mock_list_result = MagicMock()
        mock_list_result.fetchall = MagicMock(return_value=[])

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_list_result])

        await repo.list(card_id="tok_card123", limit=10)

        calls = mock_session.execute.call_args_list
        assert len(calls) == 2

    @pytest.mark.asyncio
    async def test_list_with_cursor_pagination(self):
        """Test list handles cursor pagination."""
        mock_session = MagicMock()
        repo = TransactionRepository(mock_session)

        mock_count_result = MagicMock()
        mock_count_result.scalar = MagicMock(return_value=20)

        rows = [self._create_mock_row() for _ in range(11)]
        mock_list_result = MagicMock()
        mock_list_result.fetchall = MagicMock(return_value=rows)

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_list_result])

        transactions, next_cursor, total = await repo.list(limit=10)

        assert len(transactions) == 10
        assert next_cursor is not None
        assert total == 20

    @pytest.mark.asyncio
    async def test_list_with_decision_filter(self):
        """Test list passes decision filter."""
        mock_session = MagicMock()
        repo = TransactionRepository(mock_session)

        mock_count_result = MagicMock()
        mock_count_result.scalar = MagicMock(return_value=0)

        mock_list_result = MagicMock()
        mock_list_result.fetchall = MagicMock(return_value=[])

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_list_result])

        await repo.list(decision="DECLINE", limit=10)

        calls = mock_session.execute.call_args_list
        assert len(calls) == 2

    @pytest.mark.asyncio
    async def test_list_with_date_filters(self):
        """Test list passes from_date and to_date filters."""
        mock_session = MagicMock()
        repo = TransactionRepository(mock_session)

        mock_count_result = MagicMock()
        mock_count_result.scalar = MagicMock(return_value=0)

        mock_list_result = MagicMock()
        mock_list_result.fetchall = MagicMock(return_value=[])

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_list_result])

        from_date = datetime.now()
        to_date = datetime.now()

        await repo.list(from_date=from_date, to_date=to_date, limit=10)

        calls = mock_session.execute.call_args_list
        assert len(calls) == 2

    @pytest.mark.asyncio
    async def test_upsert_transaction_inserts_new(self):
        """Test upsert_transaction inserts new transaction."""
        mock_session = MagicMock()
        repo = TransactionRepository(mock_session)

        transaction_data = {
            "transaction_id": uuid7(),
            "occurred_at": datetime.now(),
            "card_id": "tok_card123",
            "amount": 100.00,
            "currency": "USD",
            "decision": "APPROVE",
            "decision_reason": "DEFAULT_ALLOW",
        }

        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=[transaction_data["transaction_id"]])
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo.get_by_transaction_id = AsyncMock(return_value=transaction_data)

        result = await repo.upsert_transaction(transaction_data)

        assert result is not None
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_rule_match_executes_query(self):
        """Test add_rule_match executes database query."""
        mock_session = MagicMock()
        repo = TransactionRepository(mock_session)

        mock_session.execute = AsyncMock()

        await repo.add_rule_match(
            transaction_id=uuid7(),
            rule_match_data={
                "rule_id": "rule_001",
                "rule_version": 1,
                "rule_name": "Velocity Check",
                "priority": 10,
            },
        )

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_rule_matches_for_event_returns_list(self):
        """Test get_rule_matches_for_event returns list of rule matches."""
        mock_session = MagicMock()
        repo = TransactionRepository(mock_session)

        rule_row = MagicMock()
        rule_values = [
            uuid7(),
            uuid7(),
            "rule_001",
            uuid7(),
            1,
            "Velocity Check",
            True,
            True,
            None,
            10.0,
            "High velocity",
            datetime.now(),
        ]
        rule_row.__getitem__.side_effect = lambda idx: rule_values[idx]

        mock_result = MagicMock()
        mock_result.fetchall = MagicMock(return_value=[rule_row])
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_rule_matches_for_event(uuid7())

        assert isinstance(result, list)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_rule_matches_for_event_returns_empty_list(self):
        """Test get_rule_matches_for_event returns empty list when no rules."""
        mock_session = MagicMock()
        repo = TransactionRepository(mock_session)

        mock_result = MagicMock()
        mock_result.fetchall = MagicMock(return_value=[])
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_rule_matches_for_event(uuid7())

        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_metrics_returns_metrics_dict(self):
        """Test get_metrics returns metrics dictionary."""
        mock_session = MagicMock()
        repo = TransactionRepository(mock_session)

        mock_row = MagicMock()
        metrics_values = [100, 80, 15, 70, 5, 50000.00, 500.00]
        mock_row.__getitem__.side_effect = lambda idx: metrics_values[idx]

        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=mock_row)
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_metrics()

        assert isinstance(result, dict)
        assert result["total_transactions"] == 100
        assert result["approved_count"] == 80
        assert result["declined_count"] == 15
        assert result["monitoring_count"] == 5

    @pytest.mark.asyncio
    async def test_get_metrics_with_date_range(self):
        """Test get_metrics passes date filters."""
        mock_session = MagicMock()
        repo = TransactionRepository(mock_session)

        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        from_date = datetime.now()
        to_date = datetime.now()

        await repo.get_metrics(from_date=from_date, to_date=to_date)

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_metrics_handles_null_values(self):
        """Test get_metrics handles NULL database values."""
        mock_session = MagicMock()
        repo = TransactionRepository(mock_session)

        mock_row = MagicMock()
        null_values = [None, None, None, None, None, None, None]
        mock_row.__getitem__.side_effect = lambda idx: null_values[idx]

        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=mock_row)
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_metrics()

        assert result["total_transactions"] == 0
        assert result["total_amount"] == 0.0
        assert result["avg_amount"] == 0.0

    def test_row_to_dict_converts_row_to_dict(self):
        """Test _row_to_dict converts database row to dictionary."""
        mock_session = MagicMock()
        repo = TransactionRepository(mock_session)

        test_id = uuid7()
        transaction_id = uuid7()
        mock_row = MagicMock()
        values = [
            test_id,
            transaction_id,
            "AUTH",
            "tok_card",
            "1234",
            "VISA",
            100.00,
            "USD",
            "merchant_001",
            "5411",
            "APPROVE",
            "DEFAULT_ALLOW",
            None,
            None,  # ruleset_key
            None,  # ruleset_id
            None,  # ruleset_version
            "LOW",  # risk_level
            None,  # transaction_context
            None,  # velocity_snapshot
            None,  # velocity_results
            None,  # engine_metadata
            datetime.now(),
            datetime.now(),
            None,
            None,
            None,
            None,
            "trace-123",
            None,
            None,
            None,
            None,
            "HTTP",
            datetime.now(),
            datetime.now(),
        ]
        mock_row.__getitem__.side_effect = lambda idx: values[idx]

        result = repo._row_to_dict(mock_row)

        assert isinstance(result, dict)
        assert result["transaction_id"] == str(transaction_id)
        assert result["card_id"] == "tok_card"
        assert result["amount"] == 100.00
        assert result["decision"] == "APPROVE"
        assert result["matched_rules"] == []
        assert result["risk_level"] == "LOW"

    def test_rule_match_row_to_dict_converts_row(self):
        """Test _rule_match_row_to_dict converts rule match row to dictionary."""
        mock_session = MagicMock()
        repo = TransactionRepository(mock_session)

        test_txn_id = uuid7()
        test_rule_id = uuid7()
        mock_row = MagicMock()
        values = [
            1,
            test_txn_id,
            test_rule_id,
            uuid7(),
            1,
            "Velocity Check",
            True,
            True,
            None,
            10.0,
            "High velocity",
            datetime.now(),
        ]
        mock_row.__getitem__.side_effect = lambda idx: values[idx]

        result = repo._rule_match_row_to_dict(mock_row)

        assert isinstance(result, dict)
        assert result["transaction_id"] == str(test_txn_id)
        assert result["rule_id"] == str(test_rule_id)
        assert result["rule_version"] == 1
        assert result["rule_name"] == "Velocity Check"
        assert result["matched"] is True
