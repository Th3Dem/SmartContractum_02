import unittest
import os
import sys
import json
import sqlite3
import datetime
from contextlib import contextmanager
from unittest.mock import patch, MagicMock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import server
from server import hash_password, verify_password

class DummyServer:
    def __init__(self):
        self.db_path = "test_db.sqlite"
        self.email_service = MagicMock()
        self.allow_demo_login = False
        self.enforce_csrf = True
        self.allow_csrf_bypass = False

class DummyRequest:
    def makefile(self, *args, **kwargs):
        import io
        return io.BytesIO(b"")

class DummyHandler(server.ModerationRequestHandler):
    def __init__(self, *args, **kwargs):
        pass
    
    def setup(self):
        pass
        
    def clear_cookie(self, name):
        pass

    def get_db(self):
        conn = sqlite3.connect(self.server.db_path)
        conn.row_factory = sqlite3.Row
        return conn
        
    def send_json_response(self, status, payload, extra_headers=None):
        self._status = status
        self._payload = payload
        self._extra_headers = extra_headers or []

class TestIssue208(unittest.TestCase):
    def setUp(self):
        if os.path.exists("test_db.sqlite"):
            os.remove("test_db.sqlite")
        self.server = DummyServer()
        server.init_db(self.server.db_path)
        self.handler = DummyHandler()
        self.handler.server = self.server
        self.handler.headers = {}
        self.handler._status = None
        self.handler._payload = None
        
        # Create a test user
        conn = self.handler.get_db()
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with conn:
            conn.execute("""
                INSERT INTO users (id, login, login_normalized, email, email_normalized, password_hash, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)
            """, ("user1", "testuser", "testuser", "test@test.com", "test@test.com", hash_password("oldpass123"), now_iso, now_iso))
            conn.execute("""
                INSERT INTO user_profiles (user_id, name, created_at, updated_at)
                VALUES (?, ?, ?, ?)
            """, ("user1", "Test User", now_iso, now_iso))
            conn.execute("""
                INSERT INTO sessions (user_id, user_name, user_role, token, expires_at, created_at)
                VALUES (?, ?, 'user', ?, ?, ?)
            """, ("user1", "Test User", "token123", (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)).isoformat(), now_iso))
            
    def set_session(self, token="token123", csrf="csrf123"):
        self.handler.headers["Cookie"] = f"sc_session={token}; sc_csrf={csrf}"
        self.handler.headers["X-CSRF-Token"] = csrf
        self.handler.headers["Host"] = "localhost"
        self.handler.headers["Origin"] = "http://localhost"
        
    def invoke_get(self, path):
        self.handler.path = path
        self.handler.do_GET()
        return self.handler._status, self.handler._payload
        
    def invoke_post(self, path, body):
        import urllib.parse
        self.handler.path = path
        body_bytes = json.dumps(body).encode("utf-8")
        self.handler.headers["Content-Length"] = str(len(body_bytes))
        self.handler.rfile = __import__("io").BytesIO(body_bytes)
        self.handler.do_POST()
        return self.handler._status, self.handler._payload

    def test_get_settings(self):
        self.set_session()
        status, payload = self.invoke_get("/api/user/settings")
        self.assertEqual(status, 200)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["settings"]["email"], "test@test.com")
        
    def test_update_profile(self):
        self.set_session()
        status, payload = self.invoke_post("/api/user/profile", {
            "name": "New Name",
            "firstName": "John",
            "lastName": "Doe"
        })
        self.assertEqual(status, 200)
        conn = self.handler.get_db()
        cur = conn.cursor()
        cur.execute("SELECT first_name, last_name FROM user_profiles WHERE user_id='user1'")
        row = cur.fetchone()
        self.assertEqual(row["first_name"], "John")
        self.assertEqual(row["last_name"], "Doe")
        
    def test_change_password(self):
        self.set_session()
        status, payload = self.invoke_post("/api/auth/change-password", {
            "currentPassword": "oldpass123",
            "newPassword": "newpass1234"
        })
        self.assertEqual(status, 200)
        conn = self.handler.get_db()
        cur = conn.cursor()
        cur.execute("SELECT is_revoked FROM sessions WHERE token='token123'")
        self.assertEqual(cur.fetchone()["is_revoked"], 1)

if __name__ == "__main__":
    unittest.main()

    def tearDown(self):
        if os.path.exists("test_db.sqlite"):
            os.remove("test_db.sqlite")
