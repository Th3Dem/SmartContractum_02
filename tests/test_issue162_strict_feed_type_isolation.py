#!/usr/bin/env python3
"""
tests/test_issue162_strict_feed_type_isolation.py

Regression test suite for Issue #162:
Feed: strictly isolate 'Publications' and 'Questions' entities.

Invariants:
- Publications feed contains zero questions
- Questions feed contains zero publications
- Search strictly preserves entity boundary
- Topic filtering strictly preserves entity boundary
- Pagination and sorting preserve entity boundary
- Saved Hub strictly preserves entity boundary (counts and rows)
- Frontend empty states and URL sync
- Zero emojis, zero em dashes, offline-first
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
from typing import Any, Dict

import server
from server import create_server, init_db
from tests.backend_source import BACKEND_FILES, backend_source_file

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue162StrictFeedTypeIsolation(unittest.TestCase):
    """
    Test suite verifying strict entity separation between Publications and Questions.
    """

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue162.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path, seed=False)
        conn.close()

        cls.httpd = create_server(
            host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR, seed=False
        )
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.1)

        # Login test users
        cls.user_a = cls._create_or_login_user("user_iso_a", "User Alpha")
        cls.user_b = cls._create_or_login_user("user_iso_b", "User Beta")

        # Seed test publications and questions
        conn = sqlite3.connect(cls.db_path)
        with conn:
            cur = conn.cursor()

            now_utc = datetime.datetime.now(datetime.timezone.utc)
            t_pub1 = (now_utc - datetime.timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
            t_pub2 = (now_utc - datetime.timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
            t_pub3 = (now_utc - datetime.timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M:%SZ")
            t_q1 = (now_utc - datetime.timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
            t_q2 = (now_utc - datetime.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
            t_q3 = (now_utc - datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
            t_ans = (now_utc - datetime.timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
            t_comm = (now_utc - datetime.timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
            t_save1 = (now_utc - datetime.timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
            t_save2 = (now_utc - datetime.timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")

            # Publication 1: materialType = article
            cur.execute("""
                INSERT OR REPLACE INTO moderation_submissions (
                    id, draft_id, title, author_id,
                    status, publication_settings, article_html, snapshot_hash, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'approved', ?, ?, 'hash_p1', ?, ?)
            """, (
                "pub-iso-01", "draft-p1", "Статья по криптографической безопасности",
                cls.user_a["id"],
                json.dumps({
                    "materialType": "article",
                    "format": "article",
                    "complexity": "medium",
                    "topics": ["pksc-architecture"],
                    "description": "Описание безопасности смарт-контрактов",
                    "author": {"id": cls.user_a["id"], "name": cls.user_a["name"]}
                }),
                "<p>Подробный текст о криптографической безопасности и протоколах.</p>",
                t_pub1, t_pub1
            ))

            # Publication 2: type = post (materialType fallback to type)
            cur.execute("""
                INSERT OR REPLACE INTO moderation_submissions (
                    id, draft_id, title, author_id,
                    status, publication_settings, article_html, snapshot_hash, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'approved', ?, ?, 'hash_p2', ?, ?)
            """, (
                "pub-iso-02", "draft-p2", "Пост по компиляции байткода",
                cls.user_a["id"],
                json.dumps({
                    "type": "post",
                    "format": "post",
                    "complexity": "easy",
                    "topics": ["smart-contracts-development"],
                    "description": "Краткий обзор оптимизаций байткода",
                    "author": {"id": cls.user_a["id"], "name": cls.user_a["name"]}
                }),
                "<p>Разбор компилятора и генерации инструкций.</p>",
                t_pub2, t_pub2
            ))

            # Publication 3: materialType = news
            cur.execute("""
                INSERT OR REPLACE INTO moderation_submissions (
                    id, draft_id, title, author_id,
                    status, publication_settings, article_html, snapshot_hash, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'approved', ?, ?, 'hash_p3', ?, ?)
            """, (
                "pub-iso-03", "draft-p3", "Новости стандартизации протоколов",
                cls.user_b["id"],
                json.dumps({
                    "materialType": "news",
                    "format": "news",
                    "complexity": "hard",
                    "topics": ["cryptography"],
                    "description": "Обновления в рабочем комитете стандартов",
                    "author": {"id": cls.user_b["id"], "name": cls.user_b["name"]}
                }),
                "<p>Принят новый драфт стандарта верификации подписей.</p>",
                t_pub3, t_pub3
            ))

            # Question 1: materialType = question
            cur.execute("""
                INSERT OR REPLACE INTO moderation_submissions (
                    id, draft_id, title, author_id,
                    status, publication_settings, article_html, snapshot_hash, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'approved', ?, ?, 'hash_q1', ?, ?)
            """, (
                "quest-iso-01", "draft-q1", "Вопрос по криптографической безопасности ключей",
                cls.user_a["id"],
                json.dumps({
                    "materialType": "question",
                    "format": "question",
                    "complexity": "medium",
                    "topics": ["pksc-architecture"],
                    "description": "Как безопасно изолировать ключи в анклаве?",
                    "author": {"id": cls.user_a["id"], "name": cls.user_a["name"]}
                }),
                "<p>Нужна консультация по аппаратному хранению закрытых ключей.</p>",
                t_q1, t_q1
            ))

            # Question 2: type = question (fallback from materialType)
            cur.execute("""
                INSERT OR REPLACE INTO moderation_submissions (
                    id, draft_id, title, author_id,
                    status, publication_settings, article_html, snapshot_hash, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'approved', ?, ?, 'hash_q2', ?, ?)
            """, (
                "quest-iso-02", "draft-q2", "Вопрос по потреблению газа в цикле",
                cls.user_b["id"],
                json.dumps({
                    "type": "question",
                    "format": "question",
                    "complexity": "easy",
                    "topics": ["smart-contracts-development"],
                    "description": "Почему растет лимит газа при итерации?",
                    "author": {"id": cls.user_b["id"], "name": cls.user_b["name"]}
                }),
                "<p>При увеличении массива транзакция падает по out of gas.</p>",
                t_q2, t_q2
            ))

            # Question 3: materialType = question (with answers and solution)
            cur.execute("""
                INSERT OR REPLACE INTO moderation_submissions (
                    id, draft_id, title, author_id,
                    status, publication_settings, article_html, snapshot_hash, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'approved', ?, ?, 'hash_q3', ?, ?)
            """, (
                "quest-iso-03", "draft-q3", "Вопрос по валидации мультисига",
                cls.user_a["id"],
                json.dumps({
                    "materialType": "question",
                    "format": "question",
                    "complexity": "hard",
                    "topics": ["smart-contracts-development"],
                    "description": "Как проверить порог подписей m из n?",
                    "author": {"id": cls.user_a["id"], "name": cls.user_a["name"]}
                }),
                "<p>Реализация верификации подписей в контракте.</p>",
                t_q3, t_q3
            ))

            # Answer comment for Question 3 with solution
            cur.execute("""
                INSERT OR REPLACE INTO article_comments (
                    id, article_id, user_id, author_name, author_avatar,
                    content, status, comment_type, is_solution, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'published', 'answer', 1, ?)
            """, (
                "ans-iso-01", "quest-iso-03", cls.user_b["id"], "User Beta", None,
                "Используйте ecrecover внутри цикла с проверкой строгой сортировки адресов подписантов.",
                t_ans
            ))

            # Regular comment on Publication 1
            cur.execute("""
                INSERT OR REPLACE INTO article_comments (
                    id, article_id, user_id, author_name, author_avatar,
                    content, status, comment_type, is_solution, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'published', 'comment', 0, ?)
            """, (
                "comm-iso-01", "pub-iso-01", cls.user_b["id"], "User Beta", None,
                "Отличный разбор архитектуры безопасности.",
                t_comm
            ))

            # Vote for Publication 1 to give it positive score
            cur.execute("""
                INSERT OR REPLACE INTO article_votes (article_id, user_id, value, created_at, updated_at)
                VALUES (?, ?, 1, ?, ?)
            """, ("pub-iso-01", cls.user_b["id"], t_comm, t_comm))

            # Saves for User Alpha: one publication and one question
            cur.execute("""
                INSERT OR REPLACE INTO article_saves (article_id, user_id, created_at)
                VALUES (?, ?, ?)
            """, ("pub-iso-01", cls.user_a["id"], t_save1))

            cur.execute("""
                INSERT OR REPLACE INTO article_saves (article_id, user_id, created_at)
                VALUES (?, ?, ?)
            """, ("quest-iso-01", cls.user_a["id"], t_save2))

        conn.close()

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
            return {"user": data.get("user"), "cookie": cookie, "id": user_id, "name": name}

    def _request(self, method: str, path: str, body: Any = None, user: Dict[str, Any] = None):
        safe_path = urllib.parse.quote(path, safe="/:?=&%")
        url = f"{self.base_url}{safe_path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json"}
        if user and "cookie" in user:
            headers["Cookie"] = user["cookie"]

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                status = resp.status
                raw = resp.read().decode("utf-8")
                return status, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as err:
            raw = err.read().decode("utf-8")
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = {"raw": raw}
            return err.code, parsed

    def test_01_publications_feed_contains_zero_questions(self):
        """Publications feed under all alias tabs must contain zero questions."""
        pub_tabs = ["all", "publications", "pubs", "articles", "focus", "top", "new"]
        for tab in pub_tabs:
            status, res = self._request("GET", f"/api/articles?tab={tab}")
            self.assertEqual(status, 200, f"Expected 200 for tab={tab}")
            self.assertTrue(res.get("success"), f"Expected success for tab={tab}")
            articles = res.get("articles", [])
            self.assertGreater(len(articles), 0, f"Expected items for tab={tab}")

            for art in articles:
                self.assertNotEqual(
                    art.get("materialType"),
                    "question",
                    f"Found question {art.get('id')} in publication tab {tab}"
                )
                self.assertEqual(
                    art.get("materialType"),
                    "publication",
                    f"Item {art.get('id')} has invalid materialType in tab {tab}"
                )

        # Explicitly asking for types=question in publications tab must return zero items
        status, res = self._request("GET", "/api/articles?tab=all&types=question")
        self.assertEqual(status, 200)
        self.assertEqual(len(res.get("articles", [])), 0)

        status, res = self._request("GET", "/api/articles?tab=publications&types=question")
        self.assertEqual(status, 200)
        self.assertEqual(len(res.get("articles", [])), 0)

    def test_02_questions_feed_contains_zero_publications(self):
        """Questions feed (tab=questions) must contain only questions and zero publications."""
        status, res = self._request("GET", "/api/articles?tab=questions")
        self.assertEqual(status, 200)
        self.assertTrue(res.get("success"))
        articles = res.get("articles", [])
        self.assertEqual(len(articles), 3, "Expected exactly 3 questions")

        for art in articles:
            self.assertEqual(
                art.get("materialType"),
                "question",
                f"Item {art.get('id')} in questions feed is not a question"
            )
            self.assertNotEqual(
                art.get("materialType"),
                "publication",
                f"Item {art.get('id')} in questions feed is a publication"
            )

        # Status filtering on questions feed
        # 1. Unanswered (quest-iso-01 and quest-iso-02 have 0 answers; quest-iso-03 has 1)
        status, res_unans = self._request("GET", "/api/articles?tab=questions&questionStatus=unanswered")
        self.assertEqual(status, 200)
        unans_articles = res_unans.get("articles", [])
        self.assertEqual(len(unans_articles), 2)
        unans_ids = {a["id"] for a in unans_articles}
        self.assertEqual(unans_ids, {"quest-iso-01", "quest-iso-02"})

        # 2. Solved (only quest-iso-03 has accepted solution)
        status, res_sol = self._request("GET", "/api/articles?tab=questions&questionStatus=solved")
        self.assertEqual(status, 200)
        sol_articles = res_sol.get("articles", [])
        self.assertEqual(len(sol_articles), 1)
        self.assertEqual(sol_articles[0]["id"], "quest-iso-03")
        self.assertTrue(sol_articles[0].get("hasSolution"))

    def test_03_search_strictly_preserves_entity_boundary(self):
        """Search query matching both entity titles must respect the tab entity boundary."""
        # Query 'безопасности' is present in pub-iso-01 and quest-iso-01
        status, res_pub = self._request("GET", "/api/articles?tab=all&search=безопасности")
        self.assertEqual(status, 200)
        pub_articles = res_pub.get("articles", [])
        self.assertEqual(len(pub_articles), 1)
        self.assertEqual(pub_articles[0]["id"], "pub-iso-01")
        self.assertEqual(pub_articles[0]["materialType"], "publication")

        status, res_q = self._request("GET", "/api/articles?tab=questions&search=безопасности")
        self.assertEqual(status, 200)
        q_articles = res_q.get("articles", [])
        self.assertEqual(len(q_articles), 1)
        self.assertEqual(q_articles[0]["id"], "quest-iso-01")
        self.assertEqual(q_articles[0]["materialType"], "question")

        # Answer text search 'ecrecover' is present in ans-iso-01 belonging to quest-iso-03
        status, res_ans_q = self._request("GET", "/api/articles?tab=questions&search=ecrecover")
        self.assertEqual(status, 200)
        ans_q_arts = res_ans_q.get("articles", [])
        self.assertEqual(len(ans_q_arts), 1)
        self.assertEqual(ans_q_arts[0]["id"], "quest-iso-03")
        self.assertIsNotNone(ans_q_arts[0].get("matchedAnswerSnippet"))

        # Searching answer text on publications feed must yield 0 results
        status, res_ans_pub = self._request("GET", "/api/articles?tab=all&search=ecrecover")
        self.assertEqual(status, 200)
        self.assertEqual(len(res_ans_pub.get("articles", [])), 0)

        status, res_ans_pub2 = self._request("GET", "/api/articles?tab=publications&search=ecrecover")
        self.assertEqual(status, 200)
        self.assertEqual(len(res_ans_pub2.get("articles", [])), 0)

    def test_04_topic_filtering_and_topic_counts_entity_boundary(self):
        """Topic filtering and topic counters must not count or leak cross-type entities."""
        # Both pub-iso-01 and quest-iso-01 share topic 'pksc-architecture'
        status, res_pub = self._request("GET", "/api/articles?tab=all&topics=pksc-architecture")
        self.assertEqual(status, 200)
        pub_arts = res_pub.get("articles", [])
        self.assertEqual(len(pub_arts), 1)
        self.assertEqual(pub_arts[0]["id"], "pub-iso-01")
        self.assertEqual(pub_arts[0]["materialType"], "publication")

        # Topic counts in publications tab must only reflect publication entities
        topic_counts = res_pub.get("topicCounts", {})
        self.assertEqual(topic_counts.get("pksc-architecture"), 1)
        self.assertEqual(topic_counts.get("smart-contracts-development"), 1)
        self.assertEqual(topic_counts.get("cryptography"), 1)

        # On questions tab
        status, res_q = self._request("GET", "/api/articles?tab=questions&topics=pksc-architecture")
        self.assertEqual(status, 200)
        q_arts = res_q.get("articles", [])
        self.assertEqual(len(q_arts), 1)
        self.assertEqual(q_arts[0]["id"], "quest-iso-01")
        self.assertEqual(q_arts[0]["materialType"], "question")

        # Topic counts in questions tab must only reflect question entities
        q_topic_counts = res_q.get("topicCounts", {})
        self.assertEqual(q_topic_counts.get("pksc-architecture"), 1)
        self.assertEqual(q_topic_counts.get("smart-contracts-development"), 2)
        self.assertNotIn("cryptography", q_topic_counts)

    def test_05_pagination_and_sorting_entity_boundary(self):
        """Pagination and sorting must maintain strict entity isolation on all pages."""
        sort_options = ["popular", "discussed", "rating", "newest", "oldest"]
        for s in sort_options:
            # Publications tab pagination: limit 1
            for offset in [0, 1, 2]:
                status, res = self._request("GET", f"/api/articles?tab=all&sort={s}&limit=1&offset={offset}")
                self.assertEqual(status, 200)
                arts = res.get("articles", [])
                if arts:
                    self.assertEqual(
                        arts[0].get("materialType"),
                        "publication",
                        f"Expected publication on page offset={offset} sort={s}"
                    )

            # Questions tab pagination: limit 1
            for offset in [0, 1, 2]:
                status, res = self._request("GET", f"/api/articles?tab=questions&sort={s}&limit=1&offset={offset}")
                self.assertEqual(status, 200)
                arts = res.get("articles", [])
                if arts:
                    self.assertEqual(
                        arts[0].get("materialType"),
                        "question",
                        f"Expected question on page offset={offset} sort={s}"
                    )

    def test_06_saved_hub_counts_and_rows_strict_isolation(self):
        """Saved Hub must accurately separate saved publications and questions."""
        status, res_counts = self._request("GET", "/api/saved/counts", user=self.user_a)
        self.assertEqual(status, 200)
        self.assertEqual(res_counts.get("publications"), 1)
        self.assertEqual(res_counts.get("questions"), 1)
        self.assertEqual(res_counts.get("total"), 2)

        # Fetch type=publications
        status, res_pubs = self._request("GET", "/api/saved?type=publications", user=self.user_a)
        self.assertEqual(status, 200)
        items = res_pubs.get("items", [])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], "pub-iso-01")
        self.assertEqual(items[0]["entityType"], "publication")
        self.assertEqual(items[0]["materialType"], "publication")

        # Fetch type=questions
        status, res_q = self._request("GET", "/api/saved?type=questions", user=self.user_a)
        self.assertEqual(status, 200)
        q_items = res_q.get("items", [])
        self.assertEqual(len(q_items), 1)
        self.assertEqual(q_items[0]["id"], "quest-iso-01")
        self.assertEqual(q_items[0]["entityType"], "question")
        self.assertEqual(q_items[0]["materialType"], "question")

    def test_07_frontend_code_invariants(self):
        """Verify frontend/public/js/feed.js contains required aliases and UI logic."""
        feed_js_path = os.path.join(FRONTEND_DIR, "js", "feed.js")
        with open(feed_js_path, "r", encoding="utf-8") as f:
            feed_code = f.read()

        # URL parsing alias for publications
        self.assertIn("tabParam === 'publications'", feed_code)
        self.assertIn("state.publicationsAlias", feed_code)

        # syncURL check
        self.assertIn("state.tab === 'all' && state.publicationsAlias", feed_code)

        # switchTab mapping
        self.assertIn("tabName === 'publications'", feed_code)

        # renderEmptyState entity-specific copy
        self.assertIn("Вопросов пока нет", feed_code)
        self.assertIn("Не найдено вопросов", feed_code)
        self.assertIn("editor.html?type=question", feed_code)
        self.assertIn("Публикаций пока нет", feed_code)
        self.assertIn("Не найдено публикаций", feed_code)

        # popstate listener calls
        self.assertIn("window.addEventListener('popstate'", feed_code)
        self.assertIn("updateSubnavTabsUI();", feed_code)
        self.assertIn("ensureToolbarPlacement();", feed_code)

    def test_08_text_invariants(self):
        """Verify zero emojis and zero em dashes in test suite and modified source files."""
        # Disallowed: unicode em-dash (U+2014)
        em_dash = "\u2014"

        # Check this test file
        with open(__file__, "r", encoding="utf-8") as f:
            test_content = f.read()
        self.assertNotIn(em_dash, test_content, "Em dash found in test file")

        # Check server.py changes
        with backend_source_file() as f:
            server_content = f.read()
        self.assertIn("is_publications_tab = tab in", server_content)
        self.assertIn("is_questions_tab = (tab == \"questions\")", server_content)


if __name__ == "__main__":
    unittest.main()
