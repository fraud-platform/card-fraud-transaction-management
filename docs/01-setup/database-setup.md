# Database Setup Guide

This guide covers setting up PostgreSQL for the card-fraud-transaction-management service.

## Quick Start

```powershell
# Start PostgreSQL and initialize database
uv run db-local-up
uv run db-init --yes

# Or do everything at once
uv run local-full-setup --yes
```

## Database Isolation

**This project shares the `fraud_gov` schema with card-fraud-rule-management, but manages only its own tables:**

| Resource | This Project | Other Projects |
|----------|--------------|----------------|
| Schema | `fraud_gov` (shared) | `fraud_gov` (shared) |
| Tables | `transactions`, `transaction_rule_matches`, `transaction_reviews`, `analyst_notes`, `transaction_cases`, `case_activity_log` | `rules`, `rulesets`, `approvals`, etc. |
| Reset commands | Only truncate/drop THIS project's tables | Not affected |

## Key Schema Features (2026-01-27 Update)

### Evaluation Types

The `transactions` table now supports two evaluation types:

| Type | Description | Use Case |
|------|-------------|----------|
| `AUTH` | Real-time fraud decision stage | Authorization requests |
| `MONITORING` | Analytics/monitoring stage | Post-authorization analysis |

**Important:** Both AUTH and MONITORING events can be stored for the same `transaction_id` via the composite unique key `(transaction_id, evaluation_type, transaction_timestamp)`.

### Ruleset Metadata

New columns for ruleset tracking:
- `ruleset_key` - Ruleset identifier for version tracking
- `ruleset_id` - UUID of the ruleset
- `ruleset_version` - Version number of the ruleset

### Velocity Results

- `velocity_results` (JSONB) - Per-rule velocity calculation results
- `velocity_snapshot` (JSONB) - Complete velocity state at decision time

### Rule Match Enhancements

New columns in `transaction_rule_matches`:
- `rule_version_id` (UUID) - Specific rule version identifier
- `rule_action` (APPROVE/DECLINE/REVIEW) - Action determined by the rule
- `conditions_met` (JSONB) - Array of condition descriptions that matched
- `condition_values` (JSONB) - Actual values evaluated for each condition

## Tables Created

```sql
-- Core decision events
CREATE TABLE fraud_gov.transactions (
    id UUID PRIMARY KEY,
    transaction_id UUID NOT NULL,
    evaluation_type fraud_gov.evaluation_type NOT NULL,
    card_id VARCHAR(64) NOT NULL,
    card_last4 VARCHAR(4),
    card_network fraud_gov.card_network,
    transaction_amount DECIMAL(19,4) NOT NULL,
    transaction_currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    merchant_id VARCHAR(64),
    merchant_category_code VARCHAR(8),
    decision fraud_gov.decision_type NOT NULL,
    decision_reason fraud_gov.decision_reason NOT NULL,
    decision_score DECIMAL(5,2),
    risk_level fraud_gov.risk_level,
    ruleset_key VARCHAR(128),
    ruleset_id UUID,
    ruleset_version INTEGER,
    transaction_context JSONB,
    velocity_snapshot JSONB,
    velocity_results JSONB,
    engine_metadata JSONB,
    transaction_timestamp TIMESTAMPTZ NOT NULL,
    ingestion_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    kafka_topic VARCHAR(256),
    kafka_partition INTEGER,
    kafka_offset BIGINT,
    source_message_id VARCHAR(256),
    trace_id VARCHAR(64),
    request_id VARCHAR(64),
    session_id VARCHAR(64),
    raw_payload JSONB,
    ingestion_source fraud_gov.ingestion_source NOT NULL DEFAULT 'HTTP',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_transaction_idempotency UNIQUE (transaction_id, evaluation_type, transaction_timestamp)
);

-- Per-transaction rule matches
CREATE TABLE fraud_gov.transaction_rule_matches (
    id SERIAL PRIMARY KEY,
    transaction_id UUID NOT NULL REFERENCES fraud_gov.transactions(id) ON DELETE CASCADE,
    rule_id UUID NOT NULL,
    rule_version_id UUID,
    rule_version INTEGER,
    rule_name VARCHAR(128) NOT NULL,
    rule_action fraud_gov.rule_action,
    matched BOOLEAN NOT NULL DEFAULT FALSE,
    contributing BOOLEAN NOT NULL DEFAULT FALSE,
    rule_output JSONB,
    conditions_met JSONB,
    condition_values JSONB,
    match_score DECIMAL(5,2),
    match_reason VARCHAR(256),
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_transaction_rule_match UNIQUE (transaction_id, rule_id, rule_version)
);

-- Analyst review workflow
CREATE TABLE fraud_gov.transaction_reviews (
    id UUID NOT NULL PRIMARY KEY,
    transaction_id UUID NOT NULL REFERENCES fraud_gov.transactions(id) ON DELETE CASCADE,
    status fraud_gov.transaction_status NOT NULL DEFAULT 'PENDING',
    assigned_analyst_id VARCHAR(128),
    assigned_at TIMESTAMPTZ,
    priority INTEGER NOT NULL DEFAULT 3,
    case_id UUID,
    resolved_at TIMESTAMPTZ,
    resolved_by VARCHAR(128),
    resolution_code VARCHAR(64),
    resolution_notes TEXT,
    escalated_at TIMESTAMPTZ,
    escalated_to VARCHAR(128),
    escalation_reason TEXT,
    first_reviewed_at TIMESTAMPTZ,
    last_activity_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_transaction_review UNIQUE (transaction_id)
);

-- Analyst notes
CREATE TABLE fraud_gov.analyst_notes (
    id UUID NOT NULL PRIMARY KEY,
    transaction_id UUID NOT NULL REFERENCES fraud_gov.transactions(id) ON DELETE CASCADE,
    note_type fraud_gov.note_type NOT NULL DEFAULT 'GENERAL',
    note_content TEXT NOT NULL,
    analyst_id VARCHAR(128) NOT NULL,
    analyst_name VARCHAR(256),
    analyst_email VARCHAR(256),
    is_private BOOLEAN NOT NULL DEFAULT FALSE,
    is_system_generated BOOLEAN NOT NULL DEFAULT FALSE,
    case_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Transaction cases
CREATE TABLE fraud_gov.transaction_cases (
    id UUID NOT NULL PRIMARY KEY,
    case_number VARCHAR(64) NOT NULL UNIQUE,
    case_type fraud_gov.case_type NOT NULL,
    case_status fraud_gov.case_status NOT NULL DEFAULT 'OPEN',
    assigned_analyst_id VARCHAR(128),
    assigned_at TIMESTAMPTZ,
    title VARCHAR(512) NOT NULL,
    description TEXT,
    total_transaction_count INTEGER NOT NULL DEFAULT 0,
    total_transaction_amount DECIMAL(19,4) NOT NULL DEFAULT 0,
    risk_level fraud_gov.risk_level,
    resolved_at TIMESTAMPTZ,
    resolved_by VARCHAR(128),
    resolution_summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMPTZ
);

-- Case activity log
CREATE TABLE fraud_gov.case_activity_log (
    id SERIAL PRIMARY KEY,
    case_id UUID NOT NULL REFERENCES fraud_gov.transaction_cases(id) ON DELETE CASCADE,
    activity_type VARCHAR(64) NOT NULL,
    activity_description TEXT NOT NULL,
    analyst_id VARCHAR(128),
    analyst_name VARCHAR(256),
    old_values JSONB,
    new_values JSONB,
    transaction_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## Available Commands

```powershell
# Start/Stop PostgreSQL
uv run db-local-up       # Start local PostgreSQL
uv run db-local-down     # Stop local PostgreSQL
uv run db-local-reset    # Stop and remove data (THIS PROJECT ONLY)

# Database initialization
uv run db-init           # First-time setup (local)
uv run db-init --demo    # First-time setup with demo data
uv run db-init-test      # First-time setup (test environment)
uv run db-init-prod      # First-time setup (prod environment)

# Database verification
uv run db-verify         # Verify local setup
uv run db-verify-test    # Verify test setup
uv run db-verify-prod    # Verify prod setup

# Database reset (WARNING: destructive)
uv run db-reset-data          # Truncate tables (THIS PROJECT ONLY)
uv run db-reset-schema        # Drop and recreate schema (THIS PROJECT ONLY)
uv run db-reset-data-test     # Truncate tables (test)
uv run db-reset-schema-test   # Drop and recreate (test)
uv run db-reset-data-prod     # Truncate tables (prod)
uv run db-reset-schema-prod   # Drop and recreate (prod)

# Seed demo data
uv run db-seed-demo      # Apply demo data (local only)
```

## Environment Configuration

| Variable | Description | Local Value |
|----------|-------------|-------------|
| `DATABASE_URL` | PostgreSQL connection | `postgresql+asyncpg://postgres:postgres@localhost:5432/fraud_tm` |
| `DATABASE_HOST` | PostgreSQL host | `localhost` |
| `DATABASE_PORT` | PostgreSQL port | `5432` |
| `DATABASE_NAME` | Database name | `fraud_tm` |
| `DATABASE_USER` | Database user | `postgres` |
| `DATABASE_PASSWORD` | Database password | `postgres` |

## Connection Strings

**Local (Docker):**
```
postgresql+asyncpg://postgres:postgres@localhost:5432/fraud_gov
```

**Neon Test:**
```
postgresql+asyncpg://fraud_gov_app_user:pass@ep-xxx.us-east-1.aws.neon.tech/fraud_gov?branch=test
```

**Neon Prod:**
```
postgresql+asyncpg://fraud_gov_app_user:pass@ep-xxx.us-east-1.aws.neon.tech/fraud_gov?branch=prod
```

## Analyst Workflow Tables

### Transaction Reviews

Stores the review workflow state for each transaction:

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `transaction_id` | UUID | FK to transactions.id |
| `status` | ENUM | PENDING, IN_REVIEW, ESCALATED, RESOLVED, CLOSED |
| `assigned_analyst_id` | VARCHAR | Analyst currently assigned |
| `priority` | INTEGER | 1=highest, 5=lowest |
| `case_id` | UUID | Associated case (optional) |
| `resolved_at` | TIMESTAMPTZ | Resolution timestamp |
| `resolved_by` | VARCHAR | Resolver analyst ID |
| `resolution_code` | VARCHAR | Standardized resolution code |
| `escalated_at` | TIMESTAMPTZ | Escalation timestamp |
| `escalated_to` | VARCHAR | Escalation target |
| `last_activity_at` | TIMESTAMPTZ | Last activity timestamp |

**Unique constraint:** One review per transaction (`uk_transaction_review`)

### Analyst Notes

Notes added by analysts during transaction review:

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `transaction_id` | UUID | FK to transactions.id |
| `note_type` | ENUM | GENERAL, INITIAL_REVIEW, CUSTOMER_CONTACT, etc. |
| `note_content` | TEXT | Note content |
| `analyst_id` | VARCHAR | Author analyst ID |
| `analyst_name` | VARCHAR | Author name |
| `analyst_email` | VARCHAR | Author email |
| `is_private` | BOOLEAN | Private note flag |
| `is_system_generated` | BOOLEAN | System-generated note flag |
| `case_id` | UUID | Associated case (optional) |

### Transaction Cases

Groups related transactions for investigation:

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `case_number` | VARCHAR | Human-readable case number (auto-generated) |
| `case_type` | ENUM | INVESTIGATION, DISPUTE, CHARGEBACK, etc. |
| `case_status` | ENUM | OPEN, IN_PROGRESS, PENDING_INFO, RESOLVED, CLOSED |
| `assigned_analyst_id` | VARCHAR | Assigned analyst |
| `title` | VARCHAR | Case title |
| `description` | TEXT | Case description |
| `total_transaction_count` | INTEGER | Total transactions in case (denormalized) |
| `total_transaction_amount` | DECIMAL | Sum of transaction amounts (denormalized) |
| `risk_level` | ENUM | LOW, MEDIUM, HIGH, CRITICAL |
| `resolved_at` | TIMESTAMPTZ | Resolution timestamp |
| `resolved_by` | VARCHAR | Resolver analyst ID |

**Auto-updates:** Triggers maintain `total_transaction_count` and `total_transaction_amount` when transactions are added/removed.

### Case Activity Log

Audit trail for case activities:

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL | Primary key |
| `case_id` | UUID | FK to transaction_cases.id |
| `activity_type` | VARCHAR | Activity type (e.g., "CASE_CREATED", "TRANSACTION_ADDED") |
| `activity_description` | TEXT | Activity description |
| `analyst_id` | VARCHAR | Analyst who performed action |
| `analyst_name` | VARCHAR | Analyst name |
| `old_values` | JSONB | Previous values (for updates) |
| `new_values` | JSONB | New values (for updates) |
| `transaction_id` | UUID | Related transaction (optional) |

**Automatically populated:** Triggers log all case changes.

## Troubleshooting

### "relation 'transactions' does not exist"

```powershell
# Run database initialization
uv run db-init --yes

# Or manually apply schema
psql "$DATABASE_URL" -f db/fraud_transactions_schema.sql
```

### "could not connect to server"

```powershell
# Check if PostgreSQL is running
uv run db-local-up

# Check container status
docker ps --filter "name=card-fraud-transaction-management-postgres"
```

### Reset commands affecting other project data

**This should NOT happen.** Verify reset commands only target this project's tables:

```sql
-- This project's tables
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'fraud_gov'
AND table_name IN ('transactions', 'transaction_rule_matches');

-- Other project tables (should NOT be affected by this project's resets)
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'fraud_gov'
AND table_name NOT IN ('transactions', 'transaction_rule_matches');
```

## Data Isolation Verification

To verify this project only affects its own data:

```powershell
# Check tables created by this project
uv run db-verify

# Output should show:
# - transactions table exists
# - transaction_rule_matches table exists
# - No other tables are created or dropped
```

## Next Steps

1. **Set up Neon for test/prod** - See `uv run neon-full-setup --yes`
2. **Configure Doppler secrets** - Update DATABASE_URL_* in Doppler
3. **Run tests** - `uv run doppler-test`
