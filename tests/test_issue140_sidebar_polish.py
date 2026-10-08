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
from typing import Any, Dict

from tests.fixtures import seed_data
import server
from server import create_server, init_db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue140SidebarPolish(unittest.TestCase):
    """
    Targeted tests for Issue #140:
    - Compact #widgetCommunityCta with reduced vertical paddings and margins
    - Emerald pearl-green button style on #btnWidgetWritePub matching Editor .btn-next-to-pub
    - Min(realCount, 3) unanswered questions with metadata showing date only (no technical topic slug)
    - Thin border-bottom dividers between unanswered questions
    - Link 'linkAllUnanswered' triggers switchTab('questions') with questionStatus='unanswered'
    - Seed data ensures at least 3 unanswered questions (0 answers)
    """

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue140.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path, seed=True)
        conn.close()

        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR, seed=False)
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.1)

        css_path = os.path.join(FRONTEND_DIR, "css", "feed.css")
        with open(css_path, "r", encoding="utf-8") as f:
            cls.feed_css = f.read()

        js_path = os.path.join(FRONTEND_DIR, "js", "feed.js")
        with open(js_path, "r", encoding="utf-8") as f:
            cls.feed_js = f.read()

        html_path = os.path.join(FRONTEND_DIR, "feed.html")
        with open(html_path, "r", encoding="utf-8") as f:
            cls.feed_html = f.read()

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "httpd"):
            cls.httpd.shutdown()
        if hasattr(cls, "temp_dir") and os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def _api_request(self, method: str, path: str, data: Any = None, cookie: str = "") -> Any:
        url = f"{self.base_url}{path}"
        body = json.dumps(data).encode("utf-8") if data is not None else None
        headers = {"Content-Type": "application/json"}
        if cookie:
            headers["Cookie"] = cookie
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}

    def test_01_widget_community_cta_compact_styling(self):
        """Verify #widgetCommunityCta has compact vertical padding and #btnWidgetWritePub has emerald styling."""
        self.assertIn("#widgetCommunityCta", self.feed_css)
        self.assertIn("padding: 12px 14px", self.feed_css)
        self.assertIn("#widgetCommunityCta .widget-header", self.feed_css)
        self.assertIn("#widgetCommunityCta .widget-body", self.feed_css)

        # Emerald gradient on #btnWidgetWritePub
        self.assertIn("#btnWidgetWritePub", self.feed_css)
        self.assertIn("linear-gradient(135deg, #10b981 0%, #059669 100%)", self.feed_css)
        self.assertIn("rgba(52, 211, 153", self.feed_css)
        self.assertIn("rgba(16, 185, 129", self.feed_css)

    def test_02_unanswered_items_dividers_and_styling(self):
        """Verify .unanswered-item has thin border-bottom dividers and .widget-unanswered-list has gap: 0."""
        self.assertIn(".widget-unanswered-list", self.feed_css)
        self.assertIn("gap: 0;", self.feed_css)
        self.assertIn(".unanswered-item", self.feed_css)
        self.assertIn("border-bottom: 1px solid var(--border-color);", self.feed_css)
        self.assertIn(".unanswered-item:last-child", self.feed_css)
        self.assertIn("border-bottom: none;", self.feed_css)

    def test_03_unanswered_questions_js_rendering(self):
        """Verify loadUnansweredQuestions outputs only date (no topic slug) and wires linkAllUnanswered."""
        self.assertIn("loadUnansweredQuestions", self.feed_js)
        self.assertIn("unansweredQuestionsList", self.feed_js)

        # Meta should contain only date without topic title or slug
        self.assertIn("unanswered-item-meta", self.feed_js)

        # Check that topicTitle / topic is omitted from unanswered item meta in loadUnansweredQuestions
        func_start = self.feed_js.find("function loadUnansweredQuestions()")
        self.assertGreater(func_start, 0)
        func_body = self.feed_js[func_start:func_start + 1800]
        self.assertNotIn("q.topic", func_body)
        self.assertNotIn("topicTitle", func_body)
        self.assertIn("dateStr", func_body)

        # Check all unanswered link wires switchTab('questions') with questionStatus='unanswered'
        self.assertIn("linkAllUnanswered", func_body)
        self.assertIn("state.questionStatus = 'unanswered'", func_body)
        self.assertIn("switchTab('questions')", func_body)

    def test_04_seed_data_contains_at_least_three_unanswered_questions(self):
        """Verify seed data contains at least 3 approved questions with 0 answers."""
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT ms.id, ms.title,
                       (SELECT COUNT(*) FROM article_comments ac WHERE ac.article_id = ms.id AND ac.status = 'published' AND ac.comment_type = 'answer') AS ans_cnt
                FROM moderation_submissions ms
                WHERE ms.status = 'approved'
                  AND (
                    json_extract(ms.publication_settings, '$.materialType') = 'question'
                    OR json_extract(ms.publication_settings, '$.type') = 'question'
                  )
                  AND ans_cnt = 0
                ORDER BY ms.created_at DESC
            """)
            rows = cur.fetchall()
            self.assertGreaterEqual(
                len(rows),
                3,
                f"Expected at least 3 unanswered questions in seed data, found {len(rows)}"
            )
            unanswered_ids = [r[0] for r in rows]
            self.assertIn("art-29", unanswered_ids)
            self.assertIn("art-31", unanswered_ids)
            self.assertIn("art-32", unanswered_ids)
        finally:
            conn.close()

    def test_05_unanswered_api_returns_three_questions_on_fresh_seed(self):
        """Verify GET /api/questions/unanswered returns 3 items with date, materialType=question, and answersCount=0."""
        status, data = self._api_request("GET", "/api/questions/unanswered")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        questions = data.get("questions", [])
        self.assertEqual(len(questions), 3, "Endpoint must return 3 questions when at least 3 exist")

        for q in questions:
            self.assertEqual(q.get("materialType"), "question")
            self.assertEqual(q.get("answersCount"), 0)
            self.assertTrue(bool(q.get("title")))
            self.assertTrue(bool(q.get("date")), "Russian formatted date must be present")
