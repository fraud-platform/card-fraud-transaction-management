"""
Database setup commands with Doppler integration.

These commands wrap setup_database.py with Doppler to inject environment variables.

Usage:
    uv run neon-setup       # Create Neon project/branches
    uv run db-init          # First-time setup (local)
    uv run db-init-test     # First-time setup (test)
    uv run db-reset-data    # Data reset
    uv run db-reset-schema  # Schema reset
    uv run db-verify        # Verify setup
    uv run db-seed-demo     # Seed with demo data
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from cli._runner import run_doppler

_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
_SETUP_DB_SCRIPT = _SCRIPTS_DIR / "setup_database.py"
_SETUP_NEON_SCRIPT = _SCRIPTS_DIR / "setup_neon.py"
_SYNC_DOPPLER_DB_URLS_SCRIPT = _SCRIPTS_DIR / "sync_doppler_db_urls.py"
_NEON_FULL_SETUP_SCRIPT = _SCRIPTS_DIR / "neon_full_setup.py"
_LOCAL_FULL_SETUP_SCRIPT = _SCRIPTS_DIR / "local_full_setup.py"


def _validated_passthrough_args(
    raw_args: list[str],
    *,
    allowed_flags: dict[str, int],
    command_name: str,
) -> list[str]:
    """Validate and return a safe subset of CLI args."""
    filtered: list[str] = []
    i = 0
    while i < len(raw_args):
        token = raw_args[i]
        if not token.startswith("-"):
            raise SystemExit(
                f"Unexpected positional argument '{token}' for {command_name}. "
                "Only supported flags are allowed."
            )

        if token not in allowed_flags:
            allowed = " ".join(sorted(allowed_flags.keys()))
            raise SystemExit(f"Unsupported flag '{token}' for {command_name}. Allowed: {allowed}")

        filtered.append(token)
        value_count = allowed_flags[token]
        if value_count:
            if i + value_count >= len(raw_args) + 1:
                raise SystemExit(
                    f"Flag '{token}' for {command_name} requires {value_count} value(s)."
                )
            for _ in range(value_count):
                i += 1
                filtered.append(raw_args[i])

        i += 1

    return filtered


def _run_db_reset(config: str, mode: str, *extra_args: str) -> int:
    """Run database reset with specified config and mode."""
    cmd = [sys.executable, str(_SETUP_DB_SCRIPT), "--yes", "reset", "--mode", mode, *extra_args]
    return run_doppler(config, cmd)


def _run_db_init(config: str, *extra_args: str) -> int:
    """Run database init with specified config."""
    cmd = [sys.executable, str(_SETUP_DB_SCRIPT), *extra_args]
    return run_doppler(config, cmd)


def _run_db_verify(config: str) -> int:
    """Run database verify with specified config."""
    return run_doppler(config, [sys.executable, str(_SETUP_DB_SCRIPT), "verify"])


def local_full_setup() -> None:
    """Full local setup: start Docker PostgreSQL, init DB, verify."""
    passthrough = _validated_passthrough_args(
        sys.argv[1:],
        allowed_flags={
            "--yes": 0,
            "-y": 0,
            "--reset": 0,
            "--help": 0,
            "-h": 0,
        },
        command_name="local-full-setup",
    )
    sys.exit(
        subprocess.run(
            [sys.executable, str(_LOCAL_FULL_SETUP_SCRIPT), *passthrough],
            check=False,
        ).returncode
    )


def neon_setup() -> None:
    """Create Neon project and branches via API."""
    passthrough = _validated_passthrough_args(
        sys.argv[1:],
        allowed_flags={
            "--yes": 0,
            "-y": 0,
            "--delete-project": 0,
            "--create-compute": 0,
            "--project-name": 1,
        },
        command_name="neon-setup",
    )
    sys.exit(
        run_doppler(
            "local",
            [sys.executable, str(_SETUP_NEON_SCRIPT), *passthrough],
        )
    )


def neon_full_setup() -> None:
    """Full Neon setup: delete/create project, sync Doppler, init DBs, verify."""
    passthrough = _validated_passthrough_args(
        sys.argv[1:],
        allowed_flags={
            "--yes": 0,
            "-y": 0,
            "--config": 1,
            "--skip-delete": 0,
            "--project-name": 1,
            "--help": 0,
            "-h": 0,
        },
        command_name="neon-full-setup",
    )
    sys.exit(
        run_doppler(
            "local",
            [sys.executable, str(_NEON_FULL_SETUP_SCRIPT), *passthrough],
        )
    )


def db_init() -> None:
    """First-time database setup (local config).

    Uses DATABASE_URL_ADMIN which has embedded password - no --password-env needed.
    """
    passthrough = _validated_passthrough_args(
        sys.argv[1:],
        allowed_flags={"--demo": 0},
        command_name="db-init",
    )
    sys.exit(
        run_doppler(
            "local",
            [
                sys.executable,
                str(_SETUP_DB_SCRIPT),
                "--yes",
                "init",
                *passthrough,
            ],
        )
    )


def db_init_test() -> None:
    """First-time database setup (test config, automated)."""
    sys.exit(_run_db_init("test", "--yes", "init"))


def db_init_prod() -> None:
    """First-time database setup (prod config, automated)."""
    sys.exit(_run_db_init("prod", "--yes", "init"))


def db_reset_data() -> None:
    """Reset database (data mode - truncate tables)."""
    sys.exit(_run_db_reset("local", "data"))


def db_reset_schema() -> None:
    """Reset database (schema mode - drop and recreate tables)."""
    sys.exit(_run_db_reset("local", "schema"))


def db_reset_tables() -> None:
    """Reset database tables (drop and recreate - same as schema mode)."""
    sys.exit(_run_db_reset("local", "schema"))


def db_reset_data_test() -> None:
    """Reset database (data mode - truncate tables) using Doppler test config."""
    sys.exit(_run_db_reset("test", "data"))


def db_reset_schema_test() -> None:
    """Reset database (schema mode - drop and recreate tables) using Doppler test config."""
    sys.exit(_run_db_reset("test", "schema"))


def db_reset_tables_test() -> None:
    """Reset database tables (drop and recreate) using Doppler test config."""
    sys.exit(_run_db_reset("test", "schema"))


def db_reset_data_prod() -> None:
    """Reset database (data mode - truncate tables) using Doppler prod config."""
    sys.exit(_run_db_reset("prod", "data"))


def db_reset_schema_prod() -> None:
    """Reset database (schema mode - drop and recreate tables) using Doppler prod config."""
    passthrough = _validated_passthrough_args(
        sys.argv[1:],
        allowed_flags={"--yes": 0, "-y": 0},
        command_name="db-reset-schema-prod",
    )
    # Always add --yes for prod unless --no-yes explicitly passed (not implemented)
    has_yes = "--yes" in passthrough or "-y" in passthrough
    if not has_yes:
        passthrough.append("--yes")
    sys.exit(_run_db_reset("prod", "schema", *passthrough))


def db_reset_tables_prod() -> None:
    """Reset database tables (drop and recreate) using Doppler prod config."""
    passthrough = _validated_passthrough_args(
        sys.argv[1:],
        allowed_flags={"--yes": 0, "-y": 0},
        command_name="db-reset-tables-prod",
    )
    # Always add --yes for prod unless --no-yes explicitly passed (not implemented)
    has_yes = "--yes" in passthrough or "-y" in passthrough
    if not has_yes:
        passthrough.append("--yes")
    sys.exit(_run_db_reset("prod", "schema", *passthrough))


def db_verify() -> None:
    """Verify database setup."""
    sys.exit(_run_db_verify("local"))


def db_verify_test() -> None:
    """Verify database setup using Doppler test config."""
    sys.exit(_run_db_verify("test"))


def db_verify_prod() -> None:
    """Verify database setup using Doppler prod config."""
    sys.exit(_run_db_verify("prod"))


def db_seed_demo() -> None:
    """Apply demo seed data."""
    sys.exit(run_doppler("local", [sys.executable, str(_SETUP_DB_SCRIPT), "seed", "--demo"]))


def db_sync_doppler_urls() -> None:
    """Update Doppler DATABASE_URL_* for test/prod from Neon endpoints."""
    passthrough = _validated_passthrough_args(
        sys.argv[1:],
        allowed_flags={
            "--yes": 0,
            "-y": 0,
            "--create-compute": 0,
            "--verbose": 0,
        },
        command_name="db-sync-doppler-urls",
    )
    sys.exit(
        run_doppler(
            "local",
            [sys.executable, str(_SYNC_DOPPLER_DB_URLS_SCRIPT), *passthrough],
        )
    )


def main() -> None:
    """Default entry point - shows help."""
    from cli._runner import run

    run([sys.executable, "-m", "cli.db_setup", "--help"])
