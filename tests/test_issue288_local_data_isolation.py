#!/usr/bin/env python3
"""
tests/test_issue288_local_data_isolation.py

Issue #288 (acceptance tests, written before the fix): test runs must never touch the repository
data/ directory, which holds the owner's real local portal content.

Every test builds a sandbox copy of the backend in a temporary folder with its own data/ directory
(a marker database and a marker media file) and runs small unittest or plain Python processes there.
The real data/ of the working folder is never opened, even before the fix.
"""

import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

INNER_HEADER = """
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REAL_DB = os.path.join(HERE, "data", "moderation.db")
REAL_MEDIA = os.path.join(HERE, "data", "media")
"""


def digest(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


class SandboxTestCase(unittest.TestCase):
    """A disposable copy of the backend whose data/ plays the role of the owner's local data."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="sc288-")
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

        # The sandbox "real" data: a marker database and a marker media file
        self.data = os.path.join(self.root, "data")
        self.real_db = os.path.join(self.data, "moderation.db")
        self.real_media = os.path.join(self.data, "media")
        os.makedirs(self.real_media)
        conn = sqlite3.connect(self.real_db)
        with conn:
            conn.execute("CREATE TABLE owner_marker (note TEXT)")
            conn.execute("INSERT INTO owner_marker VALUES ('real local content')")
        conn.close()
        with open(os.path.join(self.real_media, "owner-photo.png"), "wb") as f:
            f.write(b"marker")
        self.before = self.snapshot()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def snapshot(self):
        files = {}
        for dirpath, _, names in os.walk(self.data):
            for name in names:
                path = os.path.join(dirpath, name)
                files[os.path.relpath(path, self.data)] = digest(path)
        return files

    def env(self):
        env = dict(os.environ)
        for key in ("MODERATION_DB_PATH", "MEDIA_DIR", "SEED_ON_INIT", "SC_ENV_FILE"):
            env.pop(key, None)
        env["SERVER_QUIET"] = "1"
        return env

    def run_inner_unittest(self, body):
        with open(os.path.join(self.root, "inner_case.py"), "w", encoding="utf-8") as f:
            f.write(INNER_HEADER + textwrap.dedent(body))
        return subprocess.run([sys.executable, "-m", "unittest", "inner_case", "-v"], cwd=self.root, env=self.env(),
                              capture_output=True, text=True, timeout=180)

    def assert_inner_passed(self, res):
        self.assertEqual(res.returncode, 0, "inner unittest run failed:\n" + res.stdout + res.stderr)

    def assert_data_untouched(self):
        self.assertEqual(self.snapshot(), self.before, "the sandbox data/ directory was changed")


class TestDefaultsUnderUnittest(SandboxTestCase):
    def test_default_database_and_server_stay_out_of_data(self):
        res = self.run_inner_unittest("""
            from backend.db import init_db
            from backend.app import create_server

            class Inner(unittest.TestCase):
                def test_defaults(self):
                    init_db().close()
                    httpd = create_server(host="127.0.0.1", port=0)
                    httpd.server_close()
        """)
        self.assert_inner_passed(res)
        self.assert_data_untouched()


class TestExplicitDataPathsRefused(SandboxTestCase):
    def test_explicit_data_paths_raise_and_name_the_path(self):
        res = self.run_inner_unittest("""
            from backend.db import init_db
            from backend.app import create_server

            class Inner(unittest.TestCase):
                def test_init_db_refuses_real_db(self):
                    with self.assertRaises(Exception) as cm:
                        init_db(REAL_DB)
                    self.assertIn("moderation.db", str(cm.exception))

                def test_create_server_refuses_real_db(self):
                    with self.assertRaises(Exception) as cm:
                        create_server(host="127.0.0.1", port=0, db_path=REAL_DB)
                    self.assertIn("moderation.db", str(cm.exception))

                def test_create_server_refuses_real_media(self):
                    tmp = tempfile.mkdtemp()
                    with self.assertRaises(Exception) as cm:
                        create_server(host="127.0.0.1", port=0, db_path=os.path.join(tmp, "t.db"), media_dir=REAL_MEDIA)
                    self.assertIn("media", str(cm.exception))
        """)
        self.assert_inner_passed(res)
        self.assertIn("Ran 3 tests", res.stderr)
        self.assert_data_untouched()


class TestUploadsUnderUnittest(SandboxTestCase):
    def test_upload_without_media_dir_leaves_no_file_in_data_media(self):
        res = self.run_inner_unittest("""
            import base64
            import sqlite3
            import struct
            import threading
            import zlib

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

            class Inner(unittest.TestCase):
                def test_upload(self):
                    db = os.path.join(tempfile.mkdtemp(), "t.db")
                    init_db(db, seed=False).close()
                    conn = sqlite3.connect(db)
                    conn.row_factory = sqlite3.Row
                    create_user(conn, "uploader", "uploader@example.com", "Upload-pass-1", email_verified=True)
                    conn.close()
                    httpd = create_server(host="127.0.0.1", port=0, db_path=db, seed=False)
                    threading.Thread(target=httpd.serve_forever, daemon=True).start()
                    try:
                        client = Client("http://127.0.0.1:%d" % httpd.server_address[1]).login("uploader", "Upload-pass-1")
                        status, body = client.request("POST", "/api/media/upload",
                                                      {"image": "data:image/png;base64," + base64.b64encode(png()).decode()})
                        self.assertEqual(status, 200, body)
                    finally:
                        httpd.shutdown()
                        httpd.server_close()
        """)
        self.assert_inner_passed(res)
        self.assert_data_untouched()


class TestProductPathUnchanged(SandboxTestCase):
    def test_outside_unittest_init_db_uses_data_and_never_seeds(self):
        os.remove(self.real_db)
        res = subprocess.run(
            [sys.executable, "-c", "from backend.db import init_db; init_db().close()"],
            cwd=self.root, env=self.env(), capture_output=True, text=True, timeout=120)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue(os.path.exists(self.real_db), "the product default is data/moderation.db")
        conn = sqlite3.connect(self.real_db)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM moderation_submissions").fetchone()[0], 0)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
