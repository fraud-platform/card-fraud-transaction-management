# Ingestion Architecture

This document covers both HTTP and Kafka ingestion paths for decision events.

## Overview

| Aspect | HTTP (Dev/Testing) | Kafka (Production) |
|--------|-------------------|-------------------|
| **Endpoint** | `POST /v1/decision-events` | Topic: `fraud.card.decisions.v1` |
| **Pattern** | Synchronous request/response | Async event streaming |
| **Idempotency** | Via `transaction_id` | Via `transaction_id` |
| **Delivery** | At-least-once (client retry) | At-least-once (Kafka) |
| **Ordering** | Per request | Per partition |
| **Error handling** | HTTP status codes | DLQ routing |

---

## 1. Common Ingestion Behavior

### 1.1 Idempotency Keys

- **Primary key**: `transaction_id` (must be unique per decision event)
- **Rule match composite key**: `(transaction_id, rule_id, rule_version)`

### 1.2 Write Semantics

**Transactions:**
- Upsert by `transaction_id`
- On duplicate: update metadata only (`raw_payload`, `trace_id`, `ingestion_source`, `updated_at`)
- Never modify business fields (`occurred_at`, `amount`, `currency`, `country`, `merchant_id`, `card_id`, `decision`, `decision_reason`)

**Rule Matches:**
- UNIQUE CONSTRAINT on `(transaction_id, rule_id, rule_version)`
- Use upsert or insert-ignore semantics

### 1.3 PCI Compliance — PAN Detection

Locked rule: **raw PAN must never transit this service boundary.**

Detection approach:
- Enforce token pattern for `transaction.card_id` (e.g., starts with `tok_`)
- On suspected PAN detection:
  - HTTP: return 400/422, do not persist
  - Kafka: route to DLQ with reason `PAN_DETECTED`
  - Log only minimal metadata (`trace_id`, `transaction_id`)

### 1.4 Card Identifier Mode

| Mode | Behavior |
|------|----------|
| `TOKEN_ONLY` (default) | Never persist `card_last4` even if present |
| `TOKEN_PLUS_LAST4` | Require and persist `card_last4` |

### 1.5 Payload Limits

| Limit | Value |
|-------|-------|
| Max request body | 1MB |
| Max `matched_rules` array | 100 items |
| Max persisted `raw_payload` | 64KB (after allowlist + redaction) |

### 1.6 Correlation Headers

Accept `X-Correlation-ID` or `X-Request-ID` header. If `trace_id` is missing/empty, use the header value as fallback.

---

## 2. HTTP Ingestion (Development/Testing)

### 2.1 Endpoint

```
POST /v1/decision-events
```

### 2.2 Request

```json
{
  "event_version": "1.0",
  "transaction_id": "txn_12345",
  "occurred_at": "2026-01-15T10:30:00Z",
  "produced_at": "2026-01-15T10:30:01Z",
  "transaction": {
    "card_id": "tok_visa_abc123",
    "card_last4": "4242",
    "card_network": "VISA",
    "amount": 99.99,
    "currency": "USD",
    "country": "US",
    "merchant_id": "merch_123",
    "mcc": "5411",
    "ip": "192.168.1.1"
  },
  "decision": "DECLINE",
  "decision_reason": "RULE_MATCH",
  "matched_rules": [
    {
      "rule_id": "rule_001",
      "rule_version": 1,
      "priority": 100,
      "matched_at": "2026-01-15T10:30:00.500Z"
    }
  ],
  "raw_payload": {
    "transaction_id": "txn_12345",
    "amount": 99.99,
    "currency": "USD"
  }
}
```

### 2.3 Response

| Status | Meaning |
|--------|---------|
| `202 Accepted` | Event accepted for processing |
| `400 Bad Request` | Validation failure |
| `409 Conflict` | Conflicting business fields (optional) |
| `500 Internal Server Error` | Persistence failure |

### 2.4 Security

For non-local use, protect with:
- mTLS, or
- OAuth2/JWT, or
- Internal network + API gateway

### 2.5 Deprecation

HTTP ingestion is labeled as temporary. Kafka is the preferred production path. Add configuration flag to disable in prod:

```yaml
ENABLE_HTTP_INGESTION: false  # default in prod
```

---

## 3. Kafka Ingestion (Production)

### 3.1 Topic & Consumer Group

- **Topic**: `fraud.card.decisions.v1`
- **Consumer Group**: `card-fraud-transaction-management.<env>`

### 3.2 Message Format

- JSON with schema versioning via `event_version`
- **Key**: `transaction_id` (improves ordering per transaction)

### 3.3 Consumer Behavior

1. Poll batch of records
2. For each record:
   - Parse + validate against JSON Schema v1
   - Apply config-driven validation/normalization
   - Write to DB within transaction
   - Persist `ingestion_source=KAFKA` as metadata
   - On success: mark record processed
3. Commit offsets only after successful DB transaction

### 3.4 Ordering Expectations

- Guarantee ordering only per partition
- With keying by `transaction_id`, duplicates/retries land in same partition

### 3.5 Retry & DLQ

| Error Type | Handling |
|------------|----------|
| Transient DB errors | Retry with bounded backoff |
| Validation errors / poison messages | Send to DLQ with reason + trace_id |

**DLQ Topic**: `fraud.card.decisions.v1.dlq.<env>`

### 3.6 Circuit Breaker / Bulkhead

Required: If DB health is failing, open circuit breaker and:
- Stop attempting writes for a short window
- Pause partition consumption
- Avoid tight retry loops
- On recovery: resume with bounded concurrency (prevent thundering herd)

### 3.7 Concurrency Model (Locked)

- Process messages sequentially **per partition**
- Use **bounded parallelism** across partitions (configurable)
- Commit offsets only after DB transaction commits

### 3.8 Backpressure

- If DB is slow: reduce concurrency, increase batch size carefully
- Consider pause/resume partition consumption on sustained failures

### 3.9 Observability Metrics

| Metric | Description |
|--------|-------------|
| `records consumed/sec` | Ingestion throughput |
| `processing latency` | End-to-end latency |
| `commit lag` | Consumer lag |
| `DLQ count` | Poison messages |
| `DB error rate` | Persistence failures |

---

## 4. Raw Payload Handling

### 4.1 Redaction Policy

- Fields must be allowlist-only
- Recommended default allowlist: `transaction_id`, `amount`, `currency`, `country`, `merchant_id`, `mcc`, `decision_reason`

### 4.2 Configuration

```yaml
RAW_PAYLOAD_ALLOWLIST: "transaction_id,amount,currency,country,merchant_id,mcc,decision_reason"
ENABLE_RAW_PAYLOAD: false  # default in prod unless explicitly approved
```

---

## 5. Validation Checklist

- [ ] `TOKEN_ONLY`: ensure `card_last4` is never persisted
- [ ] `TOKEN_PLUS_LAST4`: ensure missing/invalid `card_last4` is rejected or DLQ'd
- [ ] `transaction_id` uniqueness enforced
- [ ] Rule match composite key constraint exists
- [ ] PAN detection enabled and tested
- [ ] DLQ routing verified

---

## 6. TODO Items

- [ ] Confirm Kafka provider and client library
- [ ] Confirm message schema (JSON vs Avro/Protobuf + registry)
- [ ] Decide DLQ payload (full message vs redacted + pointer)
- [ ] Tune concurrency and backpressure defaults
- [ ] Define request timeouts for HTTP
- [ ] Add OpenAPI spec for HTTP endpoint
