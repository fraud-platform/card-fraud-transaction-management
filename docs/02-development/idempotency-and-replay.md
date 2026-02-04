# Idempotency, Replay & Backfill Plan

## Idempotency goals
- Duplicate events must not create duplicate `transactions` rows.
- Rule matches must be inserted idempotently.
- Service must tolerate **at-least-once delivery**.

## Idempotency keys
- Transaction: `transaction_id` (primary idempotency key).
- Rule match: recommend unique key `(transaction_id, rule_id, rule_version)`.

## Write semantics
### Transactions
- Use upsert by PK.
- Update policy (locked):
  - On duplicate, update **metadata only** (e.g., `raw_payload`, `trace_id`, `ingestion_source`, `updated_at`).
  - Never modify business fields (`occurred_at`, `amount`, `currency`, `country`, `merchant_id`, `card_id`, `decision`, `decision_reason`, `ruleset_*`).
  - If a duplicate arrives with conflicting business fields, keep the original row unchanged and emit a warning log/metric for investigation.

### Rule matches
Preferred approach:
- Create UNIQUE CONSTRAINT on `(transaction_id, rule_id, rule_version)`.
- Use upsert or insert-ignore semantics.

## Replay/backfill behavior
- Replay is re-consuming historical decision events and applying normal idempotent writes.
- No rule logic executed during replay.

## Kafka offset & exactly-once notes
- Kafka side remains at-least-once.
- Commit offsets only after successful DB transaction commit.
- For higher guarantees, consider transactional outbox (explicitly out of scope due to “two tables only”).

## Operational runbooks
- Replay a time range (requires consumer to support seeking by timestamp/offset).
- Backfill from object store or event archive (if available).
- Handling schema changes: dual-read or tolerant parsing.

## TODO checklist
- Validate transaction upsert update policy in tests.
- Ensure unique constraint for rule matches exists in migrations.
- Define replay tooling approach (CLI job vs admin endpoint).
- Define DLQ policy for poison events (include trace_id).
