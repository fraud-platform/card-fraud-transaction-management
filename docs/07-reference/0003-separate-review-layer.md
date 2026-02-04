# ADR-003: Separate Review Layer from Immutable Events

**Status:** Accepted

**Date:** 2026-01-27

**Context:**

Fraud decision events are immutable records of what happened at decision time. However, analysts need to:
1. Review transactions (assign status, add notes, resolve)
2. Group related transactions into cases
3. Track workflow state (pending → in-review → resolved)

If we stored review state directly on the `transactions` table:
- Row updates would violate immutability principle
- Event replay would overwrite review state
- Cannot distinguish between "original event" and "current state"
- Audit trail would be lost

**Requirements:**
- Preserve immutable decision events
- Support mutable analyst workflow (assignments, status changes)
- Enable audit trail of all review activities
- Allow multiple analysts to work on same transaction over time
- Link transactions to cases for investigation

**Decision:**

Create a separate mutable review layer that references immutable transaction events by their primary key (`transactions.id`), not by business key (`transaction_id`).

**Technical Implementation:**
```sql
-- Immutable event (append-only)
CREATE TABLE fraud_gov.transactions (
    id UUID NOT NULL PRIMARY KEY,  -- Surrogate key
    transaction_id UUID NOT NULL,    -- Business key
    evaluation_type fraud_gov.evaluation_type NOT NULL,
    decision fraud_gov.decision_type NOT NULL,
    -- ... event data never changes ...
    CONSTRAINT uk_transaction_idempotency UNIQUE (transaction_id, evaluation_type, transaction_timestamp)
);

-- Mutable review state (separate table)
CREATE TABLE fraud_gov.transaction_reviews (
    id UUID NOT NULL PRIMARY KEY,
    transaction_id UUID NOT NULL REFERENCES fraud_gov.transactions(id) ON DELETE CASCADE,
    status fraud_gov.transaction_status NOT NULL DEFAULT 'PENDING',
    assigned_analyst_id VARCHAR(128),
    priority INTEGER NOT NULL DEFAULT 3,
    case_id UUID,
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT,
    -- ... mutable state changes here ...
    CONSTRAINT uk_transaction_review UNIQUE (transaction_id)  -- One review per event
);

-- Audit trail (immutable log)
CREATE TABLE fraud_gov.case_activity_log (
    id SERIAL PRIMARY KEY,
    case_id UUID NOT NULL,
    activity_type VARCHAR(64) NOT NULL,
    old_values JSONB,
    new_values JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Key Design Point:**
- Reviews reference `transactions.id` (PK), not `transactions.transaction_id` (business key)
- This allows PREAUTH and POSTAUTH events to have separate reviews
- Each event is independently reviewable

**Consequences:**

**Positive:**
- Clean separation of concerns: events = facts, reviews = workflow
- Event replay never affects review state
- Full audit trail via activity log
- Can re-evaluate old events without losing review work
- Supports temporal queries (what was the state at time T?)

**Negative:**
- More complex queries (JOINs required)
- Additional tables to maintain
- Need to ensure referential integrity (reviews → events)
- Slightly higher storage overhead

**Query Patterns:**
```sql
-- Get event with review state
SELECT t.*, r.status, r.assigned_analyst_id
FROM fraud_gov.transactions t
LEFT JOIN fraud_gov.transaction_reviews r ON r.transaction_id = t.id
WHERE t.transaction_id = :transaction_id
  AND t.evaluation_type = 'PREAUTH';

-- Get events for a case
SELECT t.*
FROM fraud_gov.transaction_cases c
JOIN fraud_gov.transaction_reviews r ON r.case_id = c.id
JOIN fraud_gov.transactions t ON t.id = r.transaction_id
WHERE c.id = :case_id;
```

**Alternatives Considered:**

1. **Store review state on transactions table**
   - Rejected: Violates immutability, replay overwrites reviews

2. **Separate review database**
   - Rejected: Over-engineering, adds operational complexity
   - JOINs across databases would be required

3. **JSONB review state on transactions**
   - Rejected: No audit trail, harder to query, no referential integrity

4. **Use transaction_id (not id) for reviews**
   - Rejected: PREAUTH/POSTAUTH couldn't have separate reviews
   - Would violate ADR-002 design

**Data Flow:**
```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   Kafka Event   │ ───> │   transactions  │ <──── │  Event Replay   │
│                 │      │   (immutable)   │      │                 │
└─────────────────┘      └────────┬────────┘
                                   │
                                   │ references (id)
                                   ▼
                          ┌─────────────────┐
                          │ transaction_    │
                          │     reviews     │
                          │   (mutable)     │
                          └─────────────────�
```

**Related:**
- ADR-002: Composite Idempotency Key
- ADR-004: PREAUTH/POSTAUTH Evaluation Types
- [db/fraud_transactions_schema.sql](../../db/fraud_transactions_schema.sql)
- [docs/07-reference/fraud-analyst-workflow.md](../07-reference/fraud-analyst-workflow.md)
