#!/usr/bin/env python3
"""
tests/test_issue170_full_profile_navigation_overview.py

Automated test suite for Issue #170:
[P0][frontend/backend] Full Profile: навигация, вкладка «Обзор» и единая лента активности автора.

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

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue170FullProfileNavigationOverview(unittest.TestCase):
    """Verifies all backend endpoints, markup, styles, interactions and invariants for Issue #170."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue170.db")
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
        author_id = "author_alice"
        t0 = (now - datetime.timedelta(days=120)).isoformat()
        cur.execute("""
            INSERT OR REPLACE INTO user_profiles (user_id, name, specialization, company, bio, avatar, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            author_id,
            "Алиса Инженерова",
            "Smart Contract Lead",
            "OpenChain Labs",
            "Строю надежные децентрализованные протоколы.",
            None,
            t0,
            t0
        ))

        # 2. Approved publications (articles)
        # Article 1: 5 upvotes, 2 comments
        t1 = (now - datetime.timedelta(days=10)).isoformat()
        cur.execute("""
            INSERT INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'approved', ?, 'hash101', ?, ?)
        """, (
            "art_101",
            "draft_101",
            author_id,
            "Глубокий анализ безопасности ERC-4337",
            "<p>Полное руководство по безопасности абстракции учетных записей и верификации пеймастеров.</p>",
            json.dumps({"materialType": "article"}),
            t1,
            t1
        ))
        for i in range(5):
            cur.execute("INSERT INTO article_votes (article_id, user_id, value, created_at, updated_at) VALUES (?, ?, ?, ?, ?)", ("art_101", f"voter_{i}", 1, t1, t1))
        cur.execute("""
            INSERT INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, created_at)
            VALUES ('comm_1', 'art_101', 'user_bob', 'Bob', 'Отличная статья!', 'published', 'comment', ?)
        """, (t1,))
        cur.execute("""
            INSERT INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, created_at)
            VALUES ('comm_2', 'art_101', 'user_charlie', 'Charlie', 'Спасибо за детали.', 'published', 'comment', ?)
        """, (t1,))

        # Article 2: 2 upvotes
        t2 = (now - datetime.timedelta(days=5)).isoformat()
        cur.execute("""
            INSERT INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'approved', ?, 'hash102', ?, ?)
        """, (
            "art_102",
            "draft_102",
            author_id,
            "Оптимизация газа в EVM компиляторах",
            "<p>Практические паттерны упаковки слотов памяти и ассемблерные вставки Yul.</p>",
            json.dumps({"materialType": "article"}),
            t2,
            t2
        ))
        for i in range(2):
            cur.execute("INSERT INTO article_votes (article_id, user_id, value, created_at, updated_at) VALUES (?, ?, ?, ?, ?)", ("art_102", f"voter_{i}", 1, t2, t2))

        # 3. Approved question: 3 upvotes, 1 answer
        t3 = (now - datetime.timedelta(days=8)).isoformat()
        cur.execute("""
            INSERT INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'approved', ?, 'hash201', ?, ?)
        """, (
            "quest_201",
            "draft_201",
            author_id,
            "Как правильно организовать апгрейд TransparentUpgradeableProxy?",
            "<p>Возникает коллизия селекторов при наследовании интерфейсов админа.</p>",
            json.dumps({"materialType": "question"}),
            t3,
            t3
        ))
        for i in range(3):
            cur.execute("INSERT INTO article_votes (article_id, user_id, value, created_at, updated_at) VALUES (?, ?, ?, ?, ?)", ("quest_201", f"voter_{i}", 1, t3, t3))
        cur.execute("""
            INSERT INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, created_at)
            VALUES ('ans_external', 'quest_201', 'user_external', 'External Dev', 'Используйте UUPS вместо Transparent.', 'published', 'answer', ?)
        """, (t3,))

        # 4. Answers by Alice to another question
        # Target Question created by another user
        t_target = (now - datetime.timedelta(days=15)).isoformat()
        cur.execute("""
            INSERT INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'approved', ?, 'hash_target', ?, ?)
        """, (
            "quest_other",
            "draft_other",
            "user_target_author",
            "Вызов delegatecall в fallback функции: риски?",
            "<p>Вопрос о сохранении контекста msg.sender и storage layout.</p>",
            json.dumps({"materialType": "question"}),
            t_target,
            t_target
        ))

        # Alice's answer 1: accepted solution! 8 upvotes
        t4 = (now - datetime.timedelta(days=3)).isoformat()
        cur.execute("""
            INSERT INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, is_solution, created_at)
            VALUES (?, ?, ?, ?, ?, 'published', 'answer', 1, ?)
        """, (
            "ans_301",
            "quest_other",
            author_id,
            "Алиса Инженерова",
            "<p>Главный риск заключается в перезаписи слота 0 прокси контракта. Рекомендуется использовать ERC-1967 слоты.</p>",
            t4
        ))
        for i in range(8):
            cur.execute("INSERT INTO comment_votes (comment_id, user_id, value, created_at, updated_at) VALUES (?, ?, ?, ?, ?)", ("ans_301", f"voter_{i}", 1, t4, t4))

        # Alice's answer 2: ordinary answer (not solution), 1 upvote on a second question
        t_target2 = (now - datetime.timedelta(days=12)).isoformat()
        cur.execute("""
            INSERT INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'approved', ?, 'hash_target2', ?, ?)
        """, (
            "quest_other_2",
            "draft_other_2",
            "user_target_author_2",
            "Защита от reentrancy в Solidity: ReentrancyGuard vs CEI",
            "<p>Что эффективнее по газу: modifier nonReentrant или checks-effects-interactions?</p>",
            json.dumps({"materialType": "question"}),
            t_target2,
            t_target2
        ))

        t5 = (now - datetime.timedelta(days=1)).isoformat()
        cur.execute("""
            INSERT INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, is_solution, created_at)
            VALUES (?, ?, ?, ?, ?, 'published', 'answer', 0, ?)
        """, (
            "ans_302",
            "quest_other_2",
            author_id,
            "Алиса Инженерова",
            "<p>Также обязательно проверьте защиту от reentrancy в fallback функции.</p>",
            t5
        ))
        cur.execute("INSERT INTO comment_votes (comment_id, user_id, value, created_at, updated_at) VALUES (?, ?, ?, ?, ?)", ("ans_302", "voter_0", 1, t5, t5))

        conn.commit()

    def _http_get(self, path):
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

    def test_01_backend_get_user_activity_aggregation_and_sorting(self):
        """Verify GET /api/users/:id/activity aggregates publications, questions, answers sorted DESC."""
        status, data = self._http_get("/api/users/author_alice/activity")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        activity = data.get("activity", [])

        # Total 5 items: 2 articles, 1 question, 2 answers
        self.assertEqual(data.get("total"), 5)
        self.assertEqual(len(activity), 5)
        self.assertFalse(data.get("hasMore"))

        # Verify sorted strictly DESC by createdAt
        dates = [item["createdAt"] for item in activity]
        self.assertEqual(dates, sorted(dates, reverse=True))

        # Verify item types presence
        types = [item["type"] for item in activity]
        self.assertIn("publication", types)
        self.assertIn("question", types)
        self.assertIn("answer", types)

        # Check solution badge & question context on answer 1
        sol_item = next(it for it in activity if it["id"] == "ans_301")
        self.assertTrue(sol_item["isSolution"])
        self.assertEqual(sol_item["type"], "answer")
        self.assertEqual(sol_item["rating"], 8)
        self.assertIn("Вызов delegatecall", sol_item["title"])
        self.assertIn("article.html?id=quest_other", sol_item["url"])
        self.assertIn("ans_301", sol_item["url"])

        # Check snippet text extraction (no raw HTML tags)
        self.assertNotIn("<p>", sol_item["contentSnippet"])
        self.assertIn("Главный риск заключается", sol_item["contentSnippet"])

    def test_02_backend_get_user_activity_pagination(self):
        """Verify limit and offset pagination on /api/users/:id/activity."""
        # Page 1: limit=2, offset=0
        status, page1 = self._http_get("/api/users/author_alice/activity?limit=2&offset=0")
        self.assertEqual(status, 200)
        self.assertEqual(len(page1["activity"]), 2)
        self.assertEqual(page1["total"], 5)
        self.assertEqual(page1["offset"], 0)
        self.assertEqual(page1["limit"], 2)
        self.assertTrue(page1["hasMore"])

        # Page 2: limit=2, offset=2
        status, page2 = self._http_get("/api/users/author_alice/activity?limit=2&offset=2")
        self.assertEqual(status, 200)
        self.assertEqual(len(page2["activity"]), 2)
        self.assertTrue(page2["hasMore"])

        # Page 3: limit=2, offset=4
        status, page3 = self._http_get("/api/users/author_alice/activity?limit=2&offset=4")
        self.assertEqual(status, 200)
        self.assertEqual(len(page3["activity"]), 1)
        self.assertFalse(page3["hasMore"])

        # Disjoint verification
        ids_p1 = [it["id"] for it in page1["activity"]]
        ids_p2 = [it["id"] for it in page2["activity"]]
        ids_p3 = [it["id"] for it in page3["activity"]]
        all_paged_ids = ids_p1 + ids_p2 + ids_p3
        self.assertEqual(len(all_paged_ids), 5)
        self.assertEqual(len(set(all_paged_ids)), 5)

    def test_03_backend_get_user_activity_404_for_unknown_user(self):
        """Verify 404 response when querying activity for a non-existent user."""
        status, data = self._http_get("/api/users/non_existent_user_9999/activity")
        self.assertEqual(status, 404)
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("code"), "USER_NOT_FOUND")

    def test_04_backend_get_user_profile_top_contributions(self):
        """Verify GET /api/users/:id includes topContributions (top 2-3 rated publications & solutions)."""
        status, data = self._http_get("/api/users/author_alice")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        profile = data.get("profile", {})
        top = profile.get("topContributions", [])

        self.assertIsInstance(top, list)
        self.assertLessEqual(len(top), 3)
        self.assertGreaterEqual(len(top), 2)

        # Alice's top rated items are:
        # 1. ans_301 (rating 8, solution)
        # 2. art_101 (rating 5, article)
        # 3. quest_201 (rating 3, question)
        self.assertEqual(top[0]["id"], "ans_301")
        self.assertEqual(top[0]["rating"], 8)
        self.assertTrue(top[0]["isSolution"])

        self.assertEqual(top[1]["id"], "art_101")
        self.assertEqual(top[1]["rating"], 5)

        self.assertEqual(top[2]["id"], "quest_201")
        self.assertEqual(top[2]["rating"], 3)

        # Verify sorted strictly DESC by rating
        ratings = [it["rating"] for it in top]
        self.assertEqual(ratings, sorted(ratings, reverse=True))

    def test_05_profile_html_tabs_and_panels_markup(self):
        """Verify profile.html markup contains accessible tabs bar, count badges, and tab panels."""
        html_path = os.path.join(FRONTEND_DIR, "profile.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        # Tabs bar accessibility
        self.assertIn('class="profile-tabs-bar"', html)
        self.assertIn('role="tablist"', html)
        self.assertIn('aria-label="Разделы профиля"', html)

        # Tab buttons
        self.assertIn('id="tabBtnOverview"', html)
        self.assertIn('data-tab="overview"', html)
        self.assertIn('id="tabBtnPublications"', html)
        self.assertIn('data-tab="publications"', html)
        self.assertIn('id="tabBtnQuestions"', html)
        self.assertIn('data-tab="questions"', html)
        self.assertIn('id="tabBtnAnswers"', html)
        self.assertIn('data-tab="answers"', html)

        # Tab count badges
        self.assertIn('id="tabCountPublications"', html)
        self.assertIn('id="tabCountQuestions"', html)
        self.assertIn('id="tabCountAnswers"', html)

        # Panels
        self.assertIn('id="profileTabOverview"', html)
        self.assertIn('id="profileTabPublications"', html)
        self.assertIn('id="profileTabQuestions"', html)
        self.assertIn('id="profileTabAnswers"', html)

        # Overview components: Top contributions & Activity feed
        self.assertIn('id="profileTopContributionsSection"', html)
        self.assertIn('id="profileTopContributionsGrid"', html)
        self.assertIn('Лучший вклад', html)
        self.assertIn('id="profileActivitySection"', html)
        self.assertIn('id="profileActivityFeed"', html)
        self.assertIn('Лента активности', html)
        self.assertIn('id="btnProfileLoadMore"', html)
        self.assertIn('Показать еще', html)

        # Backwards compatible container exists
        self.assertIn('id="profileArticlesList"', html)

    def test_06_profile_page_js_tab_and_feed_logic(self):
        """Verify profile-page.js implements tab switching, query parameter sync, and activity stream."""
        js_path = os.path.join(FRONTEND_DIR, "js", "profile-page.js")
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()

        # Tab switching & query sync
        self.assertIn("setActiveTab", js)
        self.assertIn("tabBtnOverview", js)
        self.assertIn("tabBtnPublications", js)
        self.assertIn("tabBtnQuestions", js)
        self.assertIn("tabBtnAnswers", js)
        self.assertIn("history.replaceState", js)
        self.assertIn("searchParams.set('tab'", js)
        self.assertIn("searchParams.delete('tab'", js)

        # Top contributions rendering
        self.assertIn("renderTopContributions", js)
        self.assertIn("profileTopContributionsSection", js)
        self.assertIn("profileTopContributionsGrid", js)
        self.assertIn("top-contribution-card", js)

        # Activity stream loader and rendering
        self.assertIn("loadActivity", js)
        self.assertIn("/api/users/", js)
        self.assertIn("/activity", js)
        self.assertIn("renderActivityFeed", js)
        self.assertIn("btnProfileLoadMore", js)
        self.assertIn("activity-card", js)
        self.assertIn("activity-solution-badge", js)

        # Module exports
        self.assertIn("setActiveTab: setActiveTab", js)
        self.assertIn("loadActivity: loadActivity", js)
        self.assertIn("renderTopContributions: renderTopContributions", js)
        self.assertIn("renderActivityFeed: renderActivityFeed", js)

    def test_07_profile_css_tab_and_feed_styles(self):
        """Verify profile.css defines tabs bar, badges, responsive scrolling, and activity layout."""
        css_path = os.path.join(FRONTEND_DIR, "css", "profile.css")
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()

        # Tabs bar styling
        self.assertIn(".profile-tabs-bar", css)
        self.assertIn("overflow-x: auto", css)
        self.assertIn(".profile-tab-btn", css)
        self.assertIn(".profile-tab-btn.is-active", css)
        self.assertIn(".profile-tab-count", css)

        # Panels
        self.assertIn(".profile-tab-panel", css)
        self.assertIn(".profile-tab-panel.is-active", css)

        # Top contributions
        self.assertIn(".profile-top-contributions-grid", css)
        self.assertIn(".top-contribution-card", css)
        self.assertIn(".top-contrib-badge", css)

        # Activity feed
        self.assertIn(".profile-activity-feed", css)
        self.assertIn(".activity-card", css)
        self.assertIn(".activity-type-badge", css)
        self.assertIn(".activity-solution-badge", css)
        self.assertIn(".btn-profile-load-more", css)

    def test_08_invariants_zero_emojis_zero_em_dashes_offline(self):
        """Verify strict invariants: zero emojis, zero em dashes, and 100% offline-first."""
        emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]', flags=re.UNICODE)

        frontend_assets = [
            os.path.join(FRONTEND_DIR, "profile.html"),
            os.path.join(FRONTEND_DIR, "css", "profile.css"),
            os.path.join(FRONTEND_DIR, "js", "profile-page.js"),
        ]

        all_files = frontend_assets + [
            os.path.join(PROJECT_ROOT, "tests", "test_issue170_full_profile_navigation_overview.py")
        ]

        for filepath in all_files:
            self.assertTrue(os.path.exists(filepath), f"File {filepath} must exist")
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Zero emojis
            self.assertIsNone(
                emoji_pattern.search(content),
                f"Emoji found in {os.path.basename(filepath)}"
            )

            # Zero em dashes
            self.assertNotIn(
                "\u2014", content,
                f"Em dash found in {os.path.basename(filepath)}"
            )

        for filepath in frontend_assets:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            clean_content = content.replace("http://www.w3.org/2000/svg", "")
            self.assertNotIn("http://", clean_content, f"External http link found in {os.path.basename(filepath)}")
            self.assertNotIn("https://", clean_content, f"External https link found in {os.path.basename(filepath)}")


if __name__ == "__main__":
    unittest.main()
