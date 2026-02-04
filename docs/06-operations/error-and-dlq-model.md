# Error Model & DLQ Contract (Plan)

This document standardizes **how failures are represented** across HTTP ingestion, Kafka ingestion, and internal logs/metrics.

## Goals
- Make ingest failures diagnosable without exposing sensitive data.
- Ensure DLQ messages are actionable for replay/triage.
- Keep contracts stable for LLM-driven implementation.

## Guiding rules (locked)
- Never log or persist raw PAN (or other sensitive card data).
- Always include `trace_id` and `transaction_id` when available.
- Prefer deterministic, enumerable error codes.

## Error codes (recommended)

### Validation / contract
- `SCHEMA_INVALID` — JSON Schema validation failed.
- `MISSING_REQUIRED_FIELD` — required field missing (if not already covered by schema tooling).
- `ENUM_INVALID` — enum value not allowed.
- `POSTAUTH_DECISION_NOT_NULL` — ruleset_key POSTAUTH but decision not null.
- `PREAUTH_DECISION_NULL` — ruleset_key PREAUTH but decision/decision_reason missing.

### Compliance boundary
- `PAN_DETECTED` — payload appears to contain PAN-like data.

### Persistence
- `DB_TRANSIENT_ERROR` — retryable DB error.
- `DB_CONSTRAINT_VIOLATION` — non-retryable constraint failure.
- `DB_TIMEOUT` — DB timeout.

### Processing
- `UNHANDLED_EXCEPTION` — unexpected code path.

## HTTP ingestion response model (plan)

Endpoint: `POST /v1/decision-events`

Recommended responses:
- `202 Accepted` on success.
- `400 Bad Request` on validation/compliance errors (schema invalid / PAN detected).
- `500 Internal Server Error` for unexpected server errors.

Response body (recommended):
```json
{
  "status": "ACCEPTED",
  "transaction_id": "txn_123",
  "trace_id": "...",
  "result": "CREATED|NOOP|UPDATED",
  "warnings": []
}
```

Error body (recommended):
```json
{
  "status": "REJECTED",
  "error_code": "SCHEMA_INVALID",
  "message": "Decision event failed schema validation",
  "transaction_id": "txn_123",
  "trace_id": "..."
}
```

## Kafka DLQ message contract (plan)

DLQ topic: `fraud.card.decisions.v1.dlq.<env>`

DLQ envelope (recommended):
```json
{
  "dlq_version": "1.0",
  "error_code": "PAN_DETECTED",
  "error_message": "PAN-like value detected in payload",
  "original_topic": "fraud.card.decisions.v1",
  "original_partition": 3,
  "original_offset": 123456,
  "ingested_at": "2026-01-15T10:45:32Z",
  "trace_id": "...",
  "transaction_id": "txn_123",
  "event_version": "1.0",
  "event_type": "FRAUD_DECISION",
  "event": { "...": "redacted or full depending on policy" }
}
```

DLQ payload policy:
- For `PAN_DETECTED`: store **no raw event** (or store a heavily redacted minimal subset) to avoid propagating sensitive data.
- For schema-invalid events: storing the raw event may be acceptable only if it does not violate PCI/PII policies; otherwise store a redacted subset.

## Metrics alignment
- `ingest_rejected_total{error_code=...}`
- `ingest_dlq_total{error_code=...}`
- `ingest_db_retry_total`
- `ingest_processed_total{result=CREATED|NOOP|UPDATED}`

## TODO checklist
- Confirm HTTP status codes and response shape.
- Confirm DLQ topic naming standard.
- Decide DLQ payload policy per error code.
- Confirm schema validation is wired in (PREAUTH requires non-null `decision` and `decision_reason`).
