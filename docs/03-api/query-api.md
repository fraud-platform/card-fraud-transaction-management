# Query API Plan

## Purpose
Provide read access for dashboards, investigations, and reporting.

## Design principles
- Read-only endpoints.
- Pagination required for list endpoints.
- Time-range filters should be first-class.
- Avoid exposing `raw_payload` by default.

## MVP endpoint candidates
1. Transactions list
- `GET /v1/transactions`
  - filters: time range, decision, merchant_id, card_id, country, amount min/max
  - sort: occurred_at desc
  - pagination: cursor or offset/limit

2. Transaction detail
- `GET /v1/transactions/{transaction_id}`
  - returns transaction fields + rule matches

3. Declines over time
- `GET /v1/metrics/declines`
  - grouped by hour/day
  - filters: merchant_id/country

4. Rule effectiveness
- `GET /v1/metrics/rules`
  - counts by rule_id over time range

(Exact endpoints should be aligned to the portal’s needs.)

## Data shaping
- For list endpoints: omit `raw_payload` and large nested arrays.
- For detail endpoint: include rule matches; optionally include raw_payload behind a flag/permission.

## Performance plan
- Use indexes described in storage plan.
- Favor bounded time ranges.
- Apply server-side limits for max range and page size:
  - Default page size: 50
  - Max page size: 500
  - Max time range without pagination: 7 days

## TODO checklist
- Confirm required portal screens/workflows to finalize endpoints.
- Decide pagination scheme (cursor recommended).
- Decide authorization model and field-level filtering for raw_payload.
- Define OpenAPI spec plan for all endpoints.
