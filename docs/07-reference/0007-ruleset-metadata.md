# ADR-007: Ruleset Metadata Tracking

**Status:** Accepted

**Date:** 2026-01-27

**Context:**

Fraud decisions are made based on a specific version of a ruleset (collection of rules). For analysis, debugging, and compliance, we need to answer:

1. "Which ruleset version made this decision?"
2. "What rules were in the ruleset at decision time?"
3. "How did rule changes affect decision rates?"
4. "Can we compare decisions across ruleset versions?"

The original design only stored individual `rule_id` and `rule_version` for matched rules, but not the containing ruleset context.

**Requirements:**
- Track which ruleset produced each decision
- Enable ruleset-level analysis (decision rates by ruleset version)
- Support A/B testing of different ruleset versions
- Maintain historical accuracy (ruleset at decision time, not current)

**Decision:**

Add ruleset metadata columns to the `transactions` table and enhance rule match tracking with `rule_version_id` (UUID).

**Technical Implementation:**
```sql
-- Ruleset metadata on transactions
CREATE TABLE fraud_gov.transactions (
    -- ... existing columns ...
    ruleset_key VARCHAR(128),           -- Human-readable ruleset identifier
    ruleset_id UUID,                     -- UUID of the ruleset
    ruleset_version INTEGER,             -- Version number
    -- ... existing columns ...
);

-- Enhanced rule match tracking
CREATE TABLE fraud_gov.transaction_rule_matches (
    -- ... existing columns ...
    rule_version_id UUID,                -- NEW: UUID identifier for specific rule version
    rule_version INTEGER,                -- Integer version (kept for compatibility)
    rule_name VARCHAR(128) NOT NULL,
    rule_action fraud_gov.rule_action,   -- NEW: Action (APPROVE/DECLINE/REVIEW)
    conditions_met JSONB,                -- NEW: Which conditions matched
    condition_values JSONB,              -- NEW: Actual values evaluated
    -- ... existing columns ...
);
```

**Why Both `rule_version_id` (UUID) and `rule_version` (INTEGER)?**

| Field | Type | Purpose | Source |
|-------|------|---------|--------|
| `rule_version_id` | UUID | Precise identifier, links to rule-management service | From rule engine |
| `rule_version` | INTEGER | Human-readable version number | From rule engine |

**Query Patterns:**
```sql
-- Compare decision rates across ruleset versions
SELECT
    ruleset_key,
    ruleset_version,
    COUNT(*) FILTER (WHERE decision = 'APPROVE') AS approved_count,
    COUNT(*) FILTER (WHERE decision = 'DECLINE') AS declined_count,
    ROUND(100.0 * COUNT(*) FILTER (WHERE decision = 'DECLINE') / COUNT(*), 2) AS decline_rate_pct
FROM fraud_gov.transactions
WHERE transaction_timestamp >= NOW() - INTERVAL '7 days'
GROUP BY ruleset_key, ruleset_version
ORDER BY ruleset_key, ruleset_version DESC;

-- Find transactions using specific ruleset version
SELECT t.transaction_id, t.decision
FROM fraud_gov.transactions t
WHERE t.ruleset_key = 'production.v1'
  AND t.ruleset_version = 42;

-- Analyze rule match details
SELECT
    trm.rule_name,
    trm.rule_action,
    COUNT(*) AS match_count,
    COUNT(*) FILTER (WHERE t.decision = 'DECLINE') AS decline_count
FROM fraud_gov.transaction_rule_matches trm
JOIN fraud_gov.transactions t ON t.transaction_id = t.id
WHERE trm.rule_version_id = :rule_version_id
GROUP BY trm.rule_name, trm.rule_action;
```

**Consequences:**

**Positive:**
- Full traceability from decision → ruleset → rules
- Enables ruleset performance analysis
- Supports A/B testing (compare decisions by ruleset version)
- Historical accuracy (ruleset at decision time preserved)
- Enhanced debugging (know exactly which rules and conditions fired)

**Negative:**
- Additional storage overhead (3 columns per transaction)
- Must populate fields correctly (data quality dependency)
- Slightly larger index footprint
- Rule engine must provide ruleset metadata

**Data Flow:**
```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│ Rule Engine      │────>│ Kafka Topic      │────>│ This Service     │
│                  │     │                  │     │                  │
│ Output includes: │     │ Event payload:   │     │ Stores:          │
│ - ruleset_key    │     │ - ruleset_key    │     │ - ruleset_key    │
│ - ruleset_id     │     │ - ruleset_id     │     │ - ruleset_id     │
│ - ruleset_version│     │ - ruleset_version│     │ - ruleset_version│
│ - rule_version_id│     │ - matched_rules[] │     │ - rule_version_id│
└──────────────────┘     └──────────────────┘     └──────────────────┘
```

**Schema Evolution:**
- Original design: No ruleset tracking
- V1 (this ADR): Add ruleset metadata columns
- Future: May add ruleset_diff (what changed between versions)

**Alternatives Considered:**

1. **Look up ruleset from rule-management service (at query time)**
   - Rejected: Loses historical accuracy (ruleset may have changed)
   - Adds service dependency and latency

2. **Store only ruleset_key, not ID/version**
   - Rejected: Cannot distinguish between versions of same ruleset
   - Limits analysis capabilities

3. **Separate rulesets table (lookup)**
   - Rejected: Adds complexity without clear benefit
   - Ruleset management is rule-management's responsibility

4. **JSONB ruleset blob**
   - Rejected: Harder to query, no type safety
   - Indexed columns more efficient for common queries

**Compliance & Audit:**

For regulatory compliance, we must be able to reconstruct:
1. What rules were in effect at decision time?
2. What version of each rule was used?
3. What conditions matched?

This ADR enables all three requirements.

**Related:**
- ADR-002: Composite Idempotency Key
- [docs/../03-api/decision-event-schema-v1.md](../03-api/decision-event-schema-v1.md)
- [db/fraud_transactions_schema.sql](../../db/fraud_transactions_schema.sql)
