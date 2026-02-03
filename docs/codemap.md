# Code Map

## Core Layout

- `app/`: FastAPI service implementation.
  - `api/routes/`: endpoint handlers.
  - `schemas/`: API contracts.
  - `services/`: business orchestration.
  - `persistence/`: repository/data access layer.
  - `ingestion/`: Kafka consumer and ingestion flow.
- `cli/`: `uv run` entrypoints.
- `scripts/`: setup, verification, and local utilities.
- `db/`: SQL and migration-related artifacts.
- `tests/`: unit, smoke, and integration suites.

## Key Commands

- `uv run doppler-local`
- `uv run doppler-local-test`
- `uv run doppler-test`
- `uv run db-init`

## Integration Role

Consumes decision events and serves analyst-facing transaction/review APIs.
