#!/usr/bin/env python3
"""
tests/test_issue16_sc016_answers_comments_solutions_invariants.py

Comprehensive regression test suite for Issue #16 (SC-016):
"Унифицировать подсчет и инварианты сущностей «ответ», «комментарий» и «решение»".

Acceptance Criteria & Test Matrix:
1. Попытка отправки commentType='answer' к обычной статье отклоняется со статусом 400 Bad Request.
2. Отправка commentType='answer' к вопросу успешно сохраняется со статусом 201 Created.
3. Отправка commentType='comment' к вопросу успешно сохраняется со статусом 201 Created.
4. Отметка решения на комментарии с типом answer успешно устанавливает isSolution=True (200 OK).
5. Попытка отметки решения на комментарии с типом comment отклоняется со статусом 400 Bad Request.
6. Попытка отметки решения на комментарии к обычной статье (не вопросу) отклоняется со статусом 400 Bad Request.
7. Вопрос с 1 уточнением (comment_type='comment') и 0 ответов корректно отображается в виджете /api/questions/unanswered.
8. Вопрос с 1 релевантным ответом (comment_type='answer') корректно исключается из виджета /api/questions/unanswered.
9. В ленте /api/articles?tab=questions&questionStatus=unanswered вопрос с 0 ответов и >0 комментариев корректно выводится как неотвеченный.
10. Поддержка альтернативных маршрутов решения (/comments/<id>/solution и /articles/<id>/solution).
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
import urllib.request
from typing import Optional, Tuple

import server
from server import create_server, init_db

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue16AnswersCommentsSolutionsInvariants(unittest.TestCase):
    """Test suite for domain invariants of answers, comments, and solutions."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue16.db")
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
            res_body = e.read().decode("utf-8")
            return e.code, json.loads(res_body) if res_body else {}

    def _create_publication(self, pub_id: str, author_id: str, material_type: str, title: str) -> str:
        """Helper to directly insert an approved publication with specified materialType."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        settings = {
            "materialType": material_type,
            "type": material_type,
            "topics": ["Смарт-контракты"],
            "description": f"Описание {title}"
        }
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO moderation_submissions (
                    id, draft_id, author_id, title, article_html, article_delta, publication_settings, snapshot_hash, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'hash_dummy', 'approved', ?, ?)
            """, (
                pub_id, f"draft_{pub_id}", author_id, title,
                f"<p>Тестовый контент для {title}</p>",
                json.dumps({"ops": [{"insert": f"Тестовый контент для {title}\n"}]}),
                json.dumps(settings),
                now_iso, now_iso
            ))
            # Also create profile for author so it displays nicely
            conn.execute("""
                INSERT OR IGNORE INTO user_profiles (user_id, name, specialization, created_at, updated_at)
                VALUES (?, ?, 'Эксперт', ?, ?)
            """, (author_id, f"Пользователь {author_id}", now_iso, now_iso))
        conn.close()
        return pub_id

    # 1. Posting commentType='answer' to non-question fails with 400
    def test_01_comment_type_answer_to_article_fails(self):
        art_id = "test_art_01"
        self._create_publication(art_id, "author_art_1", "article", "Статья об архитектуре")
        cookie_user = self._login("user_commenter_1", "Комментатор")

        # Attempt with camelCase commentType
        status, res = self._post_json(f"/api/articles/{art_id}/comments", {
            "content": "Пытаюсь отправить ответ к статье",
            "commentType": "answer"
        }, cookie=cookie_user)
        self.assertEqual(status, 400)
        self.assertFalse(res.get("success"))
        self.assertIn("Ответ (answer) возможен только для публикаций с типом 'Вопрос'", res.get("error", ""))

        # Attempt with snake_case comment_type
        status, res2 = self._post_json(f"/api/articles/{art_id}/comments", {
            "content": "Пытаюсь отправить ответ (snake_case) к статье",
            "comment_type": "answer"
        }, cookie=cookie_user)
        self.assertEqual(status, 400)
        self.assertFalse(res2.get("success"))
        self.assertIn("Ответ (answer) возможен только для публикаций с типом 'Вопрос'", res2.get("error", ""))

    # 2. Posting commentType='answer' to question succeeds (201)
    def test_02_comment_type_answer_to_question_succeeds(self):
        q_id = "test_q_02"
        self._create_publication(q_id, "author_q_2", "question", "Вопрос по EVM")
        cookie_user = self._login("user_answerer_2", "Отвечающий")

        status, res = self._post_json(f"/api/articles/{q_id}/comments", {
            "content": "Вот развернутый ответ на ваш вопрос по опкодам EVM.",
            "commentType": "answer"
        }, cookie=cookie_user)
        self.assertEqual(status, 201)
        self.assertTrue(res.get("success"))
        comment = res.get("comment", {})
        self.assertEqual(comment.get("commentType"), "answer")
        self.assertFalse(comment.get("isSolution"))
        self.assertEqual(comment.get("articleId"), q_id)

    # 3. Posting commentType='comment' to question succeeds (201)
    def test_03_comment_type_comment_to_question_succeeds(self):
        q_id = "test_q_03"
        self._create_publication(q_id, "author_q_3", "question", "Вопрос по Gas Optimization")
        cookie_user = self._login("user_clarifier_3", "Уточняющий")

        status, res = self._post_json(f"/api/articles/{q_id}/comments", {
            "content": "Уточните, пожалуйста, какую версию solc вы используете?",
            "commentType": "comment"
        }, cookie=cookie_user)
        self.assertEqual(status, 201)
        self.assertTrue(res.get("success"))
        comment = res.get("comment", {})
        self.assertEqual(comment.get("commentType"), "comment")
        self.assertFalse(comment.get("isSolution"))

    # 4. Strict commentType validation (superseded in Issue #24: omission returns 400)
    def test_04_default_comment_type_assignment(self):
        q_id = "test_q_04"
        art_id = "test_art_04"
        self._create_publication(q_id, "author_q_4", "question", "Вопрос без типа ответа")
        self._create_publication(art_id, "author_art_4", "article", "Статья без типа комментария")
        cookie_user = self._login("user_generic_4", "Обычный пользователь")

        # To question without commentType -> 400 (strict validation)
        status, res_q = self._post_json(f"/api/articles/{q_id}/comments", {
            "content": "Ответ без явного указания commentType"
        }, cookie=cookie_user)
        self.assertEqual(status, 400)
        self.assertFalse(res_q.get("success"))

        # To article without commentType -> 400 (strict validation)
        status, res_art = self._post_json(f"/api/articles/{art_id}/comments", {
            "content": "Комментарий без явного указания commentType"
        }, cookie=cookie_user)
        self.assertEqual(status, 400)
        self.assertFalse(res_art.get("success"))

    # 5. Marking answer as solution succeeds (200, isSolution: True)
    def test_05_mark_answer_as_solution_succeeds(self):
        q_id = "test_q_05"
        author_id = "author_q_5"
        self._create_publication(q_id, author_id, "question", "Вопрос для проверки решения")
        cookie_author = self._login(author_id, "Автор Вопроса 5")
        cookie_ans = self._login("user_ans_5", "Ответивший 5")

        # Post answer
        _, res_ans = self._post_json(f"/api/articles/{q_id}/comments", {
            "content": "Правильное решение проблемы с ReentrancyGuard.",
            "commentType": "answer"
        }, cookie=cookie_ans)
        comment_id = res_ans["comment"]["id"]

        # Mark as solution
        status, res_sol = self._post_json(f"/api/articles/{q_id}/comments/{comment_id}/solution", {}, cookie=cookie_author)
        self.assertEqual(status, 200)
        self.assertTrue(res_sol.get("success"))
        self.assertTrue(res_sol.get("isSolution"))
        self.assertTrue(res_sol.get("is_solution"))

        # Verify detail endpoint returns hasSolution = True
        status, detail = self._get_json(f"/api/articles/{q_id}")
        self.assertEqual(status, 200)
        self.assertTrue(detail["article"]["hasSolution"])

        # Unmark solution (toggle OFF)
        status, res_unsol = self._post_json(f"/api/articles/{q_id}/comments/{comment_id}/solution", {}, cookie=cookie_author)
        self.assertEqual(status, 200)
        self.assertFalse(res_unsol.get("isSolution"))

    # 6. Marking ordinary comment as solution fails with 400
    def test_06_mark_ordinary_comment_as_solution_fails(self):
        q_id = "test_q_06"
        author_id = "author_q_6"
        self._create_publication(q_id, author_id, "question", "Вопрос с уточнением")
        cookie_author = self._login(author_id, "Автор Вопроса 6")
        cookie_comm = self._login("user_comm_6", "Комментатор 6")

        # Post clarifying comment (NOT answer)
        _, res_comm = self._post_json(f"/api/articles/{q_id}/comments", {
            "content": "Это просто уточняющий комментарий, а не решение.",
            "commentType": "comment"
        }, cookie=cookie_comm)
        comm_id = res_comm["comment"]["id"]

        # Attempt to mark comment as solution
        status, res_sol = self._post_json(f"/api/articles/{q_id}/comments/{comm_id}/solution", {}, cookie=cookie_author)
        self.assertEqual(status, 400)
        self.assertFalse(res_sol.get("success"))
        self.assertIn("Статус решения может быть установлен только ответу (comment_type = 'answer').", res_sol.get("error", ""))

    # 7. Marking solution on non-question publication comment fails with 400
    def test_07_mark_solution_on_article_comment_fails(self):
        art_id = "test_art_07"
        author_id = "author_art_7"
        self._create_publication(art_id, author_id, "article", "Обычная статья")
        cookie_author = self._login(author_id, "Автор Статьи 7")
        cookie_comm = self._login("user_comm_7", "Комментатор 7")

        # Post comment to article
        _, res_comm = self._post_json(f"/api/articles/{art_id}/comments", {
            "content": "Комментарий к статье.",
            "commentType": "comment"
        }, cookie=cookie_comm)
        comm_id = res_comm["comment"]["id"]

        # Attempt to mark comment on article as solution
        status, res_sol = self._post_json(f"/api/articles/{art_id}/comments/{comm_id}/solution", {}, cookie=cookie_author)
        self.assertEqual(status, 400)
        self.assertFalse(res_sol.get("success"))
        self.assertIn("Статус решения может быть установлен только для вопросов (materialType = 'question').", res_sol.get("error", ""))

    # 8. Authorization for solution toggle (403 for non-author, 200 for author and admin)
    def test_08_solution_toggle_authorization(self):
        q_id = "test_q_08"
        author_id = "author_q_8"
        self._create_publication(q_id, author_id, "question", "Вопрос для проверки прав")
        cookie_author = self._login(author_id, "Автор Вопроса 8")
        cookie_stranger = self._login("user_stranger_8", "Посторонний")
        cookie_admin = self._login("user_admin_8", "Админ", role="admin")

        # Post answer
        _, res_ans = self._post_json(f"/api/articles/{q_id}/comments", {
            "content": "Ответ для тестирования прав.",
            "commentType": "answer"
        }, cookie=cookie_stranger)
        ans_id = res_ans["comment"]["id"]

        # Stranger attempts solution toggle -> 403
        status, res_err = self._post_json(f"/api/articles/{q_id}/comments/{ans_id}/solution", {}, cookie=cookie_stranger)
        self.assertEqual(status, 403)
        self.assertFalse(res_err.get("success"))

        # Admin (non-author) attempts solution toggle -> 403 (admin bypass removed in Issue #24)
        status, res_adm = self._post_json(f"/api/articles/{q_id}/comments/{ans_id}/solution", {}, cookie=cookie_admin)
        self.assertEqual(status, 403)
        self.assertFalse(res_adm.get("success"))

        # Author toggles solution -> 200
        status, res_author = self._post_json(f"/api/articles/{q_id}/comments/{ans_id}/solution", {}, cookie=cookie_author)
        self.assertEqual(status, 200)
        self.assertTrue(res_author.get("isSolution"))

    # 9. GET /api/questions/unanswered includes question with 1 comment and 0 answers
    def test_09_unanswered_widget_includes_question_with_comments_only(self):
        q_id = "test_q_09"
        self._create_publication(q_id, "author_q_9", "question", "Вопрос с комментариями, но без ответов")
        cookie_user = self._login("user_comm_9", "Комментатор 9")

        # Add 2 clarifying comments
        self._post_json(f"/api/articles/{q_id}/comments", {
            "content": "Первое уточнение к вопросу.",
            "commentType": "comment"
        }, cookie=cookie_user)
        self._post_json(f"/api/articles/{q_id}/comments", {
            "content": "Второе уточнение к вопросу.",
            "commentType": "comment"
        }, cookie=cookie_user)

        # GET /api/questions/unanswered
        status, data = self._get_json("/api/questions/unanswered")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        questions = data.get("questions", [])
        q_ids = [q["id"] for q in questions]
        self.assertIn(q_id, q_ids, "Question with comments but 0 answers MUST appear in unanswered widget")

        target_q = next(q for q in questions if q["id"] == q_id)
        self.assertEqual(target_q.get("answersCount"), 0)
        self.assertEqual(target_q.get("material_type"), "question")
        self.assertEqual(target_q.get("materialType"), "question")

    # 10. GET /api/questions/unanswered excludes question with 1 answer
    def test_10_unanswered_widget_excludes_question_with_answer(self):
        q_id = "test_q_10"
        self._create_publication(q_id, "author_q_10", "question", "Вопрос, который получит ответ")
        cookie_user = self._login("user_comm_10", "Пользователь 10")

        # Verify it is in unanswered widget before answer
        status, data_before = self._get_json("/api/questions/unanswered")
        self.assertEqual(status, 200)
        self.assertIn(q_id, [q["id"] for q in data_before.get("questions", [])])

        # Post answer
        status_post, _ = self._post_json(f"/api/articles/{q_id}/comments", {
            "content": "Полноценный ответ на вопрос.",
            "commentType": "answer"
        }, cookie=cookie_user)
        self.assertEqual(status_post, 201)

        # Verify it is now excluded from unanswered widget
        status, data_after = self._get_json("/api/questions/unanswered")
        self.assertEqual(status, 200)
        self.assertNotIn(q_id, [q["id"] for q in data_after.get("questions", [])],
                         "Question with published answer MUST NOT appear in unanswered widget")

    # 11. GET /api/articles?tab=questions&questionStatus=unanswered includes question with 0 answers even if comments > 0
    def test_11_articles_feed_unanswered_filter(self):
        q_unans_id = "test_q_11_unans"
        q_ans_id = "test_q_11_ans"
        self._create_publication(q_unans_id, "author_q_11a", "question", "Неотвеченный вопрос с комментариями")
        self._create_publication(q_ans_id, "author_q_11b", "question", "Отвеченный вопрос")
        cookie_user = self._login("user_11", "Пользователь 11")

        # Post comment to q_unans_id
        self._post_json(f"/api/articles/{q_unans_id}/comments", {
            "content": "Уточнение к неотвеченному вопросу.",
            "commentType": "comment"
        }, cookie=cookie_user)

        # Post answer to q_ans_id
        self._post_json(f"/api/articles/{q_ans_id}/comments", {
            "content": "Ответ к отвеченному вопросу.",
            "commentType": "answer"
        }, cookie=cookie_user)

        # Request feed with tab=questions&questionStatus=unanswered
        status, data = self._get_json("/api/articles?tab=questions&questionStatus=unanswered")
        self.assertEqual(status, 200)
        items = data.get("articles", [])
        item_ids = [it["id"] for it in items]

        self.assertIn(q_unans_id, item_ids,
                      "Question with comments but 0 answers MUST appear in unanswered questions feed")
        self.assertNotIn(q_ans_id, item_ids,
                         "Question with answer MUST NOT appear in unanswered questions feed")

        matched = next(it for it in items if it["id"] == q_unans_id)
        self.assertEqual(matched.get("answersCount"), 0)
        self.assertEqual(matched.get("commentsCount"), 1)

    # 12. Alternative solution endpoint routes
    def test_12_alternative_solution_endpoint_routes(self):
        q_id = "test_q_12"
        author_id = "author_q_12"
        self._create_publication(q_id, author_id, "question", "Вопрос для проверки альтернативных путей")
        cookie_author = self._login(author_id, "Автор Вопроса 12")
        cookie_user = self._login("user_12", "Отвечающий 12")

        # Post answer
        _, res_ans = self._post_json(f"/api/articles/{q_id}/comments", {
            "content": "Ответ для альтернативного роута.",
            "commentType": "answer"
        }, cookie=cookie_user)
        ans_id = res_ans["comment"]["id"]

        # Route 1: POST /api/comments/<comm_id>/solution
        status1, res1 = self._post_json(f"/api/comments/{ans_id}/solution", {}, cookie=cookie_author)
        self.assertEqual(status1, 200)
        self.assertTrue(res1.get("isSolution"))

        # Route 2: POST /api/articles/<art_id>/solution with {"commentId": ...}
        status2, res2 = self._post_json(f"/api/articles/{q_id}/solution", {"commentId": ans_id}, cookie=cookie_author)
        self.assertEqual(status2, 200)
        self.assertFalse(res2.get("isSolution"))  # Toggled off


if __name__ == "__main__":
    unittest.main()
