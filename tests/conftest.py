"""Pytest configuration and fixtures."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Add app to path for imports
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Set test environment variables before importing app
# Unit tests use mocks, so these are just defaults
os.environ.setdefault("AUTH0_DOMAIN", "test.local")
os.environ.setdefault("AUTH0_AUDIENCE", "https://fraud-transaction-management-api")
os.environ.setdefault("AUTH0_ALGORITHMS", "RS256")


# =============================================================================
# Mock Token Payloads (matching AUTH_MODEL.md role/permission structure)
# =============================================================================

# Namespace for roles claim (matches Auth0 configuration)
ROLES_CLAIM = "https://fraud-transaction-management-api/roles"

# Platform Admin - full access
MOCK_PLATFORM_ADMIN_TOKEN = {
    "sub": "auth0|test-platform-admin",
    "email": "test-platform-admin@fraud-platform.test",
    ROLES_CLAIM: ["PLATFORM_ADMIN"],
    "permissions": [
        "txn:view",
        "txn:comment",
        "txn:flag",
        "txn:recommend",
        "txn:approve",
        "txn:block",
        "txn:override",
    ],
    "exp": 9999999999,
}

# Fraud Analyst - view, comment, flag, recommend
MOCK_FRAUD_ANALYST_TOKEN = {
    "sub": "auth0|test-fraud-analyst",
    "email": "test-fraud-analyst@fraud-platform.test",
    ROLES_CLAIM: ["FRAUD_ANALYST"],
    "permissions": ["txn:view", "txn:comment", "txn:flag", "txn:recommend"],
    "exp": 9999999999,
}

# Fraud Supervisor - view, approve, block, override
MOCK_FRAUD_SUPERVISOR_TOKEN = {
    "sub": "auth0|test-fraud-supervisor",
    "email": "test-fraud-supervisor@fraud-platform.test",
    ROLES_CLAIM: ["FRAUD_SUPERVISOR"],
    "permissions": ["txn:view", "txn:approve", "txn:block", "txn:override"],
    "exp": 9999999999,
}

# User with no roles (authenticated but no permissions)
MOCK_NO_ROLE_TOKEN = {
    "sub": "auth0|test-no-role",
    "email": "test-no-role@fraud-platform.test",
    ROLES_CLAIM: [],
    "permissions": [],
    "exp": 9999999999,
}

# User with view-only permission
MOCK_VIEW_ONLY_TOKEN = {
    "sub": "auth0|test-view-only",
    "email": "test-view-only@fraud-platform.test",
    ROLES_CLAIM: [],
    "permissions": ["txn:view"],
    "exp": 9999999999,
}

from app.schemas.decision_event import (
    CardNetwork,
    DecisionEventCreate,
    DecisionReason,
    DecisionType,
    EvaluationType,
    RuleMatch,
    TransactionDetails,
)


@pytest.fixture
def sample_decision_event() -> DecisionEventCreate:
    """Sample decision event for testing."""
    return DecisionEventCreate(
        event_version="1.0",
        transaction_id="txn_test_001",
        occurred_at=datetime.utcnow(),
        produced_at=datetime.utcnow(),
        evaluation_type=EvaluationType.AUTH,
        transaction=TransactionDetails(
            card_id="tok_visa_42424242",
            card_last4="4242",
            card_network=CardNetwork.VISA,
            amount=Decimal("99.99"),
            currency="USD",
            country="US",
            merchant_id="merch_test_001",
            mcc="5411",
            ip_address="192.168.1.100",
        ),
        decision=DecisionType.DECLINE,
        decision_reason=DecisionReason.RULE_MATCH,
        matched_rules=[
            RuleMatch(
                rule_id="rule_high_value",
                rule_version=1,
                priority=100,
                rule_name="High Value Transaction",
            )
        ],
        raw_payload={"transaction_id": "txn_test_001", "amount": 99.99},
    )


@pytest.fixture
def sample_transaction_data() -> dict:
    """Sample transaction data dict for testing."""
    return {
        "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "transaction_id": "txn_test_002",
        "event_version": "1.0",
        "occurred_at": datetime.utcnow(),
        "produced_at": datetime.utcnow(),
        "card_id": "tok_visa_42424242",
        "card_last4": "4242",
        "card_network": "VISA",
        "amount": 99.99,
        "currency": "USD",
        "country": "US",
        "merchant_id": "merch_test_001",
        "mcc": "5411",
        "ip_address": "192.168.1.100",
        "decision": "DECLINE",
        "decision_reason": "RULE_MATCH",
        "trace_id": "trace_001",
        "raw_payload": {"transaction_id": "txn_test_002"},
        "ingestion_source": "HTTP",
    }


@pytest.fixture
def mock_session():
    """Mock async database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


# =============================================================================
# Mock User Fixtures
# =============================================================================


@pytest.fixture
def mock_platform_admin_user():
    """Mock platform admin user payload."""
    return MOCK_PLATFORM_ADMIN_TOKEN.copy()


@pytest.fixture
def mock_fraud_analyst_user():
    """Mock fraud analyst user payload."""
    return MOCK_FRAUD_ANALYST_TOKEN.copy()


@pytest.fixture
def mock_fraud_supervisor_user():
    """Mock fraud supervisor user payload."""
    return MOCK_FRAUD_SUPERVISOR_TOKEN.copy()


@pytest.fixture
def mock_no_role_user():
    """Mock user with no roles."""
    return MOCK_NO_ROLE_TOKEN.copy()


@pytest.fixture
def mock_view_only_user():
    """Mock user with view-only permission."""
    return MOCK_VIEW_ONLY_TOKEN.copy()
