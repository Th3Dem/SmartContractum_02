#!/usr/bin/env python3
"""
tests/test_issue206_registration_and_email_verification.py

Comprehensive test suite for Issue #206 (Epic #204):
Real user registration, cryptographically secure email verification challenges,
rate-limited resend, mail adapter with durable outbox, and pending user restriction.

Acceptance Criteria:
1. Registration flow and successful verification and login.
2. Incorrect code decrements attempts and locks out at 0.
3. Expired code rejected.
4. Resend cooldown (60s) and invalidation of old code.
5. Consumed code cannot be reused.
6. Cross-account code tamper rejected.
7. Pending user cannot login or access protected endpoints.
8. Hourly rate limiting on resend and registration.
9. Mail delivery failure handling and retry.
10. Persistence across server restart.
11. Concurrent verify and race conditions.
"""

import concurrent.futures
import datetime
import http.client
import json
import os
import re
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
    EMAIL_SERVICE,
    LOGIN_RATE_LIMITER,
    REGISTRATION_RATE_LIMITER,
    create_server,
    hash_verification_code,
    init_db,
    mask_email,
    reset_login_rate_limiter,
    reset_registration_rate_limiter,
    verify_verification_code,
)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue206RegistrationAndEmailVerification(unittest.TestCase):
    """Integration and security test suite for registration and email verification."""

    @classmethod
    def setUpClass(cls):
        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue206.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path, seed=False)
        conn.close()

        cls.httpd = create_server(
            host="127.0.0.1",
            port=0,
            db_path=cls.db_path,
            directory=FRONTEND_DIR,
            allow_demo_login=False,
            enforce_csrf=False,
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
        reset_registration_rate_limiter()
        EMAIL_SERVICE.clear_sent_emails()
        EMAIL_SERVICE.set_simulate_failure(False)

    def _get_db(self, db_path: Optional[str] = None) -> sqlite3.Connection:
        target = db_path or self.db_path
        conn = sqlite3.connect(target)
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
        base_url: Optional[str] = None,
    ) -> Tuple[int, Dict[str, Any], http.client.HTTPMessage, Dict[str, str], str]:
        target_base = base_url or self.base_url
        url = f"{target_base}{path}"
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

    def _get_latest_code(self, email: str, db_path: Optional[str] = None) -> str:
        # Check in-memory emails first
        emails = [e for e in EMAIL_SERVICE.get_sent_emails() if e["recipient"] == email]
        if emails:
            return emails[-1]["code"]

        # Check durable email_outbox in DB
        conn = self._get_db(db_path)
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT body_text FROM email_outbox
                WHERE recipient = ? AND status = 'sent'
                ORDER BY created_at DESC LIMIT 1
            """, (email,))
            row = cur.fetchone()
            if row:
                m = re.search(r"\b(\d{6})\b", row["body_text"])
                if m:
                    return m.group(1)
        finally:
            conn.close()
        return ""

    def test_01_registration_flow_and_successful_verification_login(self):
        """Standard registration flow: register, verify email code, login, check status."""
        email = "alice01@smartcontractum.local"
        login = "alice_reg_01"
        password = "AliceSecurePass2026!"

        # 1. Register new user
        st_reg, data_reg, _, _, _ = self._request("POST", "/api/auth/register", payload={
            "login": login,
            "email": email,
            "password": password,
            "name": "Алиса Эксперт"
        })
        self.assertEqual(st_reg, 201)
        self.assertTrue(data_reg.get("success"))
        self.assertEqual(data_reg.get("email"), mask_email(email))

        # Verify DB pending status
        conn = self._get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT status, email_verified_at FROM users WHERE email = ?", (email,))
            u_row = cur.fetchone()
            self.assertIsNotNone(u_row)
            self.assertEqual(u_row["status"], "pending")
            self.assertIsNone(u_row["email_verified_at"])
        finally:
            conn.close()

        # 2. Login before verification must fail with 403 and requiresEmailVerification flag
        st_pre_login, data_pre_login, _, _, _ = self._request("POST", "/api/auth/login", payload={
            "login": login,
            "password": password
        })
        self.assertEqual(st_pre_login, 403)
        self.assertFalse(data_pre_login.get("success"))
        self.assertTrue(data_pre_login.get("requiresEmailVerification"))

        # 3. Retrieve code from outbox
        code = self._get_latest_code(email)
        self.assertTrue(code and len(code) == 6 and code.isdigit(), f"Valid 6-digit code expected, got '{code}'")

        # 4. Verify code
        st_ver, data_ver, _, _, _ = self._request("POST", "/api/auth/verify-email", payload={
            "email": email,
            "code": code
        })
        self.assertEqual(st_ver, 200)
        self.assertTrue(data_ver.get("success"))

        # Verify DB active status and consumed challenge
        conn = self._get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT status, email_verified_at FROM users WHERE email = ?", (email,))
            u_row = cur.fetchone()
            self.assertEqual(u_row["status"], "active")
            self.assertIsNotNone(u_row["email_verified_at"])

            cur.execute("SELECT status FROM email_verifications WHERE email = ?", (email,))
            ch_row = cur.fetchone()
            self.assertEqual(ch_row["status"], "consumed")
        finally:
            conn.close()

        # 5. Login after verification must succeed
        st_login, data_login, _, cookies, cookie_hdr = self._request("POST", "/api/auth/login", payload={
            "login": login,
            "password": password
        })
        self.assertEqual(st_login, 200)
        self.assertTrue(data_login.get("authenticated"))
        self.assertEqual(data_login["user"]["login" if "login" in data_login["user"] else "name"], "Алиса Эксперт")
        self.assertIn("sc_session", cookies)

        # 6. Check authenticated status
        st_status, data_status, _, _, _ = self._request("GET", "/api/auth/status", cookie=cookie_hdr)
        self.assertEqual(st_status, 200)
        self.assertTrue(data_status.get("authenticated"))
        self.assertEqual(data_status["user"]["name"], "Алиса Эксперт")

    def test_02_incorrect_code_decrements_attempts_and_locks(self):
        """Incorrect code decrements attempts_left and permanently locks after 5 failed attempts."""
        email = "bob02@smartcontractum.local"
        login = "bob_reg_02"
        password = "BobSecurePass2026!"

        st_reg, _, _, _, _ = self._request("POST", "/api/auth/register", payload={
            "login": login,
            "email": email,
            "password": password
        })
        self.assertEqual(st_reg, 201)

        real_code = self._get_latest_code(email)

        # Attempts 1 to 4 with incorrect code
        for expected_attempts_left in [4, 3, 2, 1]:
            st_fail, data_fail, _, _, _ = self._request("POST", "/api/auth/verify-email", payload={
                "email": email,
                "code": "000000"
            })
            self.assertEqual(st_fail, 400)
            self.assertEqual(data_fail.get("attemptsLeft"), expected_attempts_left)

        # 5th failed attempt: locks out challenge (attemptsLeft = 0)
        st_lock, data_lock, _, _, _ = self._request("POST", "/api/auth/verify-email", payload={
            "email": email,
            "code": "000000"
        })
        self.assertEqual(st_lock, 400)
        self.assertEqual(data_lock.get("attemptsLeft"), 0)

        # Check DB challenge status is invalidated
        conn = self._get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT status, attempts_left FROM email_verifications WHERE email = ?", (email,))
            ch_row = cur.fetchone()
            self.assertEqual(ch_row["status"], "invalidated")
            self.assertEqual(ch_row["attempts_left"], 0)
        finally:
            conn.close()

        # 6th attempt with REAL code must still be rejected because challenge was locked
        st_real_after_lock, data_real, _, _, _ = self._request("POST", "/api/auth/verify-email", payload={
            "email": email,
            "code": real_code
        })
        self.assertEqual(st_real_after_lock, 400)

        # User remains pending
        conn = self._get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT status FROM users WHERE email = ?", (email,))
            self.assertEqual(cur.fetchone()["status"], "pending")
        finally:
            conn.close()

    def test_03_expired_code_rejected(self):
        """Expired challenge codes are rejected and marked invalidated."""
        email = "charlie03@smartcontractum.local"
        login = "charlie_reg_03"
        password = "CharlieSecurePass2026!"

        st_reg, _, _, _, _ = self._request("POST", "/api/auth/register", payload={
            "login": login,
            "email": email,
            "password": password
        })
        self.assertEqual(st_reg, 201)
        real_code = self._get_latest_code(email)

        # Set expires_at in DB to 1 hour in the past
        past_iso = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)).isoformat()
        conn = self._get_db()
        try:
            with conn:
                conn.execute("UPDATE email_verifications SET expires_at = ? WHERE email = ?", (past_iso, email))
        finally:
            conn.close()

        # Attempt to verify with real code
        st_exp, data_exp, _, _, _ = self._request("POST", "/api/auth/verify-email", payload={
            "email": email,
            "code": real_code
        })
        self.assertEqual(st_exp, 400)
        self.assertIn("истек", data_exp.get("error", "").lower())

        # Check DB challenge status is invalidated
        conn = self._get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT status FROM email_verifications WHERE email = ?", (email,))
            self.assertEqual(cur.fetchone()["status"], "invalidated")

            cur.execute("SELECT status FROM users WHERE email = ?", (email,))
            self.assertEqual(cur.fetchone()["status"], "pending")
        finally:
            conn.close()

    def test_04_resend_cooldown_60s_and_invalidation_of_old_code(self):
        """Resend enforces 60-second cooldown, invalidates older code, and validates new code."""
        email = "dave04@smartcontractum.local"
        login = "dave_reg_04"
        password = "DaveSecurePass2026!"

        st_reg, _, _, _, _ = self._request("POST", "/api/auth/register", payload={
            "login": login,
            "email": email,
            "password": password
        })
        self.assertEqual(st_reg, 201)
        code_1 = self._get_latest_code(email)

        # Immediate resend attempt must fail with 429 and Retry-After header
        st_resend_early, data_resend_early, headers_early, _, _ = self._request(
            "POST", "/api/auth/resend-code", payload={"email": email}
        )
        self.assertEqual(st_resend_early, 429)
        self.assertIn("Retry-After", headers_early)
        self.assertGreaterEqual(int(headers_early["Retry-After"]), 1)

        # Fast-forward cooldown by setting resend_available_at to the past
        past_cooldown = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5)).isoformat()
        conn = self._get_db()
        try:
            with conn:
                conn.execute(
                    "UPDATE email_verifications SET resend_available_at = ? WHERE email = ?",
                    (past_cooldown, email)
                )
        finally:
            conn.close()

        # Resend code after cooldown
        st_resend_ok, data_resend_ok, _, _, _ = self._request(
            "POST", "/api/auth/resend-code", payload={"email": email}
        )
        self.assertEqual(st_resend_ok, 200)
        self.assertTrue(data_resend_ok.get("success"))

        code_2 = self._get_latest_code(email)

        # Check DB: first challenge is invalidated
        conn = self._get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT status FROM email_verifications WHERE email = ? ORDER BY created_at ASC", (email,))
            statuses = [r["status"] for r in cur.fetchall()]
            self.assertEqual(statuses, ["invalidated", "pending"])
        finally:
            conn.close()

        # Submitting old code_1 must fail (400)
        st_old, data_old, _, _, _ = self._request("POST", "/api/auth/verify-email", payload={
            "email": email,
            "code": code_1
        })
        self.assertEqual(st_old, 400)

        # Submitting new code_2 must succeed (200)
        st_new, data_new, _, _, _ = self._request("POST", "/api/auth/verify-email", payload={
            "email": email,
            "code": code_2
        })
        self.assertEqual(st_new, 200)
        self.assertTrue(data_new.get("success"))

    def test_05_consumed_code_cannot_be_reused(self):
        """A consumed verification challenge cannot be replayed or reused."""
        email = "eve05@smartcontractum.local"
        login = "eve_reg_05"
        password = "EveSecurePass2026!"

        self._request("POST", "/api/auth/register", payload={"login": login, "email": email, "password": password})
        code = self._get_latest_code(email)

        # First verify succeeds
        st1, data1, _, _, _ = self._request("POST", "/api/auth/verify-email", payload={"email": email, "code": code})
        self.assertEqual(st1, 200)
        self.assertTrue(data1.get("success"))

        # Replay attempt with same code must be rejected (400)
        st2, data2, _, _, _ = self._request("POST", "/api/auth/verify-email", payload={"email": email, "code": code})
        self.assertEqual(st2, 400)
        conn = self._get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT status FROM email_verifications WHERE email = ?", (email,))
            self.assertEqual(cur.fetchone()["status"], "consumed")

            cur.execute("SELECT status FROM users WHERE email = ?", (email,))
            self.assertEqual(cur.fetchone()["status"], "active")
        finally:
            conn.close()

    def test_06_cross_account_code_tamper_rejected(self):
        """Code issued for User A cannot be used to verify User B."""
        user_a_email = "frank06a@smartcontractum.local"
        user_b_email = "frank06b@smartcontractum.local"

        self._request("POST", "/api/auth/register", payload={
            "login": "frank06a", "email": user_a_email, "password": "PasswordA2026!"
        })
        code_a = self._get_latest_code(user_a_email)

        self._request("POST", "/api/auth/register", payload={
            "login": "frank06b", "email": user_b_email, "password": "PasswordB2026!"
        })
        code_b = self._get_latest_code(user_b_email)

        # Attempt to verify User B with User A's code
        st_tamper, data_tamper, _, _, _ = self._request("POST", "/api/auth/verify-email", payload={
            "email": user_b_email,
            "code": code_a
        })
        self.assertEqual(st_tamper, 400)

        # User B remains pending
        conn = self._get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT status FROM users WHERE email = ?", (user_b_email,))
            self.assertEqual(cur.fetchone()["status"], "pending")
        finally:
            conn.close()

        # Both users can verify with their own authentic codes
        st_ok_a, _, _, _, _ = self._request("POST", "/api/auth/verify-email", payload={"email": user_a_email, "code": code_a})
        self.assertEqual(st_ok_a, 200)

        st_ok_b, _, _, _, _ = self._request("POST", "/api/auth/verify-email", payload={"email": user_b_email, "code": code_b})
        self.assertEqual(st_ok_b, 200)

    def test_07_pending_user_cannot_login_or_access_protected_endpoints(self):
        """Pending users cannot establish sessions or access private API actions."""
        email = "grace07@smartcontractum.local"
        login = "grace_reg_07"
        password = "GracePassword2026!"

        st_reg, _, _, _, _ = self._request("POST", "/api/auth/register", payload={
            "login": login,
            "email": email,
            "password": password
        })
        self.assertEqual(st_reg, 201)

        # 1. Login fails with 403
        st_login, data_login, _, cookies, _ = self._request("POST", "/api/auth/login", payload={
            "login": login,
            "password": password
        })
        self.assertEqual(st_login, 403)
        self.assertNotIn("sc_session", cookies)

        # 2. Forged cookie for pending user is rejected on protected endpoints
        conn = self._get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM users WHERE email = ?", (email,))
            u_id = cur.fetchone()["id"]

            forged_token = "forged_pending_token_07"
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            exp_iso = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)).isoformat()
            with conn:
                conn.execute("""
                    INSERT INTO sessions (token, user_id, user_name, user_role, created_at, expires_at, is_revoked)
                    VALUES (?, ?, 'Grace Pending', 'user', ?, ?, 0)
                """, (forged_token, u_id, now_iso, exp_iso))
        finally:
            conn.close()

        forged_cookie = f"sc_session={forged_token}"

        # Status check must report not authenticated
        st_status, data_status, _, _, _ = self._request("GET", "/api/auth/status", cookie=forged_cookie)
        self.assertEqual(st_status, 200)
        self.assertFalse(data_status.get("authenticated"))

        # Protected action returns 401
        st_prot, _, _, _, _ = self._request("GET", "/api/subscriptions", cookie=forged_cookie)
        self.assertEqual(st_prot, 401)

    def test_08_hourly_rate_limiting_on_resend_and_registration(self):
        """Rate limiters throttle repeated registration and resend requests in rolling 1-hour window."""
        reset_registration_rate_limiter()

        # 1. Registration rate limiting: 5 allowed, 6th returns 429
        for i in range(5):
            st, _, _, _, _ = self._request("POST", "/api/auth/register", payload={
                "login": f"limit_user_{i}",
                "email": f"limit_{i}@test.local",
                "password": "LimitPassword2026!"
            })
            self.assertEqual(st, 201, f"Attempt {i+1} must succeed")

        st_throttled, data_throttled, headers_throttled, _, _ = self._request("POST", "/api/auth/register", payload={
            "login": "limit_user_overflow",
            "email": "limit_overflow@test.local",
            "password": "LimitPassword2026!"
        })
        self.assertEqual(st_throttled, 429)
        self.assertIn("Retry-After", headers_throttled)

        # 2. Resend hourly limit: 5 challenges max per hour
        reset_registration_rate_limiter()
        target_email = "resend_limit@test.local"
        self._request("POST", "/api/auth/register", payload={
            "login": "resend_limit_user",
            "email": target_email,
            "password": "ResendLimitPass2026!"
        })

        # Do 4 more resends by fast-forwarding cooldown each time
        for i in range(4):
            past = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5)).isoformat()
            conn = self._get_db()
            try:
                with conn:
                    conn.execute("UPDATE email_verifications SET resend_available_at = ? WHERE email = ?", (past, target_email))
            finally:
                conn.close()

            st, _, _, _, _ = self._request("POST", "/api/auth/resend-code", payload={"email": target_email})
            self.assertEqual(st, 200, f"Resend {i+1} must succeed")

        # 5th resend (6th challenge in 1 hour) must return 429
        past = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5)).isoformat()
        conn = self._get_db()
        try:
            with conn:
                conn.execute("UPDATE email_verifications SET resend_available_at = ? WHERE email = ?", (past, target_email))
        finally:
            conn.close()

        st_resend_overflow, _, headers_resend_overflow, _, _ = self._request("POST", "/api/auth/resend-code", payload={"email": target_email})
        self.assertEqual(st_resend_overflow, 429)
        self.assertIn("Retry-After", headers_resend_overflow)

    def test_09_mail_delivery_failure_handling_and_retry(self):
        """Mail delivery failure records failed status in outbox and allows clean retry."""
        email = "fail09@smartcontractum.local"
        login = "fail_reg_09"
        password = "FailPassword2026!"

        # Enable simulated delivery failure
        EMAIL_SERVICE.set_simulate_failure(True)

        st_fail, data_fail, _, _, _ = self._request("POST", "/api/auth/register", payload={
            "login": login,
            "email": email,
            "password": password
        })
        self.assertEqual(st_fail, 500)

        # Check outbox has record with status='failed'
        conn = self._get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT status, error_message FROM email_outbox WHERE recipient = ?", (email,))
            outbox_row = cur.fetchone()
            self.assertIsNotNone(outbox_row)
            self.assertEqual(outbox_row["status"], "failed")
            self.assertIsNotNone(outbox_row["error_message"])
        finally:
            conn.close()

        # Disable simulated failure and retry registration with same credentials
        EMAIL_SERVICE.set_simulate_failure(False)

        st_ok, data_ok, _, _, _ = self._request("POST", "/api/auth/register", payload={
            "login": login,
            "email": email,
            "password": password
        })
        self.assertEqual(st_ok, 201)
        self.assertTrue(data_ok.get("success"))

        code = self._get_latest_code(email)
        self.assertTrue(code)

        # Verify succeeds with new code
        st_ver, data_ver, _, _, _ = self._request("POST", "/api/auth/verify-email", payload={"email": email, "code": code})
        self.assertEqual(st_ver, 200)

    def test_10_persistence_across_server_restart(self):
        """Verification challenges and accounts persist safely across server restarts."""
        restart_db = os.path.join(self.temp_dir, "restart_test.db")
        conn = init_db(restart_db, seed=False)
        conn.close()

        # Instance 1
        httpd_1 = create_server(
            host="127.0.0.1", port=0, db_path=restart_db, directory=FRONTEND_DIR, allow_demo_login=False
        )
        port_1 = httpd_1.server_address[1]
        t1 = threading.Thread(target=httpd_1.serve_forever, daemon=True)
        t1.start()
        base_1 = f"http://127.0.0.1:{port_1}"
        time.sleep(0.05)

        email = "persist10@smartcontractum.local"
        login = "persist_user_10"
        password = "PersistPassword2026!"

        # Register on Server 1
        st_reg, _, _, _, _ = self._request("POST", "/api/auth/register", payload={
            "login": login, "email": email, "password": password
        }, base_url=base_1)
        self.assertEqual(st_reg, 201)

        code = self._get_latest_code(email, db_path=restart_db)
        self.assertTrue(code)

        # Shutdown Server 1
        httpd_1.shutdown()
        httpd_1.server_close()
        t1.join(timeout=2)

        # Instance 2 pointing to same database
        httpd_2 = create_server(
            host="127.0.0.1", port=0, db_path=restart_db, directory=FRONTEND_DIR, allow_demo_login=False
        )
        port_2 = httpd_2.server_address[1]
        t2 = threading.Thread(target=httpd_2.serve_forever, daemon=True)
        t2.start()
        base_2 = f"http://127.0.0.1:{port_2}"
        time.sleep(0.05)

        try:
            # Verify code on Server 2
            st_ver, data_ver, _, _, _ = self._request("POST", "/api/auth/verify-email", payload={
                "email": email, "code": code
            }, base_url=base_2)
            self.assertEqual(st_ver, 200)
            self.assertTrue(data_ver.get("success"))

            # Login on Server 2
            st_login, data_login, _, _, _ = self._request("POST", "/api/auth/login", payload={
                "login": login, "password": password
            }, base_url=base_2)
            self.assertEqual(st_login, 200)
            self.assertTrue(data_login.get("authenticated"))
        finally:
            httpd_2.shutdown()
            httpd_2.server_close()
            t2.join(timeout=2)

    def test_11_concurrent_verify_and_race_conditions(self):
        """Simultaneous concurrent verifications for the same code consume atomically exactly once."""
        email = "concurrent11@smartcontractum.local"
        login = "concurrent_user_11"
        password = "ConcurrentPass2026!"

        self._request("POST", "/api/auth/register", payload={"login": login, "email": email, "password": password})
        code = self._get_latest_code(email)
        self.assertTrue(code)

        results = []

        def verify_worker():
            st, data, _, _, _ = self._request("POST", "/api/auth/verify-email", payload={"email": email, "code": code})
            return st

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(verify_worker) for _ in range(10)]
            for f in concurrent.futures.as_completed(futures):
                results.append(f.result())

        # Exactly 1 request succeeds with 200, others fail with 400
        success_count = results.count(200)
        failure_count = results.count(400)
        self.assertEqual(success_count, 1, f"Expected exactly 1 success, got {success_count}. Results: {results}")
        self.assertEqual(failure_count, 9, f"Expected 9 failures, got {failure_count}. Results: {results}")

        # Check DB state: exactly 1 consumed challenge, user active
        conn = self._get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT status FROM email_verifications WHERE email = ?", (email,))
            self.assertEqual(cur.fetchone()["status"], "consumed")

            cur.execute("SELECT status FROM users WHERE email = ?", (email,))
            self.assertEqual(cur.fetchone()["status"], "active")
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
