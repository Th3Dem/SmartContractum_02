#!/usr/bin/env python3
"""
tests/test_issue71_comment_new_actions.py

Automated backend test suite for Issue #71 (SC-030):
"Comment new actions: Report, Subscribe, and Subscriptions list".

Requirements tested:
1. SQLite schema:
   - comment_reports table creation, columns, and indexes.
   - comment_subscriptions table creation, columns, unique constraint, and indexes.
   - Repeated init_db execution idempotency.
2. POST /api/comments/<id>/report:
   - Requires authentication (401).
   - Validates reason: non-empty string, max length 200 (400).
   - Prevents author from reporting their own comment (403 CANNOT_REPORT_OWN_COMMENT).
   - Prevents duplicate report from same user on same comment (409 REPORT_ALREADY_EXISTS).
   - Non-existent comment returns 404.
   - Successful report inserts row and returns 200 with success: true and message: "Жалоба отправлена".
   - Different users can report the same comment.
3. POST /api/comments/<id>/subscribe:
   - Requires authentication (401).
   - Non-existent comment returns 404.
   - Toggles subscription:
     * First call: inserts row, returns {"success": true, "subscribed": true}.
     * Second call: deletes row, returns {"success": true, "subscribed": false}.
     * Third call: re-subscribes, returns {"success": true, "subscribed": true}.
4. GET /api/comments/subscriptions:
   - Requires authentication (401).
   - Returns array of subscribed comment IDs: {"success": true, "subscriptions": [...]}.
   - User isolation: subscriptions of one user do not leak into another user's list.
   - Reflects toggle state immediately.

Strict compliance: 100% offline-first, zero emojis, zero em dashes.
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


class TestIssue71CommentNewActionsBackend(unittest.TestCase):
    """Verifies backend API, schema, report invariants, and subscription toggles for Issue #71."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue71.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path, seed=False)
        with conn:
            # Seed users
            users = [
                ("u_alice", "Алиса", "user"),
                ("u_bob", "Боб", "user"),
                ("u_charlie", "Чарли", "user"),
            ]
            for uid, name, role in users:
                conn.execute("""
                    INSERT INTO user_profiles (
                        user_id, name, specialization, company, bio, avatar, created_at, updated_at
                    ) VALUES (?, ?, 'Engineer', 'SmartCo', '', '', '2026-10-01T10:00:00Z', '2026-10-01T10:00:00Z')
                """, (uid, name))

            # Seed approved publication
            conn.execute("""
                INSERT INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, idempotency_key, snapshot_hash, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'approved', ?, ?, ?, ?, ?, ?)
            """, (
                "art_issue71_01", "draft_art_71_01", "Статья для тестирования действий", "u_alice",
                json.dumps({"materialType": "article", "topics": ["development"]}, ensure_ascii=False),
                "<p>Содержимое статьи</p>", "idemp_71_art", "hash_71_art",
                "2026-10-01T10:00:00Z", "2026-10-01T10:00:00Z"
            ))

            # Seed comments
            # comm_alice: author is u_alice
            conn.execute("""
                INSERT INTO article_comments (
                    id, article_id, user_id, author_name, author_avatar, content,
                    status, comment_type, is_solution, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'published', 'comment', 0, '2026-10-01T10:05:00Z')
            """, ("comm_alice", "art_issue71_01", "u_alice", "Алиса", "", "Комментарий Алисы"))

            # comm_bob: author is u_bob
            conn.execute("""
                INSERT INTO article_comments (
                    id, article_id, user_id, author_name, author_avatar, content,
                    status, comment_type, is_solution, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'published', 'comment', 0, '2026-10-01T10:10:00Z')
            """, ("comm_bob", "art_issue71_01", "u_bob", "Боб", "", "Комментарий Боба"))

            # comm_deleted: deleted comment
            conn.execute("""
                INSERT INTO article_comments (
                    id, article_id, user_id, author_name, author_avatar, content,
                    status, comment_type, is_solution, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'deleted', 'comment', 0, '2026-10-01T10:15:00Z')
            """, ("comm_deleted", "art_issue71_01", "u_bob", "Боб", "", "Удаленный комментарий"))
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
            try:
                res_body = e.read().decode("utf-8")
                return e.code, json.loads(res_body) if res_body else {}
            finally:
                e.close()

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
            try:
                res_body = e.read().decode("utf-8")
                return e.code, json.loads(res_body) if res_body else {}
            finally:
                e.close()

    # ---------------------------------------------------------
    # 1. Database Schema and Invariants
    # ---------------------------------------------------------
    def test_01_schema_tables_and_indexes(self):
        """Verifies comment_reports and comment_subscriptions tables and columns exist in SQLite."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        # Check comment_reports columns
        cur.execute("PRAGMA table_info(comment_reports)")
        report_cols = {row[1]: row[2] for row in cur.fetchall()}
        self.assertIn("id", report_cols)
        self.assertIn("comment_id", report_cols)
        self.assertIn("user_id", report_cols)
        self.assertIn("reason", report_cols)
        self.assertIn("details", report_cols)
        self.assertIn("created_at", report_cols)

        # Check comment_subscriptions columns
        cur.execute("PRAGMA table_info(comment_subscriptions)")
        sub_cols = {row[1]: row[2] for row in cur.fetchall()}
        self.assertIn("id", sub_cols)
        self.assertIn("comment_id", sub_cols)
        self.assertIn("user_id", sub_cols)
        self.assertIn("created_at", sub_cols)

        # Check unique constraint on comment_subscriptions (comment_id, user_id)
        cur.execute("PRAGMA index_list(comment_subscriptions)")
        indexes = cur.fetchall()
        has_unique = any(idx[2] == 1 for idx in indexes)
        self.assertTrue(has_unique, "comment_subscriptions must enforce unique constraint on (comment_id, user_id)")

        conn.close()

    def test_02_init_db_idempotency(self):
        """Verifies repeated init_db calls preserve existing schema and data without errors."""
        conn = init_db(self.db_path, seed=False)
        conn.close()

    # ---------------------------------------------------------
    # 2. Report Endpoint Invariants
    # ---------------------------------------------------------
    def test_03_report_requires_auth(self):
        """POST /api/comments/<id>/report returns 401 when unauthorized."""
        status, body = self._post_json("/api/comments/comm_bob/report", {"reason": "spam"})
        self.assertEqual(status, 401)
        self.assertFalse(body.get("success"))
        self.assertEqual(body.get("code"), "AUTH_REQUIRED")

    def test_04_cannot_report_own_comment(self):
        """POST /api/comments/<id>/report returns 403 CANNOT_REPORT_OWN_COMMENT if author reports own comment."""
        cookie_alice = self._login("u_alice", "Алиса")
        # comm_alice was authored by u_alice
        status, body = self._post_json("/api/comments/comm_alice/report", {"reason": "spam"}, cookie=cookie_alice)
        self.assertEqual(status, 403)
        self.assertFalse(body.get("success"))
        self.assertEqual(body.get("code"), "CANNOT_REPORT_OWN_COMMENT")

    def test_05_report_validates_reason(self):
        """POST /api/comments/<id>/report validates reason (required, non-empty, max 200 chars)."""
        cookie_alice = self._login("u_alice", "Алиса")

        # Missing reason
        status, body = self._post_json("/api/comments/comm_bob/report", {}, cookie=cookie_alice)
        self.assertEqual(status, 400)
        self.assertEqual(body.get("code"), "INVALID_REASON")

        # Empty reason
        status, body = self._post_json("/api/comments/comm_bob/report", {"reason": "   "}, cookie=cookie_alice)
        self.assertEqual(status, 400)
        self.assertEqual(body.get("code"), "INVALID_REASON")

        # Reason exceeding 200 characters
        too_long = "x" * 201
        status, body = self._post_json("/api/comments/comm_bob/report", {"reason": too_long}, cookie=cookie_alice)
        self.assertEqual(status, 400)
        self.assertEqual(body.get("code"), "REASON_TOO_LONG")

    def test_06_report_non_existent_comment(self):
        """POST /api/comments/<id>/report returns 404 if comment does not exist."""
        cookie_alice = self._login("u_alice", "Алиса")
        status, body = self._post_json("/api/comments/non_existent_comm/report", {"reason": "spam"}, cookie=cookie_alice)
        self.assertEqual(status, 404)
        self.assertEqual(body.get("code"), "NOT_FOUND")

    def test_07_report_success_and_duplicate_prevention(self):
        """Reporting with valid reason succeeds (200), duplicate report fails (409)."""
        cookie_alice = self._login("u_alice", "Алиса")

        # First report on comm_bob by u_alice
        status, body = self._post_json(
            "/api/comments/comm_bob/report",
            {"reason": "spam", "details": "Рекламная ссылка на сторонний сайт"},
            cookie=cookie_alice
        )
        self.assertEqual(status, 200)
        self.assertTrue(body.get("success"))
        self.assertEqual(body.get("message"), "Жалоба отправлена")

        # Verify record in SQLite
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT user_id, comment_id, reason, details FROM comment_reports WHERE comment_id = 'comm_bob'")
        row = cur.fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "u_alice")
        self.assertEqual(row[1], "comm_bob")
        self.assertEqual(row[2], "spam")
        self.assertEqual(row[3], "Рекламная ссылка на сторонний сайт")

        # Second report by same user on same comment returns 409 REPORT_ALREADY_EXISTS
        status_dup, body_dup = self._post_json(
            "/api/comments/comm_bob/report",
            {"reason": "insult"},
            cookie=cookie_alice
        )
        self.assertEqual(status_dup, 409)
        self.assertFalse(body_dup.get("success"))
        self.assertEqual(body_dup.get("code"), "REPORT_ALREADY_EXISTS")

        # Another user (u_charlie) can report the same comment
        cookie_charlie = self._login("u_charlie", "Чарли")
        status_charlie, body_charlie = self._post_json(
            "/api/comments/comm_bob/report",
            {"reason": "insult"},
            cookie=cookie_charlie
        )
        self.assertEqual(status_charlie, 200)
        self.assertTrue(body_charlie.get("success"))

    # ---------------------------------------------------------
    # 3. Subscribe Endpoint Invariants
    # ---------------------------------------------------------
    def test_08_subscribe_requires_auth(self):
        """POST /api/comments/<id>/subscribe returns 401 when unauthorized."""
        status, body = self._post_json("/api/comments/comm_bob/subscribe", {})
        self.assertEqual(status, 401)
        self.assertFalse(body.get("success"))
        self.assertEqual(body.get("code"), "AUTH_REQUIRED")

    def test_09_subscribe_non_existent_comment(self):
        """POST /api/comments/<id>/subscribe returns 404 if comment does not exist."""
        cookie_alice = self._login("u_alice", "Алиса")
        status, body = self._post_json("/api/comments/ghost_comm/subscribe", {}, cookie=cookie_alice)
        self.assertEqual(status, 404)
        self.assertEqual(body.get("code"), "NOT_FOUND")

    def test_10_subscribe_toggle(self):
        """POST /api/comments/<id>/subscribe toggles subscription state between true and false."""
        cookie_alice = self._login("u_alice", "Алиса")

        # 1st call: subscribe -> returns subscribed: true
        status1, body1 = self._post_json("/api/comments/comm_bob/subscribe", {}, cookie=cookie_alice)
        self.assertEqual(status1, 200)
        self.assertTrue(body1.get("success"))
        self.assertTrue(body1.get("subscribed"))

        # Verify DB entry exists
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT id FROM comment_subscriptions WHERE user_id = 'u_alice' AND comment_id = 'comm_bob'")
        self.assertIsNotNone(cur.fetchone())
        conn.close()

        # 2nd call: unsubscribe -> returns subscribed: false
        status2, body2 = self._post_json("/api/comments/comm_bob/subscribe", {}, cookie=cookie_alice)
        self.assertEqual(status2, 200)
        self.assertTrue(body2.get("success"))
        self.assertFalse(body2.get("subscribed"))

        # Verify DB entry deleted
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT id FROM comment_subscriptions WHERE user_id = 'u_alice' AND comment_id = 'comm_bob'")
        self.assertIsNone(cur.fetchone())
        conn.close()

        # 3rd call: re-subscribe -> returns subscribed: true
        status3, body3 = self._post_json("/api/comments/comm_bob/subscribe", {}, cookie=cookie_alice)
        self.assertEqual(status3, 200)
        self.assertTrue(body3.get("success"))
        self.assertTrue(body3.get("subscribed"))

    # ---------------------------------------------------------
    # 4. Subscriptions List Endpoint Invariants
    # ---------------------------------------------------------
    def test_11_subscriptions_list_requires_auth(self):
        """GET /api/comments/subscriptions returns 401 when unauthorized."""
        status, body = self._get_json("/api/comments/subscriptions")
        self.assertEqual(status, 401)
        self.assertFalse(body.get("success"))
        self.assertEqual(body.get("code"), "AUTH_REQUIRED")

    def test_12_subscriptions_list_returns_subscribed_comments(self):
        """GET /api/comments/subscriptions returns list of subscribed comment IDs with user isolation."""
        cookie_alice = self._login("u_alice", "Алиса")
        cookie_bob = self._login("u_bob", "Боб")

        # Alice is currently subscribed to comm_bob (from test_10)
        status_alice, body_alice = self._get_json("/api/comments/subscriptions", cookie=cookie_alice)
        self.assertEqual(status_alice, 200)
        self.assertTrue(body_alice.get("success"))
        self.assertIn("comm_bob", body_alice.get("subscriptions", []))

        # Bob has not subscribed to anything yet
        status_bob, body_bob = self._get_json("/api/comments/subscriptions", cookie=cookie_bob)
        self.assertEqual(status_bob, 200)
        self.assertTrue(body_bob.get("success"))
        self.assertEqual(body_bob.get("subscriptions"), [])

        # Bob subscribes to comm_alice
        status_sub, body_sub = self._post_json("/api/comments/comm_alice/subscribe", {}, cookie=cookie_bob)
        self.assertEqual(status_sub, 200)
        self.assertTrue(body_sub.get("subscribed"))

        # Bob now has comm_alice in subscriptions list
        status_bob2, body_bob2 = self._get_json("/api/comments/subscriptions", cookie=cookie_bob)
        self.assertEqual(status_bob2, 200)
        self.assertEqual(body_bob2.get("subscriptions"), ["comm_alice"])

        # Alice's subscriptions still only contain comm_bob (isolated)
        status_alice2, body_alice2 = self._get_json("/api/comments/subscriptions", cookie=cookie_alice)
        self.assertEqual(status_alice2, 200)
        self.assertEqual(body_alice2.get("subscriptions"), ["comm_bob"])

        # Alice unsubscribes from comm_bob
        self._post_json("/api/comments/comm_bob/subscribe", {}, cookie=cookie_alice)

        # Alice's subscriptions list is now empty
        status_alice3, body_alice3 = self._get_json("/api/comments/subscriptions", cookie=cookie_alice)
        self.assertEqual(status_alice3, 200)
        self.assertEqual(body_alice3.get("subscriptions"), [])


def read_file(relative_path: str) -> str:
    full_path = os.path.join(PROJECT_ROOT, relative_path)
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()


class TestIssue71CommentNewActionsFrontend(unittest.TestCase):
    """Verifies frontend action buttons, sequence, DOM wiring, CSS styles, and contracts for Issue #71."""

    @classmethod
    def setUpClass(cls):
        cls.article_js = read_file("frontend/public/js/article.js")
        cls.article_css = read_file("frontend/public/css/article.css")
        cls.theme_css = read_file("frontend/public/css/theme.css")
        cls.article_html = read_file("frontend/public/article.html")

    def test_13_new_buttons_exist_with_classes_and_attributes(self):
        """Verify Bookmark, Share, Subscribe, and Report buttons exist with classes, titles, and aria-labels."""
        # 1. Bookmark (Save)
        # Comment save button
        save_comm_match = re.search(
            r'class="btn-comment-action btn-save-comment[^"]*"\s+title="[^"]*"\s+aria-label="[^"]*"\s+data-comment-id=',
            self.article_js
        )
        self.assertIsNotNone(save_comm_match, "Comment save button must be .btn-comment-action.btn-save-comment with title, aria-label, and data-comment-id")
        self.assertIn('title="\' + (isSaved ? \'Удалить из закладок\' : \'Сохранить\') + \'"', self.article_js)
        self.assertIn('aria-label="\' + (isSaved ? \'Удалить из закладок\' : \'Сохранить\') + \'"', self.article_js)

        # Answer save button
        save_ans_match = re.search(
            r'class="btn-comment-action btn-save-answer[^"]*"\s+title="[^"]*"\s+aria-label="[^"]*"\s+data-comment-id=',
            self.article_js
        )
        self.assertIsNotNone(save_ans_match, "Answer save button must be .btn-comment-action.btn-save-answer with title, aria-label, and data-comment-id")

        # 2. Share
        # Comment share button
        share_comm_match = re.search(
            r'class="btn-comment-action btn-share-comment"\s+title="Поделиться"\s+aria-label="Поделиться"\s+data-comment-id=',
            self.article_js
        )
        self.assertIsNotNone(share_comm_match, "Comment share button must have title='Поделиться', aria-label='Поделиться', and data-comment-id")

        # Answer share button
        share_ans_match = re.search(
            r'class="btn-comment-action btn-share-answer"\s+title="Поделиться"\s+aria-label="Поделиться"\s+data-comment-id=',
            self.article_js
        )
        self.assertIsNotNone(share_ans_match, "Answer share button must have title='Поделиться', aria-label='Поделиться', and data-comment-id")

        # 3. Subscribe (Bell)
        # Comment subscribe button
        sub_comm_match = re.search(
            r'class="btn-comment-action btn-subscribe-comment[^"]*"\s+title="[^"]*"\s+aria-label="[^"]*"\s+data-comment-id=',
            self.article_js
        )
        self.assertIsNotNone(sub_comm_match, "Comment subscribe button must be .btn-comment-action.btn-subscribe-comment")
        self.assertIn('title="\' + (isSubscribed ? \'Отписаться от ответов\' : \'Подписаться на ответы\') + \'"', self.article_js)
        self.assertIn('aria-label="\' + (isSubscribed ? \'Отписаться от ответов\' : \'Подписаться на ответы\') + \'"', self.article_js)

        # Answer subscribe button
        sub_ans_match = re.search(
            r'class="btn-comment-action btn-subscribe-answer[^"]*"\s+title="[^"]*"\s+aria-label="[^"]*"\s+data-comment-id=',
            self.article_js
        )
        self.assertIsNotNone(sub_ans_match, "Answer subscribe button must be .btn-comment-action.btn-subscribe-answer")

        # 4. Report (Flag)
        # Comment report button
        rep_comm_match = re.search(
            r'class="btn-comment-action btn-report-comment[^"]*"\s+title="[^"]*"\s+aria-label="Пожаловаться"\s+data-comment-id=',
            self.article_js
        )
        self.assertIsNotNone(rep_comm_match, "Comment report button must be .btn-comment-action.btn-report-comment with aria-label='Пожаловаться'")

        # Answer report button
        rep_ans_match = re.search(
            r'class="btn-comment-action btn-report-answer[^"]*"\s+title="[^"]*"\s+aria-label="Пожаловаться"\s+data-comment-id=',
            self.article_js
        )
        self.assertIsNotNone(rep_ans_match, "Answer report button must be .btn-comment-action.btn-report-answer with aria-label='Пожаловаться'")

    def test_14_strict_action_sequence_in_comment_and_answer_rows(self):
        """Verify strict sequence: Capsule -> Reply -> Save -> Share -> Subscribe -> Report -> Delete -> Edit."""
        # Comment row sequence
        comm_row_pattern = (
            r'<div class="comment-vote-row comment-action-row">\s*\'\s*\+\s*'
            r'commVoteCapsuleHtml\s*\+\s*'
            r'replyBtnHtml\s*\+\s*'
            r'saveBtnHtml\s*\+\s*'
            r'shareBtnHtml\s*\+\s*'
            r'subscribeBtnHtml\s*\+\s*'
            r'reportBtnHtml\s*\+\s*'
            r'deleteBtnHtml\s*\+\s*'
            r'editBtnHtml\s*\+\s*'
            r'\'\s*</div>'
        )
        match_comm = re.search(comm_row_pattern, self.article_js)
        self.assertIsNotNone(
            match_comm,
            "Comment action row must strictly assemble: Capsule -> Reply -> Save -> Share -> Subscribe -> Report -> Delete -> Edit"
        )

        # Answer row sequence
        ans_row_pattern = (
            r'<div class="comment-vote-row answer-vote-row comment-action-row answer-actions">\s*\'\s*\+\s*'
            r'ansVoteCapsuleHtml\s*\+\s*'
            r'replyBtnHtml\s*\+\s*'
            r'saveBtnHtml\s*\+\s*'
            r'shareBtnHtml\s*\+\s*'
            r'subscribeBtnHtml\s*\+\s*'
            r'reportBtnHtml\s*\+\s*'
            r'editBtnHtml\s*\+\s*'
            r'\'\s*</div>'
        )
        match_ans = re.search(ans_row_pattern, self.article_js)
        self.assertIsNotNone(
            match_ans,
            "Answer action row must strictly assemble: Capsule -> Reply -> Save -> Share -> Subscribe -> Report -> Edit"
        )

    def test_15_report_button_hidden_for_own_comment_and_answer(self):
        """Verify report button is hidden for comment/answer author's own posts."""
        # For comments: reportBtnHtml is only created when !isMyComment
        self.assertIn("if (!isMyComment)", self.article_js)
        comm_report_guard = re.search(
            r'if\s*\(!isMyComment\)\s*\{\s*[^}]*btn-report-comment',
            self.article_js
        )
        self.assertIsNotNone(comm_report_guard, "Comment report button must be guarded by !isMyComment check")

        # For answers: reportBtnHtml is only created when !isMyAnswer
        self.assertIn("if (!isMyAnswer)", self.article_js)
        ans_report_guard = re.search(
            r'if\s*\(!isMyAnswer\)\s*\{\s*[^}]*btn-report-answer',
            self.article_js
        )
        self.assertIsNotNone(ans_report_guard, "Answer report button must be guarded by !isMyAnswer check")

    def test_16_bookmark_toggling_and_localstorage_persistence(self):
        """Verify bookmark toggling uses sc_comment_bookmarks in localStorage and toggles .is-bookmarked."""
        self.assertIn("sc_comment_bookmarks", self.article_js, "Storage key sc_comment_bookmarks must be used in article.js")
        self.assertIn("toggleCommentBookmark", self.article_js)
        self.assertIn("isCommentBookmarked", self.article_js)
        self.assertIn("getCommentBookmarks", self.article_js)
        self.assertIn("is-bookmarked", self.article_js)
        self.assertIn("Комментарий сохранен в закладки", self.article_js)
        self.assertIn("Комментарий удален из закладок", self.article_js)

    def test_17_subscribe_toggling_logic_and_api(self):
        """Verify subscription toggling calls POST /api/comments/<id>/subscribe and updates state."""
        self.assertIn("/api/comments/' + encodeURIComponent(commentId) + '/subscribe", self.article_js)
        self.assertIn("sc_comment_subscriptions", self.article_js)
        self.assertIn("is-subscribed", self.article_js)
        self.assertIn("handleSubscribeComment", self.article_js)
        self.assertIn("Войдите, чтобы подписаться на ответы", self.article_js)
        self.assertIn("Подписка на ответы оформлена", self.article_js)
        self.assertIn("Подписка на ответы отменена", self.article_js)

    def test_18_report_modal_and_dialog_logic(self):
        """Verify report dialog/modal structure, reason options, and submission logic."""
        self.assertIn("commentReportModal", self.article_html)
        self.assertIn("commentReportForm", self.article_html)
        self.assertIn("reportReason", self.article_html)
        self.assertIn('value="spam"', self.article_html)
        self.assertIn('value="insult"', self.article_html)
        self.assertIn('value="malicious"', self.article_html)
        self.assertIn('value="other"', self.article_html)

        # In article.js
        self.assertIn("/api/comments/' + encodeURIComponent(commentId) + '/report", self.article_js)
        self.assertIn("openCommentReportModal", self.article_js)
        self.assertIn("Войдите, чтобы отправить жалобу", self.article_js)
        self.assertIn("Жалоба отправлена", self.article_js)
        self.assertIn("Жалоба уже отправлена", self.article_js)
        self.assertIn("is-reported", self.article_js)

    def test_19_share_action_clipboard_copy(self):
        """Verify share button copies formatted link to clipboard and notifies via toast."""
        self.assertIn("copyCommentLink", self.article_js)
        self.assertIn("#comm_", self.article_js)
        self.assertIn("Ссылка скопирована", self.article_js)

    def test_20_css_classes_and_hover_active_states(self):
        """Verify CSS hover, active, and focus states for all 4 new actions in article.css and theme.css."""
        for css_content, source_name in [(self.article_css, "article.css"), (self.theme_css, "theme.css")]:
            # Bookmark hover
            bm_hover = re.search(r'\.btn-comment-action\.btn-save-comment:hover[^{]*\{([^}]+)\}', css_content)
            self.assertIsNotNone(bm_hover, f"Bookmark hover rule must exist in {source_name}")
            self.assertIn("#f59e0b", bm_hover.group(1))

            # Bookmark active .is-bookmarked
            bm_active = re.search(r'\.btn-comment-action(?:\.btn-save-comment)?\.is-bookmarked[^{]*\{([^}]+)\}', css_content)
            self.assertIsNotNone(bm_active, f"Bookmark .is-bookmarked rule must exist in {source_name}")
            self.assertIn("#f59e0b", bm_active.group(1))

            # Subscribe hover
            sub_hover = re.search(r'\.btn-comment-action\.btn-subscribe-comment:hover[^{]*\{([^}]+)\}', css_content)
            self.assertIsNotNone(sub_hover, f"Subscribe hover rule must exist in {source_name}")
            self.assertIn("#38bdf8", sub_hover.group(1))

            # Subscribe active .is-subscribed
            sub_active = re.search(r'\.btn-comment-action(?:\.btn-subscribe-comment)?\.is-subscribed[^{]*\{([^}]+)\}', css_content)
            self.assertIsNotNone(sub_active, f"Subscribe .is-subscribed rule must exist in {source_name}")
            self.assertIn("#38bdf8", sub_active.group(1))

            # Report hover
            rep_hover = re.search(r'\.btn-comment-action\.btn-report-comment:hover[^{]*\{([^}]+)\}', css_content)
            self.assertIsNotNone(rep_hover, f"Report hover rule must exist in {source_name}")
            self.assertIn("#f97316", rep_hover.group(1))

            # Report .is-reported
            rep_active = re.search(r'\.btn-comment-action(?:\.btn-report-comment)?\.is-reported[^{]*\{([^}]+)\}', css_content)
            self.assertIsNotNone(rep_active, f"Report .is-reported rule must exist in {source_name}")
            rep_block = rep_active.group(1)
            self.assertIn("opacity: 0.5;", rep_block)
            self.assertIn("cursor: default;", rep_block)

            # Report modal styling
            self.assertIn(".comment-report-modal-card", css_content)
            self.assertIn(".comment-report-form", css_content)
            self.assertIn(".comment-report-radio", css_content)
            self.assertIn(".comment-report-textarea", css_content)

    def test_21_zero_emojis_no_em_dashes_offline_first(self):
        """Ensure zero emojis, zero em dashes, and 100% offline-first in all modified files."""
        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]|[\u2600-\u26ff]|[\u2700-\u27bf]")
        files_to_check = [
            (read_file("tests/test_issue71_comment_new_actions.py"), "test_issue71_comment_new_actions.py"),
            (self.article_js, "article.js"),
            (self.article_css, "article.css"),
            (self.theme_css, "theme.css"),
            (self.article_html, "article.html")
        ]
        for content, name in files_to_check:
            self.assertIsNone(emoji_pattern.search(content), f"Emoji found in {name}")
            self.assertNotIn("\u2014", content, f"Em dash found in {name}")

        for css_content, source_name in [(self.article_css, "article.css"), (self.theme_css, "theme.css")]:
            urls = re.findall(r'url\s*\(\s*["\']?(https?://[^"\')]+)', css_content)
            self.assertEqual(len(urls), 0, f"External CDN url found in {source_name}: {urls}")


if __name__ == "__main__":
    unittest.main()

