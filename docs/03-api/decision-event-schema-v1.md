# Decision Event Schema v1 (LOCKED)

This document locks the canonical **v1** decision event consumed by the transaction management service.

- Event type: `FRAUD_DECISION`
- Event version: `1.0`
- Same envelope for **AUTH** and **MONITORING** (MONITORING uses `decision=null`).

## Canonical v1 envelope

```json
{
  "event_version": "1.0",
  "event_type": "FRAUD_DECISION",
  "produced_at": "2026-01-15T10:45:32Z",

  "trace_id": "6f2c9c7e9c4b4b3c",
  "transaction_id": "txn_123456",

  "ruleset_key": "CARD_AUTH",
  "ruleset_version": 42,

  "decision": "DECLINE",
  "decision_reason": "RULE_MATCH",

  "matched_rules": [
    {
      "rule_id": "R-1001",
      "rule_version": 7,
      "rule_type": "BLOCKLIST",
      "priority": 10,

      "reason_code": "HIGH_AMOUNT_RISK",
      "severity": "HIGH",

      "matched_at": "2026-01-15T10:45:32Z"
    }
  ],

  "transaction": {
    "occurred_at": "2026-01-15T10:45:30Z",
    "card_id": "tok_card_8f29caa1",
    "card_last4": "1111",
    "merchant_id": "M12345",
    "amount": 5200,
    "currency": "INR",
    "country": "IN",
    "mcc": "5411",
    "ip": "10.1.2.3"
  }
}
```

## MONITORING variant (differences only)

```json
{
  "ruleset_key": "CARD_MONITORING",
  "decision": null,
  "decision_reason": null
}
```

## Mapping rules (event → DB)

- One event → exactly one row in `transactions` (idempotent).
- Each object in `matched_rules[]` → one row in `transaction_rule_matches` (idempotent).
- `transaction_id` → `transactions.transaction_id` primary key.
- If `decision == null`, treat as MONITORING (still persist normally).

## Locked policy: card identifiers (PCI-safe)

- This service never stores raw PAN.
- `transaction.card_id` is a **tokenized**, stable identifier.
- `transaction.card_last4` is optional and allowed for analyst usability.
- Any PAN reveal (if required) must happen via a separate PCI-scoped system with RBAC + audit.

## Config-driven constraint: require last4 only in TOKEN_PLUS_LAST4 mode

The JSON Schema cannot express requirements that depend on service configuration.
Therefore, the following rule is enforced by ingestion code:
- If `card_identifier_mode=TOKEN_ONLY` (default), drop `transaction.card_last4` and do not persist it.
- If `card_identifier_mode=TOKEN_PLUS_LAST4`, require `transaction.card_last4` to be present and match `^[0-9]{4}$`.

## Locked decision_reason enum

- `RULE_MATCH`
- `VELOCITY_MATCH`
- `SYSTEM_DECLINE`
- `DEFAULT_ALLOW`

## Kafka defaults (recommended)

- Topic: `fraud.card.decisions.v1`
- Key: `transaction_id`
- Value: decision event JSON v1

## JSON Schema

The machine-readable JSON Schema is in [../03-api/decision-event.schema.v1.json](../03-api/decision-event.schema.v1.json).

Forward-compatibility note (v1):
- Producers may add additional fields over time.
- Consumers must ignore unknown fields and continue processing as long as required fields remain valid.

## Boundary: contract vs compliance policy (locked)

The JSON Schema defines the **structural data contract** (shape, types, enums, required fields).
It intentionally does **not** encode environment-specific or compliance policy such as PCI handling.

Locked principles:
- The event answers “what happened” (decision, matched rules, transaction attributes).
- Storage/compliance concerns are enforced by this service at runtime (validation/normalization), not via schema hacks.
- `card_identifier_mode` is a service configuration concern and does not belong in the event envelope.
