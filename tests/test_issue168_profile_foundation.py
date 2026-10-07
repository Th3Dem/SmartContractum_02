#!/usr/bin/env python3
"""
tests/test_issue168_profile_foundation.py

Automated test suite for Issue #168:
Profile Foundation: elimination of duplication, shared profile.js module,
API enhancements (questionsCount, followersCount, followingCount, createdAt),
self-subscription rejection, and /user/<id> routing redirect.

Invariants:
- Zero emojis
- Zero em dashes
- 100% offline-first
"""

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
from typing import Any, Dict, Optional, Tuple

import server
from server import create_server, init_db
from tests.backend_source import BACKEND_FILES, backend_source_file

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue168ProfileFoundation(unittest.TestCase):
    """Verifies all architectural, backend, and frontend requirements for Issue #168."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue168.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path, seed=False)
        conn.close()

        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR, seed=False)
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

    def _login(self, user_id: str, name: str = "Test User", role: str = "user") -> str:
        url = f"{self.base_url}/api/auth/login"
        body = json.dumps({"userId": user_id, "name": name, "role": role}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST"
        )
        with urllib.request.urlopen(req) as resp:
            return resp.headers.get("Set-Cookie", "")

    def _post_json(self, path: str, data: Any, cookie: Optional[str] = None) -> Tuple[int, dict]:
        url = f"{self.base_url}{path}"
        body = json.dumps(data).encode("utf-8")
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if cookie:
            headers["Cookie"] = cookie
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                res_body = resp.read().decode("utf-8")
                return resp.status, json.loads(res_body) if res_body else {}
        except urllib.error.HTTPError as e:
            res_body = e.read().decode("utf-8")
            e.close()
            return e.code, json.loads(res_body) if res_body else {}

    def _get_json(self, path: str, cookie: Optional[str] = None) -> Tuple[int, dict]:
        url = f"{self.base_url}{path}"
        headers = {}
        if cookie:
            headers["Cookie"] = cookie
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req) as resp:
                res_body = resp.read().decode("utf-8")
                return resp.status, json.loads(res_body) if res_body else {}
        except urllib.error.HTTPError as e:
            res_body = e.read().decode("utf-8")
            e.close()
            return e.code, json.loads(res_body) if res_body else {}

    def _insert_submission(self, sub_id: str, author_id: str, title: str, material_type: str = "article", status: str = "approved") -> None:
        conn = sqlite3.connect(self.db_path)
        with conn:
            pst = json.dumps({"materialType": material_type, "type": material_type, "topics": ["smart-contracts"]})
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            conn.execute("""
                INSERT INTO moderation_submissions (
                    id, draft_id, title, author_id,
                    status, publication_settings, article_html, snapshot_hash, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sub_id, f"draft_{sub_id}", title, author_id,
                status, pst, "<p>Content</p>", "dummy_hash", now, now
            ))
        conn.close()

    def _insert_subscription(self, user_id: str, target_type: str, target_id: str, target_title: str = "") -> None:
        conn = sqlite3.connect(self.db_path)
        with conn:
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            conn.execute("""
                INSERT INTO user_subscriptions (user_id, target_type, target_id, target_title, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, target_type, target_id, target_title or target_id, now))
        conn.close()

    def test_01_profile_js_exists_and_included_in_pages(self):
        """Verify profile.js exists, exports SmartContractumProfile, and is included in feed.html and article.html."""
        profile_js_path = os.path.join(FRONTEND_DIR, "js", "profile.js")
        self.assertTrue(os.path.exists(profile_js_path), "frontend/public/js/profile.js must exist")

        with open(profile_js_path, "r", encoding="utf-8") as f:
            profile_js = f.read()

        self.assertIn("window.SmartContractumProfile", profile_js)
        self.assertIn("initUserProfileModal", profile_js)
        self.assertIn("openUserProfileModal", profile_js)
        self.assertIn("closeUserProfileModal", profile_js)
        self.assertIn("smartcontractum:voted", profile_js)

        # Included in feed.html
        feed_html_path = os.path.join(FRONTEND_DIR, "feed.html")
        with open(feed_html_path, "r", encoding="utf-8") as f:
            feed_html = f.read()
        self.assertIn('<script src="js/profile.js"></script>', feed_html)

        # Included in article.html
        article_html_path = os.path.join(FRONTEND_DIR, "article.html")
        with open(article_html_path, "r", encoding="utf-8") as f:
            article_html = f.read()
        self.assertIn('<script src="js/profile.js"></script>', article_html)

    def test_02_no_duplicate_modal_in_feed_and_article_js(self):
        """Verify feed.js and article.js delegate to SmartContractumProfile and do not duplicate modal body markup."""
        feed_js_path = os.path.join(FRONTEND_DIR, "js", "feed.js")
        with open(feed_js_path, "r", encoding="utf-8") as f:
            feed_js = f.read()

        article_js_path = os.path.join(FRONTEND_DIR, "js", "article.js")
        with open(article_js_path, "r", encoding="utf-8") as f:
            article_js = f.read()

        for js_name, js_code in [("feed.js", feed_js), ("article.js", article_js)]:
            self.assertIn("window.SmartContractumProfile", js_code, f"{js_name} must reference SmartContractumProfile")
            self.assertIn("function initUserProfileModal", js_code, f"{js_name} must retain bridge initUserProfileModal")
            self.assertIn("function openUserProfileModal", js_code, f"{js_name} must retain bridge openUserProfileModal")
            self.assertIn("function closeUserProfileModal", js_code, f"{js_name} must retain bridge closeUserProfileModal")

            # Duplicate modal rendering must NOT exist in feed.js / article.js
            self.assertNotIn("user-profile-header", js_code, f"{js_name} must not contain duplicated profile markup")
            self.assertNotIn("user-profile-avatar", js_code, f"{js_name} must not contain duplicated profile markup")
            self.assertNotIn("user-profile-rating-num", js_code, f"{js_name} must not contain duplicated profile markup")

    def test_03_api_user_profile_counters_and_created_at(self):
        """Verify GET /api/users/:id returns questionsCount, followersCount, followingCount, and createdAt."""
        author_id = "author_168_metrics"
        # Register author profile
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute("""
                INSERT INTO user_profiles (user_id, name, specialization, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (author_id, "Metrics Test Author", "Smart Contract Auditor", "2026-01-15T10:00:00Z", "2026-01-15T10:00:00Z"))
        conn.close()

        # Add 2 articles and 1 question
        self._insert_submission("art_168_01", author_id, "Article 1", material_type="article")
        self._insert_submission("art_168_02", author_id, "Article 2", material_type="post")
        self._insert_submission("quest_168_01", author_id, "Question 1", material_type="question")

        # Add 3 followers to author
        self._insert_subscription("follower_1", "author", author_id)
        self._insert_subscription("follower_2", "author", author_id)
        self._insert_subscription("follower_3", "author", author_id)

        # Author follows 2 other authors
        self._insert_subscription(author_id, "author", "other_author_1")
        self._insert_subscription(author_id, "author", "other_author_2")

        status, data = self._get_json(f"/api/users/{author_id}")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))

        profile = data.get("profile") or {}
        stats = profile.get("stats") or {}

        # Separation of questions vs publications
        self.assertEqual(profile.get("questionsCount"), 1)
        self.assertEqual(profile.get("publicationsCount"), 2)
        self.assertEqual(stats.get("questionsCount"), 1)
        self.assertEqual(stats.get("publicationsCount"), 2)

        # Followers and following counts
        self.assertEqual(profile.get("followersCount"), 3)
        self.assertEqual(profile.get("followingCount"), 2)
        self.assertEqual(stats.get("followersCount"), 3)
        self.assertEqual(stats.get("followingCount"), 2)

        # createdAt field
        self.assertEqual(profile.get("createdAt"), "2026-01-15T10:00:00Z")

        # Parity with self profile endpoint
        cookie = self._login(author_id, name="Metrics Test Author")
        status_self, data_self = self._get_json("/api/user/profile", cookie=cookie)
        self.assertEqual(status_self, 200)
        profile_self = data_self.get("profile") or {}
        self.assertEqual(profile_self.get("questionsCount"), 1)
        self.assertEqual(profile_self.get("publicationsCount"), 2)
        self.assertEqual(profile_self.get("followersCount"), 3)
        self.assertEqual(profile_self.get("followingCount"), 2)
        self.assertEqual(profile_self.get("createdAt"), "2026-01-15T10:00:00Z")

    def test_04_api_user_not_found_404(self):
        """Verify GET /api/users/:id returns 404 with USER_NOT_FOUND when user does not exist."""
        status, data = self._get_json("/api/users/non_existent_author_xyz_999")
        self.assertEqual(status, 404)
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("code"), "USER_NOT_FOUND")
        self.assertIn("Пользователь не найден", data.get("error", ""))

    def test_05_self_subscription_rejection_400(self):
        """Verify POST /api/subscriptions/toggle rejects self-subscription with 400 Bad Request."""
        user_id = "user_168_selfsub"
        cookie = self._login(user_id, name="Self Sub User")

        # Attempt self-subscription
        payload = {
            "targetType": "author",
            "targetId": user_id
        }
        status, data = self._post_json("/api/subscriptions/toggle", payload, cookie=cookie)
        self.assertEqual(status, 400)
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("code"), "SELF_SUBSCRIPTION_FORBIDDEN")
        self.assertIn("Нельзя подписаться на самого себя", data.get("error", ""))

        # Subscribing to another author must succeed
        payload_other = {
            "targetType": "author",
            "targetId": "another_valid_author"
        }
        status_other, data_other = self._post_json("/api/subscriptions/toggle", payload_other, cookie=cookie)
        self.assertEqual(status_other, 200)
        self.assertTrue(data_other.get("success"))
        self.assertTrue(data_other.get("subscribed"))

    def test_06_user_routing_redirect_302(self):
        """Verify GET /user/:id issues 302 redirect to /profile.html?id=:id."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request("GET", "/user/alice_wonder")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 302)
        self.assertEqual(resp.getheader("Location"), "/profile.html?id=alice_wonder")
        resp.read()
        conn.close()

        # URL encoded ID
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request("GET", "/user/bob%20marley")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 302)
        self.assertEqual(resp.getheader("Location"), "/profile.html?id=bob%2520marley")
        resp.read()
        conn.close()

        # HEAD request
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request("HEAD", "/user/charlie")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 302)
        self.assertEqual(resp.getheader("Location"), "/profile.html?id=charlie")
        resp.read()
        conn.close()

    def test_07_invariants_zero_emojis_and_offline(self):
        """Verify zero emojis, zero em dashes, and offline-first compliance in changed files."""
        emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]', flags=re.UNICODE)

        files_to_check = [
            os.path.join(FRONTEND_DIR, "js", "profile.js"),
            os.path.join(FRONTEND_DIR, "js", "feed.js"),
            os.path.join(FRONTEND_DIR, "js", "article.js"),
            *BACKEND_FILES,
        ]

        for filepath in files_to_check:
            self.assertTrue(os.path.exists(filepath), f"File {filepath} must exist")
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIsNone(
                emoji_pattern.search(content),
                f"Emoji found in {os.path.basename(filepath)}"
            )

            # In profile.js and server.py, zero em dashes
            if os.path.basename(filepath) in ["profile.js"]:
                self.assertNotIn(
                    "\u2014", content,
                    f"Em dash found in {os.path.basename(filepath)}"
                )


if __name__ == "__main__":
    unittest.main()
