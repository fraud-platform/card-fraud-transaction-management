# Domain & Contracts Plan

## Primary domain concepts

### Transaction (fact)
Represents a single payment attempt as captured by the upstream event.

Key identity:
- `transaction_id` (idempotency key; stable)

Core attributes (from spec table):
- `occurred_at` (event time / business time)
- `card_id` (tokenized), `card_last4` (optional), `card_network` (optional), `merchant_id`
- `amount`, `currency`, `country`
- `decision` (APPROVE / DECLINE / NULL)
- `ruleset_key` (CARD_PREAUTH / CARD_POSTAUTH)
- `ruleset_version` (integer)
- `trace_id`
- `raw_payload` (optional; may be redacted)

### Rule match (detail)
Represents each matched rule per transaction.

Key identity (logical):
- `(transaction_id, rule_id, rule_version)` — recommended natural idempotency key.

Attributes:
- `rule_type`
- `severity`, `reason_code`
- `matched_at`

## Input contract (Decision Event — canonical v1)

The canonical v1 envelope and examples are locked in:
- [../03-api/decision-event-schema-v1.md](../03-api/decision-event-schema-v1.md)
- [../03-api/decision-event.schema.v1.json](../03-api/decision-event.schema.v1.json)

Required top-level fields:
- `event_version` ("1.0")
- `event_type` ("FRAUD_DECISION")
- `produced_at`
- `trace_id`
- `transaction_id`
- `ruleset_key` (CARD_PREAUTH / CARD_POSTAUTH)
- `ruleset_version`
- `decision` (APPROVE/DECLINE or null for POSTAUTH)
- `decision_reason` (nullable for POSTAUTH)
- `matched_rules[]`
- `transaction` (nested object)

### Locked meanings
- `transaction.occurred_at` is the business timestamp and maps to `transactions.occurred_at`.
- `matched_rules[].matched_at` maps to `transaction_rule_matches.matched_at`.
- `decision == null` indicates POSTAUTH.

### Timestamp requirements (v1)
- Required format: ISO8601 `date-time` with timezone offset (UTC `Z` recommended).
- Required precision: milliseconds (e.g., `2026-01-15T10:45:32.123Z`).
- Validation: reject timestamps missing an explicit timezone offset.

## Locked policy: card identifiers

- `card_id` is always tokenized (stable, non-reversible here). Never raw PAN.
- `card_last4` may be stored for analyst usability.
- No masking flags or country-based PAN handling in this service.

## Locked policy: `card_identifier_mode` enforcement

The service uses a configuration mode (not an event field):
- `TOKEN_ONLY` (default): `card_last4` is not persisted even if provided.
- `TOKEN_PLUS_LAST4`: `card_last4` must be present and valid.

This rule is enforced during ingestion validation/normalization.

## Boundary: schema vs policy

- The event contract is stable and environment-agnostic.
- Compliance/storage decisions (like dropping `card_last4` in `TOKEN_ONLY`) are service policy, not part of the event.

## Mapping rules (event → DB)
- `transactions.transaction_id` ← `event.transaction_id`
- `transactions.ruleset_key` ← `event.ruleset_key`
- `transactions.ruleset_version` ← `event.ruleset_version`
- `transactions.decision` ← `event.decision`
- `transactions.decision_reason` ← `event.decision_reason`
- `transactions.produced_at` ← `event.produced_at`
- `transactions.trace_id` ← `event.trace_id`
- `transactions.occurred_at` ← `event.transaction.occurred_at`
- `transactions.card_id` ← `event.transaction.card_id` (expected masked/tokenized)
- `transactions.card_last4` ← `event.transaction.card_last4` (optional)
- `transactions.card_network` ← `event.transaction.card_network` (optional)
- `transactions.merchant_id` ← `event.transaction.merchant_id`
- `transactions.amount` ← `event.transaction.amount`
- `transactions.currency` ← `event.transaction.currency`
- `transactions.country` ← `event.transaction.country`
- `transactions.mcc` ← `event.transaction.mcc` (optional)
- `transactions.ip` ← `event.transaction.ip` (optional)
- `transactions.ingestion_source` ← internal (set to `KAFKA` or `HTTP` based on ingestion path)
- `transactions.created_at` ← internal (set on first insert)
- `transactions.updated_at` ← internal (set on insert and updated on duplicate metadata-only upserts)
- `transaction_rule_matches.transaction_id` ← `event.transaction_id`
- `transaction_rule_matches.rule_id` ← `event.matched_rules[i].rule_id`
- `transaction_rule_matches.rule_version` ← `event.matched_rules[i].rule_version`
- `transaction_rule_matches.rule_type` ← `event.matched_rules[i].rule_type`
- `transaction_rule_matches.priority` ← `event.matched_rules[i].priority` (optional)
- `transaction_rule_matches.severity` ← `event.matched_rules[i].severity`
- `transaction_rule_matches.reason_code` ← `event.matched_rules[i].reason_code`
- `transaction_rule_matches.matched_at` ← `event.matched_rules[i].matched_at`

Notes:
- Unknown/unmodeled fields should be ignored by default and may be captured in redacted allowlist `raw_payload` if needed.

## Validation rules (ingestion)
- Reject / quarantine events missing any required field.
- Enforce `ruleset_key` enum.
- Enforce `decision` enum when non-null.
- Enforce `ruleset_version` is integer >= 1.
- Enforce `transaction_id` non-empty, stable.
- Enforce `matched_rules` is an array (can be empty).

Additional v1 validations:
- `event_version` must be "1.0".
- `event_type` must be "FRAUD_DECISION".
- `transaction.currency` must be 3-letter code.
- `transaction.country` must be 2-letter code.

## Versioning strategy

- Treat upstream schema as versioned via `event_version`.
- v1 is forward-compatible at the parser boundary: unknown fields must not break ingestion.
- Breaking changes (type changes, enum removals, required field changes) must introduce a new version (e.g., 1.1/2.0) and update consumer accordingly.

## TODO checklist
- Confirm allowed values for `decision_reason` vocabulary.
- Confirm whether `card_id` is always masked/tokenized (never full PAN).
- Confirm whether `matched_rules` is allowed to be empty in all cases.
