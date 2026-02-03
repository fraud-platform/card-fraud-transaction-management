# AGENTS.md

This is the canonical instruction file for coding agents working in `card-fraud-transaction-management`.

Use this file first. Keep `CLAUDE.md` as a pointer to this file only.

## Cross-Repo Agent Standards

- Secrets: Doppler-only workflows. Do not create or commit `.env` files.
- Commands: use repository wrappers from `pyproject.toml` or `package.json`; avoid ad-hoc commands.
- Docs publishing: keep only curated docs in `docs/01-setup` through `docs/07-reference`, plus `docs/README.md` and `docs/codemap.md`.
- Docs naming: use lowercase kebab-case for docs files. Exceptions: `README.md`, `codemap.md`, and generated contract files.
- Never commit docs/planning artifacts named `todo`, `status`, `archive`, or session notes.
- If behavior, routes, scripts, ports, or setup steps change, update `README.md`, `AGENTS.md`, `docs/README.md`, and `docs/codemap.md` in the same change.
- Keep health endpoint references consistent with current service contracts (for APIs, prefer `/api/v1/health`).
- Preserve shared local port conventions from `card-fraud-platform` unless an explicit migration is planned.
- Before handoff, run the repo's local lint/type/test gate and report the exact command + result.

## Agent Contract

- Treat this file as source of truth for commands, architecture guardrails, and safety rules.
- Prefer updating docs to match implementation. If docs are correct and code is wrong, fix code.
- Do not remove historical information; archive it under `docs/archive/`.
- Use ASCII when editing docs unless there is a strong reason not to.

## Core Rules

- Secrets: Doppler is required. Do not use `.env` workflows for normal development.
- Data safety: only manage this service's tables and topics.
- IDs: generate UUIDv7 in application code, never via DB defaults.
- Auth bypass: `SECURITY_SKIP_JWT_VALIDATION=true` is allowed only when `APP_ENV=local`.

## Quick Start

```powershell
# Install dependencies
uv sync --extra dev

# One-command local setup
uv run local-full-setup --yes

# Start API with Doppler local config
uv run doppler-local
```

## Most Used Commands

```powershell
# Infrastructure (platform-first)
uv run infra-check
uv run infra-local-up
uv run infra-local-down            # preserve volumes
uv run infra-local-down -- -v      # remove volumes

# DB lifecycle
uv run db-init
uv run db-verify
uv run db-reset-data
uv run db-reset-tables

# Tests
uv run doppler-local-test
uv run doppler-test
uv run doppler-prod
uv run pytest tests/unit -v --no-cov

# Kafka
uv run kafka-local-up
python scripts/setup_kafka.py create-topics

# Docs / quality
uv run openapi
uv run lint
uv run format
```

## Local Infrastructure

This service is part of the Card Fraud Platform. Prefer shared infra from `../card-fraud-platform`.

```powershell
cd ../card-fraud-platform
uv run platform-up
uv run platform-status
```

Fallback (from this repo):

```powershell
uv run infra-local-up
uv run db-local-up
uv run redis-local-up
uv run kafka-local-up
uv run objstore-local-up
```

## Neon / Doppler DB Setup

```powershell
# Full setup (test + prod)
uv run neon-full-setup --yes

# One environment
uv run neon-full-setup --config=test --yes
uv run neon-full-setup --config=prod --yes

# Granular
uv run neon-setup --delete-project --yes
uv run neon-setup --yes --create-compute
uv run db-sync-doppler-urls --yes
uv run db-init-test
uv run db-init-prod
uv run db-verify-test
uv run db-verify-prod
```

## API Surface (Current)

Base path: `/api/v1`

- Ingestion: `POST /decision-events`
- Transactions: `GET /transactions`, `GET /transactions/{transaction_id}`
- Combined views: `GET /transactions/{transaction_id}/combined`, `GET /transactions/{transaction_id}/overview`
- Metrics: `GET /metrics`
- Reviews: `GET/POST /transactions/{transaction_id}/review`, plus status/assign/resolve/escalate
- Notes: `GET/POST /transactions/{transaction_id}/notes`, plus get/update/delete note
- Cases: list/create/get/update, case transactions, activity, resolve
- Worklist: list/stats/unassigned/claim
- Bulk: assign/status/create-case
- Health: `/api/v1/health`, `/ready`, `/live`

Use `docs/openapi.json` as the API contract artifact.

## Architecture Guardrails

1. UUID strategy
   - Use UUIDv7 in app code.
   - Do not add DB-generated UUID defaults.

2. Idempotency
   - Business key: `transaction_id`.
   - Composite idempotency in DB: `(transaction_id, evaluation_type, transaction_timestamp)`.
   - Rule matches idempotent on `(transaction_id, rule_id, rule_version)`.

3. PCI
   - Never store raw PAN.
   - `card_id` must be tokenized.
   - PAN-like values must be rejected/quarantined.

4. Schema ownership
   - Shared schema: `fraud_gov`.
   - This service tables:
     - `transactions`
     - `transaction_rule_matches`
     - `transaction_reviews`
     - `analyst_notes`
     - `transaction_cases`
     - `case_activity_log`

5. Async stack
   - SQLAlchemy async (`create_async_engine`, `AsyncSession`, `await session.execute`).
   - URL conversion uses `postgresql+asyncpg://` for runtime.

## Testing Guidance

- Fast local unit tests:

```powershell
uv run pytest tests/unit -v --no-cov
uv run pytest tests/unit -v --cov=app --cov-report=term-missing
```

- Integration suites (Doppler-backed):

```powershell
uv run doppler-local-test
uv run doppler-test
uv run doppler-prod
```

- Markers:
  - `unit`
  - `integration`
  - `smoke`
  - `e2e_integration` (excluded by default)

## Auth0 Notes

Bootstrap order across platform repos:

1. `card-fraud-rule-management` first (shared roles, SPA, actions, test users)
2. this repo second (API + M2M app)

```powershell
cd C:\Users\kanna\github\card-fraud-rule-management
uv run auth0-bootstrap --yes --verbose

cd C:\Users\kanna\github\card-fraud-transaction-management
uv run auth0-bootstrap --yes --verbose
```

## Documentation Map

- `README.md`: human-friendly project overview
- `DEVELOPER_GUIDE.md`: command reference
- `docs/README.md`: docs index and archive map
- `docs/openapi.json`: generated API schema
- `docs/01-setup/`: environment setup docs
- `docs/runbooks/`: operational runbooks
- `docs/archive/`: historical docs (do not delete; archive instead)

## Common Problems

- Missing tables: run `uv run db-init`.
- Kafka connection errors: run `uv run kafka-local-up` and create topics.
- Missing DATABASE_URL: run tests with `uv run doppler-...` wrappers.
- Event loop closed in tests: avoid sharing closed async clients between tests.

## Change Management for Docs

When implementation changes:

1. Update `AGENTS.md` if commands/contracts changed.
2. Regenerate OpenAPI (`uv run openapi`) if API changed.
3. Update `README.md`, `DEVELOPER_GUIDE.md`, and `docs/README.md` links.
4. Archive superseded docs under `docs/archive/` instead of deleting content.
