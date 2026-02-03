"""Integration tests for repository layer.

These tests use real database connections. Run with:
    pytest -m integration -v

Note: Requires local PostgreSQL to be running.
"""

from datetime import datetime
from uuid import UUID, uuid7

import pytest

from app.core.database import create_async_engine, create_session_factory
from app.persistence.transaction_repository import TransactionRepository


@pytest.fixture
async def engine():
    """Create test database engine."""
    from app.core.config import get_settings

    settings = get_settings()
    engine = create_async_engine(settings.database)
    yield engine
    await engine.dispose()


@pytest.fixture
def session_factory(engine):
    """Create test session factory."""
    return create_session_factory(engine)


@pytest.fixture
async def session(session_factory):
    """Create test session."""
    async with session_factory() as s:
        yield s


@pytest.mark.integration
class TestTransactionRepositoryIntegration:
    """Integration tests for TransactionRepository."""

    async def test_create_and_get_transaction(self, session):
        """Test creating and retrieving a transaction."""
        repo = TransactionRepository(session)

        transaction_id = uuid7()
        transaction_data = {
            "transaction_id": transaction_id,
            "occurred_at": datetime.utcnow(),
            "card_id": "tok_visa_integration",
            "card_last4": "4242",
            "card_network": "VISA",
            "amount": 150.00,
            "currency": "USD",
            "merchant_id": "merch_test_001",
            "merchant_category_code": "5411",
            "decision": "DECLINE",
            "decision_reason": "RULE_MATCH",
            "ingestion_source": "HTTP",
        }

        created = await repo.upsert_transaction(transaction_data)
        assert created is not None
        assert created["transaction_id"] == str(transaction_id)

        retrieved = await repo.get_by_transaction_id(transaction_id)
        assert retrieved is not None
        assert retrieved["transaction_id"] == str(transaction_id)
        assert retrieved["card_id"] == "tok_visa_integration"
        assert float(retrieved["amount"]) == 150.00

    async def test_idempotent_upsert(self, session):
        """Test that upsert is idempotent."""
        repo = TransactionRepository(session)

        transaction_id = uuid7()
        transaction_data = {
            "transaction_id": transaction_id,
            "occurred_at": datetime.utcnow(),
            "card_id": "tok_visa_idem",
            "amount": 100.00,
            "currency": "USD",
            "decision": "APPROVE",
            "decision_reason": "DEFAULT_ALLOW",
            "ingestion_source": "HTTP",
        }

        first = await repo.upsert_transaction(transaction_data)

        updated_data = transaction_data.copy()
        updated_data["trace_id"] = "trace_updated"

        second = await repo.upsert_transaction(updated_data)

        assert first["transaction_id"] == second["transaction_id"]

    async def test_list_transactions_with_filters(self, session):
        """Test listing transactions with filters."""
        repo = TransactionRepository(session)

        items, next_cursor, total = await repo.list(
            card_id="tok_visa_list_test",
            decision="DECLINE",
            limit=10,
        )

        assert isinstance(items, list)
        assert isinstance(total, int)

    async def test_add_and_get_rule_matches_for_event(self, session):
        """Test adding and retrieving rule matches."""
        repo = TransactionRepository(session)

        transaction_id = uuid7()
        transaction_data = {
            "transaction_id": transaction_id,
            "occurred_at": datetime.utcnow(),
            "card_id": "tok_visa_rules",
            "amount": 200.00,
            "currency": "USD",
            "decision": "DECLINE",
            "decision_reason": "RULE_MATCH",
            "ingestion_source": "HTTP",
        }

        await repo.upsert_transaction(transaction_data)
        created = await repo.get_by_transaction_id(transaction_id)
        assert created is not None
        transaction_event_id = UUID(created["id"])

        rule_data = {
            "rule_id": str(uuid7()),
            "rule_version": 1,
            "rule_name": "Test Rule",
            "priority": 50,
        }

        await repo.add_rule_match(transaction_event_id, rule_data)

        matches = await repo.get_rule_matches_for_event(transaction_event_id)
        assert len(matches) >= 1

    async def test_get_metrics(self, session):
        """Test getting transaction metrics."""
        repo = TransactionRepository(session)

        metrics = await repo.get_metrics()
        assert "total_transactions" in metrics
        assert "approved_count" in metrics
        assert "declined_count" in metrics
        assert "total_amount" in metrics
        assert "avg_amount" in metrics


@pytest.mark.integration
class TestRuleMatchCompositeKey:
    """Tests for rule match composite key idempotency."""

    async def test_duplicate_rule_match_ignored(self, session):
        """Test that duplicate rule matches are handled."""
        repo = TransactionRepository(session)

        transaction_id = uuid7()
        transaction_data = {
            "transaction_id": transaction_id,
            "occurred_at": datetime.utcnow(),
            "card_id": "tok_visa_dup",
            "amount": 75.00,
            "currency": "USD",
            "decision": "DECLINE",
            "decision_reason": "RULE_MATCH",
            "ingestion_source": "HTTP",
        }

        await repo.upsert_transaction(transaction_data)

        rule_data = {
            "rule_id": str(uuid7()),
            "rule_version": 1,
            "rule_name": "Test Duplicate Rule",
        }

        # First insert
        created = await repo.get_by_transaction_id(transaction_id)
        assert created is not None
        transaction_event_id = UUID(created["id"])

        await repo.add_rule_match(transaction_event_id, rule_data)
        # Flush to ensure the insert is visible to the next call
        await session.flush()

        # Second insert with same data (should be idempotent due to ON CONFLICT)
        await repo.add_rule_match(transaction_event_id, rule_data)
        await session.flush()

        matches = await repo.get_rule_matches_for_event(transaction_event_id)
        # Database constraint ensures exactly one match
        assert len(matches) == 1
