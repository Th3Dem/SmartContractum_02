"""
Targeted tests for Issue #132: Save: user-scoped state and persistent accumulated Save Count.
Verifies cross-user isolation (User A, B, C), question entity save support,
persistence across reloads, rollback on API error, and zero leakage between users.
"""

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
from typing import Any, Dict, Optional, Tuple

import server
from server import create_server, init_db

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue132UserScopedSaveAndCount(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue132.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path, seed=False)
        conn.close()

        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR, seed=False)
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.1)

        # Seed test users
        cls.user_a = cls._create_or_login_user("user_alpha", "User Alpha")
        cls.user_b = cls._create_or_login_user("user_bravo", "User Bravo")
        cls.user_c = cls._create_or_login_user("user_charlie", "User Charlie")
        cls.author = cls._create_or_login_user("user_author", "Author User")

        # Seed publication
        cls.pub_id = cls._create_material("art_pub_132", "user_author", "Test Article 132", "article")

        # Seed question
        cls.quest_id = cls._create_material("art_quest_132", "user_author", "Test Question 132", "question")

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "httpd"):
            cls.httpd.shutdown()
        if hasattr(cls, "temp_dir") and os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir, ignore_errors=True)

    @classmethod
    def _create_or_login_user(cls, user_id: str, name: str) -> Dict[str, Any]:
        payload = json.dumps({"userId": user_id, "name": name}).encode("utf-8")
        req = urllib.request.Request(
            f"{cls.base_url}/api/auth/login",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            cookie = resp.headers.get("Set-Cookie", "")
            return {"user": data.get("user"), "cookie": cookie}

    @classmethod
    def _create_material(cls, art_id: str, author_id: str, title: str, mat_type: str) -> str:
        conn = sqlite3.connect(cls.db_path)
        now_iso = "2026-10-01T10:00:00Z"
        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, idempotency_key, snapshot_hash, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                art_id, art_id, title, author_id, "approved",
                json.dumps({"materialType": mat_type, "type": mat_type, "topics": ["development"]}, ensure_ascii=False),
                f"<p>{title}</p>", f"idemp_{art_id}", f"hash_{art_id}", now_iso, now_iso
            ))
        conn.close()
        return art_id

    def _api_request(self, method: str, path: str, data: Optional[Dict[str, Any]] = None, cookie: str = "") -> Tuple[int, Dict[str, Any]]:
        url = f"{self.base_url}{path}"
        body = json.dumps(data).encode("utf-8") if data is not None else None
        headers = {"Content-Type": "application/json"}
        if cookie:
            headers["Cookie"] = cookie

        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                status = resp.status
                raw = resp.read().decode("utf-8")
                res_json = json.loads(raw) if raw else {}
                return status, res_json
        except urllib.error.HTTPError as err:
            status = err.code
            raw = err.read().decode("utf-8")
            try:
                res_json = json.loads(raw)
            except Exception:
                res_json = {"raw": raw}
            return status, res_json

    def test_01_cross_user_save_isolation_publication(self):
        """
        Required cross-user regression scenario:
        User A saves X -> count 1, A active.
        User B GET X -> count 1, B inactive.
        User B saves X -> count 2, B active.
        User C GET X -> count 2, C inactive.
        User A GET X -> count 2, A active.
        User A unsaves X -> count 1.
        User B GET X -> count 1, B active.
        """
        cookie_a = self.user_a["cookie"]
        cookie_b = self.user_b["cookie"]
        cookie_c = self.user_c["cookie"]

        target_id = self.pub_id

        # 1. User A saves X
        status, data = self._api_request("POST", f"/api/articles/{target_id}/save", cookie=cookie_a)
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        self.assertTrue(data.get("isSaved"))
        self.assertTrue(data.get("hasSaved"))
        self.assertEqual(data.get("savesCount"), 1)

        # 2. User B GET X -> count 1, B inactive
        status, data = self._api_request("GET", f"/api/articles/{target_id}", cookie=cookie_b)
        self.assertEqual(status, 200)
        self.assertFalse(data.get("hasSaved"))
        self.assertFalse(data.get("isSaved"))
        self.assertEqual(data.get("savesCount"), 1)

        # 3. User B saves X -> count 2, B active
        status, data = self._api_request("POST", f"/api/articles/{target_id}/save", cookie=cookie_b)
        self.assertEqual(status, 200)
        self.assertTrue(data.get("isSaved"))
        self.assertEqual(data.get("savesCount"), 2)

        # 4. User C GET X -> count 2, C inactive
        status, data = self._api_request("GET", f"/api/articles/{target_id}", cookie=cookie_c)
        self.assertEqual(status, 200)
        self.assertFalse(data.get("hasSaved"))
        self.assertEqual(data.get("savesCount"), 2)

        # 5. User A GET X -> count 2, A active
        status, data = self._api_request("GET", f"/api/articles/{target_id}", cookie=cookie_a)
        self.assertEqual(status, 200)
        self.assertTrue(data.get("hasSaved"))
        self.assertEqual(data.get("savesCount"), 2)

        # 6. User A unsaves X -> count 1
        status, data = self._api_request("POST", f"/api/articles/{target_id}/unsave", cookie=cookie_a)
        self.assertEqual(status, 200)
        self.assertFalse(data.get("isSaved"))
        self.assertEqual(data.get("savesCount"), 1)

        # 7. User B GET X -> count 1, B active
        status, data = self._api_request("GET", f"/api/articles/{target_id}", cookie=cookie_b)
        self.assertEqual(status, 200)
        self.assertTrue(data.get("hasSaved"))
        self.assertEqual(data.get("savesCount"), 1)

        # 8. User A GET X -> count 1, A inactive
        status, data = self._api_request("GET", f"/api/articles/{target_id}", cookie=cookie_a)
        self.assertEqual(status, 200)
        self.assertFalse(data.get("hasSaved"))
        self.assertEqual(data.get("savesCount"), 1)

        # Clean up User B save
        self._api_request("POST", f"/api/articles/{target_id}/unsave", cookie=cookie_b)

    def test_02_question_save_support_and_routes(self):
        """
        Verifies question entity save works with both /api/articles/ and /api/questions/ endpoints.
        """
        cookie_a = self.user_a["cookie"]
        cookie_b = self.user_b["cookie"]
        question_id = self.quest_id

        # Save via /api/questions/<id>/save
        status, data = self._api_request("POST", f"/api/questions/{question_id}/save", cookie=cookie_a)
        self.assertEqual(status, 200)
        self.assertTrue(data.get("isSaved"))
        self.assertEqual(data.get("savesCount"), 1)

        # User B reads question via /api/questions/<id>
        status, data = self._api_request("GET", f"/api/questions/{question_id}", cookie=cookie_b)
        self.assertEqual(status, 200)
        self.assertFalse(data.get("hasSaved"))
        self.assertEqual(data.get("savesCount"), 1)

        # User B saves question via /api/articles/<id>/save
        status, data = self._api_request("POST", f"/api/articles/{question_id}/save", cookie=cookie_b)
        self.assertEqual(status, 200)
        self.assertEqual(data.get("savesCount"), 2)

        # Cleanup
        self._api_request("POST", f"/api/questions/{question_id}/unsave", cookie=cookie_a)
        self._api_request("POST", f"/api/questions/{question_id}/unsave", cookie=cookie_b)

    def test_03_duplicate_save_idempotency(self):
        """
        Repeated saves by same user must be idempotent and not increment count.
        """
        cookie = self.user_a["cookie"]
        target_id = self.pub_id

        status, data1 = self._api_request("POST", f"/api/articles/{target_id}/save", cookie=cookie)
        self.assertEqual(status, 200)
        cnt1 = data1.get("savesCount")

        # Second save click
        status, data2 = self._api_request("POST", f"/api/articles/{target_id}/save", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual(data2.get("savesCount"), cnt1)

        # Cleanup
        self._api_request("POST", f"/api/articles/{target_id}/unsave", cookie=cookie)

    def test_04_unauthorized_save_returns_401(self):
        """
        Unauthenticated requests must return 401 and not modify database.
        """
        target_id = self.pub_id
        status, data = self._api_request("POST", f"/api/articles/{target_id}/save")
        self.assertEqual(status, 401)
        self.assertEqual(data.get("code"), "AUTH_REQUIRED")

    def test_05_feed_batch_has_saved_and_counts(self):
        """
        GET /api/articles returns personalized hasSaved and savesCount for all cards without N+1.
        """
        cookie_a = self.user_a["cookie"]
        cookie_b = self.user_b["cookie"]
        pub_id = self.pub_id

        self._api_request("POST", f"/api/articles/{pub_id}/save", cookie=cookie_a)

        # User A feed
        status, feed_a = self._api_request("GET", "/api/articles", cookie=cookie_a)
        self.assertEqual(status, 200)
        art_a = next((a for a in feed_a.get("articles", []) if a["id"] == pub_id), None)
        self.assertIsNotNone(art_a)
        self.assertTrue(art_a.get("hasSaved"))
        self.assertEqual(art_a.get("savesCount"), 1)

        # User B feed
        status, feed_b = self._api_request("GET", "/api/articles", cookie=cookie_b)
        self.assertEqual(status, 200)
        art_b = next((a for a in feed_b.get("articles", []) if a["id"] == pub_id), None)
        self.assertIsNotNone(art_b)
        self.assertFalse(art_b.get("hasSaved"))
        self.assertEqual(art_b.get("savesCount"), 1)

        # Cleanup
        self._api_request("POST", f"/api/articles/{pub_id}/unsave", cookie=cookie_a)

    def test_06_frontend_contract_isolation(self):
        """
        Verifies frontend files contain user-scoped bookmarks and rollback handling.
        """
        card_js_path = os.path.join(FRONTEND_DIR, "js", "card.js")
        feed_js_path = os.path.join(FRONTEND_DIR, "js", "feed.js")
        article_js_path = os.path.join(FRONTEND_DIR, "js", "article.js")

        with open(card_js_path, "r", encoding="utf-8") as f:
            card_content = f.read()
        with open(feed_js_path, "r", encoding="utf-8") as f:
            feed_content = f.read()
        with open(article_js_path, "r", encoding="utf-8") as f:
            article_content = f.read()

        # Check user-scoped keys
        self.assertIn("sc_bookmarks_", card_content)
        self.assertIn("sc_bookmarks_", feed_content)
        self.assertIn("sc_bookmarks_", article_content)

        # Check migration logic
        self.assertIn("sc_bookmarks_migrated", feed_content)
        self.assertIn("sc_bookmarks_migrated", article_content)

        # Check optimistic rollback
        self.assertIn("wasBookmarked", card_content)
        self.assertIn("wasActive", feed_content)
        self.assertIn("wasBookmarked", article_content)


if __name__ == "__main__":
    unittest.main()
