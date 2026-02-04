# Observability & Operations Plan

## Logging
- Structured JSON logs.
- Always include: `transaction_id` (when known), `trace_id`, ingestion source (kafka/http), and outcome (persisted/no-op/dlq).
- Avoid logging full `raw_payload` in production.

## Metrics
### Ingestion
- Kafka lag (per partition)
- Records processed/sec
- Processing latency (p50/p95/p99)
- DB errors/sec
- DLQ count/sec

### API
- Request rate
- Error rate
- Latency (p95)

### DB
- Insert/upsert latency
- Connection pool saturation

## Tracing
- Propagate `trace_id` from event to logs and (if supported) distributed tracing.
- Standardize on OpenTelemetry for tracing and metrics export.

## Health endpoints (plan-level)
- Liveness: process up.
- Readiness: DB connectivity; (Kafka connectivity optional).

Health response shape (recommended):
```json
{
	"status": "healthy|degraded|unhealthy",
	"components": {
		"database": { "status": "healthy", "latency_ms": 12 },
		"kafka": { "status": "healthy", "lag": 0 }
	}
}
```

## Runbooks
- DLQ triage steps.
- Replay/backfill procedure.
- Index maintenance / slow query troubleshooting.
- Incident response for ingestion backlog.

## SLO suggestions (to confirm)
- Ingestion: 99% of events persisted within X seconds.
- Query API: p95 < Y ms for list endpoints within last 7 days.

## TODO checklist
- Confirm observability stack (Prometheus/Grafana, Azure Monitor, Datadog, etc.).
- Define log redaction rules.
- Define alert thresholds for lag and DLQ spikes.
