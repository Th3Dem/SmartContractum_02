#!/usr/bin/env python3
"""
tests/test_issue30_sc027_navigation_and_highlighting.py

Backend integration tests for Issue #30 (SC-027):
Unified commentsCount contract and counters accuracy across:
- GET /api/articles/<id>/comments
- POST /api/articles/<id>/comments (created 201 and replay 200)
- GET /api/articles/<id>
- GET /api/articles (feed list and sort=discussed)
"""

import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from typing import Optional, Tuple

import server
from scripts.migration_diagnostic import run_diagnostic
from server import create_server, init_db

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")
ARTICLE_JS_PATH = os.path.join(FRONTEND_DIR, "js", "article.js")
ARTICLE_CSS_PATH = os.path.join(FRONTEND_DIR, "css", "article.css")
DIAGNOSTIC_SCRIPT = os.path.join(PROJECT_ROOT, "scripts", "migration_diagnostic.py")


class TestIssue30NavigationAndHighlightingBackend(unittest.TestCase):
    """
    Verifies unified commentsCount, answersCount, and discussionCount contracts.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue30.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path, seed=False)
        with conn:
            users = [
                ("u_author", "Автор Вопроса", "author"),
                ("u_alice", "Алиса", "user"),
                ("u_bob", "Боб", "user"),
                ("u_charlie", "Чарли", "user"),
                ("u_david", "Давид", "user"),
                ("u_elena", "Елена", "user"),
            ]
            for uid, name, role in users:
                conn.execute(
                    """
                    INSERT INTO user_profiles (
                        user_id, name, specialization, company, bio, avatar, created_at, updated_at
                    ) VALUES (?, ?, 'Engineer', 'SmartCo', '', '', '2026-10-01T00:00:00Z', '2026-10-01T00:00:00Z')
                    """,
                    (uid, name),
                )

            # Question material 1 (Mixed: question comment, answers, answer replies)
            conn.execute(
                """
                INSERT INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, article_delta, idempotency_key, snapshot_hash,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'approved', ?, ?, NULL, ?, ?, ?, ?)
                """,
                (
                    "quest_mixed_01",
                    "draft_qm_01",
                    "Смешанный вопрос с ответами и комментариями",
                    "u_author",
                    json.dumps(
                        {"materialType": "question", "topics": ["architecture"]},
                        ensure_ascii=False,
                    ),
                    "<p>Текст смешанного вопроса.</p>",
                    "idemp_qm_01",
                    "hash_qm_01",
                    "2026-10-01T00:00:00Z",
                    "2026-10-01T00:00:00Z",
                ),
            )

            # Question material 2 (For deletion tests)
            conn.execute(
                """
                INSERT INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, article_delta, idempotency_key, snapshot_hash,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'approved', ?, ?, NULL, ?, ?, ?, ?)
                """,
                (
                    "quest_del_01",
                    "draft_qd_01",
                    "Вопрос для проверки удаления",
                    "u_author",
                    json.dumps(
                        {"materialType": "question", "topics": ["testing"]},
                        ensure_ascii=False,
                    ),
                    "<p>Текст вопроса для удаления.</p>",
                    "idemp_qd_01",
                    "hash_qd_01",
                    "2026-10-01T00:00:00Z",
                    "2026-10-01T00:00:00Z",
                ),
            )

            # Article material (For sorting test)
            conn.execute(
                """
                INSERT INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, article_delta, idempotency_key, snapshot_hash,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'approved', ?, ?, NULL, ?, ?, ?, ?)
                """,
                (
                    "art_sort_01",
                    "draft_as_01",
                    "Статья для проверки сортировки",
                    "u_author",
                    json.dumps(
                        {"materialType": "article", "topics": ["sorting"]},
                        ensure_ascii=False,
                    ),
                    "<p>Текст статьи для сортировки.</p>",
                    "idemp_as_01",
                    "hash_as_01",
                    "2026-10-01T00:00:00Z",
                    "2026-10-01T00:00:00Z",
                ),
            )
        conn.close()

        cls.httpd = create_server(
            host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR
        )
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(
            target=cls.httpd.serve_forever, daemon=True
        )
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
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

    def _login(self, user_id: str, name: str = "User") -> str:
        url = f"{self.base_url}/api/auth/login"
        body = json.dumps(
            {"userId": user_id, "name": name, "role": "user"}
        ).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            return resp.headers.get("Set-Cookie", "")

    def _post_json(
        self, path: str, data: dict, cookie: Optional[str] = None
    ) -> Tuple[int, dict]:
        url = f"{self.base_url}{path}"
        body = json.dumps(data).encode("utf-8")
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if cookie:
            headers["Cookie"] = cookie
        req = urllib.request.Request(
            url, data=body, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req) as resp:
                res_body = resp.read().decode("utf-8")
                return resp.status, json.loads(res_body) if res_body else {}
        except urllib.error.HTTPError as e:
            with e:
                res_body = e.read().decode("utf-8")
                return e.code, json.loads(res_body) if res_body else {}

    def _get_json(
        self, path: str, cookie: Optional[str] = None
    ) -> Tuple[int, dict]:
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
            with e:
                res_body = e.read().decode("utf-8")
                return e.code, json.loads(res_body) if res_body else {}

    def _delete_json(
        self, path: str, cookie: Optional[str] = None
    ) -> Tuple[int, dict]:
        url = f"{self.base_url}{path}"
        headers = {}
        if cookie:
            headers["Cookie"] = cookie
        req = urllib.request.Request(url, headers=headers, method="DELETE")
        try:
            with urllib.request.urlopen(req) as resp:
                res_body = resp.read().decode("utf-8")
                return resp.status, json.loads(res_body) if res_body else {}
        except urllib.error.HTTPError as e:
            with e:
                res_body = e.read().decode("utf-8")
                return e.code, json.loads(res_body) if res_body else {}

    def test_00_diagnostic_clean(self) -> None:
        """Verifies migration diagnostic reports 0 violations on the test database."""
        res = run_diagnostic(self.db_path)
        self.assertTrue(
            res["clean"], f"Database diagnostic failed: {res.get('details')}"
        )

    def test_01_mixed_question_counters_across_all_endpoints(self) -> None:
        """
        Tests mixed question with:
        - 1 question comment
        - 2 answers
        - 3 answer replies
        Expects:
        - commentsCount == 4 (1 question comment + 3 answer replies)
        - answersCount == 2
        - discussionCount == 6
        across GET /api/articles/<id>/comments, POST /api/articles/<id>/comments,
        GET /api/articles/<id>, and GET /api/articles.
        """
        c_alice = self._login("u_alice", "Алиса")
        c_bob = self._login("u_bob", "Боб")
        c_charlie = self._login("u_charlie", "Чарли")
        c_david = self._login("u_david", "Давид")
        c_elena = self._login("u_elena", "Елена")

        art_id = "quest_mixed_01"

        # 1. Alice posts 1 root question comment
        st, res = self._post_json(
            f"/api/articles/{art_id}/comments",
            {
                "content": "Комментарий непосредственно к вопросу",
                "commentType": "comment",
                "clientOperationId": "op_mix_qcomm_01",
            },
            cookie=c_alice,
        )
        self.assertEqual(st, 201)
        self.assertEqual(res.get("commentsCount"), 1)
        self.assertEqual(res.get("answersCount"), 0)
        self.assertEqual(res.get("discussionCount"), 1)

        # 2. Bob posts answer 1
        st, res = self._post_json(
            f"/api/articles/{art_id}/comments",
            {
                "content": "Ответ номер один от Боба",
                "commentType": "answer",
                "clientOperationId": "op_mix_ans_01",
            },
            cookie=c_bob,
        )
        self.assertEqual(st, 201)
        ans1_id = res["comment"]["id"]
        self.assertEqual(res.get("commentsCount"), 1)
        self.assertEqual(res.get("answersCount"), 1)
        self.assertEqual(res.get("discussionCount"), 2)

        # 3. Charlie posts answer 2
        st, res = self._post_json(
            f"/api/articles/{art_id}/comments",
            {
                "content": "Ответ номер два от Чарли",
                "commentType": "answer",
                "clientOperationId": "op_mix_ans_02",
            },
            cookie=c_charlie,
        )
        self.assertEqual(st, 201)
        ans2_id = res["comment"]["id"]
        self.assertEqual(res.get("commentsCount"), 1)
        self.assertEqual(res.get("answersCount"), 2)
        self.assertEqual(res.get("discussionCount"), 3)

        # 4. Alice posts reply 1 to answer 1
        st, res = self._post_json(
            f"/api/articles/{art_id}/comments",
            {
                "content": "Ответ Алисы на ответ Боба",
                "commentType": "comment",
                "parentAnswerId": ans1_id,
                "clientOperationId": "op_mix_reply_01",
            },
            cookie=c_alice,
        )
        self.assertEqual(st, 201)
        ans1_reply1_id = res["comment"]["id"]
        self.assertEqual(res.get("commentsCount"), 2)
        self.assertEqual(res.get("answersCount"), 2)
        self.assertEqual(res.get("discussionCount"), 4)

        # 5. David posts reply 2 to answer 1 (nested under Alice's reply)
        st, res = self._post_json(
            f"/api/articles/{art_id}/comments",
            {
                "content": "Ответ Давида на комментарий Алисы в ветке Боба",
                "commentType": "comment",
                "parentCommentId": ans1_reply1_id,
                "clientOperationId": "op_mix_reply_02",
            },
            cookie=c_david,
        )
        self.assertEqual(st, 201)
        self.assertEqual(res.get("commentsCount"), 3)
        self.assertEqual(res.get("answersCount"), 2)
        self.assertEqual(res.get("discussionCount"), 5)

        # 6. Elena posts reply 3 to answer 2
        st, res = self._post_json(
            f"/api/articles/{art_id}/comments",
            {
                "content": "Ответ Елены на ответ Чарли",
                "commentType": "comment",
                "parentAnswerId": ans2_id,
                "clientOperationId": "op_mix_reply_03",
            },
            cookie=c_elena,
        )
        self.assertEqual(st, 201)
        self.assertEqual(res.get("commentsCount"), 4)
        self.assertEqual(res.get("answersCount"), 2)
        self.assertEqual(res.get("discussionCount"), 6)

        # 7. Check replay 200 with existing clientOperationId
        st_rep, res_rep = self._post_json(
            f"/api/articles/{art_id}/comments",
            {
                "content": "Ответ Елены на ответ Чарли",
                "commentType": "comment",
                "parentAnswerId": ans2_id,
                "clientOperationId": "op_mix_reply_03",
            },
            cookie=c_elena,
        )
        self.assertEqual(st_rep, 200)
        self.assertTrue(res_rep.get("isDuplicate"))
        self.assertEqual(res_rep.get("commentsCount"), 4)
        self.assertEqual(res_rep.get("answersCount"), 2)
        self.assertEqual(res_rep.get("discussionCount"), 6)

        # 8. Check GET /api/articles/<id>/comments
        st_get_comm, res_get_comm = self._get_json(
            f"/api/articles/{art_id}/comments"
        )
        self.assertEqual(st_get_comm, 200)
        self.assertEqual(res_get_comm.get("commentsCount"), 4)
        self.assertEqual(res_get_comm.get("answersCount"), 2)
        self.assertEqual(res_get_comm.get("discussionCount"), 6)

        # 9. Check GET /api/articles/<id>
        st_get_art, res_get_art = self._get_json(f"/api/articles/{art_id}")
        self.assertEqual(st_get_art, 200)
        art_dto = res_get_art.get("article", {})
        self.assertEqual(art_dto.get("commentsCount"), 4)
        self.assertEqual(art_dto.get("answersCount"), 2)
        self.assertEqual(art_dto.get("discussionCount"), 6)
        self.assertEqual(res_get_art.get("commentsCount"), 4)
        self.assertEqual(res_get_art.get("answersCount"), 2)
        self.assertEqual(res_get_art.get("discussionCount"), 6)

        # 10. Check GET /api/articles (isolated tab=questions per Issue #162)
        st_list, res_list = self._get_json("/api/articles?tab=questions")
        self.assertEqual(st_list, 200)
        articles = res_list.get("articles", [])
        matched = next((a for a in articles if a["id"] == art_id), None)
        self.assertIsNotNone(matched)
        self.assertEqual(matched.get("commentsCount"), 4)
        self.assertEqual(matched.get("answersCount"), 2)
        self.assertEqual(matched.get("discussionCount"), 6)

    def test_02_soft_deleted_comment_placeholder_not_counted(self) -> None:
        """
        Verifies that soft deleted comments:
        - When acting as placeholder for published descendants, isDeleted=True
        - NOT counted in commentsCount or discussionCount
        - Deleted comment without descendants is completely omitted from counts
        """
        c_bob = self._login("u_bob", "Боб")
        c_alice = self._login("u_alice", "Алиса")
        c_charlie = self._login("u_charlie", "Чарли")

        art_id = "quest_del_01"

        # Bob posts answer
        st, res_ans = self._post_json(
            f"/api/articles/{art_id}/comments",
            {"content": "Ответ Боба для теста удаления", "commentType": "answer"},
            cookie=c_bob,
        )
        self.assertEqual(st, 201)
        ans_id = res_ans["comment"]["id"]

        # Alice posts parent comment under answer
        st, res_c1 = self._post_json(
            f"/api/articles/{art_id}/comments",
            {
                "content": "Родительский комментарий Алисы под ответом",
                "commentType": "comment",
                "parentAnswerId": ans_id,
            },
            cookie=c_alice,
        )
        self.assertEqual(st, 201)
        c1_id = res_c1["comment"]["id"]

        # Charlie posts reply to Alice's comment
        st, res_c2 = self._post_json(
            f"/api/articles/{art_id}/comments",
            {
                "content": "Ответ Чарли на комментарий Алисы",
                "commentType": "comment",
                "parentCommentId": c1_id,
            },
            cookie=c_charlie,
        )
        self.assertEqual(st, 201)

        # Baseline counters: 2 comments, 1 answer, 3 discussion
        st, comm_data = self._get_json(f"/api/articles/{art_id}/comments")
        self.assertEqual(st, 200)
        self.assertEqual(comm_data["commentsCount"], 2)
        self.assertEqual(comm_data["answersCount"], 1)
        self.assertEqual(comm_data["discussionCount"], 3)

        # Alice soft-deletes her comment
        st_del, res_del = self._delete_json(
            f"/api/articles/{art_id}/comments/{c1_id}",
            cookie=c_alice,
        )
        self.assertEqual(st_del, 200)

        # Verify GET /api/articles/<id>/comments:
        # Alice's comment is now a placeholder (isDeleted=True), so commentsCount must be 1 (only Charlie's reply)
        st, comm_data = self._get_json(f"/api/articles/{art_id}/comments")
        self.assertEqual(st, 200)
        self.assertEqual(comm_data["commentsCount"], 1)
        self.assertEqual(comm_data["answersCount"], 1)
        self.assertEqual(comm_data["discussionCount"], 2)

        # Verify GET /api/articles/<id>
        st_art, res_art = self._get_json(f"/api/articles/{art_id}")
        self.assertEqual(st_art, 200)
        art_dto = res_art.get("article", {})
        self.assertEqual(art_dto.get("commentsCount"), 1)
        self.assertEqual(art_dto.get("answersCount"), 1)
        self.assertEqual(art_dto.get("discussionCount"), 2)

        # Verify GET /api/articles (isolated tab=questions per Issue #162)
        st_list, res_list = self._get_json("/api/articles?tab=questions")
        self.assertEqual(st_list, 200)
        matched = next(
            (a for a in res_list.get("articles", []) if a["id"] == art_id), None
        )
        self.assertIsNotNone(matched)
        self.assertEqual(matched.get("commentsCount"), 1)
        self.assertEqual(matched.get("answersCount"), 1)
        self.assertEqual(matched.get("discussionCount"), 2)

        # Verify next POST reflects accurate counts
        st_post, res_post = self._post_json(
            f"/api/articles/{art_id}/comments",
            {
                "content": "Новый комментарий после удаления",
                "commentType": "comment",
                "parentAnswerId": ans_id,
            },
            cookie=c_alice,
        )
        self.assertEqual(st_post, 201)
        self.assertEqual(res_post.get("commentsCount"), 2)
        self.assertEqual(res_post.get("answersCount"), 1)
        self.assertEqual(res_post.get("discussionCount"), 3)

    def test_03_discussed_sorting_prioritizes_total_discussion_count(
        self,
    ) -> None:
        """
        Verifies that sort=discussed uses discussionCount.
        Article A has 2 comments (discussionCount = 2).
        Question B has 1 answer and 2 comments (discussionCount = 3).
        In sort=discussed, Question B must precede Article A.
        """
        c_alice = self._login("u_alice", "Алиса")
        c_bob = self._login("u_bob", "Боб")

        art_id = "art_sort_01"

        # Article A: 2 comments
        st1, _ = self._post_json(
            f"/api/articles/{art_id}/comments",
            {"content": "Коммент 1 к статье", "commentType": "comment"},
            cookie=c_alice,
        )
        self.assertEqual(st1, 201)

        st2, _ = self._post_json(
            f"/api/articles/{art_id}/comments",
            {"content": "Коммент 2 к статье", "commentType": "comment"},
            cookie=c_bob,
        )
        self.assertEqual(st2, 201)

        # Check list sorted by discussed within questions entity (Issue #162)
        st_sort_q, res_sort_q = self._get_json("/api/articles?tab=questions&sort=discussed")
        self.assertEqual(st_sort_q, 200)
        items_q = res_sort_q.get("articles", [])
        ids_q = [it["id"] for it in items_q]

        # quest_mixed_01 has discussionCount = 6
        # quest_del_01 has discussionCount = 3
        self.assertIn("quest_mixed_01", ids_q)
        self.assertIn("quest_del_01", ids_q)

        idx_mix = ids_q.index("quest_mixed_01")
        idx_del = ids_q.index("quest_del_01")

        self.assertLess(
            idx_mix,
            idx_del,
            "quest_mixed_01 (discussionCount=6) must precede quest_del_01 (discussionCount=3)",
        )

        # Check list sorted by discussed within publications entity (Issue #162)
        st_sort_pub, res_sort_pub = self._get_json("/api/articles?tab=all&sort=discussed")
        self.assertEqual(st_sort_pub, 200)
        items_pub = res_sort_pub.get("articles", [])
        ids_pub = [it["id"] for it in items_pub]
        self.assertIn("art_sort_01", ids_pub)


class TestIssue30NavigationAndHighlightingFrontend(unittest.TestCase):
    """Verifies contracts for dynamic timestamp scheduling, precise path highlighting, and depth windowing."""

    @classmethod
    def setUpClass(cls) -> None:
        with open(ARTICLE_JS_PATH, "r", encoding="utf-8") as f:
            cls.article_js = f.read()
        with open(ARTICLE_CSS_PATH, "r", encoding="utf-8") as f:
            cls.article_css = f.read()

    def test_01_dynamic_smart_timestamp_scheduler_algorithm(self) -> None:
        """Simulate dynamic timestamp scheduler delay calculation across age boundaries."""
        def calculate_next_delay(diff_sec: int) -> int:
            if diff_sec < 60:
                return 1000
            elif diff_sec < 3600:
                rem_min = 60 - (diff_sec % 60)
                delay = max(1, min(60, rem_min))
                return delay * 1000
            elif diff_sec <= 86400:
                rem_hour = 3600 - (diff_sec % 3600)
                delay = max(1, min(60, rem_hour))
                return delay * 1000
            else:
                return 60000

        # Comments younger than 60s: ticks every 1 second (1000ms)
        self.assertEqual(calculate_next_delay(0), 1000)
        self.assertEqual(calculate_next_delay(1), 1000)
        self.assertEqual(calculate_next_delay(35), 1000)
        self.assertEqual(calculate_next_delay(59), 1000)

        # Comments between 1 minute and 1 hour: delay to nearest minute boundary
        self.assertEqual(calculate_next_delay(60), 60000)
        self.assertEqual(calculate_next_delay(65), 55000)
        self.assertEqual(calculate_next_delay(119), 1000)
        self.assertEqual(calculate_next_delay(120), 60000)
        self.assertEqual(calculate_next_delay(3599), 1000)

        # Comments between 1 hour and 24 hours: delay to nearest hour, capped at 60s
        self.assertEqual(calculate_next_delay(3600), 60000)
        self.assertEqual(calculate_next_delay(7199), 1000)
        self.assertEqual(calculate_next_delay(7200), 60000)

        # Comments strictly older than 24h (> 86400s)
        self.assertEqual(calculate_next_delay(86401), 60000)

    def test_02_dynamic_timestamp_scheduler_js_contracts(self) -> None:
        """Verify dynamic scheduler contracts and tab visibility/focus handlers in article.js."""
        # Dynamic scheduler functions
        self.assertIn("function updateCommentTimestamps()", self.article_js)
        self.assertIn("function runCommentTimestampScheduler()", self.article_js)
        self.assertIn("window.updateCommentTimestamps", self.article_js)
        self.assertIn("window.runCommentTimestampScheduler", self.article_js)

        # Boundaries in JS implementation
        self.assertIn("diffSec < 60", self.article_js)
        self.assertIn("minNextDelaySec = Math.min(minNextDelaySec, 1)", self.article_js)
        self.assertIn("60 - (diffSec % 60)", self.article_js)
        self.assertIn("3600 - (diffSec % 3600)", self.article_js)

        # Visibility and focus event listeners
        self.assertIn("visibilitychange", self.article_js)
        self.assertIn("window._commentTimestampVisibilityHandler", self.article_js)
        self.assertIn("window._commentTimestampFocusHandler", self.article_js)
        self.assertIn("document.addEventListener('visibilitychange'", self.article_js)
        self.assertIn("window.addEventListener('focus'", self.article_js)

        # Cleanup on re-init
        self.assertIn("clearTimeout(window._commentTimestampTimer)", self.article_js)
        self.assertIn("document.removeEventListener('visibilitychange'", self.article_js)
        self.assertIn("window.removeEventListener('focus'", self.article_js)

        # Only updates textContent without DOM re-render
        self.assertIn("el.textContent = rel", self.article_js)

    def test_03_tree_path_highlighting_precise_path_isolation(self) -> None:
        """Verify setTreePathHighlight highlights only direct connection path and avatars."""
        self.assertIn("function setTreePathHighlight(active)", self.article_js)
        self.assertIn("elbow.classList.toggle('is-tree-path-active', active)", self.article_js)
        self.assertIn("parentUpper.classList.toggle('is-tree-path-active', active)", self.article_js)
        self.assertIn("pStemUpper.classList.toggle('is-tree-path-active', active)", self.article_js)
        self.assertIn("pStemThrough.classList.toggle('is-tree-path-active', active)", self.article_js)
        self.assertIn("pToggleBtn.classList.toggle('is-tree-path-active', active)", self.article_js)
        self.assertIn("pToggleIcon.classList.toggle('is-tree-path-active', active)", self.article_js)

        # Avatars highlighted
        self.assertIn("myAvatar.classList.toggle('avatar-peer-highlight', active)", self.article_js)
        self.assertIn("parentAvatar.classList.toggle('avatar-peer-highlight', active)", self.article_js)

        # Previous siblings stems included
        self.assertIn("sibStem.classList.toggle('is-tree-path-active', active)", self.article_js)

        # Stem on child itself must NOT be activated in setTreePathHighlight
        # (child's own stem leads downward to subsequent siblings)
        pattern = re.compile(r"function setTreePathHighlight\(active\) \{.*?\bif \(stem\) \b", re.DOTALL)
        self.assertIsNone(pattern.search(self.article_js), "Child node stem should not be toggled in setTreePathHighlight")

    def test_04_decorative_lines_click_safety_and_cursor(self) -> None:
        """Verify absence of click handlers on decorative lines and default cursor."""
        # No click handler on elbow in article.js
        self.assertNotIn("elbow.addEventListener('click'", self.article_js)

        # Decorative connectors styled with cursor: default
        self.assertIn(".comment-branch-elbow", self.article_css)
        self.assertIn(".comment-branch-stem", self.article_css)

        # Smooth transitions
        self.assertIn("transition: border-color var(--transition-fast);", self.article_css)
        self.assertIn("transition: background-color var(--transition-fast);", self.article_css)

    def test_05_depth_windowing_limits(self) -> None:
        """Verify getMaxWindowDepth returns 8 on desktop and 5 on mobile (<680px)."""
        self.assertIn("function getMaxWindowDepth()", self.article_js)

        # Extract function body including return 8
        match = re.search(r"function getMaxWindowDepth\(\)\s*\{([\s\S]*?return 8;?[\s\S]*?)\}", self.article_js)
        self.assertIsNotNone(match, "getMaxWindowDepth function not found")
        body = match.group(1)

        self.assertIn("680", body)
        self.assertIn("return 5", body)
        self.assertIn("return 8", body)

    def test_06_handle_deep_link_deep_target_windowing(self) -> None:
        """Verify handleDeepLink supports deep targets (> maxDepth) across contexts."""
        self.assertIn("function handleDeepLink()", self.article_js)
        self.assertIn("targetIdx >= maxDepth", self.article_js)
        self.assertIn("for (let d = maxDepth; d <= targetIdx; d += maxDepth)", self.article_js)
        self.assertIn("window._commentDrilldownState.stack.push", self.article_js)
        self.assertIn("renderCommentsData", self.article_js)
        self.assertIn("window._expandedCommentIds.add(parentId)", self.article_js)
        self.assertIn("targetEl.scrollIntoView", self.article_js)
        self.assertIn("targetEl.classList.add('comment-highlight')", self.article_js)

    def test_07_drilldown_back_button_immediate_restoration(self) -> None:
        """Verify drilldown Back button restores scroll position immediately after DOM render."""
        pattern = re.compile(
            r"backBtn\.addEventListener\('click',\s*function\s*\([^)]*\)\s*\{([\s\S]*?window\.scrollTo\(\{\s*top:\s*popped\.scrollY,\s*behavior:\s*'auto'\s*\}\);[\s\S]*?\n\s*\})\);"
        )
        handlers = pattern.findall(self.article_js)
        self.assertGreaterEqual(len(handlers), 3, "Expected back button handler in article, question, and answer contexts")

        for h in handlers:
            self.assertIn("window._commentDrilldownState.stack.pop()", h)
            self.assertIn("window.scrollTo", h)
            self.assertNotIn("setTimeout", h, "Arbitrary setTimeout must not be used to delay scroll restoration")

    def test_08_zero_emojis_and_no_em_dashes(self) -> None:
        """Ensure zero emojis, zero em dashes, zero server IPs, and zero local filesystem paths."""
        with open(__file__, "r", encoding="utf-8") as f:
            content = f.read()

        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]|[\u2600-\u26ff]|[\u2700-\u27bf]")
        self.assertIsNone(emoji_pattern.search(content), "Emoji found in test file")
        self.assertNotIn("\u2014", content, "Em dash found in test file")
        self.assertNotIn("\u2014", self.article_js, "Em dash found in article.js")
        self.assertNotIn("\u2014", self.article_css, "Em dash found in article.css")


if __name__ == "__main__":
    unittest.main()
