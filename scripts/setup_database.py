#!/usr/bin/env python3
"""
Card Fraud Transaction Management — Database Setup Script

Supports:
- init: First-time schema creation
- reset: Drop and recreate tables (--mode=data|schema)
- verify: Check DB connectivity and schema
- seed: Add demo data (--demo)

IMPORTANT: This script NEVER drops the fraud_gov schema.
It only drops THIS project's tables to avoid affecting other projects
that share the schema (e.g., card-fraud-rule-management).

Usage:
    doppler run --config local -- uv run db-init --demo
    doppler run --config local -- uv run db-reset --mode schema
    doppler run --config local -- uv run db-verify
    doppler run --config local -- uv run db-seed --demo

Environment Variables (from Doppler):
- DATABASE_URL_ADMIN: Admin connection with schema creation permissions (primary)
- DATABASE_URL: Fallback for backwards compatibility
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


@dataclass
class SetupResult:
    """Result of a setup step."""

    success: bool
    message: str
    details: str | None = None


class ResetMode(Enum):
    """Database reset modes."""

    SCHEMA = "schema"
    DATA = "data"


class DatabaseSetup:
    """Handles database setup for Card Fraud Transaction Management."""

    def __init__(self, admin_url: str):
        self.admin_url = admin_url
        self.repo_root = Path(__file__).parent.parent

    def _load_sql_file(self, filename: str) -> str:
        """Load SQL file from db directory."""
        sql_path = self.repo_root / "db" / filename
        if not sql_path.exists():
            raise FileNotFoundError(f"SQL file not found: {sql_path}")
        return sql_path.read_text(encoding="utf-8")

    def _split_sql_statements(self, sql_content: str) -> list[str]:
        """Split SQL content into statements, preserving transaction blocks
        and dollar-quoted strings."""
        statements = []
        current = []
        in_transaction = False
        in_dollar_quote = False
        dollar_quote_tag = None
        in_block_comment = False

        for line in sql_content.splitlines():
            stripped = line.strip()
            original_line = line

            while "/*" in stripped or in_block_comment:
                if in_block_comment:
                    if "*/" in stripped:
                        end_idx = stripped.index("*/") + 2
                        after_comment = stripped[end_idx:].strip()
                        if after_comment:
                            stripped = after_comment
                        else:
                            stripped = ""
                        in_block_comment = False
                        continue
                    else:
                        stripped = ""
                        break
                else:
                    start_idx = stripped.index("/*")
                    before_comment = stripped[:start_idx].strip()
                    if "*/" in stripped[start_idx:]:
                        end_idx = stripped.index("*/", start_idx) + 2
                        after_comment = stripped[end_idx:].strip()
                        if before_comment:
                            stripped = before_comment + " " + after_comment
                        else:
                            stripped = after_comment if after_comment else ""
                        continue
                    else:
                        in_block_comment = True
                        stripped = before_comment
                        if stripped:
                            break
                        else:
                            stripped = ""
                            break

            if not stripped or (
                stripped.startswith("--") and not (in_transaction or in_dollar_quote or current)
            ):
                if current:
                    current.append(original_line)
                continue

            if "$$" in stripped:
                if not in_dollar_quote:
                    in_dollar_quote = True
                    current.append(original_line)
                    continue
                else:
                    in_dollar_quote = False
                    current.append(original_line)
                    continue
            elif in_dollar_quote:
                current.append(original_line)
                continue

            if "$" in stripped:
                if not in_dollar_quote and not in_transaction:
                    match = None
                    for tag in ["$func$", "$body$", "$table$", "$def$"]:
                        if tag in stripped:
                            match = tag
                            break
                    if match:
                        in_dollar_quote = True
                        dollar_quote_tag = match
                        current.append(original_line)
                        continue
                if in_dollar_quote and dollar_quote_tag and dollar_quote_tag in stripped:
                    in_dollar_quote = False
                    dollar_quote_tag = None
                    current.append(original_line)
                    continue

            if stripped.upper().startswith("BEGIN"):
                in_transaction = True
                current.append(original_line)
            elif stripped.upper().startswith("COMMIT"):
                current.append(original_line)
                in_transaction = False
                statements.append("\n".join(current))
                current = []
            elif stripped.endswith(";"):
                current.append(original_line)
                if not in_transaction:
                    statements.append("\n".join(current))
                    current = []
            else:
                current.append(original_line)

        if current and not in_transaction:
            content = "\n".join(current).strip()
            if content:
                statements.append(content)

        return statements

    def _execute_sql(
        self, conn: psycopg.Connection, sql_content: str, description: str
    ) -> SetupResult:
        """Execute SQL content with error handling."""
        try:
            statements = self._split_sql_statements(sql_content)
            for stmt in statements:
                if stmt.strip():
                    conn.execute(stmt)
            conn.commit()
            return SetupResult(
                success=True,
                message=description,
                details=f"Executed {len(statements)} statements",
            )
        except psycopg.Error as e:
            conn.rollback()
            return SetupResult(
                success=False,
                message=description,
                details=f"{type(e).__name__}: {e}",
            )

    def init(self, demo: bool = False) -> int:
        """Initialize database schema."""
        print("Initializing database schema...")

        schema_sql = self._load_sql_file("fraud_transactions_schema.sql")
        demo_sql = self._load_sql_file("seed_demo.sql") if demo else ""

        try:
            with psycopg.connect(self.admin_url, autocommit=False) as conn:
                print("  Applying schema...")
                result = self._execute_sql(conn, schema_sql, "Schema creation failed")
                if not result.success:
                    print(f"ERROR: {result.details}")
                    return 1
                print(f"  Schema applied: {result.details}")

                if demo:
                    print("  Applying demo data...")
                    result = self._execute_sql(conn, demo_sql, "Demo data insertion failed")
                    if not result.success:
                        print(f"ERROR: {result.details}")
                        return 1
                    print(f"  Demo data applied: {result.details}")

        except psycopg.Error as e:
            print(f"ERROR: Database connection failed: {e}")
            return 1

        print("Database initialization complete.")
        return 0

    def reset(self, mode: ResetMode, force: bool = False) -> int:
        """Reset database tables (schema or data mode)."""
        print(f"Resetting database tables ({mode.value})...")

        if not force:
            response = input("This will destroy data in our tables only. Continue? [y/N]: ")
            if response.lower() != "y":
                print("Aborted.")
                return 1

        try:
            with psycopg.connect(self.admin_url, autocommit=False) as conn:
                if mode == ResetMode.SCHEMA:
                    print("  Dropping tables (preserving fraud_gov schema)...")
                    # Drop in correct order due to foreign key dependencies
                    conn.execute("DROP TABLE IF EXISTS fraud_gov.case_activity_log CASCADE")
                    conn.execute("DROP TABLE IF EXISTS fraud_gov.transaction_reviews CASCADE")
                    conn.execute("DROP TABLE IF EXISTS fraud_gov.analyst_notes CASCADE")
                    conn.execute("DROP TABLE IF EXISTS fraud_gov.transaction_cases CASCADE")
                    conn.execute("DROP TABLE IF EXISTS fraud_gov.transaction_rule_matches CASCADE")
                    conn.execute("DROP TABLE IF EXISTS fraud_gov.transactions CASCADE")
                    conn.commit()
                    print("  Tables dropped.")

                    print("  Dropping project ENUM types...")
                    # Drop ENUM types owned by this project (after tables are dropped)
                    conn.execute("DROP TYPE IF EXISTS fraud_gov.case_type CASCADE")
                    conn.execute("DROP TYPE IF EXISTS fraud_gov.case_status CASCADE")
                    conn.execute("DROP TYPE IF EXISTS fraud_gov.transaction_status CASCADE")
                    conn.execute("DROP TYPE IF EXISTS fraud_gov.risk_level CASCADE")
                    conn.execute("DROP TYPE IF EXISTS fraud_gov.note_type CASCADE")
                    conn.execute("DROP TYPE IF EXISTS fraud_gov.rule_action CASCADE")
                    conn.commit()
                    print("  ENUM types dropped.")

                    print("  Applying schema...")
                    schema_sql = self._load_sql_file("fraud_transactions_schema.sql")
                    result = self._execute_sql(conn, schema_sql, "Schema recreation failed")
                    if not result.success:
                        print(f"ERROR: {result.details}")
                        return 1
                    print(f"  Schema applied: {result.details}")
                else:
                    print("  Truncating tables...")
                    # Truncate in correct order due to foreign key dependencies
                    conn.execute("TRUNCATE TABLE fraud_gov.case_activity_log CASCADE")
                    conn.execute("TRUNCATE TABLE fraud_gov.transaction_reviews CASCADE")
                    conn.execute("TRUNCATE TABLE fraud_gov.analyst_notes CASCADE")
                    conn.execute("TRUNCATE TABLE fraud_gov.transaction_cases CASCADE")
                    conn.execute("TRUNCATE TABLE fraud_gov.transaction_rule_matches CASCADE")
                    conn.execute("TRUNCATE TABLE fraud_gov.transactions CASCADE")
                    conn.commit()
                    print("  Tables truncated.")

        except psycopg.Error as e:
            print(f"ERROR: Database reset failed: {e}")
            return 1

        print("Database reset complete.")
        return 0

    def seed(self, demo: bool = False) -> int:
        """Apply seed data."""
        print("Seeding database...")

        try:
            with psycopg.connect(self.admin_url, autocommit=False) as conn:
                if demo:
                    print("  Applying demo data...")
                    demo_sql = self._load_sql_file("seed_demo.sql")
                    result = self._execute_sql(conn, demo_sql, "Demo data insertion failed")
                    if not result.success:
                        print(f"ERROR: {result.details}")
                        return 1
                    print(f"  Demo data applied: {result.details}")
                else:
                    print("  No demo data specified. Use --demo flag.")
                    return 1

        except psycopg.Error as e:
            print(f"ERROR: Database seed failed: {e}")
            return 1

        print("Demo data seeded.")
        return 0

    def verify(self) -> int:
        """Verify database setup."""
        print("Verifying database setup...")

        errors: list[str] = []

        try:
            with psycopg.connect(self.admin_url, autocommit=True) as conn:
                print("  [OK] Database connection")
        except psycopg.Error as e:
            errors.append(f"Database connection failed: {e}")

        try:
            with psycopg.connect(self.admin_url, autocommit=True, row_factory=dict_row) as conn:
                result = conn.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'fraud_gov'
                    AND table_name IN (
                        'transactions',
                        'transaction_rule_matches',
                        'transaction_reviews',
                        'analyst_notes',
                        'transaction_cases',
                        'case_activity_log'
                    )
                    ORDER BY table_name
                """).fetchall()
                tables = [row["table_name"] for row in result]
                expected = [
                    "transactions",
                    "transaction_rule_matches",
                    "transaction_reviews",
                    "analyst_notes",
                    "transaction_cases",
                    "case_activity_log",
                ]
                missing = [t for t in expected if t not in tables]
                if missing:
                    errors.append(f"Missing tables: {missing}")
                else:
                    print(f"  [OK] Tables exist: {', '.join(tables)}")
        except psycopg.Error as e:
            errors.append(f"Schema check failed: {e}")

        try:
            with psycopg.connect(self.admin_url, autocommit=True) as conn:
                result = conn.execute("""
                    SELECT indexname FROM pg_indexes
                    WHERE schemaname = 'fraud_gov'
                    AND tablename IN (
                        'transactions', 'transaction_reviews',
                        'analyst_notes', 'transaction_cases'
                    )
                """).fetchall()
                indexes = [row[0] for row in result]
                if indexes:
                    print(f"  [OK] Indexes on tables: {len(indexes)}")
        except psycopg.Error as e:
            errors.append(f"Index check failed: {e}")

        # Verify ENUM types
        try:
            with psycopg.connect(self.admin_url, autocommit=True, row_factory=dict_row) as conn:
                result = conn.execute("""
                    SELECT typname FROM pg_type t
                    JOIN pg_namespace n ON n.oid = t.typnamespace
                    WHERE n.nspname = 'fraud_gov'
                    AND t.typname IN (
                        'decision_type',
                        'evaluation_type',
                        'decision_reason',
                        'card_network',
                        'ingestion_source',
                        'transaction_status',
                        'risk_level',
                        'note_type',
                        'case_type',
                        'case_status',
                        'rule_action'
                    )
                    ORDER BY typname
                """).fetchall()
                enum_types = [row["typname"] for row in result]
                if enum_types:
                    print(f"  [OK] ENUM types exist: {len(enum_types)}")
        except psycopg.Error as e:
            errors.append(f"ENUM check failed: {e}")

        # Verify case_type enum has all required values
        try:
            with psycopg.connect(self.admin_url, autocommit=True, row_factory=dict_row) as conn:
                result = conn.execute("""
                    SELECT enumlabel FROM pg_enum e
                    JOIN pg_type t ON e.enumtypid = t.oid
                    JOIN pg_namespace n ON n.oid = t.typnamespace
                    WHERE n.nspname = 'fraud_gov' AND t.typname = 'case_type'
                    ORDER BY e.enumsortorder
                """).fetchall()
                case_types = [row["enumlabel"] for row in result]
                expected_case_types = [
                    "INVESTIGATION",
                    "DISPUTE",
                    "CHARGEBACK",
                    "FRAUD_RING",
                    "ACCOUNT_TAKEOVER",
                    "PATTERN_ANALYSIS",
                    "MERCHANT_REVIEW",
                    "CARD_COMPROMISE",
                    "OTHER",
                ]
                missing = [ct for ct in expected_case_types if ct not in case_types]
                if missing:
                    errors.append(f"Missing case_type values: {missing}")
                else:
                    print(f"  [OK] case_type values: {', '.join(case_types)}")
        except psycopg.Error as e:
            errors.append(f"case_type values check failed: {e}")

        if errors:
            print("\nVerification FAILED:")
            for err in errors:
                print(f"  - {err}")
            return 1

        print("\nVerification PASSED.")
        return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Card Fraud Transaction Management - Database Setup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--admin-url",
        help="Admin database URL (overrides env var)",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompts",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    init_parser = subparsers.add_parser("init", help="First-time setup")
    init_parser.add_argument("--demo", action="store_true", help="Include demo data")

    reset_parser = subparsers.add_parser("reset", help="Reset database")
    reset_parser.add_argument(
        "--mode",
        choices=["schema", "data"],
        default="schema",
        help="Reset mode: schema (drop/recreate) or data (truncate only)",
    )
    reset_parser.add_argument("--force", action="store_true", help="Bypass safety checks")
    reset_parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Bypass safety checks (alias for --force)",
    )

    seed_parser = subparsers.add_parser("seed", help="Apply seed data")
    seed_parser.add_argument("--demo", action="store_true", help="Include demo data")

    subparsers.add_parser("verify", help="Verify database setup")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    admin_url = args.admin_url or os.getenv("DATABASE_URL_ADMIN") or os.getenv("DATABASE_URL")

    if not admin_url:
        print("ERROR: DATABASE_URL_ADMIN is required")
        print("Set it as environment variable or via --admin-url")
        return 2

    setup = DatabaseSetup(admin_url=admin_url)

    if args.command == "init":
        return setup.init(demo=args.demo)
    elif args.command == "reset":
        return setup.reset(mode=ResetMode(args.mode), force=args.force or args.yes)
    elif args.command == "seed":
        return setup.seed(demo=args.demo)
    elif args.command == "verify":
        return setup.verify()

    return 0


if __name__ == "__main__":
    sys.exit(main())
