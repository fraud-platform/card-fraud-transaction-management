# OpenAPI Outline (Plan)

This document defines the planned HTTP surface area (no implementation).

## Principles
- Read API is primary for portal/dashboards.
- Ingestion API is temporary and should be disable-able in prod.
- Avoid exposing `raw_payload` by default.

## Endpoints (MVP)

### Ingestion (temporary)
- `POST /v1/decision-events`
  - Request: Decision Event v1
  - Response: Accepted + idempotency result
  - Errors: validation failures, PAN detected

Non-goal (MVP):
- No bulk/batch ingestion endpoint. Backfills should use Kafka replay/tooling.

### Queries
- `GET /v1/transactions`
  - Filters: time range, decision, merchant_id, card_id, country, amount min/max
  - Sort: occurred_at desc
  - Pagination: cursor recommended

- `GET /v1/transactions/{transaction_id}`
  - Returns: transaction + rule matches

### Health
- `GET /health/live`
- `GET /health/ready`

## Pagination (cursor recommended)
Cursor response fields (plan):
```json
{
  "items": [ ... ],
  "next_cursor": "...",
  "page_size": 100
}
```

Cursor construction guidance:
- Prefer `(occurred_at, transaction_id)` tuple to avoid duplicates/skips.

Default limits (must be enforced):
- Default page size: 50
- Max page size: 500
- Max time range without pagination: 7 days

## API versioning & deprecation (policy)
- Versioned via URL prefix (`/v1/...`).
- Backward-compatible changes allowed within a major version (additive fields, new endpoints).
- Breaking changes require a new major version (`/v2/...`).
- Deprecations should provide a migration path and a published timeline.

## Field exposure policy
- `raw_payload` should be omitted from list endpoints.
- `raw_payload` on detail endpoint should be gated by config/role.

## TODO checklist
- Confirm final portal-driven query shapes.
- Decide cursor encoding format (opaque base64).
- Decide whether to include `/v1/metrics/*` in MVP.
