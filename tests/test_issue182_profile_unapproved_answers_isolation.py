#!/usr/bin/env python3
"""
tests/test_issue182_profile_unapproved_answers_isolation.py

Automated test suite for Issue #182:
[P0][backend][PROFILE] Исключить ответы к неодобренным/непубличным материалам и закрыть доступ к черновикам.

Invariants:
- Zero emojis
- Zero em dashes
- 100% offline-first
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
import urllib.parse
import urllib.request

import server
from server import create_server, init_db

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue182ProfileUnapprovedAnswersIsolation(unittest.TestCase):
    """Verifies that answers to unapproved/pending/rejected/draft/non-question materials never leak."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue182.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path, seed=False)
        cls._seed_test_data(conn)
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

    @classmethod
    def _seed_test_data(cls, conn):
        cur = conn.cursor()
        now = datetime.datetime.now(datetime.timezone.utc)
        t_base = (now - datetime.timedelta(days=10)).isoformat()

        # 1. Respondent author
        respondent_id = "user_respondent"
        cur.execute("""
            INSERT OR REPLACE INTO user_profiles (user_id, name, specialization, company, bio, avatar, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            respondent_id,
            "Иван Экспертов",
            "Solidity Auditor",
            "SecAudit",
            "Аудит смарт-контрактов и ответы на вопросы сообщества.",
            None,
            t_base,
            t_base
        ))

        # 2. Approved Question (Normal)
        t_q1 = (now - datetime.timedelta(days=5)).isoformat()
        cur.execute("""
            INSERT INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'approved', ?, 'hash_q1', ?, ?)
        """, (
            "q_approved_1",
            "draft_q1",
            "user_other_1",
            "Как предотвратить reentrancy в Solidity 0.8?",
            "<p>Вопрос о reentrancy guards и checks-effects-interactions.</p>",
            json.dumps({"materialType": "question", "topics": ["security"]}),
            t_q1,
            t_q1
        ))

        # 3. Rejected Question
        t_q2 = (now - datetime.timedelta(days=4)).isoformat()
        cur.execute("""
            INSERT INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'rejected', ?, 'hash_q2', ?, ?)
        """, (
            "q_rejected_1",
            "draft_q2",
            "user_other_2",
            "Секретный вопрос, который был отклонен",
            "<p>Спам или нарушение правил.</p>",
            json.dumps({"materialType": "question", "topics": ["general"]}),
            t_q2,
            t_q2
        ))

        # 4. Pending Moderation Question
        t_q3 = (now - datetime.timedelta(days=3)).isoformat()
        cur.execute("""
            INSERT INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'pending_moderation', ?, 'hash_q3', ?, ?)
        """, (
            "q_pending_1",
            "draft_q3",
            "user_other_3",
            "Вопрос на модерации",
            "<p>Непроверенный вопрос.</p>",
            json.dumps({"materialType": "question", "topics": ["general"]}),
            t_q3,
            t_q3
        ))

        # 5. Non-question material (article), even if approved
        t_a1 = (now - datetime.timedelta(days=2)).isoformat()
        cur.execute("""
            INSERT INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'approved', ?, 'hash_a1', ?, ?)
        """, (
            "art_regular_1",
            "draft_a1",
            "user_other_4",
            "Обычная статья об архитектуре",
            "<p>Текст статьи.</p>",
            json.dumps({"materialType": "article", "topics": ["architecture"]}),
            t_a1,
            t_a1
        ))

        # 6. Approved Question linked via draft_id
        t_q4 = (now - datetime.timedelta(days=1)).isoformat()
        cur.execute("""
            INSERT INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'approved', ?, 'hash_q4', ?, ?)
        """, (
            "q_approved_draftlink",
            "draft_q4_unique",
            "user_other_5",
            "Вопрос привязанный по draft_id",
            "<p>Вопрос с драфт айди.</p>",
            json.dumps({"materialType": "question", "topics": ["testing"]}),
            t_q4,
            t_q4
        ))

        # Answers from respondent:
        # A1: Answer to approved question (marked as solution)
        cur.execute("""
            INSERT INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, is_solution, created_at)
            VALUES (?, ?, ?, 'Иван Экспертов', ?, 'published', 'answer', 1, ?)
        """, (
            "ans_approved_sol",
            "q_approved_1",
            respondent_id,
            "Используйте OpenZeppelin ReentrancyGuard и шаблон Checks-Effects-Interactions.",
            (now - datetime.timedelta(days=4, hours=20)).isoformat()
        ))

        # A2: Answer to rejected question (should NOT leak)
        cur.execute("""
            INSERT INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, is_solution, created_at)
            VALUES (?, ?, ?, 'Иван Экспертов', ?, 'published', 'answer', 1, ?)
        """, (
            "ans_to_rejected",
            "q_rejected_1",
            respondent_id,
            "Ответ на отклоненный вопрос с конфиденциальной информацией.",
            (now - datetime.timedelta(days=3, hours=20)).isoformat()
        ))

        # A3: Answer to pending question (should NOT leak)
        cur.execute("""
            INSERT INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, is_solution, created_at)
            VALUES (?, ?, ?, 'Иван Экспертов', ?, 'published', 'answer', 0, ?)
        """, (
            "ans_to_pending",
            "q_pending_1",
            respondent_id,
            "Ответ на вопрос на модерации.",
            (now - datetime.timedelta(days=2, hours=20)).isoformat()
        ))

        # A4: Answer to article (not question, should NOT leak)
        cur.execute("""
            INSERT INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, is_solution, created_at)
            VALUES (?, ?, ?, 'Иван Экспертов', ?, 'published', 'answer', 0, ?)
        """, (
            "ans_to_article",
            "art_regular_1",
            respondent_id,
            "Ответ на статью, которая не является вопросом.",
            (now - datetime.timedelta(days=1, hours=20)).isoformat()
        ))

        # A5: Answer referencing question via draft_id (approved, should show)
        cur.execute("""
            INSERT INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, is_solution, created_at)
            VALUES (?, ?, ?, 'Иван Экспертов', ?, 'published', 'answer', 0, ?)
        """, (
            "ans_draftlink",
            "draft_q4_unique",
            respondent_id,
            "Ответ через draft_id родительского вопроса.",
            (now - datetime.timedelta(hours=5)).isoformat()
        ))

        # A6: Answer to non-existent question / draft that was never submitted (should NOT leak)
        cur.execute("""
            INSERT INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, is_solution, created_at)
            VALUES (?, ?, ?, 'Иван Экспертов', ?, 'published', 'answer', 1, ?)
        """, (
            "ans_orphan",
            "non_existent_or_unsubmitted_draft",
            respondent_id,
            "Ответ на несуществующий или неопубликованный черновик.",
            (now - datetime.timedelta(hours=2)).isoformat()
        ))

        conn.commit()

    def _get_json(self, path: str):
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, headers={}, method="GET")
        with urllib.request.urlopen(req) as resp:
            data = resp.read().decode("utf-8")
            return resp.status, json.loads(data) if data else {}

    def test_01_user_answers_tab_excludes_unapproved_and_non_questions(self):
        """GET /api/users/:id/answers must only contain answers to approved questions."""
        status, data = self._get_json("/api/users/user_respondent/answers")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        items = data.get("items", [])
        item_ids = [it["id"] for it in items]

        # Valid approved question answers must be present
        self.assertIn("ans_approved_sol", item_ids)
        self.assertIn("ans_draftlink", item_ids)

        # Unapproved or non-question answers must NOT be present
        self.assertNotIn("ans_to_rejected", item_ids)
        self.assertNotIn("ans_to_pending", item_ids)
        self.assertNotIn("ans_to_article", item_ids)
        self.assertNotIn("ans_orphan", item_ids)

        # Verify total count matches filtered items length
        self.assertEqual(data.get("total"), 2)
        self.assertEqual(len(items), 2)

    def test_02_user_answers_tab_solutions_filter(self):
        """GET /api/users/:id/answers?filter=solutions must only return approved solutions."""
        status, data = self._get_json("/api/users/user_respondent/answers?filter=solutions")
        self.assertEqual(status, 200)
        items = data.get("items", [])
        item_ids = [it["id"] for it in items]

        self.assertIn("ans_approved_sol", item_ids)
        self.assertNotIn("ans_to_rejected", item_ids)  # is_solution=1 but question rejected!
        self.assertNotIn("ans_draftlink", item_ids)    # not a solution
        self.assertNotIn("ans_orphan", item_ids)       # is_solution=1 but question non-existent!
        self.assertEqual(len(items), 1)

    def test_03_user_activity_tab_excludes_unapproved_and_non_questions(self):
        """GET /api/users/:id/activity must not leak answers to rejected/pending/draft materials."""
        status, data = self._get_json("/api/users/user_respondent/activity")
        self.assertEqual(status, 200)
        items = data.get("activity") or data.get("items") or []
        answer_items = [it for it in items if it.get("type") == "answer" or it.get("activityType") == "answer"]
        item_ids = [it["id"] for it in answer_items]

        self.assertIn("ans_approved_sol", item_ids)
        self.assertIn("ans_draftlink", item_ids)
        self.assertNotIn("ans_to_rejected", item_ids)
        self.assertNotIn("ans_to_pending", item_ids)
        self.assertNotIn("ans_to_article", item_ids)
        self.assertNotIn("ans_orphan", item_ids)

    def test_04_user_profile_stats_and_top_contributions(self):
        """GET /api/users/:id must reflect accurate answer counts and approved top solutions."""
        status, data = self._get_json("/api/users/user_respondent")
        self.assertEqual(status, 200)
        user = data.get("user", {})
        stats = user.get("stats", {})

        # answersCount must be exactly 2
        self.assertEqual(stats.get("answersCount"), 2)
        self.assertEqual(stats.get("solutionsCount"), 1)

        # topContributions must only have the approved solution
        top = user.get("topContributions", [])
        top_ids = [it.get("id") for it in top]
        self.assertIn("ans_approved_sol", top_ids)
        self.assertNotIn("ans_to_rejected", top_ids)
        self.assertNotIn("ans_orphan", top_ids)

    def test_05_invariants_no_emojis(self):
        """Zero emojis across test file and server code."""
        emoji_pattern = re.compile(
            r"[\U00010000-\U0010ffff]|"
            r"[\u2600-\u27bf]|"
            r"[\u2300-\u23ff]|"
            r"[\u2b50-\u2b55]"
        )
        with open(__file__, "r", encoding="utf-8") as f:
            test_content = f.read()
        self.assertFalse(bool(emoji_pattern.search(test_content)), "Found emoji in test file!")

    def test_06_invariants_no_em_dashes(self):
        """Zero em dashes (\\u2014) across test file."""
        with open(__file__, "r", encoding="utf-8") as f:
            test_content = f.read()
        self.assertNotIn("\u2014", test_content, "Found em dash (\\u2014) in test file!")


if __name__ == "__main__":
    unittest.main()
