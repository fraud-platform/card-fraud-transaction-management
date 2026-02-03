from __future__ import annotations

import subprocess
import sys

from cli._constants import PROJECT_PREFIX

_COMPOSE_FILE = "docker-compose.local.yml"
MINIO_CONTAINER = "card-fraud-minio"


def _is_container_running(name: str) -> bool:
    """Check if a container is running."""
    result = subprocess.run(
        ["docker", "inspect", "--format", "{{.State.Status}}", name],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "running"


def _run_compose(action: str, volumes: bool = False, detached: bool = True) -> int:
    """Run docker compose for MinIO services."""
    cmd = [
        "docker",
        "compose",
        "-f",
        _COMPOSE_FILE,
        "-p",
        PROJECT_PREFIX,
        action,
    ]
    if detached:
        cmd.append("-d")
    if volumes:
        cmd.append("-v")
    cmd.extend(["minio", "minio-init"])
    print(f"  > {' '.join(cmd)}")
    return subprocess.run(cmd, check=False).returncode


def up() -> None:
    """Start local MinIO object storage."""
    if _is_container_running(MINIO_CONTAINER):
        print(f"[OK] MinIO already running ({MINIO_CONTAINER})")
        print("     API: http://localhost:9000")
        print("     Console: http://localhost:9001")
        return
    print("Starting MinIO...")
    sys.exit(_run_compose("up", volumes=False))


def down() -> None:
    """Stop local MinIO object storage."""
    if not _is_container_running(MINIO_CONTAINER):
        print("MinIO is not running")
        return
    print("Stopping MinIO (volumes preserved)...")
    sys.exit(_run_compose("down", volumes=False, detached=False))


def reset() -> None:
    """Reset local MinIO object storage and remove volumes."""
    print("Resetting MinIO and removing object storage data volumes...")
    sys.exit(_run_compose("down", volumes=True, detached=False))


def verify() -> None:
    """Verify MinIO availability."""
    if _is_container_running(MINIO_CONTAINER):
        print(f"[OK] MinIO is running ({MINIO_CONTAINER})")
        print("     API: http://localhost:9000")
        print("     Console: http://localhost:9001")
        return

    print("[ERROR] MinIO is not running")
    print("        Start with: uv run objstore-local-up")
    sys.exit(1)
