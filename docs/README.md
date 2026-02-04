# Card Fraud Transaction Management Documentation

FastAPI service for decision-event ingestion, transaction query, and analyst workflows.

## Quick Start

```powershell
uv sync
uv run doppler-local
uv run doppler-local-test
```

## Documentation Standards

- Keep published docs inside `docs/01-setup` through `docs/07-reference`.
- Use lowercase kebab-case file names for topic docs.
- Exceptions: `README.md`, `codemap.md`, and generated contract artifacts (for example `openapi.json`).
- Do not keep TODO/archive/status/session planning docs in tracked documentation.

## Section Index

### `01-setup` - Setup

Prerequisites, first-run onboarding, and environment bootstrap.

- `01-setup/auth0-setup-guide.md`
- `01-setup/configuration.md`
- `01-setup/database-setup.md`
- `01-setup/doppler-secrets-setup.md`
- `01-setup/kafka-setup.md`

### `02-development` - Development

Day-to-day workflows, architecture notes, and contributor practices.

- `02-development/architecture.md`
- `02-development/domain-and-contracts.md`
- `02-development/idempotency-and-replay.md`
- `02-development/storage-and-migrations.md`

### `03-api` - API

Contracts, schemas, endpoint references, and integration notes.

- `03-api/decision-event-schema-v1.md`
- `03-api/../03-api/decision-event.schema.v1.json`
- `03-api/ingestion.md`
- `03-api/openapi-outline.md`
- `03-api/openapi.json`
- `03-api/query-api.md`
- `03-api/ui-integration.md`

### `04-testing` - Testing

Test strategy, local commands, and validation playbooks.

- `04-testing/testing-strategy.md`

### `05-deployment` - Deployment

Local runtime/deployment patterns and release-readiness guidance.

- `05-deployment/deployment-and-config.md`

### `06-operations` - Operations

Runbooks, observability, troubleshooting, and security operations.

- `06-operations/dlq-triage.md`
- `06-operations/error-and-dlq-model.md`
- `06-operations/observability.md`
- `06-operations/replay-backfill.md`
- `06-operations/retention-and-archival.md`
- `06-operations/runbook-readme.md`
- `06-operations/security-and-data-governance.md`

### `07-reference` - Reference

ADRs, glossary, and cross-repo reference material.

- `07-reference/0000-use-adr.md`
- `07-reference/0001-async-sqlalchemy.md`
- `07-reference/0002-composite-idempotency-key.md`
- `07-reference/0003-separate-review-layer.md`
- `07-reference/0004-evaluation-types.md`
- `07-reference/0005-uuidv7-for-ids.md`
- `07-reference/0006-kafka-dlz-pattern.md`
- `07-reference/0007-ruleset-metadata.md`
- `07-reference/0008-token-only-card-mode.md`
- `07-reference/auth-model.md`
- `07-reference/fraud-analyst-workflow.md`

## Core Index Files

- `docs/README.md`
- `docs/codemap.md`
