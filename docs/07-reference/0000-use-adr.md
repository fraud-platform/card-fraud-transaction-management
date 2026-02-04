# Architecture Decision Records (ADRs)

This directory contains Architecture Decision Records (ADRs) for the Card Fraud Transaction Management service.

## What is an ADR?

An Architecture Decision Record (ADR) is a document that describes an important architectural decision, the context surrounding it, and the consequences of adopting that decision.

## ADR Template

Each ADR follows this structure:

```markdown
# ADR-XXX: [Title]

**Status:** Accepted | Proposed | Deprecated | Superseded

**Date:** YYYY-MM-DD

**Context:** [Problem statement and context]

**Decision:** [The decision made]

**Consequences:**
- Positive: [Benefits]
- Negative: [Drawbacks/Trade-offs]

**Alternatives Considered:**
- [Alternative 1]
- [Alternative 2]

**Related:**
- ADR-XXX
- [Link to related docs]
```

## ADR Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [ADR-001](0001-async-sqlalchemy.md) | Use Async SQLAlchemy | Accepted | 2026-01-27 |
| [ADR-002](0002-composite-idempotency-key.md) | Composite Idempotency Key | Accepted | 2026-01-27 |
| [ADR-003](0003-separate-review-layer.md) | Separate Review Layer from Immutable Events | Accepted | 2026-01-27 |
| [ADR-004](0004-evaluation-types.md) | PREAUTH/POSTAUTH Evaluation Types | Accepted | 2026-01-27 |
| [ADR-005](0005-uuidv7-for-ids.md) | UUIDv7 for All IDs | Accepted | 2026-01-27 |
| [ADR-006](0006-kafka-dlz-pattern.md) | Kafka Consumer with DLQ Pattern | Accepted | 2026-01-27 |
| [ADR-007](0007-ruleset-metadata.md) | Ruleset Metadata Tracking | Accepted | 2026-01-27 |
| [ADR-008](0008-token-only-card-mode.md) | Token-Only Card Data Mode (PCI Compliance) | Accepted | 2026-01-27 |

## How to Create a New ADR

1. Copy the template above
2. Use the next sequential number (ADR-009, ADR-010, etc.)
3. Fill in all sections
4. Save as `docs/07-reference/NNNN-short-title.md`
5. Update this index

## Categories

- **Data Architecture:** ADR-002, ADR-003, ADR-004, ADR-007
- **Technology Choices:** ADR-001, ADR-006
- **Security & Compliance:** ADR-008
- **Identity & Data:** ADR-005
