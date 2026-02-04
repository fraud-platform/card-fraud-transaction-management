# Replay / Backfill Runbook

## Goal
Safely reprocess historical decision events (replay) or load missing history (backfill) without introducing duplicates or corrupting business fields.

## Preconditions
- Idempotency policy is implemented (metadata-only updates on duplicate).
- Rule matches enforce UNIQUE (`transaction_id`, `rule_id`, `rule_version`).
- Kafka offsets are committed only after DB commit.

## Replay by time range (Kafka)
1. Determine time window (business requirement).
2. Seek consumer offsets by timestamp (if supported by client) or use stored offsets.
3. Run consumer with bounded concurrency.
4. Monitor:
   - processing latency
   - DB errors
   - DLQ count

## Backfill from archive
- If events are stored in object storage, run a one-off job that publishes to Kafka (preferred) or calls HTTP ingestion (dev only).

## Post-run verification
- Compare counts by day/hour (ingested vs persisted).
- Spot-check several `transaction_id`s across the range.

## Guardrails
- Never modify business fields on duplicates.
- If conflicting duplicates appear, investigate producer/source-of-truth.
