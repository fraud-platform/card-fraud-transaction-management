# Architecture Plan

## Goal
Build a downstream **transaction persistence and management** service that consumes immutable decision events and supports operational queries, dashboards, audit, and replay.

## Non-goals (explicit)
- No fraud decisioning, rule evaluation, velocity checks, Redis-based logic, or rule compilation.
- No additional database tables in v1 beyond `transactions` and `transaction_rule_matches`.

## Context / position
Upstream: `card-fraud-rule-engine` emits decision events.
Downstream: analyst portal / reporting tools query this service.

## Proposed logical components
1. **Ingestion layer**
   - Kafka consumer (preferred) and optional HTTP ingestion endpoint (temporary).
   - Validates event shape and required fields.
   - Applies idempotent persistence.

2. **Persistence layer**
   - Postgres (recommended) or another relational DB that supports JSONB + upsert.
   - Enforces “transaction before rule matches” ordering (atomic transaction).

3. **Query API**
   - Read-only endpoints for worklists/dashboards and analytics queries.
   - Pagination, filtering, and time-range scanning.

4. **Observability & Ops**
   - Structured logs, metrics, tracing.
   - Replay/backfill runbook.

## Stack & deployable model (locked)
- **Single deployable** containing:
   - HTTP API (query endpoints + optional HTTP ingestion)
   - Kafka consumer loop
- **FastAPI** for HTTP layer.
- **PostgreSQL** for persistence.
- Internal modular separation only (e.g., `ingestion/`, `persistence/`, `api/`).

## High-level data flow
1. Receive decision event (Kafka or HTTP).
2. Normalize to internal transaction record + rule match rows.
3. Persist using a single DB transaction with upsert semantics.
4. Expose queries via HTTP read API.

## Failure mode expectations
- At-least-once ingestion implies duplicates: must be safe.
- Partial failures: must not create rule matches without a transaction row.
- Poison messages: must route to DLQ/quarantine with traceability.

## Deployment environments (assumption)
- `dev`, `staging`, `prod`.
- Separate Kafka topics/consumer groups per environment.
- Separate DB per environment.

## Decisions to confirm

Remaining decisions:
- Kafka platform (Confluent/MSK/Event Hubs Kafka endpoint).
- Auth approach for query API (mTLS, OAuth2/JWT, internal network only).

## TODO checklist
- Define repo structure (service, infra, docs, scripts).
- Define environment variables and configuration conventions.
- Define “MVP query API” endpoints used by portal.
- Define SLOs (ingestion latency, API p95).
