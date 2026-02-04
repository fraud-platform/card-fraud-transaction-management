# Card Fraud Transaction Management API - UI Integration Guide

This document provides information for UI teams integrating with the Card Fraud Transaction Management API.

## Overview

The **Card Fraud Transaction Management** service is a persistence layer for fraud decision events. It stores transaction data and rule matches with idempotency guarantees.

### What This Service Does

- **Ingests** fraud decision events from HTTP (dev/testing) and Kafka (production)
- **Stores** transactions with PCI-compliant card tokenization (never stores raw PANs)
- **Provides** query API for fraud analysis and reporting
- **Enables** replay/backfill for data recovery

### What This Service Does NOT Do

- Does NOT evaluate fraud rules (handled by rule-management service)
- Does NOT perform real-time fraud detection (handled by runtime engine)
- Does NOT compute velocity checks (handled by Redis in runtime)

## Base URL

- **Development**: `http://localhost:8080`
- **Test**: Contact DevOps for test environment URL
- **Production**: Contact DevOps for production environment URL

## Authentication

All API endpoints require JWT Bearer token authentication via Auth0.

### Getting a Token

1. **For M2M (service-to-service)**: Use Client Credentials flow with Auth0
2. **For user-facing apps**: Use Authorization Code flow with Auth0

### Required Scopes

| Endpoint | Required Scope |
|----------|---------------|
| `POST /v1/decision-events` | `txn:write` or `txn:ingest` |
| `GET /v1/transactions` | `txn:view` |
| `GET /v1/transactions/{id}` | `txn:view` |
| `GET /v1/metrics` | `txn:view` or `txn:metrics` |

### Auth0 Configuration

Contact DevOps for Auth0 client credentials for your environment.

## API Endpoints

### 1. Ingest Decision Event

**Purpose**: Submit a fraud decision event for processing and storage.

```
POST /v1/decision-events
Authorization: Bearer <token>
Content-Type: application/json
X-Trace-ID: <optional-trace-id>
```

**Request Body**:

```json
{
  "transaction_id": "txn_12345",
  "event_version": "1.0",
  "occurred_at": "2024-01-15T10:30:00Z",
  "produced_at": "2024-01-15T10:30:01Z",
  "transaction": {
    "card_id": "tok_visa_xxxx",
    "card_last4": "4242",
    "card_network": "VISA",
    "amount": "99.99",
    "currency": "USD",
    "country": "US",
    "merchant_id": "merchant_001",
    "mcc": "5411",
    "ip_address": "192.168.1.1"
  },
  "decision": "APPROVE",
  "decision_reason": "DEFAULT_ALLOW",
  "matched_rules": [
    {
      "rule_id": "rule_001",
      "rule_version": 1,
      "rule_name": "Velocity Check",
      "rule_type": "velocity",
      "priority": 10,
      "matched_at": "2024-01-15T10:30:00Z",
      "match_reason_text": "Exceeded velocity threshold"
    }
  ],
  "raw_payload": {
    "user_agent": "Mozilla/5.0",
    "ip_country": "US"
  }
}
```

**Card ID Format**:
- Must use tokenized format: `tok_<identifier>` (e.g., `tok_visa_1234`)
- Raw PANs will be rejected with 422 status
- For testing PAN detection, use format: `pan_<16-digit-number>`

**Decision Values**:
- `APPROVE` - Transaction was approved
- `DECLINE` - Transaction was declined
- `POSTAUTH` - Post-authorization review

**Decision Reason Values**:
- `DEFAULT_ALLOW` - No rules matched, default to allow
- `RULE_MATCH` - Declined due to rule match
- `VELOCITY_MATCH` - Declined due to velocity check
- `SYSTEM_DECLINE` - System-initiated decline
- `MANUAL_REVIEW` - Sent to manual review

**Card Network Values**:
- `VISA` - Visa card
- `MASTERCARD` - Mastercard
- `AMEX` - American Express
- `DISCOVER` - Discover
- `OTHER` - Other network

**Response** (202 Accepted):

```json
{
  "status": "accepted",
  "transaction_id": "01929xyz...",  // UUIDv7
  "ingestion_source": "HTTP",
  "ingested_at": "2024-01-15T10:30:02Z"
}
```

**Idempotency**: Duplicate requests with the same `transaction_id` will update metadata only (trace_id, raw_payload, ingestion_source) without modifying business fields.

**Errors**:
- `400 Bad Request` - Validation error
- `401 Unauthorized` - Missing/invalid token
- `403 Forbidden` - Insufficient permissions
- `409 Conflict` - Transaction exists with conflicting data
- `422 Unprocessable Entity` - PAN pattern detected (PCI violation)

### 2. List Transactions

**Purpose**: Query transactions with filtering and pagination.

```
GET /v1/transactions?page_size=50&card_id=tok_visa_xxxx&decision=APPROVE
Authorization: Bearer <token>
```

**Query Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `page_size` | int | Items per page (1-500, default: 50) |
| `card_id` | string | Filter by card token |
| `decision` | string | Filter by decision (APPROVE/DECLINE/POSTAUTH) |
| `country` | string | Filter by country code (not persisted) |
| `merchant_id` | string | Filter by merchant ID |
| `from_date` | datetime | Filter from date (ISO 8601) |
| `to_date` | datetime | Filter to date (ISO 8601) |
| `review_status` | string | Filter by review status (PENDING/IN_REVIEW/ESCALATED/RESOLVED/CLOSED) |
| `risk_level` | string | Filter by risk level (LOW/MEDIUM/HIGH/CRITICAL) |
| `case_id` | string | Filter by case ID |
| `rule_id` | string | **NEW** - Filter by rule ID (matched rules) |
| `ruleset_id` | string | **NEW** - Filter by ruleset ID |
| `assigned_to_me` | bool | **NEW** - Filter transactions assigned to current user |
| `min_amount` | float | Minimum transaction amount |
| `max_amount` | float | Maximum transaction amount |
| `cursor` | string | Pagination cursor from previous response |

**Response** (200 OK):

```json
{
  "items": [
    {
      "transaction_id": "01929xyz...",
      "card_id": "tok_visa_xxxx",
      "card_last4": "4242",
      "card_network": "VISA",
      "amount": 99.99,
      "currency": "USD",
      "merchant_id": "merchant_001",
      "mcc": "5411",
      "decision": "APPROVE",
      "decision_reason": "DEFAULT_ALLOW",
      "decision_score": null,
      "ruleset_id": null,
      "ruleset_version": null,
      "transaction_timestamp": "2024-01-15T10:30:00Z",
      "ingestion_timestamp": "2024-01-15T10:30:02Z",
      "kafka_topic": null,
      "kafka_partition": null,
      "kafka_offset": null,
      "source_message_id": null,
      "trace_id": "trace-123",
      "request_id": null,
      "session_id": null,
      "raw_payload": null,
      "ingestion_source": "HTTP",
      "matched_rules": [
        {
          "id": "rule-match-uuid",
          "transaction_id": "01929xyz...",
          "rule_id": "rule_001",
          "rule_version": 1,
          "rule_name": "Velocity Check",
          "matched": true,
          "contributing": true,
          "rule_output": null,
          "match_score": 10.0,
          "match_reason": "Exceeded threshold",
          "matched_at": "2024-01-15T10:30:00Z"
        }
      ],
      "created_at": "2024-01-15T10:30:02Z",
      "updated_at": "2024-01-15T10:30:02Z"
    }
  ],
  "total": 1234,
  "page_size": 50,
  "has_more": true,
  "next_cursor": "base64-encoded-cursor"
}
```

**Note**: The `country` field is NOT persisted in the database. It can be used for filtering but will be applied in-memory.

### 3. Get Transaction by ID

**Purpose**: Get detailed information about a specific transaction.

```
GET /v1/transactions/{transaction_id}?include_rules=true
Authorization: Bearer <token>
```

**Path Parameters**:
- `transaction_id` (string) - The UUID of the transaction

**Query Parameters**:
- `include_rules` (boolean, default: true) - Include matched rules

**Response** (200 OK): Same structure as transaction in list response.

**Errors**:
- `404 Not Found` - Transaction does not exist

### 3a. Get Transaction Overview (NEW)

**Purpose**: Get combined view with transaction, review, notes, case, and rules in a single call. Optimized for UI performance.

```
GET /v1/transactions/{transaction_id}/overview?include_rules=true
Authorization: Bearer <token>
```

**Path Parameters**:
- `transaction_id` (string) - The UUID of the transaction

**Query Parameters**:
- `include_rules` (boolean, default: false) - Include matched rules in response

**Response** (200 OK):

```json
{
  "transaction": {
    "id": "uuid",
    "transaction_id": "uuid",
    "card_id": "tok_visa_xxxx",
    "card_last4": "4242",
    "amount": 99.99,
    "currency": "USD",
    "decision": "APPROVE",
    "risk_level": "MEDIUM",
    "transaction_timestamp": "2024-01-15T10:30:00Z",
    ...
  },
  "review": {
    "id": "uuid",
    "status": "IN_REVIEW",
    "priority": 2,
    "assigned_analyst_id": "auth0|user123",
    "assigned_at": "2024-01-15T10:35:00Z",
    "case_id": null,
    ...
  },
  "notes": [
    {
      "id": "uuid",
      "note_type": "INITIAL_REVIEW",
      "note_content": "Flagged for review",
      "analyst_id": "auth0|user123",
      "created_at": "2024-01-15T10:36:00Z"
    }
  ],
  "case": null,
  "matched_rules": [
    {
      "id": "uuid",
      "rule_id": "rule_001",
      "rule_name": "Velocity Check",
      "matched": true,
      "match_score": 10.0
    }
  ],
  "last_activity_at": "2024-01-15T10:36:00Z"
}
```

**Use Cases**:
- Transaction detail pages - single API call instead of 4-5
- Worklist item drill-down
- Case investigation views

### 4. Get Transaction Metrics

**Purpose**: Get aggregate transaction metrics.

```
GET /v1/metrics?from_date=2024-01-01T00:00:00Z&to_date=2024-01-31T23:59:59Z
Authorization: Bearer <token>
```

**Query Parameters**:
- `from_date` (optional) - Start of date range
- `to_date` (optional) - End of date range

**Response** (200 OK):

```json
{
  "total_transactions": 10000,
  "approved_count": 8500,
  "declined_count": 1200,
  "postauth_count": 300,
  "total_amount": 500000.0,
  "avg_amount": 500.0
}
```

**Note**: Amount fields are returned as numbers (float), not strings.

### 5. Health Check Endpoints

**Purpose**: Monitor service health.

```
GET /health          # Basic health check
GET /health/ready    # Readiness check (includes DB)
GET /health/live     # Liveness check (Kubernetes)
```

All return 200 OK with JSON response. No authentication required.

**Responses**:

```json
// GET /health
{"status": "healthy", "version": "0.1.0"}

// GET /health/ready
{"status": "ready", "database": "connected"}

// GET /health/live
{"status": "alive"}
```

## Data Model Reference

### TransactionQueryResult

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `transaction_id` | string (UUID) | Yes | Transaction UUID |
| `card_id` | string | Yes | Tokenized card identifier |
| `card_last4` | string | Yes | Last 4 digits of card (nullable) |
| `card_network` | string | Yes | Card network (VISA, MASTERCARD, AMEX, DISCOVER, OTHER) |
| `amount` | number | Yes | Transaction amount |
| `currency` | string | Yes | ISO 4217 currency code |
| `merchant_id` | string | Yes | Merchant ID (nullable) |
| `mcc` | string | Yes | Merchant category code (nullable) |
| `decision` | string | Yes | Decision (APPROVE, DECLINE, POSTAUTH) |
| `decision_reason` | string | Yes | Reason for decision |
| `decision_score` | number | No | Decision score (nullable) |
| `ruleset_id` | string (UUID) | No | Ruleset UUID used for evaluation (nullable) |
| `ruleset_version` | int | No | Ruleset version (nullable) |
| `transaction_timestamp` | datetime | Yes | When transaction occurred |
| `ingestion_timestamp` | datetime | Yes | When event was ingested |
| `kafka_topic` | string | No | Kafka topic if ingested via Kafka (nullable) |
| `kafka_partition` | int | No | Kafka partition (nullable) |
| `kafka_offset` | int | No | Kafka offset (nullable) |
| `source_message_id` | string | No | Source message ID (nullable) |
| `trace_id` | string | No | Distributed trace ID (nullable) |
| `request_id` | string | No | Request ID (nullable) |
| `session_id` | string | No | Session ID (nullable) |
| `raw_payload` | object | No | Raw payload data (nullable) |
| `ingestion_source` | string | Yes | Source (HTTP or KAFKA) |
| `matched_rules` | array | Yes | List of matched rules |
| `created_at` | datetime | Yes | Record creation timestamp |
| `updated_at` | datetime | Yes | Record update timestamp |

### RuleMatch (in matched_rules)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string (UUID) | Yes | Rule match record ID |
| `transaction_id` | string (UUID) | Yes | Associated transaction ID |
| `rule_id` | string | Yes | Rule identifier |
| `rule_version` | int | Yes | Rule version |
| `rule_name` | string | No | Rule name (nullable) |
| `matched` | boolean | Yes | Whether rule matched |
| `contributing` | boolean | Yes | Whether rule contributed to decision |
| `rule_output` | object | No | Rule output data (nullable) |
| `match_score` | number | No | Match score/priority (nullable) |
| `match_reason` | string | No | Human-readable match reason (nullable) |
| `matched_at` | datetime | No | When rule was evaluated (nullable) |

### TransactionListResponse

| Field | Type | Description |
|-------|------|-------------|
| `items` | array | List of transactions |
| `total` | int | Total count of matching transactions |
| `page_size` | int | Items per page |
| `has_more` | boolean | Whether more pages exist |
| `next_cursor` | string | Cursor for next page (null if last page) |

### DecisionEventCreate (Request)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `transaction_id` | string | Yes | Business transaction ID (idempotency key) |
| `event_version` | string | No | Event schema version (default: "1.0") |
| `occurred_at` | datetime | Yes | When transaction occurred |
| `produced_at` | datetime | Yes | When decision was produced |
| `transaction` | object | Yes | Transaction details |
| `decision` | string | Yes | Decision (APPROVE, DECLINE, POSTAUTH) |
| `decision_reason` | string | Yes | Decision reason |
| `matched_rules` | array | No | Matched rules (default: []) |
| `raw_payload` | object | No | Raw payload data (default: null) |

### TransactionDetails (nested in DecisionEventCreate)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `card_id` | string | Yes | Tokenized card ID (must start with `tok_`) |
| `card_last4` | string | No | Last 4 digits (max 4 chars) |
| `card_network` | string | No | Card network enum |
| `amount` | number | Yes | Transaction amount (must be > 0) |
| `currency` | string | Yes | ISO 4217 currency code (3 chars) |
| `country` | string | Yes | ISO 3166-1 alpha-2 country code (2 chars) |
| `merchant_id` | string | No | Merchant ID |
| `mcc` | string | No | Merchant category code |
| `ip_address` | string | No | Client IP address |

## PCI Compliance

**IMPORTANT**: This API is PCI-compliant by design:

1. **Never send raw PANs** - Use tokenized card IDs (`tok_<identifier>`)
2. **PAN detection** - Raw PAN patterns (13-19 digits passing Luhn) will be rejected with 422
3. **Raw payload filtering** - Only allowlisted fields are stored in `raw_payload`
4. **Card last4** - Optional field, mode-gated (`TOKEN_ONLY` vs `TOKEN_PLUS_LAST4`)

## Rate Limiting

Contact DevOps for current rate limits per environment.

## Error Handling

All errors follow standard HTTP status codes with JSON response:

```json
{
  "error": "Error type",
  "details": {
    "field": "card_id",
    "reason": "Invalid format"
  }
}
```

## OpenAPI Specification

Full OpenAPI 3.1 specification available at:
- Development: `http://localhost:8080/openapi.json`
- Generated file: `docs/03-api/openapi.json`

Regenerate with: `uv run openapi`

## Pagination

This API uses **keyset pagination** (cursor-based) for efficient querying:

1. First request: `GET /v1/transactions?page_size=50`
2. Response includes `has_more` and `next_cursor`
3. Next page: `GET /v1/transactions?page_size=50&cursor=<next_cursor>`
4. When `has_more` is false, you've reached the last page

**Benefits**:
- Consistent results even if data changes during pagination
- Better performance than offset-based pagination
- No duplicate or skipped records

---

## Analyst Workflow Endpoints (NEW)

The following endpoints support the fraud analyst workflow for reviewing, annotating, and resolving transactions.

### Transaction Reviews

Reviews are automatically created when a transaction is ingested. These endpoints manage the review lifecycle.

#### Get Transaction Review

```
GET /v1/transactions/{transaction_id}/review
Authorization: Bearer <token>
```

**Response** (200 OK):

```json
{
  "id": "uuid",
  "transaction_id": "uuid",
  "status": "PENDING",
  "priority": 3,
  "case_id": null,
  "assigned_analyst_id": null,
  "assigned_at": null,
  "resolved_at": null,
  "resolved_by": null,
  "resolution_code": null,
  "resolution_notes": null,
  "escalated_at": null,
  "escalated_to": null,
  "escalation_reason": null,
  "first_reviewed_at": null,
  "last_activity_at": null,
  "created_at": "2024-01-15T10:30:02Z",
  "updated_at": "2024-01-15T10:30:02Z",
  "transaction_amount": 99.99,
  "transaction_currency": "USD",
  "decision": "APPROVE",
  "risk_level": null
}
```

**Status Values**:
- `PENDING` - Awaiting review
- `IN_REVIEW` - Analyst is reviewing
- `ESCALATED` - Escalated to supervisor
- `RESOLVED` - Review completed
- `CLOSED` - Final state

#### Create/Update Review

```
POST /v1/transactions/{transaction_id}/review
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "priority": 1
}
```

#### Update Review Status

```
PATCH /v1/transactions/{transaction_id}/review/status
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "status": "IN_REVIEW",
  "notes": "Starting investigation"
}
```

#### Assign Transaction

```
PATCH /v1/transactions/{transaction_id}/review/assign
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "analyst_id": "auth0|user123"
}
```

#### Resolve Transaction

```
POST /v1/transactions/{transaction_id}/review/resolve
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "resolution_code": "FRAUD_CONFIRMED",
  "resolution_notes": "Card was reported stolen"
}
```

**Resolution Codes**:
- `FRAUD_CONFIRMED` - Confirmed fraudulent
- `FALSE_POSITIVE` - Not fraud
- `LEGITIMATE` - Valid transaction
- `DUPLICATE` - Duplicate investigation
- `INSUFFICIENT_INFO` - Cannot determine

#### Escalate Transaction

```
POST /v1/transactions/{transaction_id}/review/escalate
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "escalate_to": "auth0|supervisor456",
  "escalation_reason": "Complex fraud pattern requires supervisor review"
}
```

---

### Analyst Notes

Notes can be added to any transaction for documentation.

#### List Notes

```
GET /v1/transactions/{transaction_id}/notes
Authorization: Bearer <token>
```

**Response** (200 OK):

```json
{
  "items": [
    {
      "id": "uuid",
      "transaction_id": "uuid",
      "note_type": "INITIAL_REVIEW",
      "note_content": "Flagged due to unusual velocity pattern",
      "analyst_id": "auth0|user123",
      "analyst_name": "John Doe",
      "analyst_email": "john@example.com",
      "is_private": false,
      "is_system_generated": false,
      "case_id": null,
      "created_at": "2024-01-15T10:35:00Z",
      "updated_at": "2024-01-15T10:35:00Z"
    }
  ],
  "total": 1,
  "page_size": 50,
  "has_more": false
}
```

**Note Types**:
- `GENERAL` - General note
- `INITIAL_REVIEW` - Initial review note
- `CUSTOMER_CONTACT` - Customer contact log
- `MERCHANT_CONTACT` - Merchant contact log
- `BANK_CONTACT` - Bank contact log
- `FRAUD_CONFIRMED` - Fraud confirmation note
- `FALSE_POSITIVE` - False positive note
- `ESCALATION` - Escalation note
- `RESOLUTION` - Resolution note
- `LEGAL_HOLD` - Legal hold note
- `INTERNAL_REVIEW` - Internal review note

#### Create Note

```
POST /v1/transactions/{transaction_id}/notes
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "note_type": "CUSTOMER_CONTACT",
  "note_content": "Called customer at 555-1234. Confirmed they did not make this purchase.",
  "is_private": false
}
```

#### Update Note

```
PATCH /v1/transactions/{transaction_id}/notes/{note_id}
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "note_content": "Updated: Called customer at 555-1234. They confirmed fraud.",
  "note_type": "FRAUD_CONFIRMED"
}
```

#### Delete Note

```
DELETE /v1/transactions/{transaction_id}/notes/{note_id}
Authorization: Bearer <token>
```

Returns `204 No Content` on success.

---

### Worklist

The worklist provides a prioritized queue of transactions for analysts.

#### Get Worklist

```
GET /v1/worklist?status=PENDING&priority_filter=1&risk_level_filter=HIGH&limit=50
Authorization: Bearer <token>
```

**Query Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status (PENDING, IN_REVIEW, etc.) |
| `assigned_only` | bool | If true, show only assigned items; if false, show unassigned |
| `priority_filter` | int | **NEW** - Filter by priority (1-5, where 1=highest) |
| `risk_level_filter` | string | **NEW** - Filter by risk (LOW, MEDIUM, HIGH, CRITICAL) |
| `limit` | int | Items per page (1-100, default: 50) |
| `cursor` | string | Pagination cursor |

**Response** (200 OK):

```json
{
  "items": [
    {
      "review_id": "uuid",
      "transaction_id": "uuid",
      "status": "PENDING",
      "priority": 1,
      "card_id": "tok_visa_xxxx",
      "card_last4": "4242",
      "transaction_amount": 5000.00,
      "transaction_currency": "USD",
      "transaction_timestamp": "2024-01-15T10:30:00Z",
      "decision": "DECLINE",
      "decision_reason": "VELOCITY_MATCH",
      "decision_score": 85.5,
      "risk_level": "HIGH",
      "assigned_analyst_id": null,
      "assigned_at": null,
      "case_id": null,
      "case_number": null,
      "first_reviewed_at": null,
      "last_activity_at": null,
      "created_at": "2024-01-15T10:30:02Z",
      "merchant_id": "merchant_001",
      "merchant_category_code": "5411",
      "trace_id": "trace-123"
    }
  ],
  "total": 150,
  "page_size": 50,
  "has_more": true,
  "next_cursor": "base64-encoded-cursor"
}
```

#### Get Unassigned Transactions

```
GET /v1/worklist/unassigned?limit=50
Authorization: Bearer <token>
```

Same response format as worklist.

#### Get Worklist Statistics

```
GET /v1/worklist/stats
Authorization: Bearer <token>
```

**Response** (200 OK):

```json
{
  "unassigned_total": 150,
  "unassigned_by_priority": {
    "1": 10,
    "2": 25,
    "3": 50,
    "4": 40,
    "5": 25
  },
  "unassigned_by_risk": {
    "CRITICAL": 5,
    "HIGH": 30,
    "MEDIUM": 65,
    "LOW": 50
  },
  "my_assigned_total": 15,
  "my_assigned_by_status": {
    "PENDING": 3,
    "IN_REVIEW": 10,
    "ESCALATED": 2
  },
  "resolved_today": 25,
  "resolved_by_code": {
    "FRAUD_CONFIRMED": 10,
    "FALSE_POSITIVE": 8,
    "LEGITIMATE": 5,
    "INSUFFICIENT_INFO": 2
  },
  "avg_resolution_minutes": 45.5
}
```

#### Claim Next Transaction

```
POST /v1/worklist/claim
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "priority_filter": 1,
  "risk_level_filter": "CRITICAL"
}
```

**Request Body Parameters** (all optional):
- `priority_filter` (int) - Only claim transactions at or below this priority (1=highest)
- `risk_level_filter` (string) - Only claim transactions at this risk level or higher

**Response** (200 OK): Returns the WorklistItem that was claimed.

---

### Cases

Cases group related transactions for investigation.

#### List Cases

```
GET /v1/cases?case_status=OPEN&case_type=INVESTIGATION&limit=50
Authorization: Bearer <token>
```

**Query Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `case_status` | string | Filter by status (OPEN, IN_PROGRESS, RESOLVED, CLOSED) |
| `case_type` | string | Filter by type (INVESTIGATION, DISPUTE, etc.) |
| `assigned_analyst_id` | string | Filter by assigned analyst |
| `risk_level` | string | Filter by risk level |
| `limit` | int | Items per page (1-100, default: 50) |
| `cursor` | string | Pagination cursor |

**Response** (200 OK):

```json
{
  "items": [
    {
      "id": "uuid",
      "case_number": "CASE-2024-00001",
      "case_type": "INVESTIGATION",
      "case_status": "OPEN",
      "assigned_analyst_id": "auth0|user123",
      "assigned_at": "2024-01-15T10:30:00Z",
      "title": "Suspicious velocity pattern - Card tok_visa_xxxx",
      "description": "Multiple high-value transactions in short timeframe",
      "total_transaction_count": 5,
      "total_transaction_amount": 15000.00,
      "risk_level": "HIGH",
      "resolved_at": null,
      "resolved_by": null,
      "resolution_summary": null,
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 25,
  "page_size": 50,
  "has_more": false,
  "next_cursor": null
}
```

**Case Types**:
- `INVESTIGATION` - General investigation
- `DISPUTE` - Customer dispute
- `CHARGEBACK` - Chargeback case
- `FRAUD_RING` - Fraud ring investigation
- `ACCOUNT_TAKEOVER` - Account takeover
- `PATTERN_ANALYSIS` - Pattern analysis
- `MERCHANT_REVIEW` - Merchant-specific investigation
- `CARD_COMPROMISE` - Compromised card investigation
- `OTHER` - Other

**Case Status**:
- `OPEN` - New case
- `IN_PROGRESS` - Being worked
- `PENDING_INFO` - Waiting for information
- `RESOLVED` - Resolved
- `CLOSED` - Closed

#### Create Case

```
POST /v1/cases
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "case_type": "INVESTIGATION",
  "title": "Suspicious velocity pattern - Card tok_visa_xxxx",
  "description": "Multiple high-value transactions in short timeframe",
  "transaction_ids": ["uuid1", "uuid2", "uuid3"],
  "assigned_analyst_id": "auth0|user123",
  "risk_level": "HIGH"
}
```

#### Get Case

```
GET /v1/cases/{case_id}
Authorization: Bearer <token>
```

#### Get Case by Number

```
GET /v1/cases/number/{case_number}
Authorization: Bearer <token>
```

Example: `GET /v1/cases/number/CASE-2024-00001`

#### Update Case

```
PATCH /v1/cases/{case_id}
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "case_status": "IN_PROGRESS",
  "risk_level": "CRITICAL",
  "title": "Updated title"
}
```

#### Resolve Case

```
POST /v1/cases/{case_id}/resolve
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "resolution_summary": "Confirmed fraud ring operating across 5 transactions. Cards blocked.",
  "resolved_by": "auth0|user123"
}
```

#### Get Case Transactions

```
GET /v1/cases/{case_id}/transactions
Authorization: Bearer <token>
```

Returns list of transactions linked to the case.

#### Add Transaction to Case

```
POST /v1/cases/{case_id}/transactions
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "transaction_id": "uuid"
}
```

#### Remove Transaction from Case

```
DELETE /v1/cases/{case_id}/transactions/{transaction_id}
Authorization: Bearer <token>
```

Returns `204 No Content` on success.

#### Get Case Activity Log

```
GET /v1/cases/{case_id}/activity?limit=50
Authorization: Bearer <token>
```

**Response** (200 OK):

```json
{
  "items": [
    {
      "id": "uuid",
      "case_id": "uuid",
      "activity_type": "TRANSACTION_ADDED",
      "activity_data": {
        "transaction_id": "uuid",
        "amount": 5000.00
      },
      "performed_by": "auth0|user123",
      "performed_by_name": "John Doe",
      "created_at": "2024-01-15T10:35:00Z"
    }
  ],
  "total": 10,
  "has_more": false
}
```

---

### Bulk Operations

Bulk operations allow processing multiple transactions at once.

#### Bulk Assign

```
POST /v1/bulk/assign
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "transaction_ids": ["uuid1", "uuid2", "uuid3"],
  "analyst_id": "auth0|user123"
}
```

**Response** (200 OK):

```json
{
  "success_count": 3,
  "failure_count": 0,
  "results": [
    {"transaction_id": "uuid1", "success": true, "error_message": null, "error_code": null},
    {"transaction_id": "uuid2", "success": true, "error_message": null, "error_code": null},
    {"transaction_id": "uuid3", "success": true, "error_message": null, "error_code": null}
  ],
  "case_id": null
}
```

#### Bulk Update Status

```
POST /v1/bulk/status
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "transaction_ids": ["uuid1", "uuid2"],
  "status": "RESOLVED",
  "resolution_code": "FALSE_POSITIVE",
  "resolution_notes": "All transactions verified as legitimate"
}
```

#### Bulk Create Case

```
POST /v1/bulk/create-case
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "transaction_ids": ["uuid1", "uuid2", "uuid3"],
  "case_type": "FRAUD_RING",
  "title": "Related fraud pattern investigation",
  "description": "Transactions share common characteristics",
  "assigned_analyst_id": "auth0|user123",
  "risk_level": "CRITICAL"
}
```

**Response** (200 OK):

```json
{
  "success_count": 3,
  "failure_count": 0,
  "results": [...],
  "case_id": "uuid"
}
```

---

### Required Scopes (Updated)

| Endpoint Category | Required Scope |
|-------------------|---------------|
| Reviews (GET) | `txn:view` |
| Reviews (POST/PATCH) | `txn:review` |
| Reviews (assign) | `txn:assign` |
| Reviews (resolve) | `txn:resolve` |
| Reviews (escalate) | `txn:escalate` |
| Notes (GET) | `txn:view` |
| Notes (POST/PATCH/DELETE) | `note:create` |
| Notes (DELETE others) | `note:delete` |
| Worklist | `txn:view` |
| Cases (GET) | `txn:view` |
| Cases (POST/PATCH) | `case:create` |
| Cases (resolve) | `case:resolve` |
| Bulk operations | `bulk:operations` |

---

## Support

- **API Issues**: Create ticket in project repository
- **Auth0 Issues**: Contact DevOps/Security team
- **PCI Concerns**: Contact Security team immediately
