#!/usr/bin/env python3
"""
tests/test_issue4_sc001_secure_sessions.py

Regression & Security test suite for Issue #4 (SC-001):
"Заменить подмену identity на безопасную серверную аутентификацию".

Acceptance Criteria:
1. POST /api/auth/login generates an opaque, cryptographically secure token
   (secrets.token_hex(32)) and persists session in SQLite `sessions` table.
2. Set-Cookie header contains HttpOnly and SameSite=Lax (and Secure when HTTPS / X-Forwarded-Proto: https).
3. Arbitrary X-User-Id header does not authenticate the user (returns 401 / unauthenticated).
4. Query parameters ?userId=... and ?authUser=... do not authenticate the user.
5. Forged sc_session cookie (e.g. sc_session=user_admin not in DB) does not authenticate the user.
6. POST /api/auth/logout revokes session in DB (is_revoked = 1), after which subsequent requests are rejected.
7. Expired session token (expires_at <= now) is rejected by the server.
8. Authorization: Bearer <token> is supported and validated against DB.
9. Database schema and indexes: sessions table structure with idx_sessions_user_id and idx_sessions_token.
"""

import datetime
import json
import os
import shutil
import sqlite3
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

import server
from server import create_server, init_db

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue4SC001SecureSessions(unittest.TestCase):
    """Security and regression tests for Issue #4 (SC-001) secure session authentication."""

    @classmethod
    def setUpClass(cls):
        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue4_sc001.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path)
        conn.close()

        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR)
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.httpd.shutdown()
            cls.httpd.server_close()
        except Exception:
            pass
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def _get_json(self, path: str, headers: dict = None):
        h = headers or {}
        req = urllib.request.Request(f"{self.base_url}{path}", headers=h)
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return resp.status, data, resp.headers.get("Set-Cookie")
        except urllib.error.HTTPError as e:
            try:
                data = json.loads(e.read().decode("utf-8"))
            except Exception:
                data = {"error": str(e)}
            return e.code, data, e.headers.get("Set-Cookie")

    def _post_json(self, path: str, payload: dict, headers: dict = None):
        h = {"Content-Type": "application/json"}
        if headers:
            h.update(headers)
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers=h
        )
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return resp.status, data, resp.headers.get("Set-Cookie")
        except urllib.error.HTTPError as e:
            try:
                data = json.loads(e.read().decode("utf-8"))
            except Exception:
                data = {"error": str(e)}
            return e.code, data, e.headers.get("Set-Cookie")

    def test_01_login_generates_unique_opaque_token_and_persists_in_sessions(self):
        """Test 1: POST /api/auth/login generates opaque token (secrets.token_hex) and persists in sessions table."""
        # 1. Login user_sec_1
        payload1 = {"userId": "user_sec_1", "name": "Security User 1"}
        status1, data1, cookie1 = self._post_json("/api/auth/login", payload1)
        self.assertEqual(status1, 200)
        self.assertTrue(data1.get("success"))
        self.assertTrue(data1.get("authenticated"))
        self.assertEqual(data1["user"]["id"], "user_sec_1")
        self.assertEqual(data1["user"]["name"], "Security User 1")

        token1 = data1.get("sessionToken")
        self.assertIsNotNone(token1)
        self.assertEqual(len(token1), 64, "Token should be 64 hex characters (32 bytes)")
        self.assertNotEqual(token1, "user_sec_1", "Token must be opaque and not the plain userId")

        # 2. Login again with same user_id generates a distinct new token
        status2, data2, cookie2 = self._post_json("/api/auth/login", payload1)
        self.assertEqual(status2, 200)
        token2 = data2.get("sessionToken")
        self.assertNotEqual(token1, token2, "Subsequent logins must generate unique random tokens")

        # 3. Check SQLite sessions table persistence
        conn = server.get_db_connection(self.db_path)
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT token, user_id, user_name, created_at, expires_at, is_revoked
                    FROM sessions WHERE token = ?
                """, (token1,))
                row = cur.fetchone()
                self.assertIsNotNone(row, "Session record must exist in SQLite sessions table")
                self.assertEqual(row["user_id"], "user_sec_1")
                self.assertEqual(row["user_name"], "Security User 1")
                self.assertEqual(row["is_revoked"], 0)

                # Validate expiration is ~7 days in the future
                created_dt = datetime.datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
                expires_dt = datetime.datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
                delta = expires_dt - created_dt
                self.assertGreaterEqual(delta.total_seconds(), 6.9 * 86400)
                self.assertLessEqual(delta.total_seconds(), 7.1 * 86400)
        finally:
            conn.close()

    def test_02_cookie_flags_httponly_samesite_and_conditional_secure(self):
        """Test 2: Cookie contains HttpOnly and SameSite=Lax (and Secure with HTTPS/X-Forwarded-Proto)."""
        # 1. Plain HTTP request -> HttpOnly, SameSite=Lax, NO Secure
        status, data, set_cookie = self._post_json("/api/auth/login", {"userId": "user_cookie_test"})
        self.assertEqual(status, 200)
        self.assertIsNotNone(set_cookie)
        self.assertIn("HttpOnly", set_cookie)
        self.assertIn("SameSite=Lax", set_cookie)
        self.assertNotIn("Secure", set_cookie)

        token = data.get("sessionToken")
        self.assertIn(f"sc_session={token}", set_cookie)

        # 2. HTTPS reverse proxy request via X-Forwarded-Proto: https -> contains Secure
        status_https, data_https, set_cookie_https = self._post_json(
            "/api/auth/login",
            {"userId": "user_cookie_https"},
            headers={"X-Forwarded-Proto": "https"}
        )
        self.assertEqual(status_https, 200)
        self.assertIsNotNone(set_cookie_https)
        self.assertIn("HttpOnly", set_cookie_https)
        self.assertIn("SameSite=Lax", set_cookie_https)
        self.assertIn("Secure", set_cookie_https)

        # 3. Logout cookie also respects HTTPS
        _, _, logout_cookie_plain = self._post_json("/api/auth/logout", {}, headers={"Cookie": f"sc_session={token}"})
        self.assertIn("Max-Age=0", logout_cookie_plain)
        self.assertIn("HttpOnly", logout_cookie_plain)
        self.assertIn("SameSite=Lax", logout_cookie_plain)
        self.assertNotIn("Secure", logout_cookie_plain)

        _, _, logout_cookie_https = self._post_json(
            "/api/auth/logout",
            {},
            headers={"Cookie": f"sc_session={token}", "X-Forwarded-Proto": "https"}
        )
        self.assertIn("Secure", logout_cookie_https)

    def test_03_arbitrary_x_user_id_header_is_ignored(self):
        """Test 3: Arbitrary X-User-Id header does not authenticate user (returns unauthenticated / 401)."""
        # 1. /api/auth/status with X-User-Id returns authenticated: False
        status, data, _ = self._get_json("/api/auth/status", headers={"X-User-Id": "attacker_admin"})
        self.assertEqual(status, 200)
        self.assertFalse(data.get("authenticated"))
        self.assertIsNone(data.get("user"))

        # 2. Protected endpoint with X-User-Id returns 401 requireAuth
        status_prot, data_prot, _ = self._post_json(
            "/api/subscriptions/toggle",
            {"targetType": "author", "targetId": "author_smirnov"},
            headers={"X-User-Id": "attacker_admin"}
        )
        self.assertEqual(status_prot, 401)
        self.assertTrue(data_prot.get("requireAuth"))

        # 3. /api/articles?tab=my with X-User-Id returns 401
        status_my, _, _ = self._get_json("/api/articles?tab=my", headers={"X-User-Id": "attacker_admin"})
        self.assertEqual(status_my, 401)

    def test_04_query_params_userid_and_authuser_are_ignored(self):
        """Test 4: Query parameters ?userId=... and ?authUser=... do not authenticate user."""
        # 1. /api/auth/status with ?userId=...
        status1, data1, _ = self._get_json("/api/auth/status?userId=attacker_admin")
        self.assertEqual(status1, 200)
        self.assertFalse(data1.get("authenticated"))
        self.assertIsNone(data1.get("user"))

        # 2. /api/auth/status with ?authUser=...
        status2, data2, _ = self._get_json("/api/auth/status?authUser=attacker_admin")
        self.assertEqual(status2, 200)
        self.assertFalse(data2.get("authenticated"))
        self.assertIsNone(data2.get("user"))

        # 3. Protected endpoint /api/articles?tab=my with query parameters returns 401
        status3, _, _ = self._get_json("/api/articles?tab=my&userId=attacker_admin")
        self.assertEqual(status3, 401)

        status4, _, _ = self._get_json("/api/articles?tab=my&authUser=attacker_admin")
        self.assertEqual(status4, 401)

    def test_05_forged_cookie_not_in_db_is_rejected(self):
        """Test 5: Forged cookie sc_session=user_admin (missing from DB) does not authenticate user."""
        # 1. /api/auth/status with fake sc_session
        status, data, _ = self._get_json("/api/auth/status", headers={"Cookie": "sc_session=user_admin"})
        self.assertEqual(status, 200)
        self.assertFalse(data.get("authenticated"))
        self.assertIsNone(data.get("user"))

        # 2. Protected endpoint with fake sc_session returns 401
        status_prot, _, _ = self._get_json("/api/articles?tab=my", headers={"Cookie": "sc_session=user_admin"})
        self.assertEqual(status_prot, 401)

    def test_06_logout_revokes_token_in_db_and_rejects_subsequent_requests(self):
        """Test 6: POST /api/auth/logout marks session is_revoked = 1; subsequent requests are rejected."""
        # 1. Login user
        status_log, data_log, _ = self._post_json("/api/auth/login", {"userId": "user_logout_test", "name": "Logout Tester"})
        self.assertEqual(status_log, 200)
        token = data_log["sessionToken"]

        # 2. Verify active session works
        status_st, data_st, _ = self._get_json("/api/auth/status", headers={"Cookie": f"sc_session={token}"})
        self.assertEqual(status_st, 200)
        self.assertTrue(data_st.get("authenticated"))
        self.assertEqual(data_st["user"]["id"], "user_logout_test")

        # 3. Logout
        status_out, data_out, _ = self._post_json("/api/auth/logout", {}, headers={"Cookie": f"sc_session={token}"})
        self.assertEqual(status_out, 200)
        self.assertFalse(data_out.get("authenticated"))

        # 4. Verify DB state: is_revoked == 1
        conn = server.get_db_connection(self.db_path)
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT is_revoked FROM sessions WHERE token = ?", (token,))
                row = cur.fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row["is_revoked"], 1, "Session must be marked is_revoked = 1")
        finally:
            conn.close()

        # 5. Subsequent request with revoked token must fail
        status_after, data_after, _ = self._get_json("/api/auth/status", headers={"Cookie": f"sc_session={token}"})
        self.assertEqual(status_after, 200)
        self.assertFalse(data_after.get("authenticated"))
        self.assertIsNone(data_after.get("user"))

        # Protected endpoint returns 401
        status_prot, _, _ = self._get_json("/api/articles?tab=my", headers={"Cookie": f"sc_session={token}"})
        self.assertEqual(status_prot, 401)

    def test_07_expired_token_is_rejected(self):
        """Test 7: Expired token (expires_at <= now) is rejected by get_current_user."""
        expired_token = "token_expired_1234567890abcdef1234567890abcdef"
        past_iso = "2020-01-01T00:00:00+00:00"

        conn = server.get_db_connection(self.db_path)
        try:
            with conn:
                conn.execute("""
                    INSERT INTO sessions (token, user_id, user_name, created_at, expires_at, is_revoked)
                    VALUES (?, 'user_expired', 'Expired User', '2019-12-25T00:00:00+00:00', ?, 0)
                """, (expired_token, past_iso))
        finally:
            conn.close()

        # 1. /api/auth/status returns authenticated: False
        status, data, _ = self._get_json("/api/auth/status", headers={"Cookie": f"sc_session={expired_token}"})
        self.assertEqual(status, 200)
        self.assertFalse(data.get("authenticated"))
        self.assertIsNone(data.get("user"))

        # 2. Protected endpoint returns 401
        status_prot, _, _ = self._get_json("/api/articles?tab=my", headers={"Cookie": f"sc_session={expired_token}"})
        self.assertEqual(status_prot, 401)

    def test_08_bearer_token_authorization_header_supported(self):
        """Test 8: Authorization: Bearer <token> is supported and validated against sessions table."""
        # 1. Login user
        status, data, _ = self._post_json("/api/auth/login", {"userId": "user_bearer_test", "name": "Bearer Tester"})
        self.assertEqual(status, 200)
        token = data["sessionToken"]

        # 2. Use Authorization: Bearer <token>
        status_auth, data_auth, _ = self._get_json(
            "/api/auth/status",
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(status_auth, 200)
        self.assertTrue(data_auth.get("authenticated"))
        self.assertEqual(data_auth["user"]["id"], "user_bearer_test")

        # 3. Invalid Bearer token
        status_inv, data_inv, _ = self._get_json(
            "/api/auth/status",
            headers={"Authorization": "Bearer invalid_nonexistent_token"}
        )
        self.assertEqual(status_inv, 200)
        self.assertFalse(data_inv.get("authenticated"))

    def test_09_database_schema_and_indexes_verification(self):
        """Test 9: Verify sessions table schema and indexes exist in SQLite database."""
        conn = server.get_db_connection(self.db_path)
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'")
                self.assertIsNotNone(cur.fetchone(), "sessions table must exist")

                cur.execute("PRAGMA table_info(sessions)")
                columns = {row["name"]: row for row in cur.fetchall()}
                expected_columns = ["token", "user_id", "user_name", "created_at", "expires_at", "is_revoked"]
                for col in expected_columns:
                    self.assertIn(col, columns, f"Column '{col}' must be present in sessions table")

                cur.execute("SELECT name FROM sqlite_master WHERE type='index'")
                indexes = {row["name"] for row in cur.fetchall()}
                self.assertIn("idx_sessions_user_id", indexes, "idx_sessions_user_id index must exist")
                self.assertIn("idx_sessions_token", indexes, "idx_sessions_token index must exist")
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
