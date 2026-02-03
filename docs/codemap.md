# Code Map

## Repository Purpose

FastAPI service for decision-event ingestion, transaction query, and analyst workflows.

## Key Paths

- `app/`: FastAPI application code for ingestion, querying, and workflow APIs.
- `cli/`: Developer and Doppler-aware command wrappers.
- `tests/`: Unit, integration, smoke, and e2e integration tests.
- `scripts/`: Utility scripts for setup and local operations.
- `docs/`: Curated onboarding and operational documentation.

## Local Commands

- `uv sync`
- `uv run doppler-local`
- `uv run doppler-local-test`

## Local Test Commands

- `uv run doppler-local-test`
- `uv run test`

## API Note

Primary API surface is FastAPI under `/api/v1/*`.

## Platform Integration

- Standalone mode: run this repository using its own local commands and Doppler project config.
- Consolidated mode: run this repository through `card-fraud-platform` compose stack for cross-service validation.
