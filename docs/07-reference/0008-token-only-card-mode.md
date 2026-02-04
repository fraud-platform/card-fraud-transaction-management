# ADR-008: Token-Only Card Data Mode (PCI Compliance)

**Status:** Accepted

**Date:** 2026-01-27

**Context:**

The Card Fraud Transaction Management service stores fraud decision events which include card information. Under PCI-DSS, storing cardholder data (PAN - Primary Account Number) requires:
- Significant security controls
- Encryption at rest and in transit
- Strict access logging
- Quarterly compliance audits
- Higher infrastructure costs

The fraud detection system receives **tokenized** card IDs from upstream services (the card processor tokenizes before sending). The PAN is not needed for fraud analysis.

**Requirements:**
1. **PCI Compliance**: Never persist raw PAN (card number)
2. **Usability**: Enough card info for analyst investigations
3. **Flexibility**: Support different tokenization schemes
4. **Safety**: Detect and reject any events containing suspected PAN

**Decision:**

Implement **Token-Only** card data mode with optional mode-gated `card_last4`:

```sql
CREATE TABLE fraud_gov.transactions (
    id UUID NOT NULL PRIMARY KEY,
    -- Token identification (required, tokenized)
    card_id VARCHAR(64) NOT NULL,        -- Tokenized card ID (e.g., tok_12345)

    -- Optional last-4 digits (mode-gated, not raw PAN)
    card_last4 VARCHAR(4),               -- Only if explicitly enabled

    -- Card metadata (not PAN)
    card_network fraud_gov.card_network, -- VISA, MASTERCARD, etc.
    -- ... other fields ...
);
```

**Configuration Modes:**
```python
class CardDataMode(str, Enum):
    TOKEN_ONLY = "TOKEN_ONLY"      # card_id only (default)
    TOKEN_PLUS_LAST4 = "TOKEN_PLUS_LAST4"  # card_id + last4 digits
```

**PAN Detection (Security Layer):**
```python
# Sink events with suspected PAN patterns
PAN_PATTERNS = [
    r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14})',  # Visa, MC
    r'\b3[47][0-9]{13}',                                   # AMEX
    r'\b6(?:011|5[0-9]{2})[0-9]{12}',                     # Discover
]

def detect_pan_in_payload(data: dict) -> bool:
    """Check if payload contains suspected PAN."""
    json_str = json.dumps(data)
    for pattern in PAN_PATTERNS:
        if re.search(pattern, json_str):
            return True
    return False
```

**Allowlist for Raw Payload:**
```python
# Only store these fields from raw_payload (redacted)
ALLOWLIST_FIELDS = {
    'transaction_id', 'card_id', 'evaluation_type',
    'decision', 'ruleset_key', 'matched_rules',
    # ... safe fields only, no PAN
}

def redact_payload(payload: dict) -> dict:
    """Redact any non-allowlisted fields."""
    return {k: v for k, v in payload.items() if k in ALLOWLIST_FIELDS}
```

**Consequences:**

**Positive:**
- **Reduced PCI scope**: Token-only storage has minimal PCI requirements
- **Lower infrastructure costs**: No encryption at rest for tokens
- **Security**: PAN never touches our database
- **Audit-ready**: Clear demarcation of what's stored

**Negative:**
- `card_last4` not available in TOKEN_ONLY mode
- Cannot reconstruct full card number (security feature, not bug)
- Dependency on upstream tokenization

**Mode Comparison:**

| Field | TOKEN_ONLY | TOKEN_PLUS_LAST4 |
|-------|------------|-------------------|
| `card_id` | ✅ Required | ✅ Required |
| `card_last4` | ❌ Not stored | ✅ Stored |
| `card_network` | ✅ Stored | ✅ Stored |
| PAN Detection | ✅ Active | ✅ Active |
| PCI Scope | Minimal | Reduced |

**Security Rules:**

1. **Never accept PAN in API**: Reject requests with suspected PAN patterns
2. **Redact raw payload**: Only store allowlisted fields
3. **Log security events**: Alert when PAN detection triggers
4. **Mode enforcement**: Environment-based mode selection

**Example Payload Flow:**
```json
// Input (may contain PAN - security risk)
{
  "transaction_id": "uuid-123",
  "card_id": "tok_abc123",           // Tokenized - OK
  "card_number": "4111111111111111", // PAN - REJECTED/SUNK
  "decision": "APPROVE"
}

// Stored (redacted)
{
  "transaction_id": "uuid-123",
  "card_id": "tok_abc123",           // Token stored
  "card_number": "[REDACTED]",        // PAN removed
  "decision": "APPROVE"
}
```

**Alternatives Considered:**

1. **Store full PAN (encrypted)**
   - Rejected: Maximum PCI scope, expensive compliance
   - PAN not needed for fraud analysis

2. **Store last N digits (e.g., last 8)**
   - Rejected: Still increases PCI scope
   - Tokenization upstream is standard practice

3. **Hash the PAN**
   - Rejected: Hash considered "cardholder data" under PCI-DSS
   - Defeats purpose of tokenization

**PCI-DSS Scoping:**

| Data Type | PCI Scope | Stored Here? |
|-----------|-----------|--------------|
| Raw PAN | Full Scope | ❌ NO |
| Encrypted PAN | Full Scope | ❌ NO |
| Truncated PAN (last 4) | Reduced | ⚠️ Mode-dependent |
| Token (tok_xxx) | Out of Scope | ✅ YES |
| Hashed PAN | Full Scope | ❌ NO |

**Compliance Statement:**

> The Card Fraud Transaction Management service operates in **Token-Only** mode. All cardholder data (PAN) is tokenized upstream by the card processor before reaching this service. No raw, encrypted, or hashed PAN is stored, processed, or logged.

**Related:**
- [docs/09-security-and-data-governance.md](../06-operations/security-and-data-governance.md)
- [app/core/security/pan_detector.py](../../app/core/security/pan_detector.py)
- [README.md](../../README.md) - Security & Compliance section
