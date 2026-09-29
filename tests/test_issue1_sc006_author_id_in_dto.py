#!/usr/bin/env python3
"""
tests/test_issue1_sc006_author_id_in_dto.py

Regression test suite for Issue #1 (SC-006):
"Вернуть authorId в DTO статей (list и detail) для возможности принятия ответа автором".

Acceptance Criteria:
1. GET /api/articles returns authorId and author_id in every article DTO, matching SQLite author_id.
2. GET /api/articles/<id> and GET /api/articles?id=<id> return authorId and author_id in article DTO.
3. Feed cards (card.js) and article detail page (article.js) receive valid authorId.
4. Solution button ("Отметить как решение" / btn-toggle-solution) is shown to the question author
   and hidden from other users / guests based on DTO authorId.
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
import urllib.parse
import urllib.request

import server
from server import create_server, init_db

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue1SC006AuthorIdInDTO(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue1_sc006.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path)
        conn.close()

        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR)
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.1)

        with open(os.path.join(FRONTEND_DIR, "js", "article.js"), "r", encoding="utf-8") as f:
            cls.article_js = f.read()
        with open(os.path.join(FRONTEND_DIR, "js", "card.js"), "r", encoding="utf-8") as f:
            cls.card_js = f.read()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.httpd.shutdown()
            cls.httpd.server_close()
        except Exception:
            pass
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def _login(self, user_id, user_name):
        req = urllib.request.Request(
            f"{self.base_url}/api/auth/login",
            data=json.dumps({"userId": user_id, "name": user_name}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            cookie = resp.headers.get("Set-Cookie")
            return data, cookie

    def _get_json(self, path, cookie=None):
        headers = {}
        if cookie:
            headers["Cookie"] = cookie
        req = urllib.request.Request(f"{self.base_url}{path}", headers=headers)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data

    def _post_json(self, path, payload, cookie=None):
        headers = {"Content-Type": "application/json"}
        if cookie:
            headers["Cookie"] = cookie
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers
        )
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return resp.status, data
        except urllib.error.HTTPError as e:
            data = json.loads(e.read().decode("utf-8"))
            return e.code, data

    def test_articles_list_contains_author_id(self):
        """Verify that GET /api/articles includes authorId and author_id in all items."""
        status, data = self._get_json("/api/articles?limit=50")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        articles = data.get("articles", [])
        self.assertGreater(len(articles), 0, "Feed should contain seeded articles")

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        with conn:
            cur = conn.cursor()
            for article in articles:
                self.assertIn("authorId", article, f"Article {article.get('id')} missing authorId")
                self.assertIn("author_id", article, f"Article {article.get('id')} missing author_id")
                self.assertEqual(article["authorId"], article["author_id"])
                self.assertTrue(bool(article["authorId"]), f"Article {article.get('id')} has empty authorId")

                # Verify against database record
                cur.execute("SELECT author_id FROM moderation_submissions WHERE id = ?", (article["id"],))
                row = cur.fetchone()
                if row:
                    self.assertEqual(article["authorId"], row["author_id"])

    def test_article_detail_contains_author_id(self):
        """Verify that GET /api/articles/<id> and GET /api/articles?id=<id> return authorId and author_id."""
        status, feed_data = self._get_json("/api/articles?limit=1")
        self.assertEqual(status, 200)
        first_article_id = feed_data["articles"][0]["id"]
        expected_author_id = feed_data["articles"][0]["authorId"]

        # 1. Path param GET /api/articles/<id>
        status, detail_data = self._get_json(f"/api/articles/{first_article_id}")
        self.assertEqual(status, 200)
        self.assertTrue(detail_data.get("success"))
        article_obj = detail_data.get("article", {})
        self.assertIn("authorId", article_obj)
        self.assertIn("author_id", article_obj)
        self.assertEqual(article_obj["authorId"], expected_author_id)
        self.assertEqual(article_obj["author_id"], expected_author_id)

        # 2. Query param GET /api/articles?id=<id>
        status, query_data = self._get_json(f"/api/articles?id={first_article_id}")
        self.assertEqual(status, 200)
        self.assertTrue(query_data.get("success"))
        article_q_obj = query_data.get("article", {})
        self.assertIn("authorId", article_q_obj)
        self.assertIn("author_id", article_q_obj)
        self.assertEqual(article_q_obj["authorId"], expected_author_id)
        self.assertEqual(article_q_obj["author_id"], expected_author_id)

    def test_article_js_code_contract(self):
        """Verify article.js contract for author identification and solution button."""
        # article.js must verify author via currentArticle.authorId || currentArticle.author_id
        self.assertIn(
            "currentUser.id === currentArticle.authorId || currentUser.id === currentArticle.author_id",
            self.article_js,
            "article.js must match currentUser against currentArticle.authorId"
        )
        self.assertIn("btn-toggle-solution", self.article_js)
        self.assertIn("Отметить как решение", self.article_js)
        self.assertIn("Снять отметку решения", self.article_js)

    def test_card_js_code_contract_and_markup(self):
        """Verify card.js extracts authorId and binds it to data-user-id."""
        self.assertIn(
            "const authorId = item.authorId || item.author_id || item.userId || '';",
            self.card_js,
            "card.js must extract authorId from item"
        )
        self.assertIn('data-user-id="\' + escapeHtml(authorId) + \'"', self.card_js)

        # Simulate card.js logic with actual server article DTO
        status, feed_data = self._get_json("/api/articles?limit=5")
        self.assertEqual(status, 200)
        for item in feed_data["articles"]:
            author_id = item.get("authorId") or item.get("author_id") or item.get("userId") or ""
            self.assertTrue(bool(author_id), "Author ID must not be empty in card DTO")
            card_author_btn = f'<button type="button" class="author-name btn-author-profile" data-user-id="{author_id}"'
            self.assertIn(f'data-user-id="{item["authorId"]}"', card_author_btn)

    def test_solution_button_visibility_simulation(self):
        """
        Verify that having authorId in DTO allows article.js to correctly determine
        isAuthor and toggle solution button visibility.
        """
        author_user_id = "user_issue1_author"
        other_user_id = "user_issue1_other"

        _, cookie_author = self._login(author_user_id, "Автор Вопроса")
        _, cookie_other = self._login(other_user_id, "Сторонний Пользователь")

        # 1. Publish a question
        question_payload = {
            "draftId": "draft_issue1_q",
            "authorId": author_user_id,
            "title": "Вопрос по смарт-контрактам: как проверить authorId?",
            "html": "<p>Вопрос для проверки отображения кнопки решения у автора вопроса в интерфейсе.</p>",
            "publicationSettings": {
                "author": "Автор Вопроса",
                "authorRole": "Smart Contract Auditor",
                "targetAudience": "smart-contracts-dev",
                "materialType": "question",
                "topics": ["pksc-architecture"],
                "keywords": ["smart-contracts", "security"],
                "format": "none",
                "complexity": "medium",
                "description": "Подробный вопрос для проверки корректности передачи authorId в DTO статей и отображения кнопки принятия решения."
            }
        }
        status, submit_res = self._post_json("/api/moderation/submit", question_payload, cookie=cookie_author)
        self.assertEqual(status, 200)
        question_id = submit_res.get("submissionId")

        # Approve question
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute("UPDATE moderation_submissions SET status = 'approved' WHERE id = ?", (question_id,))

        # 2. Other user posts an answer
        ans_payload = {
            "content": "Для проверки authorId убедитесь, что сервер возвращает его в GET /api/articles/<id>.",
            "commentType": "answer"
        }
        status, ans_res = self._post_json(f"/api/articles/{question_id}/comments", ans_payload, cookie=cookie_other)
        self.assertIn(status, (200, 201))
        comment_id = ans_res["comment"]["id"]

        # 3. Retrieve question DTO from server
        status, detail_data = self._get_json(f"/api/articles/{question_id}")
        self.assertEqual(status, 200)
        current_article = detail_data["article"]

        # Verify DTO has authorId
        self.assertEqual(current_article.get("authorId"), author_user_id)
        self.assertEqual(current_article.get("author_id"), author_user_id)

        # 4. Simulate article.js solution button decision logic
        def render_solution_action(current_user, article, comment):
            is_question = article and (article.get("materialType") == "question" or
                                       (article.get("publication_settings") and article["publication_settings"].get("materialType") == "question"))
            is_author = bool(
                current_user and article and (
                    current_user.get("id") == article.get("authorId") or
                    current_user.get("id") == article.get("author_id")
                )
            )
            is_sol = comment.get("isSolution") or comment.get("is_solution")
            if is_question and is_author:
                return (
                    f'<button type="button" class="btn btn-sm btn-toggle-solution" data-comment-id="{comment["id"]}">'
                    f'{"Снять отметку решения" if is_sol else "Отметить как решение"}'
                    f'</button>'
                )
            return ""

        # Case A: Logged in as Question Author
        author_user = {"id": author_user_id, "name": "Автор Вопроса"}
        author_btn = render_solution_action(author_user, current_article, {"id": comment_id, "isSolution": False})
        self.assertIn("btn-toggle-solution", author_btn)
        self.assertIn("Отметить как решение", author_btn)

        # Case B: Logged in as Other User
        other_user = {"id": other_user_id, "name": "Сторонний Пользователь"}
        other_btn = render_solution_action(other_user, current_article, {"id": comment_id, "isSolution": False})
        self.assertEqual(other_btn, "", "Solution button must not be visible to non-author")

        # Case C: Guest (not logged in)
        guest_btn = render_solution_action(None, current_article, {"id": comment_id, "isSolution": False})
        self.assertEqual(guest_btn, "", "Solution button must not be visible to guest")

        # 5. Author marks solution on server
        status, sol_res = self._post_json(f"/api/articles/{question_id}/comments/{comment_id}/solution", {}, cookie=cookie_author)
        self.assertEqual(status, 200)
        self.assertTrue(sol_res.get("isSolution"))

        # Case D: Once marked as solution, button changes to "Снять отметку решения" for author
        author_unmark_btn = render_solution_action(author_user, current_article, {"id": comment_id, "isSolution": True})
        self.assertIn("btn-toggle-solution", author_unmark_btn)
        self.assertIn("Снять отметку решения", author_unmark_btn)


if __name__ == "__main__":
    unittest.main()
