# Retention & Archival Plan

## Purpose
Prevent unbounded growth of the `transactions` and `transaction_rule_matches` tables while preserving the ability to investigate and audit historical events.

This is **not required for v1 MVP implementation**, but should be addressed before production at scale.

## Data categories
- **Hot operational data**: recent transactions used by dashboards/worklists.
- **Warm analytical data**: historical data still queried occasionally.
- **Cold archive**: long-term retention in object storage.

## Recommended retention targets (initial)
- Hot storage: 30–90 days (portal-driven; confirm requirements)
- Warm storage: 6–12 months (optional)
- Cold archive: multi-year (optional; compliance-driven)

## Partitioning strategy (PostgreSQL)
Recommended: partition `transactions` by `occurred_at` monthly.

Notes:
- Partitioning is driven by **business time** (`occurred_at`), not ingestion time.
- Ensure query predicates include `occurred_at` to leverage partition pruning.

`transaction_rule_matches` options:
- Keep unpartitioned and rely on FK-less joins + indexes, or
- Partition by `matched_at` monthly, or
- Partition by `transaction_id` hash (less common).

Prefer keeping `transaction_rule_matches` aligned with `transactions` (either via `occurred_at` denormalization or by querying via `transaction_id` joins).

## Archive process (plan)
- A scheduled job exports partitions older than the hot window to object storage.
- Export format: newline-delimited JSON or Parquet (preferred for analytics).
- Archive must be **redacted** consistently with `raw_payload` policy.

Implementation note:
- Local development can use MinIO (already used in rule management) as the archive target.

## Deletion requests (GDPR/CCPA)
Policy decision required:
- **Hard delete**: delete rows and any rule matches.
- **Soft delete**: set `deleted_at` and filter from query endpoints.

If soft-delete is chosen, add `deleted_at TIMESTAMP NULL` to both tables and implement query filters.

## Querying archived data
Options:
- Separate offline query tool (Athena/BigQuery/Spark)
- Restore selected partitions into a scratch DB for investigations

## TODO checklist
- Confirm retention requirements with stakeholders.
- Decide partitioning approach and migration plan.
- Decide archive storage target and format.
- Decide hard-delete vs soft-delete for compliance.
