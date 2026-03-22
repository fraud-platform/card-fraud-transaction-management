# Code Map

## Repository Purpose

FastAPI service for decision-event ingestion, transaction query, and analyst workflows.
Auth0 runtime accepts the shared human-user audience plus the service audience.
Shared M2M normalization comes from the rule-management credentials-exchange Action, which mirrors issued access-token scopes into `permissions`.

## Documentation Layout

- `01-setup/`: Setup
- `02-development/`: Development
- `03-api/`: API
- `04-testing/`: Testing
- `05-deployment/`: Deployment
- `06-operations/`: Operations
- `07-reference/`: Reference

## Local Commands

- `uv sync`
- `uv run doppler-local`
- `uv run doppler-local-test`
- `curl -H "X-Metrics-Token: $METRICS_TOKEN" http://localhost:8002/metrics`

## Platform Modes

- Standalone mode: run this repository with its own local commands and Doppler config.
- Consolidated mode: run via `card-fraud-platform` for cross-service local validation.
