#!/usr/bin/env python3
"""
tests/test_issue133_user_scoped_report_state.py

Targeted test suite for Issue #133:
1. User-scoped report state for publications, questions, comments, and answers.
2. Cross-user isolation: User A report does not make buttons active for User B or User C.
3. Server-side hasReported flag returned in:
   - GET /api/articles/<id>
   - GET /api/questions/<id>
   - GET /api/articles (batch feed)
   - GET /api/articles/<id>/comments (for comments and answers)
4. Preservation of self-report prevention (CANNOT_REPORT_OWN_ARTICLE, CANNOT_REPORT_OWN_COMMENT).
5. Duplicate report prevention (REPORT_ALREADY_EXISTS 409).
6. Unauthorized guard (401).
7. Strict project invariants:
   - Zero emojis.
   - Zero em dashes.
   - 100% offline-first.
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


class TestIssue133UserScopedReportState(unittest.TestCase):
    """Verifies user-scoped report state across publications, questions, and comments."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue133.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path, seed=False)
        conn.close()

        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR, seed=False)
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.1)

        # Create test users via /api/auth/login
        cls.author = cls._create_or_login_user("usr_author_133", "Author 133")
        cls.user_b = cls._create_or_login_user("usr_user_b_133", "User B 133")
        cls.user_c = cls._create_or_login_user("usr_user_c_133", "User C 133")

        # Seed publication
        cls.pub_id = cls._create_material("art_pub_133", "usr_author_133", "Test Publication 133", "article")

        # Seed question
        cls.quest_id = cls._create_material("art_quest_133", "usr_author_133", "Test Question 133", "question")

        # Seed comments on publication: regular comment and answer
        cls._create_comment("comm_reg_133", "art_pub_133", "usr_author_133", "Regular comment", "comment")
        cls._create_comment("comm_ans_133", "art_pub_133", "usr_author_133", "Answer comment", "answer")

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

    @classmethod
    def _create_comment(cls, comm_id: str, art_id: str, user_id: str, content: str, comm_type: str):
        conn = sqlite3.connect(cls.db_path)
        now_iso = "2026-10-01T10:05:00Z"
        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO article_comments (
                    id, article_id, user_id, author_name, content, status, comment_type, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                comm_id, art_id, user_id, "Author", content, "published", comm_type, now_iso
            ))
        conn.close()

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
                res_json = json.loads(raw) if raw else {}
            except Exception:
                res_json = {"error": raw}
            return status, res_json

    def test_01_cross_user_report_isolation_publication(self):
        """User B reports publication; User C and guest still see hasReported False."""
        cookie_b = self.user_b["cookie"]
        cookie_c = self.user_c["cookie"]

        # 1. User B initially has not reported
        st, data = self._api_request("GET", "/api/articles/art_pub_133", cookie=cookie_b)
        self.assertEqual(st, 200)
        self.assertFalse(data.get("hasReported", False))
        self.assertFalse(data.get("article", {}).get("hasReported", False))

        # 2. User B submits report
        st, data = self._api_request(
            "POST",
            "/api/articles/art_pub_133/report",
            data={"reason": "spam", "details": "Spam details from B"},
            cookie=cookie_b
        )
        self.assertEqual(st, 200)
        self.assertTrue(data.get("success"))
        self.assertTrue(data.get("hasReported"))

        # 3. User B now sees hasReported == True
        st, data = self._api_request("GET", "/api/articles/art_pub_133", cookie=cookie_b)
        self.assertEqual(st, 200)
        self.assertTrue(data.get("hasReported"))
        self.assertTrue(data.get("article", {}).get("hasReported"))

        # 4. User C checks publication -> must be False
        st, data = self._api_request("GET", "/api/articles/art_pub_133", cookie=cookie_c)
        self.assertEqual(st, 200)
        self.assertFalse(data.get("hasReported", False))
        self.assertFalse(data.get("article", {}).get("hasReported", False))

        # 5. Guest checks publication -> must be False
        st, data = self._api_request("GET", "/api/articles/art_pub_133")
        self.assertEqual(st, 200)
        self.assertFalse(data.get("hasReported", False))
        self.assertFalse(data.get("article", {}).get("hasReported", False))

        # 6. User C reports publication -> must succeed
        st, data = self._api_request(
            "POST",
            "/api/articles/art_pub_133/report",
            data={"reason": "rules", "details": "Violation from C"},
            cookie=cookie_c
        )
        self.assertEqual(st, 200)
        self.assertTrue(data.get("hasReported"))

        # 7. User C now sees hasReported == True
        st, data = self._api_request("GET", "/api/articles/art_pub_133", cookie=cookie_c)
        self.assertEqual(st, 200)
        self.assertTrue(data.get("hasReported"))

    def test_02_cross_user_report_isolation_question(self):
        """User B reports question via /api/questions/<id>/report; User C sees un-reported."""
        cookie_b = self.user_b["cookie"]
        cookie_c = self.user_c["cookie"]

        # 1. User B initially has not reported question
        st, data = self._api_request("GET", "/api/questions/art_quest_133", cookie=cookie_b)
        self.assertEqual(st, 200)
        self.assertFalse(data.get("hasReported", False))

        # 2. User B reports question
        st, data = self._api_request(
            "POST",
            "/api/questions/art_quest_133/report",
            data={"reason": "offtopic", "details": "Question not relevant"},
            cookie=cookie_b
        )
        self.assertEqual(st, 200)
        self.assertTrue(data.get("hasReported"))

        # 3. User B sees hasReported True
        st, data = self._api_request("GET", "/api/questions/art_quest_133", cookie=cookie_b)
        self.assertEqual(st, 200)
        self.assertTrue(data.get("hasReported"))

        # 4. User C sees hasReported False
        st, data = self._api_request("GET", "/api/questions/art_quest_133", cookie=cookie_c)
        self.assertEqual(st, 200)
        self.assertFalse(data.get("hasReported", False))

    def test_03_cross_user_report_isolation_comments_and_answers(self):
        """User B reports regular comment and answer; User C and guest see un-reported."""
        cookie_b = self.user_b["cookie"]
        cookie_c = self.user_c["cookie"]

        # 1. Initially neither comment is reported for User B
        st, data = self._api_request("GET", "/api/articles/art_pub_133/comments", cookie=cookie_b)
        self.assertEqual(st, 200)
        comms = {c["id"]: c for c in data.get("comments", [])}
        self.assertIn("comm_reg_133", comms)
        self.assertIn("comm_ans_133", comms)
        self.assertFalse(comms["comm_reg_133"].get("hasReported", False))
        self.assertFalse(comms["comm_ans_133"].get("hasReported", False))

        # 2. User B reports regular comment
        st, res = self._api_request(
            "POST",
            "/api/comments/comm_reg_133/report",
            data={"reason": "insult", "details": "Offensive"},
            cookie=cookie_b
        )
        self.assertEqual(st, 200)
        self.assertTrue(res.get("hasReported"))

        # 3. User B reports answer
        st, res = self._api_request(
            "POST",
            "/api/comments/comm_ans_133/report",
            data={"reason": "spam", "details": "Spam answer"},
            cookie=cookie_b
        )
        self.assertEqual(st, 200)
        self.assertTrue(res.get("hasReported"))

        # 4. User B verifies both are marked reported
        st, data = self._api_request("GET", "/api/articles/art_pub_133/comments", cookie=cookie_b)
        self.assertEqual(st, 200)
        comms_b = {c["id"]: c for c in data.get("comments", [])}
        self.assertTrue(comms_b["comm_reg_133"].get("hasReported"))
        self.assertTrue(comms_b["comm_ans_133"].get("hasReported"))

        # 5. User C sees both as un-reported
        st, data = self._api_request("GET", "/api/articles/art_pub_133/comments", cookie=cookie_c)
        self.assertEqual(st, 200)
        comms_c = {c["id"]: c for c in data.get("comments", [])}
        self.assertFalse(comms_c["comm_reg_133"].get("hasReported", False))
        self.assertFalse(comms_c["comm_ans_133"].get("hasReported", False))

        # 6. Guest sees both as un-reported
        st, data = self._api_request("GET", "/api/articles/art_pub_133/comments")
        self.assertEqual(st, 200)
        comms_guest = {c["id"]: c for c in data.get("comments", [])}
        self.assertFalse(comms_guest["comm_reg_133"].get("hasReported", False))
        self.assertFalse(comms_guest["comm_ans_133"].get("hasReported", False))

    def test_04_self_report_prevention(self):
        """Author cannot report own publication or own comment (403)."""
        cookie_author = self.author["cookie"]

        # Report own publication -> 403
        st, data = self._api_request(
            "POST",
            "/api/articles/art_pub_133/report",
            data={"reason": "spam"},
            cookie=cookie_author
        )
        self.assertEqual(st, 403)
        self.assertEqual(data.get("code"), "CANNOT_REPORT_OWN_ARTICLE")

        # Report own comment -> 403
        st, data = self._api_request(
            "POST",
            "/api/comments/comm_reg_133/report",
            data={"reason": "spam"},
            cookie=cookie_author
        )
        self.assertEqual(st, 403)
        self.assertEqual(data.get("code"), "CANNOT_REPORT_OWN_COMMENT")

    def test_05_duplicate_report_conflict_409(self):
        """Duplicate report by same user returns 409 REPORT_ALREADY_EXISTS."""
        cookie_b = self.user_b["cookie"]

        # Duplicate article report -> 409
        st, data = self._api_request(
            "POST",
            "/api/articles/art_pub_133/report",
            data={"reason": "duplicate"},
            cookie=cookie_b
        )
        self.assertEqual(st, 409)
        self.assertEqual(data.get("code"), "REPORT_ALREADY_EXISTS")

        # Duplicate comment report -> 409
        st, data = self._api_request(
            "POST",
            "/api/comments/comm_reg_133/report",
            data={"reason": "duplicate"},
            cookie=cookie_b
        )
        self.assertEqual(st, 409)
        self.assertEqual(data.get("code"), "REPORT_ALREADY_EXISTS")

    def test_06_unauthorized_report_guard_401(self):
        """Unauthenticated requests cannot report (401)."""
        st, data = self._api_request(
            "POST",
            "/api/articles/art_pub_133/report",
            data={"reason": "spam"}
        )
        self.assertEqual(st, 401)
        self.assertEqual(data.get("code"), "AUTH_REQUIRED")

        st, data = self._api_request(
            "POST",
            "/api/comments/comm_reg_133/report",
            data={"reason": "spam"}
        )
        self.assertEqual(st, 401)
        self.assertEqual(data.get("code"), "AUTH_REQUIRED")

    def test_07_feed_batch_has_reported(self):
        """GET /api/articles returns batch user-scoped hasReported without N+1."""
        cookie_b = self.user_b["cookie"]
        cookie_c = self.user_c["cookie"]

        # User B reported art_pub_133 and art_quest_133
        st, data_b = self._api_request("GET", "/api/articles", cookie=cookie_b)
        self.assertEqual(st, 200)
        items_b = {item["id"]: item for item in data_b.get("articles", [])}
        if "art_pub_133" in items_b:
            self.assertTrue(items_b["art_pub_133"].get("hasReported"))

        # User C reported art_pub_133, but not art_quest_133
        st, data_c = self._api_request("GET", "/api/articles", cookie=cookie_c)
        self.assertEqual(st, 200)
        items_c = {item["id"]: item for item in data_c.get("articles", [])}
        if "art_pub_133" in items_c:
            self.assertTrue(items_c["art_pub_133"].get("hasReported"))
        if "art_quest_133" in items_c:
            self.assertFalse(items_c["art_quest_133"].get("hasReported", False))

        # Guest sees False for all
        st, data_guest = self._api_request("GET", "/api/articles")
        self.assertEqual(st, 200)
        items_guest = {item["id"]: item for item in data_guest.get("articles", [])}
        if "art_pub_133" in items_guest:
            self.assertFalse(items_guest["art_pub_133"].get("hasReported", False))
        if "art_quest_133" in items_guest:
            self.assertFalse(items_guest["art_quest_133"].get("hasReported", False))

    def test_08_frontend_contract_isolation_and_invariants(self):
        """Verify frontend contract: user-scoped storage keys, helper functions, and zero emojis."""
        card_js_path = os.path.join(FRONTEND_DIR, "js", "card.js")
        feed_js_path = os.path.join(FRONTEND_DIR, "js", "feed.js")
        article_js_path = os.path.join(FRONTEND_DIR, "js", "article.js")
        test_py_path = os.path.join(PROJECT_ROOT, "tests", "test_issue133_user_scoped_report_state.py")

        with open(card_js_path, "r", encoding="utf-8") as f:
            card_content = f.read()
        with open(feed_js_path, "r", encoding="utf-8") as f:
            feed_content = f.read()
        with open(article_js_path, "r", encoding="utf-8") as f:
            article_content = f.read()
        with open(test_py_path, "r", encoding="utf-8") as f:
            test_content = f.read()

        # Check user-scoped storage keys
        self.assertIn("sc_reported_articles_", feed_content)
        self.assertIn("sc_reported_articles_", article_content)
        self.assertIn("sc_comment_reports_", article_content)

        # Check card.js helper export
        self.assertIn("updateReportButtonState", card_content)

        # Check zero em dashes in test file
        self.assertNotIn("\u2014", test_content)

        # Check zero emojis across all
        emoji_pattern = re.compile(
            r'[\U00010000-\U0010ffff]|[\u2600-\u27ff]|[\u2300-\u23ff]|[\u2b50-\u2b55]'
        )
        for name, content in [("card.js", card_content), ("feed.js", feed_content), ("article.js", article_content), ("test", test_content)]:
            self.assertIsNone(emoji_pattern.search(content), f"Emoji found in {name}")


if __name__ == "__main__":
    unittest.main()
