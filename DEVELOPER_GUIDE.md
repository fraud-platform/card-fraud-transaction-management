# Developer Guide

Operational command reference for local development and test workflows.

## Prerequisites

- `uv`
- Docker Desktop
- Doppler CLI
- Python 3.14+

## Start Here

```powershell
uv sync --extra dev
uv run local-full-setup --yes
uv run doppler-local
```

## Infrastructure

```powershell
# Platform-aware status and startup
uv run infra-check
uv run infra-local-up
uv run infra-local-down            # keep volumes
uv run infra-local-down -- -v      # remove volumes

# Individual services
uv run db-local-up
uv run redis-local-up
uv run kafka-local-up
uv run objstore-local-up
```

## Database

```powershell
# Local
uv run db-init
uv run db-verify
uv run db-reset-data
uv run db-reset-tables
uv run db-seed-demo

# Neon (test/prod)
uv run neon-full-setup --yes
uv run db-sync-doppler-urls --yes
uv run db-init-test
uv run db-init-prod
uv run db-verify-test
uv run db-verify-prod
```

## Kafka

```powershell
uv run kafka-local-up
python scripts/setup_kafka.py create-topics
python scripts/setup_kafka.py list-topics
python scripts/setup_kafka.py produce
python scripts/setup_kafka.py consume
```

## Tests

```powershell
# Fast local unit tests
uv run pytest tests/unit -v --no-cov
uv run pytest tests/unit -v --cov=app --cov-report=term-missing

# Doppler-backed suites
uv run doppler-local-test
uv run doppler-test
uv run doppler-prod

# Marker-based subsets
uv run test-smoke
uv run test-e2e
```

## Quality and Docs

```powershell
uv run lint
uv run format
uv run openapi
```

## Auth0

```powershell
uv run auth0-bootstrap --yes --verbose
uv run auth0-verify
```

## Canonical References

- `AGENTS.md`
- `docs/README.md`
- `docs/openapi.json`
