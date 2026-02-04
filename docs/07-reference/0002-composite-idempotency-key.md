# ADR-002: Composite Idempotency Key for Multiple Events Per Transaction

**Status:** Accepted

**Date:** 2026-01-27

**Context:**

The fraud detection system evaluates transactions at different points:
1. **PREAUTH** - Real-time decision during authorization (requires immediate response)
2. **POSTAUTH** - Post-authorization analytics (batch processing, no time constraint)

Both evaluations produce decision events for the same `transaction_id`, but with different purposes. The original design assumed a single event per `transaction_id`, which prevented storing both PREAUTH and POSTAUTH results.

**Requirements:**
- Store both PREAUTH and POSTAUTH events for the same transaction
- Enable idempotent ingestion (duplicate events should not create duplicates)
- Support event replay and backfill for data recovery
- Maintain queryability for analysis (PREAUTH vs POSTAUTH comparison)

**Original Constraint:**
```sql
-- Old unique constraint (prevented multiple events)
CONSTRAINT uk_transaction_id UNIQUE (transaction_id)
```

**Decision:**

Use a composite unique constraint on `(transaction_id, evaluation_type, transaction_timestamp)` to allow multiple events per transaction while maintaining idempotency.

**Technical Implementation:**
```sql
-- New composite unique constraint
CREATE TABLE fraud_gov.transactions (
    id UUID NOT NULL PRIMARY KEY,
    transaction_id UUID NOT NULL,
    evaluation_type fraud_gov.evaluation_type NOT NULL,  -- PREAUTH or POSTAUTH
    transaction_timestamp TIMESTAMPTZ NOT NULL,
    -- ... other columns ...
    CONSTRAINT uk_transaction_idempotency UNIQUE (transaction_id, evaluation_type, transaction_timestamp)
);
```

**Idempotency Behavior:**
```sql
INSERT INTO fraud_gov.transactions (...) VALUES (...)
ON CONFLICT (transaction_id, evaluation_type, transaction_timestamp) DO UPDATE SET
    trace_id = EXCLUDED.trace_id,
    raw_payload = EXCLUDED.raw_payload,
    updated_at = NOW();
```

**Consequences:**

**Positive:**
- Both PREAUTH and POSTAUTH events can be stored for same transaction
- Idempotency maintained per event type
- Safe event replay and backfill
- Enables comparative analysis (real-time vs analytics decision)
- Composite key acts as natural deduplication mechanism

**Negative:**
- Slightly more complex unique constraint
- Queries must consider `evaluation_type` filter
- Index size increases (3 columns vs 1)
- Application must provide all three values on insert

**Query Impact:**
```sql
-- Get all events for a transaction (both PREAUTH and POSTAUTH)
SELECT * FROM fraud_gov.transactions
WHERE transaction_id = :transaction_id
ORDER BY evaluation_type, transaction_timestamp;

-- Get specific evaluation type
SELECT * FROM fraud_gov.transactions
WHERE transaction_id = :transaction_id
  AND evaluation_type = 'PREAUTH';
```

**Alternatives Considered:**

1. **Single event per transaction (original design)**
   - Rejected: Cannot store both PREAUTH and POSTAUTH
   - POSTAUTH analytics would overwrite PREAUTH decision

2. **Separate tables for PREAUTH and POSTAUTH**
   - Rejected: Duplicated schema, complex queries
   - Hard to maintain consistency across tables

3. **Transaction-based versioning**
   - Rejected: Added complexity, unclear semantics
   - Would require sequence numbers or timestamps

**Data Model Impact:**

This decision influenced:
- ADR-004: Evaluation Types (PREAUTH/POSTAUTH enum)
- ADR-003: Separate Review Layer (reviews link to events, not transaction_id)

**Related:**
- ADR-003: Separate Review Layer from Immutable Events
- ADR-004: PREAUTH/POSTAUTH Evaluation Types
- [docs/04-idempotency-and-replay.md](../02-development/idempotency-and-replay.md)
- [docs/../03-api/decision-event-schema-v1.md](../03-api/decision-event-schema-v1.md)
