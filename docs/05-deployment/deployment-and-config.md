# Deployment & Configuration Plan

## Packaging
- Container image recommended.
- Single deployable service (API + consumer) or split into two processes.

## Environment infrastructure (aligned with existing rule-management setup)

- **Local development**:
  - PostgreSQL via local Docker (reuse the existing local Postgres container setup used by rule management).
  - MinIO via local Docker (reuse the existing MinIO container setup used by rule management).
  - Secrets/config via Doppler using a **local** config.

- **Test & production**:
  - PostgreSQL via Neon (use environment branches, e.g., `test` branch and `production` branch).
  - Object storage compatible with S3 semantics (MinIO locally; cloud S3-equivalent in non-local environments if/when archival is enabled).
  - Secrets/config via Doppler using **test** and **prod** configs.

## Deployment model options

Locked decision: **single deployable**
- One service process that runs:
  - FastAPI HTTP server (query endpoints + optional HTTP ingestion)
  - Kafka consumer loop

Future option (not now): split into `ingestion-worker` and `query-api` if scaling demands it.

## Configuration
Use environment variables / config files for:
- DB connection string
- Kafka bootstrap servers + topic + group id
- HTTP port
- Feature flags (enable_http_ingestion, enable_raw_payload)
- Redaction policy for raw_payload

Optional (data classification mode, not masking logic):
- `card_identifier_mode`: `TOKEN_ONLY` (default) or `TOKEN_PLUS_LAST4`

### Enforcement (must be implemented in ingestion validation)

Because `card_identifier_mode` is configuration (not part of the event), this rule is enforced by the service at ingest time:
- `TOKEN_ONLY`:
  - Accept events whether or not `transaction.card_last4` is present, but **do not persist it** (drop it during normalization).
  - Do not drop `transaction.card_network` (it is not sensitive and is useful for analytics).
- `TOKEN_PLUS_LAST4`:
  - Require `transaction.card_last4` to be present and match `^[0-9]{4}$`.
  - Persist `card_last4` into `transactions.card_last4`.

Rationale: prevents accidental leakage and keeps prod default PCI-safe.

## Secrets
- Doppler is the standard secrets/config manager (already used by rule management).
- Never commit secrets.

## DB migrations in deploy
- Run migrations as a pre-deploy step or an init container/job.
- Ensure migrations run exactly once per deploy.

## Rollout strategy
- Blue/green or rolling deployments.
- For consumer: consider cooperative rebalancing and graceful shutdown.

## TODO checklist
- Confirm hosting platform and baseline deployment template.
- Decide single vs split deployables.
- Define config naming conventions.
- Define migration execution method.
