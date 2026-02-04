# Configuration Reference

**Consolidated from:**
- `docs/15-config-reference.md` (plan-level)
- `docs/02-development/technical-04-configuration-schema.md` (implementation-level)

**Status:** DRAFT
**Last Updated:** 2026-01-18

---

## 1. Core Configuration

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `ENV` | string | Yes | - | Environment: `dev`, `staging`, `prod` |
| `LOG_LEVEL` | string | No | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `HTTP_PORT` | integer | No | `8080` | HTTP server port |
| `HOST` | string | No | `0.0.0.0` | Host to bind server |
| `WORKERS` | integer | No | `4` | Number of Gunicorn workers |
| `DEBUG` | boolean | No | `false` | Enable debug mode (disables production guards) |
| `API_PREFIX` | string | No | `/v1` | URL prefix for all API routes |

---

## 2. Database (PostgreSQL 18)

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `DATABASE_URL` | string | Yes | - | PostgreSQL connection string |
| `DATABASE_HOST` | string | Yes | - | PostgreSQL hostname |
| `DATABASE_PORT` | integer | Yes | - | PostgreSQL port |
| `DATABASE_NAME` | string | Yes | - | Database name |
| `DATABASE_USER` | string | Yes | - | Database username |
| `DATABASE_PASSWORD` | secret | Yes | - | Database password |
| `DB_POOL_SIZE` | integer | No | `10` | Minimum pool size |
| `DB_POOL_MAX_OVERFLOW` | integer | No | `20` | Maximum overflow connections |
| `DB_POOL_TIMEOUT` | integer | No | `30` | Pool timeout in seconds |
| `DB_POOL_RECYCLE` | integer | No | `1800` | Connection recycle in seconds |
| `DATABASE_ECHO` | boolean | No | `false` | Log SQL statements |
| `DATABASE_REQUIRE_SSL` | boolean | No | `true` | Require SSL for connections |

### Database Provider Notes

| Environment | Provider | Notes |
|-------------|----------|-------|
| Local | Docker Postgres | Use Docker Compose |
| Test | Neon | Use environment branch |
| Prod | Neon | Use production branch |

---

## 3. Kafka

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | string | Yes | - | Kafka broker addresses (comma-separated) |
| `KAFKA_TOPIC` | string | No | `fraud.card.decisions.v1` | Decision events topic |
| `KAFKA_CONSUMER_GROUP` | string | Yes | - | Consumer group ID |
| `KAFKA_ENABLE` | boolean | No | `true` | Enable Kafka consumer |
| `KAFKA_DLQ_TOPIC` | string | No | `fraud.card.decisions.v1.dlq.<env>` | Dead letter queue topic |
| `KAFKA_AUTO_OFFSET_RESET` | string | No | `earliest` | Offset reset policy |
| `KAFKA_ENABLE_AUTO_COMMIT` | boolean | No | `true` | Auto-commit offsets |
| `KAFKA_AUTO_COMMIT_INTERVAL_MS` | integer | No | `5000` | Auto-commit interval |
| `KAFKA_SESSION_TIMEOUT_MS` | integer | No | `30000` | Consumer session timeout |
| `KAFKA_HEARTBEAT_INTERVAL_MS` | integer | No | `10000` | Heartbeat interval |
| `KAFKA_MAX_POLL_RECORDS` | integer | No | `500` | Maximum records per poll |
| `KAFKA_CONSUMER_TIMEOUT_MS` | integer | No | `300000` | Consumer timeout (5 min) |
| `KAFKA_SECURITY_PROTOCOL` | string | No | `SASL_SSL` | Security protocol |
| `KAFKA_SASL_MECHANISM` | string | No | `SCRAM-SHA-512` | SASL mechanism |
| `KAFKA_SASL_USERNAME` | secret | Yes | - | Kafka SASL username |
| `KAFKA_SASL_PASSWORD` | secret | Yes | - | Kafka SASL password |

---

## 4. Auth0 (Authentication)

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `AUTH0_DOMAIN` | string | Yes | - | Auth0 domain |
| `AUTH0_AUDIENCE` | string | Yes | - | API audience |
| `AUTH0_CLIENT_ID` | string | Yes | - | Auth0 client ID |
| `AUTH0_CLIENT_SECRET` | secret | Yes | - | Auth0 client secret |
| `AUTH0_ALGORITHMS` | string | No | `RS256` | JWT algorithms |
| `AUTH0_ISSUER` | string | No | - | Token issuer URL |
| `AUTH0_JWKS_CACHE_TTL` | integer | No | `600` | JWKS cache TTL in seconds |

### Auth0 Management (for Bootstrap)

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| `AUTH0_MGMT_DOMAIN` | string | Yes | Auth0 management domain |
| `AUTH0_MGMT_CLIENT_ID` | string | Yes | Management M2M client ID |
| `AUTH0_MGMT_CLIENT_SECRET` | secret | Yes | Management M2M secret |

---

## 5. Object Storage (S3/MinIO)

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `S3_ENDPOINT_URL` | string | Yes | - | S3 endpoint URL |
| `S3_REGION` | string | Yes | - | AWS region |
| `S3_BUCKET_NAME` | string | Yes | - | S3 bucket name |
| `S3_ACCESS_KEY_ID` | secret | Yes | - | S3 access key |
| `S3_SECRET_ACCESS_KEY` | secret | Yes | - | S3 secret key |
| `S3_USE_PATH_STYLE` | boolean | No | `true` | Use path-style addressing |
| `S3_SIGNATURE_VERSION` | string | No | `s3v4` | S3 signature version |

---

## 6. Feature Flags

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ENABLE_HTTP_INGESTION` | boolean | `false` (prod), `true` (dev) | Enable HTTP ingestion endpoint |
| `ENABLE_RAW_PAYLOAD` | boolean | `false` | Enable raw payload persistence (prod requires approval) |
| `FEATURE_ENABLE_RULE_ENRICHMENT` | boolean | `true` | Enable rule metadata enrichment |
| `FEATURE_REQUIRE_ANALYST_APPROVAL` | boolean | `false` | Require analyst review before resolution |

---

## 7. Card Identifier Handling

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CARD_IDENTIFIER_MODE` | enum | `TOKEN_ONLY` | `TOKEN_ONLY` or `TOKEN_PLUS_LAST4` |

**Behavior:**
- `TOKEN_ONLY`: never persist `card_last4` even if present
- `TOKEN_PLUS_LAST4`: require and persist `card_last4`

---

## 8. PAN Detection (PCI Compliance)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `PAN_DETECTION_ENABLE` | boolean | `true` | Enable PAN detection |
| `PAN_DETECTION_STRICT_TOKEN_PREFIX` | string | `tok_` | Required token prefix |

**Behavior:** If PAN-like data is detected, reject (HTTP) or DLQ (Kafka) and never persist.

---

## 9. Raw Payload Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `RAW_PAYLOAD_ALLOWLIST` | string | - | Comma-separated allowlist of fields |
| `RAW_PAYLOAD_MAX_BYTES` | integer | `65536` | Max persisted raw payload size (64KB) |

**Recommended default allowlist:**
```
transaction_id,amount,currency,country,merchant_id,mcc,decision_reason
```

---

## 10. Payload Limits

| Variable | Default | Description |
|----------|---------|-------------|
| `HTTP_MAX_BODY_BYTES` | `1048576` | Max HTTP request body (1MB) |
| `MATCHED_RULES_MAX_ITEMS` | `100` | Max matched_rules array length |

---

## 11. Doppler (Secrets Management)

| Variable | Description |
|----------|-------------|
| `DOPPLER_PROJECT` | Project name (default: `card-fraud-transaction-management`) |
| `DOPPLER_CONFIG` | Config name: `local`, `test`, `prod` |

### Environment Config Mapping

| Config | Use Case |
|--------|----------|
| `local` | Local development |
| `test` | CI/testing (Neon test branch) |
| `prod` | Production (Neon production branch) |

---

## 12. Observability (OpenTelemetry)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OTEL_ENABLE` | boolean | `true` | Enable OpenTelemetry |
| `OTEL_SERVICE_NAME` | string | `card-fraud-transaction-management` | Service name |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | string | - | OTLP exporter endpoint |
| `OTEL_TRACES_SAMPLER` | string | `always_on` | Trace sampler |
| `OTEL_METRICS_EXPORT_INTERVAL` | integer | `60000` | Metrics export interval (ms) |
| `OTEL_LOG_RECORD_FORMAT` | string | `json` | Log record format |

### Datadog (Optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `DATADOG_AGENT_HOST` | - | Datadog agent host |
| `DATADOG_TRACE_AGENT_PORT` | `8126` | Datadog trace agent port |

---

## 13. Rule Management Service

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `RULE_MANAGEMENT_URL` | string | Yes | Rule management service base URL |
| `RULE_MANAGEMENT_TIMEOUT` | integer | `30` | HTTP timeout in seconds |
| `RULE_MANAGEMENT_RETRIES` | integer | `3` | Number of retry attempts |
| `RULE_CACHE_TTL_SECONDS` | integer | `300` | Rule metadata cache TTL (5 min) |
| `RULE_CACHE_MAX_SIZE` | integer | `10000` | Maximum cached rules |

---

## 14. Configuration Classes (Pydantic)

```python
from pydantic import BaseModel, Field, SecretStr
from typing import Optional
from enum import Enum

class AppEnvironment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class CardIdentifierMode(str, Enum):
    TOKEN_ONLY = "TOKEN_ONLY"
    TOKEN_PLUS_LAST4 = "TOKEN_PLUS_LAST4"

class DatabaseConfig(BaseModel):
    host: str
    port: int
    name: str
    user: str
    password: SecretStr
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 1800
    echo: bool = False
    require_ssl: bool = True

    @property
    def url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

class KafkaConfig(BaseModel):
    bootstrap_servers: str
    consumer_group_id: str
    topic_decisions: str = "fraud.card.decisions.v1"
    topic_dlq: Optional[str] = None
    security_protocol: str = "SASL_SSL"
    sasl_mechanism: str = "SCRAM-SHA-512"
    sasl_username: str
    sasl_password: SecretStr

class Auth0Config(BaseModel):
    domain: str
    audience: str
    client_id: str
    client_secret: SecretStr
    algorithms: list[str] = ["RS256"]
    jwks_cache_ttl: int = 600

class ObservabilityConfig(BaseModel):
    service_name: str = "card-fraud-transaction-management"
    otlp_endpoint: str
    traces_sampler: str = "always_on"
    metrics_export_interval: int = 60000
    log_record_format: str = "json"

class Settings(BaseModel):
    env: AppEnvironment
    log_level: LogLevel = LogLevel.INFO
    http_port: int = 8080
    database: DatabaseConfig
    kafka: KafkaConfig
    auth0: Auth0Config
    observability: ObservabilityConfig
    card_identifier_mode: CardIdentifierMode = CardIdentifierMode.TOKEN_ONLY
    pan_detection_enabled: bool = True
    raw_payload_allowlist: str = "transaction_id,amount,currency,country,merchant_id,mcc,decision_reason"
```

---

## 15. Environment-Specific Configurations

### Local Development

```bash
# Doppler local config
ENV=development
LOG_LEVEL=DEBUG
HTTP_PORT=8080

DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/fraud_tm

KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC=fraud.card.decisions.v1
KAFKA_CONSUMER_GROUP=card-fraud-transaction-management.local
KAFKA_SASL_USERNAME=
KAFKA_SASL_PASSWORD=

AUTH0_DOMAIN=localhost
AUTH0_AUDIENCE=http://localhost:8080
AUTH0_CLIENT_ID=local-client
AUTH0_CLIENT_SECRET=local-secret

S3_ENDPOINT_URL=http://localhost:9000
S3_REGION=us-east-1
S3_BUCKET_NAME=fraud-tm
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=minioadmin

OTEL_SERVICE_NAME=card-fraud-transaction-management-local
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

### Docker Compose (Local)

```yaml
services:
  postgres:
    image: postgres:18
    environment:
      POSTGRES_DB: fraud_tm
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports:
      - "9000:9000"
      - "9001:9001"
```

---

## 16. Validation

### Startup Validation

```python
from pydantic import ValidationError

def validate_configuration():
    """Validate configuration at startup."""
    try:
        settings = Settings.from_env()
    except ValidationError as e:
        raise RuntimeError(f"Configuration validation failed: {e}")

    if settings.env == "production":
        if settings.debug:
            raise RuntimeError("DEBUG must be false in production")
        if not settings.database.require_ssl:
            raise RuntimeError("SSL is required in production")

    return settings
```

---

## 17. Migration Checklist

- [ ] Confirm org standard naming for env vars
- [ ] Confirm Doppler project/config naming and access model
- [ ] Decide DLQ payload policy for non-PAN errors
- [ ] Verify all required secrets are present at startup
