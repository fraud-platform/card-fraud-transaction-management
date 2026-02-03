#!/usr/bin/env python3
"""
Redpanda (Kafka) helper commands for local development.

Usage:
    python scripts/setup_kafka.py create-topics    # Create decision events topic
    python scripts/setup_kafka.py list-topics      # List existing topics
    python scripts/setup_kafka.py produce          # Produce test message
    python scripts/setup_kafka.py consume          # Consume messages
    python scripts/setup_kafka.py reset            # Reset topics
    python scripts/setup_kafka.py health           # Check Redpanda health
"""

from __future__ import annotations

import json
import subprocess
import sys
import time

import httpx

REDPANDA_ADMIN_URL = "http://localhost:8082"
REDPANDA_KAFKA_URL = "localhost:9092"
DECISIONS_TOPIC = "fraud.card.decisions.v1"


def _get_container_name() -> str:
    """Get Redpanda container name (dynamic based on project)."""
    result = subprocess.run(
        ["docker", "ps", "--filter", "name=redpanda", "-q"],
        capture_output=True,
        encoding="utf-8",
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return "card-fraud-transaction-management-redpanda-1"


def _rpk(*args: str) -> subprocess.CompletedProcess:
    """Run rpk (Redpanda CLI) inside the container."""
    container = _get_container_name()
    cmd = ["docker", "exec", "-i", container, "rpk", "-X", f"brokers={REDPANDA_KAFKA_URL}", *args]
    return subprocess.run(cmd, check=False, capture_output=True, encoding="utf-8")


def cmd_create_topics() -> int:
    """Create required Kafka topics."""
    print(f"Creating topic: {DECISIONS_TOPIC}")

    result = _rpk(
        "topic",
        "create",
        DECISIONS_TOPIC,
        "-p",
        "3",
        "-r",
        "1",
    )

    if result.returncode != 0:
        print(f"Warning: {result.stderr}")

    dlq_topic = f"{DECISIONS_TOPIC}.dlq.local"
    print(f"Creating DLQ topic: {dlq_topic}")
    _rpk("topic", "create", dlq_topic, "-p", "3", "-r", "1")

    return cmd_list_topics()


def cmd_list_topics() -> int:
    """List existing Kafka topics."""
    print("\nKafka Topics:")
    result = _rpk("topic", "list")
    print(result.stdout or result.stderr)
    return 0


def cmd_produce() -> int:
    """Produce a test decision event."""
    test_event = {
        "event_version": "1.0",
        "transaction_id": f"txn_local_{int(time.time())}",
        "occurred_at": "2026-01-18T10:00:00Z",
        "produced_at": "2026-01-18T10:00:01Z",
        "transaction": {
            "card_id": "tok_visa_test123",
            "card_last4": "4242",
            "card_network": "VISA",
            "amount": 99.99,
            "currency": "USD",
            "country": "US",
            "merchant_id": "merch_test",
            "mcc": "5411",
        },
        "decision": "DECLINE",
        "decision_reason": "RULE_MATCH",
        "matched_rules": [
            {
                "rule_id": "rule_test_001",
                "rule_version": 1,
                "priority": 100,
            }
        ],
    }

    print(f"\nProducing to topic: {DECISIONS_TOPIC}")
    print(json.dumps(test_event, indent=2))

    event_json = json.dumps(test_event)
    result = subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            _get_container_name(),
            "rpk",
            "-X",
            f"brokers={REDPANDA_KAFKA_URL}",
            "topic",
            "produce",
            DECISIONS_TOPIC,
            "--key",
            test_event["transaction_id"],
            "--format",
            "json",
        ],
        input=event_json,
        capture_output=True,
        encoding="utf-8",
    )

    print(f"\nResult: {'Success' if result.returncode == 0 else 'Failed'}")
    if result.stderr:
        print(result.stderr)

    return 0


def cmd_consume() -> int:
    """Consume messages from decision events topic."""
    print(f"\nConsuming from: {DECISIONS_TOPIC} (Ctrl+C to stop)")
    result = _rpk("topic", "consume", DECISIONS_TOPIC, "--num", "10")
    print(result.stdout or result.stderr)
    return result.returncode


def cmd_reset() -> int:
    """Delete and recreate topics."""
    print(f"\nResetting topic: {DECISIONS_TOPIC}")
    _rpk("topic", "delete", DECISIONS_TOPIC)
    return cmd_create_topics()


def cmd_health() -> int:
    """Check Redpanda health."""
    try:
        resp = httpx.get(f"{REDPANDA_ADMIN_URL}/health", timeout=5)
        status = resp.json().get("status", "unknown")
        print(f"\nRedpanda Health: {status}")
        return 0 if status == "ok" else 1
    except Exception as e:
        print(f"\nRedpanda Health Check Failed: {e}")
        return 1


def main() -> int:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Redpanda/Kafka local development helper")
    parser.add_argument(
        "command",
        choices=["create-topics", "list-topics", "produce", "consume", "reset", "health"],
        help="Command to run",
    )

    args = parser.parse_args()

    match args.command:
        case "create-topics":
            return cmd_create_topics()
        case "list-topics":
            return cmd_list_topics()
        case "produce":
            return cmd_produce()
        case "consume":
            return cmd_consume()
        case "reset":
            return cmd_reset()
        case "health":
            return cmd_health()

    return 1


if __name__ == "__main__":
    sys.exit(main())
