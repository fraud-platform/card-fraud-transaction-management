# ADR-004: AUTH/MONITORING Evaluation Types

**Status:** Accepted

**Date:** 2026-01-27

**Context:**

Fraud detection happens at multiple stages in the transaction lifecycle:

1. **Authorization (AUTH)**: Real-time decision during the authorization request
   - Time-critical (must respond in ~100ms)
   - Determines approve/decline for the transaction
   - Limited data available (transaction + historical velocity)

2. **Monitoring (MONITORING)**: Analytics after authorization completes
   - No time constraint (batch processing)
   - Does not change the transaction decision
   - Full data available (including PREAUTH result)
   - Full data available (including AUTH result)
   - Used for model training, pattern detection, alerting

The original design conflated these by using `decision_type` (APPROVE/DECLINE/POSTAUTH), treating POSTAUTH as if it were a decision outcome.

**Problems with Original Design:**
- `decision_type` mixed "decision outcome" with "evaluation stage"
- POSTAUTH was not a real decision (it's analytics-only)
- Could not distinguish AUTH from MONITORING for the same transaction
- Unclear semantics for combined AUTH + MONITORING views

**Decision:**

Separate concerns:
- `decision_type` = Outcome only: **APPROVE**, **DECLINE**
- `evaluation_type` = Stage only: **AUTH**, **MONITORING**

MONITORING events carry the decision from AUTH (no new decisioning).

**Technical Implementation:**
```sql
-- Evaluation type enum (stage)
CREATE TYPE fraud_gov.evaluation_type AS ENUM ('AUTH', 'MONITORING');

-- Decision type enum (outcome only)
CREATE TYPE fraud_gov.decision_type AS ENUM ('APPROVE', 'DECLINE');

CREATE TABLE fraud_gov.transactions (
    id UUID NOT NULL PRIMARY KEY,
    transaction_id UUID NOT NULL,
    evaluation_type fraud_gov.evaluation_type NOT NULL,  -- NEW: AUTH/MONITORING
    decision fraud_gov.decision_type NOT NULL,           -- APPROVE/DECLINE only
    decision_reason fraud_gov.decision_reason NOT NULL,
    -- ... other columns ...
);
```

**Semantic Rules:**

| Evaluation Type | Decision Source | Time Constraint | Purpose |
|-----------------|-----------------|-----------------|---------|
| `AUTH` | Rule engine output | ~100ms | Real-time fraud decision |
| `MONITORING` | Copied from AUTH or caller | None | Analytics, model training |

**MONITORING Decision Flow:**
```
1. AUTH event: decision=APPROVE (from rule engine)
2. MONITORING event: decision=APPROVE (copied from AUTH or caller-provided)
```

**API Impact:**
```python
# Request schema
class DecisionEventCreate(BaseModel):
    transaction_id: UUID
    evaluation_type: EvaluationType  # REQUIRED: AUTH or MONITORING
    decision: DecisionType           # APPROVE or DECLINE only
    decision_reason: DecisionReason
    # ... other fields ...
```

**Consequences:**

**Positive:**
- Clear separation of "when" (evaluation_type) vs "what" (decision)
- Both AUTH and MONITORING can be stored for same transaction_id
- Combined views enable analysis (e.g., "did MONITORING analytics agree with AUTH?")
- Semantically correct: MONITORING is not a decision, it's an evaluation stage

**Negative:**
- Breaking change from original design
- All event producers must provide `evaluation_type`
- Queries must filter by `evaluation_type` where relevant
- Historical data migration may be needed

**Query Patterns:**
```sql
-- Get AUTH decision for a transaction
SELECT decision FROM fraud_gov.transactions
WHERE transaction_id = :tx_id AND evaluation_type = 'AUTH';

-- Get both evaluations (combined view)
SELECT
    transaction_id,
    MAX(CASE WHEN evaluation_type = 'AUTH' THEN decision END) AS auth_decision,
    MAX(CASE WHEN evaluation_type = 'MONITORING' THEN decision END) AS monitoring_decision
FROM fraud_gov.transactions
WHERE transaction_id = :tx_id
GROUP BY transaction_id;

-- Check for discrepancies (MONITORING analytics flagged after AUTH approved)
SELECT t1.transaction_id
FROM fraud_gov.transactions t1  -- AUTH
JOIN fraud_gov.transactions t2 ON t2.transaction_id = t1.transaction_id
  AND t2.evaluation_type = 'MONITORING'
WHERE t1.evaluation_type = 'AUTH'
  AND t1.decision = 'APPROVE'
  AND t2.risk_level IN ('HIGH', 'CRITICAL');
```

**Alternatives Considered:**

1. **Keep POSTAUTH as decision_type**
   - Rejected: Semantically incorrect (POSTAUTH is not a decision)
   - Confused evaluation stage with decision outcome

2. **Single event per transaction (no MONITORING)**
   - Rejected: Loses analytics value, no post-decision analysis

3. **Separate tables for AUTH and MONITORING**
   - Rejected: Duplicated schema, complex combined queries
   - Hard to maintain consistency

**Migration Impact:**

Existing events with `decision=POSTAUTH` need migration:
- Determine if event was AUTH or MONITORING based on context
- Set appropriate `evaluation_type`
- Set `decision` to actual outcome (APPROVE/DECLINE)

**Related:**
- ADR-002: Composite Idempotency Key (enables AUTH + MONITORING)
- ADR-003: Separate Review Layer
- [docs/../03-api/decision-event-schema-v1.md](../03-api/decision-event-schema-v1.md)
- [TODO.md](../README.md)
