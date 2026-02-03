#!/usr/bin/env python3
"""
Card Fraud Transaction Management — Schema Verification Script

Verifies that all expected tables, indexes, constraints, and functions
exist in the fraud_gov schema.

Usage:
    python scripts/verify_schema.py [--verbose]

Exit codes:
    0 = All checks passed
    1 = One or more checks failed
"""

from __future__ import annotations

import argparse
import os
import sys

import psycopg
from psycopg import sql
from psycopg.rows import dict_row


def get_db_url() -> str:
    """Get database URL from environment."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL not set in environment")
    return url


def connect() -> psycopg.Connection:
    """Create database connection."""
    return psycopg.connect(get_db_url())


class SchemaVerifier:
    """Verifies database schema components."""

    def __init__(self, conn: psycopg.Connection, verbose: bool = False):
        self.conn = conn
        self.verbose = verbose
        self.passed = 0
        self.failed = 0
        self.warnings = 0

    def log(self, msg: str) -> None:
        """Log message if verbose mode."""
        if self.verbose:
            print(f"  {msg}")

    def check(self, name: str, condition: bool, details: str = "") -> bool:
        """Record a check result."""
        if condition:
            print(f"  [PASS] {name}")
            self.passed += 1
            return True
        else:
            print(f"  [FAIL] {name}")
            if details:
                print(f"         {details}")
            self.failed += 1
            return False

    def check_warning(self, name: str, condition: bool, details: str = "") -> bool:
        """Record a check result as warning."""
        if condition:
            print(f"  [PASS] {name}")
            self.passed += 1
            return True
        else:
            print(f"  [WARN] {name}")
            if details:
                print(f"         {details}")
            self.warnings += 1
            return True

    def verify_tables(self) -> bool:
        """Verify required tables exist."""
        print("\n=== Tables ===")
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                sql.SQL(
                    """
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'fraud_gov'
                    ORDER BY table_name
                """
                )
            )
            tables = {row["table_name"] for row in cur.fetchall()}

        expected_tables = {"transactions", "transaction_rule_matches"}
        extra = tables - expected_tables

        all_ok = True
        for table in expected_tables:
            all_ok &= self.check(
                f"Table exists: {table}",
                table in tables,
            )

        for table in extra:
            self.check_warning(
                f"Extra table found: {table}",
                True,
                "(may be from other project)",
            )

        return all_ok

    def verify_columns(self) -> bool:
        """Verify required columns exist."""
        print("\n=== Columns ===")
        all_ok = True

        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                sql.SQL(
                    """
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'fraud_gov' AND table_name = 'transactions'
                """
                )
            )
            txn_cols = {row["column_name"]: row for row in cur.fetchall()}

            required_txn_cols = {
                "id": "uuid",
                "transaction_id": "character varying",
                "event_version": "character varying",
                "occurred_at": "timestamp with time zone",
                "produced_at": "timestamp with time zone",
                "ingested_at": "timestamp with time zone",
                "card_id": "character varying",
                "card_last4": "character varying",
                "card_network": "user-defined",
                "amount": "numeric",
                "currency": "character",
                "country": "character",
                "merchant_id": "character varying",
                "mcc": "character varying",
                "ip_address": "inet",
                "decision": "user-defined",
                "decision_reason": "user-defined",
                "trace_id": "character varying",
                "raw_payload": "jsonb",
                "raw_payload_redacted": "jsonb",
                "ingestion_source": "user-defined",
                "kafka_partition": "integer",
                "kafka_offset": "bigint",
                "source_message_id": "character varying",
                "created_at": "timestamp with time zone",
                "updated_at": "timestamp with time zone",
            }

            for col, _dtype in required_txn_cols.items():
                if col in txn_cols:
                    self.log(f"  Column {col}: {txn_cols[col]['data_type']}")
                    all_ok &= self.check(
                        f"Column exists: transactions.{col}",
                        col in txn_cols,
                    )
                else:
                    all_ok &= self.check(
                        f"Column exists: transactions.{col}",
                        False,
                        "MISSING!",
                    )

        return all_ok

    def verify_indexes(self) -> bool:
        """Verify required indexes exist."""
        print("\n=== Indexes ===")
        all_ok = True

        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                sql.SQL(
                    """
                    SELECT indexname, tablename
                    FROM pg_indexes
                    WHERE schemaname = 'fraud_gov'
                    ORDER BY tablename, indexname
                """
                )
            )
            indexes = {(row["indexname"], row["tablename"]) for row in cur.fetchall()}

        required_indexes = {
            ("idx_transactions_occurred_at", "transactions"),
            ("idx_transactions_card_id", "transactions"),
            ("idx_transactions_country", "transactions"),
            ("idx_transactions_decision", "transactions"),
            ("idx_transactions_merchant", "transactions"),
            ("idx_transactions_trace_id", "transactions"),
            ("idx_transactions_ip_address", "transactions"),
            ("idx_transactions_mcc", "transactions"),
            ("idx_transactions_created_at", "transactions"),
            ("idx_transactions_declined_30d", "transactions"),
            ("idx_transactions_high_value", "transactions"),
            ("idx_transactions_raw_payload_ginpath", "transactions"),
            ("idx_rule_matches_rule_id", "transaction_rule_matches"),
            ("idx_rule_matches_transaction", "transaction_rule_matches"),
            ("idx_rule_matches_contributing", "transaction_rule_matches"),
        }

        for idx_name, table_name in required_indexes:
            all_ok &= self.check(
                f"Index exists: {idx_name}",
                (idx_name, table_name) in indexes,
            )

        return all_ok

    def verify_constraints(self) -> bool:
        """Verify required constraints exist."""
        print("\n=== Constraints ===")
        all_ok = True

        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                sql.SQL(
                    """
                    SELECT conname, contype, tablename
                    FROM pg_constraints
                    WHERE connamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'fraud_gov')
                    ORDER BY contype, conname
                """
                )
            )
            constraints = {
                (row["conname"], row["tablename"], row["contype"]) for row in cur.fetchall()
            }

        required_constraints = {
            ("chk_card_id_token", "transactions", "c"),
            ("chk_amount_positive", "transactions", "c"),
            ("chk_currency_upper", "transactions", "c"),
            ("unq_transaction_rule_version", "transaction_rule_matches", "u"),
        }

        con_type_map = {"c": "CHECK", "u": "UNIQUE", "f": "FOREIGN KEY", "p": "PRIMARY KEY"}
        for con_name, table_name, con_type in required_constraints:
            all_ok &= self.check(
                f"Constraint exists: {con_name} ({con_type_map.get(con_type, con_type)})",
                (con_name, table_name, con_type) in constraints,
            )

        all_ok &= self.check(
            "FK constraint on transaction_rule_matches.transaction_id",
            any(c[0].startswith("fk_rule_match_transaction") for c in constraints),
        )

        return all_ok

    def verify_enums(self) -> bool:
        """Verify required enum types exist."""
        print("\n=== Enums ===")
        all_ok = True

        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                sql.SQL(
                    """
                    SELECT typname, enumlabel
                    FROM pg_enum e
                    JOIN pg_type t ON e.enumtypid = t.oid
                    JOIN pg_namespace n ON t.typnamespace = n.oid
                    WHERE n.nspname = 'fraud_gov'
                    ORDER BY typname, enumlabel
                """
                )
            )
            enums = {(row["typname"], row["enumlabel"]) for row in cur.fetchall()}

        expected_enum_values = {
            ("decision_type", "APPROVE"),
            ("decision_type", "DECLINE"),
            ("evaluation_type", "AUTH"),
            ("evaluation_type", "MONITORING"),
            ("decision_reason", "RULE_MATCH"),
            ("decision_reason", "VELOCITY_MATCH"),
            ("decision_reason", "SYSTEM_DECLINE"),
            ("decision_reason", "DEFAULT_ALLOW"),
            ("decision_reason", "MANUAL_REVIEW"),
            ("card_network", "VISA"),
            ("card_network", "MASTERCARD"),
            ("card_network", "AMEX"),
            ("card_network", "DISCOVER"),
            ("card_network", "OTHER"),
            ("ingestion_source", "HTTP"),
            ("ingestion_source", "KAFKA"),
        }

        for type_name, label in expected_enum_values:
            all_ok &= self.check(
                f"Enum value: {type_name}.{label}",
                (type_name, label) in enums,
            )

        return all_ok

    def verify_functions(self) -> bool:
        """Verify required functions exist."""
        print("\n=== Functions ===")
        all_ok = True

        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                sql.SQL(
                    """
                    SELECT routine_name
                    FROM information_schema.routines
                    WHERE routine_schema = 'fraud_gov'
                    AND routine_type = 'FUNCTION'
                    ORDER BY routine_name
                """
                )
            )
            functions = {row["routine_name"] for row in cur.fetchall()}

        required_functions = {"update_updated_at_column"}

        for func_name in required_functions:
            all_ok &= self.check(
                f"Function exists: {func_name}",
                func_name in functions,
            )

        return all_ok

    def verify_triggers(self) -> bool:
        """Verify required triggers exist."""
        print("\n=== Triggers ===")
        all_ok = True

        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                sql.SQL(
                    """
                    SELECT trigger_name, event_object_table
                    FROM information_schema.triggers
                    WHERE event_object_schema = 'fraud_gov'
                    ORDER BY trigger_name
                """
                )
            )
            triggers = {(row["trigger_name"], row["event_object_table"]) for row in cur.fetchall()}

        required_triggers = {("update_transactions_updated_at", "transactions")}

        for trigger_name, table_name in required_triggers:
            all_ok &= self.check(
                f"Trigger exists: {trigger_name}",
                (trigger_name, table_name) in triggers,
            )

        return all_ok

    def verify_row_counts(self) -> bool:
        """Verify seed data was applied."""
        print("\n=== Seed Data ===")
        all_ok = True

        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql.SQL("SELECT COUNT(*) as count FROM fraud_gov.transactions"))
            row = cur.fetchone()
            txn_count = row["count"] if row else 0
            all_ok &= self.check(
                "Transactions have data",
                txn_count > 0,
                f"Found {txn_count} rows",
            )

            cur.execute(sql.SQL("SELECT COUNT(*) as count FROM fraud_gov.transaction_rule_matches"))
            row = cur.fetchone()
            rm_count = row["count"] if row else 0
            all_ok &= self.check(
                "Rule matches have data",
                rm_count > 0,
                f"Found {rm_count} rows",
            )

        return all_ok

    def run_all(self) -> bool:
        """Run all verification checks."""
        print("=" * 60)
        print("Card Fraud Transaction Management — Schema Verification")
        print("=" * 60)

        checks = [
            self.verify_tables,
            self.verify_columns,
            self.verify_indexes,
            self.verify_constraints,
            self.verify_enums,
            self.verify_functions,
            self.verify_triggers,
            self.verify_row_counts,
        ]

        for check in checks:
            check()

        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"  Passed:   {self.passed}")
        print(f"  Failed:   {self.failed}")
        print(f"  Warnings: {self.warnings}")
        print("=" * 60)

        if self.failed > 0:
            print("\n[RESULT] VERIFICATION FAILED")
            return False

        print("\n[RESULT] VERIFICATION PASSED")
        return True


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Verify database schema for card-fraud-transaction-management"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show verbose output",
    )

    args = parser.parse_args()

    try:
        with connect() as conn:
            verifier = SchemaVerifier(conn, verbose=args.verbose)
            success = verifier.run_all()
            return 0 if success else 1

    except psycopg.Error as e:
        print(f"[ERROR] Database error: {e}")
        return 1
    except RuntimeError as e:
        print(f"[ERROR] {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
