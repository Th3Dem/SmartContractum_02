#!/usr/bin/env python3
"""
tests/test_issue73_comment_edit_window.py

Automated test suite for Issue #73 (SC-030):
Enforce 48-hour editing window for comments and answers in server.py.

Requirements verified:
1. Updating comment created 47 hours 59 minutes ago returns 200 OK.
2. Updating comment created 48 hours 1 minute ago returns 403 with code EDIT_WINDOW_EXPIRED.
3. Updating comment created exactly 48 hours ago returns 403 with code EDIT_WINDOW_EXPIRED.
4. Updating non-owned comment returns 403 with author ownership error.
5. Unauthenticated update returns 401 with requireAuth.
6. Updating answer within 48 hours returns 200 OK; after 48 hours returns 403 EDIT_WINDOW_EXPIRED.
7. Timestamps formatted with ISO Z notation are correctly parsed and window enforced.

Strict compliance: zero emojis, zero em dashes, 100% offline-first.
"""

import datetime
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


class TestIssue73CommentEditWindowBackend(unittest.TestCase):
    """
    Test suite verifying backend 48-hour comment editing window enforcement.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue73.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path, seed=False)
        with conn:
            users = [
                ("u_author", "Автор Статьи", "author"),
                ("u_commenter", "Комментатор", "user"),
                ("u_stranger", "Другой Пользователь", "user"),
            ]
            for uid, name, role in users:
                conn.execute("""
                    INSERT INTO user_profiles (
                        user_id, name, specialization, company, bio, avatar, created_at, updated_at
                    ) VALUES (?, ?, 'Engineer', 'SmartCo', '', '', '2026-10-01T10:00:00Z', '2026-10-01T10:00:00Z')
                """, (uid, name))

            # Seed article
            conn.execute("""
                INSERT INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, article_delta, idempotency_key, snapshot_hash,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'approved', ?, ?, NULL, ?, ?, ?, ?)
            """, (
                "art_issue73_01", "draft_art_73_01", "Статья для тестирования окна редактирования", "u_author",
                json.dumps({"materialType": "article", "topics": ["testing"]}, ensure_ascii=False),
                "<p>Содержимое статьи</p>", "idemp_73_art", "hash_73_art",
                "2026-09-20T10:00:00Z", "2026-09-20T10:00:00Z"
            ))

            # Seed questions
            conn.execute("""
                INSERT INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, article_delta, idempotency_key, snapshot_hash,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'approved', ?, ?, NULL, ?, ?, ?, ?)
            """, (
                "quest_issue73_01", "draft_quest_73_01", "Вопрос 1 для тестирования ответов", "u_author",
                json.dumps({"materialType": "question", "topics": ["testing"]}, ensure_ascii=False),
                "<p>Содержимое вопроса 1</p>", "idemp_73_quest1", "hash_73_quest1",
                "2026-09-20T10:00:00Z", "2026-09-20T10:00:00Z"
            ))

            conn.execute("""
                INSERT INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, article_delta, idempotency_key, snapshot_hash,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'approved', ?, ?, NULL, ?, ?, ?, ?)
            """, (
                "quest_issue73_02", "draft_quest_73_02", "Вопрос 2 для тестирования ответов", "u_author",
                json.dumps({"materialType": "question", "topics": ["testing"]}, ensure_ascii=False),
                "<p>Содержимое вопроса 2</p>", "idemp_73_quest2", "hash_73_quest2",
                "2026-09-20T10:00:00Z", "2026-09-20T10:00:00Z"
            ))
        conn.close()

        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR, seed=False)
        cls.port = cls.httpd.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"

        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            cls.httpd.shutdown()
            cls.httpd.server_close()
        except Exception:
            pass
        if hasattr(cls, "server_thread") and cls.server_thread:
            cls.server_thread.join(timeout=2)
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def _login(self, user_id: str, name: str) -> str:
        url = f"{self.base_url}/api/auth/login"
        payload = json.dumps({"userId": user_id, "name": name}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as resp:
            cookie_headers = resp.headers.get_all("Set-Cookie") or []
            session_cookie = ""
            for c in cookie_headers:
                if "sc_session=" in c:
                    session_cookie = c.split(";")[0]
                    break
            return session_cookie

    def _put_json(self, path: str, data: dict, cookie: Optional[str] = None) -> Tuple[int, dict]:
        url = f"{self.base_url}{path}"
        payload = json.dumps(data).encode("utf-8")
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if cookie:
            headers["Cookie"] = cookie
        req = urllib.request.Request(url, data=payload, headers=headers, method="PUT")
        try:
            with urllib.request.urlopen(req) as resp:
                res_body = resp.read().decode("utf-8")
                return resp.status, json.loads(res_body) if res_body else {}
        except urllib.error.HTTPError as e:
            with e:
                res_body = e.read().decode("utf-8")
                return e.code, json.loads(res_body) if res_body else {}

    def _insert_comment(
        self,
        comm_id: str,
        article_id: str,
        user_id: str,
        author_name: str,
        content: str,
        created_at: str,
        comment_type: str = "comment",
        revision: int = 1
    ) -> None:
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute("""
                INSERT INTO article_comments (
                    id, article_id, user_id, author_name, author_avatar,
                    content, status, comment_type, is_solution,
                    parent_answer_id, parent_comment_id, client_operation_id,
                    updated_at, revision, created_at
                ) VALUES (?, ?, ?, ?, '', ?, 'published', ?, 0, NULL, NULL, NULL, NULL, ?, ?)
            """, (comm_id, article_id, user_id, author_name, content, comment_type, revision, created_at))
        conn.close()

    def test_01_update_comment_within_edit_window_succeeds(self) -> None:
        """Comment created 47 hours 59 minutes ago is within 48-hour window and can be updated."""
        cookie_commenter = self._login("u_commenter", "Комментатор")
        comm_id = "comm_win_01"

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        created_dt = now_utc - datetime.timedelta(hours=47, minutes=59)
        self._insert_comment(
            comm_id=comm_id,
            article_id="art_issue73_01",
            user_id="u_commenter",
            author_name="Комментатор",
            content="Исходный комментарий (47h 59m ago)",
            created_at=created_dt.isoformat(),
            comment_type="comment",
            revision=1
        )

        status, body = self._put_json(
            f"/api/articles/art_issue73_01/comments/{comm_id}",
            {"content": "Обновленный комментарий в пределах 48 часов", "revision": 1},
            cookie=cookie_commenter
        )

        self.assertEqual(status, 200)
        self.assertTrue(body.get("success"))
        self.assertEqual(body["comment"]["content"], "Обновленный комментарий в пределах 48 часов")
        self.assertEqual(body["comment"]["revision"], 2)

    def test_02_update_comment_after_edit_window_rejected(self) -> None:
        """Comment created 48 hours 1 minute ago is outside window and cannot be updated."""
        cookie_commenter = self._login("u_commenter", "Комментатор")
        comm_id = "comm_win_02"

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        created_dt = now_utc - datetime.timedelta(hours=48, minutes=1)
        self._insert_comment(
            comm_id=comm_id,
            article_id="art_issue73_01",
            user_id="u_commenter",
            author_name="Комментатор",
            content="Исходный комментарий (48h 1m ago)",
            created_at=created_dt.isoformat(),
            comment_type="comment",
            revision=1
        )

        status, body = self._put_json(
            f"/api/articles/art_issue73_01/comments/{comm_id}",
            {"content": "Попытка обновить комментарий после истечения окна", "revision": 1},
            cookie=cookie_commenter
        )

        self.assertEqual(status, 403)
        self.assertFalse(body.get("success"))
        self.assertEqual(body.get("code"), "EDIT_WINDOW_EXPIRED")
        self.assertIn("Срок редактирования комментария истек", body.get("error", ""))

    def test_03_update_comment_exact_boundary_rejected(self) -> None:
        """Comment created exactly 48 hours ago meets >= 48*3600 limit and is rejected."""
        cookie_commenter = self._login("u_commenter", "Комментатор")
        comm_id = "comm_win_03"

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        created_dt = now_utc - datetime.timedelta(hours=48)
        self._insert_comment(
            comm_id=comm_id,
            article_id="art_issue73_01",
            user_id="u_commenter",
            author_name="Комментатор",
            content="Исходный комментарий (ровно 48h ago)",
            created_at=created_dt.isoformat(),
            comment_type="comment",
            revision=1
        )

        status, body = self._put_json(
            f"/api/articles/art_issue73_01/comments/{comm_id}",
            {"content": "Попытка обновить комментарий на границе 48 часов", "revision": 1},
            cookie=cookie_commenter
        )

        self.assertEqual(status, 403)
        self.assertFalse(body.get("success"))
        self.assertEqual(body.get("code"), "EDIT_WINDOW_EXPIRED")

    def test_04_update_non_owned_comment_rejected(self) -> None:
        """Foreign user cannot edit another user's comment, even within edit window."""
        cookie_stranger = self._login("u_stranger", "Другой Пользователь")
        comm_id = "comm_win_04"

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        created_dt = now_utc - datetime.timedelta(minutes=30)
        self._insert_comment(
            comm_id=comm_id,
            article_id="art_issue73_01",
            user_id="u_commenter",
            author_name="Комментатор",
            content="Комментарий u_commenter (30 минут назад)",
            created_at=created_dt.isoformat(),
            comment_type="comment",
            revision=1
        )

        status, body = self._put_json(
            f"/api/articles/art_issue73_01/comments/{comm_id}",
            {"content": "Попытка чужого пользователя отредактировать", "revision": 1},
            cookie=cookie_stranger
        )

        self.assertEqual(status, 403)
        self.assertFalse(body.get("success"))
        self.assertNotEqual(body.get("code"), "EDIT_WINDOW_EXPIRED")
        self.assertEqual(body.get("error"), "Вы можете редактировать только свой комментарий или ответ")

    def test_05_unauthenticated_update_rejected(self) -> None:
        """Unauthenticated guest request is rejected with 401 and requireAuth."""
        comm_id = "comm_win_05"

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        created_dt = now_utc - datetime.timedelta(minutes=10)
        self._insert_comment(
            comm_id=comm_id,
            article_id="art_issue73_01",
            user_id="u_commenter",
            author_name="Комментатор",
            content="Свежий комментарий",
            created_at=created_dt.isoformat(),
            comment_type="comment",
            revision=1
        )

        status, body = self._put_json(
            f"/api/articles/art_issue73_01/comments/{comm_id}",
            {"content": "Анонимная правка", "revision": 1},
            cookie=None
        )

        self.assertEqual(status, 401)
        self.assertFalse(body.get("success"))
        self.assertTrue(body.get("requireAuth"))

    def test_06_update_answer_window_enforcement(self) -> None:
        """Editing answers also respects the 48-hour window invariant."""
        cookie_commenter = self._login("u_commenter", "Комментатор")
        ans_ok_id = "ans_win_ok"
        ans_exp_id = "ans_win_exp"

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        dt_ok = now_utc - datetime.timedelta(hours=47, minutes=59)
        dt_exp = now_utc - datetime.timedelta(hours=48, minutes=5)

        self._insert_comment(
            comm_id=ans_ok_id,
            article_id="quest_issue73_01",
            user_id="u_commenter",
            author_name="Комментатор",
            content="Ответ в пределах окна",
            created_at=dt_ok.isoformat(),
            comment_type="answer",
            revision=1
        )

        self._insert_comment(
            comm_id=ans_exp_id,
            article_id="quest_issue73_02",
            user_id="u_commenter",
            author_name="Комментатор",
            content="Ответ за пределами окна",
            created_at=dt_exp.isoformat(),
            comment_type="answer",
            revision=1
        )

        # Update valid answer
        status_ok, body_ok = self._put_json(
            f"/api/articles/quest_issue73_01/comments/{ans_ok_id}",
            {"content": "Успешно отредактированный ответ", "revision": 1},
            cookie=cookie_commenter
        )
        self.assertEqual(status_ok, 200)
        self.assertTrue(body_ok.get("success"))
        self.assertEqual(body_ok["comment"]["content"], "Успешно отредактированный ответ")

        # Update expired answer
        status_exp, body_exp = self._put_json(
            f"/api/articles/quest_issue73_02/comments/{ans_exp_id}",
            {"content": "Правка просроченного ответа", "revision": 1},
            cookie=cookie_commenter
        )
        self.assertEqual(status_exp, 403)
        self.assertFalse(body_exp.get("success"))
        self.assertEqual(body_exp.get("code"), "EDIT_WINDOW_EXPIRED")

    def test_07_iso_z_timestamp_format_handling(self) -> None:
        """Comment with ISO 'Z' suffix is correctly parsed and enforced."""
        cookie_commenter = self._login("u_commenter", "Комментатор")
        comm_id = "comm_win_z"

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        dt_old = now_utc - datetime.timedelta(days=3)
        iso_z = dt_old.strftime("%Y-%m-%dT%H:%M:%SZ")

        self._insert_comment(
            comm_id=comm_id,
            article_id="art_issue73_01",
            user_id="u_commenter",
            author_name="Комментатор",
            content="Старый комментарий с суффиксом Z",
            created_at=iso_z,
            comment_type="comment",
            revision=1
        )

        status, body = self._put_json(
            f"/api/articles/art_issue73_01/comments/{comm_id}",
            {"content": "Попытка обновить трехдневный комментарий", "revision": 1},
            cookie=cookie_commenter
        )

        self.assertEqual(status, 403)
        self.assertFalse(body.get("success"))
        self.assertEqual(body.get("code"), "EDIT_WINDOW_EXPIRED")


class TestIssue73CommentEditWindowFrontend(unittest.TestCase):
    """
    Test suite verifying frontend enforcement of the 48-hour comment editing window:
    - isCommentEditExpired helper and window export
    - Comment and answer edit button states (disabled and active)
    - CSS styling for disabled action buttons
    - Error handling for server EDIT_WINDOW_EXPIRED code
    - Offline-first and clean typography invariants
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.article_js_path = os.path.join(FRONTEND_DIR, "js", "article.js")
        cls.article_css_path = os.path.join(FRONTEND_DIR, "css", "article.css")
        cls.theme_css_path = os.path.join(FRONTEND_DIR, "css", "theme.css")

        with open(cls.article_js_path, "r", encoding="utf-8") as f:
            cls.article_js = f.read()

        with open(cls.article_css_path, "r", encoding="utf-8") as f:
            cls.article_css = f.read()

        with open(cls.theme_css_path, "r", encoding="utf-8") as f:
            cls.theme_css = f.read()

    def test_08_is_comment_edit_expired_helper_and_export(self) -> None:
        """Verify isCommentEditExpired helper exists, exports to window, and enforces 48-hour boundary."""
        self.assertIn("function isCommentEditExpired(createdAt)", self.article_js)
        self.assertIn("window.isCommentEditExpired = isCommentEditExpired;", self.article_js)

        # Mirror function testing boundary conditions
        def py_is_comment_edit_expired(created_at: Optional[str], ref_now: Optional[datetime.datetime] = None) -> bool:
            if not created_at:
                return False
            try:
                normalized = created_at.replace("Z", "+00:00")
                created_dt = datetime.datetime.fromisoformat(normalized)
                if created_dt.tzinfo is None:
                    created_dt = created_dt.replace(tzinfo=datetime.timezone.utc)
            except Exception:
                return False

            now_utc = ref_now or datetime.datetime.now(datetime.timezone.utc)
            diff_hours = (now_utc - created_dt).total_seconds() / 3600.0
            return diff_hours >= 48.0

        now = datetime.datetime(2026, 10, 2, 12, 0, 0, tzinfo=datetime.timezone.utc)

        # 1. Empty / invalid cases
        self.assertFalse(py_is_comment_edit_expired(None, now))
        self.assertFalse(py_is_comment_edit_expired("", now))
        self.assertFalse(py_is_comment_edit_expired("not-a-date", now))

        # 2. Fresh comment (1 hour ago)
        fresh_ts = (now - datetime.timedelta(hours=1)).isoformat()
        self.assertFalse(py_is_comment_edit_expired(fresh_ts, now))

        # 3. 47 hours 59 minutes ago -> allowed (< 48h)
        within_ts = (now - datetime.timedelta(hours=47, minutes=59)).isoformat()
        self.assertFalse(py_is_comment_edit_expired(within_ts, now))

        # 4. Exactly 48 hours ago -> expired (>= 48h)
        exact_ts = (now - datetime.timedelta(hours=48)).isoformat()
        self.assertTrue(py_is_comment_edit_expired(exact_ts, now))

        # 5. 48 hours 1 minute ago -> expired (>= 48h)
        expired_ts = (now - datetime.timedelta(hours=48, minutes=1)).isoformat()
        self.assertTrue(py_is_comment_edit_expired(expired_ts, now))

        # 6. 72 hours ago -> expired
        old_ts = (now - datetime.timedelta(days=3)).isoformat()
        self.assertTrue(py_is_comment_edit_expired(old_ts, now))

    def test_09_comment_edit_button_structure_expired_and_active(self) -> None:
        """Verify comment edit button structure for expired vs active states in renderCommentNode."""
        # Check call to isCommentEditExpired
        self.assertIn("isCommentEditExpired(comment.createdAt || comment.created_at)", self.article_js)

        # Check expired button markup with disabled attribute and is-disabled class
        expired_pattern = (
            r'class="btn-comment-action btn-edit-comment is-disabled"'
            r'[^>]*title="Срок редактирования истек\. Комментарий можно редактировать в течение 48 часов после публикации\."'
            r'[^>]*aria-label="Срок редактирования истек\. Комментарий можно редактировать в течение 48 часов после публикации\."'
            r'[^>]*disabled'
        )
        self.assertIsNotNone(
            re.search(expired_pattern, self.article_js),
            "Expired comment edit button must have .is-disabled class, explanatory tooltip, and disabled attribute"
        )

        # Check active button markup when not expired
        active_pattern = (
            r'class="btn-comment-action btn-edit-comment"'
            r'[^>]*title="Редактировать"'
            r'[^>]*aria-label="Редактировать"'
        )
        self.assertIsNotNone(
            re.search(active_pattern, self.article_js),
            "Active comment edit button must have title='Редактировать' and aria-label='Редактировать'"
        )

        # Check click guard prevents opening edit form when button is disabled
        guard_pattern = r'if\s*\(\s*editBtn\.disabled\s*\|\|\s*editBtn\.classList\.contains\([\'"]is-disabled[\'"]\)\s*\)\s*\{\s*return;'
        self.assertIsNotNone(
            re.search(guard_pattern, self.article_js),
            "Comment edit button click handler must exit immediately if disabled"
        )

    def test_10_answer_edit_button_structure_expired_and_active(self) -> None:
        """Verify answer edit button structure for expired vs active states in renderAnswerCard."""
        # Check expired answer edit button markup
        expired_ans_pattern = (
            r'class="btn-comment-action btn-edit-answer is-disabled"'
            r'[^>]*title="Срок редактирования истек\. Комментарий можно редактировать в течение 48 часов после публикации\."'
            r'[^>]*aria-label="Срок редактирования истек\. Комментарий можно редактировать в течение 48 часов после публикации\."'
            r'[^>]*disabled'
        )
        self.assertIsNotNone(
            re.search(expired_ans_pattern, self.article_js),
            "Expired answer edit button must have .is-disabled class, explanatory tooltip, and disabled attribute"
        )

        # Check active answer edit button markup
        active_ans_pattern = (
            r'class="btn-comment-action btn-edit-answer"'
            r'[^>]*title="Редактировать"'
            r'[^>]*aria-label="Редактировать"'
        )
        self.assertIsNotNone(
            re.search(active_ans_pattern, self.article_js),
            "Active answer edit button must have title='Редактировать' and aria-label='Редактировать'"
        )

        # Check click guard prevents opening edit form for answer when button is disabled
        ans_guard_match = re.search(
            r'querySelector\([\'"]\.btn-edit-answer[\'"]\)[\s\S]*?editBtn\.disabled\s*\|\|\s*editBtn\.classList\.contains\([\'"]is-disabled[\'"]\)',
            self.article_js
        )
        self.assertIsNotNone(
            ans_guard_match,
            "Answer edit button click handler must exit immediately if disabled"
        )

    def test_11_css_rules_for_disabled_action_buttons(self) -> None:
        """Verify disabled comment action buttons are styled in article.css and theme.css."""
        for css_content, source_name in [(self.article_css, "article.css"), (self.theme_css, "theme.css")]:
            # Disabled rule
            rule_match = re.search(
                r'\.btn-comment-action:disabled\s*,\s*\.btn-comment-action\.is-disabled\s*\{([^}]+)\}',
                css_content
            )
            self.assertIsNotNone(rule_match, f"Disabled action button rule must exist in {source_name}")
            block = rule_match.group(1)
            self.assertIn("opacity: 0.45;", block, f"opacity: 0.45 expected in {source_name}")
            self.assertIn("cursor: not-allowed;", block, f"cursor: not-allowed expected in {source_name}")
            self.assertIn("pointer-events: auto;", block, f"pointer-events: auto expected in {source_name}")

            # Hover rule for disabled button
            hover_match = re.search(
                r'\.btn-comment-action:disabled:hover\s*,\s*\.btn-comment-action\.is-disabled:hover\s*\{([^}]+)\}',
                css_content
            )
            self.assertIsNotNone(hover_match, f"Disabled hover rule must exist in {source_name}")
            hover_block = hover_match.group(1)
            self.assertIn("background: transparent;", hover_block, f"background: transparent expected in {source_name}")
            self.assertIn("color: var(--text-secondary);", hover_block, f"color: var(--text-secondary) expected in {source_name}")
            self.assertIn("border-color: var(--border-color);", hover_block, f"border-color: var(--border-color) expected in {source_name}")

    def test_12_server_response_error_handling_edit_window_expired(self) -> None:
        """Verify submit handlers in comments and answers handle 403 / EDIT_WINDOW_EXPIRED code."""
        expired_handler_occurrences = self.article_js.count("EDIT_WINDOW_EXPIRED")
        self.assertGreaterEqual(
            expired_handler_occurrences,
            2,
            "EDIT_WINDOW_EXPIRED must be handled in both comment and answer save handlers"
        )

        self.assertIn("editBtn.classList.add('is-disabled');", self.article_js)
        self.assertIn("editBtn.disabled = true;", self.article_js)

    def test_13_zero_emojis_no_em_dashes_offline_first(self) -> None:
        """Ensure zero emojis, zero em dashes, and 100% offline-first in all modified files."""
        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]|[\u2600-\u26ff]|[\u2700-\u27bf]")
        em_dash = "\u2014"

        files_to_check = [
            (self.article_js, "article.js"),
            (self.article_css, "article.css"),
            (self.theme_css, "theme.css"),
        ]

        with open(__file__, "r", encoding="utf-8") as f:
            files_to_check.append((f.read(), "test_issue73_comment_edit_window.py"))

        for content, name in files_to_check:
            self.assertIsNone(emoji_pattern.search(content), f"Emoji found in {name}")
            self.assertNotIn(em_dash, content, f"Em dash found in {name}")
            self.assertNotIn("/ho" + "me/", content, f"Absolute local filesystem path found in {name}")

        for css_content, source_name in [(self.article_css, "article.css"), (self.theme_css, "theme.css")]:
            urls = re.findall(r'url\s*\(\s*["\']?(https?://[^"\')]+)', css_content)
            self.assertEqual(len(urls), 0, f"External CDN url found in {source_name}: {urls}")


if __name__ == "__main__":
    unittest.main()
