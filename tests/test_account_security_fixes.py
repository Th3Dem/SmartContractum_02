"""
HTTP tests for the account stack review fixes (Issues #206 and #208).

Every scenario runs against a real server instance with the real email service,
so missing helpers or broken handlers fail here instead of being mocked away.
"""
import datetime
import http.cookiejar
import json
import os
import re
import shutil
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

import server
from server import (
    EMAIL_SERVICE,
    create_server,
    create_user,
    init_db,
    reset_login_rate_limiter,
    reset_recovery_rate_limiter,
    reset_registration_rate_limiter,
)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PASSWORD = "Initial-pass-123"


class Client:
    """A browser stand-in with its own cookie jar."""

    def __init__(self, base_url):
        self.base_url = base_url
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def cookie(self, name):
        for c in self.jar:
            if c.name == name:
                return c.value
        return None

    def request(self, method, path, payload=None):
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        csrf = self.cookie("sc_csrf")
        if csrf:
            req.add_header("X-CSRF-Token", csrf)
        try:
            with self.opener.open(req, timeout=10) as resp:
                raw = resp.read()
                return resp.status, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            raw = e.read()
            e.close()
            return e.code, json.loads(raw) if raw else {}

    def login(self, login, password=PASSWORD):
        return self.request("POST", "/api/auth/login", {"login": login, "password": password})[0]

    def authenticated(self):
        return self.request("GET", "/api/auth/status")[1].get("authenticated")


class TestAccountSecurityFixes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "account_fixes.db")
        init_db(cls.db_path, seed=False).close()
        cls.httpd = create_server(
            host="127.0.0.1", port=0, db_path=cls.db_path,
            directory=os.path.join(PROJECT_ROOT, "frontend", "public"),
            allow_demo_login=False, enforce_csrf=True,
        )
        cls.base_url = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=2)
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self):
        reset_login_rate_limiter()
        reset_registration_rate_limiter()
        reset_recovery_rate_limiter()
        EMAIL_SERVICE.clear_sent_emails()
        EMAIL_SERVICE.set_simulate_failure(False)

    def tearDown(self):
        EMAIL_SERVICE.set_simulate_failure(False)

    # helpers

    def db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def make_active_user(self, login):
        conn = self.db()
        try:
            create_user(conn, login, f"{login}@example.com", PASSWORD, email_verified=True)
        finally:
            conn.close()
        return f"{login}@example.com"

    def client(self):
        return Client(self.base_url)

    def mails_to(self, address):
        return [m for m in EMAIL_SERVICE.get_sent_emails() if m["recipient"] == address]

    def last_code(self, address):
        mails = self.mails_to(address)
        self.assertTrue(mails, f"no email sent to {address}")
        return re.findall(r"\b\d{6}\b", mails[-1]["body_text"])[0]

    # password recovery

    def test_forgot_password_sends_code_and_is_neutral(self):
        email = self.make_active_user("rec_user")
        anon = self.client()
        st_known, body_known = anon.request("POST", "/api/auth/forgot-password", {"identifier": "rec_user"})
        st_unknown, body_unknown = anon.request("POST", "/api/auth/forgot-password", {"identifier": "nobody_here"})
        self.assertEqual((st_known, st_unknown), (200, 200))
        self.assertEqual(body_known, body_unknown)
        self.assertEqual(len(self.mails_to(email)), 1)

    def test_reset_password_full_cycle_revokes_sessions(self):
        self.make_active_user("reset_user")
        device = self.client()
        self.assertEqual(device.login("reset_user"), 200)

        anon = self.client()
        anon.request("POST", "/api/auth/forgot-password", {"identifier": "reset_user"})
        code = self.last_code("reset_user@example.com")
        st, _ = anon.request("POST", "/api/auth/reset-password",
                             {"identifier": "reset_user", "code": code, "newPassword": "Brand-new-pass-1"})
        self.assertEqual(st, 200)
        self.assertFalse(device.authenticated())
        self.assertEqual(self.client().login("reset_user", "Brand-new-pass-1"), 200)
        self.assertEqual(self.client().login("reset_user"), 401)

        st_reuse, _ = anon.request("POST", "/api/auth/reset-password",
                                   {"identifier": "reset_user", "code": code, "newPassword": "Another-pass-22"})
        self.assertEqual(st_reuse, 400)

    def test_reset_password_errors_do_not_reveal_accounts(self):
        self.make_active_user("enum_user")
        anon = self.client()
        anon.request("POST", "/api/auth/forgot-password", {"identifier": "enum_user"})
        _, wrong_code = anon.request("POST", "/api/auth/reset-password",
                                     {"identifier": "enum_user", "code": "000000", "newPassword": "Whatever-123"})
        _, unknown = anon.request("POST", "/api/auth/reset-password",
                                  {"identifier": "ghost_user", "code": "000000", "newPassword": "Whatever-123"})
        self.assertEqual(wrong_code, unknown)

    def test_forgot_password_cooldown_and_rate_limits(self):
        email = self.make_active_user("limit_user")
        anon = self.client()
        anon.request("POST", "/api/auth/forgot-password", {"identifier": "limit_user"})
        anon.request("POST", "/api/auth/forgot-password", {"identifier": "limit_user"})
        self.assertEqual(len(self.mails_to(email)), 1, "second request inside the 60 s cooldown must not send a new code")

        statuses = [anon.request("POST", "/api/auth/forgot-password", {"identifier": f"x{i}"})[0] for i in range(4)]
        self.assertEqual(statuses[-1], 429, "a client IP is limited to 5 recovery requests per hour")

    def test_reset_password_guessing_is_limited_per_ip(self):
        anon = self.client()
        statuses = [
            anon.request("POST", "/api/auth/reset-password",
                         {"identifier": f"guess{i}", "code": "123456", "newPassword": "Guessing-123"})[0]
            for i in range(21)
        ]
        self.assertEqual(statuses[:20], [400] * 20)
        self.assertEqual(statuses[20], 429)

    # email change

    def test_change_email_full_cycle(self):
        old = self.make_active_user("mail_user")
        user = self.client()
        user.login("mail_user")
        st_wrong, _ = user.request("POST", "/api/auth/change-email", {"password": "wrong-pass", "newEmail": "new@example.com"})
        self.assertEqual(st_wrong, 400)

        st, _ = user.request("POST", "/api/auth/change-email", {"password": PASSWORD, "newEmail": "new@example.com"})
        self.assertEqual(st, 200)
        self.assertEqual(len(self.mails_to(old)), 1, "the old address is warned")
        code = self.last_code("new@example.com")

        st_ver, _ = user.request("POST", "/api/auth/verify-change-email", {"code": code})
        self.assertEqual(st_ver, 200)
        settings = user.request("GET", "/api/user/settings")[1]["settings"]
        self.assertEqual(settings["email"], "new@example.com")

    def test_change_email_to_taken_address_rejected(self):
        self.make_active_user("taken_a")
        self.make_active_user("taken_b")
        user = self.client()
        user.login("taken_a")
        st, _ = user.request("POST", "/api/auth/change-email", {"password": PASSWORD, "newEmail": "taken_b@example.com"})
        self.assertEqual(st, 400)

    def test_change_email_delivery_failure_keeps_old_address(self):
        old = self.make_active_user("fail_user")
        user = self.client()
        user.login("fail_user")
        EMAIL_SERVICE.set_simulate_failure(True)
        st, _ = user.request("POST", "/api/auth/change-email", {"password": PASSWORD, "newEmail": "lost@example.com"})
        self.assertEqual(st, 502)
        EMAIL_SERVICE.set_simulate_failure(False)
        settings = user.request("GET", "/api/user/settings")[1]["settings"]
        self.assertEqual(settings["email"], old)
        self.assertEqual(self.client().login("fail_user"), 200)

    # password change and sessions

    def test_change_password_keeps_this_device_and_revokes_others(self):
        self.make_active_user("pass_user")
        this_device, other_device = self.client(), self.client()
        this_device.login("pass_user")
        other_device.login("pass_user")

        st_wrong, _ = this_device.request("POST", "/api/auth/change-password",
                                          {"currentPassword": "nope-nope", "newPassword": "Second-pass-123"})
        self.assertEqual(st_wrong, 400)

        st, body = this_device.request("POST", "/api/auth/change-password",
                                       {"currentPassword": PASSWORD, "newPassword": "Second-pass-123"})
        self.assertEqual(st, 200)
        self.assertTrue(body.get("csrfToken"))
        self.assertTrue(this_device.authenticated())
        self.assertFalse(other_device.authenticated())
        self.assertEqual(self.client().login("pass_user", "Second-pass-123"), 200)

    def test_logout_all_revokes_every_session(self):
        self.make_active_user("out_user")
        first, second = self.client(), self.client()
        first.login("out_user")
        second.login("out_user")
        st, _ = first.request("POST", "/api/auth/logout-all", {})
        self.assertEqual(st, 200)
        self.assertFalse(first.authenticated())
        self.assertFalse(second.authenticated())

    # registration takeover

    def test_pending_registration_cannot_be_taken_over(self):
        owner, intruder = self.client(), self.client()
        st, _ = owner.request("POST", "/api/auth/register",
                              {"login": "owner_login", "email": "owner@example.com", "password": PASSWORD})
        self.assertEqual(st, 201)
        st_intr, _ = intruder.request("POST", "/api/auth/register",
                                      {"login": "intruder_login", "email": "owner@example.com", "password": "Intruder-123"})
        self.assertEqual(st_intr, 409)

        code = self.last_code("owner@example.com")
        st_steal, _ = intruder.request("POST", "/api/auth/verify-email", {"email": "owner@example.com", "code": code})
        self.assertEqual(st_steal, 400, "a code without the registration token of this browser is rejected")

        st_ok, _ = owner.request("POST", "/api/auth/verify-email", {"email": "owner@example.com", "code": code})
        self.assertEqual(st_ok, 200)
        self.assertEqual(self.client().login("owner_login"), 200)
        self.assertEqual(self.client().login("intruder_login", "Intruder-123"), 401)

    def test_owner_cannot_activate_registration_made_by_someone_else(self):
        intruder, owner = self.client(), self.client()
        intruder.request("POST", "/api/auth/register",
                         {"login": "squatter", "email": "victim@example.com", "password": "Intruder-123"})
        code = self.last_code("victim@example.com")
        # The mailbox owner types the code they received, but in their own browser
        st, _ = owner.request("POST", "/api/auth/verify-email", {"email": "victim@example.com", "code": code})
        self.assertEqual(st, 400)
        self.assertEqual(self.client().login("squatter", "Intruder-123"), 403, "the account stays pending")

    def test_expired_pending_registration_releases_login(self):
        first = self.client()
        first.request("POST", "/api/auth/register",
                      {"login": "free_login", "email": "first@example.com", "password": PASSWORD})
        conn = self.db()
        past = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1)).isoformat()
        with conn:
            conn.execute("UPDATE email_verifications SET expires_at = ? WHERE email = ?", (past, "first@example.com"))
        conn.close()

        second = self.client()
        st, _ = second.request("POST", "/api/auth/register",
                               {"login": "free_login", "email": "second@example.com", "password": PASSWORD})
        self.assertEqual(st, 201)


if __name__ == "__main__":
    unittest.main()
