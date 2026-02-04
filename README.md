# Card Fraud Transaction Management

FastAPI service for ingesting fraud decision events, storing them idempotently, and supporting analyst workflows (reviews, notes, cases, worklists, and bulk actions).

## Quick Start

```powershell
uv sync --extra dev
uv run local-full-setup --yes
uv run doppler-local
```

API docs (local): `http://localhost:8002/docs`

## Core Responsibilities

- Ingest decision events via HTTP and Kafka
- Persist transactions and rule matches with idempotency guarantees
- Expose query and analyst workflow APIs
- Support replay/backfill operations

## Stack

- FastAPI
- SQLAlchemy async + PostgreSQL
- Kafka (Redpanda locally)
- Auth0 JWT auth
- Doppler secrets management

## High-Value Commands

```powershell
# Infra
uv run infra-check
uv run infra-local-up

# DB
uv run db-init
uv run db-verify

# Tests
uv run doppler-local-test
uv run doppler-test
uv run doppler-prod

# Quality/docs
uv run lint
uv run format
uv run openapi
```

## API Base Path

`/api/v1`

For full endpoint details, use `docs/03-api/openapi.json`.

## Documentation

- `AGENTS.md` - canonical agent instructions
- `DEVELOPER_GUIDE.md` - command reference
- `docs/README.md` - documentation index and archive map
- `docs/01-setup/` - setup guides
- `docs/06-operations/` - operations runbooks

## Security and Compliance

- Doppler-first secrets management (no `.env` workflow for normal usage)
- No raw PAN storage
- Tokenized card identifiers only
- Local-only JWT bypass guarded by config validation
