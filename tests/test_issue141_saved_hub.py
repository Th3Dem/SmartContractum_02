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

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue141SavedHub(unittest.TestCase):
    """
    Targeted tests for Issue #141:
    - Unified Saved Hub with type switcher (All, Publications, Questions, Comments)
    - Server persistence for comment saves (comment_saves table)
    - Legacy bookmarks migration via /api/comments/sync-saves
    - Aggregated saved counts via /api/saved/counts
    - User-scoped isolation (no cross-user leakage)
    - HTML and CSS layout verification
    """

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue141.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path, seed=False)
        conn.close()

        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR, seed=False)
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.1)

        # Login test users to create authenticated sessions
        cls.user_a = cls._create_or_login_user("user_saved_a", "User Alpha")
        cls.user_b = cls._create_or_login_user("user_saved_b", "User Beta")

        # Seed test article, question, and comment
        conn = sqlite3.connect(cls.db_path)
        with conn:
            cur = conn.cursor()

            # 1. Publication
            cur.execute("""
                INSERT OR REPLACE INTO moderation_submissions (
                    id, draft_id, title, author_id,
                    status, publication_settings, article_html, snapshot_hash, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'approved', ?, ?, 'hash1', '2026-02-01T10:00:00Z', '2026-02-01T10:00:00Z')
            """, (
                "art-hub-pub-01", "draft-pub-01", "Статья по архитектуре ПКСК",
                cls.user_a["id"],
                json.dumps({
                    "materialType": "article",
                    "format": "tutorial",
                    "complexity": "medium",
                    "topics": ["pksc-architecture"],
                    "description": "Описание статьи",
                    "author": {"id": cls.user_a["id"], "name": cls.user_a["name"]}
                }),
                "<p>Текст статьи</p>"
            ))

            # 2. Question
            cur.execute("""
                INSERT OR REPLACE INTO moderation_submissions (
                    id, draft_id, title, author_id,
                    status, publication_settings, article_html, snapshot_hash, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'approved', ?, ?, 'hash2', '2026-02-02T10:00:00Z', '2026-02-02T10:00:00Z')
            """, (
                "art-hub-quest-01", "draft-quest-01", "Вопрос по валидации подписей",
                cls.user_a["id"],
                json.dumps({
                    "materialType": "question",
                    "format": "question",
                    "complexity": "easy",
                    "topics": ["smart-contracts-development"],
                    "description": "Описание вопроса",
                    "author": {"id": cls.user_a["id"], "name": cls.user_a["name"]}
                }),
                "<p>Текст вопроса</p>"
            ))

            # 3. Comment
            cur.execute("""
                INSERT OR REPLACE INTO article_comments (
                    id, article_id, user_id, author_name, author_avatar, content, status, comment_type, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'published', 'comment', '2026-02-03T10:00:00Z')
            """, (
                "comm-hub-01", "art-hub-pub-01", cls.user_b["id"], "User Beta", None,
                "Важное архитектурное замечание по HSM модулю",
            ))
        conn.close()

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
            return {"user": data.get("user"), "cookie": cookie, "id": user_id, "name": name}

    def _request(self, method, path, body=None, user=None):
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json"}
        if user and "cookie" in user:
            headers["Cookie"] = user["cookie"]

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                status = resp.status
                raw = resp.read().decode("utf-8")
                return status, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as err:
            raw = err.read().decode("utf-8")
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = {"raw": raw}
            return err.code, parsed

    def test_01_saved_counts_guest_and_auth(self):
        """Guest gets zeroes, auth user gets accurate counts."""
        status, res = self._request("GET", "/api/saved/counts")
        self.assertEqual(status, 200)
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("total"), 0)
        self.assertEqual(res.get("publications"), 0)
        self.assertEqual(res.get("questions"), 0)
        self.assertEqual(res.get("comments"), 0)

        # User A saves publication
        status_save, res_save = self._request("POST", "/api/articles/art-hub-pub-01/save", user=self.user_a)
        self.assertEqual(status_save, 200)
        self.assertTrue(res_save.get("isSaved"))

        status, res = self._request("GET", "/api/saved/counts", user=self.user_a)
        self.assertEqual(status, 200)
        self.assertEqual(res.get("publications"), 1)
        self.assertEqual(res.get("questions"), 0)
        self.assertEqual(res.get("comments"), 0)
        self.assertEqual(res.get("total"), 1)

    def test_02_comment_save_and_unsave_endpoints(self):
        """Comment saving, unsaving, and auth enforcement."""
        # Unauthenticated save fails
        status, res = self._request("POST", "/api/comments/comm-hub-01/save")
        self.assertEqual(status, 401)
        self.assertTrue(res.get("requireAuth"))

        # User A saves comment
        status, res = self._request("POST", "/api/comments/comm-hub-01/save", body={"action": "save"}, user=self.user_a)
        self.assertEqual(status, 200)
        self.assertTrue(res.get("success"))
        self.assertTrue(res.get("isSaved"))
        self.assertEqual(res.get("savesCount"), 1)

        # Check comment in saved comments
        status, res = self._request("GET", "/api/comments/saved", user=self.user_a)
        self.assertEqual(status, 200)
        self.assertEqual(res.get("total"), 1)
        item = res["items"][0]
        self.assertEqual(item["id"], "comm-hub-01")
        self.assertEqual(item["articleTitle"], "Статья по архитектуре ПКСК")
        self.assertIn("#comment-comm-hub-01", item["permalink"])

        # Check saved counts updated
        status, res = self._request("GET", "/api/saved/counts", user=self.user_a)
        self.assertEqual(status, 200)
        self.assertEqual(res.get("comments"), 1)

    def test_03_legacy_comment_sync_saves(self):
        """Syncs legacy client-side bookmark IDs into server database."""
        status, res = self._request("POST", "/api/comments/sync-saves", body={"commentIds": ["comm-hub-01"]}, user=self.user_b)
        self.assertEqual(status, 200)
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("totalSaved"), 1)

        # User B now has 1 saved comment
        status, res = self._request("GET", "/api/saved/counts", user=self.user_b)
        self.assertEqual(status, 200)
        self.assertEqual(res.get("comments"), 1)

    def test_04_unified_api_saved_endpoint(self):
        """GET /api/saved returns all types, filtered by type or search."""
        # Save question for User A
        self._request("POST", "/api/articles/art-hub-quest-01/save", user=self.user_a)

        # GET /api/saved?type=all
        status, res = self._request("GET", "/api/saved?type=all", user=self.user_a)
        self.assertEqual(status, 200)
        self.assertTrue(res.get("success"))
        items = res.get("items", [])
        types_in_items = {it.get("entityType") for it in items}
        self.assertIn("publication", types_in_items)
        self.assertIn("question", types_in_items)
        self.assertIn("comment", types_in_items)
        self.assertEqual(res["counts"]["total"], 3)
        self.assertEqual(res["counts"]["publications"], 1)
        self.assertEqual(res["counts"]["questions"], 1)
        self.assertEqual(res["counts"]["comments"], 1)

        # GET /api/saved?type=comments
        status, res = self._request("GET", "/api/saved?type=comments", user=self.user_a)
        self.assertEqual(status, 200)
        self.assertEqual(len(res["items"]), 1)
        self.assertEqual(res["items"][0]["entityType"], "comment")

        # GET /api/saved?type=questions
        status, res = self._request("GET", "/api/saved?type=questions", user=self.user_a)
        self.assertEqual(status, 200)
        self.assertEqual(len(res["items"]), 1)
        self.assertEqual(res["items"][0]["entityType"], "question")

        # Search filter
        status, res = self._request("GET", "/api/saved?type=all&search=HSM", user=self.user_a)
        self.assertEqual(status, 200)
        self.assertEqual(len(res["items"]), 1)
        self.assertEqual(res["items"][0]["id"], "comm-hub-01")

    def test_05_saved_hub_html_and_css_structure(self):
        """Validates HTML elements and CSS classes for Saved Hub."""
        feed_html_path = os.path.join(FRONTEND_DIR, "feed.html")
        feed_css_path = os.path.join(FRONTEND_DIR, "css", "feed.css")
        feed_js_path = os.path.join(FRONTEND_DIR, "js", "feed.js")

        with open(feed_html_path, "r", encoding="utf-8") as f:
            html = f.read()
        with open(feed_css_path, "r", encoding="utf-8") as f:
            css = f.read()
        with open(feed_js_path, "r", encoding="utf-8") as f:
            js = f.read()

        # HTML pills
        self.assertIn('id="feedSavedHubPills"', html)
        self.assertIn('data-saved-type="all"', html)
        self.assertIn('data-saved-type="publications"', html)
        self.assertIn('data-saved-type="questions"', html)
        self.assertIn('data-saved-type="comments"', html)
        self.assertIn('id="savedCountAll"', html)
        self.assertIn('id="savedCountPublications"', html)
        self.assertIn('id="savedCountQuestions"', html)
        self.assertIn('id="savedCountComments"', html)

        # CSS classes
        self.assertIn(".feed-saved-hub-pills", css)
        self.assertIn(".feed-saved-pill", css)
        self.assertIn(".saved-comment-card", css)
        self.assertIn(".saved-comment-quote", css)
        self.assertIn(".btn-saved-comment-unsave", css)

        # JS Saved Hub logic
        self.assertIn("savedType", js)
        self.assertIn("/api/saved", js)
        self.assertIn("renderSavedCommentCard", js)
        self.assertIn("runLegacyCommentBookmarksMigration", js)


if __name__ == "__main__":
    unittest.main()
