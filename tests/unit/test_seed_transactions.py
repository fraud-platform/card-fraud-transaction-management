"""Unit tests for seed transaction determinism."""

from scripts.seed_transactions import _build_transactions, _stable_uuid7


def test_stable_uuid7_is_deterministic_and_valid_v7() -> None:
    """Same input should always produce the same UUIDv7 output."""
    first = _stable_uuid7("seed:example")
    second = _stable_uuid7("seed:example")
    third = _stable_uuid7("seed:different")

    assert first == second
    assert first != third
    assert first.version == 7


def test_build_transactions_reuses_same_identifiers_across_runs() -> None:
    """Seeded transaction IDs should stay stable across repeated runs."""
    first_run = _build_transactions()
    second_run = _build_transactions()

    first_ids = [txn["id"] for txn in first_run]
    second_ids = [txn["id"] for txn in second_run]
    first_transaction_ids = [txn["transaction_id"] for txn in first_run]
    second_transaction_ids = [txn["transaction_id"] for txn in second_run]

    assert first_ids == second_ids
    assert first_transaction_ids == second_transaction_ids
    assert len(set(first_ids)) == len(first_ids)
    assert len(set(first_transaction_ids)) == len(first_transaction_ids)
