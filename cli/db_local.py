from __future__ import annotations

import subprocess
import sys

from cli._constants import PROJECT_PREFIX

_COMPOSE_FILE = "docker-compose.local.yml"

# Infrastructure containers (match shared platform)
INFRA_CONTAINERS = [
    "card-fraud-postgres",
    "card-fraud-minio",
    "card-fraud-redis",
    "card-fraud-redpanda",
    "card-fraud-redpanda-console",
]

POSTGRES_CONTAINER = "card-fraud-postgres"
MINIO_CONTAINER = "card-fraud-minio"
REDIS_CONTAINER = "card-fraud-redis"
REDPANDA_CONTAINER = "card-fraud-redpanda"


def _is_container_running(name: str) -> bool:
    """Check if a container is running."""
    result = subprocess.run(
        ["docker", "inspect", "--format", "{{.State.Status}}", name],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "running"


def _get_running_containers() -> dict[str, bool]:
    """Check which infrastructure containers are already running."""
    status = {}
    for name in INFRA_CONTAINERS:
        status[name] = _is_container_running(name)
    return status


def _print_status(status: dict[str, bool]) -> None:
    """Print container status table."""
    print()
    print("=" * 60)
    print(f"  {'Container':<35} {'Status':<15}")
    print("-" * 60)
    for name, running in status.items():
        icon = "[OK]" if running else "[--]"
        state = "running" if running else "stopped"
        print(f"  {icon} {name:<31} {state}")
    print("=" * 60)


def _run_compose(
    services: str | list[str],
    action: str,
    volumes: bool = False,
    detached: bool = True,
) -> int:
    """Run docker compose for services."""
    service_args = services.split() if isinstance(services, str) else services
    cmd = [
        "docker", "compose",
        "-f", _COMPOSE_FILE,
        "-p", PROJECT_PREFIX,
        action,
    ]
    if detached:
        cmd.append("-d")
    if volumes:
        cmd.append("-v")
    cmd.extend(service_args)
    print(f"  > {' '.join(cmd)}")
    return subprocess.run(cmd, check=False).returncode


def up() -> None:
    """Start local PostgreSQL via Docker."""
    if _is_container_running(POSTGRES_CONTAINER):
        print(f"[OK] PostgreSQL already running ({POSTGRES_CONTAINER})")
        print("     Endpoint: postgresql://localhost:5432/fraud_gov")
        return
    print("Starting PostgreSQL...")
    result = _run_compose(["postgres"], "up", volumes=False)
    sys.exit(result)


def down() -> None:
    """Stop local PostgreSQL via Docker."""
    if _is_container_running(POSTGRES_CONTAINER):
        print("[INFO] To stop: cd ../card-fraud-platform && uv run platform-down")
        print("       (only stops containers started by this project)")
        return
    print("PostgreSQL is not running or managed by platform")
    return


def reset() -> None:
    """Reset local PostgreSQL (stop + start). THIS PROJECT ONLY."""
    print("Resetting PostgreSQL...")
    print("WARNING: This only affects THIS project's tables")
    print("         (fraud_gov.transactions, fraud_gov.transaction_rule_reviews, etc.)")
    _run_compose(["postgres"], "down", volumes=False, detached=False)
    result = _run_compose(["postgres"], "up", volumes=False)
    sys.exit(result)


def redis_up() -> None:
    """Start Redis via Docker."""
    if _is_container_running(REDIS_CONTAINER):
        print(f"[OK] Redis already running ({REDIS_CONTAINER})")
        print("     Endpoint: redis://localhost:6379")
        return
    print("Starting Redis...")
    result = _run_compose(["redis"], "up", volumes=False)
    sys.exit(result)


def redis_down() -> None:
    """Stop Redis via Docker."""
    if _is_container_running(REDIS_CONTAINER):
        print("[INFO] To stop: cd ../card-fraud-platform && uv run platform-down")
        return
    print("Redis is not running or managed by platform")
    return


def kafka_up() -> None:
    """Start Redpanda (Kafka-compatible) via Docker."""
    if _is_container_running(REDPANDA_CONTAINER):
        print(f"[OK] Redpanda already running ({REDPANDA_CONTAINER})")
        print("     Kafka: localhost:9092")
        print("     Console: http://localhost:8083")
        return
    print("Starting Redpanda...")
    result = _run_compose(["redpanda", "redpanda-console"], "up", volumes=False)
    sys.exit(result)


def kafka_down() -> None:
    """Stop Redpanda via Docker."""
    if _is_container_running(REDPANDA_CONTAINER):
        print("[INFO] To stop: cd ../card-fraud-platform && uv run platform-down")
        return
    print("Redpanda is not running or managed by platform")
    return


def kafka_reset() -> None:
    """Reset Redpanda (stop + start). THIS PROJECT ONLY."""
    print("Resetting Redpanda...")
    print("WARNING: This only affects THIS project's topics")
    _run_compose(["redpanda", "redpanda-console"], "down", volumes=False, detached=False)
    result = _run_compose(["redpanda", "redpanda-console"], "up", volumes=False)
    sys.exit(result)


def infra_up() -> None:
    """Start all local infrastructure (PostgreSQL + MinIO + Redis + Redpanda)."""
    status = _get_running_containers()
    running_count = sum(1 for v in status.values() if v)
    total = len(INFRA_CONTAINERS)

    if running_count == total:
        print(f"[OK] All {total} infrastructure containers already running")
        _print_status(status)
        return

    if running_count > 0:
        print(f"{running_count}/{total} containers already running.")
        print("Starting remaining containers...")
    else:
        print(f"Starting all {total} infrastructure containers...")

    result = _run_compose(
        ["postgres", "minio", "minio-init", "redis", "redpanda", "redpanda-console"],
        "up",
        volumes=False
    )
    sys.exit(result)


def infra_down() -> None:
    """Stop all local infrastructure started by this project."""
    remove_volumes = "-v" in sys.argv[1:] or "--volumes" in sys.argv[1:]
    print("Stopping infrastructure containers...")
    if remove_volumes:
        print("(removing volumes)")
    else:
        print("(volumes preserved)")
    result = _run_compose(
        ["postgres", "minio", "minio-init", "redis", "redpanda", "redpanda-console"],
        "down",
        volumes=remove_volumes,
        detached=False,
    )
    sys.exit(result)
