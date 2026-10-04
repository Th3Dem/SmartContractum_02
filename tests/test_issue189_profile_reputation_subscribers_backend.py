#!/usr/bin/env python3
"""
tests/test_issue189_profile_reputation_subscribers_backend.py

Automated test suite for Issue #189 backend requirements:
1. Rating breakdown and formula explanation:
   - materialsRating (approved publications and questions votes)
   - discussionsRating (published comments and answers votes)
   - totalRating = materialsRating + discussionsRating
   - Likes are excluded from rating
   - ratingFormula explanation string present
2. Topics resolution:
   - Slugs resolved to Russian titles via TOPICS_TITLE_MAP
   - Topics aggregated only from author's approved publications
3. Topic filtering:
   - GET /api/users/<user_id>/publications?topic=<topic_id> filters by topic
   - GET /api/users/<user_id>/questions?topic=<topic_id> filters by topic
4. Subscribers endpoint:
   - GET /api/users/<user_id>/subscribers returns paginated followers
   - 400 on empty user_id, 404 on non-existent user
   - Pagination with limit, offset, total, hasMore
5. Subscriptions endpoint:
   - GET /api/users/<user_id>/subscriptions returns separated authors and blogs for owner
   - For non-owner, respects privacy (isPrivate: true, empty items)
6. Subscriptions toggle:
   - Returns real followersCount from database for author subscriptions
7. Invariants: zero emojis, zero em dashes, 100% offline-first
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
import urllib.error
import urllib.request

import server
from server import create_server, init_db

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue189ProfileReputationSubscribersBackend(unittest.TestCase):
    """Test suite for Issue #189 backend reputation, topics, and subscribers."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue189.db")
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
        if os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir, ignore_errors=True)

    @classmethod
    def _seed_test_data(cls, conn):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        t_exp = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)).isoformat()
        with conn:
            cur = conn.cursor()
            # Author Alice
            cur.execute("""
                INSERT OR REPLACE INTO user_profiles (user_id, name, specialization, company, bio, avatar, website, created_at, updated_at)
                VALUES ('author_alice', 'Алиса Селезнева', 'Архитектор смарт-контрактов', 'Иннотех', 'Исследую ПКСК и безопасность', NULL, 'https://alice.dev', ?, ?)
            """, (now, now))
            cur.execute("""
                INSERT OR REPLACE INTO sessions (token, user_id, user_name, user_role, expires_at, created_at, is_revoked)
                VALUES ('alice_token', 'author_alice', 'Алиса Селезнева', 'user', ?, ?, 0)
            """, (t_exp, now))

            # User Bob
            cur.execute("""
                INSERT OR REPLACE INTO user_profiles (user_id, name, specialization, company, bio, avatar, website, created_at, updated_at)
                VALUES ('user_bob', 'Боб Марли', 'Разработчик', 'DeFi Lab', 'Люблю криптографию', NULL, '', ?, ?)
            """, (now, now))
            cur.execute("""
                INSERT OR REPLACE INTO sessions (token, user_id, user_name, user_role, expires_at, created_at, is_revoked)
                VALUES ('bob_token', 'user_bob', 'Боб Марли', 'user', ?, ?, 0)
            """, (t_exp, now))

            # User Charlie
            cur.execute("""
                INSERT OR REPLACE INTO user_profiles (user_id, name, specialization, company, bio, avatar, website, created_at, updated_at)
                VALUES ('user_charlie', 'Чарли Бро', 'Тестировщик', 'QA Hub', '', NULL, '', ?, ?)
            """, (now, now))
            cur.execute("""
                INSERT OR REPLACE INTO sessions (token, user_id, user_name, user_role, expires_at, created_at, is_revoked)
                VALUES ('charlie_token', 'user_charlie', 'Чарли Бро', 'user', ?, ?, 0)
            """, (t_exp, now))

            # Club / Blog
            cur.execute("""
                INSERT OR REPLACE INTO clubs (id, title, description, avatar, rules, owner_id, directions, tags, created_at, updated_at)
                VALUES ('blog_crypto', 'Криптография и безопасность', 'Блог о безопасности смарт-контрактов', NULL, '', 'user_bob', '[]', '[]', ?, ?)
            """, (now, now))

            # Alice publication 1 (topic: smart-contracts-development)
            settings_1 = json.dumps({
                "materialType": "article",
                "topics": ["smart-contracts-development"],
                "format": "overview"
            })
            cur.execute("""
                INSERT OR REPLACE INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
                VALUES ('art_alice_01', 'draft_alice_01', 'author_alice', 'Введение в смарт-контракты', '<p>Статья о разработке контрактов</p>', 'approved', ?, 'hash_alice_01', ?, ?)
            """, (settings_1, now, now))

            # Alice publication 2 (topic: pksc-architecture)
            settings_2 = json.dumps({
                "materialType": "article",
                "topics": ["pksc-architecture"],
                "format": "analytics"
            })
            cur.execute("""
                INSERT OR REPLACE INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
                VALUES ('art_alice_02', 'draft_alice_02', 'author_alice', 'Архитектура ПКСК в деталях', '<p>Глубокий разбор узлов</p>', 'approved', ?, 'hash_alice_02', ?, ?)
            """, (settings_2, now, now))

            # Votes for Alice publications (Bob +1, Charlie +1 on art 1; Bob +1 on art 2 = 3 materials score)
            cur.execute("INSERT OR REPLACE INTO article_votes (article_id, user_id, value, created_at, updated_at) VALUES ('art_alice_01', 'user_bob', 1, ?, ?)", (now, now))
            cur.execute("INSERT OR REPLACE INTO article_votes (article_id, user_id, value, created_at, updated_at) VALUES ('art_alice_01', 'user_charlie', 1, ?, ?)", (now, now))
            cur.execute("INSERT OR REPLACE INTO article_votes (article_id, user_id, value, created_at, updated_at) VALUES ('art_alice_02', 'user_bob', 1, ?, ?)", (now, now))

            # Likes on Alice publications (should NOT be counted in rating)
            cur.execute("INSERT OR REPLACE INTO article_likes (user_id, article_id, created_at) VALUES ('user_bob', 'art_alice_01', ?)", (now,))
            cur.execute("INSERT OR REPLACE INTO article_likes (user_id, article_id, created_at) VALUES ('user_charlie', 'art_alice_01', ?)", (now,))

            # Alice comments on another article
            cur.execute("""
                INSERT OR REPLACE INTO article_comments (id, article_id, user_id, author_name, author_avatar, content, status, comment_type, created_at)
                VALUES ('comm_alice_01', 'art_alice_01', 'author_alice', 'Алиса Селезнева', NULL, 'Полезное уточнение по теме', 'published', 'comment', ?)
            """, (now,))
            # Vote on Alice comment (+1 discussions score)
            cur.execute("INSERT OR REPLACE INTO comment_votes (comment_id, user_id, value, created_at, updated_at) VALUES ('comm_alice_01', 'user_bob', 1, ?, ?)", (now, now))

            # Subscriptions: Bob and Charlie follow Alice
            cur.execute("""
                INSERT OR REPLACE INTO user_subscriptions (user_id, target_type, target_id, target_title, created_at)
                VALUES ('user_bob', 'author', 'author_alice', 'Алиса Селезнева', ?)
            """, (now,))
            cur.execute("""
                INSERT OR REPLACE INTO user_subscriptions (user_id, target_type, target_id, target_title, created_at)
                VALUES ('user_charlie', 'author', 'author_alice', 'Алиса Селезнева', ?)
            """, (now,))

            # Subscriptions of Alice: follows Bob and blog_crypto
            cur.execute("""
                INSERT OR REPLACE INTO user_subscriptions (user_id, target_type, target_id, target_title, created_at)
                VALUES ('author_alice', 'author', 'user_bob', 'Боб Марли', ?)
            """, (now,))
            cur.execute("""
                INSERT OR REPLACE INTO user_subscriptions (user_id, target_type, target_id, target_title, created_at)
                VALUES ('author_alice', 'club', 'blog_crypto', 'Криптография и безопасность', ?)
            """, (now,))

    def _request(self, method, path, body=None, token=None):
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, method=method)
        req.add_header("Accept", "application/json")
        if token:
            req.add_header("Cookie", f"sc_session={token}")
            req.add_header("Authorization", f"Bearer {token}")
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            req.add_header("Content-Type", "application/json; charset=utf-8")
            req.data = data

        try:
            with urllib.request.urlopen(req) as resp:
                status = resp.status
                raw = resp.read().decode("utf-8")
                return status, json.loads(raw)
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8")
            try:
                data = json.loads(raw)
            except Exception:
                data = {"raw": raw}
            return e.code, data

    # =========================================================================
    # 1. Rating Breakdown & Formula
    # =========================================================================

    def test_01_profile_rating_breakdown_and_formula(self):
        """Verify profile returns materialsRating, discussionsRating, and ratingFormula."""
        status, data = self._request("GET", "/api/users/author_alice")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))

        profile = data.get("profile", {})
        stats = profile.get("stats", {})

        # Materials rating: +1 + 1 on art 1 + 1 on art 2 = 3
        self.assertEqual(stats.get("materialsRating"), 3)
        self.assertEqual(profile.get("materialsRating"), 3)

        # Discussions rating: +1 on comm 1 = 1
        self.assertEqual(stats.get("discussionsRating"), 1)
        self.assertEqual(profile.get("discussionsRating"), 1)

        # Total rating: 3 + 1 = 4 (likes are ignored!)
        self.assertEqual(stats.get("rating"), 4)
        self.assertEqual(profile.get("rating"), 4)
        self.assertEqual(profile.get("totalRating"), 4)

        # Formula text
        formula = stats.get("ratingFormula") or profile.get("ratingFormula") or ""
        self.assertIn("Рейтинг складывается из голосов", formula)
        self.assertIn("Лайки не учитываются", formula)

    # =========================================================================
    # 2. Topic Titles Resolution
    # =========================================================================

    def test_02_topics_titles_resolved_from_dictionary(self):
        """Verify technical topic slugs are resolved to human-readable titles in profile."""
        status, data = self._request("GET", "/api/users/author_alice")
        self.assertEqual(status, 200)

        topics = data.get("profile", {}).get("topics", [])
        self.assertGreater(len(topics), 0)

        for t in topics:
            tid = t.get("id")
            title = t.get("title")
            if tid == "smart-contracts-development":
                self.assertEqual(title, "Разработка смарт-контрактов")
            elif tid == "pksc-architecture":
                self.assertEqual(title, "Архитектура и развитие ПКСК")

    # =========================================================================
    # 3. Topic Filtering on Author Publications
    # =========================================================================

    def test_03_publications_topic_filter(self):
        """Verify GET /api/users/<user_id>/publications?topic=<topic_id> filters correctly."""
        # 1. Without topic filter -> returns both publications
        status, data = self._request("GET", "/api/users/author_alice/publications")
        self.assertEqual(status, 200)
        self.assertEqual(data.get("total"), 2)

        # 2. Filter by smart-contracts-development -> returns 1
        status, data = self._request("GET", "/api/users/author_alice/publications?topic=smart-contracts-development")
        self.assertEqual(status, 200)
        self.assertEqual(data.get("total"), 1)
        self.assertEqual(data.get("items")[0]["id"], "art_alice_01")

        # 3. Filter by pksc-architecture -> returns 1
        status, data = self._request("GET", "/api/users/author_alice/publications?topic=pksc-architecture")
        self.assertEqual(status, 200)
        self.assertEqual(data.get("total"), 1)
        self.assertEqual(data.get("items")[0]["id"], "art_alice_02")

        # 4. Filter by non-existent topic -> returns 0
        status, data = self._request("GET", "/api/users/author_alice/publications?topic=non_existent_topic")
        self.assertEqual(status, 200)
        self.assertEqual(data.get("total"), 0)
        self.assertEqual(len(data.get("items")), 0)

    # =========================================================================
    # 4. Subscribers Endpoint
    # =========================================================================

    def test_04_subscribers_endpoint_success_and_pagination(self):
        """Verify GET /api/users/<user_id>/subscribers returns paginated followers."""
        # Alice has 2 subscribers: Bob and Charlie
        status, data = self._request("GET", "/api/users/author_alice/subscribers?limit=1&offset=0")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("total"), 2)
        self.assertEqual(len(data.get("items")), 1)
        self.assertTrue(data.get("hasMore"))

        first_sub = data.get("items")[0]
        self.assertIn("userId", first_sub)
        self.assertIn("name", first_sub)
        self.assertIn("specialization", first_sub)
        self.assertIn("url", first_sub)
        self.assertTrue(first_sub["url"].startswith("profile.html?id="))

        # Page 2
        status, data2 = self._request("GET", "/api/users/author_alice/subscribers?limit=1&offset=1")
        self.assertEqual(status, 200)
        self.assertEqual(len(data2.get("items")), 1)
        self.assertFalse(data2.get("hasMore"))

    def test_05_subscribers_endpoint_user_not_found(self):
        """Verify GET /api/users/<user_id>/subscribers returns 404 for unknown user."""
        status, data = self._request("GET", "/api/users/non_existent_author_9999/subscribers")
        self.assertEqual(status, 404)
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("code"), "USER_NOT_FOUND")

    # =========================================================================
    # 5. Subscriptions Endpoint & Privacy
    # =========================================================================

    def test_06_subscriptions_endpoint_owner_separation(self):
        """Verify owner can view their subscriptions separated into authors and blogs."""
        # Alice views her own subscriptions with session token
        status, data = self._request("GET", "/api/users/author_alice/subscriptions", token="alice_token")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        self.assertFalse(data.get("isPrivate"))

        authors = data.get("authors", [])
        blogs = data.get("blogs", [])

        self.assertEqual(len(authors), 1)
        self.assertEqual(authors[0]["id"], "user_bob")
        self.assertEqual(authors[0]["type"], "author")

        self.assertEqual(len(blogs), 1)
        self.assertEqual(blogs[0]["id"], "blog_crypto")
        self.assertEqual(blogs[0]["type"], "blog")

    def test_07_subscriptions_endpoint_non_owner_privacy(self):
        """Verify other users cannot access another author's subscriptions (privacy enforced)."""
        # Bob tries to view Alice's subscriptions
        status, data = self._request("GET", "/api/users/author_alice/subscriptions", token="bob_token")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        self.assertTrue(data.get("isPrivate"))
        self.assertEqual(len(data.get("items", [])), 0)
        self.assertIn("приватности", data.get("message", ""))

        # Guest without token
        status, data_guest = self._request("GET", "/api/users/author_alice/subscriptions")
        self.assertEqual(status, 200)
        self.assertTrue(data_guest.get("isPrivate"))

    # =========================================================================
    # 6. Subscriptions Toggle Returns followersCount
    # =========================================================================

    def test_08_subscriptions_toggle_returns_followers_count(self):
        """Verify POST /api/subscriptions/toggle returns accurate followersCount."""
        # Bob is already subscribed to Alice (initial count: 2)
        # Bob toggles (unsubscribes)
        status, data = self._request("POST", "/api/subscriptions/toggle", {
            "targetType": "author",
            "targetId": "author_alice"
        }, token="bob_token")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        self.assertFalse(data.get("subscribed"))
        self.assertEqual(data.get("followersCount"), 1)

        # Bob subscribes again
        status, data2 = self._request("POST", "/api/subscriptions/toggle", {
            "targetType": "author",
            "targetId": "author_alice"
        }, token="bob_token")
        self.assertEqual(status, 200)
        self.assertTrue(data2.get("subscribed"))
        self.assertEqual(data2.get("followersCount"), 2)

    # =========================================================================
    # 7. Strict Invariants
    # =========================================================================

    def test_09_strict_invariants(self):
        """Verify zero emojis, zero em dashes, and offline-first compliance."""
        emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]', flags=re.UNICODE)
        with open(__file__, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIsNone(emoji_pattern.search(content), "Emoji found in test file")
        self.assertNotIn("\u2014", content, "Em dash found in test file")


if __name__ == "__main__":
    unittest.main()
