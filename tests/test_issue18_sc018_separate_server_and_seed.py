#!/usr/bin/env python3
"""
tests/test_issue18_sc018_separate_server_and_seed.py

Unit and integration tests for Issue #18 (SC-018):
"Разделить запуск сервера и демонстрационный seed данных".

Test Matrix:
1. test_init_db_without_seed: init_db(seed=False) creates all tables with 0 demo records.
2. test_init_db_with_seed: init_db(seed=True) creates tables and populates demo records.
3. test_seed_database_direct: seed_database(conn) populates an empty DB idempotently.
4. test_init_db_env_override: SEED_ON_INIT="0" disables seeding when seed is None.
5. test_init_db_env_enable: SEED_ON_INIT="1" enables seeding when seed is None.
6. test_create_server_seed_false: create_server(seed=False) leaves DB without demo records.
7. test_create_server_seed_true: create_server(seed=True) seeds DB with demo records.
8. test_scripts_seed_cli: scripts/seed.py --db <path> populates demo data with exit code 0.
9. test_scripts_seed_executable: Direct execution of ./scripts/seed.py succeeds.
10. test_server_subprocess_without_seed: server.py without --seed starts cleanly and leaves DB unseeded.
11. test_server_subprocess_with_seed: server.py with --seed starts cleanly and seeds demo records.
"""

import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import server
from server import create_server, init_db, seed_database


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestIssue18SeparateServerStartupAndSeed(unittest.TestCase):
    """Test suite for server startup and seed separation."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_sc018.db")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init_db_without_seed(self):
        """init_db(seed=False) creates schema and tables with 0 demo records."""
        conn = init_db(self.db_path, seed=False)
        try:
            # Check schema exists
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = {row[0] for row in cur.fetchall()}
            expected_tables = {
                "moderation_submissions",
                "user_subscriptions",
                "user_feed_exceptions",
                "article_likes",
                "article_comments",
                "user_notifications",
                "user_profiles",
                "user_feed_settings",
                "clubs",
                "companies",
                "company_members",
                "sessions",
            }
            self.assertTrue(expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}")

            # Verify tables have 0 demo records
            for table in ["moderation_submissions", "companies", "clubs", "article_comments", "user_subscriptions"]:
                cur.execute(f"SELECT COUNT(*) AS cnt FROM {table}")
                count = cur.fetchone()["cnt"]
                self.assertEqual(count, 0, f"Table {table} should have 0 records, got {count}")
        finally:
            conn.close()

    def test_init_db_with_seed(self):
        """init_db(seed=True) initializes tables and populates demo records."""
        conn = init_db(self.db_path, seed=True)
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) AS cnt FROM moderation_submissions")
            self.assertGreater(cur.fetchone()["cnt"], 0, "moderation_submissions should contain demo articles")

            cur.execute("SELECT COUNT(*) AS cnt FROM companies")
            self.assertGreater(cur.fetchone()["cnt"], 0, "companies should contain demo companies")

            cur.execute("SELECT COUNT(*) AS cnt FROM clubs")
            self.assertGreater(cur.fetchone()["cnt"], 0, "clubs should contain demo clubs")

            cur.execute("SELECT COUNT(*) AS cnt FROM article_comments")
            self.assertGreater(cur.fetchone()["cnt"], 0, "article_comments should contain demo comments")
        finally:
            conn.close()

    def test_seed_database_direct(self):
        """seed_database(conn) populates demo records into empty database idempotently."""
        conn = init_db(self.db_path, seed=False)
        try:
            seed_database(conn)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) AS cnt FROM moderation_submissions")
            initial_count = cur.fetchone()["cnt"]
            self.assertGreater(initial_count, 0)

            # Second call should not raise errors and maintain idempotency
            seed_database(conn)
            cur.execute("SELECT COUNT(*) AS cnt FROM moderation_submissions")
            second_count = cur.fetchone()["cnt"]
            self.assertEqual(initial_count, second_count)
        finally:
            conn.close()

    def test_init_db_env_override(self):
        """SEED_ON_INIT='0' disables seeding even when unittest is active."""
        orig_val = os.environ.get("SEED_ON_INIT")
        try:
            os.environ["SEED_ON_INIT"] = "0"
            conn = init_db(self.db_path, seed=None)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) AS cnt FROM moderation_submissions")
            self.assertEqual(cur.fetchone()["cnt"], 0)
            conn.close()
        finally:
            if orig_val is not None:
                os.environ["SEED_ON_INIT"] = orig_val
            else:
                os.environ.pop("SEED_ON_INIT", None)

    def test_init_db_env_enable(self):
        """SEED_ON_INIT='1' forces seeding when seed is None."""
        orig_val = os.environ.get("SEED_ON_INIT")
        try:
            os.environ["SEED_ON_INIT"] = "1"
            conn = init_db(self.db_path, seed=None)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) AS cnt FROM moderation_submissions")
            self.assertGreater(cur.fetchone()["cnt"], 0)
            conn.close()
        finally:
            if orig_val is not None:
                os.environ["SEED_ON_INIT"] = orig_val
            else:
                os.environ.pop("SEED_ON_INIT", None)

    def test_create_server_seed_false(self):
        """create_server(seed=False) initializes database without demo records."""
        port = get_free_port()
        httpd = create_server(host="127.0.0.1", port=port, db_path=self.db_path, seed=False)
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) AS cnt FROM moderation_submissions")
            self.assertEqual(cur.fetchone()["cnt"], 0)
            cur.execute("SELECT COUNT(*) AS cnt FROM companies")
            self.assertEqual(cur.fetchone()["cnt"], 0)
            conn.close()
        finally:
            httpd.server_close()

    def test_create_server_seed_true(self):
        """create_server(seed=True) initializes database and seeds demo records."""
        port = get_free_port()
        httpd = create_server(host="127.0.0.1", port=port, db_path=self.db_path, seed=True)
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) AS cnt FROM moderation_submissions")
            self.assertGreater(cur.fetchone()["cnt"], 0)
            cur.execute("SELECT COUNT(*) AS cnt FROM companies")
            self.assertGreater(cur.fetchone()["cnt"], 0)
            conn.close()
        finally:
            httpd.server_close()

    def test_scripts_seed_cli(self):
        """scripts/seed.py --db <path> populates demo data with returncode 0."""
        script_path = os.path.join(PROJECT_ROOT, "scripts", "seed.py")
        res = subprocess.run(
            [sys.executable, script_path, "--db", self.db_path],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"seed.py failed: {res.stderr}")
        self.assertIn("Database seeded successfully.", res.stdout)

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM moderation_submissions")
        self.assertGreater(cur.fetchone()[0], 0)
        cur.execute("SELECT COUNT(*) FROM companies")
        self.assertGreater(cur.fetchone()[0], 0)
        conn.close()

    def test_scripts_seed_executable(self):
        """Executing scripts/seed.py directly works as executable."""
        script_path = os.path.join(PROJECT_ROOT, "scripts", "seed.py")
        self.assertTrue(os.access(script_path, os.X_OK), "scripts/seed.py must be executable")
        res = subprocess.run(
            [script_path, "--db", self.db_path],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"Executable failed: {res.stderr}")
        self.assertIn("Database seeded successfully.", res.stdout)

    def test_server_subprocess_without_seed(self):
        """Running server.py via subprocess without --seed leaves DB without demo records."""
        port = get_free_port()
        proc = subprocess.Popen(
            [sys.executable, "server.py", "--host", "127.0.0.1", "--port", str(port), "--db", self.db_path],
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            # Wait for server to print startup line
            started = False
            for _ in range(30):
                if proc.poll() is not None:
                    break
                if os.path.exists(self.db_path):
                    started = True
                    break
                time.sleep(0.1)

            self.assertTrue(started, "Server did not initialize database in time")
            time.sleep(0.2)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM moderation_submissions")
        self.assertEqual(cur.fetchone()[0], 0, "server.py without --seed should not seed moderation_submissions")
        cur.execute("SELECT COUNT(*) FROM companies")
        self.assertEqual(cur.fetchone()[0], 0, "server.py without --seed should not seed companies")
        conn.close()

    def test_server_subprocess_with_seed(self):
        """Running server.py --seed via subprocess populates demo records."""
        port = get_free_port()
        proc = subprocess.Popen(
            [sys.executable, "server.py", "--host", "127.0.0.1", "--port", str(port), "--db", self.db_path, "--seed"],
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            # Wait for server to initialize and seed database
            started = False
            for _ in range(60):
                if proc.poll() is not None:
                    break
                if os.path.exists(self.db_path):
                    try:
                        conn_chk = sqlite3.connect(self.db_path)
                        cur_chk = conn_chk.cursor()
                        cur_chk.execute("SELECT COUNT(*) FROM moderation_submissions")
                        row = cur_chk.fetchone()
                        conn_chk.close()
                        if row and row[0] > 0:
                            started = True
                            break
                    except Exception:
                        pass
                time.sleep(0.1)

            self.assertTrue(started, "Server did not seed database in time")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM moderation_submissions")
        self.assertGreater(cur.fetchone()[0], 0, "server.py --seed should populate moderation_submissions")
        cur.execute("SELECT COUNT(*) FROM companies")
        self.assertGreater(cur.fetchone()[0], 0, "server.py --seed should populate companies")
        conn.close()


if __name__ == "__main__":
    unittest.main()
