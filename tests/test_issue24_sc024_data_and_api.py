#!/usr/bin/env python3
"""
tests/test_issue24_sc024_data_and_api.py

Regression test suite for Issue #24 (SC-024.1):
"Схема данных, атомарные инварианты, API ответов и обсуждений, транзакционные уведомления".

Coverage:
- test_01_create_answer_and_prevent_duplicate_409
- test_02_create_comments_and_parent_validation_400
- test_03_put_update_answer_concurrency_409_and_auth_403
- test_04_solution_mark_atomic_and_auth_403_admin_forbidden
- test_05_structured_comments_get_and_profile_counters
"""

import datetime
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
from typing import Optional, Tuple

import server
from server import create_server, init_db

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue24DataAndApi(unittest.TestCase):
    """Test suite for Q&A data schema, atomic invariants, and discussion API."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue24.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path)
        conn.close()

        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR)
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

    def _post_json(self, path: str, data: dict, cookie: Optional[str] = None) -> Tuple[int, dict]:
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
            with e:
                res_body = e.read().decode("utf-8")
                return e.code, json.loads(res_body) if res_body else {}

    def _put_json(self, path: str, data: dict, cookie: Optional[str] = None) -> Tuple[int, dict]:
        url = f"{self.base_url}{path}"
        body = json.dumps(data).encode("utf-8")
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if cookie:
            headers["Cookie"] = cookie
        req = urllib.request.Request(url, data=body, headers=headers, method="PUT")
        try:
            with urllib.request.urlopen(req) as resp:
                res_body = resp.read().decode("utf-8")
                return resp.status, json.loads(res_body) if res_body else {}
        except urllib.error.HTTPError as e:
            with e:
                res_body = e.read().decode("utf-8")
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
            with e:
                res_body = e.read().decode("utf-8")
                return e.code, json.loads(res_body) if res_body else {}

    def _create_publication(self, pub_id: str, author_id: str, material_type: str, title: str) -> str:
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        settings = {
            "materialType": material_type,
            "type": material_type,
            "topics": ["Разработка"],
            "description": f"Описание для {title}"
        }
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO moderation_submissions (
                    id, draft_id, author_id, title, article_html, article_delta,
                    publication_settings, snapshot_hash, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'hash_dummy', 'approved', ?, ?)
            """, (
                pub_id, f"draft_{pub_id}", author_id, title,
                f"<p>Тело публикации {title}</p>",
                json.dumps({"ops": [{"insert": f"Тело {title}\n"}]}),
                json.dumps(settings),
                now_iso, now_iso
            ))
            conn.execute("""
                INSERT OR IGNORE INTO user_profiles (user_id, name, specialization, created_at, updated_at)
                VALUES (?, ?, 'Инженер', ?, ?)
            """, (author_id, f"Автор {author_id}", now_iso, now_iso))
        conn.close()
        return pub_id

    def test_01_create_answer_and_prevent_duplicate_409(self):
        """
        Creates an answer to a question, validates 1 answer per user invariant (409),
        checks notification creation, and verifies commentType validation.
        """
        q_id = "test_q_01"
        art_id = "test_art_01"
        self._create_publication(q_id, "author_q1", "question", "Вопрос по архитектуре")
        self._create_publication(art_id, "author_art1", "article", "Обычная статья")

        cookie_ans = self._login("ans_user_1", "Отвечающий 1")

        # 1. Invalid commentType fails with 400
        status, res = self._post_json(f"/api/articles/{q_id}/comments", {
            "content": "Невалидный тип",
            "commentType": "wrong_type"
        }, cookie=cookie_ans)
        self.assertEqual(status, 400)
        self.assertFalse(res.get("success"))

        # 2. commentType='answer' on regular article fails with 400
        status, res = self._post_json(f"/api/articles/{art_id}/comments", {
            "content": "Ответ на статью",
            "commentType": "answer"
        }, cookie=cookie_ans)
        self.assertEqual(status, 400)
        self.assertFalse(res.get("success"))

        # 3. Create first answer successfully (201 Created)
        status, res = self._post_json(f"/api/articles/{q_id}/comments", {
            "content": "Первый подробный ответ на вопрос",
            "commentType": "answer"
        }, cookie=cookie_ans)
        self.assertEqual(status, 201)
        self.assertTrue(res.get("success"))
        comment = res.get("comment", {})
        ans_id = comment.get("id")
        self.assertTrue(ans_id)
        self.assertEqual(comment.get("commentType"), "answer")
        self.assertEqual(comment.get("revision"), 1)
        self.assertIsNone(comment.get("parentAnswerId"))

        # 4. Check new_answer notification for question author in DB
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            SELECT type, user_id, actor_id FROM user_notifications
            WHERE article_id = ? AND comment_id = ?
        """, (q_id, ans_id))
        notif = cur.fetchone()
        conn.close()
        self.assertIsNotNone(notif)
        self.assertEqual(notif[0], "new_answer")
        self.assertEqual(notif[1], "author_q1")
        self.assertEqual(notif[2], "ans_user_1")

        # 5. Attempt second answer by the same user -> 409 Conflict with myAnswerId
        status_dup, res_dup = self._post_json(f"/api/articles/{q_id}/comments", {
            "content": "Попытка второго ответа от того же пользователя",
            "commentType": "answer"
        }, cookie=cookie_ans)
        self.assertEqual(status_dup, 409)
        self.assertFalse(res_dup.get("success"))
        self.assertEqual(res_dup.get("code"), "ANSWER_ALREADY_EXISTS")
        self.assertEqual(res_dup.get("myAnswerId"), ans_id)

    def test_02_create_comments_and_parent_validation_400(self):
        """
        Tests creating question clarifications and replies to answers,
        validating parent_answer_id checks (400) and notifications.
        """
        q_id = "test_q_02"
        self._create_publication(q_id, "author_q2", "question", "Вопрос о базах данных")

        cookie_ans = self._login("user_ans_2", "Отвечающий 2")
        cookie_comm = self._login("user_comm_2", "Комментатор 2")

        # Post an answer
        status, res = self._post_json(f"/api/articles/{q_id}/comments", {
            "content": "Ответ на вопрос о базах данных",
            "commentType": "answer"
        }, cookie=cookie_ans)
        self.assertEqual(status, 201)
        ans_id = res["comment"]["id"]

        # 1. Post top-level clarification comment to question (parentAnswerId is None)
        status, res = self._post_json(f"/api/articles/{q_id}/comments", {
            "content": "Уточнение к формулировке вопроса",
            "commentType": "comment"
        }, cookie=cookie_comm)
        self.assertEqual(status, 201)
        comm_clarif_id = res["comment"]["id"]
        self.assertEqual(res["comment"]["commentType"], "comment")
        self.assertIsNone(res["comment"].get("parentAnswerId"))

        # Verify new_reply notification sent to question author
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            SELECT user_id, type FROM user_notifications
            WHERE article_id = ? AND comment_id = ?
        """, (q_id, comm_clarif_id))
        notif = cur.fetchone()
        conn.close()
        self.assertIsNotNone(notif)
        self.assertEqual(notif[0], "author_q2")
        self.assertEqual(notif[1], "new_reply")

        # 2. Attempt reply to non-existent parentAnswerId -> 400 Bad Request
        status, res = self._post_json(f"/api/articles/{q_id}/comments", {
            "content": "Ответ на несуществующего родителя",
            "commentType": "comment",
            "parentAnswerId": "non_existent_answer_id"
        }, cookie=cookie_comm)
        self.assertEqual(status, 400)
        self.assertFalse(res.get("success"))

        # 3. Attempt reply where parentAnswerId points to a comment instead of an answer -> 400
        status, res = self._post_json(f"/api/articles/{q_id}/comments", {
            "content": "Попытка ответить на уточнение",
            "commentType": "comment",
            "parentAnswerId": comm_clarif_id
        }, cookie=cookie_comm)
        self.assertEqual(status, 400)
        self.assertFalse(res.get("success"))

        # 4. Valid reply to an answer -> 201 Created
        status, res = self._post_json(f"/api/articles/{q_id}/comments", {
            "content": "Комментарий к конкретному ответу",
            "commentType": "comment",
            "parentAnswerId": ans_id
        }, cookie=cookie_comm)
        self.assertEqual(status, 201)
        self.assertTrue(res.get("success"))
        comm_reply_id = res["comment"]["id"]
        self.assertEqual(res["comment"].get("parentAnswerId"), ans_id)

        # Verify new_reply notification sent to answer author
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            SELECT user_id, type FROM user_notifications
            WHERE article_id = ? AND comment_id = ?
        """, (q_id, comm_reply_id))
        notif = cur.fetchone()
        conn.close()
        self.assertIsNotNone(notif)
        self.assertEqual(notif[0], "user_ans_2")
        self.assertEqual(notif[1], "new_reply")

    def test_03_put_update_answer_concurrency_409_and_auth_403(self):
        """
        Tests updating answers via PUT:
        - Authentication and authorization checks (401, 403)
        - Validation of content and article matching (400)
        - Optimistic concurrency control via revision (409)
        - Alternate route PUT /api/comments/<id>
        """
        q_id = "test_q_03"
        self._create_publication(q_id, "author_q3", "question", "Вопрос по многопоточности")

        cookie_author = self._login("user_ans_3", "Автор ответа")
        cookie_intruder = self._login("user_intruder_3", "Чужой пользователь")

        # Create answer (revision 1)
        status, res = self._post_json(f"/api/articles/{q_id}/comments", {
            "content": "Исходный текст ответа v1",
            "commentType": "answer"
        }, cookie=cookie_author)
        self.assertEqual(status, 201)
        ans_id = res["comment"]["id"]
        self.assertEqual(res["comment"]["revision"], 1)

        # 1. Unauthenticated PUT -> 401
        status, res = self._put_json(f"/api/articles/{q_id}/comments/{ans_id}", {
            "content": "Попытка без авторизации",
            "revision": 1
        })
        self.assertEqual(status, 401)

        # 2. Intruder attempts to edit author's answer -> 403 Forbidden
        status, res = self._put_json(f"/api/articles/{q_id}/comments/{ans_id}", {
            "content": "Взлом текста ответа",
            "revision": 1
        }, cookie=cookie_intruder)
        self.assertEqual(status, 403)
        self.assertFalse(res.get("success"))

        # 3. Empty content validation -> 400 Bad Request
        status, res = self._put_json(f"/api/articles/{q_id}/comments/{ans_id}", {
            "content": "   ",
            "revision": 1
        }, cookie=cookie_author)
        self.assertEqual(status, 400)

        # 4. Wrong article id in URL -> 400 Bad Request
        status, res = self._put_json(f"/api/articles/wrong_q_id/comments/{ans_id}", {
            "content": "Текст",
            "revision": 1
        }, cookie=cookie_author)
        self.assertEqual(status, 400)

        # 5. Successful update with revision 1 -> 200 OK, revision becomes 2
        status, res = self._put_json(f"/api/articles/{q_id}/comments/{ans_id}", {
            "content": "Обновленный текст ответа v2",
            "revision": 1
        }, cookie=cookie_author)
        self.assertEqual(status, 200)
        self.assertTrue(res.get("success"))
        comm = res.get("comment", {})
        self.assertEqual(comm.get("content"), "Обновленный текст ответа v2")
        self.assertEqual(comm.get("revision"), 2)
        self.assertTrue(comm.get("updatedAt"))

        # 6. Concurrency conflict: update with stale revision 1 -> 409 Conflict
        status, res = self._put_json(f"/api/articles/{q_id}/comments/{ans_id}", {
            "content": "Устаревшая редакция",
            "revision": 1
        }, cookie=cookie_author)
        self.assertEqual(status, 409)
        self.assertFalse(res.get("success"))
        self.assertEqual(res.get("code"), "CONCURRENCY_CONFLICT")
        self.assertEqual(res.get("currentRevision"), 2)
        self.assertEqual(res.get("currentContent"), "Обновленный текст ответа v2")

        # 7. Update via alternate route PUT /api/comments/<id> with revision 2 -> 200 OK
        status, res = self._put_json(f"/api/comments/{ans_id}", {
            "content": "Обновленный текст через короткий маршрут v3",
            "revision": 2
        }, cookie=cookie_author)
        self.assertEqual(status, 200)
        self.assertTrue(res.get("success"))
        self.assertEqual(res["comment"]["revision"], 3)
        self.assertEqual(res["comment"]["content"], "Обновленный текст через короткий маршрут v3")

    def test_04_solution_mark_atomic_and_auth_403_admin_forbidden(self):
        """
        Tests marking solutions:
        - Only question author permitted (admin forbidden: 403)
        - Only published answers can be marked (400 for comments)
        - Atomic switch between answers (single solution invariant)
        - Idempotence and notification behavior
        - Unmarking solution (isSolution=False)
        """
        q_id = "test_q_04"
        self._create_publication(q_id, "author_q4", "question", "Вопрос по алгоритмам")

        cookie_author = self._login("author_q4", "Автор Вопроса")
        cookie_ans_a = self._login("ans_user_4a", "Отвечающий А")
        cookie_ans_b = self._login("ans_user_4b", "Отвечающий Б")
        cookie_admin = self._login("admin_user_4", "Администратор", role="admin")
        cookie_random = self._login("random_user_4", "Случайный пользователь")

        # Create Answer A
        status, res = self._post_json(f"/api/articles/{q_id}/comments", {
            "content": "Ответ алгоритмический А",
            "commentType": "answer"
        }, cookie=cookie_ans_a)
        self.assertEqual(status, 201)
        ans_a_id = res["comment"]["id"]

        # Create Answer B
        status, res = self._post_json(f"/api/articles/{q_id}/comments", {
            "content": "Ответ алгоритмический Б",
            "commentType": "answer"
        }, cookie=cookie_ans_b)
        self.assertEqual(status, 201)
        ans_b_id = res["comment"]["id"]

        # Create a clarification comment
        status, res = self._post_json(f"/api/articles/{q_id}/comments", {
            "content": "Уточнение к условию",
            "commentType": "comment"
        }, cookie=cookie_author)
        self.assertEqual(status, 201)
        comm_id = res["comment"]["id"]

        # 1. Random user attempt -> 403 Forbidden
        status, res = self._post_json(f"/api/articles/{q_id}/comments/{ans_a_id}/solution", {
            "isSolution": True
        }, cookie=cookie_random)
        self.assertEqual(status, 403)

        # 2. Admin attempt without authorship -> 403 Forbidden (admin exception removed)
        status, res = self._post_json(f"/api/articles/{q_id}/comments/{ans_a_id}/solution", {
            "isSolution": True
        }, cookie=cookie_admin)
        self.assertEqual(status, 403)
        self.assertFalse(res.get("success"))

        # 3. Marking regular comment as solution -> 400 Bad Request
        status, res = self._post_json(f"/api/articles/{q_id}/comments/{comm_id}/solution", {
            "isSolution": True
        }, cookie=cookie_author)
        self.assertEqual(status, 400)

        # 4. Author marks Answer A as solution -> 200 OK
        status, res = self._post_json(f"/api/articles/{q_id}/comments/{ans_a_id}/solution", {
            "isSolution": True
        }, cookie=cookie_author)
        self.assertEqual(status, 200)
        self.assertTrue(res.get("isSolution"))

        # Check in DB: ans_a is solution, notification sent to ans_user_4a
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT is_solution FROM article_comments WHERE id = ?", (ans_a_id,))
        self.assertEqual(cur.fetchone()[0], 1)
        cur.execute("""
            SELECT COUNT(*) FROM user_notifications
            WHERE user_id = ? AND type = 'solution_accepted' AND comment_id = ?
        """, ("ans_user_4a", ans_a_id))
        self.assertEqual(cur.fetchone()[0], 1)
        conn.close()

        # 5. Author switches solution to Answer B -> 200 OK, Answer A reset to 0
        status, res = self._post_json(f"/api/articles/{q_id}/comments/{ans_b_id}/solution", {
            "isSolution": True
        }, cookie=cookie_author)
        self.assertEqual(status, 200)
        self.assertTrue(res.get("isSolution"))

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT is_solution FROM article_comments WHERE id = ?", (ans_a_id,))
        self.assertEqual(cur.fetchone()[0], 0)
        cur.execute("SELECT is_solution FROM article_comments WHERE id = ?", (ans_b_id,))
        self.assertEqual(cur.fetchone()[0], 1)
        cur.execute("""
            SELECT COUNT(*) FROM user_notifications
            WHERE user_id = ? AND type = 'solution_accepted' AND comment_id = ?
        """, ("ans_user_4b", ans_b_id))
        self.assertEqual(cur.fetchone()[0], 1)
        conn.close()

        # 6. Idempotence: re-sending isSolution=True on Answer B does not duplicate notifications
        status, res = self._post_json(f"/api/articles/{q_id}/comments/{ans_b_id}/solution", {
            "isSolution": True
        }, cookie=cookie_author)
        self.assertEqual(status, 200)

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM user_notifications
            WHERE user_id = ? AND type = 'solution_accepted' AND comment_id = ?
        """, ("ans_user_4b", ans_b_id))
        self.assertEqual(cur.fetchone()[0], 1)
        conn.close()

        # 7. Unmarking solution: isSolution=False -> 200 OK, is_solution becomes 0
        status, res = self._post_json(f"/api/articles/{q_id}/comments/{ans_b_id}/solution", {
            "isSolution": False
        }, cookie=cookie_author)
        self.assertEqual(status, 200)
        self.assertFalse(res.get("isSolution"))

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT is_solution FROM article_comments WHERE id = ?", (ans_b_id,))
        self.assertEqual(cur.fetchone()[0], 0)
        conn.close()

    def test_05_structured_comments_get_and_profile_counters(self):
        """
        Tests structured comments retrieval (answers, nested replies, questionComments,
        myAnswerId, counters) and user profile stats (answersCount, solutionsCount).
        Also tests that search snippet matchedAnswerSnippet only matches answers.
        """
        q_id = "test_q_05"
        art_id = "test_art_05"
        self._create_publication(q_id, "author_q5", "question", "Вопрос по микросервисам")
        self._create_publication(art_id, "author_art5", "article", "Статья по микросервисам")

        cookie_expert = self._login("user_expert_5", "Эксперт Архитектор")
        cookie_reply = self._login("user_reply_5", "Коллега")
        cookie_q_author = self._login("author_q5", "Автор Вопроса 5")

        # 1. Expert posts an answer containing unique keyword "MicroserviceSnippetAlpha"
        status, res = self._post_json(f"/api/articles/{q_id}/comments", {
            "content": "Развернутый ответ по MicroserviceSnippetAlpha шаблонам",
            "commentType": "answer"
        }, cookie=cookie_expert)
        self.assertEqual(status, 201)
        ans_id = res["comment"]["id"]

        # 2. Expert posts a regular comment to a non-question article
        status, res = self._post_json(f"/api/articles/{art_id}/comments", {
            "content": "Обычный комментарий к статье",
            "commentType": "comment"
        }, cookie=cookie_expert)
        self.assertEqual(status, 201)

        # 3. Question author posts a top-level clarification to the question
        status, res = self._post_json(f"/api/articles/{q_id}/comments", {
            "content": "Уточнение к вопросу о версионировании",
            "commentType": "comment"
        }, cookie=cookie_q_author)
        self.assertEqual(status, 201)
        clarif_id = res["comment"]["id"]

        # 4. Colleague posts a reply to expert's answer
        status, res = self._post_json(f"/api/articles/{q_id}/comments", {
            "content": "Согласен с MicroserviceSnippetAlpha подходом",
            "commentType": "comment",
            "parentAnswerId": ans_id
        }, cookie=cookie_reply)
        self.assertEqual(status, 201)
        reply_id = res["comment"]["id"]

        # 5. Mark expert's answer as solution
        status, res = self._post_json(f"/api/articles/{q_id}/comments/{ans_id}/solution", {
            "isSolution": True
        }, cookie=cookie_q_author)
        self.assertEqual(status, 200)

        # 6. Verify structured GET /api/articles/<q_id>/comments as expert
        status, res = self._get_json(f"/api/articles/{q_id}/comments", cookie=cookie_expert)
        self.assertEqual(status, 200)
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("answersCount"), 1)
        self.assertEqual(res.get("questionCommentsCount"), 1)
        self.assertEqual(res.get("discussionCount"), 3)
        self.assertTrue(res.get("hasSolution"))
        self.assertEqual(res.get("myAnswerId"), ans_id)

        answers = res.get("answers", [])
        self.assertEqual(len(answers), 1)
        self.assertEqual(answers[0]["id"], ans_id)
        self.assertTrue(answers[0]["isSolution"])
        self.assertEqual(len(answers[0].get("comments", [])), 1)
        self.assertEqual(answers[0]["comments"][0]["id"], reply_id)

        question_comments = res.get("questionComments", [])
        self.assertEqual(len(question_comments), 1)
        self.assertEqual(question_comments[0]["id"], clarif_id)

        # 7. Check user profile counters GET /api/users/<user_id>
        status, prof = self._get_json("/api/users/user_expert_5")
        self.assertEqual(status, 200)
        self.assertTrue(prof.get("success"))
        stats = prof.get("stats", {})
        # Expert posted 1 answer (on question) and 1 comment (on article)
        # Only the answer counts towards answersCount
        self.assertEqual(stats.get("answersCount"), 1)
        self.assertEqual(stats.get("solutionsCount"), 1)

        # 8. Search query matching answer snippet
        status, feed = self._get_json("/api/articles?tab=questions&q=MicroserviceSnippetAlpha")
        self.assertEqual(status, 200)
        articles = feed.get("articles", [])
        matched = [a for a in articles if a["id"] == q_id]
        self.assertEqual(len(matched), 1)
        self.assertIsNotNone(matched[0].get("matchedAnswerSnippet"))
        self.assertIn("MicroserviceSnippetAlpha", matched[0]["matchedAnswerSnippet"])


if __name__ == "__main__":
    unittest.main()
