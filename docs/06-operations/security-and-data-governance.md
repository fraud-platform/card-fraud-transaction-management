# Security & Data Governance Plan

## Data classification
- `card_id` is a tokenized stable identifier (non-reversible here).
- `raw_payload` may contain PII/PCI data; treat as sensitive by default.

## Locked policy: PAN handling

- The transaction-management DB never stores raw PAN.
- Raw PAN must not even transit this service boundary (ingestion must reject/quarantine if discovered).
- No global masking on/off flags.
- No country-based PAN storage logic in this service.
- PAN reveal (if required) must be handled by a separate PCI-scoped system with RBAC + audit.

## Boundary: schema vs policy

- JSON Schema enforces event structure (required fields/types/enums).
- PCI/compliance policy is enforced by runtime validation/normalization and storage rules.
- Avoid adding “masking flags” to the event; keep policy in configuration.

## Raw payload policy

Locked policy:
- `raw_payload` is allowed in prod but must be **allowlist-only and redacted**.
- Mask or hash sensitive fields.
- Never store full PAN, CVV, expiry, or non-tokenized PII.

Implementation plan for the allowlist:
- Maintain a small field allowlist (e.g., `transaction_id`, `amount`, `currency`, `country`, `merchant_id`, `mcc`, `decision_reason`).
- Build a deterministic redaction step in ingestion before persistence.

## Authentication & authorization
- Internal service-to-service authentication for ingestion (if HTTP enabled).
- Query API should require auth (JWT/mTLS) and enforce role-based access:
  - Analyst: can query transactions, view rule matches.
  - Investigator: may view raw_payload (if allowed).
  - Admin: replay tools, DLQ tools.

## Audit and access logging
- Log who accessed transaction detail endpoints (especially if raw_payload is exposed).

## Threat model checklist
- Injection protection (parameterized queries).
- Rate limiting and request size caps.
- Secrets management.
- Principle of least privilege for DB user.
- Secure defaults: disable debug endpoints, disable HTTP ingestion in prod unless needed.

## Compliance hooks (out of scope for v1 but planned)
- Retention enforcement (TTL/job) for raw_payload.
- Data deletion requests (GDPR/CCPA) workflow.

## TODO checklist
- Confirm auth provider (Azure AD, Okta, custom).
- Confirm whether raw_payload is allowed in prod.
- Confirm encryption requirements (at rest / in transit).
- Define RBAC roles and field-level permissions.
