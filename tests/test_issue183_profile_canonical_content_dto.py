#!/usr/bin/env python3
"""
tests/test_issue183_profile_canonical_content_dto.py

Automated test suite for Issue #183:
[P1][fullstack][PROFILE] Канонические типы контента (question vs others), DTO-согласование card.js (score, myVote, focal point).

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


class TestIssue183ProfileCanonicalContentDto(unittest.TestCase):
    """Verifies canonical content types, card.js DTO alignment, draft_id aggregation, and registration date stability."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue183.db")
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
        t_base = (now - datetime.timedelta(days=20)).isoformat()

        # 1. Author with known registration date
        author_id = "user_dto_author"
        cur.execute("""
            INSERT OR REPLACE INTO user_profiles (user_id, name, specialization, company, bio, avatar, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            author_id,
            "Михаил Согласованный",
            "Fullstack Architect",
            "Contractum Labs",
            "Архитектура фронтенда и контрактов.",
            None,
            t_base,
            t_base
        ))

        # 2. Author with NO registration date in any table (to test stable unknown date handling)
        cur.execute("""
            INSERT OR REPLACE INTO user_profiles (user_id, name, specialization, company, bio, avatar, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, '', '')
        """, (
            "user_no_date",
            "Бессмертный Разработчик",
            "Core Contributor",
            "DAO",
            "Дата регистрации неизвестна.",
            None
        ))

        # 3. Regular Article with focal point and cover
        t_art1 = (now - datetime.timedelta(days=10)).isoformat()
        cur.execute("""
            INSERT INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'approved', ?, 'h_art1', ?, ?)
        """, (
            "art_canonical_1",
            "draft_art1",
            author_id,
            "Оптимизация хранения в EVM",
            "<p>Разбор slot packing и transient storage.</p>",
            json.dumps({
                "materialType": "article",
                "topics": ["ethereum", "solidity"],
                "coverImage": "images/covers/cover-1.svg",
                "focalPoint": "60% 40%"
            }),
            t_art1,
            t_art1
        ))

        # 4. Legacy Question with {"type": "question"} (missing materialType property)
        t_q_legacy = (now - datetime.timedelta(days=8)).isoformat()
        cur.execute("""
            INSERT INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'approved', ?, 'h_q_legacy', ?, ?)
        """, (
            "q_legacy_type",
            "draft_q_legacy",
            author_id,
            "Как работает CREATE3 в Solidity?",
            "<p>Вопрос о детерминированном развертывании.</p>",
            json.dumps({
                "type": "question",
                "topics": ["solidity"]
            }),
            t_q_legacy,
            t_q_legacy
        ))

        # 5. Canonical Question with {"materialType": "question"}
        t_q_canon = (now - datetime.timedelta(days=6)).isoformat()
        cur.execute("""
            INSERT INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'approved', ?, 'h_q_canon', ?, ?)
        """, (
            "q_canon_type",
            "draft_q_canon",
            author_id,
            "Как правильно проверять подписи EIP-712?",
            "<p>Вопрос по стандарту EIP-712.</p>",
            json.dumps({
                "materialType": "question",
                "topics": ["security"]
            }),
            t_q_canon,
            t_q_canon
        ))

        # Interactions from voter:
        # Votes on art_canonical_1: 1 vote on id, 1 vote on draft_art1 (legacy split)
        cur.execute("INSERT INTO article_votes (user_id, article_id, value, created_at, updated_at) VALUES ('voter_1', 'art_canonical_1', 1, ?, ?)", (t_art1, t_art1))
        cur.execute("INSERT INTO article_votes (user_id, article_id, value, created_at, updated_at) VALUES ('voter_2', 'draft_art1', 1, ?, ?)", (t_art1, t_art1))

        # Comments on art_canonical_1: 1 on id, 1 on draft_art1
        cur.execute("""
            INSERT INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, created_at)
            VALUES ('comm_art_1', 'art_canonical_1', 'user_c1', 'Dev 1', 'Отличная статья!', 'published', 'comment', ?)
        """, (t_art1,))
        cur.execute("""
            INSERT INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, created_at)
            VALUES ('comm_art_2', 'draft_art1', 'user_c2', 'Dev 2', 'Согласен.', 'published', 'comment', ?)
        """, (t_art1,))

        # Saves and likes on art_canonical_1
        cur.execute("INSERT INTO article_saves (user_id, article_id, created_at) VALUES ('user_viewer', 'art_canonical_1', ?)", (t_art1,))
        cur.execute("INSERT INTO article_likes (user_id, article_id, created_at) VALUES ('user_viewer', 'art_canonical_1', ?)", (t_art1,))
        cur.execute("INSERT INTO article_votes (user_id, article_id, value, created_at, updated_at) VALUES ('user_viewer', 'art_canonical_1', 1, ?, ?)", (t_art1, t_art1))

        # Viewer session
        cur.execute("INSERT INTO sessions (token, user_id, user_name, user_role, expires_at, created_at) VALUES ('sess_viewer', 'user_viewer', 'Тестовый Читатель', 'user', '2030-01-01', ?)", (t_base,))

        conn.commit()

    def _login_cookie(self):
        return "sc_session=sess_viewer"

    def _get_json(self, path: str, cookie: str = None):
        url = f"{self.base_url}{path}"
        headers = {}
        if cookie:
            headers["Cookie"] = cookie
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req) as resp:
            data = resp.read().decode("utf-8")
            return resp.status, json.loads(data) if data else {}

    def test_01_legacy_question_strictly_in_questions_not_in_publications(self):
        """Legacy question with {'type': 'question'} must be excluded from publications and included in questions."""
        # 1. Publications tab
        status, pubs_data = self._get_json("/api/users/user_dto_author/publications")
        self.assertEqual(status, 200)
        pub_ids = [it["id"] for it in pubs_data.get("items", [])]
        self.assertIn("art_canonical_1", pub_ids)
        self.assertNotIn("q_legacy_type", pub_ids, "Legacy question must NOT appear in publications!")
        self.assertNotIn("q_canon_type", pub_ids, "Canonical question must NOT appear in publications!")
        self.assertEqual(pubs_data.get("total"), 1)

        # 2. Questions tab
        status, quest_data = self._get_json("/api/users/user_dto_author/questions")
        self.assertEqual(status, 200)
        quest_ids = [it["id"] for it in quest_data.get("items", [])]
        self.assertIn("q_legacy_type", quest_ids, "Legacy question must appear in questions!")
        self.assertIn("q_canon_type", quest_ids, "Canonical question must appear in questions!")
        self.assertNotIn("art_canonical_1", quest_ids)
        self.assertEqual(quest_data.get("total"), 2)

    def test_02_legacy_question_appears_only_once_in_activity(self):
        """Legacy question must appear exactly once in GET /api/users/:id/activity (as question)."""
        status, act_data = self._get_json("/api/users/user_dto_author/activity")
        self.assertEqual(status, 200)
        items = act_data.get("activity") or act_data.get("items") or []

        q_legacy_items = [it for it in items if it.get("id") == "q_legacy_type"]
        self.assertEqual(len(q_legacy_items), 1, "Legacy question must appear exactly once in activity!")
        self.assertEqual(q_legacy_items[0].get("type"), "question")

    def test_03_card_js_dto_fields_publications(self):
        """Publications endpoint must provide score, rating, myVote, focalPoint, isSaved, hasLiked, etc."""
        cookie = self._login_cookie()
        status, data = self._get_json("/api/users/user_dto_author/publications", cookie=cookie)
        self.assertEqual(status, 200)
        items = data.get("items", [])
        self.assertEqual(len(items), 1)
        art = items[0]

        # Score and rating must match and account for draft_id votes (1 + 1 + 1 = 3)
        self.assertEqual(art.get("score"), 3)
        self.assertEqual(art.get("rating"), 3)

        # Comments count must account for draft_id comments (1 + 1 = 2)
        self.assertEqual(art.get("commentsCount"), 2)

        # Viewer states
        self.assertEqual(art.get("myVote"), 1)
        self.assertTrue(art.get("isSaved"))
        self.assertTrue(art.get("hasSaved"))
        self.assertTrue(art.get("isLiked"))
        self.assertTrue(art.get("hasLiked"))

        # Focal point / cover position
        self.assertEqual(art.get("coverPosition"), "60% 40%")
        self.assertEqual(art.get("focalPoint"), "60% 40%")
        self.assertEqual(art.get("objectPosition"), "60% 40%")

    def test_04_unknown_registration_date_returns_none(self):
        """When user registration date is unknown, API must return None and NOT current timestamp."""
        status, data = self._get_json("/api/users/user_no_date")
        self.assertEqual(status, 200)
        user = data.get("user") or data.get("profile") or {}
        self.assertIsNone(user.get("createdAt"), "createdAt must be None when unknown!")
        self.assertIsNone(user.get("date"), "date must be None when unknown!")

    def test_05_profile_html_no_fake_today_or_nedavno(self):
        """profile.html and profile-page.js must not contain 'На платформе с недавно'."""
        with open(os.path.join(FRONTEND_DIR, "profile.html"), "r", encoding="utf-8") as f:
            html = f.read()
        self.assertNotIn("На платформе с недавно", html)

        with open(os.path.join(FRONTEND_DIR, "js", "profile-page.js"), "r", encoding="utf-8") as f:
            js = f.read()
        self.assertNotIn("'недавно'", js.lower())

    def test_06_top_contributions_score_and_draft_id_aggregation(self):
        """topContributions in user profile must include score and aggregate draft_id votes and comments."""
        status, data = self._get_json("/api/users/user_dto_author")
        self.assertEqual(status, 200)
        user = data.get("user") or {}
        top = user.get("topContributions", [])
        self.assertTrue(len(top) > 0)
        top_art = next((it for it in top if it.get("id") == "art_canonical_1"), None)
        self.assertIsNotNone(top_art)
        self.assertEqual(top_art.get("score"), 3)
        self.assertEqual(top_art.get("rating"), 3)
        self.assertEqual(top_art.get("commentsCount"), 2)

    def test_07_invariants_no_emojis(self):
        """Zero emojis across test file and changes."""
        emoji_pattern = re.compile(
            r"[\U00010000-\U0010ffff]|"
            r"[\u2600-\u27bf]|"
            r"[\u2300-\u23ff]|"
            r"[\u2b50-\u2b55]"
        )
        with open(__file__, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertFalse(bool(emoji_pattern.search(content)), "Found emoji in test file!")

    def test_08_invariants_no_em_dashes(self):
        """Zero em dashes (\\u2014) across test file."""
        with open(__file__, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn("\u2014", content, "Found em dash (\\u2014) in test file!")


if __name__ == "__main__":
    unittest.main()
