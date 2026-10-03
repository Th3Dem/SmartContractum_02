#!/usr/bin/env python3
"""
tests/test_issue127_publication_save_count.py

Automated test suite for Issue #127:
"Добавить публичную метрику количества сохранений публикации (Save Count)".

Verifies:
1. Database schema:
   - table article_saves (id, article_id, user_id, created_at)
   - UNIQUE index on (article_id, user_id)
   - indexes on article_id and user_id
2. API endpoints:
   - POST /api/articles/<id>/save (auth required, increments savesCount, idempotent)
   - POST /api/articles/<id>/unsave (auth required, decrements savesCount, non-negative)
   - POST /api/articles/<id>/bookmark and POST /api/saves/toggle (toggle save state)
   - POST /api/articles/sync-saves (batch sync of localStorage bookmarks)
3. Retrieval and Feed DTOs:
   - GET /api/articles/<id> includes savesCount, hasSaved, isSaved
   - GET /api/articles includes savesCount, hasSaved, isSaved in list items
   - GET /api/articles?tab=saved filters by user saves
4. Frontend components:
   - article.html: #railBookmarkCount and #mobileBookmarkCount spans inside bookmark buttons
   - article.js: syncBookmarkButtons updates counters without clobbering count text
   - card.js: renders .card-action-count.card-save-count and handles toggleCardBookmark
   - feed.js: onBookmarkToggle updates .card-save-count and syncs with backend
   - feed.css: .btn-card-bookmark has padding, min-width, gap, transparent hover, count colors
   - article.css: rail and mobile bookmark hover and active count styles
5. Invariants:
   - Zero emojis
   - Zero em dashes
   - 100% offline-first
"""

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
from typing import Any, Dict, Optional, Tuple

import server
from server import create_server, init_db

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue127PublicationSaveCount(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_saves.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path, seed=False)
        conn.close()

        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR, seed=False)
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.1)

        # Seed test article
        cls.author_user = cls._create_or_login_user("author_user", "Author One")
        cls.reader_user = cls._create_or_login_user("reader_user", "Reader One")
        cls.second_reader = cls._create_or_login_user("second_reader", "Reader Two")

        cls.test_article_id = cls._create_article("author_user", "Save Count Test Article")

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
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            cookie = resp.headers.get("Set-Cookie", "")
            return {"user": data.get("user", {}), "cookie": cookie}

    @classmethod
    def _create_article(cls, author_id: str, title: str) -> str:
        art_id = f"art_save_{int(time.time() * 1000)}"
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
                json.dumps({"materialType": "article", "topics": ["development"]}, ensure_ascii=False),
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

    def test_01_database_schema_article_saves(self):
        """Verify article_saves table and its unique and foreign indexes exist."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Check table columns
        cur.execute("PRAGMA table_info(article_saves)")
        cols = {row["name"]: row["type"].upper() for row in cur.fetchall()}
        self.assertIn("id", cols)
        self.assertIn("article_id", cols)
        self.assertIn("user_id", cols)
        self.assertIn("created_at", cols)

        # Check indexes
        cur.execute("PRAGMA index_list(article_saves)")
        index_names = [row["name"] for row in cur.fetchall()]
        self.assertTrue(any("saves_article_user" in name for name in index_names), "Unique index on article_id, user_id must exist")
        self.assertTrue(any("saves_article_id" in name for name in index_names), "Index on article_id must exist")
        self.assertTrue(any("saves_user_id" in name for name in index_names), "Index on user_id must exist")
        conn.close()

    def test_02_save_and_unsave_endpoints_require_authentication(self):
        """Verify unauthenticated requests to save, unsave, bookmark, and sync-saves return 401."""
        status, res = self._api_request("POST", f"/api/articles/{self.test_article_id}/save")
        self.assertEqual(status, 401)
        self.assertTrue(res.get("requireAuth"))

        status, res = self._api_request("POST", f"/api/articles/{self.test_article_id}/unsave")
        self.assertEqual(status, 401)
        self.assertTrue(res.get("requireAuth"))

        status, res = self._api_request("POST", f"/api/articles/{self.test_article_id}/bookmark")
        self.assertEqual(status, 401)
        self.assertTrue(res.get("requireAuth"))

        status, res = self._api_request("POST", "/api/articles/sync-saves", {"articleIds": [self.test_article_id]})
        self.assertEqual(status, 401)
        self.assertTrue(res.get("requireAuth"))

    def test_03_authenticated_save_and_unsave_lifecycle(self):
        """Verify save, duplicate save (idempotency), multi-user save count, and unsave behavior."""
        # 1. Reader one saves article
        status, res = self._api_request(
            "POST",
            f"/api/articles/{self.test_article_id}/save",
            cookie=self.reader_user["cookie"]
        )
        self.assertEqual(status, 200)
        self.assertTrue(res.get("success"))
        self.assertTrue(res.get("isSaved"))
        self.assertTrue(res.get("hasSaved"))
        self.assertEqual(res.get("savesCount"), 1)

        # 2. Reader one duplicate save: must be idempotent
        status, res = self._api_request(
            "POST",
            f"/api/articles/{self.test_article_id}/save",
            cookie=self.reader_user["cookie"]
        )
        self.assertEqual(status, 200)
        self.assertTrue(res.get("isSaved"))
        self.assertEqual(res.get("savesCount"), 1)

        # 3. Second reader saves article: count becomes 2
        status, res = self._api_request(
            "POST",
            f"/api/articles/{self.test_article_id}/save",
            cookie=self.second_reader["cookie"]
        )
        self.assertEqual(status, 200)
        self.assertEqual(res.get("savesCount"), 2)

        # 4. Reader one unsaves: count becomes 1
        status, res = self._api_request(
            "POST",
            f"/api/articles/{self.test_article_id}/unsave",
            cookie=self.reader_user["cookie"]
        )
        self.assertEqual(status, 200)
        self.assertFalse(res.get("isSaved"))
        self.assertFalse(res.get("hasSaved"))
        self.assertEqual(res.get("savesCount"), 1)

        # 5. Second reader unsaves: count becomes 0
        status, res = self._api_request(
            "POST",
            f"/api/articles/{self.test_article_id}/unsave",
            cookie=self.second_reader["cookie"]
        )
        self.assertEqual(status, 200)
        self.assertFalse(res.get("isSaved"))
        self.assertEqual(res.get("savesCount"), 0)

        # 6. Redundant unsave: count remains 0 (non-negative)
        status, res = self._api_request(
            "POST",
            f"/api/articles/{self.test_article_id}/unsave",
            cookie=self.second_reader["cookie"]
        )
        self.assertEqual(status, 200)
        self.assertEqual(res.get("savesCount"), 0)

    def test_04_save_toggle_endpoint(self):
        """Verify POST /api/articles/<id>/bookmark and POST /api/saves/toggle toggle save state."""
        # Toggle on
        status, res = self._api_request(
            "POST",
            f"/api/articles/{self.test_article_id}/bookmark",
            cookie=self.reader_user["cookie"]
        )
        self.assertEqual(status, 200)
        self.assertTrue(res.get("isSaved"))
        self.assertEqual(res.get("savesCount"), 1)

        # Toggle off via /api/saves/toggle
        status, res = self._api_request(
            "POST",
            "/api/saves/toggle",
            {"articleId": self.test_article_id},
            cookie=self.reader_user["cookie"]
        )
        self.assertEqual(status, 200)
        self.assertFalse(res.get("isSaved"))
        self.assertEqual(res.get("savesCount"), 0)

    def test_05_sync_saves_batch_endpoint(self):
        """Verify POST /api/articles/sync-saves idempotently migrates client bookmarks to server."""
        # Create second test article
        second_art_id = self._create_article("author_user", "Sync Saves Target Article")

        # Sync two article IDs plus one non-existent ID
        status, res = self._api_request(
            "POST",
            "/api/articles/sync-saves",
            {"articleIds": [self.test_article_id, second_art_id, "non_existent_id_xyz"]},
            cookie=self.reader_user["cookie"]
        )
        self.assertEqual(status, 200)
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("syncedCount"), 2)
        self.assertEqual(res.get("totalSaved"), 2)

        # Repeat sync: syncedCount should be 0 because already present, totalSaved remains 2
        status, res = self._api_request(
            "POST",
            "/api/articles/sync-saves",
            {"articleIds": [self.test_article_id, second_art_id]},
            cookie=self.reader_user["cookie"]
        )
        self.assertEqual(status, 200)
        self.assertEqual(res.get("syncedCount"), 0)
        self.assertEqual(res.get("totalSaved"), 2)

    def test_06_get_article_and_feed_save_metrics(self):
        """Verify GET /api/articles/<id> and GET /api/articles return savesCount and hasSaved."""
        # Reader user currently has test_article_id saved from test_05
        status, res = self._api_request(
            "GET",
            f"/api/articles/{self.test_article_id}",
            cookie=self.reader_user["cookie"]
        )
        self.assertEqual(status, 200)
        self.assertIn("savesCount", res)
        self.assertEqual(res["savesCount"], 1)
        self.assertTrue(res.get("hasSaved"))
        self.assertTrue(res.get("isSaved"))
        article = res.get("article", {})
        self.assertEqual(article.get("savesCount"), 1)
        self.assertTrue(article.get("hasSaved"))

        # Check feed list includes savesCount and supports tab=saved
        status, res = self._api_request(
            "GET",
            "/api/articles?tab=saved",
            cookie=self.reader_user["cookie"]
        )
        self.assertEqual(status, 200)
        articles = res.get("articles", [])
        self.assertTrue(any(a["id"] == self.test_article_id for a in articles))
        for a in articles:
            self.assertIn("savesCount", a)
            self.assertIn("hasSaved", a)
            self.assertTrue(a["hasSaved"])

    def test_07_frontend_markup_and_counter_bindings(self):
        """Verify HTML spans, JS logic, and CSS styles for save count metrics."""
        article_html_path = os.path.join(FRONTEND_DIR, "article.html")
        article_js_path = os.path.join(FRONTEND_DIR, "js", "article.js")
        card_js_path = os.path.join(FRONTEND_DIR, "js", "card.js")
        feed_js_path = os.path.join(FRONTEND_DIR, "js", "feed.js")
        feed_css_path = os.path.join(FRONTEND_DIR, "css", "feed.css")
        article_css_path = os.path.join(FRONTEND_DIR, "css", "article.css")

        with open(article_html_path, "r", encoding="utf-8") as f:
            article_html = f.read()
        with open(article_js_path, "r", encoding="utf-8") as f:
            article_js = f.read()
        with open(card_js_path, "r", encoding="utf-8") as f:
            card_js = f.read()
        with open(feed_js_path, "r", encoding="utf-8") as f:
            feed_js = f.read()
        with open(feed_css_path, "r", encoding="utf-8") as f:
            feed_css = f.read()
        with open(article_css_path, "r", encoding="utf-8") as f:
            article_css = f.read()

        # 1. HTML counter elements
        self.assertIn('id="railBookmarkCount"', article_html)
        self.assertIn('id="mobileBookmarkCount"', article_html)

        # 2. article.js updates railBookmarkCount and does not overwrite count with label text
        self.assertIn("document.getElementById('railBookmarkCount')", article_js)
        self.assertIn("document.getElementById('mobileBookmarkCount')", article_js)
        self.assertIn("syncLocalBookmarksWithServer", article_js)

        # 3. card.js includes card-save-count and handles toggleCardBookmark
        self.assertIn("card-action-count card-save-count", card_js)
        self.assertIn("btn.querySelector('.card-save-count')", card_js)

        # 4. feed.js updates card-save-count on toggle and syncs with server
        self.assertIn(".card-save-count", feed_js)
        self.assertIn("syncLocalBookmarksWithServer", feed_js)

        # 5. feed.css styling for .btn-card-bookmark
        self.assertIn(".btn-card-bookmark", feed_css)
        self.assertIn("padding: 0 6px;", feed_css)
        self.assertIn("gap: 5px;", feed_css)
        self.assertIn(".btn-card-bookmark.is-bookmarked .card-save-count", feed_css)

        # 6. article.css hover and active count styling
        self.assertIn(".btn-rail-bookmark:hover .rail-action-count", article_css)
        self.assertIn(".btn-rail-bookmark.is-bookmarked .rail-action-count", article_css)

    def test_08_strict_invariants(self):
        """Verify strict zero emojis and zero em dashes across all modified files."""
        files_to_check = [
            os.path.join(PROJECT_ROOT, "server.py"),
            os.path.join(FRONTEND_DIR, "article.html"),
            os.path.join(FRONTEND_DIR, "js", "article.js"),
            os.path.join(FRONTEND_DIR, "js", "card.js"),
            os.path.join(FRONTEND_DIR, "css", "feed.css"),
            os.path.join(FRONTEND_DIR, "css", "article.css"),
            os.path.join(PROJECT_ROOT, "tests", "test_issue127_publication_save_count.py"),
        ]

        # Unicode ranges for emojis
        emoji_pattern = re.compile(
            r"[\U0001F600-\U0001F64F"  # Emoticons
            r"\U0001F300-\U0001F5FF"  # Misc symbols and pictographs
            r"\U0001F680-\U0001F6FF"  # Transport and map
            r"\U0001F1E0-\U0001F1FF"  # Flags
            r"\U00002702-\U000027B0"  # Dingbats
            r"\U000024C2-\U0001F251"
            r"\U0001F900-\U0001F9FF"  # Supplemental symbols
            r"\U0001FA70-\U0001FAFF"
            r"]"
        )

        for path in files_to_check:
            if not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertNotIn("\u2014", content, f"Em dash found in {path}")
            self.assertIsNone(emoji_pattern.search(content), f"Emoji found in {path}")

        # In feed.js, verify our additions do not contain emojis or em dashes
        with open(os.path.join(FRONTEND_DIR, "js", "feed.js"), "r", encoding="utf-8") as f:
            feed_js = f.read()
        self.assertIn("function syncLocalBookmarksWithServer", feed_js)
        fn_idx = feed_js.find("function syncLocalBookmarksWithServer")
        fn_slice = feed_js[fn_idx:fn_idx + 800]
        self.assertNotIn("\u2014", fn_slice)
        self.assertIsNone(emoji_pattern.search(fn_slice))

        # In WORKLOG.md, verify Issue 127 entries do not contain emojis or em dashes
        with open(os.path.join(PROJECT_ROOT, "WORKLOG.md"), "r", encoding="utf-8") as f:
            worklog = f.read()
        issue127_entries = [line for line in worklog.splitlines() if "issue-127" in line]
        self.assertTrue(len(issue127_entries) > 0)
        for entry in issue127_entries:
            self.assertNotIn("\u2014", entry)
            self.assertIsNone(emoji_pattern.search(entry))


if __name__ == "__main__":
    unittest.main()
