# Kafka (Redpanda) Local Setup Guide

This guide covers setting up Kafka locally using **Redpanda** - a Kafka-compatible streaming platform that's free and easy to run.

## Why Redpanda?

| Feature | Redpanda | Apache Kafka |
|---------|----------|--------------|
| License | BSL (free for dev) | Apache 2.0 |
| Setup | Single container | Requires Zookeeper |
| Resource usage | ~500MB RAM | ~2GB RAM |
| Schema Registry | Built-in | Confluent Schema Registry |
| Console UI | Built-in | Kafkacat/Conduktor |

## Quick Start

```powershell
# 1. Start Kafka (Redpanda)
uv run kafka-local-up

# 2. Create required topics
python scripts/setup_kafka.py create-topics

# 3. Verify health
python scripts/setup_kafka.py health
```

## Access Points

| Service | URL | Purpose |
|---------|-----|---------|
| Kafka API | `localhost:9092` | Kafka clients connect here |
| Console UI | http://localhost:8083 | Web UI for topic management |
| Schema Registry | http://localhost:8081 | JSON Schema storage |
| Admin API | http://localhost:8082 | Cluster management |

## Available Commands

```powershell
# Start/Stop Kafka only
uv run kafka-local-up
uv run kafka-local-down

# Topic management
python scripts/setup_kafka.py create-topics   # Create fraud.card.decisions.v1
python scripts/setup_kafka.py list-topics     # List all topics
python scripts/setup_kafka.py produce         # Produce test message
python scripts/setup_kafka.py consume         # Consume messages
python scripts/setup_kafka.py reset           # Delete and recreate topics
python scripts/setup_kafka.py health          # Check cluster health
```

## Topic Naming Convention

| Topic | Purpose |
|-------|---------|
| `fraud.card.decisions.v1` | Production decision events |
| `fraud.card.decisions.v1.dlq.local` | Dead letter queue (local/dev) |
| `fraud.card.decisions.v1.dlq.test` | Dead letter queue (test) |
| `fraud.card.decisions.v1.dlq.prod` | Dead letter queue (prod) |

## Consumer Groups

| Environment | Consumer Group |
|-------------|----------------|
| Local | `card-fraud-transaction-management.local` |
| Test | `card-fraud-transaction-management.test` |
| Prod | `card-fraud-transaction-management.prod` |

## Docker Compose Configuration

Redpanda is included in `docker-compose.local.yml`:

```yaml
services:
  redpanda:
    image: redpandadata/redpanda:v24.3.11
    command: >
      redpanda start
      --overprovisioned
      --smp 1
      --memory 1G
      --node-id 0
      --check=false
      --kafka-addr PLAINTEXT://0.0.0.0:9092
      --rpc-addr 0.0.0.0:33145
      --advertise-kafka-addr localhost:9092
    ports:
      - "9092:9092"   # Kafka API
      - "8081:8081"   # Schema Registry
      - "8082:8082"   # Admin API
    volumes:
      - redpanda_data:/var/lib/redpanda/data

  redpanda-console:
    image: redpandadata/console:v2.3.4
    ports:
      - "8083:8080"
    environment:
      KAFKA_BROKERS: redpanda:9092
      CONNECTORS_ENABLED: "false"
    depends_on:
      - redpanda

volumes:
  redpanda_data:
```

## Environment Variables

```bash
# Required for Kafka consumer/producer
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC=fraud.card.decisions.v1
KAFKA_DLQ_TOPIC=fraud.card.decisions.v1.dlq.local
KAFKA_CONSUMER_GROUP=card-fraud-transaction-management.local
KAFKA_ENABLE=true
```

## Testing with the Console UI

1. Open http://localhost:8083
2. Click "Topics" in the sidebar
3. You should see:
   - `fraud.card.decisions.v1`
   - `fraud.card.decisions.v1.dlq.local`
4. Click on a topic to view messages

## Producing Test Messages

```powershell
# Produce a test decision event
python scripts/setup_kafka.py produce

# Output example:
# Producing to topic: fraud.card.decisions.v1
# {
#   "event_version": "1.0",
#   "transaction_id": "txn_local_1737225600",
#   ...
# }
# Result: Success
```

## Consuming Messages

```powershell
# Consume up to 10 messages
python scripts/setup_kafka.py consume

# Output example:
# Consuming from: fraud.card.decisions.v1 (Ctrl+C to stop)
# {
#   "topic": "fraud.card.decisions.v1",
#   "key": "txn_local_1737225600",
#   "value": {...},
#   "partition": 0,
#   "offset": 0
# }
```

## Troubleshooting

### Kafka not starting

```powershell
# Check container logs
docker compose -f docker-compose.local.yml logs redpanda

# Common issues:
# - Port 9092 already in use (another Kafka instance)
# - Not enough memory (Redpanda needs ~1GB)
```

### Consumer fails to connect

```powershell
# Verify Kafka is running
python scripts/setup_kafka.py health

# Check if topic exists
python scripts/setup_kafka.py list-topics
```

### Messages not appearing

```powershell
# Reset topics (deletes all data)
python scripts/setup_kafka.py reset

# Recreate topics
python scripts/setup_kafka.py create-topics
```

## Data Isolation

**Important:** This project's Kafka resources are isolated:

| Resource | This Project | Other Projects |
|----------|--------------|----------------|
| Topics | `fraud.card.decisions.v1*` | Different topic names |
| Consumer Groups | `card-fraud-transaction-management.*` | Different group names |
| Docker Volume | `card_fraud_transaction_mgmt_redpanda_data` | Separate volume |

Reset commands (`kafka-local-down -v`) only affect THIS project's data.

## Next Steps

1. **Add Kafka consumer** to your FastAPI app (see `app/ingestion/kafka_consumer.py`)
2. **Configure production Kafka** credentials in Doppler
3. **Set up schema registry** for event schema evolution
