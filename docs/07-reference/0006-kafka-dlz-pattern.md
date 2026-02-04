# ADR-006: Kafka Consumer with Dead Letter Queue Pattern

**Status:** Accepted

**Date:** 2026-01-27

**Context:**

The Card Fraud Transaction Management service ingests decision events via Kafka in production. Events must be reliably processed with guarantees:

1. **No data loss**: Every valid event must be persisted
2. **Idempotency**: Duplicate events (retries) should not create duplicates
3. **Error handling**: Invalid events should not block consumption
4. **Observability**: Failed events must be inspectable for troubleshooting

**Key Challenges:**
- Events may be malformed (schema validation failures)
- Database may be temporarily unavailable
- Business logic errors should not stop the consumer
- Need to replay failed events after fixes

**Decision:**

Implement Kafka consumer with Dead Letter Queue (DLQ) pattern:

1. **Main Topic**: `fraud.card.decisions.v1` - Valid events for processing
2. **DLQ Topic**: `fraud.card.decisions.v1.dlq.{env}` - Failed events for inspection
3. **Consumer Group**: `card-fraud-transaction-management.{env}`
4. **Commit Strategy**: Offset commit AFTER successful database write

**Technical Implementation:**
```python
class KafkaConsumerService:
    async def process_messages(self):
        async for message in self.consumer:
            try:
                # 1. Parse and validate
                event = DecisionEventCreate.model_validate_json(message.value)

                # 2. Store to database (idempotent upsert)
                await self.ingestion_service.ingest_event(event)

                # 3. Commit offset ONLY after success
                await self.consumer.commit()

            except ValidationError as e:
                # Schema error - send to DLQ immediately
                await self.send_to_dlq(message, reason="validation_error", error=str(e))
                await self.consumer.commit()  # Skip bad message

            except DatabaseError as e:
                # Transient error - retry with backoff
                await self.retry_with_backoff(message, error=e)

            except Exception as e:
                # Unexpected error - send to DLQ
                await self.send_to_dlq(message, reason="unexpected_error", error=str(e))
                await self.consumer.commit()
```

**Topic Naming Convention:**
```
Main:   fraud.card.decisions.v1
DLQ:    fraud.card.decisions.v1.dlq.local
DLQ:    fraud.card.decisions.v1.dlq.dev
DLQ:    fraud.card.decisions.v1.dlq.prod
```

**Consumer Group Naming:**
```
Local:  card-fraud-transaction-management.local
Dev:    card-fraud-transaction-management.dev
Prod:   card-fraud-transaction-management.prod
```

**DLQ Message Envelope:**
```json
{
  "original_message": { /* raw Kafka message */ },
  "error": {
    "type": "ValidationError",
    "message": "Field 'transaction_id' is required",
    "timestamp": "2026-01-27T10:30:00Z"
  },
  "metadata": {
    "original_topic": "fraud.card.decisions.v1",
    "original_partition": 0,
    "original_offset": 12345,
    "consumer_group": "card-fraud-transaction-management.prod"
  }
}
```

**Consequences:**

**Positive:**
- Invalid events don't block consumption
- Failed events are preserved for replay
- Full observability into failure patterns
- Consumer auto-recovers from transient errors
- Idempotency ensures safe replay from DLQ

**Negative:**
- Additional operational complexity (DLQ monitoring)
- Need DLQ triage runbook
- Replayed messages may still fail (need investigation)
- DLQ can grow if not monitored

**Error Categories:**

| Error Type | Retry? | DLQ? | Action |
|------------|--------|-----|--------|
| Validation Error | No | Yes | Schema mismatch, manual fix needed |
| Database Unavailable | Yes | No | Transient, auto-retry |
| PAN Detected | No | No | Security event, sink message |
| Business Logic Error | No | Yes | Code bug, fix and replay |

**Idempotency Requirements:**
```sql
-- Must support safe replay
INSERT INTO fraud_gov.transactions (...) VALUES (...)
ON CONFLICT (transaction_id, evaluation_type, transaction_timestamp) DO UPDATE SET
    -- Only update metadata, not business fields
    raw_payload = EXCLUDED.raw_payload,
    updated_at = NOW();
```

**Monitoring:**
```python
# Metrics to track
- kafka.consumer.lag (consumer lag)
- kafka.dlq.messages (DLQ message count)
- kafka.dlq.errors_by_type (error type breakdown)
- ingestion.events_processed (success count)
- ingestion.events_failed (failure count)
```

**Alternatives Considered:**

1. **Stop consumer on any error**
   - Rejected: Single bad message blocks entire pipeline

2. **Skip errors without DLQ**
   - Rejected: Lost data, cannot troubleshoot or replay

3. **Retry indefinitely**
   - Rejected: Permanent errors never resolve, consumer stuck

4. **Separate consumer per error type**
   - Rejected: Over-engineering, complex coordination

**Runbook Reference:**

For DLQ triage and replay procedures, see:
- [docs/06-operations/dlq-triage.md](../06-operations/dlq-triage.md)
- [docs/06-operations/replay-backfill.md](../06-operations/replay-backfill.md)

**Related:**
- [docs/05-ingestion.md](../03-api/ingestion.md)
- [docs/13-error-and-dlq-model.md](../06-operations/error-and-dlq-model.md)
- [app/ingestion/kafka_consumer.py](../../app/ingestion/kafka_consumer.py)
