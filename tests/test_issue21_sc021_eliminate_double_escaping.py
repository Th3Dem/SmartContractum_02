#!/usr/bin/env python3
"""
tests/test_issue21_sc021_eliminate_double_escaping.py

Comprehensive regression test suite for Issue #21 (SC-021):
"Устранить двойное экранирование plain-text полей".

Verifies:
1. Article comments (article_comments.content):
   - POST /api/articles/<id>/comments stores raw plain-text in SQLite.
   - Returns unescaped raw plain-text in API response comment.content.
   - GET /api/articles/<id>/comments returns unescaped raw plain-text.
   - Special characters & < > " ' are preserved intact without double-escaping.
   - Length validation (5000 chars) and non-empty checks remain strictly enforced.
2. User profile fields (user_profiles.name, specialization, company, bio):
   - POST /api/user/profile stores raw stripped strings in SQLite.
   - Returns unescaped raw strings in API response profile object.
   - GET /api/user/profile returns unescaped raw strings.
   - Special characters & < > " ' are preserved intact without double-escaping.
3. Frontend single-escaping contracts:
   - Verifies escapeHtml logic in article.js and feed.js produces single-escaped HTML.
   - Ensures no double-escaped entities (&amp;amp;, &amp;lt;, &amp;gt;, &amp;quot;).
   - Validates that DOM rendering of escapeHtml output is safe from XSS.
"""

import datetime
import html
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
import urllib.request
from typing import Optional, Tuple

import server
from server import create_server, init_db

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


def client_escape_html(s: str) -> str:
    """
    Exact simulation of escapeHtml() from frontend/public/js/article.js
    and frontend/public/js/feed.js:
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    """
    if not s:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )


class TestIssue21EliminateDoubleEscaping(unittest.TestCase):
    """Test suite for Issue #21 (SC-021) verifying plain-text storage and single escaping."""

    @classmethod
    def setUpClass(cls):
        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue21_sc021.db")
        cls.media_dir = os.path.join(cls.temp_dir, "media")
        os.makedirs(cls.media_dir, exist_ok=True)
        server.DEFAULT_DB_PATH = cls.db_path
        server.MEDIA_DIR = cls.media_dir

        conn = init_db(cls.db_path)
        conn.close()

        cls.httpd = create_server(
            host="127.0.0.1",
            port=0,
            db_path=cls.db_path,
            directory=FRONTEND_DIR,
            media_dir=cls.media_dir,
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
        if os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self):
        # Create an approved article in SQLite for comment testing
        conn = sqlite3.connect(self.db_path)
        with conn:
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            conn.execute("""
                INSERT OR REPLACE INTO moderation_submissions (
                    id, draft_id, author_id, title, article_html, article_delta,
                    publication_settings, snapshot_hash, status, created_at, updated_at
                ) VALUES (
                    'art_test_21', 'draft_21', 'alice', 'Статья для тестирования Issue 21',
                    '<p>Тестовый контент</p>', '{}', '{"materialType": "article"}', 'hash21',
                    'approved', ?, ?
                )
            """, (now_iso, now_iso))
        conn.close()

        # Log in alice to obtain auth session cookie
        login_url = f"{self.base_url}/api/auth/login"
        payload = json.dumps({"userId": "alice", "name": "Алиса", "role": "user"}).encode("utf-8")
        req = urllib.request.Request(
            login_url,
            data=payload,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            self.alice_cookie = resp.headers.get("Set-Cookie", "")

    def _post_json(self, path: str, payload: dict, cookie: Optional[str] = None) -> Tuple[int, dict]:
        """Sends POST request with JSON payload and returns (status_code, json_dict)."""
        url = f"{self.base_url}{path}"
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if cookie:
            headers["Cookie"] = cookie
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return resp.status, data
        except urllib.error.HTTPError as e:
            try:
                data = json.loads(e.read().decode("utf-8"))
            except Exception:
                data = {"error": str(e)}
            return e.code, data

    def _get_json(self, path: str, cookie: Optional[str] = None) -> Tuple[int, dict]:
        """Sends GET request and returns (status_code, json_dict)."""
        url = f"{self.base_url}{path}"
        headers = {}
        if cookie:
            headers["Cookie"] = cookie
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return resp.status, data
        except urllib.error.HTTPError as e:
            try:
                data = json.loads(e.read().decode("utf-8"))
            except Exception:
                data = {"error": str(e)}
            return e.code, data

    # -------------------------------------------------------------------------
    # 1. Article Comments Tests
    # -------------------------------------------------------------------------

    def test_01_comment_with_special_characters_stored_and_returned_raw(self):
        """
        Verify that a comment containing &, <, >, ", ' is saved and returned
        in its exact raw plain-text format without server-side html.escape.
        """
        raw_content = "Проверка <script>alert('xss')</script> & \"кавычки\" 'апостроф' > < &amp;"
        status, data = self._post_json(
            "/api/articles/art_test_21/comments",
            {"content": raw_content, "commentType": "comment"},
            cookie=self.alice_cookie,
        )
        self.assertEqual(status, 201)
        self.assertTrue(data.get("success"))

        comment = data["comment"]
        # Must match raw text exactly
        self.assertEqual(comment["content"], raw_content)
        self.assertIn("<script>", comment["content"])
        self.assertIn("&", comment["content"])
        self.assertIn('"', comment["content"])
        self.assertIn("'", comment["content"])
        # Must NOT contain server-pre-escaped entities
        self.assertNotIn("&lt;script&gt;", comment["content"])
        self.assertNotIn("&amp;amp;", comment["content"])

        # Verify via GET endpoint
        status_get, data_get = self._get_json("/api/articles/art_test_21/comments")
        self.assertEqual(status_get, 200)
        matching_comments = [c for c in data_get["comments"] if c["id"] == comment["id"]]
        self.assertEqual(len(matching_comments), 1)
        self.assertEqual(matching_comments[0]["content"], raw_content)

        # Verify direct storage in SQLite database
        conn = sqlite3.connect(self.db_path)
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT content FROM article_comments WHERE id = ?", (comment["id"],))
            row = cur.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], raw_content)
        conn.close()

    def test_02_comment_multiline_and_whitespaces(self):
        """Verify leading/trailing whitespaces are stripped, but newlines and internal spaces are preserved."""
        multiline_raw = "Строка 1\nСтрока 2 <tag> & text\nСтрока 3"
        content_with_padding = f"   \n{multiline_raw}\n   "
        status, data = self._post_json(
            "/api/articles/art_test_21/comments",
            {"content": content_with_padding, "commentType": "comment"},
            cookie=self.alice_cookie,
        )
        self.assertEqual(status, 201)
        comment = data["comment"]
        self.assertEqual(comment["content"], multiline_raw)

    def test_03_comment_validation_rules_maintained(self):
        """Verify empty comments and comments exceeding 5000 chars are rejected."""
        # Empty comment
        status, data = self._post_json(
            "/api/articles/art_test_21/comments",
            {"content": "   ", "commentType": "comment"},
            cookie=self.alice_cookie,
        )
        self.assertEqual(status, 400)
        self.assertFalse(data.get("success"))

        # Exactly 5000 characters accepted
        boundary_5000 = "x" * 5000
        status_ok, data_ok = self._post_json(
            "/api/articles/art_test_21/comments",
            {"content": boundary_5000, "commentType": "comment"},
            cookie=self.alice_cookie,
        )
        self.assertEqual(status_ok, 201)
        self.assertEqual(data_ok["comment"]["content"], boundary_5000)

        # 5001 characters rejected
        too_long = "x" * 5001
        status_fail, data_fail = self._post_json(
            "/api/articles/art_test_21/comments",
            {"content": too_long, "commentType": "comment"},
            cookie=self.alice_cookie,
        )
        self.assertEqual(status_fail, 400)
        self.assertFalse(data_fail.get("success"))

    # -------------------------------------------------------------------------
    # 2. User Profile Fields Tests
    # -------------------------------------------------------------------------

    def test_04_user_profile_special_characters_stored_and_returned_raw(self):
        """
        Verify that profile fields (name, specialization, company, bio) containing
        &, <, >, ", ' are stored and returned as raw plain-text strings.
        """
        profile_payload = {
            "name": 'Алиса & "Боб" <Tech>',
            "specialization": 'Senior <Backend & Frontend> "Architect"',
            "company": 'ООО "Вектор" & Co <LLC>',
            "bio": 'Инженер: <c++>, python & rust. Пишет "чистый" код без \'багов\'.'
        }
        status, data = self._post_json("/api/user/profile", profile_payload, cookie=self.alice_cookie)
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))

        prof = data["profile"]
        self.assertEqual(prof["name"], profile_payload["name"])
        self.assertEqual(prof["specialization"], profile_payload["specialization"])
        self.assertEqual(prof["company"], profile_payload["company"])
        self.assertEqual(prof["bio"], profile_payload["bio"])

        # Check that no escaped HTML entities are present in API response
        for key in ("name", "specialization", "company", "bio"):
            val = prof[key]
            self.assertNotIn("&lt;", val)
            self.assertNotIn("&gt;", val)
            self.assertNotIn("&quot;", val)

        # Verify via GET /api/user/profile
        status_get, data_get = self._get_json("/api/user/profile", cookie=self.alice_cookie)
        self.assertEqual(status_get, 200)
        prof_get = data_get["profile"]
        self.assertEqual(prof_get["name"], profile_payload["name"])
        self.assertEqual(prof_get["specialization"], profile_payload["specialization"])
        self.assertEqual(prof_get["company"], profile_payload["company"])
        self.assertEqual(prof_get["bio"], profile_payload["bio"])

        # Verify direct storage in SQLite database
        conn = sqlite3.connect(self.db_path)
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT name, specialization, company, bio FROM user_profiles WHERE user_id = ?", ("alice",))
            row = cur.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], profile_payload["name"])
            self.assertEqual(row[1], profile_payload["specialization"])
            self.assertEqual(row[2], profile_payload["company"])
            self.assertEqual(row[3], profile_payload["bio"])
        conn.close()

    def test_05_user_profile_whitespace_handling_and_defaults(self):
        """Verify profile string values are stripped and empty fields do not cause null errors."""
        profile_payload = {
            "name": "   Только имя   ",
            "specialization": "   ",
            "company": "",
            "bio": "   "
        }
        status, data = self._post_json("/api/user/profile", profile_payload, cookie=self.alice_cookie)
        self.assertEqual(status, 200)
        prof = data["profile"]
        self.assertEqual(prof["name"], "Только имя")
        self.assertEqual(prof["specialization"], "")
        self.assertEqual(prof["company"], "")
        self.assertEqual(prof["bio"], "")

    # -------------------------------------------------------------------------
    # 3. Single Escaping Contract and Frontend Verification
    # -------------------------------------------------------------------------

    def test_06_frontend_single_escaping_contract(self):
        """
        Verify that client_escape_html (matching frontend escapeHtml implementation)
        produces single escaping on raw plain-text and does NOT cause double-escaping.
        """
        raw_text = 'Тест & <script>alert("xss")</script> > "кавычки" \'апостроф\''
        escaped = client_escape_html(raw_text)

        # Single escaping assertions
        self.assertIn("&amp;", escaped)
        self.assertIn("&lt;script&gt;", escaped)
        self.assertIn("&quot;кавычки&quot;", escaped)
        self.assertIn("&#039;апостроф&#039;", escaped)

        # Ensure NO double escaping exists
        self.assertNotIn("&amp;amp;", escaped)
        self.assertNotIn("&amp;lt;", escaped)
        self.assertNotIn("&amp;gt;", escaped)
        self.assertNotIn("&amp;quot;", escaped)
        self.assertNotIn("&amp;#039;", escaped)

        # Verify unescaping returns original plain-text exactly
        unescaped = html.unescape(escaped)
        self.assertEqual(unescaped, raw_text)

    def test_07_demonstrate_previous_double_escaping_bug_eliminated(self):
        """
        Demonstrate that before SC-021:
          html.escape(raw) -> &lt;script&gt;
          escapeHtml(html.escape(raw)) -> &amp;lt;script&amp;gt; (double escaped!)
        With SC-021:
          raw plain-text stored -> escapeHtml(raw) -> &lt;script&gt; (single escaped, safely rendered).
        """
        raw_sample = '<script>alert("XSS")</script>'
        legacy_server_escaped = html.escape(raw_sample)
        legacy_double_escaped = client_escape_html(legacy_server_escaped)

        # The buggy behavior had &amp;lt;
        self.assertIn("&amp;lt;", legacy_double_escaped)
        self.assertIn("&amp;gt;", legacy_double_escaped)

        # The new behavior stores raw_sample and escapes once on the client
        sc021_client_escaped = client_escape_html(raw_sample)
        self.assertNotIn("&amp;lt;", sc021_client_escaped)
        self.assertIn("&lt;script&gt;", sc021_client_escaped)
        self.assertEqual(html.unescape(sc021_client_escaped), raw_sample)

    def test_08_verify_frontend_code_files_contain_escape_html(self):
        """Verify that frontend js files properly call escapeHtml at DOM boundaries."""
        article_js_path = os.path.join(FRONTEND_DIR, "js", "article.js")
        feed_js_path = os.path.join(FRONTEND_DIR, "js", "feed.js")
        profile_js_path = os.path.join(FRONTEND_DIR, "js", "profile.js")

        with open(article_js_path, "r", encoding="utf-8") as f:
            article_js = f.read()

        with open(feed_js_path, "r", encoding="utf-8") as f:
            feed_js = f.read()

        profile_js = ""
        if os.path.exists(profile_js_path):
            with open(profile_js_path, "r", encoding="utf-8") as f:
                profile_js = f.read()

        # Files must define escapeHtml
        self.assertIn("function escapeHtml(str)", article_js)
        self.assertIn("function escapeHtml(str)", feed_js)
        if profile_js:
            self.assertIn("function escapeHtml(str)", profile_js)

        # article.js must escape comment.content before injecting into comment-text
        self.assertTrue(
            bool(re.search(r"escapeHtml\(\s*comment\.content\s*\)", article_js)),
            "article.js must escape comment.content using escapeHtml()",
        )

        # Author card (profile.js, Issues #271, #272) must escape every user field it renders.
        # The card shows name, initials, bio and the profile link; specialization and company
        # live only on the full profile page.
        for field in ("name", "initials", "bio", "profileUrl", "p.avatar"):
            self.assertTrue(
                bool(re.search(r"escapeHtml\(\s*" + re.escape(field) + r"\s*\)", profile_js)),
                "profile.js must escape %s using escapeHtml()" % field,
            )

if __name__ == "__main__":
    unittest.main()
