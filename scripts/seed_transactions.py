"""Seed realistic transaction mix for integration and e2e testing.

Uses deterministic UUIDv7 values for seeded IDs.
Idempotent: repeated runs target the same transaction identifiers.

Run via Doppler:
    doppler run --config local -- uv run python scripts/seed_transactions.py

Inserts:
  - 100 transactions total (realistic fraud ratio)
  - 10 DECLINE transactions (with rule matches) - ~10% fraud rate
  - 90 APPROVE transactions - legitimate purchases across diverse merchants
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import random
import sys
import uuid
from datetime import UTC, datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

NOW = datetime.now(UTC)
SEED_UUID7_EPOCH_MS = int(datetime(2025, 1, 1, tzinfo=UTC).timestamp() * 1000)

# Fixed seed for reproducible risk scores and approve distributions.
random.seed(42)

# Shared ruleset
RULESET_ID = uuid.UUID("019501a0-0000-7000-8000-000000000001")
RULE_VELOCITY = uuid.UUID("019501a0-0000-7000-8000-000000000010")
RULE_GEO = uuid.UUID("019501a0-0000-7000-8000-000000000011")
RULE_HIGH_VALUE = uuid.UUID("019501a0-0000-7000-8000-000000000012")
RULE_CARD_TEST = uuid.UUID("019501a0-0000-7000-8000-000000000013")
RULE_BUST_OUT = uuid.UUID("019501a0-0000-7000-8000-000000000014")

# ---------------------------------------------------------------------------
# DECLINE transactions (10) - each has rule matches
# ---------------------------------------------------------------------------
DECLINES = [
    {
        "card_id": "tok_visa_fraud_001",
        "card_last4": "4242",
        "card_network": "VISA",
        "amount": "1250.00",
        "currency": "USD",
        "merchant": "merch_electronics_001",
        "mcc": "5732",
        "decision": "DECLINE",
        "reason": "RULE_MATCH",
        "score": "92.50",
        "risk": "HIGH",
        "hours_ago": 2,
        "rules": [
            {
                "rule_id": RULE_VELOCITY,
                "name": "velocity_spike_24h",
                "action": "DECLINE",
                "score": "90.00",
                "match_reason": "Card velocity exceeded 10 txns in 24h",
            },
            {
                "rule_id": RULE_HIGH_VALUE,
                "name": "high_value_electronics",
                "action": "DECLINE",
                "score": "85.00",
                "match_reason": "High-value electronics purchase",
            },
        ],
    },
    {
        "card_id": "tok_mc_fraud_002",
        "card_last4": "1234",
        "card_network": "MASTERCARD",
        "amount": "499.99",
        "currency": "GBP",
        "merchant": "merch_travel_007",
        "mcc": "4722",
        "decision": "DECLINE",
        "reason": "VELOCITY_MATCH",
        "score": "78.00",
        "risk": "HIGH",
        "hours_ago": 5,
        "rules": [
            {
                "rule_id": RULE_GEO,
                "name": "geo_improbable_velocity",
                "action": "DECLINE",
                "score": "78.00",
                "match_reason": "Geographically improbable transaction velocity",
            },
        ],
    },
    {
        "card_id": "tok_amex_fraud_003",
        "card_last4": "0005",
        "card_network": "AMEX",
        "amount": "3750.00",
        "currency": "USD",
        "merchant": "merch_luxury_003",
        "mcc": "5094",
        "decision": "DECLINE",
        "reason": "RULE_MATCH",
        "score": "95.00",
        "risk": "HIGH",
        "hours_ago": 8,
        "rules": [
            {
                "rule_id": RULE_CARD_TEST,
                "name": "card_testing_pattern",
                "action": "DECLINE",
                "score": "95.00",
                "match_reason": "Card testing pattern: multiple small txns then large",
            },
            {
                "rule_id": RULE_HIGH_VALUE,
                "name": "high_risk_mcc",
                "action": "DECLINE",
                "score": "80.00",
                "match_reason": "High-risk merchant category code",
            },
        ],
    },
    {
        "card_id": "tok_visa_fraud_004",
        "card_last4": "9999",
        "card_network": "VISA",
        "amount": "89.50",
        "currency": "USD",
        "merchant": "merch_online_010",
        "mcc": "5999",
        "decision": "DECLINE",
        "reason": "RULE_MATCH",
        "score": "71.00",
        "risk": "MEDIUM",
        "hours_ago": 12,
        "rules": [
            {
                "rule_id": RULE_CARD_TEST,
                "name": "new_card_large_purchase",
                "action": "DECLINE",
                "score": "71.00",
                "match_reason": "New card (<30 days) with above-average purchase",
            },
        ],
    },
    {
        "card_id": "tok_visa_fraud_005",
        "card_last4": "5678",
        "card_network": "VISA",
        "amount": "2100.00",
        "currency": "EUR",
        "merchant": "merch_wire_020",
        "mcc": "6012",
        "decision": "DECLINE",
        "reason": "RULE_MATCH",
        "score": "88.00",
        "risk": "HIGH",
        "hours_ago": 18,
        "rules": [
            {
                "rule_id": RULE_BUST_OUT,
                "name": "cross_merchant_bust_out",
                "action": "DECLINE",
                "score": "88.00",
                "match_reason": "Cross-merchant spend pattern: bust-out fraud",
            },
        ],
    },
    {
        "card_id": "tok_visa_fraud_006",
        "card_last4": "7777",
        "card_network": "VISA",
        "amount": "5000.00",
        "currency": "USD",
        "merchant": "merch_casino_001",
        "mcc": "7995",
        "decision": "DECLINE",
        "reason": "RULE_MATCH",
        "score": "97.00",
        "risk": "HIGH",
        "hours_ago": 24,
        "rules": [
            {
                "rule_id": RULE_VELOCITY,
                "name": "high_risk_mcc_casino",
                "action": "DECLINE",
                "score": "97.00",
                "match_reason": "Casino/gambling high-risk MCC with large amount",
            },
        ],
    },
    {
        "card_id": "tok_mc_fraud_007",
        "card_last4": "3333",
        "card_network": "MASTERCARD",
        "amount": "299.00",
        "currency": "USD",
        "merchant": "merch_digital_999",
        "mcc": "5816",
        "decision": "DECLINE",
        "reason": "RULE_MATCH",
        "score": "68.00",
        "risk": "MEDIUM",
        "hours_ago": 30,
        "rules": [
            {
                "rule_id": RULE_CARD_TEST,
                "name": "digital_goods_velocity",
                "action": "DECLINE",
                "score": "68.00",
                "match_reason": "High velocity digital goods purchases",
            },
        ],
    },
    {
        "card_id": "tok_visa_fraud_008",
        "card_last4": "8888",
        "card_network": "VISA",
        "amount": "750.00",
        "currency": "CAD",
        "merchant": "merch_atm_withdraw",
        "mcc": "6011",
        "decision": "DECLINE",
        "reason": "RULE_MATCH",
        "score": "82.00",
        "risk": "HIGH",
        "hours_ago": 36,
        "rules": [
            {
                "rule_id": RULE_GEO,
                "name": "atm_withdrawal_abroad",
                "action": "DECLINE",
                "score": "82.00",
                "match_reason": "ATM withdrawal in foreign country shortly after domestic",
            },
        ],
    },
    {
        "card_id": "tok_disc_fraud_009",
        "card_last4": "6543",
        "card_network": "DISCOVER",
        "amount": "1800.00",
        "currency": "USD",
        "merchant": "merch_jewelry_005",
        "mcc": "5944",
        "decision": "DECLINE",
        "reason": "RULE_MATCH",
        "score": "91.00",
        "risk": "HIGH",
        "hours_ago": 42,
        "rules": [
            {
                "rule_id": RULE_BUST_OUT,
                "name": "jewelry_bust_out_pattern",
                "action": "DECLINE",
                "score": "91.00",
                "match_reason": "Jewelry purchase pattern consistent with bust-out",
            },
            {
                "rule_id": RULE_VELOCITY,
                "name": "spend_acceleration",
                "action": "DECLINE",
                "score": "75.00",
                "match_reason": "Spend acceleration detected: 5x normal velocity",
            },
        ],
    },
    {
        "card_id": "tok_visa_fraud_010",
        "card_last4": "2020",
        "card_network": "VISA",
        "amount": "425.00",
        "currency": "USD",
        "merchant": "merch_gift_cards_009",
        "mcc": "5947",
        "decision": "DECLINE",
        "reason": "RULE_MATCH",
        "score": "76.00",
        "risk": "HIGH",
        "hours_ago": 48,
        "rules": [
            {
                "rule_id": RULE_CARD_TEST,
                "name": "gift_card_purchase_fraud",
                "action": "DECLINE",
                "score": "76.00",
                "match_reason": "Gift card purchases: common fraud vector",
            },
        ],
    },
]

# ---------------------------------------------------------------------------
# APPROVE transactions (90) - diverse legitimate purchases
# ---------------------------------------------------------------------------
_APPROVE_TEMPLATES = [
    # Grocery / everyday
    ("VISA", "4111", "merch_wholefds_001", "5411", "48.32", "USD", "LOW", 0.5),
    ("MASTERCARD", "5500", "merch_kroger_002", "5411", "92.15", "USD", "LOW", 1.0),
    ("VISA", "4242", "merch_aldi_003", "5411", "31.50", "GBP", "LOW", 2.0),
    ("AMEX", "3700", "merch_costco_004", "5300", "187.40", "USD", "LOW", 3.0),
    ("VISA", "4444", "merch_target_005", "5311", "65.00", "USD", "LOW", 4.0),
    # Restaurants / cafes
    ("VISA", "4567", "merch_starbucks_001", "5812", "8.50", "USD", "LOW", 5.0),
    ("MASTERCARD", "5432", "merch_mcdonalds_002", "5814", "12.75", "USD", "LOW", 6.0),
    ("VISA", "4899", "merch_chipotle_003", "5812", "15.20", "USD", "LOW", 7.0),
    ("VISA", "4321", "merch_subway_004", "5814", "9.80", "USD", "LOW", 8.0),
    ("AMEX", "3701", "merch_cheesecake_005", "5812", "85.00", "USD", "LOW", 9.0),
    # Fuel / gas
    ("VISA", "4100", "merch_shell_001", "5541", "55.00", "USD", "LOW", 10.0),
    ("MASTERCARD", "5200", "merch_bp_002", "5541", "48.75", "USD", "LOW", 11.0),
    ("VISA", "4200", "merch_chevron_003", "5542", "62.30", "USD", "LOW", 12.0),
    ("VISA", "4300", "merch_exxon_004", "5541", "50.40", "USD", "LOW", 13.0),
    ("DISCOVER", "6011", "merch_speedway_005", "5541", "40.00", "USD", "LOW", 14.0),
    # Entertainment / streaming
    ("VISA", "4500", "merch_netflix_001", "7922", "15.99", "USD", "LOW", 15.0),
    ("MASTERCARD", "5600", "merch_spotify_002", "7922", "9.99", "USD", "LOW", 16.0),
    ("VISA", "4600", "merch_hulu_003", "7922", "17.99", "USD", "LOW", 17.0),
    ("VISA", "4700", "merch_disney_004", "7922", "13.99", "USD", "LOW", 18.0),
    ("AMEX", "3702", "merch_hbo_005", "7922", "15.99", "USD", "LOW", 19.0),
    # Utilities / bills
    ("VISA", "4800", "merch_electric_001", "4911", "125.00", "USD", "LOW", 20.0),
    ("MASTERCARD", "5700", "merch_water_002", "4941", "45.00", "USD", "LOW", 21.0),
    ("VISA", "4900", "merch_telecom_003", "4813", "80.00", "USD", "LOW", 22.0),
    ("VISA", "4001", "merch_internet_004", "4899", "59.99", "USD", "LOW", 23.0),
    ("AMEX", "3703", "merch_insurance_005", "6321", "200.00", "USD", "LOW", 24.0),
    # Healthcare / pharmacy
    ("VISA", "4002", "merch_cvs_001", "5912", "28.50", "USD", "LOW", 25.0),
    ("MASTERCARD", "5800", "merch_walgreens_002", "5912", "42.75", "USD", "LOW", 26.0),
    ("VISA", "4003", "merch_rite_aid_003", "5912", "19.99", "USD", "LOW", 27.0),
    ("VISA", "4004", "merch_doctor_004", "8011", "150.00", "USD", "LOW", 28.0),
    ("AMEX", "3704", "merch_dental_005", "8021", "280.00", "USD", "LOW", 29.0),
    # Online retail (moderate amounts, known merchants)
    ("VISA", "4005", "merch_amazon_001", "5999", "35.00", "USD", "LOW", 30.0),
    ("MASTERCARD", "5900", "merch_amazon_002", "5999", "79.99", "USD", "LOW", 31.0),
    ("VISA", "4006", "merch_etsy_003", "5999", "45.00", "USD", "LOW", 32.0),
    ("VISA", "4007", "merch_ebay_004", "5999", "65.00", "USD", "LOW", 33.0),
    ("AMEX", "3705", "merch_apple_005", "5734", "1.99", "USD", "LOW", 34.0),
    # Transportation
    ("VISA", "4008", "merch_uber_001", "4121", "22.50", "USD", "LOW", 35.0),
    ("MASTERCARD", "5901", "merch_lyft_002", "4121", "18.75", "USD", "LOW", 36.0),
    ("VISA", "4009", "merch_parking_003", "7521", "15.00", "USD", "LOW", 37.0),
    ("VISA", "4010", "merch_metro_004", "4111", "5.00", "USD", "LOW", 38.0),
    ("AMEX", "3706", "merch_airline_005", "4511", "320.00", "USD", "LOW", 39.0),
    # Home / hardware
    ("VISA", "4011", "merch_homeDepot_001", "5251", "142.00", "USD", "LOW", 40.0),
    ("MASTERCARD", "5902", "merch_lowes_002", "5251", "98.50", "USD", "LOW", 41.0),
    ("VISA", "4012", "merch_ikea_003", "5021", "250.00", "USD", "LOW", 42.0),
    ("VISA", "4013", "merch_wayfair_004", "5021", "199.00", "USD", "LOW", 43.0),
    ("AMEX", "3707", "merch_bbeyond_005", "5731", "55.00", "USD", "LOW", 44.0),
    # Clothing / fashion (moderate)
    ("VISA", "4014", "merch_gap_001", "5691", "85.00", "USD", "LOW", 45.0),
    ("MASTERCARD", "5903", "merch_hm_002", "5691", "62.50", "USD", "LOW", 46.0),
    ("VISA", "4015", "merch_zara_003", "5691", "95.00", "USD", "LOW", 47.0),
    ("VISA", "4016", "merch_nike_004", "5661", "110.00", "USD", "LOW", 48.0),
    ("AMEX", "3708", "merch_nordstrom_005", "5311", "175.00", "USD", "LOW", 49.0),
    # Education / books
    ("VISA", "4017", "merch_amazon_books_001", "5942", "24.99", "USD", "LOW", 50.0),
    ("MASTERCARD", "5904", "merch_udemy_002", "8299", "14.99", "USD", "LOW", 51.0),
    ("VISA", "4018", "merch_coursera_003", "8299", "49.00", "USD", "LOW", 52.0),
    ("VISA", "4019", "merch_audible_004", "5942", "14.95", "USD", "LOW", 53.0),
    ("AMEX", "3709", "merch_kindle_005", "5942", "9.99", "USD", "LOW", 54.0),
    # Hotels / accommodation
    ("VISA", "4020", "merch_marriott_001", "7011", "199.00", "USD", "LOW", 55.0),
    ("MASTERCARD", "5905", "merch_hilton_002", "7011", "189.00", "USD", "LOW", 56.0),
    ("VISA", "4021", "merch_airbnb_003", "7011", "145.00", "USD", "LOW", 57.0),
    ("VISA", "4022", "merch_hampton_004", "7011", "130.00", "USD", "LOW", 58.0),
    ("AMEX", "3710", "merch_westin_005", "7011", "250.00", "USD", "LOW", 59.0),
    # Fitness / sport
    ("VISA", "4023", "merch_peloton_001", "7997", "44.00", "USD", "LOW", 60.0),
    ("MASTERCARD", "5906", "merch_gymshark_002", "5699", "75.00", "USD", "LOW", 61.0),
    ("VISA", "4024", "merch_orange_003", "7997", "30.00", "USD", "LOW", 62.0),
    ("VISA", "4025", "merch_lifetime_004", "7997", "120.00", "USD", "LOW", 63.0),
    ("AMEX", "3711", "merch_tennis_005", "5941", "95.00", "USD", "LOW", 64.0),
    # Pet supplies
    ("VISA", "4026", "merch_chewy_001", "5995", "68.00", "USD", "LOW", 65.0),
    ("MASTERCARD", "5907", "merch_petco_002", "5995", "45.00", "USD", "LOW", 66.0),
    ("VISA", "4027", "merch_petsmart_003", "5995", "52.50", "USD", "LOW", 67.0),
    # International / forex (normal amounts)
    ("VISA", "4028", "merch_google_uk_001", "7372", "12.99", "GBP", "LOW", 68.0),
    ("MASTERCARD", "5908", "merch_amazon_de_002", "5999", "55.00", "EUR", "LOW", 69.0),
    ("VISA", "4029", "merch_zalando_003", "5691", "89.99", "EUR", "LOW", 70.0),
    ("VISA", "4030", "merch_booking_004", "7011", "220.00", "EUR", "LOW", 71.0),
    ("AMEX", "3712", "merch_expedia_005", "4722", "380.00", "USD", "LOW", 72.0),
    # SaaS / software
    ("VISA", "4031", "merch_adobe_001", "7372", "54.99", "USD", "LOW", 73.0),
    ("MASTERCARD", "5909", "merch_msft_002", "7372", "9.99", "USD", "LOW", 74.0),
    ("VISA", "4032", "merch_slack_003", "7372", "12.50", "USD", "LOW", 75.0),
    ("VISA", "4033", "merch_dropbox_004", "7372", "11.99", "USD", "LOW", 76.0),
    ("AMEX", "3713", "merch_zoom_005", "7372", "14.99", "USD", "LOW", 77.0),
    # Dining out
    ("VISA", "4034", "merch_panera_001", "5812", "18.50", "USD", "LOW", 78.0),
    ("MASTERCARD", "5910", "merch_olive_002", "5812", "65.00", "USD", "LOW", 79.0),
    ("VISA", "4035", "merch_sushi_003", "5812", "55.00", "USD", "LOW", 80.0),
    ("VISA", "4036", "merch_pizza_004", "5812", "32.00", "USD", "LOW", 81.0),
    ("AMEX", "3714", "merch_steakhouse_005", "5812", "180.00", "USD", "LOW", 82.0),
    # Charity / donations
    ("VISA", "4037", "merch_redcross_001", "8398", "25.00", "USD", "LOW", 83.0),
    ("MASTERCARD", "5911", "merch_unicef_002", "8398", "50.00", "USD", "LOW", 84.0),
    # Financial services (legitimate)
    ("VISA", "4038", "merch_paypal_001", "6012", "200.00", "USD", "LOW", 85.0),
    ("MASTERCARD", "5912", "merch_venmo_002", "6012", "75.00", "USD", "LOW", 86.0),
    # Miscellaneous
    ("VISA", "4039", "merch_post_001", "7399", "18.00", "USD", "LOW", 87.0),
    ("MASTERCARD", "5913", "merch_cleaners_002", "7216", "35.00", "USD", "LOW", 88.0),
    ("VISA", "4040", "merch_florist_003", "5992", "75.00", "USD", "LOW", 89.0),
    ("VISA", "4041", "merch_bookstore_004", "5942", "42.00", "USD", "LOW", 90.0),
]


def _build_approves() -> list[dict]:
    approves = []
    for i, tmpl in enumerate(_APPROVE_TEMPLATES):
        network, last4, merchant, mcc, amount, currency, risk, hours_ago = tmpl
        approves.append(
            {
                "card_id": f"tok_{network.lower()}_good_{i:03d}",
                "card_last4": last4,
                "card_network": network,
                "amount": amount,
                "currency": currency,
                "merchant": merchant,
                "mcc": mcc,
                "decision": "APPROVE",
                "reason": "DEFAULT_ALLOW",
                "score": f"{random.uniform(5.0, 25.0):.2f}",
                "risk": risk,
                "hours_ago": hours_ago,
                "rules": [],
            }
        )
    return approves


def _stable_uuid7(label: str) -> uuid.UUID:
    """Build a deterministic UUIDv7 from a stable label."""
    digest = hashlib.sha256(label.encode("utf-8")).digest()
    raw = bytearray(digest[:16])
    raw[0:6] = SEED_UUID7_EPOCH_MS.to_bytes(6, "big")
    raw[6] = (raw[6] & 0x0F) | 0x70
    raw[8] = (raw[8] & 0x3F) | 0x80
    return uuid.UUID(bytes=bytes(raw))


def _build_transactions() -> list[dict]:
    all_txns = []
    for index, tmpl in enumerate(DECLINES + _build_approves()):
        seed_key = (
            f"{index}:{tmpl['card_id']}:{tmpl['merchant']}:{tmpl['hours_ago']}:{tmpl['decision']}"
        )
        all_txns.append(
            {
                "id": _stable_uuid7(f"seed:id:{seed_key}"),
                "transaction_id": _stable_uuid7(f"seed:transaction_id:{seed_key}"),
                "evaluation_type": "AUTH",
                **tmpl,
            }
        )
    return all_txns


async def seed_transactions() -> None:
    database_url = os.environ.get("DATABASE_URL_ADMIN") or os.environ.get("DATABASE_URL_APP")
    if not database_url:
        logger.error("DATABASE_URL_ADMIN or DATABASE_URL_APP not set. Run via Doppler.")
        sys.exit(1)

    if database_url.startswith("postgresql://") and "+asyncpg" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(database_url, echo=False)
    transactions = _build_transactions()

    async with engine.begin() as conn:
        inserted_txns = 0
        inserted_rules = 0

        for txn in transactions:
            rules = txn["rules"]
            raw_payload = json.dumps(
                {
                    "transaction_id": str(txn["transaction_id"]),
                    "amount": txn["amount"],
                    "merchant_id": txn["merchant"],
                    "seed": True,
                }
            )

            result = await conn.execute(
                text("""
                    INSERT INTO fraud_gov.transactions (
                        id, transaction_id, evaluation_type,
                        card_id, card_last4, card_network,
                        transaction_amount, transaction_currency,
                        merchant_id, merchant_category_code,
                        decision, decision_reason, decision_score,
                        risk_level, ruleset_id, ruleset_version,
                        transaction_timestamp, trace_id,
                        raw_payload, ingestion_source
                    ) VALUES (
                        :id, :transaction_id, :evaluation_type,
                        :card_id, :card_last4, :card_network,
                        :amount, :currency,
                        :merchant, :mcc,
                        :decision, :reason, :score,
                        :risk, :ruleset_id, 3,
                        :ts, :trace_id,
                        :raw_payload, 'HTTP'
                    )
                    ON CONFLICT DO NOTHING
                """),
                {
                    "id": str(txn["id"]),
                    "transaction_id": str(txn["transaction_id"]),
                    "evaluation_type": txn["evaluation_type"],
                    "card_id": txn["card_id"],
                    "card_last4": txn["card_last4"],
                    "card_network": txn["card_network"],
                    "amount": txn["amount"],
                    "currency": txn["currency"],
                    "merchant": txn["merchant"],
                    "mcc": txn["mcc"],
                    "decision": txn["decision"],
                    "reason": txn["reason"],
                    "score": txn["score"],
                    "risk": txn["risk"],
                    "ruleset_id": str(RULESET_ID),
                    "ts": NOW - timedelta(hours=txn["hours_ago"]),
                    "trace_id": f"trace-seed-{str(txn['id'])[:8]}",
                    "raw_payload": raw_payload,
                },
            )
            if result.rowcount > 0:
                inserted_txns += 1

            txn_pk = str(txn["id"])
            for rule in rules:
                rule_version_id = _stable_uuid7(
                    f"seed:rule_version_id:{txn_pk}:{str(rule['rule_id'])}:v3"
                )
                rule_result = await conn.execute(
                    text("""
                        INSERT INTO fraud_gov.transaction_rule_matches (
                            transaction_id, rule_id, rule_version_id, rule_version,
                            rule_name, rule_action, matched, contributing,
                            match_score, match_reason, evaluated_at
                        ) VALUES (
                            :transaction_id, :rule_id, :rule_version_id, 3,
                            :rule_name, :rule_action, TRUE, TRUE,
                            :match_score, :match_reason, NOW()
                        )
                        ON CONFLICT (transaction_id, rule_id, rule_version) DO NOTHING
                    """),
                    {
                        "transaction_id": txn_pk,
                        "rule_id": str(rule["rule_id"]),
                        "rule_version_id": str(rule_version_id),
                        "rule_name": rule["name"],
                        "rule_action": rule["action"],
                        "match_score": rule["score"],
                        "match_reason": rule["match_reason"],
                    },
                )
                if rule_result.rowcount > 0:
                    inserted_rules += 1

    await engine.dispose()

    declines = [t for t in transactions if t["decision"] == "DECLINE"]
    approves = [t for t in transactions if t["decision"] == "APPROVE"]

    logger.info("")
    logger.info("=" * 60)
    logger.info(
        "Seed complete: %d total (%d DECLINE, %d APPROVE), %d rule matches",
        inserted_txns,
        len(declines),
        len(approves),
        inserted_rules,
    )
    logger.info("")
    logger.info("DECLINE transaction_ids (for ops-agent e2e):")
    for t in declines:
        logger.info(
            "  %s  score=%-5s  rule=%s",
            t["transaction_id"],
            t["score"],
            t["rules"][0]["name"] if t.get("rules") else "n/a",
        )
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(seed_transactions())

