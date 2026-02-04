# ADR-005: UUIDv7 for All Primary Keys

**Status:** Accepted

**Date:** 2026-01-27

**Context:**

The application needs globally unique identifiers for:
- Transactions (events)
- Reviews
- Notes
- Cases

Key requirements:
- Must be generable in application (not database)
- Must be time-ordered for efficient B-tree indexing
- Must be globally unique (no coordination between services)
- Must work with PostgreSQL UUID type

**Options Considered:**

| Option | Time-Ordered | App-Generated | DB Collision Risk | Index Performance |
|--------|--------------|----------------|-------------------|-------------------|
| UUID v1 | Yes | Yes | Low | Good |
| UUID v4 | No | Yes | Low | Poor (random) |
| UUID v7 | Yes | Yes | None | Excellent |
| Auto-increment | Yes | No | N/A | Excellent |
| Snowflake | Yes | Yes | Requires config | Good |

**Decision:**

Use **UUIDv7** for all primary key identifiers, generated in the application before database insertion.

**Technical Implementation:**
```python
from uuid import UUID, uuid7  # Python 3.14+

# Generate in application
event_id = uuid7()  # Returns UUIDv7

# Insert with explicit ID (no database default)
INSERT INTO fraud_gov.transactions (id, transaction_id, ...)
VALUES (:event_id, :transaction_id, ...);
```

**DDL Constraint:**
```sql
-- NEVER add DEFAULT gen_random_uuid() to ID columns
CREATE TABLE fraud_gov.transactions (
    id UUID NOT NULL PRIMARY KEY,  -- No default!
    transaction_id UUID NOT NULL,
    -- ...
);

-- WRONG (do not do this):
-- id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY
```

**Why UUIDv7?**

UUIDv7 combines the benefits of UUIDs with time-ordering:
- First 48 bits: Unix timestamp (milliseconds since epoch)
- Remaining bits: Random for uniqueness
- Result: Time-sorted, globally unique, no coordination needed

**Index Performance:**
```
UUIDv4 (random):     Poor  - Scattered inserts, index fragmentation
UUIDv7 (time-ordered): Excellent - Sequential inserts, like auto-increment
Auto-increment:      Excellent - But requires database generation
```

**Consequences:**

**Positive:**
- Application has ID before database insert (needed for Kafka, logging)
- Time-ordered for efficient B-tree scans
- No database coordination needed
- No collision risk with proper random bits
- Works with PostgreSQL native UUID type
- Natural sort order = insertion order (useful for pagination)

**Negative:**
- Requires Python 3.13+ for built-in `uuid.uuid7()`
- Slightly larger than 64-bit auto-increment (16 bytes vs 8 bytes)
- Need external library for older Python versions

**UUIDv7 Structure:**
```
┌─────────────────────┬──────────────────────────────────────────┐
│    Timestamp (48b)   │           Random (74b)                   │
├─────────────────────┼──────────────────────────────────────────┤
│ Unix MS (since epoch)│ Uniqueness, randomness                   │
└─────────────────────┴──────────────────────────────────────────┘
```

**Comparison with Alternatives:**

**vs UUIDv4 (Random):**
- UUIDv4: Scattered index inserts, poor for time-series queries
- UUIDv7: Sequential inserts, excellent for time-series

**vs Auto-increment:**
- Auto-increment: Requires database round-trip to get ID
- UUIDv7: ID known before insert, better for distributed systems

**vs Snowflake:**
- Snowflake: Requires worker ID coordination
- UUIDv7: No coordination needed

**Use Cases by ID Type:**

| ID Field | Type | Rationale |
|----------|------|-----------|
| `transactions.id` | UUIDv7 | PK, needs to be time-ordered |
| `transaction_id` | UUIDv7 | Business key, shared across services |
| `transaction_reviews.id` | UUIDv7 | PK, links to transactions.id |
| `analyst_notes.id` | UUIDv7 | PK, independent entity |
| `transaction_cases.id` | UUIDv7 | PK, case identifier |
| `rule_id` | UUIDv7 | From rule-management service |
| `rule_version_id` | UUIDv7 | Specific rule version |

**Related:**
- [AGENTS.md](../../AGENTS.md) - UUID Strategy section
- [db/fraud_transactions_schema.sql](../../db/fraud_transactions_schema.sql)
