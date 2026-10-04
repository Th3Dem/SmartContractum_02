#!/usr/bin/env python3
"""
tests/test_issue187_profile_comments_backend.py

Automated test suite for Issue #187:
[P1][fullstack][PROFILE] Comments and search across author content.

Verifies:
1. /api/users/<user_id>/comments returns ordinary published comments on approved materials.
2. Comments endpoint supports pagination (limit, offset), sorting (new vs rating), and search query q.
3. Activity feed includes comments alongside publications and questions/answers with correct permalinks.
4. Profile response includes commentsCount and comments_count.
5. Server search parameter q filters publications, questions, and answers by title and content.
6. Invariants: zero emojis, zero em dashes, 100% offline-first.
"""

import datetime
import json
import os
import shutil
import tempfile
import threading
import time
import unicodedata
import unittest
import urllib.parse
import urllib.request

import server
from server import create_server, init_db

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue187ProfileCommentsBackend(unittest.TestCase):
    """Verifies profile comments endpoint, search query q, activity feed, and profile counts."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue187.db")
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
        t_base = (now - datetime.timedelta(days=15)).isoformat()

        # Users
        author_id = "user_author"
        other_id = "user_other"

        cur.execute("""
            INSERT OR REPLACE INTO user_profiles (user_id, name, specialization, company, bio, avatar, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            author_id,
            "Алексей Разработчик",
            "Smart Contract Dev",
            "DeFi Labs",
            "Разработка смарт-контрактов и протоколов.",
            None,
            t_base,
            t_base
        ))

        cur.execute("""
            INSERT OR REPLACE INTO user_profiles (user_id, name, specialization, company, bio, avatar, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            other_id,
            "Мария Тестировщик",
            "QA Engineer",
            "Security Team",
            "Аудит безопасности и тестирование.",
            None,
            t_base,
            t_base
        ))

        # Materials
        # 1. Approved publication by author
        t_pub1 = (now - datetime.timedelta(days=10)).isoformat()
        cur.execute("""
            INSERT INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'approved', ?, 'hash_pub1', ?, ?)
        """, (
            "art_pub_1",
            "draft_pub_1",
            author_id,
            "Архитектура децентрализованных приложений",
            "<p>Подробный разбор архитектуры dApp на стеке Ethereum.</p>",
            json.dumps({"materialType": "article", "topics": ["architecture"]}),
            t_pub1,
            t_pub1
        ))

        # 2. Approved question by author
        t_q1 = (now - datetime.timedelta(days=8)).isoformat()
        cur.execute("""
            INSERT INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'approved', ?, 'hash_q1', ?, ?)
        """, (
            "art_quest_1",
            "draft_quest_1",
            author_id,
            "Оптимизация газа в циклах Solidity",
            "<p>Как оптимизировать вызовы storage внутри цикла?</p>",
            json.dumps({"materialType": "question", "topics": ["solidity"]}),
            t_q1,
            t_q1
        ))

        # 3. Approved question by other user (where author provides answer and comment)
        t_q2 = (now - datetime.timedelta(days=7)).isoformat()
        cur.execute("""
            INSERT INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'approved', ?, 'hash_q2', ?, ?)
        """, (
            "art_quest_2",
            "draft_quest_2",
            other_id,
            "Безопасность delegatecall в прокси-контрактах",
            "<p>Какие опасности несет неаккуратное использование delegatecall?</p>",
            json.dumps({"materialType": "question", "topics": ["security"]}),
            t_q2,
            t_q2
        ))

        # 4. Rejected article
        t_rej = (now - datetime.timedelta(days=6)).isoformat()
        cur.execute("""
            INSERT INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'rejected', ?, 'hash_rej', ?, ?)
        """, (
            "art_rejected_1",
            "draft_rej_1",
            other_id,
            "Отклоненный материал по спаму",
            "<p>Непрошедший спам.</p>",
            json.dumps({"materialType": "article", "topics": ["general"]}),
            t_rej,
            t_rej
        ))

        # 5. Pending moderation article
        t_pend = (now - datetime.timedelta(days=5)).isoformat()
        cur.execute("""
            INSERT INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'pending_moderation', ?, 'hash_pend', ?, ?)
        """, (
            "art_pending_1",
            "draft_pend_1",
            other_id,
            "Материал на модерации",
            "<p>Черновик на проверке модераторами.</p>",
            json.dumps({"materialType": "article", "topics": ["general"]}),
            t_pend,
            t_pend
        ))

        # Author's Answer on art_quest_2 (comment_type = 'answer')
        t_ans1 = (now - datetime.timedelta(days=6, hours=12)).isoformat()
        cur.execute("""
            INSERT INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, is_solution, created_at)
            VALUES (?, ?, ?, 'Алексей Разработчик', ?, 'published', 'answer', 1, ?)
        """, (
            "ans_1",
            "art_quest_2",
            author_id,
            "Используйте slot storage collision checks и ERC-1967 стандарт.",
            t_ans1
        ))

        # Author's Ordinary Comments:
        # C1: on art_pub_1, comment_type = 'comment', high rating (3 votes)
        t_comm1 = (now - datetime.timedelta(days=5, hours=10)).isoformat()
        cur.execute("""
            INSERT INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, is_solution, created_at)
            VALUES (?, ?, ?, 'Алексей Разработчик', ?, 'published', 'comment', 0, ?)
        """, (
            "comm_1",
            "art_pub_1",
            author_id,
            "Замечание по поводу структуры каталогов dApp проекта.",
            t_comm1
        ))
        for voter, val in [("voter1", 1), ("voter2", 1), ("voter3", 1)]:
            cur.execute("""
                INSERT INTO comment_votes (comment_id, user_id, value, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, ("comm_1", voter, val, t_comm1, t_comm1))

        # C2: on art_quest_1, comment_type = 'comment', medium rating (1 vote)
        t_comm2 = (now - datetime.timedelta(days=4, hours=10)).isoformat()
        cur.execute("""
            INSERT INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, is_solution, created_at)
            VALUES (?, ?, ?, 'Алексей Разработчик', ?, 'published', 'comment', 0, ?)
        """, (
            "comm_2",
            "art_quest_1",
            author_id,
            "Рекомендую кешировать array.length в стек перед началом цикла for.",
            t_comm2
        ))
        cur.execute("""
            INSERT INTO comment_votes (comment_id, user_id, value, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, ("comm_2", "voter1", 1, t_comm2, t_comm2))

        # C3: on art_quest_2, comment_type = 'comment', 0 votes
        t_comm3 = (now - datetime.timedelta(days=3, hours=10)).isoformat()
        cur.execute("""
            INSERT INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, is_solution, created_at)
            VALUES (?, ?, ?, 'Алексей Разработчик', ?, 'published', 'comment', 0, ?)
        """, (
            "comm_3",
            "art_quest_2",
            author_id,
            "Дополнительно обратите внимание на защиту от selfdestruct в логическом контракте.",
            t_comm3
        ))

        # C4: ordinary comment on rejected article (should NOT appear)
        cur.execute("""
            INSERT INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, is_solution, created_at)
            VALUES (?, ?, ?, 'Алексей Разработчик', ?, 'published', 'comment', 0, ?)
        """, (
            "comm_rejected",
            "art_rejected_1",
            author_id,
            "Комментарий к отклоненному материалу.",
            (now - datetime.timedelta(days=2)).isoformat()
        ))

        # C5: ordinary comment on pending article (should NOT appear)
        cur.execute("""
            INSERT INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, is_solution, created_at)
            VALUES (?, ?, ?, 'Алексей Разработчик', ?, 'published', 'comment', 0, ?)
        """, (
            "comm_pending",
            "art_pending_1",
            author_id,
            "Комментарий к материалу на модерации.",
            (now - datetime.timedelta(days=1)).isoformat()
        ))

        # C6: deleted comment on approved article (should NOT appear)
        cur.execute("""
            INSERT INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, is_solution, created_at)
            VALUES (?, ?, ?, 'Алексей Разработчик', ?, 'deleted', 'comment', 0, ?)
        """, (
            "comm_deleted",
            "art_pub_1",
            author_id,
            "Удаленный комментарий.",
            (now - datetime.timedelta(days=1)).isoformat()
        ))

        # C7: other user's comment (should NOT appear in author's comments)
        cur.execute("""
            INSERT INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, is_solution, created_at)
            VALUES (?, ?, ?, 'Мария Тестировщик', ?, 'published', 'comment', 0, ?)
        """, (
            "comm_other",
            "art_pub_1",
            other_id,
            "Комментарий другого пользователя.",
            (now - datetime.timedelta(days=1)).isoformat()
        ))

        conn.commit()

    def _get_json(self, path: str):
        parsed = urllib.parse.urlsplit(path)
        encoded_query = urllib.parse.quote_plus(parsed.query, safe="=&?/") if parsed.query else ""
        encoded_path = urllib.parse.quote(parsed.path, safe="/")
        rebuilt = encoded_path + (f"?{encoded_query}" if encoded_query else "")
        url = f"{self.base_url}{rebuilt}"
        req = urllib.request.Request(url, headers={}, method="GET")
        with urllib.request.urlopen(req) as resp:
            data = resp.read().decode("utf-8")
            return resp.status, json.loads(data) if data else {}

    def test_01_user_comments_basic_and_isolation(self):
        """GET /api/users/<user_id>/comments returns only published ordinary comments on approved materials."""
        status, data = self._get_json("/api/users/user_author/comments")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("totalCount"), 3)

        items = data.get("items", [])
        item_ids = [it["id"] for it in items]

        # Ordinary comments on approved materials must be present
        self.assertIn("comm_1", item_ids)
        self.assertIn("comm_2", item_ids)
        self.assertIn("comm_3", item_ids)

        # Answers must not be present in comments endpoint
        self.assertNotIn("ans_1", item_ids)

        # Comments on unapproved materials must not leak
        self.assertNotIn("comm_rejected", item_ids)
        self.assertNotIn("comm_pending", item_ids)

        # Deleted comments must not appear
        self.assertNotIn("comm_deleted", item_ids)

        # Other users' comments must not appear
        self.assertNotIn("comm_other", item_ids)

        # Verify fields on items
        comm1_item = next(it for it in items if it["id"] == "comm_1")
        self.assertEqual(comm1_item["articleId"], "art_pub_1")
        self.assertEqual(comm1_item["parentTitle"], "Архитектура децентрализованных приложений")
        self.assertIn("Замечание по поводу структуры", comm1_item["content"])
        self.assertEqual(comm1_item["rating"], 3)
        self.assertEqual(comm1_item["score"], 3)
        self.assertIn("article.html?id=art_pub_1#comment-comm_1", comm1_item["url"])
        self.assertIn("article.html?id=art_pub_1#comment-comm_1", comm1_item["permalink"])

    def test_02_user_comments_sorting(self):
        """Comments endpoint supports sorting by date (sort=new) and rating (sort=rating)."""
        # 1. Sort by new (default): comm_3 (newest), comm_2, comm_1
        status, data_new = self._get_json("/api/users/user_author/comments?sort=new")
        self.assertEqual(status, 200)
        items_new = data_new.get("items", [])
        self.assertEqual([it["id"] for it in items_new], ["comm_3", "comm_2", "comm_1"])

        # 2. Sort by rating: comm_1 (rating=3), comm_2 (rating=1), comm_3 (rating=0)
        status, data_rating = self._get_json("/api/users/user_author/comments?sort=rating")
        self.assertEqual(status, 200)
        items_rating = data_rating.get("items", [])
        self.assertEqual([it["id"] for it in items_rating], ["comm_1", "comm_2", "comm_3"])

    def test_03_user_comments_pagination(self):
        """Comments endpoint supports limit and offset pagination."""
        # Page 1: limit=2, offset=0 -> 2 items, totalCount=3, hasMore=True
        status, page1 = self._get_json("/api/users/user_author/comments?limit=2&offset=0")
        self.assertEqual(status, 200)
        self.assertEqual(len(page1.get("items", [])), 2)
        self.assertEqual(page1.get("totalCount"), 3)
        self.assertTrue(page1.get("hasMore"))

        # Page 2: limit=2, offset=2 -> 1 item, totalCount=3, hasMore=False
        status, page2 = self._get_json("/api/users/user_author/comments?limit=2&offset=2")
        self.assertEqual(status, 200)
        self.assertEqual(len(page2.get("items", [])), 1)
        self.assertEqual(page2.get("totalCount"), 3)
        self.assertFalse(page2.get("hasMore"))

    def test_04_user_comments_search_q(self):
        """Comments endpoint supports search parameter q matching comment text or parent title."""
        # Match comment content
        status, data_q1 = self._get_json("/api/users/user_author/comments?q=кешировать")
        self.assertEqual(status, 200)
        items_q1 = data_q1.get("items", [])
        self.assertEqual(len(items_q1), 1)
        self.assertEqual(items_q1[0]["id"], "comm_2")

        # Match parent title (case-insensitive Cyrillic)
        status, data_q2 = self._get_json("/api/users/user_author/comments?q=архитектура")
        self.assertEqual(status, 200)
        items_q2 = data_q2.get("items", [])
        self.assertEqual(len(items_q2), 1)
        self.assertEqual(items_q2[0]["id"], "comm_1")

        # Match across question title
        status, data_q3 = self._get_json("/api/users/user_author/comments?q=delegatecall")
        self.assertEqual(status, 200)
        items_q3 = data_q3.get("items", [])
        self.assertEqual(len(items_q3), 1)
        self.assertEqual(items_q3[0]["id"], "comm_3")

        # Non-matching query returns empty list
        status, data_none = self._get_json("/api/users/user_author/comments?q=несуществующий_запрос_123")
        self.assertEqual(status, 200)
        self.assertEqual(len(data_none.get("items", [])), 0)
        self.assertEqual(data_none.get("totalCount"), 0)
        self.assertFalse(data_none.get("hasMore"))

    def test_05_activity_feed_includes_comments(self):
        """GET /api/users/<user_id>/activity includes ordinary comments alongside publications, questions, and answers."""
        status, data = self._get_json("/api/users/user_author/activity")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))

        items = data.get("items", [])
        types = [it["type"] for it in items]

        # Feed must include all content types
        self.assertIn("publication", types)
        self.assertIn("question", types)
        self.assertIn("answer", types)
        self.assertIn("comment", types)

        # Inspect comment item in activity feed
        comm_item = next(it for it in items if it["id"] == "comm_1")
        self.assertEqual(comm_item["type"], "comment")
        self.assertEqual(comm_item["materialType"], "comment")
        self.assertEqual(comm_item["parentTitle"], "Архитектура децентрализованных приложений")
        self.assertIn("article.html?id=art_pub_1#comment-comm_1", comm_item["url"])

        # Feed must be sorted in reverse chronological order
        dates = [it["createdAt"] for it in items]
        self.assertEqual(dates, sorted(dates, reverse=True))

        # Comments on unapproved materials must not leak in activity feed
        item_ids = [it["id"] for it in items]
        self.assertNotIn("comm_rejected", item_ids)
        self.assertNotIn("comm_pending", item_ids)

    def test_06_profile_response_includes_comments_count(self):
        """GET /api/users/<user_id> response contains commentsCount and comments_count."""
        status, data = self._get_json("/api/users/user_author")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))

        # Exact count of ordinary published comments on approved materials is 3
        self.assertEqual(data.get("commentsCount"), 3)
        self.assertEqual(data.get("comments_count"), 3)

        # Check inside profile and stats objects
        profile_obj = data.get("profile", {})
        self.assertEqual(profile_obj.get("commentsCount"), 3)
        self.assertEqual(profile_obj.get("comments_count"), 3)

        stats_obj = profile_obj.get("stats", {})
        self.assertEqual(stats_obj.get("commentsCount"), 3)
        self.assertEqual(stats_obj.get("comments_count"), 3)

    def test_07_content_search_q_publications_questions_answers(self):
        """Publications, questions, and answers endpoints support search parameter q."""
        # 1. Search in publications: matches title or content
        status, pub_match = self._get_json("/api/users/user_author/publications?q=архитектура")
        self.assertEqual(status, 200)
        self.assertEqual(len(pub_match.get("items", [])), 1)
        self.assertEqual(pub_match.get("items", [])[0]["id"], "art_pub_1")

        status, pub_nomatch = self._get_json("/api/users/user_author/publications?q=ненайдено")
        self.assertEqual(status, 200)
        self.assertEqual(len(pub_nomatch.get("items", [])), 0)

        # 2. Search in questions: matches title or content
        status, q_match = self._get_json("/api/users/user_author/questions?q=оптимизация")
        self.assertEqual(status, 200)
        self.assertEqual(len(q_match.get("items", [])), 1)
        self.assertEqual(q_match.get("items", [])[0]["id"], "art_quest_1")

        status, q_nomatch = self._get_json("/api/users/user_author/questions?q=ненайдено")
        self.assertEqual(status, 200)
        self.assertEqual(len(q_nomatch.get("items", [])), 0)

        # 3. Search in answers: matches question title or answer content
        status, ans_match = self._get_json("/api/users/user_author/answers?q=erc-1967")
        self.assertEqual(status, 200)
        self.assertEqual(len(ans_match.get("items", [])), 1)
        self.assertEqual(ans_match.get("items", [])[0]["id"], "ans_1")

        status, ans_nomatch = self._get_json("/api/users/user_author/answers?q=ненайдено")
        self.assertEqual(status, 200)
        self.assertEqual(len(ans_nomatch.get("items", [])), 0)

    def test_08_nonexistent_user(self):
        """GET /api/users/<user_id>/comments returns 404 for unknown user."""
        url = f"{self.base_url}/api/users/unknown_user_999/comments"
        req = urllib.request.Request(url, headers={}, method="GET")
        try:
            with urllib.request.urlopen(req) as resp:
                status = resp.status
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            status = e.code
            with e:
                data = json.loads(e.read().decode("utf-8"))

        self.assertEqual(status, 404)
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("code"), "USER_NOT_FOUND")

    def test_09_strict_invariants(self):
        """Verify strict project invariants: zero emojis, zero em dashes."""
        test_file_path = os.path.abspath(__file__)
        with open(test_file_path, "r", encoding="utf-8") as f:
            test_content = f.read()

        server_file_path = os.path.join(PROJECT_ROOT, "server.py")
        with open(server_file_path, "r", encoding="utf-8") as f:
            server_content = f.read()

        # Check for em dashes (Unicode U+2014)
        self.assertNotIn("\u2014", test_content, "Em dash found in test file")
        self.assertNotIn("\u2014", server_content, "Em dash found in server.py")

        # Check for emojis in test file
        for idx, ch in enumerate(test_content):
            cat = unicodedata.category(ch)
            self.assertFalse(
                cat in ("So", "Cs") and ord(ch) > 127 and ch not in ("№", "©", "®"),
                f"Emoji or special symbol found at pos {idx} in test file: {repr(ch)}"
            )


if __name__ == "__main__":
    unittest.main()
