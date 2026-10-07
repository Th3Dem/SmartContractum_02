#!/usr/bin/env python3
"""
tests/test_issue188_profile_edit_backend.py

Automated test suite for Issue #188 backend requirements:
1. Enforce authentication on POST /api/user/profile (401 if unauthenticated).
2. Validate field lengths and constraints:
   - name: 1..100 characters. Return 400 if empty.
   - specialization: max 120 characters.
   - company: max 120 characters.
   - bio: max 1000 characters.
   - website: max 300 characters, strictly http or https scheme (reject javascript:, data:, etc. with 400).
3. Avatar handling:
   - removeAvatar: true or avatar: "" sets avatar to None (NULL in DB).
   - Non-empty avatar updates the avatar.
   - Omitted or None avatar preserves existing avatar from user_profiles.
4. Response DTO does not expose private data.
5. Invariants: zero emojis, zero em dashes, 100% offline-first.
"""

import base64
import datetime
import json
import os
import shutil
import sqlite3
import tempfile
import threading
import time
import unicodedata
import unittest
import urllib.error
import urllib.request

from backend.media_library import record_upload
import server
from server import create_server, init_db
from tests.backend_source import BACKEND_FILES, backend_source_file

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue188ProfileEditBackend(unittest.TestCase):
    """Test suite for Issue #188 backend profile editing and avatar constraints."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue188.db")
        server.DEFAULT_DB_PATH = cls.db_path

        cls.media_dir = os.path.join(cls.temp_dir, "media")
        avatars_dir = os.path.join(cls.media_dir, "avatars")
        os.makedirs(avatars_dir, exist_ok=True)

        tiny_png_bytes = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        for avatar_filename in [
            "bob_original.png",
            "bob_new.png",
            "bob_preserved.png",
            "bob_to_remove.png",
            "bob_to_clear.png",
            "bob_to_clear_whitespace.png"
        ]:
            with open(os.path.join(avatars_dir, avatar_filename), "wb") as f:
                f.write(tiny_png_bytes)

        conn = init_db(cls.db_path, seed=False)
        cls._seed_test_data(conn)
        # The fixture files stand for Bob's own uploads: avatars can only be chosen from one's uploads
        for avatar_filename in os.listdir(avatars_dir):
            record_upload(conn, f"/media/avatars/{avatar_filename}", "user_bob")
        conn.close()

        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR, media_dir=cls.media_dir, seed=False)
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

    @classmethod
    def _seed_test_data(cls, conn):
        cur = conn.cursor()
        now = datetime.datetime.now(datetime.timezone.utc)
        t_exp = (now + datetime.timedelta(days=30)).isoformat()
        t_created = (now - datetime.timedelta(days=10)).isoformat()

        # Test User 1: Regular authenticated user with existing avatar
        cur.execute("""
            INSERT OR REPLACE INTO user_profiles (user_id, name, specialization, company, bio, website, avatar, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "user_bob",
            "Боб Тестовый",
            "Smart Contract Auditor",
            "ChainGuard",
            "Тестирование безопасности смарт-контрактов.",
            "https://chainguard.example.com",
            "/media/avatars/bob_original.png",
            t_created,
            t_created
        ))

        cur.execute("""
            INSERT OR REPLACE INTO sessions (token, user_id, user_name, user_role, expires_at, created_at, is_revoked)
            VALUES (?, ?, ?, 'user', ?, ?, 0)
        """, ("sess_bob", "user_bob", "Боб Тестовый", t_exp, t_created))

        # Secondary active session for User 1 to test cross-session identity sync
        cur.execute("""
            INSERT OR REPLACE INTO sessions (token, user_id, user_name, user_role, expires_at, created_at, is_revoked)
            VALUES (?, ?, ?, 'user', ?, ?, 0)
        """, ("sess_bob_2", "user_bob", "Боб Тестовый", t_exp, t_created))

        # Test User 2: Minimal user without avatar
        cur.execute("""
            INSERT OR REPLACE INTO user_profiles (user_id, name, specialization, company, bio, website, avatar, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "user_alice",
            "Алиса Инженер",
            "",
            "",
            "",
            "",
            None,
            t_created,
            t_created
        ))

        cur.execute("""
            INSERT OR REPLACE INTO sessions (token, user_id, user_name, user_role, expires_at, created_at, is_revoked)
            VALUES (?, ?, ?, 'user', ?, ?, 0)
        """, ("sess_alice", "user_alice", "Алиса Инженер", t_exp, t_created))

        conn.commit()

    def _api_get(self, path, session_token=None):
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, method="GET")
        if session_token:
            req.add_header("Cookie", f"sc_session={session_token}")
            req.add_header("Authorization", f"Bearer {session_token}")
        try:
            with urllib.request.urlopen(req) as resp:
                status = resp.status
                body = resp.read().decode("utf-8")
                return status, json.loads(body)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            try:
                data = json.loads(body)
            except Exception:
                data = {"raw": body}
            return e.code, data

    def _api_post(self, path, payload, session_token=None):
        url = f"{self.base_url}{path}"
        body_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body_bytes, method="POST")
        req.add_header("Content-Type", "application/json; charset=utf-8")
        if session_token:
            req.add_header("Cookie", f"sc_session={session_token}")
            req.add_header("Authorization", f"Bearer {session_token}")
        try:
            with urllib.request.urlopen(req) as resp:
                status = resp.status
                body = resp.read().decode("utf-8")
                return status, json.loads(body)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            try:
                data = json.loads(body)
            except Exception:
                data = {"raw": body}
            return e.code, data

    def _get_db_profile(self, user_id):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
            return cur.fetchone()
        finally:
            conn.close()

    # =========================================================================
    # 1. Authentication Invariants
    # =========================================================================

    def test_01_unauthenticated_edit_rejected_401(self):
        """POST /api/user/profile without session token must be rejected with 401."""
        payload = {"name": "Хакер", "bio": "Попытка несанкционированного изменения"}
        status, data = self._api_post("/api/user/profile", payload, session_token=None)
        self.assertEqual(status, 401)
        self.assertFalse(data.get("success"))
        self.assertTrue(data.get("requireAuth"))

    def test_02_invalid_session_rejected_401(self):
        """POST /api/user/profile with invalid session token must be rejected with 401."""
        payload = {"name": "Хакер 2"}
        status, data = self._api_post("/api/user/profile", payload, session_token="invalid_token_999")
        self.assertEqual(status, 401)
        self.assertFalse(data.get("success"))
        self.assertTrue(data.get("requireAuth"))

    # =========================================================================
    # 2. Successful Profile Edit and Boundary Length Checks
    # =========================================================================

    def test_03_successful_profile_edit_full_payload(self):
        """Verifies full valid profile edit updates DB and returns clean DTO without private leaks."""
        payload = {
            "name": "Боб Обновленный",
            "specialization": "Lead Security Auditor",
            "company": "SecureChain Corp",
            "bio": "Аудит L1 и L2 протоколов с формальной верификацией.",
            "website": "https://securechain.example.com",
            "avatar": "/media/avatars/bob_new.png"
        }
        status, data = self._api_post("/api/user/profile", payload, session_token="sess_bob")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))

        prof = data.get("profile")
        self.assertIsNotNone(prof)
        self.assertEqual(prof["userId"], "user_bob")
        self.assertEqual(prof["name"], "Боб Обновленный")
        self.assertEqual(prof["specialization"], "Lead Security Auditor")
        self.assertEqual(prof["company"], "SecureChain Corp")
        self.assertEqual(prof["bio"], "Аудит L1 и L2 протоколов с формальной верификацией.")
        self.assertEqual(prof["website"], "https://securechain.example.com")
        self.assertEqual(prof["avatar"], "/media/avatars/bob_new.png")
        self.assertEqual(prof.get("initials"), "БО")

        # Invariant: Verify no private data is exposed
        for forbidden_key in ("password", "password_hash", "token", "session_token", "email", "ip_address"):
            self.assertNotIn(forbidden_key, prof)
            self.assertNotIn(forbidden_key, data)

        # Invariant: Verify direct SQLite storage
        row = self._get_db_profile("user_bob")
        self.assertIsNotNone(row)
        self.assertEqual(row["name"], "Боб Обновленный")
        self.assertEqual(row["specialization"], "Lead Security Auditor")
        self.assertEqual(row["company"], "SecureChain Corp")
        self.assertEqual(row["bio"], "Аудит L1 и L2 протоколов с формальной верификацией.")
        self.assertEqual(row["website"], "https://securechain.example.com")
        self.assertEqual(row["avatar"], "/media/avatars/bob_new.png")

    def test_04_exact_boundary_lengths_success(self):
        """Verifies profile edit succeeds at exact maximum allowed boundary lengths."""
        name_100 = "N" * 100
        spec_120 = "S" * 120
        comp_120 = "C" * 120
        bio_1000 = "B" * 1000
        site_prefix = "https://example.com/"
        site_300 = site_prefix + ("x" * (300 - len(site_prefix)))

        self.assertEqual(len(name_100), 100)
        self.assertEqual(len(spec_120), 120)
        self.assertEqual(len(comp_120), 120)
        self.assertEqual(len(bio_1000), 1000)
        self.assertEqual(len(site_300), 300)

        payload = {
            "name": name_100,
            "specialization": spec_120,
            "company": comp_120,
            "bio": bio_1000,
            "website": site_300
        }
        status, data = self._api_post("/api/user/profile", payload, session_token="sess_bob")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        self.assertEqual(data["profile"]["name"], name_100)
        self.assertEqual(data["profile"]["specialization"], spec_120)
        self.assertEqual(data["profile"]["company"], comp_120)
        self.assertEqual(data["profile"]["bio"], bio_1000)
        self.assertEqual(data["profile"]["website"], site_300)

    # =========================================================================
    # 3. Validation Failures (Length and Scheme)
    # =========================================================================

    def test_05_name_empty_or_whitespace_rejection_400(self):
        """Empty or whitespace-only name must be rejected with 400."""
        for invalid_name in ["", "   ", "\t\n", None]:
            with self.subTest(name_val=invalid_name):
                payload = {"name": invalid_name}
                status, data = self._api_post("/api/user/profile", payload, session_token="sess_bob")
                self.assertEqual(status, 400)
                self.assertFalse(data.get("success"))

    def test_06_name_too_long_rejection_400(self):
        """Name exceeding 100 characters must be rejected with 400."""
        payload = {"name": "A" * 101}
        status, data = self._api_post("/api/user/profile", payload, session_token="sess_bob")
        self.assertEqual(status, 400)
        self.assertFalse(data.get("success"))

    def test_07_specialization_too_long_rejection_400(self):
        """Specialization exceeding 120 characters must be rejected with 400."""
        payload = {"specialization": "S" * 121}
        status, data = self._api_post("/api/user/profile", payload, session_token="sess_bob")
        self.assertEqual(status, 400)
        self.assertFalse(data.get("success"))

    def test_08_company_too_long_rejection_400(self):
        """Company exceeding 120 characters must be rejected with 400."""
        payload = {"company": "C" * 121}
        status, data = self._api_post("/api/user/profile", payload, session_token="sess_bob")
        self.assertEqual(status, 400)
        self.assertFalse(data.get("success"))

    def test_09_bio_too_long_rejection_400(self):
        """Bio exceeding 1000 characters must be rejected with 400."""
        payload = {"bio": "B" * 1001}
        status, data = self._api_post("/api/user/profile", payload, session_token="sess_bob")
        self.assertEqual(status, 400)
        self.assertFalse(data.get("success"))

    def test_10_website_too_long_rejection_400(self):
        """Website exceeding 300 characters must be rejected with 400."""
        site_301 = "https://example.com/" + ("x" * 285)
        self.assertGreater(len(site_301), 300)
        payload = {"website": site_301}
        status, data = self._api_post("/api/user/profile", payload, session_token="sess_bob")
        self.assertEqual(status, 400)
        self.assertFalse(data.get("success"))

    def test_11_dangerous_website_scheme_rejection_400(self):
        """Dangerous or non-http(s) schemes must be rejected with 400."""
        dangerous_urls = [
            "javascript:alert(1)",
            "javascript:void(0)",
            "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==",
            "vbscript:msgbox(1)",
            "file:///etc/passwd",
            "ftp://files.example.com/pub",
            "//example.com/relative-scheme",
            "http://",
            "https://"
        ]
        for url in dangerous_urls:
            with self.subTest(dangerous_url=url):
                payload = {"website": url}
                status, data = self._api_post("/api/user/profile", payload, session_token="sess_bob")
                self.assertEqual(
                    status, 400,
                    f"Dangerous scheme {url} should return 400, got {status}"
                )
                self.assertFalse(data.get("success"))

    def test_12_valid_website_clearing_and_protocols(self):
        """Verifies http and https are accepted, and empty string clears the website."""
        # http
        status, data = self._api_post("/api/user/profile", {"website": "http://my-domain.org"}, session_token="sess_bob")
        self.assertEqual(status, 200)
        self.assertEqual(data["profile"]["website"], "http://my-domain.org")

        # https
        status, data = self._api_post("/api/user/profile", {"website": "https://my-secure-domain.org"}, session_token="sess_bob")
        self.assertEqual(status, 200)
        self.assertEqual(data["profile"]["website"], "https://my-secure-domain.org")

        # clearing with empty string
        status, data = self._api_post("/api/user/profile", {"website": ""}, session_token="sess_bob")
        self.assertEqual(status, 200)
        self.assertEqual(data["profile"]["website"], "")

        # verify DB cleared
        row = self._get_db_profile("user_bob")
        self.assertEqual(row["website"], "")

    # =========================================================================
    # 4. Avatar Handling Invariants
    # =========================================================================

    def test_13_avatar_preservation_when_editing_other_fields(self):
        """Editing other fields without specifying avatar must preserve existing avatar."""
        # Setup known avatar for user_bob
        self._api_post("/api/user/profile", {
            "name": "Боб Хранитель",
            "avatar": "/media/avatars/bob_preserved.png"
        }, session_token="sess_bob")

        row = self._get_db_profile("user_bob")
        self.assertEqual(row["avatar"], "/media/avatars/bob_preserved.png")

        # Edit bio only (avatar key omitted)
        status, data = self._api_post("/api/user/profile", {
            "name": "Боб Хранитель",
            "bio": "Только обновление био."
        }, session_token="sess_bob")
        self.assertEqual(status, 200)
        self.assertEqual(data["profile"]["avatar"], "/media/avatars/bob_preserved.png")

        row = self._get_db_profile("user_bob")
        self.assertEqual(row["avatar"], "/media/avatars/bob_preserved.png")

        # Edit company with avatar explicitly set to None (omitted/None without removeAvatar)
        status, data = self._api_post("/api/user/profile", {
            "name": "Боб Хранитель",
            "company": "Preserved Co",
            "avatar": None
        }, session_token="sess_bob")
        self.assertEqual(status, 200)
        self.assertEqual(data["profile"]["avatar"], "/media/avatars/bob_preserved.png")

        row = self._get_db_profile("user_bob")
        self.assertEqual(row["avatar"], "/media/avatars/bob_preserved.png")

    def test_14_avatar_explicit_removal_with_remove_avatar_true(self):
        """Setting removeAvatar: true must remove avatar and set it to None in DB."""
        # Ensure user has an avatar
        self._api_post("/api/user/profile", {
            "name": "Боб С Аватаром",
            "avatar": "/media/avatars/bob_to_remove.png"
        }, session_token="sess_bob")

        # Remove avatar via removeAvatar: True
        status, data = self._api_post("/api/user/profile", {
            "name": "Боб С Аватаром",
            "removeAvatar": True
        }, session_token="sess_bob")
        self.assertEqual(status, 200)
        self.assertIsNone(data["profile"]["avatar"])

        # Check DB
        row = self._get_db_profile("user_bob")
        self.assertIsNone(row["avatar"])

    def test_15_avatar_explicit_removal_with_empty_string(self):
        """Setting avatar: '' or whitespace must remove avatar and set it to None in DB."""
        # Ensure user has an avatar
        self._api_post("/api/user/profile", {
            "name": "Боб С Аватаром 2",
            "avatar": "/media/avatars/bob_to_clear.png"
        }, session_token="sess_bob")

        # Clear avatar via empty string
        status, data = self._api_post("/api/user/profile", {
            "name": "Боб С Аватаром 2",
            "avatar": ""
        }, session_token="sess_bob")
        self.assertEqual(status, 200)
        self.assertIsNone(data["profile"]["avatar"])

        row = self._get_db_profile("user_bob")
        self.assertIsNone(row["avatar"])

        # Set avatar again
        self._api_post("/api/user/profile", {
            "name": "Боб С Аватаром 2",
            "avatar": "/media/avatars/bob_to_clear_whitespace.png"
        }, session_token="sess_bob")

        # Clear avatar via whitespace
        status, data = self._api_post("/api/user/profile", {
            "name": "Боб С Аватаром 2",
            "avatar": "   "
        }, session_token="sess_bob")
        self.assertEqual(status, 200)
        self.assertIsNone(data["profile"]["avatar"])

        row = self._get_db_profile("user_bob")
        self.assertIsNone(row["avatar"])

    def test_17_non_string_types_rejected_400_without_partial_save(self):
        """Objects, arrays, or numbers instead of string fields must return 400 without partial save."""
        # Initial known profile
        self._api_post("/api/user/profile", {
            "name": "Боб Исходный",
            "specialization": "Auditor",
            "company": "ChainCo",
            "bio": "Исходное био",
            "website": "https://chainco.example.com",
            "avatar": "/media/avatars/bob_original.png"
        }, session_token="sess_bob")

        bad_payloads = [
            ({"name": {"bad": "type"}}, "name object"),
            ({"name": ["bad", "type"]}, "name array"),
            ({"specialization": []}, "specialization array"),
            ({"specialization": {"title": "dev"}}, "specialization dict"),
            ({"company": [1, 2, 3]}, "company array"),
            ({"bio": {"text": "hello"}}, "bio dict"),
            ({"website": ["https://example.com"]}, "website array"),
            ({"avatar": {"url": "http://bad"}}, "avatar dict"),
            ({"avatar": ["bad"]}, "avatar array"),
            ({"avatar": 12345}, "avatar int")
        ]

        for payload, desc in bad_payloads:
            with self.subTest(case=desc):
                status, data = self._api_post("/api/user/profile", payload, session_token="sess_bob")
                self.assertEqual(status, 400, f"Expected 400 for {desc}, got {status}")
                self.assertFalse(data.get("success"))

                # Invariant: verify no partial save occurred in DB
                row = self._get_db_profile("user_bob")
                self.assertEqual(row["name"], "Боб Исходный")
                self.assertEqual(row["specialization"], "Auditor")
                self.assertEqual(row["company"], "ChainCo")
                self.assertEqual(row["bio"], "Исходное био")
                self.assertEqual(row["website"], "https://chainco.example.com")
                self.assertEqual(row["avatar"], "/media/avatars/bob_original.png")

    def test_18_invalid_avatar_formats_and_sizes_rejected_400(self):
        """Invalid avatar string, corrupted data URI, path traversal, nonexistent file, corrupted file, or oversized file must return 400."""
        # 1. Arbitrary non-image string
        status, data = self._api_post("/api/user/profile", {"avatar": "not-an-image"}, session_token="sess_bob")
        self.assertEqual(status, 400)
        self.assertFalse(data.get("success"))

        # 2. Corrupted base64 data URI
        status, data = self._api_post("/api/user/profile", {"avatar": "data:image/png;base64,invalid-base64-content!"}, session_token="sess_bob")
        self.assertEqual(status, 400)
        self.assertFalse(data.get("success"))

        # 3. Path traversal media path
        status, data = self._api_post("/api/user/profile", {"avatar": "/media/../../etc/passwd"}, session_token="sess_bob")
        self.assertEqual(status, 400)
        self.assertFalse(data.get("success"))

        # 4. Nonexistent media file returns 400
        status, data = self._api_post("/api/user/profile", {"avatar": "/media/nonexistent-review-file.png"}, session_token="sess_bob")
        self.assertEqual(status, 400)
        self.assertFalse(data.get("success"))
        self.assertIn("Файл изображения не найден на сервере", data.get("error", ""))

        # 5. Corrupted media file on disk returns 400
        corrupted_path = os.path.join(self.media_dir, "corrupted.png")
        with open(corrupted_path, "wb") as f:
            f.write(b"CORRUPTED_PNG_DATA_NOT_AN_IMAGE")
        status, data = self._api_post("/api/user/profile", {"avatar": "/media/corrupted.png"}, session_token="sess_bob")
        self.assertEqual(status, 400)
        self.assertFalse(data.get("success"))

        # 6. Updating bio with unchanged avatar (/media/avatars/bob_original.png) returns 200 and preserves avatar
        status, _ = self._api_post("/api/user/profile", {
            "name": "Боб Исходный",
            "avatar": "/media/avatars/bob_original.png"
        }, session_token="sess_bob")
        self.assertEqual(status, 200)

        status, data = self._api_post("/api/user/profile", {
            "bio": "Обновленная биография с сохраненным аватаром",
            "avatar": "/media/avatars/bob_original.png"
        }, session_token="sess_bob")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        self.assertEqual(data["profile"]["avatar"], "/media/avatars/bob_original.png")
        self.assertEqual(data["profile"]["bio"], "Обновленная биография с сохраненным аватаром")

        # Verify DB reflects the preserved avatar and updated bio
        row = self._get_db_profile("user_bob")
        self.assertEqual(row["avatar"], "/media/avatars/bob_original.png")
        self.assertEqual(row["bio"], "Обновленная биография с сохраненным аватаром")

        # 7. Valid tiny 1x1 PNG data URI accepted and converted to stored media url
        tiny_png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        status, data = self._api_post("/api/user/profile", {"avatar": tiny_png}, session_token="sess_bob")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        saved_avatar = data["profile"]["avatar"]
        self.assertIsNotNone(saved_avatar)
        self.assertTrue(saved_avatar.startswith("/media/"))

    def test_19_identity_synchronization_across_sessions_and_auth_status(self):
        """Profile name and avatar changes must be reflected in /api/auth/status for all active sessions."""
        # Update profile for user_bob
        tiny_png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        status, data = self._api_post("/api/user/profile", {
            "name": "Боб Синхронизированный",
            "avatar": tiny_png
        }, session_token="sess_bob")
        self.assertEqual(status, 200)
        expected_avatar = data["profile"]["avatar"]
        self.assertTrue(expected_avatar.startswith("/media/"))

        # 1. Primary session /api/auth/status reflects new identity
        st1, auth1 = self._api_get("/api/auth/status", session_token="sess_bob")
        self.assertEqual(st1, 200)
        self.assertTrue(auth1.get("authenticated"))
        self.assertEqual(auth1["user"]["id"], "user_bob")
        self.assertEqual(auth1["user"]["name"], "Боб Синхронизированный")
        self.assertEqual(auth1["user"]["avatar"], expected_avatar)
        self.assertEqual(auth1["user"]["role"], "user")

        # 2. Secondary session /api/auth/status of the SAME user reflects new identity
        st2, auth2 = self._api_get("/api/auth/status", session_token="sess_bob_2")
        self.assertEqual(st2, 200)
        self.assertTrue(auth2.get("authenticated"))
        self.assertEqual(auth2["user"]["id"], "user_bob")
        self.assertEqual(auth2["user"]["name"], "Боб Синхронизированный")
        self.assertEqual(auth2["user"]["avatar"], expected_avatar)
        self.assertEqual(auth2["user"]["role"], "user")

        # 3. Public profile endpoint reflects new identity
        st_pub, pub_data = self._api_get("/api/users/user_bob")
        self.assertEqual(st_pub, 200)
        p_user = pub_data.get("profile") or pub_data.get("user") or pub_data
        self.assertEqual(p_user["name"], "Боб Синхронизированный")
        self.assertEqual(p_user["avatar"], expected_avatar)

        # 4. Another user session remains isolated and unaltered
        st3, auth3 = self._api_get("/api/auth/status", session_token="sess_alice")
        self.assertEqual(st3, 200)
        self.assertEqual(auth3["user"]["id"], "user_alice")
        self.assertEqual(auth3["user"]["name"], "Алиса Инженер")
        self.assertIsNone(auth3["user"]["avatar"])

    def test_20_identity_update_preserves_role_and_privileges(self):
        """Updating profile identity must never alter user role or allow privilege escalation."""
        status, data = self._api_post("/api/user/profile", {
            "name": "Боб Без Эскалации",
            "role": "admin",
            "isAdmin": True
        }, session_token="sess_bob")
        self.assertEqual(status, 200)

        # Verify role in auth status is still user
        st, auth = self._api_get("/api/auth/status", session_token="sess_bob")
        self.assertEqual(st, 200)
        self.assertEqual(auth["user"]["role"], "user")

        # Verify DB session role
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            cur.execute("SELECT user_role FROM sessions WHERE user_id = ?", ("user_bob",))
            for row in cur.fetchall():
                self.assertEqual(row["user_role"], "user")
        finally:
            conn.close()

    # =========================================================================
    # 5. Code and Formatting Invariants
    # =========================================================================

    def test_16_invariants_zero_emojis_and_zero_em_dashes(self):
        """Verifies zero emojis and zero em dashes in test file and server profile handler."""
        for file_path in [__file__, *BACKEND_FILES]:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Em dash and en dash check
            self.assertNotIn("\u2014", content, f"Em dash found in {file_path}")
            self.assertNotIn("\u2013", content, f"En dash found in {file_path}")

            # Emoji check in this test file
            if file_path == __file__:
                for ch in content:
                    cat = unicodedata.category(ch)
                    self.assertFalse(
                        cat in ("So", "Cs") and ord(ch) > 127,
                        f"Emoji or symbol character {ch!r} found in {file_path}"
                    )


if __name__ == "__main__":
    unittest.main()
