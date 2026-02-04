# Runbooks

This folder contains operational procedures for on-call and support.

- [dlq-triage.md](dlq-triage.md)
- [replay-backfill.md](replay-backfill.md)

---

## Local development quickstart (infra + config)

This service is intended to reuse the same local infrastructure approach as the rule-management project.

### Prerequisites
- Docker Desktop running
- Doppler CLI installed and authenticated

### Local infra
Run the existing local Docker setup used by rule management:
- PostgreSQL (local Docker)
- MinIO (local Docker)

Note: This repo does not currently include a `docker-compose.yml`. If your rule-management repo owns the compose stack, start it from there.

### Local config (Doppler)
Use Doppler as the single source of configuration:
- `DOPPLER_PROJECT=card-fraud-transaction-management`
- `DOPPLER_CONFIG=local`

In non-local environments:
- `DOPPLER_CONFIG=test` (points to Neon test branch)
- `DOPPLER_CONFIG=prod` (points to Neon production branch)

### Database environments
- Local: Docker Postgres
- Test/prod: Neon Postgres branches (separate branches per environment)

### Sanity checks
- Postgres is reachable via `DATABASE_URL`
- MinIO is reachable if/when archival is enabled (see `docs/16-retention-and-archival.md`)
