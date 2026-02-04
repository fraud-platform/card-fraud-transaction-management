# DLQ Triage Runbook

## Goal
Diagnose and resolve ingestion failures routed to the DLQ without exposing sensitive data.

## Inputs
- DLQ message envelope (see `docs/13-error-and-dlq-model.md`)
- Metrics: DLQ rate, error_code breakdown, Kafka lag
- Logs filtered by `trace_id` and/or `transaction_id`

## Procedure
1. Identify spike scope
   - Confirm which `error_code` is increasing.
   - Check if the issue is isolated to a partition, producer, or deployment.

2. Classify by error_code
   - `PAN_DETECTED`: treat as security incident; do not reprocess raw payload. Escalate per policy.
   - `SCHEMA_INVALID` / `ENUM_INVALID`: check producer schema changes; update tolerant parsing rules if applicable.
   - `DB_TRANSIENT_ERROR` / `DB_TIMEOUT`: validate DB health; consider circuit breaker tuning.

3. Decide action
   - Fix config/infra (DB, Kafka) and replay.
   - Fix producer contract mismatch and replay.
   - If event is truly poison, keep in DLQ with ticket reference.

4. Replay strategy
   - Prefer replay from the original Kafka topic by offset/time if possible.
   - If replaying DLQ messages, ensure idempotency guarantees are in place.

## Guardrails
- Never copy raw payload into tickets/slack.
- Avoid persisting DLQ bodies for `PAN_DETECTED` errors.
