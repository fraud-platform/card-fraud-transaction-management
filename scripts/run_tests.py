#!/usr/bin/env python3
"""Run tests with Doppler secrets injection.

This script is called by:
- uv run doppler-local-test → Doppler injects DATABASE_URL → this script runs pytest
- uv run doppler-test → Doppler injects DATABASE_URL → this script runs pytest
- uv run doppler-prod → Doppler injects DATABASE_URL → this script runs pytest

The DATABASE_URL environment variable is provided by Doppler.
"""

from __future__ import annotations

import subprocess
import sys


def run_pytest(marker: str | None = None) -> int:
    """Run pytest with optional marker filter."""
    cmd = ["uv", "run", "pytest"]

    if marker:
        cmd.extend(["-m", marker])

    return subprocess.run(cmd, check=False).returncode


def main() -> int:
    """Main entry point."""
    import argparse
    import os

    # For local config, force JWT validation ON during tests.
    # This keeps auth integration tests meaningful even if dev bypass is enabled.
    if os.getenv("DOPPLER_CONFIG") == "local":
        os.environ["SECURITY_SKIP_JWT_VALIDATION"] = "false"

    parser = argparse.ArgumentParser(description="Run tests")
    parser.add_argument(
        "--marker",
        choices=["unit", "smoke", "integration", "e2e_integration"],
        default=None,
        help="Run tests with specific marker (default: all except e2e_integration)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all tests including e2e_integration",
    )

    args = parser.parse_args()

    marker = None
    if args.all:
        marker = None  # Run all
    elif args.marker:
        marker = args.marker
    else:
        marker = "not e2e_integration"  # Default: exclude e2e

    return run_pytest(marker=marker)


if __name__ == "__main__":
    sys.exit(main())
