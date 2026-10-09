#!/usr/bin/env python3
"""
tests/test_issue288_product_path_with_unittest_imported.py

Verifies that the product server entry points (server.py and run_server) never use
the test temp redirection (sc-test-data-*), even if unittest is already imported
into sys.modules.

Exercises:
1. Server default DB and media paths resolution.
2. CLI commands operating on real sandbox data/.
3. Real HTTP request handling (GET /api/articles -> 200) and media uploads landing
   in sandbox data/media/ even when unittest was loaded into the process.
"""

import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class ProductPathSandboxTestCase(unittest.TestCase):
    """Disposable sandbox environment replicating the repository layout."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="sc288-prod-")
        for name in ("backend",):
            shutil.copytree(os.path.join(PROJECT_ROOT, name), os.path.join(self.root, name),
                            ignore=shutil.ignore_patterns("__pycache__"))
        for name in ("server.py", "image_decoder.py"):
            shutil.copy2(os.path.join(PROJECT_ROOT, name), os.path.join(self.root, name))
        os.makedirs(os.path.join(self.root, "tests"))
        shutil.copytree(os.path.join(PROJECT_ROOT, "tests", "fixtures"), os.path.join(self.root, "tests", "fixtures"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(os.path.join(PROJECT_ROOT, "tests", "http_client.py"), os.path.join(self.root, "tests", "http_client.py"))
        os.makedirs(os.path.join(self.root, "frontend", "public"))

        self.data = os.path.join(self.root, "data")
        self.real_db = os.path.join(self.data, "moderation.db")
        self.real_media = os.path.join(self.data, "media")
        os.makedirs(self.real_media, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def env(self):
        env = dict(os.environ)
        for key in ("MODERATION_DB_PATH", "MEDIA_DIR", "SEED_ON_INIT", "SC_ENV_FILE"):
            env.pop(key, None)
        env["SERVER_QUIET"] = "1"
        return env

    def test_product_server_uses_data_even_if_unittest_imported(self):
        """
        When unittest is imported, run_server / create_server(is_product=True) must still
        use sandbox data/moderation.db and data/media without redirecting to test temp.
        """
        script = textwrap.dedent("""
            import unittest  # Pre-imported in process to simulate dependency/mock
            import os
            import sys
            import threading
            import time
            from backend import config
            from backend.app import create_server

            config.set_product_mode(True)
            httpd = create_server(host="127.0.0.1", port=0)
            print("RESOLVED_DB:", os.path.abspath(httpd.db_path))
            print("RESOLVED_MEDIA:", os.path.abspath(httpd.media_dir))
            httpd.server_close()
        """)
        runner_path = os.path.join(self.root, "run_prod_check.py")
        with open(runner_path, "w", encoding="utf-8") as f:
            f.write(script)

        res = subprocess.run([sys.executable, "run_prod_check.py"], cwd=self.root, env=self.env(),
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(res.returncode, 0, f"Process failed: {res.stderr}\n{res.stdout}")

        expected_db = os.path.abspath(self.real_db)
        expected_media = os.path.abspath(self.real_media)
        self.assertIn(f"RESOLVED_DB: {expected_db}", res.stdout)
        self.assertIn(f"RESOLVED_MEDIA: {expected_media}", res.stdout)
        self.assertNotIn("sc-test-data", res.stdout)
        self.assertTrue(os.path.exists(self.real_db), "Sandbox moderation.db must exist in data/")

    def test_server_cli_create_admin_uses_data_even_if_unittest_imported(self):
        """
        When unittest is imported, server.py CLI commands (such as --create-admin)
        must operate on the sandbox data/ directory, not temporary test data.
        """
        script = textwrap.dedent("""
            import unittest  # Pre-imported
            import runpy
            import sys

            sys.argv = ["server.py", "--create-admin", "superadmin", "superadmin@example.com"]
            try:
                runpy.run_path("server.py", run_name="__main__")
            except SystemExit as e:
                print("CLI_EXIT:", e.code)
        """)
        runner_path = os.path.join(self.root, "run_cli_check.py")
        with open(runner_path, "w", encoding="utf-8") as f:
            f.write(script)

        res = subprocess.run([sys.executable, "run_cli_check.py"], cwd=self.root, env=self.env(),
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(res.returncode, 0, f"CLI command failed: {res.stderr}\n{res.stdout}")
        self.assertIn("CLI_EXIT: 0", res.stdout)
        self.assertIn("Administrator 'superadmin' is ready", res.stdout)
        self.assertTrue(os.path.exists(self.real_db), "Sandbox moderation.db must exist in data/")

        conn = sqlite3.connect(self.real_db)
        try:
            row = conn.execute("SELECT email FROM users WHERE login = 'superadmin'").fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], "superadmin@example.com")
        finally:
            conn.close()

    def test_product_server_serves_requests_and_uploads_to_data_media(self):
        """
        When unittest is imported, starting the product server must serve GET /api/articles (200)
        and save user uploads directly into the sandbox data/media directory.
        """
        script = textwrap.dedent("""
            import unittest  # Pre-imported in process to simulate dependency/mock
            import base64
            import os
            import sqlite3
            import struct
            import threading
            import zlib
            import time

            from backend import config
            from backend.app import create_server
            from backend.db import init_db
            from backend.users import create_user
            from tests.http_client import Client

            def png():
                raw = b"".join(b"\\x00" + b"\\x10\\x20\\x30" * 4 for _ in range(4))
                def chunk(kind, data):
                    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
                return (b"\\x89PNG\\r\\n\\x1a\\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 4, 8, 2, 0, 0, 0))
                        + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))

            # Initialize product db with an author user so we can test login & upload
            config.set_product_mode(True)
            init_db(seed=False).close()

            conn = sqlite3.connect(config.DEFAULT_DB_PATH)
            conn.row_factory = sqlite3.Row
            create_user(conn, "author_uploader", "uploader@example.com", "Password-123", email_verified=True)
            conn.close()

            # Start product server on port 0
            httpd = create_server(host="127.0.0.1", port=0)
            t = threading.Thread(target=httpd.serve_forever, daemon=True)
            t.start()
            port = httpd.server_address[1]

            try:
                client = Client(f"http://127.0.0.1:{port}")
                # 1. GET /api/articles returns 200
                st, data = client.request("GET", "/api/articles?limit=5")
                assert st == 200, f"Expected 200 on /api/articles, got {st}: {data}"

                # 2. Login as author and upload image
                client.login("author_uploader", "Password-123")
                payload = {"image": "data:image/png;base64," + base64.b64encode(png()).decode()}
                st, body = client.request("POST", "/api/media/upload", payload)
                assert st == 200, f"Expected 200 on /api/media/upload, got {st}: {body}"
                print("UPLOAD_URL:", body.get("url"))
            finally:
                httpd.shutdown()
                httpd.server_close()
        """)
        runner_path = os.path.join(self.root, "run_e2e_check.py")
        with open(runner_path, "w", encoding="utf-8") as f:
            f.write(script)

        res = subprocess.run([sys.executable, "run_e2e_check.py"], cwd=self.root, env=self.env(),
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(res.returncode, 0, f"E2E test failed: {res.stderr}\n{res.stdout}")
        self.assertIn("UPLOAD_URL:", res.stdout)

        # Verify that the image file was written directly into sandbox data/media
        media_files = [f for f in os.listdir(self.real_media) if f.endswith(".png")]
        self.assertEqual(len(media_files), 1, f"Expected 1 uploaded image in {self.real_media}, got {media_files}")


if __name__ == "__main__":
    unittest.main()
