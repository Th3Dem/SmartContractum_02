#!/usr/bin/env python3
"""
scripts/seed.py — Standalone script to initialize schema and seed demo data.
"""

import argparse
import os
import sys

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from server import DEFAULT_DB_PATH, init_db, seed_database


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed database with demo data")
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Path to SQLite database (default: DEFAULT_DB_PATH or MODERATION_DB_PATH)",
    )
    args = parser.parse_args()

    target_db = args.db or os.environ.get("MODERATION_DB_PATH", DEFAULT_DB_PATH)
    try:
        conn = init_db(target_db, seed=False)
        seed_database(conn)
        conn.close()
        print("Database seeded successfully.")
        return 0
    except Exception as e:
        print(f"Error seeding database: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
