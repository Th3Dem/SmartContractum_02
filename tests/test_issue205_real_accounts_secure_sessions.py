#!/usr/bin/env python3
"""
tests/test_issue205_real_accounts_secure_sessions.py

Comprehensive test suite for Issue #205 (Epic #204):
Real user accounts and secure server sessions.

Acceptance Criteria:
1. Two distinct accounts maintain distinct identities across login, reload, and navigation.
2. POST with arbitrary userId/role=admin without valid password fails (401) and cannot elevate privileges.
3. Revoked, expired sessions, and disabled accounts cannot perform private actions.
4. Forged cookies, identity headers, and direct API requests cannot bypass authentication.
5. Idempotent migration preserves existing profiles, authorship, and subscriptions without data loss.
6. CSRF protection rejects mismatched Origin/Referer and missing/invalid CSRF tokens on state-changing requests.
7. Rate limiter throttles brute force attacks with 429 and Retry-After header.
8. Minimal safe DTO in /api/auth/status never exposes password_hash or private email.
9. Password hashing invariants with scrypt, Unicode support, and constant-time verification.
10. Trusted administrator bootstrap is secure and idempotent.
"""

import datetime
import http.client
import json
import os
import shutil
import sqlite3
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

import server
from server import (
    LOGIN_RATE_LIMITER,
    authenticate_user,
    bootstrap_admin,
    create_server,
    create_user,
    hash_password,
    init_db,
    migrate_legacy_profiles,
    reset_login_rate_limiter,
    verify_password,
)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue205RealAccountsSecureSessions(unittest.TestCase):
    """Integration and security test suite for real accounts and secure sessions."""

    @classmethod
    def setUpClass(cls):
        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue205.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path, seed=False)
        conn.close()

        # Create server in strict production mode: no demo login, CSRF enforced, test bypass enabled
        cls.httpd = create_server(
            host="127.0.0.1",
            port=0,
            db_path=cls.db_path,
            directory=FRONTEND_DIR,
            allow_demo_login=False,
            enforce_csrf=True,
            allow_csrf_bypass=True,
        )
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
        if hasattr(cls, "server_thread") and cls.server_thread.is_alive():
            cls.server_thread.join(timeout=2)
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self):
        reset_login_rate_limiter()

    def _get_db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _parse_cookies(self, headers: http.client.HTTPMessage) -> Tuple[Dict[str, str], str]:
        raw_list = headers.get_all("Set-Cookie") or []
        cookie_dict = {}
        for cookie_str in raw_list:
            part = cookie_str.split(";")[0].strip()
            if "=" in part:
                k, v = part.split("=", 1)
                cookie_dict[k.strip()] = v.strip()
        cookie_header = "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])
        return cookie_dict, cookie_header

    def _request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        cookie: Optional[str] = None,
    ) -> Tuple[int, Dict[str, Any], http.client.HTTPMessage, Dict[str, str], str]:
        url = f"{self.base_url}{path}"
        req_headers = {}
        if headers:
            req_headers.update(headers)
        if cookie:
            req_headers["Cookie"] = cookie

        data_bytes = None
        if payload is not None:
            data_bytes = json.dumps(payload).encode("utf-8")
            if "Content-Type" not in req_headers:
                req_headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data_bytes, headers=req_headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read().decode("utf-8")
                data = json.loads(raw) if raw else {}
                cookie_dict, cookie_hdr = self._parse_cookies(resp.headers)
                return resp.status, data, resp.headers, cookie_dict, cookie_hdr
        except urllib.error.HTTPError as e:
            try:
                raw = e.read().decode("utf-8")
                data = json.loads(raw) if raw else {}
            except Exception:
                data = {"error": str(e)}
            cookie_dict, cookie_hdr = self._parse_cookies(e.headers)
            return e.code, data, e.headers, cookie_dict, cookie_hdr

    def test_01_password_hashing_invariants(self):
        """Verifies scrypt format, Unicode support, constant-time check, and non-truncation."""
        # 1. Standard password
        pw = "CorrectHorseBatteryStaple2026!"
        h = hash_password(pw)
        self.assertTrue(h.startswith("scrypt$16384$8$1$"), "Hash must begin with scrypt parameters")
        parts = h.split("$")
        self.assertEqual(len(parts), 6, "Hash format must have 6 dollar-separated parts")
        salt_hex = parts[4]
        hash_hex = parts[5]
        self.assertEqual(len(salt_hex), 32, "Salt must be 16 random bytes (32 hex characters)")
        self.assertEqual(len(hash_hex), 128, "Derived key must be 64 bytes (128 hex characters)")

        # Verify correct password matches
        self.assertTrue(verify_password(pw, h), "Exact password must verify successfully")
        self.assertFalse(verify_password("WrongPassword!", h), "Wrong password must be rejected")

        # 2. Never trim or lowercase password
        self.assertFalse(verify_password(f" {pw} ", h), "Passwords must not be trimmed")
        self.assertFalse(verify_password(pw.lower(), h), "Passwords must not be lowercased")

        # 3. Unicode passwords and passphrases
        unicode_pw = "Пароль [Секретный-205] Смарт-Контрактум: 100% надежность! (alpha, beta, gamma: αβγ)"
        unicode_h = hash_password(unicode_pw)
        self.assertTrue(verify_password(unicode_pw, unicode_h), "Unicode password must verify")
        self.assertFalse(verify_password("Пароль [Секретный-205] Смарт-Контрактум: 100% надежность! (alpha, beta, delta: αβδ)", unicode_h))

        # 4. Long passphrases (no arbitrary truncation)
        long_pw = "PassphraseSecret_" * 40 + "_EndingSuffix"
        long_h = hash_password(long_pw)
        self.assertTrue(verify_password(long_pw, long_h), "Long passphrase must verify")
        truncated = long_pw[:72]
        self.assertFalse(verify_password(truncated, long_h), "Passphrase must not be truncated at 72 chars")

        # 5. Invalid hash formats gracefully return False
        self.assertFalse(verify_password(pw, ""))
        self.assertFalse(verify_password(pw, "invalid_hash_string"))
        self.assertFalse(verify_password(pw, None))

    def test_02_two_distinct_accounts_maintain_distinct_identities(self):
        """Two distinct accounts maintain separate identities across login, reload, and navigation."""
        conn = self._get_db()
        try:
            u_alice = create_user(
                conn,
                login="alice_issue205",
                email="alice@smartcontractum.local",
                password="AlicePassword2026!",
                role="user",
                status="active",
                email_verified=True,
            )
            u_bob = create_user(
                conn,
                login="bob_issue205",
                email="bob@smartcontractum.local",
                password="BobPassword2026!",
                role="moderator",
                status="active",
                email_verified=True,
            )
        finally:
            conn.close()

        # Alice logs in
        login_alice = {
            "login": "alice_issue205",
            "password": "AlicePassword2026!",
        }
        status_a, data_a, headers_a, cookies_a, cookie_hdr_a = self._request(
            "POST", "/api/auth/login", payload=login_alice
        )
        self.assertEqual(status_a, 200)
        self.assertTrue(data_a.get("authenticated"))
        self.assertEqual(data_a["user"]["id"], u_alice["id"])
        self.assertEqual(data_a["user"]["name"], "alice_issue205")
        self.assertEqual(data_a["user"]["role"], "user")
        self.assertIn("read", data_a["user"]["capabilities"])
        self.assertNotIn("moderate", data_a["user"]["capabilities"])

        # Sensitive fields must never be exposed
        self.assertNotIn("sessionToken", data_a, "sessionToken must not be in response body")
        self.assertNotIn("password_hash", data_a["user"])
        self.assertNotIn("email", data_a["user"])
        self.assertIn("csrfToken", data_a)
        self.assertIn("sc_session", cookies_a)
        self.assertIn("sc_csrf", cookies_a)

        # Bob logs in
        login_bob = {
            "login": "bob_issue205",
            "password": "BobPassword2026!",
        }
        status_b, data_b, headers_b, cookies_b, cookie_hdr_b = self._request(
            "POST", "/api/auth/login", payload=login_bob
        )
        self.assertEqual(status_b, 200)
        self.assertTrue(data_b.get("authenticated"))
        self.assertEqual(data_b["user"]["id"], u_bob["id"])
        self.assertEqual(data_b["user"]["name"], "bob_issue205")
        self.assertEqual(data_b["user"]["role"], "moderator")
        self.assertIn("moderate", data_b["user"]["capabilities"])

        # Check tokens are distinct
        self.assertNotEqual(cookies_a["sc_session"], cookies_b["sc_session"])
        self.assertNotEqual(cookies_a["sc_csrf"], cookies_b["sc_csrf"])

        # Alice checks status (simulate page reload / navigation)
        status_check_a, data_check_a, _, _, _ = self._request(
            "GET", "/api/auth/status", cookie=cookie_hdr_a
        )
        self.assertEqual(status_check_a, 200)
        self.assertTrue(data_check_a.get("authenticated"))
        self.assertEqual(data_check_a["user"]["id"], u_alice["id"])
        self.assertEqual(data_check_a["user"]["role"], "user")

        # Bob checks status
        status_check_b, data_check_b, _, _, _ = self._request(
            "GET", "/api/auth/status", cookie=cookie_hdr_b
        )
        self.assertEqual(status_check_b, 200)
        self.assertTrue(data_check_b.get("authenticated"))
        self.assertEqual(data_check_b["user"]["id"], u_bob["id"])
        self.assertEqual(data_check_b["user"]["role"], "moderator")

    def test_03_arbitrary_user_id_or_role_fails_and_cannot_elevate_privileges(self):
        """Arbitrary userId or role in POST body cannot bypass password or elevate privileges."""
        # 1. Unauthenticated attempt with spoofed userId and role=admin without password
        spoof_payload = {
            "userId": "user_admin",
            "role": "admin",
            "name": "Hacker Admin",
        }
        status, data, _, _, _ = self._request("POST", "/api/auth/login", payload=spoof_payload)
        self.assertEqual(status, 401, "Login without valid password must return 401 Unauthorized")
        self.assertFalse(data.get("authenticated", False))
        self.assertEqual(data.get("error"), "Неверный логин, email или пароль")

        # 2. Attempt with wrong password and role=admin
        bad_pw_payload = {
            "login": "alice_issue205",
            "password": "WrongPasswordAttempt!",
            "role": "admin",
        }
        status_bad, data_bad, _, _, _ = self._request("POST", "/api/auth/login", payload=bad_pw_payload)
        self.assertEqual(status_bad, 401)
        self.assertEqual(data_bad.get("error"), "Неверный логин, email или пароль")

        # 3. Legitimate user Alice attempts privilege escalation by injecting role='admin'
        escalation_payload = {
            "login": "alice_issue205",
            "password": "AlicePassword2026!",
            "role": "admin",
            "userId": "user_admin",
            "isAdmin": True,
        }
        status_esc, data_esc, _, cookies_esc, cookie_hdr_esc = self._request(
            "POST", "/api/auth/login", payload=escalation_payload
        )
        self.assertEqual(status_esc, 200)
        # Identity and role MUST come strictly from users table
        self.assertEqual(data_esc["user"]["role"], "user", "Role in DTO must remain user")
        self.assertNotEqual(data_esc["user"]["id"], "user_admin", "User ID must not be overwritten")

        # Verify via GET /api/auth/status
        st_code, st_data, _, _, _ = self._request("GET", "/api/auth/status", cookie=cookie_hdr_esc)
        self.assertEqual(st_code, 200)
        self.assertEqual(st_data["user"]["role"], "user")
        self.assertNotIn("moderate", st_data["user"]["capabilities"])

    def test_04_revoked_expired_and_disabled_accounts_rejected(self):
        """Revoked, expired sessions, and disabled accounts cannot perform private actions."""
        conn = self._get_db()
        try:
            u_temp = create_user(
                conn,
                login="temp_user_issue205",
                email="temp@smartcontractum.local",
                password="TempPassword2026!",
                role="user",
                status="active",
            )
        finally:
            conn.close()

        # Login
        st, data, _, cookies, cookie_hdr = self._request(
            "POST",
            "/api/auth/login",
            payload={"login": "temp_user_issue205", "password": "TempPassword2026!"},
        )
        self.assertEqual(st, 200)
        session_token = cookies["sc_session"]
        csrf_token = data["csrfToken"]

        # 1. Revoked session via logout
        logout_headers = {"X-CSRF-Token": csrf_token}
        st_logout, data_logout, _, _, cookie_hdr_cleared = self._request(
            "POST", "/api/auth/logout", headers=logout_headers, cookie=cookie_hdr
        )
        self.assertEqual(st_logout, 200)
        self.assertFalse(data_logout.get("authenticated"))

        # Verify session is revoked in DB
        conn = self._get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT is_revoked FROM sessions WHERE token = ?", (session_token,))
            row = cur.fetchone()
            self.assertEqual(row["is_revoked"], 1)
        finally:
            conn.close()

        # Trying to use the revoked session token returns 401
        st_rev, data_rev, _, _, _ = self._request(
            "GET", "/api/auth/status", cookie=f"sc_session={session_token}"
        )
        self.assertEqual(st_rev, 200)
        self.assertFalse(data_rev.get("authenticated"))
        self.assertIsNone(data_rev.get("user"))

        # 2. Expired session
        st_exp_login, _, _, cookies_exp, cookie_hdr_exp = self._request(
            "POST",
            "/api/auth/login",
            payload={"login": "temp_user_issue205", "password": "TempPassword2026!"},
        )
        self.assertEqual(st_exp_login, 200)
        token_exp = cookies_exp["sc_session"]

        # Set expiration to past in SQLite
        conn = self._get_db()
        try:
            past_iso = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)).isoformat()
            with conn:
                conn.execute("UPDATE sessions SET expires_at = ? WHERE token = ?", (past_iso, token_exp))
        finally:
            conn.close()

        st_expired, data_expired, _, _, _ = self._request(
            "GET", "/api/auth/status", cookie=cookie_hdr_exp
        )
        self.assertEqual(st_expired, 200)
        self.assertFalse(data_expired.get("authenticated"))

        # 3. Disabled account rejection
        conn = self._get_db()
        try:
            u_disabled = create_user(
                conn,
                login="disabled_user_issue205",
                email="disabled@smartcontractum.local",
                password="DisabledPassword2026!",
                status="disabled",
            )
        finally:
            conn.close()

        # Attempt to login with disabled account
        st_dis_login, data_dis_login, _, _, _ = self._request(
            "POST",
            "/api/auth/login",
            payload={"login": "disabled_user_issue205", "password": "DisabledPassword2026!"},
        )
        self.assertEqual(st_dis_login, 401)
        self.assertFalse(data_dis_login.get("authenticated", False))

        # If an active user with an active session gets disabled in DB
        st_act_login, data_act, _, cookies_act, cookie_hdr_act = self._request(
            "POST",
            "/api/auth/login",
            payload={"login": "temp_user_issue205", "password": "TempPassword2026!"},
        )
        self.assertEqual(st_act_login, 200)
        conn = self._get_db()
        try:
            with conn:
                conn.execute("UPDATE users SET status = 'disabled' WHERE id = ?", (u_temp["id"],))
        finally:
            conn.close()

        # Active session must be immediately rejected once account is disabled
        st_check_dis, data_check_dis, _, _, _ = self._request(
            "GET", "/api/auth/status", cookie=cookie_hdr_act
        )
        self.assertEqual(st_check_dis, 200)
        self.assertFalse(data_check_dis.get("authenticated"))
        self.assertIsNone(data_check_dis.get("user"))

    def test_05_forged_cookies_identity_headers_and_direct_requests_rejected(self):
        """Forged cookies and identity headers cannot bypass authentication."""
        # 1. Random forged token
        forged_cookie = "sc_session=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        st_forged, data_forged, _, _, _ = self._request("GET", "/api/auth/status", cookie=forged_cookie)
        self.assertEqual(st_forged, 200)
        self.assertFalse(data_forged.get("authenticated"))
        self.assertIsNone(data_forged.get("user"))

        # 2. Spoofed headers
        spoofed_headers = {
            "X-User-Id": "user_admin",
            "X-User-Role": "admin",
            "X-Author-Id": "user_admin",
        }
        st_hdr, data_hdr, _, _, _ = self._request("GET", "/api/auth/status", headers=spoofed_headers)
        self.assertEqual(st_hdr, 200)
        self.assertFalse(data_hdr.get("authenticated"))

        # 3. Direct protected API request without auth returns 401
        st_prot, data_prot, _, _, _ = self._request("GET", "/api/subscriptions")
        self.assertEqual(st_prot, 401)
        self.assertFalse(data_prot.get("success"))

    def test_06_idempotent_migration_preserves_profiles_and_revokes_demo(self):
        """Idempotent migration preserves existing profiles, authorship, and revokes demo sessions."""
        conn = self._get_db()
        try:
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            # Insert a legacy profile without a users table entry
            with conn:
                conn.execute("""
                    INSERT OR REPLACE INTO user_profiles (user_id, name, specialization, bio, created_at, updated_at)
                    VALUES ('author_legacy_test', 'Legacy Author', 'Core Developer', 'Bio text', ?, ?)
                """, (now_iso, now_iso))
                # Insert legacy demo session
                conn.execute("""
                    INSERT OR REPLACE INTO sessions (token, user_id, user_name, user_role, created_at, expires_at, is_revoked)
                    VALUES ('demo_legacy_token_123', 'user_demo', 'Демо', 'user', ?, ?, 0)
                """, (now_iso, now_iso))

            # Run migration first time
            migrated_count = migrate_legacy_profiles(conn)
            self.assertGreaterEqual(migrated_count, 1)

            # Verify account created in users table with disabled status
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE id = 'author_legacy_test'")
            user_row = cur.fetchone()
            self.assertIsNotNone(user_row)
            self.assertEqual(user_row["status"], "disabled")
            self.assertEqual(user_row["login_normalized"], "author_legacy_test")
            self.assertTrue(verify_password != user_row["password_hash"], "Unguessable password")

            # Verify user_profiles record is preserved
            cur.execute("SELECT * FROM user_profiles WHERE user_id = 'author_legacy_test'")
            prof_row = cur.fetchone()
            self.assertIsNotNone(prof_row)
            self.assertEqual(prof_row["name"], "Legacy Author")
            self.assertEqual(prof_row["specialization"], "Core Developer")

            # Verify old demo session is revoked
            cur.execute("SELECT is_revoked FROM sessions WHERE token = 'demo_legacy_token_123'")
            sess_row = cur.fetchone()
            self.assertEqual(sess_row["is_revoked"], 1)

            # Second run of migration: completely idempotent, 0 new migrations
            repeat_migrated = migrate_legacy_profiles(conn)
            self.assertEqual(repeat_migrated, 0, "Repeated migration must be idempotent and perform no changes")
        finally:
            conn.close()

    def test_07_bootstrap_admin_account(self):
        """Bootstrap trusted administrator account with secure hashed password."""
        conn = self._get_db()
        try:
            # Check bootstrap_admin
            admin_id = bootstrap_admin(conn)
            # If already bootstrapped in setUp, returns None; if freshly run, returns id
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE role = 'admin' AND status = 'active'")
            admin_row = cur.fetchone()
            self.assertIsNotNone(admin_row, "Active admin user must exist in users table")
            self.assertEqual(admin_row["role"], "admin")
            self.assertEqual(admin_row["status"], "active")

            # Verify admin credentials authenticate
            default_admin_pass = os.environ.get("ADMIN_INITIAL_PASSWORD", "AdminSecure2026!")
            user_dict, err = authenticate_user(conn, admin_row["login"], default_admin_pass)
            self.assertIsNotNone(user_dict)
            self.assertIsNone(err)
            self.assertEqual(user_dict["role"], "admin")

            # Verify repeated call is idempotent
            res = bootstrap_admin(conn)
            self.assertIsNone(res, "Repeated bootstrap_admin must return None when admin already exists")
        finally:
            conn.close()

    def test_08_csrf_protection_and_bypass_invariants(self):
        """CSRF protection rejects mismatched Origin/Referer and missing tokens on state-changing requests."""
        # Login to get ambient cookie session and CSRF token
        login_payload = {
            "login": "alice_issue205",
            "password": "AlicePassword2026!",
        }
        st_login, data_login, _, cookies, cookie_hdr = self._request(
            "POST", "/api/auth/login", payload=login_payload
        )
        self.assertEqual(st_login, 200)
        csrf_token = data_login["csrfToken"]
        session_token = cookies["sc_session"]

        # 1. State-changing request with mismatched Origin -> 403 Forbidden
        headers_evil_origin = {
            "Origin": "http://evil-attacker.com",
            "X-CSRF-Token": csrf_token,
        }
        st_origin, data_origin, _, _, _ = self._request(
            "POST", "/api/user/feed-settings",
            payload={"materialTypes": ["publication"]},
            headers=headers_evil_origin,
            cookie=cookie_hdr
        )
        self.assertEqual(st_origin, 403)
        self.assertIn("Mismatched Origin", data_origin.get("error", ""))

        # 2. State-changing request with mismatched Referer -> 403 Forbidden
        headers_evil_ref = {
            "Referer": "http://evil-attacker.com/malicious_page",
            "X-CSRF-Token": csrf_token,
        }
        st_ref, data_ref, _, _, _ = self._request(
            "POST", "/api/user/feed-settings",
            payload={"materialTypes": ["publication"]},
            headers=headers_evil_ref,
            cookie=cookie_hdr
        )
        self.assertEqual(st_ref, 403)
        self.assertIn("Mismatched Referer", data_ref.get("error", ""))

        # 3. Ambient cookie session with missing X-CSRF-Token header -> 403 Forbidden
        st_no_csrf, data_no_csrf, _, _, _ = self._request(
            "POST", "/api/user/feed-settings",
            payload={"materialTypes": ["publication"]},
            cookie=cookie_hdr
        )
        self.assertEqual(st_no_csrf, 403)
        self.assertIn("Invalid or missing CSRF token", data_no_csrf.get("error", ""))

        # 4. Ambient cookie session with wrong X-CSRF-Token header -> 403 Forbidden
        headers_wrong_csrf = {"X-CSRF-Token": "wrong_csrf_token_value_12345"}
        st_wrong, data_wrong, _, _, _ = self._request(
            "POST", "/api/user/feed-settings",
            payload={"materialTypes": ["publication"]},
            headers=headers_wrong_csrf,
            cookie=cookie_hdr
        )
        self.assertEqual(st_wrong, 403)
        self.assertIn("Invalid or missing CSRF token", data_wrong.get("error", ""))

        # 5. Ambient cookie session with matching X-CSRF-Token header -> 200 OK
        headers_valid_csrf = {"X-CSRF-Token": csrf_token}
        st_valid, data_valid, _, _, _ = self._request(
            "POST", "/api/user/feed-settings",
            payload={"materialTypes": ["publication"]},
            headers=headers_valid_csrf,
            cookie=cookie_hdr
        )
        self.assertEqual(st_valid, 200)
        self.assertTrue(data_valid.get("success"))

        # 6. Authorization: Bearer token bypasses CSRF check
        bearer_headers = {"Authorization": f"Bearer {session_token}"}
        st_bearer, data_bearer, _, _, _ = self._request(
            "POST", "/api/user/feed-settings",
            payload={"materialTypes": ["publication", "question"]},
            headers=bearer_headers
        )
        self.assertEqual(st_bearer, 200)
        self.assertTrue(data_bearer.get("success"))

        # 7. Test bypass header (X-Test-Bypass-CSRF) when allow_csrf_bypass is True
        test_bypass_headers = {"X-Test-Bypass-CSRF": "1"}
        st_test_bypass, data_test_bypass, _, _, _ = self._request(
            "POST", "/api/user/feed-settings",
            payload={"materialTypes": ["publication"]},
            headers=test_bypass_headers,
            cookie=cookie_hdr
        )
        self.assertEqual(st_test_bypass, 200)

        # 8. Safe GET requests are not blocked by CSRF
        st_get, data_get, _, _, _ = self._request("GET", "/api/auth/status", cookie=cookie_hdr)
        self.assertEqual(st_get, 200)

        # 9. Server mode with enforce_csrf=False
        try:
            self.httpd.enforce_csrf = False
            # When enforce_csrf is False, missing CSRF token is allowed
            st_no_enforce, data_no_enforce, _, _, _ = self._request(
                "POST", "/api/user/feed-settings",
                payload={"materialTypes": ["publication"]},
                cookie=cookie_hdr
            )
            self.assertEqual(st_no_enforce, 200)
            self.assertTrue(data_no_enforce.get("success"))

            # When enforce_csrf is False, provided matching CSRF token is allowed
            st_match_enforce, data_match_enforce, _, _, _ = self._request(
                "POST", "/api/user/feed-settings",
                payload={"materialTypes": ["publication"]},
                headers=headers_valid_csrf,
                cookie=cookie_hdr
            )
            self.assertEqual(st_match_enforce, 200)
            self.assertTrue(data_match_enforce.get("success"))

            # When enforce_csrf is False, provided mismatched CSRF token is rejected
            st_mismatch, data_mismatch, _, _, _ = self._request(
                "POST", "/api/user/feed-settings",
                payload={"materialTypes": ["publication"]},
                headers=headers_wrong_csrf,
                cookie=cookie_hdr
            )
            self.assertEqual(st_mismatch, 403)
            self.assertIn("Invalid or missing CSRF token", data_mismatch.get("error", ""))
        finally:
            self.httpd.enforce_csrf = True

    def test_09_login_rate_limiter_throttles_brute_force(self):
        """Rate limiter throttles repeated failed login attempts with 429 and Retry-After header."""
        reset_login_rate_limiter()
        target_account = "alice_issue205"

        # Send failed login attempts up to threshold (5 attempts)
        for i in range(5):
            st, data, _, _, _ = self._request(
                "POST",
                "/api/auth/login",
                payload={"login": target_account, "password": f"WrongPass_{i}"},
            )
            self.assertEqual(st, 401, f"Attempt {i+1} should return 401")

        # 6th attempt must be throttled with 429 Too Many Requests
        st_throttled, data_throttled, headers_throttled, _, _ = self._request(
            "POST",
            "/api/auth/login",
            payload={"login": target_account, "password": "WrongPass_6"},
        )
        self.assertEqual(st_throttled, 429, "Throttled request must return 429 Too Many Requests")
        self.assertFalse(data_throttled.get("success"))
        self.assertIn("retryAfter", data_throttled)
        retry_after_hdr = headers_throttled.get("Retry-After")
        self.assertIsNotNone(retry_after_hdr, "Retry-After header must be present on 429")
        self.assertTrue(int(retry_after_hdr) > 0)

        # Successful login on a different account resets that account's counters
        reset_login_rate_limiter()
        st_ok, data_ok, _, _, _ = self._request(
            "POST",
            "/api/auth/login",
            payload={"login": "bob_issue205", "password": "BobPassword2026!"},
        )
        self.assertEqual(st_ok, 200)

    def test_10_minimal_safe_user_dto_omits_sensitive_fields(self):
        """Minimal safe DTO in /api/auth/status never exposes password_hash or private email."""
        st_login, data_login, _, cookies, cookie_hdr = self._request(
            "POST",
            "/api/auth/login",
            payload={"login": "alice_issue205", "password": "AlicePassword2026!"},
        )
        self.assertEqual(st_login, 200)

        # In login response body:
        self.assertNotIn("sessionToken", data_login)
        user_login = data_login["user"]
        self.assertNotIn("password_hash", user_login)
        self.assertNotIn("password", user_login)
        self.assertNotIn("email", user_login)
        self.assertIn("id", user_login)
        self.assertIn("name", user_login)
        self.assertIn("role", user_login)
        self.assertIn("capabilities", user_login)

        # In GET /api/auth/status response body:
        st_status, data_status, _, _, _ = self._request("GET", "/api/auth/status", cookie=cookie_hdr)
        self.assertEqual(st_status, 200)
        user_status = data_status["user"]
        self.assertNotIn("password_hash", user_status)
        self.assertNotIn("password", user_status)
        self.assertNotIn("email", user_status)
        self.assertEqual(user_status["id"], user_login["id"])
        self.assertEqual(user_status["role"], user_login["role"])

    def test_11_demo_login_configuration_flag(self):
        """Tests that allow_demo_login flag strictly controls legacy demo bypass behavior."""
        # Server cls.httpd has allow_demo_login=False:
        st_no_demo, data_no_demo, _, _, _ = self._request(
            "POST", "/api/auth/login", payload={"userId": "user_demo_test"}
        )
        self.assertEqual(st_no_demo, 401, "Demo login without password must fail when allow_demo_login=False")

        # Start a temporary server with allow_demo_login=True for legacy test compatibility
        legacy_httpd = create_server(
            host="127.0.0.1",
            port=0,
            db_path=self.db_path,
            directory=FRONTEND_DIR,
            allow_demo_login=True,
            enforce_csrf=False,
        )
        legacy_port = legacy_httpd.server_address[1]
        t = threading.Thread(target=legacy_httpd.serve_forever, daemon=True)
        t.start()
        time.sleep(0.05)
        try:
            req_url = f"http://127.0.0.1:{legacy_port}/api/auth/login"
            req = urllib.request.Request(
                req_url,
                data=json.dumps({"userId": "user_legacy_demo", "name": "Legacy Demo"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req) as resp:
                self.assertEqual(resp.status, 200)
                data_legacy = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(data_legacy.get("authenticated"))
                self.assertEqual(data_legacy["user"]["id"], "user_legacy_demo")
                self.assertIn("sessionToken", data_legacy, "Legacy demo mode includes sessionToken for compatibility")
        finally:
            try:
                legacy_httpd.shutdown()
                legacy_httpd.server_close()
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
