#!/usr/bin/env python3
"""
Card Fraud Transaction Management — Local Full Setup

This script orchestrates:
1. Start Docker containers (PostgreSQL + MinIO)
2. Initialize database schema
3. Verify setup

Usage:
    python scripts/local_full_setup.py --yes          # Full setup
    python scripts/local_full_setup.py --reset --yes  # Reset and setup
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_COMPOSE_FILE = Path(__file__).parent.parent / "docker-compose.local.yml"
_SETUP_SCRIPT = Path(__file__).parent / "setup_database.py"


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return result."""
    print(f"Running: {' '.join(cmd)}")
    return subprocess.run(cmd, check=check)


def infra_up() -> None:
    """Start Docker infrastructure."""
    _run(["docker", "compose", "-f", str(_COMPOSE_FILE), "up", "-d"])


def infra_down() -> None:
    """Stop Docker infrastructure."""
    _run(["docker", "compose", "-f", str(_COMPOSE_FILE), "down", "-v"])


def db_init(demo: bool = False) -> None:
    """Initialize database."""
    cmd = [sys.executable, str(_SETUP_SCRIPT), "init", "--yes"]
    if demo:
        cmd.append("--demo")
    _run(cmd)


def db_reset() -> None:
    """Reset database schema."""
    _run([sys.executable, str(_SETUP_SCRIPT), "reset", "--mode", "schema", "--yes"])


def db_verify() -> None:
    """Verify database setup."""
    _run([sys.executable, str(_SETUP_SCRIPT), "verify"])


def local_full_setup(reset: bool = False, demo: bool = False) -> int:
    """Full local setup orchestration."""
    print("=" * 60)
    print("Card Fraud Transaction Management — Local Full Setup")
    print("=" * 60)

    try:
        # Step 1: Infrastructure
        print("\n[1/4] Starting Docker infrastructure...")
        infra_up()
        print("  PostgreSQL and MinIO started.")

        # Step 2: Database
        print("\n[2/4] Setting up database...")
        if reset:
            db_reset()
        db_init(demo=demo)
        print("  Database initialized.")

        # Step 3: Verify
        print("\n[3/4] Verifying setup...")
        db_verify()
        print("  Setup verified.")

        print("\n" + "=" * 60)
        print("Setup complete!")
        print("=" * 60)
        return 0

    except subprocess.CalledProcessError as e:
        print(f"\nError during setup: {e}")
        return 1


def main() -> int:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Local full setup for card-fraud-transaction-management"
    )
    parser.add_argument("--reset", action="store_true", help="Reset database before setup")
    parser.add_argument("--demo", action="store_true", help="Include demo data")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    parser.add_argument("--help", "-h", action="store_true", help="Show help")

    args = parser.parse_args()

    if args.help:
        parser.print_help()
        return 0

    if not args.yes:
        response = input("Start local setup? [y/N]: ")
        if response.lower() != "y":
            print("Aborted.")
            return 1

    return local_full_setup(reset=args.reset, demo=args.demo)


if __name__ == "__main__":
    sys.exit(main())
