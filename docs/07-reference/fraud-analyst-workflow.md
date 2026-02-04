# Fraud Analyst Workflow - Comprehensive Implementation Plan

**Created:** 2026-01-24
**Status:** APPROVED - Ready for Implementation
**Scope:** 3 Projects (transaction-management, rule-engine, UI portal)

---

## Executive Summary

This plan extends the Card Fraud Platform to support complete fraud analyst workflow including:
- Transaction review and resolution workflow
- Analyst notes and case management
- Velocity persistence for audit/replay
- AI agent query support
- Archive to S3/Parquet for long-term analytics

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         CARD FRAUD PLATFORM - TARGET STATE                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────────────────────┐ │
│  │    Rule      │     │    Rule      │     │      Transaction Management      │ │
│  │  Management  │────▶│   Engine     │────▶│                                  │ │
│  │   (CRUD)     │     │  (Evaluate)  │     │  ┌────────────────────────────┐  │ │
│  └──────────────┘     └──────────────┘     │  │ PostgreSQL (Hot - 90 days) │  │ │
│                              │              │  │ • transactions             │  │ │
│                              │ Kafka        │  │ • transaction_rule_matches │  │ │
│                              │              │  │ • transaction_reviews      │  │ │
│                              ▼              │  │ • analyst_notes            │  │ │
│                       ┌──────────────┐     │  │ • transaction_cases        │  │ │
│                       │   Decision   │     │  └────────────────────────────┘  │ │
│                       │    Event     │────▶│                                  │ │
│                       └──────────────┘     │  ┌────────────────────────────┐  │ │
│                                            │  │   S3/Parquet (Archive)     │  │ │
│  ┌──────────────────────────────────────┐  │  │   DuckDB queryable         │  │ │
│  │      Intelligence Portal (UI)        │  │  │   7+ years retention       │  │ │
│  │  • Transaction List/Detail           │  │  └────────────────────────────┘  │ │
│  │  • Analyst Worklist                  │  │                                  │ │
│  │  • Case Management                   │  └──────────────────────────────────┘ │
│  │  • Notes & Actions                   │                                       │
│  │  • Metrics Dashboard                 │                                       │
│  │  • AI Agent Interface (future)       │                                       │
│  └──────────────────────────────────────┘                                       │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Project 1: card-fraud-transaction-management

### Phase 1: Database Schema Changes

#### 1.1 New ENUMs

```sql
-- File: db/fraud_transactions_schema.sql (update)

-- Transaction workflow status
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace
                 WHERE t.typname='transaction_status' AND n.nspname='fraud_gov') THEN
    CREATE TYPE fraud_gov.transaction_status AS ENUM (
        'PENDING',      -- Awaiting review
        'IN_REVIEW',    -- Analyst is reviewing
        'ESCALATED',    -- Escalated to supervisor
        'RESOLVED',     -- Decision made
        'CLOSED'        -- Case closed, no further action
    );
  END IF;
END $$;

-- Risk level classification
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace
                 WHERE t.typname='risk_level' AND n.nspname='fraud_gov') THEN
    CREATE TYPE fraud_gov.risk_level AS ENUM (
        'LOW',
        'MEDIUM',
        'HIGH',
        'CRITICAL'
    );
  END IF;
END $$;

-- Note type categories
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace
                 WHERE t.typname='note_type' AND n.nspname='fraud_gov') THEN
    CREATE TYPE fraud_gov.note_type AS ENUM (
        'GENERAL',
        'INITIAL_REVIEW',
        'CUSTOMER_CONTACT',
        'MERCHANT_CONTACT',
        'BANK_CONTACT',
        'FRAUD_CONFIRMED',
        'FALSE_POSITIVE',
        'ESCALATION',
        'RESOLUTION',
        'LEGAL_HOLD',
        'INTERNAL_REVIEW'
    );
  END IF;
END $$;

-- Case type
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace
                 WHERE t.typname='case_type' AND n.nspname='fraud_gov') THEN
    CREATE TYPE fraud_gov.case_type AS ENUM (
        'INVESTIGATION',
        'DISPUTE',
        'CHARGEBACK',
        'PATTERN_ANALYSIS',
        'MERCHANT_REVIEW',
        'CARD_COMPROMISE'
    );
  END IF;
END $$;

-- Case status
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace
                 WHERE t.typname='case_status' AND n.nspname='fraud_gov') THEN
    CREATE TYPE fraud_gov.case_status AS ENUM (
        'OPEN',
        'IN_PROGRESS',
        'PENDING_INFO',
        'RESOLVED',
        'CLOSED'
    );
  END IF;
END $$;
```

#### 1.2 Update `transactions` Table

```sql
-- Add JSONB columns for extensibility
ALTER TABLE fraud_gov.transactions
    ADD COLUMN IF NOT EXISTS transaction_context JSONB,
    ADD COLUMN IF NOT EXISTS velocity_snapshot JSONB,
    ADD COLUMN IF NOT EXISTS engine_metadata JSONB;

-- Add GIN indexes for JSONB queries
CREATE INDEX IF NOT EXISTS idx_transactions_context_gin
    ON fraud_gov.transactions USING GIN (transaction_context jsonb_path_ops);
CREATE INDEX IF NOT EXISTS idx_transactions_velocity_gin
    ON fraud_gov.transactions USING GIN (velocity_snapshot jsonb_path_ops);

COMMENT ON COLUMN fraud_gov.transactions.transaction_context IS
    'Full transaction payload from rule engine (extensible, audit-complete)';
COMMENT ON COLUMN fraud_gov.transactions.velocity_snapshot IS
    'All velocity counter states at decision time (for audit/replay)';
COMMENT ON COLUMN fraud_gov.transactions.engine_metadata IS
    'Rule engine metadata: mode, processing_time, errors';
```

#### 1.3 Update `transaction_rule_matches` Table

```sql
-- Add columns for audit trail (WHY rule matched)
ALTER TABLE fraud_gov.transaction_rule_matches
    ADD COLUMN IF NOT EXISTS rule_action VARCHAR(16),
    ADD COLUMN IF NOT EXISTS conditions_met JSONB,
    ADD COLUMN IF NOT EXISTS condition_values JSONB;

COMMENT ON COLUMN fraud_gov.transaction_rule_matches.rule_action IS
    'Action this rule wanted: APPROVE, DECLINE, REVIEW';
COMMENT ON COLUMN fraud_gov.transaction_rule_matches.conditions_met IS
    'Array of condition descriptions that matched: ["amount > 5000", "velocity exceeded"]';
COMMENT ON COLUMN fraud_gov.transaction_rule_matches.condition_values IS
    'Actual field values at evaluation: { "amount": 5200, "velocity_card_5min": { "count": 4 } }';
```

#### 1.4 New Table: `transaction_reviews`

```sql
CREATE TABLE IF NOT EXISTS fraud_gov.transaction_reviews (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Link to transaction (1:1)
    transaction_id UUID NOT NULL UNIQUE
        REFERENCES fraud_gov.transactions(transaction_id) ON DELETE CASCADE,

    -- Workflow state
    status fraud_gov.transaction_status NOT NULL DEFAULT 'PENDING',
    risk_level fraud_gov.risk_level,
    priority INTEGER DEFAULT 0,

    -- Assignment
    assigned_analyst_id VARCHAR(64),
    assigned_analyst_name VARCHAR(128),
    assigned_at TIMESTAMPTZ,

    -- Review tracking
    first_reviewed_at TIMESTAMPTZ,
    last_reviewed_at TIMESTAMPTZ,
    review_count INTEGER DEFAULT 0,

    -- Resolution
    resolved_at TIMESTAMPTZ,
    resolved_by VARCHAR(64),
    resolved_by_name VARCHAR(128),
    resolution_code VARCHAR(32),
    resolution_notes TEXT,

    -- Analyst override (if analyst disagrees with engine decision)
    analyst_decision VARCHAR(16),
    analyst_decision_reason TEXT,

    -- Case linkage (optional)
    case_id UUID,

    -- Extensible metadata
    review_metadata JSONB,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_reviews_status
    ON fraud_gov.transaction_reviews(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reviews_analyst
    ON fraud_gov.transaction_reviews(assigned_analyst_id, status);
CREATE INDEX IF NOT EXISTS idx_reviews_priority
    ON fraud_gov.transaction_reviews(priority DESC, created_at ASC)
    WHERE status IN ('PENDING', 'IN_REVIEW');
CREATE INDEX IF NOT EXISTS idx_reviews_case
    ON fraud_gov.transaction_reviews(case_id) WHERE case_id IS NOT NULL;

-- Trigger for updated_at
CREATE TRIGGER trg_reviews_updated_at
    BEFORE UPDATE ON fraud_gov.transaction_reviews
    FOR EACH ROW EXECUTE FUNCTION fraud_gov.update_updated_at();

COMMENT ON TABLE fraud_gov.transaction_reviews IS
    'Analyst workflow state for transactions - separate from immutable transaction data';
```

#### 1.5 New Table: `analyst_notes`

```sql
CREATE TABLE IF NOT EXISTS fraud_gov.analyst_notes (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Link to transaction
    transaction_id UUID NOT NULL
        REFERENCES fraud_gov.transactions(transaction_id) ON DELETE CASCADE,

    -- Note content
    note_type fraud_gov.note_type NOT NULL DEFAULT 'GENERAL',
    note_content TEXT NOT NULL,

    -- Visibility
    is_private BOOLEAN DEFAULT FALSE,
    is_system_generated BOOLEAN DEFAULT FALSE,

    -- Author
    analyst_id VARCHAR(64) NOT NULL,
    analyst_name VARCHAR(128),
    analyst_email VARCHAR(256),

    -- Attachments (stored in S3)
    attachments JSONB,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_notes_transaction
    ON fraud_gov.analyst_notes(transaction_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notes_analyst
    ON fraud_gov.analyst_notes(analyst_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notes_type
    ON fraud_gov.analyst_notes(note_type);

-- Trigger for updated_at
CREATE TRIGGER trg_notes_updated_at
    BEFORE UPDATE ON fraud_gov.analyst_notes
    FOR EACH ROW EXECUTE FUNCTION fraud_gov.update_updated_at();

COMMENT ON TABLE fraud_gov.analyst_notes IS
    'Analyst notes and comments on transactions';
```

#### 1.6 New Table: `transaction_cases`

```sql
CREATE TABLE IF NOT EXISTS fraud_gov.transaction_cases (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Human-readable case number
    case_number VARCHAR(32) UNIQUE NOT NULL,

    -- Case details
    case_type fraud_gov.case_type NOT NULL,
    case_status fraud_gov.case_status NOT NULL DEFAULT 'OPEN',
    case_priority fraud_gov.risk_level DEFAULT 'MEDIUM',

    -- Description
    title VARCHAR(256) NOT NULL,
    description TEXT,

    -- Aggregates (denormalized for dashboard performance)
    transaction_count INTEGER DEFAULT 0,
    total_amount DECIMAL(19,4) DEFAULT 0,

    -- Assignment
    assigned_to VARCHAR(64),
    assigned_to_name VARCHAR(128),
    assigned_at TIMESTAMPTZ,

    -- Resolution
    resolved_at TIMESTAMPTZ,
    resolved_by VARCHAR(64),
    resolved_by_name VARCHAR(128),
    resolution_summary TEXT,

    -- Linking criteria (for auto-linking)
    link_criteria JSONB,

    -- Extensible metadata
    case_metadata JSONB,

    -- Audit
    created_by VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Add foreign key from reviews to cases
ALTER TABLE fraud_gov.transaction_reviews
    ADD CONSTRAINT fk_review_case
    FOREIGN KEY (case_id) REFERENCES fraud_gov.transaction_cases(id) ON DELETE SET NULL;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_cases_status
    ON fraud_gov.transaction_cases(case_status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cases_type
    ON fraud_gov.transaction_cases(case_type);
CREATE INDEX IF NOT EXISTS idx_cases_assigned
    ON fraud_gov.transaction_cases(assigned_to, case_status);
CREATE INDEX IF NOT EXISTS idx_cases_number
    ON fraud_gov.transaction_cases(case_number);

-- Sequence for case numbers
CREATE SEQUENCE IF NOT EXISTS fraud_gov.case_number_seq START 1;

-- Trigger for updated_at
CREATE TRIGGER trg_cases_updated_at
    BEFORE UPDATE ON fraud_gov.transaction_cases
    FOR EACH ROW EXECUTE FUNCTION fraud_gov.update_updated_at();

COMMENT ON TABLE fraud_gov.transaction_cases IS
    'Cases grouping related transactions for investigation';
```

#### 1.7 New Table: `case_activity_log`

```sql
CREATE TABLE IF NOT EXISTS fraud_gov.case_activity_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES fraud_gov.transaction_cases(id) ON DELETE CASCADE,

    -- Activity details
    activity_type VARCHAR(32) NOT NULL,
    activity_description TEXT NOT NULL,

    -- Actor
    performed_by VARCHAR(64) NOT NULL,
    performed_by_name VARCHAR(128),

    -- Change tracking
    old_value JSONB,
    new_value JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_case_activity_case
    ON fraud_gov.case_activity_log(case_id, created_at DESC);

COMMENT ON TABLE fraud_gov.case_activity_log IS
    'Audit log for all case activities';
```

---

### Phase 2: API Endpoints

#### 2.1 Transaction Review Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/transactions/{id}/review` | Get review status |
| POST | `/v1/transactions/{id}/review` | Create review record (auto on first access) |
| PATCH | `/v1/transactions/{id}/review/status` | Update status (PENDING→IN_REVIEW→etc) |
| PATCH | `/v1/transactions/{id}/review/assign` | Assign to analyst |
| POST | `/v1/transactions/{id}/review/resolve` | Resolve transaction |
| POST | `/v1/transactions/{id}/review/escalate` | Escalate to supervisor |

#### 2.2 Analyst Notes Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/transactions/{id}/notes` | List notes for transaction |
| POST | `/v1/transactions/{id}/notes` | Add note |
| GET | `/v1/transactions/{id}/notes/{note_id}` | Get single note |
| PATCH | `/v1/transactions/{id}/notes/{note_id}` | Update note (author only) |
| DELETE | `/v1/transactions/{id}/notes/{note_id}` | Delete note (author only) |

#### 2.3 Worklist Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/worklist` | Get analyst's assigned transactions |
| GET | `/v1/worklist/stats` | Get worklist statistics |
| GET | `/v1/worklist/unassigned` | Get unassigned pending transactions |
| POST | `/v1/worklist/claim` | Claim next unassigned transaction |

#### 2.4 Case Management Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/cases` | List cases (with filters) |
| POST | `/v1/cases` | Create new case |
| GET | `/v1/cases/{id}` | Get case details |
| PATCH | `/v1/cases/{id}` | Update case |
| GET | `/v1/cases/{id}/transactions` | List transactions in case |
| POST | `/v1/cases/{id}/transactions` | Add transaction to case |
| DELETE | `/v1/cases/{id}/transactions/{txn_id}` | Remove transaction from case |
| GET | `/v1/cases/{id}/activity` | Get case activity log |
| POST | `/v1/cases/{id}/resolve` | Resolve case |

#### 2.5 Bulk Operations Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/bulk/assign` | Bulk assign transactions |
| POST | `/v1/bulk/status` | Bulk status update |
| POST | `/v1/bulk/create-case` | Create case from selected transactions |

#### 2.6 Enhanced Query Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/transactions` | Enhanced with review status filters |
| GET | `/v1/metrics/workflow` | Workflow metrics (by status, analyst) |
| GET | `/v1/metrics/cases` | Case metrics |

#### 2.7 AI Agent Query Endpoints (Future)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/agent/query` | Natural language query |
| GET | `/v1/agent/transaction/{id}/explain` | Explain why transaction was flagged |

---

### Phase 3: Service Layer

#### 3.1 New Services

```
app/services/
├── review_service.py          # Transaction review workflow
├── notes_service.py           # Analyst notes CRUD
├── case_service.py            # Case management
├── worklist_service.py        # Analyst worklist/queue
├── bulk_operations_service.py # Bulk actions
└── archive_service.py         # S3 archive operations
```

#### 3.2 New Repositories

```
app/persistence/
├── review_repository.py
├── notes_repository.py
├── case_repository.py
└── archive_repository.py
```

#### 3.3 New Schemas

```
app/schemas/
├── review.py           # ReviewCreate, ReviewUpdate, ReviewResponse
├── notes.py            # NoteCreate, NoteUpdate, NoteResponse
├── case.py             # CaseCreate, CaseUpdate, CaseResponse
├── worklist.py         # WorklistItem, WorklistStats
└── bulk.py             # BulkAssignRequest, BulkStatusRequest
```

---

### Phase 4: Kafka Consumer Updates

Update `app/ingestion/kafka_consumer.py` to:

1. Store full `transaction_context` JSONB
2. Store `velocity_snapshot` JSONB
3. Store `engine_metadata` JSONB
4. Store `conditions_met` and `condition_values` per rule match
5. Auto-create `transaction_reviews` record with initial status

---

### Phase 5: Archive to S3

#### 5.1 Archive Job

```python
# scripts/archive_transactions.py

async def archive_resolved_transactions(days_old: int = 90):
    """Archive resolved transactions older than N days to S3/Parquet."""

    # 1. Query transactions with reviews, notes, rule_matches
    # 2. Transform to denormalized Parquet structure
    # 3. Write to S3 with partitioning
    # 4. Verify archive integrity
    # 5. Delete from PostgreSQL
```

#### 5.2 Parquet Schema

```
transactions_archive/
├── year=2026/
│   └── month=01/
│       └── day=15/
│           └── transactions_20260115.parquet
│
│   Schema:
│   ├── transaction_id, transaction_timestamp, ...
│   ├── transaction_context: JSON (full payload)
│   ├── velocity_snapshot: JSON
│   ├── matched_rules: ARRAY<STRUCT>
│   ├── review: STRUCT<status, analyst, resolution, ...>
│   ├── notes: ARRAY<STRUCT>
│   └── case_info: STRUCT<case_id, case_number, ...>
```

#### 5.3 DuckDB Query API

```python
# app/services/archive_query_service.py

class ArchiveQueryService:
    async def query_archive(
        self,
        sql: str,
        date_range: tuple[date, date]
    ) -> list[dict]:
        """Query archived data using DuckDB."""
        import duckdb

        conn = duckdb.connect()
        conn.execute(f"""
            CREATE SECRET (
                TYPE S3,
                KEY_ID '{settings.s3.access_key}',
                SECRET '{settings.s3.secret_key}',
                ENDPOINT '{settings.s3.endpoint}'
            )
        """)

        return conn.execute(sql).fetchall()
```

---

### Phase 6: Alerts (Future - Last Priority)

#### 6.1 Alert Table

```sql
CREATE TABLE IF NOT EXISTS fraud_gov.alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    alert_type VARCHAR(64) NOT NULL,
    alert_severity fraud_gov.risk_level NOT NULL,

    -- Target (optional - can be transaction, card, merchant, or pattern)
    transaction_id UUID REFERENCES fraud_gov.transactions(transaction_id),
    card_id VARCHAR(64),
    merchant_id VARCHAR(64),

    -- Content
    title VARCHAR(256) NOT NULL,
    description TEXT,
    alert_data JSONB,

    -- Status
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by VARCHAR(64),
    acknowledged_at TIMESTAMPTZ,

    -- Linkage
    case_id UUID REFERENCES fraud_gov.transaction_cases(id),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

#### 6.2 Alert Types (Future)

- `HIGH_VELOCITY_PATTERN` - Unusual velocity across multiple cards
- `MERCHANT_SPIKE` - Unusual transaction volume for merchant
- `GEOGRAPHIC_ANOMALY` - Transactions from unusual locations
- `AMOUNT_ANOMALY` - Unusual transaction amounts
- `RULE_EFFECTIVENESS` - Rule triggering too often/rarely

---

## Project 2: card-fraud-rule-engine

### Phase 1: Enhanced Decision Event

Update the decision event published to Kafka to include:

#### 1.1 Full Transaction Context

```java
// src/main/java/com/fraud/engine/kafka/DecisionEvent.java

public class DecisionEvent {
    // Existing fields...

    // NEW: Full transaction context (extensible)
    private Map<String, Object> transactionContext;

    // NEW: Full velocity snapshot
    private Map<String, VelocityResult> velocitySnapshot;

    // NEW: Engine metadata
    private EngineMetadata engineMetadata;
}

public class EngineMetadata {
    private String engineMode;      // NORMAL, DEGRADED, FAIL_OPEN
    private String errorCode;
    private String errorMessage;
    private double processingTimeMs;
}
```

#### 1.2 Enhanced Rule Match Details

```java
// src/main/java/com/fraud/engine/domain/MatchedRule.java

public class MatchedRule {
    // Existing fields...

    // NEW: Why this rule matched (for audit)
    private List<String> conditionsMet;

    // NEW: Actual values that were evaluated
    private Map<String, Object> conditionValues;
}
```

#### 1.3 All Velocity Dimensions

```java
// Capture ALL velocity checks, not just those that exceeded
public class VelocityResult {
    private String dimension;       // card_hash, ip_address, device_id, etc.
    private String dimensionValue;  // The actual value checked
    private int count;              // Current counter value
    private int threshold;          // Threshold configured
    private int windowSeconds;      // Time window
    private boolean exceeded;       // Did it exceed?
}
```

### Phase 2: Velocity Persistence

Ensure rule engine sends ALL velocity dimensions checked:

```java
// In evaluation flow
Map<String, VelocityResult> velocitySnapshot = new HashMap<>();

// Always capture, even if not exceeded
velocitySnapshot.put("card_1h", checkVelocity("card_hash", cardHash, 3600));
velocitySnapshot.put("card_24h", checkVelocity("card_hash", cardHash, 86400));
velocitySnapshot.put("ip_1h", checkVelocity("ip_address", ipAddress, 3600));
velocitySnapshot.put("device_1h", checkVelocity("device_id", deviceId, 3600));

decisionEvent.setVelocitySnapshot(velocitySnapshot);
```

### Phase 3: Condition Tracking

Track which conditions matched and their actual values:

```java
// During rule evaluation
List<String> conditionsMet = new ArrayList<>();
Map<String, Object> conditionValues = new HashMap<>();

for (Condition condition : rule.getConditions()) {
    Object actualValue = getFieldValue(transaction, condition.getField());
    boolean matched = evaluateCondition(condition, actualValue);

    if (matched) {
        conditionsMet.add(condition.toHumanReadable()); // "amount > 5000"
        conditionValues.put(condition.getField(), actualValue);
    }
}

// Add velocity conditions if present
if (rule.hasVelocity() && velocityExceeded) {
    conditionsMet.add(String.format("velocity(%s, %ds) >= %d",
        rule.getVelocity().getDimension(),
        rule.getVelocity().getWindowSeconds(),
        rule.getVelocity().getThreshold()));
    conditionValues.put("velocity_" + rule.getVelocity().getDimension(), velocityResult);
}

matchedRule.setConditionsMet(conditionsMet);
matchedRule.setConditionValues(conditionValues);
```

---

## Project 3: card-fraud-intelligence-portal

### Phase 1: Transaction Review UI

#### 1.1 Transaction Detail Page Enhancements

```typescript
// src/resources/transactions/show.tsx

// Add Review Actions Panel
<ReviewActionsPanel
  transactionId={transaction.transaction_id}
  currentStatus={review?.status}
  onStatusChange={handleStatusChange}
  onAssign={handleAssign}
  onEscalate={handleEscalate}
  onResolve={handleResolve}
/>

// Add Notes Panel
<NotesPanel
  transactionId={transaction.transaction_id}
  notes={notes}
  onAddNote={handleAddNote}
/>

// Add Velocity Display
<VelocityPanel
  velocitySnapshot={transaction.velocity_snapshot}
/>

// Add Condition Details
<RuleConditionsPanel
  matchedRules={transaction.matched_rules}
/>
```

#### 1.2 New Components

```
src/components/
├── review/
│   ├── ReviewActionsPanel.tsx
│   ├── StatusBadge.tsx
│   ├── StatusTransitionButton.tsx
│   ├── AssignAnalystModal.tsx
│   ├── ResolveModal.tsx
│   └── EscalateModal.tsx
├── notes/
│   ├── NotesPanel.tsx
│   ├── NoteCard.tsx
│   ├── AddNoteModal.tsx
│   └── NoteTypeSelector.tsx
├── velocity/
│   ├── VelocityPanel.tsx
│   └── VelocityDimensionCard.tsx
└── conditions/
    ├── RuleConditionsPanel.tsx
    └── ConditionTreeView.tsx
```

### Phase 2: Analyst Worklist Page

#### 2.1 New Page: `/worklist`

```typescript
// src/resources/worklist/list.tsx

export const WorklistPage = () => {
  return (
    <Page title="My Worklist">
      {/* Stats Cards */}
      <WorklistStats />

      {/* Filters */}
      <WorklistFilters />

      {/* Transaction Queue */}
      <WorklistTable
        columns={[
          'priority',
          'transaction_id',
          'amount',
          'decision',
          'risk_level',
          'assigned_at',
          'time_in_queue',
          'actions'
        ]}
      />

      {/* Claim Next Button */}
      <ClaimNextButton />
    </Page>
  );
};
```

#### 2.2 Worklist Components

```
src/resources/worklist/
├── list.tsx              # Main worklist page
├── stats.tsx             # Worklist statistics cards
├── filters.tsx           # Filter controls
├── claim-button.tsx      # Claim next transaction
└── components/
    ├── WorklistTable.tsx
    ├── PriorityIndicator.tsx
    └── TimeInQueue.tsx
```

### Phase 3: Case Management Pages

#### 3.1 New Pages

```
src/resources/cases/
├── list.tsx              # Case list with filters
├── show.tsx              # Case detail page
├── create.tsx            # Create new case
├── edit.tsx              # Edit case
└── components/
    ├── CaseHeader.tsx
    ├── CaseTransactionList.tsx
    ├── CaseActivityLog.tsx
    ├── AddTransactionModal.tsx
    └── ResolveCaseModal.tsx
```

#### 3.2 Case List Page

```typescript
// src/resources/cases/list.tsx

export const CaseListPage = () => {
  return (
    <Page title="Cases">
      {/* Stats */}
      <CaseStats />

      {/* Filters */}
      <CaseFilters />

      {/* Cases Table */}
      <CasesTable
        columns={[
          'case_number',
          'title',
          'case_type',
          'case_status',
          'transaction_count',
          'total_amount',
          'assigned_to',
          'created_at',
          'actions'
        ]}
      />

      {/* Create Case Button */}
      <CreateCaseButton />
    </Page>
  );
};
```

#### 3.3 Case Detail Page

```typescript
// src/resources/cases/show.tsx

export const CaseShowPage = () => {
  return (
    <Page title={case.case_number}>
      {/* Case Header */}
      <CaseHeader case={case} />

      {/* Tabs */}
      <Tabs>
        <Tab label="Transactions">
          <CaseTransactionList caseId={case.id} />
        </Tab>
        <Tab label="Activity">
          <CaseActivityLog caseId={case.id} />
        </Tab>
        <Tab label="Notes">
          <CaseNotesPanel caseId={case.id} />
        </Tab>
      </Tabs>

      {/* Actions */}
      <CaseActions case={case} />
    </Page>
  );
};
```

### Phase 4: Enhanced Filters

#### 4.1 Transaction List Filters

```typescript
// Add to src/resources/transactions/list.tsx

<Filters>
  {/* Existing filters */}
  <DecisionFilter />
  <DecisionReasonFilter />
  <DateRangeFilter />

  {/* NEW filters */}
  <ReviewStatusFilter />      // PENDING, IN_REVIEW, RESOLVED, etc.
  <RiskLevelFilter />         // LOW, MEDIUM, HIGH, CRITICAL
  <AssignedAnalystFilter />   // Filter by analyst
  <CaseFilter />              // Filter by case
  <AmountRangeFilter />       // Min/max amount
  <CardNetworkFilter />       // VISA, MC, AMEX, etc.
  <MCCFilter />               // Merchant category
  <VelocityExceededFilter />  // Transactions with velocity exceeded
</Filters>
```

### Phase 5: Dashboard Enhancements

#### 5.1 Workflow Metrics

```typescript
// src/resources/transactions/metrics.tsx

// Add new sections:

<WorkflowMetrics>
  {/* Status Distribution */}
  <StatusDistributionChart />

  {/* Analyst Performance */}
  <AnalystPerformanceTable />

  {/* Average Resolution Time */}
  <ResolutionTimeChart />

  {/* Case Statistics */}
  <CaseStatistics />
</WorkflowMetrics>
```

#### 5.2 Charts/Visualizations

```
src/components/charts/
├── StatusDistributionPie.tsx
├── DecisionTrendLine.tsx
├── VelocityHeatmap.tsx
├── TopRulesBar.tsx
├── ResolutionTimeline.tsx
└── AnalystWorkloadBar.tsx
```

### Phase 6: Bulk Operations

#### 6.1 Bulk Selection

```typescript
// Add to transaction list
<BulkActionsBar
  selectedCount={selected.length}
  onAssign={handleBulkAssign}
  onStatusChange={handleBulkStatusChange}
  onCreateCase={handleBulkCreateCase}
  onExport={handleBulkExport}
/>
```

### Phase 7: Export Features

#### 7.1 Export Options

```typescript
// src/components/export/ExportButton.tsx

<ExportMenu>
  <ExportCSV />
  <ExportExcel />
  <ExportPDF />
</ExportMenu>
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1-2)
**card-fraud-transaction-management:**
- [ ] Update DDL with new ENUMs and tables
- [ ] Run `uv run db-reset-schema` to recreate
- [ ] Add JSONB columns to transactions table
- [ ] Update Kafka consumer for new fields
- [ ] Create review, notes, case repositories
- [ ] Create review, notes, case services

### Phase 2: Core APIs (Week 2-3)
**card-fraud-transaction-management:**
- [ ] Implement review endpoints
- [ ] Implement notes endpoints
- [ ] Implement worklist endpoints
- [ ] Implement case endpoints
- [ ] Update transaction query with review status

**card-fraud-rule-engine:**
- [ ] Add transactionContext to decision event
- [ ] Add velocitySnapshot to decision event
- [ ] Add conditionsMet/conditionValues to matched rules
- [ ] Update Kafka producer

### Phase 3: UI - Review & Notes (Week 3-4)
**card-fraud-intelligence-portal:**
- [ ] Add ReviewActionsPanel component
- [ ] Add NotesPanel component
- [ ] Update transaction detail page
- [ ] Add status transition buttons
- [ ] Add resolve/escalate modals

### Phase 4: UI - Worklist & Cases (Week 4-5)
**card-fraud-intelligence-portal:**
- [ ] Create worklist page
- [ ] Create case list page
- [ ] Create case detail page
- [ ] Add bulk operations bar
- [ ] Update navigation menu

### Phase 5: Enhanced Features (Week 5-6)
**All projects:**
- [ ] Add advanced filters
- [ ] Add charts/visualizations
- [ ] Add export functionality
- [ ] Add velocity display panel
- [ ] Add condition tree viewer

### Phase 6: Archive & Analytics (Week 6-7)
**card-fraud-transaction-management:**
- [ ] Implement archive job
- [ ] Implement DuckDB query service
- [ ] Add archive API endpoints
- [ ] Test Parquet generation

### Phase 7: AI Agent Support (Week 7-8) - Future
**card-fraud-transaction-management:**
- [ ] Add agent query endpoint
- [ ] Add explain endpoint
- [ ] Integrate with MCP tools

### Phase 8: Alerts (Week 8+) - Future
**card-fraud-transaction-management:**
- [ ] Add alerts table
- [ ] Implement alert detection
- [ ] Add alert UI components

---

## Testing Requirements

### Unit Tests
- [ ] Review service tests
- [ ] Notes service tests
- [ ] Case service tests
- [ ] Worklist service tests
- [ ] Archive service tests

### Integration Tests
- [ ] Review API tests
- [ ] Notes API tests
- [ ] Case API tests
- [ ] Kafka consumer tests (with new fields)

### E2E Tests
- [ ] Review workflow (assign → review → resolve)
- [ ] Case workflow (create → add transactions → resolve)
- [ ] Bulk operations

---

## API Documentation Updates

- [ ] Update OpenAPI spec with new endpoints
- [ ] Update UI_INTEGRATION.md
- [ ] Update AGENTS.md
- [ ] Create WORKFLOW_GUIDE.md

---

## Permissions/Roles

New permissions needed:

| Permission | Description | Roles |
|------------|-------------|-------|
| `txn:review` | Update transaction review status | FRAUD_ANALYST, FRAUD_SUPERVISOR |
| `txn:assign` | Assign transactions | FRAUD_SUPERVISOR |
| `txn:resolve` | Resolve transactions | FRAUD_ANALYST, FRAUD_SUPERVISOR |
| `txn:escalate` | Escalate transactions | FRAUD_ANALYST |
| `note:create` | Create notes | FRAUD_ANALYST, FRAUD_SUPERVISOR |
| `note:delete` | Delete notes | FRAUD_SUPERVISOR (or note author) |
| `case:create` | Create cases | FRAUD_ANALYST, FRAUD_SUPERVISOR |
| `case:resolve` | Resolve cases | FRAUD_SUPERVISOR |
| `bulk:operations` | Bulk operations | FRAUD_SUPERVISOR |

---

## Success Criteria

1. **Analyst can review transactions:**
   - View transaction details with velocity/conditions
   - Change status through workflow
   - Add notes
   - Resolve with reason

2. **Analyst has worklist:**
   - See assigned transactions
   - Claim unassigned transactions
   - Prioritized queue

3. **Cases can group transactions:**
   - Create case from selection
   - Add/remove transactions
   - Track case activity

4. **Full audit trail:**
   - All actions logged
   - Velocity preserved
   - Conditions documented

5. **Archive works:**
   - Old data archived to S3
   - Queryable via DuckDB
   - PostgreSQL stays lean

---

**End of Plan**
