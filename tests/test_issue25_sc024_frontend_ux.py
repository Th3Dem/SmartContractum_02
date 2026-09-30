#!/usr/bin/env python3
"""
tests/test_issue25_sc024_frontend_ux.py

Test suite for Issue #25 (SC-024.2):
"Разделение веток обсуждения, карточки ответов, inline-комментарии и форма ответа."

Verification Scope:
1. Markup in frontend/public/article.html (structured Q&A containers, badges, forms, banner).
2. Styles in frontend/public/css/article.css (answer cards, solution badges, updated badges, inline replies, deep linking).
3. JS code contracts in frontend/public/js/article.js:
   - Branching for Question (two sections) vs Article (flat comments).
   - Solution button shown ONLY to question author and ONLY on answer cards.
   - Inline editing for answer author with optimistic locking (revision) and preserving draft text on 409 conflict.
   - "Ваш ответ на вопрос" banner preventing duplicate answer forms when myAnswerId exists.
   - Inline replies to answers with parentAnswerId.
   - Deep linking (#comm_<id>) smooth scroll and highlight.
4. End-to-end integration scenarios for Q&A discussion workflow.
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
import urllib.error

import server
from server import create_server, init_db

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue25MarkupAndStyles(unittest.TestCase):
    """Verify HTML structure and CSS styles for Q&A discussions."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(FRONTEND_DIR, "article.html"), "r", encoding="utf-8") as f:
            cls.article_html = f.read()
        with open(os.path.join(FRONTEND_DIR, "css", "article.css"), "r", encoding="utf-8") as f:
            cls.article_css = f.read()
        with open(os.path.join(FRONTEND_DIR, "js", "article.js"), "r", encoding="utf-8") as f:
            cls.article_js = f.read()

    def test_article_html_qa_markup_structure(self):
        """Verify presence of both standard and structured Q&A wrappers and their elements."""
        # Top-level wrappers
        self.assertIn('id="standardCommentsWrapper"', self.article_html)
        self.assertIn('id="questionCommentsWrapper"', self.article_html)

        # Badges
        self.assertIn('id="commentsCountBadge"', self.article_html)
        self.assertIn('id="questionCommentsCountBadge"', self.article_html)
        self.assertIn('id="answersCountBadge"', self.article_html)

        # Question Clarifications section
        self.assertIn('id="btnAddQuestionClarification"', self.article_html)
        self.assertIn('id="questionClarificationForm"', self.article_html)
        self.assertIn('id="questionClarificationInput"', self.article_html)
        self.assertIn('id="clarificationCharCount"', self.article_html)
        self.assertIn('id="btnCancelClarification"', self.article_html)
        self.assertIn('id="btnSubmitClarification"', self.article_html)
        self.assertIn('id="questionCommentsList"', self.article_html)

        # Answers section
        self.assertIn('id="answersList"', self.article_html)
        self.assertIn('id="answersEmpty"', self.article_html)

        # Answer submission & banner section
        self.assertIn('id="answerSubmissionSection"', self.article_html)
        self.assertIn('id="questionGuestPrompt"', self.article_html)
        self.assertIn('id="btnQuestionLogin"', self.article_html)
        self.assertIn('id="myAnswerFormWrap"', self.article_html)
        self.assertIn('id="questionAnswerForm"', self.article_html)
        self.assertIn('id="answerTextInput"', self.article_html)
        self.assertIn('id="answerCharCount"', self.article_html)
        self.assertIn('id="btnSubmitAnswer"', self.article_html)

        # Existing answer banner
        self.assertIn('id="myAnswerBanner"', self.article_html)
        self.assertIn('id="btnGoToMyAnswer"', self.article_html)
        self.assertIn('id="btnEditMyAnswer"', self.article_html)

    def test_article_css_qa_rules(self):
        """Verify CSS styling rules for Q&A cards, badges, banners, and replies."""
        self.assertIn('.answer-card', self.article_css)
        self.assertIn('.answer-card.is-solution-answer', self.article_css)
        self.assertIn('.solution-badge', self.article_css)
        self.assertIn('.comment-updated-badge', self.article_css)
        self.assertIn('.answer-edit-form-wrap', self.article_css)
        self.assertIn('.answer-edit-textarea', self.article_css)
        self.assertIn('.answer-replies-container', self.article_css)
        self.assertIn('.answer-replies-list', self.article_css)
        self.assertIn('.answer-reply-form', self.article_css)
        self.assertIn('.answer-reply-textarea', self.article_css)
        self.assertIn('.my-answer-banner', self.article_css)
        self.assertIn('.comment-highlight', self.article_css)
        self.assertIn('.btn-author-profile', self.article_css)
        self.assertIn('.btn-sm', self.article_css)

    def test_zero_emojis_and_no_cdn(self):
        """Verify strict compliance with zero emojis and 100% offline-first rules."""
        emoji_pattern = re.compile(
            r"[\U00010000-\U0010ffff]|[\u2600-\u26ff]|[\u2700-\u27bf]"
        )
        self.assertIsNone(emoji_pattern.search(self.article_html), "Found emoji in article.html")
        self.assertIsNone(emoji_pattern.search(self.article_css), "Found emoji in article.css")
        self.assertIsNone(emoji_pattern.search(self.article_js), "Found emoji in article.js")

        cdn_pattern = re.compile(r"https?://(cdn|unpkg|cdnjs|jsdelivr)")
        self.assertIsNone(cdn_pattern.search(self.article_html), "Found external CDN in article.html")
        self.assertIsNone(cdn_pattern.search(self.article_css), "Found external CDN in article.css")
        self.assertIsNone(cdn_pattern.search(self.article_js), "Found external CDN in article.js")


class TestIssue25JsCodeContracts(unittest.TestCase):
    """Verify JavaScript logic and code contracts in frontend/public/js/article.js."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(FRONTEND_DIR, "js", "article.js"), "r", encoding="utf-8") as f:
            cls.article_js = f.read()

    def test_streams_separation_contract(self):
        """Verify branching based on isQuestion to switch between standard and Q&A views."""
        self.assertIn("standardCommentsWrapper", self.article_js)
        self.assertIn("questionCommentsWrapper", self.article_js)
        self.assertIn("renderQuestionClarificationItem", self.article_js)
        self.assertIn("renderAnswerCard", self.article_js)
        self.assertIn("renderAnswerReplyItem", self.article_js)

    def test_solution_button_author_only_contract(self):
        """Verify solution button is bound to author verification and toggles solution status."""
        self.assertIn("currentUser.id === currentArticle.authorId || currentUser.id === currentArticle.author_id", self.article_js)
        self.assertIn("btn-toggle-solution", self.article_js)
        self.assertIn("Отметить как решение", self.article_js)
        self.assertIn("Снять отметку решения", self.article_js)
        self.assertIn("/solution", self.article_js)

    def test_inline_editing_contract(self):
        """Verify inline editing contract: author check, PUT endpoint, revision, and preserving input on 409."""
        self.assertIn("btn-edit-answer", self.article_js)
        self.assertIn("answer-edit-form-wrap", self.article_js)
        self.assertIn("btn-save-answer-edit", self.article_js)
        self.assertIn("btn-cancel-answer-edit", self.article_js)
        self.assertIn("PUT", self.article_js)
        self.assertIn("CONCURRENCY_CONFLICT", self.article_js)
        self.assertIn("Ответ был изменен в другой сессии. Пожалуйста, обновите страницу", self.article_js)
        self.assertIn("Ответ обновлен", self.article_js)

    def test_no_duplicate_answer_form_contract(self):
        """Verify myAnswerBanner vs myAnswerFormWrap toggle and preserving draft text on 409."""
        self.assertIn("myAnswerBanner", self.article_js)
        self.assertIn("myAnswerFormWrap", self.article_js)
        self.assertIn("btnGoToMyAnswer", self.article_js)
        self.assertIn("btnEditMyAnswer", self.article_js)
        self.assertIn("ANSWER_ALREADY_EXISTS", self.article_js)
        self.assertIn("currentMyAnswerId", self.article_js)

    def test_inline_replies_contract(self):
        """Verify inline replies logic: parentAnswerId and commentType: 'comment'."""
        self.assertIn("btn-reply-answer", self.article_js)
        self.assertIn("answer-reply-form", self.article_js)
        self.assertIn("parentAnswerId", self.article_js)

    def test_deep_linking_contract(self):
        """Verify deep link handler checks #comm_ and applies comment-highlight."""
        self.assertIn("#comm_", self.article_js)
        self.assertIn("comment-highlight", self.article_js)


class TestIssue25IntegrationQAWorkflow(unittest.TestCase):
    """End-to-end integration scenario testing Q&A API interactions."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue25_sc024.db")
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

    def _put_json(self, path, payload, cookie=None):
        headers = {"Content-Type": "application/json"}
        if cookie:
            headers["Cookie"] = cookie
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="PUT"
        )
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return resp.status, data
        except urllib.error.HTTPError as e:
            data = json.loads(e.read().decode("utf-8"))
            return e.code, data

    def test_full_qa_workflow_lifecycle(self):
        """
        Complete Q&A lifecycle test:
        1. Author creates question.
        2. User 1 submits answer.
        3. User 1 attempting second answer gets 409 with myAnswerId.
        4. User 2 submits answer.
        5. Author accepts User 2's answer as solution -> solution appears first in answers.
        6. User 1 adds inline reply to User 2's answer.
        7. User 3 adds question clarification.
        8. User 2 edits answer via PUT with revision.
        9. Obsolete revision edit gets 409 CONCURRENCY_CONFLICT.
        10. Non-author cannot toggle solution (403).
        """
        # 1. Author logs in and posts question
        _, author_cookie = self._login("author_qa_1", "Автор Вопроса")
        question_payload = {
            "draftId": "draft_issue25_q",
            "authorId": "author_qa_1",
            "title": "Как организовать оптимистическую блокировку в SQLite?",
            "html": "<p>Подскажите паттерн реализации поля revision при одновременных правках ответов.</p>",
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
        st, q_res = self._post_json("/api/moderation/submit", question_payload, author_cookie)
        self.assertEqual(st, 200)
        question_id = q_res.get("submissionId")

        # Approve question in db so it becomes active and published
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute("UPDATE moderation_submissions SET status = 'approved' WHERE id = ?", (question_id,))

        # 2. User 1 submits an answer
        _, user1_cookie = self._login("user_qa_dev1", "Разработчик 1")
        ans1_payload = {
            "content": "Используйте колонку revision INTEGER NOT NULL DEFAULT 1 и UPDATE WHERE revision = ?",
            "commentType": "answer"
        }
        st, ans1_res = self._post_json(f"/api/articles/{question_id}/comments", ans1_payload, user1_cookie)
        self.assertEqual(st, 201)
        ans1_id = ans1_res["comment"]["id"]

        # 3. User 1 attempts second answer -> 409 ANSWER_ALREADY_EXISTS with myAnswerId
        st, dup_res = self._post_json(f"/api/articles/{question_id}/comments", ans1_payload, user1_cookie)
        self.assertEqual(st, 409)
        self.assertEqual(dup_res.get("code"), "ANSWER_ALREADY_EXISTS")
        self.assertEqual(dup_res.get("myAnswerId"), ans1_id)

        # 4. User 2 submits an answer
        _, user2_cookie = self._login("user_qa_dev2", "Разработчик 2")
        ans2_payload = {
            "content": "Рекомендую дополнительно фиксировать updated_at в формате UTC ISO-8601.",
            "commentType": "answer"
        }
        st, ans2_res = self._post_json(f"/api/articles/{question_id}/comments", ans2_payload, user2_cookie)
        self.assertEqual(st, 201)
        ans2_id = ans2_res["comment"]["id"]

        # 5. Non-author cannot mark solution (403)
        st, forbid_res = self._post_json(f"/api/articles/{question_id}/comments/{ans2_id}/solution", {"isSolution": True}, user1_cookie)
        self.assertEqual(st, 403)

        # 6. Author accepts User 2's answer as solution
        st, sol_res = self._post_json(f"/api/articles/{question_id}/comments/{ans2_id}/solution", {"isSolution": True}, author_cookie)
        self.assertEqual(st, 200)
        self.assertTrue(sol_res.get("isSolution"))

        # 7. User 1 replies to User 2's answer (inline reply)
        reply_payload = {
            "content": "Отличное дополнение про ISO-8601, поддерживаю!",
            "commentType": "comment",
            "parentAnswerId": ans2_id
        }
        st, rep_res = self._post_json(f"/api/articles/{question_id}/comments", reply_payload, user1_cookie)
        self.assertEqual(st, 201)
        reply_id = rep_res["comment"]["id"]

        # 8. User 3 posts a clarification to the question
        _, user3_cookie = self._login("user_qa_clarify", "Читатель 3")
        clarify_payload = {
            "content": "Имеется в виду WAL-режим SQLite или обычный rollback journal?",
            "commentType": "comment"
        }
        st, clar_res = self._post_json(f"/api/articles/{question_id}/comments", clarify_payload, user3_cookie)
        self.assertEqual(st, 201)

        # 9. Verify GET /api/articles/<id>/comments tree structure
        st, comments_data = self._get_json(f"/api/articles/{question_id}/comments", user1_cookie)
        self.assertEqual(st, 200)
        self.assertTrue(comments_data.get("hasSolution"))
        self.assertEqual(comments_data.get("solutionCommentId"), ans2_id)
        self.assertEqual(comments_data.get("myAnswerId"), ans1_id)
        self.assertEqual(comments_data.get("answersCount"), 2)
        self.assertEqual(comments_data.get("questionCommentsCount"), 1)

        # Answers list has accepted solution first
        answers = comments_data.get("answers", [])
        self.assertEqual(len(answers), 2)
        self.assertEqual(answers[0]["id"], ans2_id, "Accepted solution answer must be ordered first")
        self.assertTrue(answers[0]["isSolution"])
        self.assertEqual(answers[1]["id"], ans1_id)
        self.assertFalse(answers[1]["isSolution"])

        # User 2's answer has inline replies
        self.assertEqual(len(answers[0]["comments"]), 1)
        self.assertEqual(answers[0]["comments"][0]["id"], reply_id)

        # 10. User 2 edits their answer with revision = 1 -> success revision = 2
        edit_payload = {
            "content": "Рекомендую дополнительно фиксировать updated_at в формате UTC ISO-8601 (обновлено).",
            "revision": 1
        }
        st, edit_res = self._put_json(f"/api/articles/{question_id}/comments/{ans2_id}", edit_payload, user2_cookie)
        self.assertEqual(st, 200)
        self.assertEqual(edit_res["comment"]["revision"], 2)
        self.assertIn("(обновлено)", edit_res["comment"]["content"])
        self.assertIsNotNone(edit_res["comment"]["updatedAt"])

        # 11. Stale revision edit -> 409 CONCURRENCY_CONFLICT
        st, stale_res = self._put_json(f"/api/articles/{question_id}/comments/{ans2_id}", edit_payload, user2_cookie)
        self.assertEqual(st, 409)
        self.assertEqual(stale_res.get("code"), "CONCURRENCY_CONFLICT")


if __name__ == "__main__":
    unittest.main()
