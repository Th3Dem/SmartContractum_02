#!/usr/bin/env python3
"""
tests/test_issue171_full_profile_tabs_content.py

Automated test suite for Issue #171:
[P0][frontend/backend] Full Profile: вкладки «Публикации», «Вопросы» и «Ответы» с фильтрацией решений.

Invariants:
- Zero emojis
- Zero em dashes
- 100% offline-first
"""

import datetime
import http.client
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
from tests.backend_source import BACKEND_FILES, backend_source_file

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue171FullProfileTabsContent(unittest.TestCase):
    """Verifies all backend endpoints, markup, styles, interactions and invariants for Issue #171."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue171.db")
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

        # 1. Author user
        author_id = "user_valery"
        t0 = (now - datetime.timedelta(days=100)).isoformat()
        cur.execute("""
            INSERT OR REPLACE INTO user_profiles (user_id, name, specialization, company, bio, avatar, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            author_id,
            "Валерий Соколов",
            "Core Protocol Developer",
            "ZK Research",
            "Разрабатываю модульные роллапы и исследую безопасность смарт-контрактов.",
            None,
            t0,
            t0
        ))

        # 2. Publications (articles) - 3 articles with different dates and ratings
        t_pub1 = (now - datetime.timedelta(days=15)).isoformat()
        cur.execute("""
            INSERT INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'approved', ?, 'h_pub1', ?, ?)
        """, (
            "art_val_1",
            "draft_val_1",
            author_id,
            "Архитектура ZK-Rollup на Starknet",
            "<p>Подробный разбор генерации STARK доказательств и Cairo VM.</p>",
            json.dumps({"materialType": "article", "topics": ["defi", "security"]}),
            t_pub1,
            t_pub1
        ))
        for i in range(12):
            cur.execute("INSERT INTO article_votes (article_id, user_id, value, created_at, updated_at) VALUES (?, ?, 1, ?, ?)",
                        ("art_val_1", f"voter_p1_{i}", t_pub1, t_pub1))

        t_pub2 = (now - datetime.timedelta(days=5)).isoformat()
        cur.execute("""
            INSERT INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'approved', ?, 'h_pub2', ?, ?)
        """, (
            "art_val_2",
            "draft_val_2",
            author_id,
            "Ассемблерные трюки в Solidity Yul",
            "<p>Оптимизация mload и mstore для снижения потребления газа в циклах.</p>",
            json.dumps({"materialType": "article", "topics": ["evm"]}),
            t_pub2,
            t_pub2
        ))
        for i in range(4):
            cur.execute("INSERT INTO article_votes (article_id, user_id, value, created_at, updated_at) VALUES (?, ?, 1, ?, ?)",
                        ("art_val_2", f"voter_p2_{i}", t_pub2, t_pub2))

        t_pub3 = (now - datetime.timedelta(days=1)).isoformat()
        cur.execute("""
            INSERT INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'approved', ?, 'h_pub3', ?, ?)
        """, (
            "art_val_3",
            "draft_val_3",
            author_id,
            "Будущее EIP-4844 и блоб-транзакции",
            "<p>Как прото-данкшардинг снижает комиссии в сетях второго уровня.</p>",
            json.dumps({"materialType": "article", "topics": ["ethereum"]}),
            t_pub3,
            t_pub3
        ))
        # art_val_3 has 1 upvote

        # 3. Questions - 2 questions: one solved, one unsolved
        # Question 1 (Solved): 6 upvotes, 2 answers, 1 marked as solution
        t_q1 = (now - datetime.timedelta(days=12)).isoformat()
        cur.execute("""
            INSERT INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'approved', ?, 'h_q1', ?, ?)
        """, (
            "quest_val_1",
            "draft_q1",
            author_id,
            "Как корректно реализовать Cross-domain Messenger в L2?",
            "<p>Вопрос о защите от повторного воспроизведения транзакций между L1 и L2.</p>",
            json.dumps({"materialType": "question", "topics": ["bridges"]}),
            t_q1,
            t_q1
        ))
        for i in range(6):
            cur.execute("INSERT INTO article_votes (article_id, user_id, value, created_at, updated_at) VALUES (?, ?, 1, ?, ?)",
                        ("quest_val_1", f"voter_q1_{i}", t_q1, t_q1))

        # Add solution to quest_val_1
        cur.execute("""
            INSERT INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, is_solution, created_at)
            VALUES ('ans_sol_1', 'quest_val_1', 'user_expert', 'Expert Dev', 'Используйте nonce-маппинг на стороне шлюза.', 'published', 'answer', 1, ?)
        """, (t_q1,))

        # Question 2 (Unsolved): 2 upvotes, 0 answers
        t_q2 = (now - datetime.timedelta(days=2)).isoformat()
        cur.execute("""
            INSERT INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'approved', ?, 'h_q2', ?, ?)
        """, (
            "quest_val_2",
            "draft_q2",
            author_id,
            "Разрешение споров о валидности в Optimistic Bridge",
            "<p>Какие таймауты финализации являются безопасными при задержках в L1?</p>",
            json.dumps({"materialType": "question", "topics": ["bridges", "security"]}),
            t_q2,
            t_q2
        ))
        for i in range(2):
            cur.execute("INSERT INTO article_votes (article_id, user_id, value, created_at, updated_at) VALUES (?, ?, 1, ?, ?)",
                        ("quest_val_2", f"voter_q2_{i}", t_q2, t_q2))

        # 4. Answers published by Valery to other users' questions
        # External question 1
        t_ext1 = (now - datetime.timedelta(days=20)).isoformat()
        cur.execute("""
            INSERT INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
            VALUES ('quest_ext_1', 'draft_ext_1', 'user_asker_1', 'Проверка подписи EIP-712 в смарт-контракте', '<p>Как защититься от replay attacks?</p>', 'approved', '{"materialType": "question"}', 'h_ext1', ?, ?)
        """, (t_ext1, t_ext1))

        # Valery answer 1: Solved! 15 upvotes
        t_ans1 = (now - datetime.timedelta(days=8)).isoformat()
        cur.execute("""
            INSERT INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, is_solution, created_at)
            VALUES ('ans_val_1', 'quest_ext_1', ?, 'Валерий Соколов', '<p>Необходимо включать chainId и адрес контракта в domainSeparator.</p>', 'published', 'answer', 1, ?)
        """, (author_id, t_ans1))
        for i in range(15):
            cur.execute("INSERT INTO comment_votes (comment_id, user_id, value, created_at, updated_at) VALUES (?, ?, 1, ?, ?)",
                        ("ans_val_1", f"voter_a1_{i}", t_ans1, t_ans1))

        # External question 2
        t_ext2 = (now - datetime.timedelta(days=18)).isoformat()
        cur.execute("""
            INSERT INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
            VALUES ('quest_ext_2', 'draft_ext_2', 'user_asker_2', 'Сравнение ERC-721A и ERC-721PSI', '<p>Какой стандарт экономнее при пакетном минте?</p>', 'approved', '{"materialType": "question"}', 'h_ext2', ?, ?)
        """, (t_ext2, t_ext2))

        # Valery answer 2: Normal answer (not solution). 3 upvotes
        t_ans2 = (now - datetime.timedelta(days=4)).isoformat()
        cur.execute("""
            INSERT INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, is_solution, created_at)
            VALUES ('ans_val_2', 'quest_ext_2', ?, 'Валерий Соколов', '<p>ERC-721A значительно выгоднее при массовом минте за счет отложенной записи владельца.</p>', 'published', 'answer', 0, ?)
        """, (author_id, t_ans2))
        for i in range(3):
            cur.execute("INSERT INTO comment_votes (comment_id, user_id, value, created_at, updated_at) VALUES (?, ?, 1, ?, ?)",
                        ("ans_val_2", f"voter_a2_{i}", t_ans2, t_ans2))

        # 5. Empty author user (no publications, no questions, no answers)
        cur.execute("""
            INSERT OR REPLACE INTO user_profiles (user_id, name, specialization, company, bio, avatar, created_at, updated_at)
            VALUES ('user_empty', 'Новый Пользователь', '', '', '', NULL, ?, ?)
        """, (t0, t0))

        conn.commit()

    def _api_get(self, path):
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req) as resp:
                status = resp.status
                body = resp.read().decode("utf-8")
                return status, json.loads(body)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            try:
                data = json.loads(body)
            except Exception:
                data = {"raw": body}
            return e.code, data

    # =========================================================================
    # Backend Tests: GET /api/users/:id/publications
    # =========================================================================

    def test_publications_endpoint_sorting_and_content(self):
        """Verifies GET /api/users/:id/publications returns only articles with newest and popular sorting."""
        # Newest sort (default)
        status, data = self._api_get("/api/users/user_valery/publications?sort=newest")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        items = data.get("items", [])
        self.assertEqual(len(items), 3)
        self.assertEqual(data.get("total"), 3)
        self.assertFalse(data.get("hasMore"))

        # Verify only articles are returned (no questions)
        for it in items:
            self.assertEqual(it.get("materialType"), "article")

        # In newest sort: art_val_3 (1 day ago) -> art_val_2 (5 days ago) -> art_val_1 (15 days ago)
        self.assertEqual(items[0]["id"], "art_val_3")
        self.assertEqual(items[1]["id"], "art_val_2")
        self.assertEqual(items[2]["id"], "art_val_1")

        # Popular sort: art_val_1 (12 votes) -> art_val_2 (4 votes) -> art_val_3 (0 votes)
        status, data_pop = self._api_get("/api/users/user_valery/publications?sort=popular")
        self.assertEqual(status, 200)
        pop_items = data_pop.get("items", [])
        self.assertEqual(pop_items[0]["id"], "art_val_1")
        self.assertEqual(pop_items[0]["rating"], 12)
        self.assertEqual(pop_items[1]["id"], "art_val_2")
        self.assertEqual(pop_items[1]["rating"], 4)

    def test_publications_endpoint_pagination(self):
        """Verifies limit, offset, and hasMore pagination on publications."""
        status, data = self._api_get("/api/users/user_valery/publications?limit=2&offset=0")
        self.assertEqual(status, 200)
        self.assertEqual(len(data.get("items", [])), 2)
        self.assertEqual(data.get("total"), 3)
        self.assertTrue(data.get("hasMore"))

        status, data_page2 = self._api_get("/api/users/user_valery/publications?limit=2&offset=2")
        self.assertEqual(status, 200)
        self.assertEqual(len(data_page2.get("items", [])), 1)
        self.assertFalse(data_page2.get("hasMore"))

    def test_publications_endpoint_not_found(self):
        """Verifies 404 with USER_NOT_FOUND code for non-existent author."""
        status, data = self._api_get("/api/users/non_existent_author_123/publications")
        self.assertEqual(status, 404)
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("code"), "USER_NOT_FOUND")

    # =========================================================================
    # Backend Tests: GET /api/users/:id/questions
    # =========================================================================

    def test_questions_endpoint_sorting_and_status_filtering(self):
        """Verifies GET /api/users/:id/questions with status filters (all, solved, unsolved)."""
        # All questions
        status, data = self._api_get("/api/users/user_valery/questions?status=all")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        items = data.get("items", [])
        self.assertEqual(len(items), 2)
        self.assertEqual(data.get("total"), 2)

        for it in items:
            self.assertEqual(it.get("materialType"), "question")

        # Solved questions filter
        status, data_solved = self._api_get("/api/users/user_valery/questions?status=solved")
        self.assertEqual(status, 200)
        solved_items = data_solved.get("items", [])
        self.assertEqual(len(solved_items), 1)
        self.assertEqual(solved_items[0]["id"], "quest_val_1")
        self.assertTrue(solved_items[0]["isSolved"])
        self.assertTrue(solved_items[0]["hasSolution"])
        self.assertEqual(solved_items[0]["answersCount"], 1)

        # Unsolved questions filter
        status, data_unsolved = self._api_get("/api/users/user_valery/questions?status=unsolved")
        self.assertEqual(status, 200)
        unsolved_items = data_unsolved.get("items", [])
        self.assertEqual(len(unsolved_items), 1)
        self.assertEqual(unsolved_items[0]["id"], "quest_val_2")
        self.assertFalse(unsolved_items[0]["isSolved"])
        self.assertFalse(unsolved_items[0]["hasSolution"])
        self.assertEqual(unsolved_items[0]["answersCount"], 0)

    def test_questions_endpoint_sorting(self):
        """Verifies questions sorting by newest and popular."""
        # quest_val_2 is newer (2 days ago), quest_val_1 has higher rating (6 vs 2)
        status, data_newest = self._api_get("/api/users/user_valery/questions?sort=newest")
        self.assertEqual(data_newest["items"][0]["id"], "quest_val_2")

        status, data_popular = self._api_get("/api/users/user_valery/questions?sort=popular")
        self.assertEqual(data_popular["items"][0]["id"], "quest_val_1")

    def test_questions_endpoint_not_found(self):
        """Verifies 404 with USER_NOT_FOUND code for non-existent author on questions."""
        status, data = self._api_get("/api/users/non_existent_author_123/questions")
        self.assertEqual(status, 404)
        self.assertEqual(data.get("code"), "USER_NOT_FOUND")

    # =========================================================================
    # Backend Tests: GET /api/users/:id/answers
    # =========================================================================

    def test_answers_endpoint_filtering_and_context(self):
        """Verifies GET /api/users/:id/answers with parent question context and filter (all vs solutions)."""
        # All answers
        status, data = self._api_get("/api/users/user_valery/answers?filter=all")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        items = data.get("items", [])
        self.assertEqual(len(items), 2)
        self.assertEqual(data.get("total"), 2)

        # Check fields
        ans1 = next(it for it in items if it["id"] == "ans_val_1")
        self.assertEqual(ans1["questionId"], "quest_ext_1")
        self.assertEqual(ans1["questionTitle"], "Проверка подписи EIP-712 в смарт-контракте")
        self.assertTrue(ans1["isSolution"])
        self.assertEqual(ans1["rating"], 15)
        self.assertIn("article.html?id=quest_ext_1#comment-ans_val_1", ans1["url"])

        # Solutions only filter
        status, data_sol = self._api_get("/api/users/user_valery/answers?filter=solutions")
        self.assertEqual(status, 200)
        sol_items = data_sol.get("items", [])
        self.assertEqual(len(sol_items), 1)
        self.assertEqual(sol_items[0]["id"], "ans_val_1")
        self.assertTrue(sol_items[0]["isSolution"])

    def test_answers_endpoint_not_found(self):
        """Verifies 404 with USER_NOT_FOUND code for non-existent author on answers."""
        status, data = self._api_get("/api/users/non_existent_author_123/answers")
        self.assertEqual(status, 404)
        self.assertEqual(data.get("code"), "USER_NOT_FOUND")

    # =========================================================================
    # Frontend Markup & Script Tests
    # =========================================================================

    def test_frontend_markup_tabs_and_toolbars(self):
        """Verifies profile.html contains required tabs, toolbars, filter pills, and load more buttons."""
        html_path = os.path.join(FRONTEND_DIR, "profile.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        # Tab buttons
        self.assertIn('id="tabBtnPublications"', html)
        self.assertIn('id="tabBtnQuestions"', html)
        self.assertIn('id="tabBtnAnswers"', html)

        # Tab panels
        self.assertIn('id="profileTabPublications"', html)
        self.assertIn('id="profileTabQuestions"', html)
        self.assertIn('id="profileTabAnswers"', html)

        # Publications toolbar & elements
        self.assertIn('data-pub-sort="newest"', html)
        self.assertIn('data-pub-sort="popular"', html)
        self.assertIn('id="profilePublicationsList"', html)
        self.assertIn('id="btnProfileLoadMorePublications"', html)

        # Questions toolbar & elements
        self.assertIn('data-quest-sort="newest"', html)
        self.assertIn('data-quest-sort="popular"', html)
        self.assertIn('data-quest-status="all"', html)
        self.assertIn('data-quest-status="solved"', html)
        self.assertIn('data-quest-status="unsolved"', html)
        self.assertIn('id="profileQuestionsList"', html)
        self.assertIn('id="btnProfileLoadMoreQuestions"', html)

        # Answers toolbar & elements
        self.assertIn('data-ans-filter="all"', html)
        self.assertIn('data-ans-filter="solutions"', html)
        self.assertIn('id="profileAnswersList"', html)
        self.assertIn('id="btnProfileLoadMoreAnswers"', html)

    def test_frontend_js_loaders_and_empty_states(self):
        """Verifies profile-page.js has dedicated tab loaders, empty states, and exports."""
        js_path = os.path.join(FRONTEND_DIR, "js", "profile-page.js")
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()

        # Empty state strings
        self.assertIn("Пользователь пока не публиковал материалы.", js)
        self.assertIn("Пользователь пока не задавал вопросы.", js)
        self.assertIn("Пользователь пока не публиковал ответы на вопросы.", js)

        # Re-use of SmartContractumCard.createCardElement
        self.assertIn("window.SmartContractumCard.createCardElement", js)

        # Module exports
        self.assertIn("loadPublications: loadPublications", js)
        self.assertIn("renderPublicationsTab: renderPublicationsTab", js)
        self.assertIn("loadQuestions: loadQuestions", js)
        self.assertIn("renderQuestionsTab: renderQuestionsTab", js)
        self.assertIn("loadAnswers: loadAnswers", js)
        self.assertIn("renderAnswersTab: renderAnswersTab", js)

    def test_frontend_css_toolbars_and_cards(self):
        """Verifies profile.css includes styles for tab toolbars, pills, and answer cards."""
        css_path = os.path.join(FRONTEND_DIR, "css", "profile.css")
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()

        self.assertIn(".profile-tab-header", css)
        self.assertIn(".profile-tab-toolbar", css)
        self.assertIn(".profile-filter-pills", css)
        self.assertIn(".profile-filter-pill", css)
        self.assertIn(".profile-filter-pill.is-active", css)
        self.assertIn(".profile-tab-actions", css)
        self.assertIn(".answer-item-card", css)
        self.assertIn(".answer-item-header", css)
        self.assertIn(".answer-badges", css)
        self.assertIn(".solution-badge", css)
        self.assertIn(".answer-question-title", css)
        self.assertIn(".answer-card-snippet", css)
        self.assertIn(".answer-item-footer", css)

    # =========================================================================
    # Strict Invariant Tests
    # =========================================================================

    def test_invariants_zero_emojis(self):
        """Verifies ZERO emojis in all project files modified or created for this issue."""
        emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]')
        files_to_check = [
            *BACKEND_FILES,
            os.path.join(FRONTEND_DIR, "profile.html"),
            os.path.join(FRONTEND_DIR, "js", "profile-page.js"),
            os.path.join(FRONTEND_DIR, "css", "profile.css"),
            os.path.abspath(__file__)
        ]
        for fpath in files_to_check:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
                matches = emoji_pattern.findall(content)
                self.assertEqual(len(matches), 0, f"Found emojis in {fpath}: {matches}")

    def test_invariants_zero_em_dashes(self):
        """Verifies ZERO em dashes in all project files modified or created for this issue."""
        em_dash = "\u2014"
        files_to_check = [
            os.path.join(FRONTEND_DIR, "profile.html"),
            os.path.join(FRONTEND_DIR, "js", "profile-page.js"),
            os.path.join(FRONTEND_DIR, "css", "profile.css"),
            os.path.abspath(__file__)
        ]
        for fpath in files_to_check:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
                self.assertNotIn(em_dash, content, f"Found em dash in {fpath}")

    def test_invariants_offline_first(self):
        """Verifies 100% offline-first architecture with no external CDNs or remote URLs."""
        files_to_check = [
            os.path.join(FRONTEND_DIR, "profile.html"),
            os.path.join(FRONTEND_DIR, "js", "profile-page.js"),
            os.path.join(FRONTEND_DIR, "css", "profile.css")
        ]
        url_pattern = re.compile(r'https?://[^\s"\'<>]+')
        for fpath in files_to_check:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
                urls = url_pattern.findall(content)
                for u in urls:
                    self.assertTrue(
                        "localhost" in u or "127.0.0.1" in u or "schema.org" in u or "w3.org" in u,
                        f"External CDN or remote URL detected in {fpath}: {u}"
                    )


if __name__ == "__main__":
    unittest.main()
