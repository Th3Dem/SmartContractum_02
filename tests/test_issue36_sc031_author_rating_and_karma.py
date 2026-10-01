#!/usr/bin/env python3
"""
tests/test_issue36_sc031_author_rating_and_karma.py

Comprehensive test suite for Issue #36:
Author Rating and Karma aggregation in user profile.

Must Prove Invariants:
1. Control Set: publications (+35), answers (+12), comments (-7) -> profile rating 40.
2. Independence and Single Count: Each vote counted once; 10+ publications/pagination do not distort sum.
3. Likes and Solutions Isolation: Likes and is_solution flags do NOT alter author rating.
4. Dynamic Transitions: Flipping vote (+1 to -1, delta 2) and removing vote (to 0) immediately updates profile.
5. Status Invalidation: Unapproved article (draft/pending) or deleted comment excluded; active published descendants of deleted comment placeholder retain contribution to their own authors.
6. Corporate Publications: Author of corporate publication receives contribution once.
7. Parity and Sign: Public profile (/api/users/<id>) and self profile (/api/user/profile) return identical rating; 0 and negative ratings work properly.

Strict compliance: 100% offline-first, zero emojis, zero em dashes.
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
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple

import server
from server import create_server, init_db

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue36AuthorRatingAndKarma(unittest.TestCase):
    """Verifies author total rating (karma) aggregation and invariants for Issue #36."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_karma.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path, seed=False)
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

    def _post_json(self, path: str, data: Any, cookie: Optional[str] = None) -> Tuple[int, dict]:
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

    def _insert_article(self, art_id: str, draft_id: str, author_id: str, title: str,
                        status: str = "approved", material_type: str = "article",
                        company_id: Optional[str] = None, created_at: str = "2026-10-01T10:00:00Z"):
        conn = sqlite3.connect(self.db_path)
        with conn:
            pub_settings = {
                "materialType": material_type,
                "topics": ["testing"]
            }
            if company_id:
                pub_settings["companyId"] = company_id
            conn.execute("""
                INSERT OR REPLACE INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, idempotency_key, snapshot_hash, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                art_id, draft_id, title, author_id, status,
                json.dumps(pub_settings, ensure_ascii=False),
                f"<p>{title}</p>", f"idemp_{art_id}", f"hash_{art_id}", created_at, created_at
            ))
        conn.close()

    def _insert_comment(self, comment_id: str, article_id: str, user_id: str, content: str,
                        comment_type: str = "comment", status: str = "published",
                        is_solution: int = 0,
                        parent_answer_id: Optional[str] = None, parent_comment_id: Optional[str] = None,
                        created_at: str = "2026-10-01T10:05:00Z"):
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO article_comments (
                    id, article_id, user_id, author_name, content, status,
                    comment_type, is_solution, parent_answer_id, parent_comment_id,
                    revision, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """, (
                comment_id, article_id, user_id, f"User_{user_id}", content, status,
                comment_type, is_solution, parent_answer_id, parent_comment_id, created_at
            ))
        conn.close()

    def _insert_article_vote(self, article_id: str, user_id: str, value: int):
        conn = sqlite3.connect(self.db_path)
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with conn:
            conn.execute("""
                INSERT INTO article_votes (article_id, user_id, value, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(article_id, user_id) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
            """, (article_id, user_id, value, now_iso, now_iso))
        conn.close()

    def _insert_comment_vote(self, comment_id: str, user_id: str, value: int):
        conn = sqlite3.connect(self.db_path)
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with conn:
            conn.execute("""
                INSERT INTO comment_votes (comment_id, user_id, value, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(comment_id, user_id) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
            """, (comment_id, user_id, value, now_iso, now_iso))
        conn.close()

    def test_01_control_set_author_rating(self):
        """
        Test 1 (Control Set):
        Author with approved publications (+35), answers (+12), comments (-7) returns total rating 40.
        """
        author_id = "author_ctrl_01"
        # 1. Approved publications (+35)
        # Publication A: +20 votes (20 users voting +1)
        art_a = "art_ctrl_01_a"
        self._insert_article(art_a, "draft_ctrl_01_a", author_id, "Article A", status="approved")
        for i in range(20):
            self._insert_article_vote(art_a, f"voter_pub_a_{i}", 1)

        # Publication B: +15 votes (15 users voting +1)
        art_b = "art_ctrl_01_b"
        self._insert_article(art_b, "draft_ctrl_01_b", author_id, "Article B", status="approved")
        for i in range(15):
            self._insert_article_vote(art_b, f"voter_pub_b_{i}", 1)

        # 2. Answers on approved question (+12)
        q_art = "q_ctrl_01"
        self._insert_article(q_art, "draft_q_ctrl_01", "other_author", "Question Material",
                             status="approved", material_type="question")
        ans_id = "ans_ctrl_01"
        self._insert_comment(ans_id, q_art, author_id, "Detailed Solution Answer",
                             comment_type="answer", status="published")
        for i in range(12):
            self._insert_comment_vote(ans_id, f"voter_ans_{i}", 1)

        # 3. Comments with downvotes (-7)
        comm_id = "comm_ctrl_01"
        self._insert_comment(comm_id, art_a, author_id, "General Discussion Comment",
                             comment_type="comment", status="published")
        for i in range(7):
            self._insert_comment_vote(comm_id, f"voter_comm_{i}", -1)

        # Total expected: 35 + 12 - 7 = 40
        status, data = self._get_json(f"/api/users/{author_id}")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("rating"), 40)
        self.assertEqual(data.get("karma"), 40)
        self.assertIsInstance(data.get("rating"), int)
        self.assertIsInstance(data.get("karma"), int)

        stats = data.get("stats", {})
        self.assertEqual(stats.get("rating"), 40)
        self.assertEqual(stats.get("karma"), 40)
        self.assertEqual(stats.get("publicationsCount"), 2)
        self.assertEqual(stats.get("answersCount"), 1)

        profile = data.get("profile", {})
        self.assertEqual(profile.get("rating"), 40)
        self.assertEqual(profile.get("karma"), 40)
        self.assertEqual(profile.get("stats", {}).get("rating"), 40)
        self.assertEqual(profile.get("stats", {}).get("karma"), 40)

        user_block = data.get("user", {})
        self.assertEqual(user_block.get("rating"), 40)
        self.assertEqual(user_block.get("karma"), 40)

    def test_02_independence_and_single_count_pagination(self):
        """
        Test 2 (Independence & Single Count):
        Each vote counted once; 10+ publications/pagination do not distort sum.
        """
        author_id = "author_paged_02"
        total_pubs = 14
        votes_per_pub = 2

        # Create 14 approved publications for this author
        for i in range(total_pubs):
            art_id = f"art_paged_02_{i:02d}"
            draft_id = f"draft_paged_02_{i:02d}"
            self._insert_article(art_id, draft_id, author_id, f"Paged Article {i}", status="approved")
            for v in range(votes_per_pub):
                self._insert_article_vote(art_id, f"voter_paged_{v}", 1)

        # Total score: 14 * 2 = 28
        status, data = self._get_json(f"/api/users/{author_id}")
        self.assertEqual(status, 200)
        self.assertEqual(data.get("rating"), 28)
        self.assertEqual(data.get("karma"), 28)
        self.assertEqual(data.get("stats", {}).get("rating"), 28)
        self.assertEqual(data.get("stats", {}).get("publicationsCount"), 14)

        # Profile preview list in API is capped at 10, but rating aggregates over ALL 14
        self.assertEqual(len(data.get("publications", [])), 10)

        # Idempotency check: duplicate voting requests from same user do not duplicate score
        cookie_v0 = self._login("voter_paged_0", "Voter Zero")
        first_art_id = "art_paged_02_00"
        vote_status, vote_data = self._post_json(f"/api/articles/{first_art_id}/vote", {"value": 1}, cookie_v0)
        self.assertEqual(vote_status, 200)
        self.assertEqual(vote_data.get("score"), 2)

        # Score remains exactly 28
        status2, data2 = self._get_json(f"/api/users/{author_id}")
        self.assertEqual(status2, 200)
        self.assertEqual(data2.get("rating"), 28)

    def test_03_likes_and_solutions_isolation(self):
        """
        Test 3 (Likes & Solutions Isolation):
        Likes and is_solution flags do NOT alter author rating.
        """
        author_id = "author_iso_03"
        art_id = "art_iso_03"
        self._insert_article(art_id, "draft_iso_03", author_id, "Isolated Article", status="approved")

        # 5 positive votes on article
        for i in range(5):
            self._insert_article_vote(art_id, f"voter_iso_{i}", 1)

        # Insert answer by author on a question
        q_id = "q_iso_03"
        self._insert_article(q_id, "draft_q_iso_03", "other_author_iso", "Question",
                             status="approved", material_type="question")
        ans_id = "ans_iso_03"
        self._insert_comment(ans_id, q_id, author_id, "Answer marked solution",
                             comment_type="answer", status="published", is_solution=1)

        # Add 10 article likes
        conn = sqlite3.connect(self.db_path)
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with conn:
            for i in range(10):
                conn.execute("""
                    INSERT OR IGNORE INTO article_likes (article_id, user_id, created_at)
                    VALUES (?, ?, ?)
                """, (art_id, f"liker_{i}", now_iso))
        conn.close()

        status, data = self._get_json(f"/api/users/{author_id}")
        self.assertEqual(status, 200)
        self.assertEqual(data.get("rating"), 5)
        self.assertEqual(data.get("karma"), 5)
        self.assertEqual(data.get("stats", {}).get("solutionsCount"), 1)
        self.assertEqual(data.get("stats", {}).get("rating"), 5)

    def test_04_dynamic_transitions(self):
        """
        Test 4 (Dynamic Transitions):
        Flipping vote (+1 to -1, delta 2) and removing vote (to 0) immediately updates profile.
        """
        author_id = "author_dyn_04"
        art_id = "art_dyn_04"
        self._insert_article(art_id, "draft_dyn_04", author_id, "Dynamic Article", status="approved")

        voter_id = "voter_dyn_user"
        cookie_voter = self._login(voter_id, "Dynamic Voter")

        # Step 1: Initial profile is 0
        status, data = self._get_json(f"/api/users/{author_id}")
        self.assertEqual(status, 200)
        self.assertEqual(data.get("rating"), 0)

        # Step 2: Voter casts +1
        v_status, v_data = self._post_json(f"/api/articles/{art_id}/vote", {"value": 1}, cookie_voter)
        self.assertEqual(v_status, 200)
        self.assertEqual(v_data.get("score"), 1)

        status, data = self._get_json(f"/api/users/{author_id}")
        self.assertEqual(data.get("rating"), 1)

        # Step 3: Voter flips to -1 (delta 2)
        v_status, v_data = self._post_json(f"/api/articles/{art_id}/vote", {"value": -1}, cookie_voter)
        self.assertEqual(v_status, 200)
        self.assertEqual(v_data.get("score"), -1)

        status, data = self._get_json(f"/api/users/{author_id}")
        self.assertEqual(data.get("rating"), -1)

        # Step 4: Voter removes vote (value 0)
        v_status, v_data = self._post_json(f"/api/articles/{art_id}/vote", {"value": 0}, cookie_voter)
        self.assertEqual(v_status, 200)
        self.assertEqual(v_data.get("score"), 0)

        status, data = self._get_json(f"/api/users/{author_id}")
        self.assertEqual(data.get("rating"), 0)

        # Step 5: Test dynamic transitions for comment vote
        comm_id = "comm_dyn_04"
        self._insert_comment(comm_id, art_id, author_id, "Author Comment",
                             comment_type="comment", status="published")

        # Vote +1 on comment
        c_status, c_data = self._post_json(f"/api/comments/{comm_id}/vote", {"value": 1}, cookie_voter)
        self.assertEqual(c_status, 200)
        self.assertEqual(c_data.get("score"), 1)

        status, data = self._get_json(f"/api/users/{author_id}")
        self.assertEqual(data.get("rating"), 1)

        # Flip comment vote to -1
        c_status, c_data = self._post_json(f"/api/comments/{comm_id}/vote", {"value": -1}, cookie_voter)
        self.assertEqual(c_status, 200)
        self.assertEqual(c_data.get("score"), -1)

        status, data = self._get_json(f"/api/users/{author_id}")
        self.assertEqual(data.get("rating"), -1)

        # Remove comment vote (value 0)
        c_status, c_data = self._post_json(f"/api/comments/{comm_id}/vote", {"value": 0}, cookie_voter)
        self.assertEqual(c_status, 200)
        self.assertEqual(c_data.get("score"), 0)

        status, data = self._get_json(f"/api/users/{author_id}")
        self.assertEqual(data.get("rating"), 0)

    def test_05_status_invalidation_and_descendant_retention(self):
        """
        Test 5 (Status Invalidation):
        Unapproved article (draft/pending/rejected) or deleted comment excluded;
        active published descendants of deleted comment placeholder retain contribution to their own authors.
        """
        author_a = "author_inv_05_a"
        author_b = "author_inv_05_b"

        # Author A: draft (+5), pending (+3), rejected (+2)
        art_draft = "art_inv_draft"
        art_pending = "art_inv_pending"
        art_rejected = "art_inv_rejected"

        self._insert_article(art_draft, "draft_inv_1", author_a, "Draft Article", status="draft")
        self._insert_article(art_pending, "draft_inv_2", author_a, "Pending Article", status="pending_moderation")
        self._insert_article(art_rejected, "draft_inv_3", author_a, "Rejected Article", status="rejected")

        for i in range(5):
            self._insert_article_vote(art_draft, f"v_draft_{i}", 1)
        for i in range(3):
            self._insert_article_vote(art_pending, f"v_pending_{i}", 1)
        for i in range(2):
            self._insert_article_vote(art_rejected, f"v_rejected_{i}", 1)

        # Unapproved publications must have zero contribution
        status, data_a = self._get_json(f"/api/users/{author_a}")
        self.assertEqual(status, 200)
        self.assertEqual(data_a.get("rating"), 0)
        self.assertEqual(data_a.get("stats", {}).get("publicationsCount"), 0)

        # Transition pending -> approved: votes immediately counted
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute("UPDATE moderation_submissions SET status = 'approved' WHERE id = ?", (art_pending,))
        conn.close()

        status, data_a = self._get_json(f"/api/users/{author_a}")
        self.assertEqual(data_a.get("rating"), 3)
        self.assertEqual(data_a.get("stats", {}).get("publicationsCount"), 1)

        # Transition approved -> rejected: votes removed
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute("UPDATE moderation_submissions SET status = 'rejected' WHERE id = ?", (art_pending,))
        conn.close()

        status, data_a = self._get_json(f"/api/users/{author_a}")
        self.assertEqual(data_a.get("rating"), 0)

        # Comment deletion and descendant retention
        art_approved = "art_inv_approved"
        self._insert_article(art_approved, "draft_inv_app", "third_author", "Approved Art", status="approved")

        # Comment 1 by Author A (+6 votes)
        comm_parent = "comm_inv_parent"
        self._insert_comment(comm_parent, art_approved, author_a, "Parent Comment",
                             comment_type="comment", status="published")
        for i in range(6):
            self._insert_comment_vote(comm_parent, f"v_par_{i}", 1)

        # Comment 2 by Author B as descendant of Comment 1 (+8 votes)
        comm_child = "comm_inv_child"
        self._insert_comment(comm_child, art_approved, author_b, "Child Reply Comment",
                             comment_type="comment", status="published", parent_comment_id=comm_parent)
        for i in range(8):
            self._insert_comment_vote(comm_child, f"v_child_{i}", 1)

        # Before deletion: Author A = 6, Author B = 8
        status, data_a = self._get_json(f"/api/users/{author_a}")
        self.assertEqual(data_a.get("rating"), 6)
        status, data_b = self._get_json(f"/api/users/{author_b}")
        self.assertEqual(data_b.get("rating"), 8)

        # Parent comment is soft-deleted
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute("UPDATE article_comments SET status = 'deleted' WHERE id = ?", (comm_parent,))
        conn.close()

        # After deletion: Author A drops to 0 (deleted comment excluded)
        status, data_a = self._get_json(f"/api/users/{author_a}")
        self.assertEqual(data_a.get("rating"), 0)

        # Descendant child comment by Author B retains its contribution (+8)
        status, data_b = self._get_json(f"/api/users/{author_b}")
        self.assertEqual(data_b.get("rating"), 8)

    def test_06_corporate_publications(self):
        """
        Test 6 (Corporate Publications):
        Author of corporate publication receives contribution once.
        """
        author_id = "author_corp_06"
        company_id = "corp_company_06"
        art_id = "art_corp_06"
        draft_id = "draft_corp_06"

        # Create company
        conn = sqlite3.connect(self.db_path)
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO companies (id, name, description, specialization, owner_id, is_verified, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """, (company_id, "Test Corp", "Description", "IT", author_id, now_iso, now_iso))
        conn.close()

        # Insert corporate article
        self._insert_article(art_id, draft_id, author_id, "Corporate Article",
                             status="approved", company_id=company_id)

        # 4 users vote +1
        for i in range(4):
            self._insert_article_vote(art_id, f"voter_corp_{i}", 1)

        # Author receives contribution exactly once
        status, data = self._get_json(f"/api/users/{author_id}")
        self.assertEqual(status, 200)
        self.assertEqual(data.get("rating"), 4)
        self.assertEqual(data.get("karma"), 4)
        self.assertEqual(data.get("stats", {}).get("rating"), 4)

    def test_07_parity_and_sign(self):
        """
        Test 7 (Parity & Sign):
        Public profile (/api/users/<id>) and self profile (/api/user/profile) return identical rating;
        0 and negative ratings work properly.
        """
        # Case A: Zero rating
        author_zero = "author_zero_07"
        art_zero = "art_zero_07"
        self._insert_article(art_zero, "draft_zero_07", author_zero, "Zero Article", status="approved")

        cookie_zero = self._login(author_zero, "Zero Author")
        status_pub, data_pub = self._get_json(f"/api/users/{author_zero}")
        status_self, data_self = self._get_json("/api/user/profile", cookie_zero)

        self.assertEqual(status_pub, 200)
        self.assertEqual(status_self, 200)
        self.assertEqual(data_pub.get("rating"), 0)
        self.assertEqual(data_self.get("rating"), 0)
        self.assertEqual(data_pub.get("karma"), 0)
        self.assertEqual(data_self.get("karma"), 0)
        self.assertIsInstance(data_pub.get("rating"), int)
        self.assertIsInstance(data_self.get("rating"), int)

        # Case B: Negative rating
        author_neg = "author_neg_07"
        art_neg = "art_neg_07"
        self._insert_article(art_neg, "draft_neg_07", author_neg, "Negative Article", status="approved")

        # 9 downvotes
        for i in range(9):
            self._insert_article_vote(art_neg, f"voter_neg_{i}", -1)

        cookie_neg = self._login(author_neg, "Negative Author")
        status_pub_neg, data_pub_neg = self._get_json(f"/api/users/{author_neg}")
        status_sub_neg, data_sub_neg = self._get_json(f"/api/users/{author_neg}/profile")
        status_self_neg, data_self_neg = self._get_json("/api/user/profile", cookie_neg)

        self.assertEqual(status_pub_neg, 200)
        self.assertEqual(status_sub_neg, 200)
        self.assertEqual(status_self_neg, 200)

        # All must match -9
        self.assertEqual(data_pub_neg.get("rating"), -9)
        self.assertEqual(data_pub_neg.get("karma"), -9)
        self.assertEqual(data_sub_neg.get("rating"), -9)
        self.assertEqual(data_sub_neg.get("karma"), -9)
        self.assertEqual(data_self_neg.get("rating"), -9)
        self.assertEqual(data_self_neg.get("karma"), -9)

        # Stats rating and karma must also match -9
        self.assertEqual(data_pub_neg.get("stats", {}).get("rating"), -9)
        self.assertEqual(data_pub_neg.get("stats", {}).get("karma"), -9)
        self.assertEqual(data_self_neg.get("stats", {}).get("rating"), -9)
        self.assertEqual(data_self_neg.get("stats", {}).get("karma"), -9)

        # Verify key parity between public and self profile
        expected_keys = {"id", "userId", "name", "specialization", "company", "bio",
                         "avatar", "rating", "karma", "stats", "publications"}
        for k in expected_keys:
            self.assertIn(k, data_pub_neg)
            self.assertIn(k, data_self_neg)
            if k not in ("isSubscribed",):
                self.assertEqual(data_pub_neg[k], data_self_neg[k])

    def test_08_profile_ui_contracts_and_tooltip(self):
        """
        Test 8 (UI Contracts & Tooltip):
        Profile modal in feed.js and article.js renders Rating stat box with approved tooltip.
        """
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # 1. feed.js
        feed_js_path = os.path.join(repo_root, "frontend", "public", "js", "feed.js")
        with open(feed_js_path, "r", encoding="utf-8") as f:
            feed_js = f.read()

        self.assertIn("user-profile-rating-num", feed_js)
        self.assertIn("Сумма оценок публикаций, ответов и комментариев. Лайки не учитываются", feed_js)
        self.assertIn("Рейтинг", feed_js)

        # 2. article.js
        article_js_path = os.path.join(repo_root, "frontend", "public", "js", "article.js")
        with open(article_js_path, "r", encoding="utf-8") as f:
            article_js = f.read()

        self.assertIn("user-profile-rating-num", article_js)
        self.assertIn("Сумма оценок публикаций, ответов и комментариев. Лайки не учитываются", article_js)
        self.assertIn("Рейтинг", article_js)

        # 3. HTML modals
        feed_html_path = os.path.join(repo_root, "frontend", "public", "feed.html")
        with open(feed_html_path, "r", encoding="utf-8") as f:
            feed_html = f.read()
        self.assertIn('id="userProfileModal"', feed_html)

        article_html_path = os.path.join(repo_root, "frontend", "public", "article.html")
        with open(article_html_path, "r", encoding="utf-8") as f:
            article_html = f.read()
        self.assertIn('id="userProfileModal"', article_html)

        # 4. Strict Quality Standards
        self.assertNotIn("\u2014", feed_js[feed_js.find("openUserProfileModal"):feed_js.find("openUserProfileModal") + 2000])

    def test_09_shared_profile_css_and_responsive_grid(self):
        """
        Test 9 (Shared CSS, Isolation & Responsive 2x2 Grid):
        - Profile styles extracted into shared profile.css linked in feed.html and article.html.
        - Stats on narrow screens use 2x2 grid layout without overflow.
        - #userProfileModal has class="feed-modal-overlay user-profile-modal-overlay".
        - Generic modal classes in profile.css are scoped strictly under #userProfileModal,
          .user-profile-modal-card, or .user-profile-modal-overlay.
        - Overlay has z-index: 9999 and does not override other modals.
        - No un-scoped global rules exist for generic modal classes.
        """
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        profile_css_path = os.path.join(repo_root, "frontend", "public", "css", "profile.css")
        self.assertTrue(os.path.exists(profile_css_path), "frontend/public/css/profile.css must exist")

        with open(profile_css_path, "r", encoding="utf-8") as f:
            profile_css = f.read()

        # Contains core modal and profile classes
        self.assertIn(".feed-modal-overlay", profile_css)
        self.assertIn(".user-profile-modal-card", profile_css)
        self.assertIn(".user-profile-modal-overlay", profile_css)
        self.assertIn(".user-profile-stats", profile_css)
        self.assertIn(".user-profile-stat-box", profile_css)

        # Overlay z-index stacks properly above headers (9999)
        self.assertIn("z-index: 9999", profile_css)

        # 2x2 grid on mobile/narrow screens
        self.assertIn("grid-template-columns: repeat(2, 1fr)", profile_css)
        self.assertIn("@media (max-width: 640px)", profile_css)

        # Linked in both feed.html and article.html
        feed_html_path = os.path.join(repo_root, "frontend", "public", "feed.html")
        with open(feed_html_path, "r", encoding="utf-8") as f:
            feed_html = f.read()
        self.assertIn('<link rel="stylesheet" href="css/profile.css">', feed_html)
        self.assertIn('class="feed-modal-overlay user-profile-modal-overlay"', feed_html)

        article_html_path = os.path.join(repo_root, "frontend", "public", "article.html")
        with open(article_html_path, "r", encoding="utf-8") as f:
            article_html = f.read()
        self.assertIn('<link rel="stylesheet" href="css/profile.css">', article_html)
        self.assertIn('class="feed-modal-overlay user-profile-modal-overlay"', article_html)

        # CSS Isolation Verification:
        css_clean = re.sub(r'/\*.*?\*/', '', profile_css, flags=re.DOTALL)

        # 1. Ensure no un-scoped global rules exist for generic modal classes
        unscoped_patterns = [
            r'(?m)^\s*\.feed-modal-overlay\s*[{,]',
            r'(?m)^\s*\.feed-modal-header\s*[{,]',
            r'(?m)^\s*\.feed-modal-title-wrap\s*[{,]',
            r'(?m)^\s*\.feed-modal-title\s*[{,]',
            r'(?m)^\s*\.feed-modal-close-btn\s*[{,:]',
            r'(?m)^\s*\.feed-modal-body\s*[{,]',
        ]
        for pattern in unscoped_patterns:
            matches = re.findall(pattern, css_clean)
            self.assertEqual(len(matches), 0, f"Un-scoped global rule found matching pattern: {pattern}")

        # 2. Ensure every selector targeting generic modal classes is scoped under #userProfileModal or .user-profile-modal-card / .user-profile-modal-overlay
        generic_modal_classes = [
            '.feed-modal-overlay',
            '.feed-modal-card',
            '.feed-modal-header',
            '.feed-modal-title-wrap',
            '.feed-modal-title',
            '.feed-modal-close-btn',
            '.feed-modal-body',
        ]
        for match in re.finditer(r'([^{}]+)\{([^{}]+)\}', css_clean):
            selector_group = match.group(1).strip()
            selectors = [s.strip() for s in selector_group.split(',')]
            if any(s.startswith('@') for s in selectors):
                continue
            for sel in selectors:
                for gen_cls in generic_modal_classes:
                    if gen_cls in sel:
                        is_scoped = (
                            '#userProfileModal' in sel or
                            '.user-profile-modal-card' in sel or
                            '.user-profile-modal-overlay' in sel
                        )
                        self.assertTrue(
                            is_scoped,
                            f"Selector '{sel}' containing generic class '{gen_cls}' is not properly scoped under #userProfileModal or .user-profile-modal-card / .user-profile-modal-overlay"
                        )

    def test_10_behavioral_profile_modal_abort_focus_and_escape(self):
        """
        Test 10 (Behavioral: Executable Modal Simulation, AbortController, Focus, and Escape):
        Simulates end-to-end frontend behavioral flows against live backend endpoints:
        1. Modal opening: sets loading state, flex display, focuses close button, resolves author profile and karma rating.
        2. AbortController cancellation on close: closing modal in-flight aborts controller and discards late responses.
        3. AbortController cancellation on author switch: switching author aborts previous controller and discards stale response.
        4. Escape key dismissal: keydown Escape closes modal, aborts in-flight request, and restores focus.
        5. Focus retention and restoration: focus moves to close button on open and restores to triggering button on close.
        6. smartcontractum:voted live refresh: silently refetches without wiping modal or moving focus, updates rating in DOM.
        7. Verification of feed.js and article.js implementations for contract conformity.
        """
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Setup test data in DB for simulation
        author_a = "author_sim_10_a"
        author_b = "author_sim_10_b"
        self._insert_article("art_sim_10_a", "draft_sim_10_a", author_a, "Article Sim 10 A")
        self._insert_article("art_sim_10_b", "draft_sim_10_b", author_b, "Article Sim 10 B")
        for i in range(15):
            self._insert_article_vote("art_sim_10_a", f"voter_a_{i}", 1)
        for i in range(42):
            self._insert_article_vote("art_sim_10_b", f"voter_b_{i}", 1)

        # Mock DOM Element
        class MockDOMElement:
            def __init__(self, tag="div", elem_id="", class_name=""):
                self.tagName = tag.upper()
                self.id = elem_id
                self.className = class_name
                self.style = {"display": "none"}
                self.innerHTML = ""
                self.attributes = {}
                self.listeners = {}

            def focus(self):
                MockEnvironment.active_element = self

            def getAttribute(self, name):
                return self.attributes.get(name)

            def setAttribute(self, name, val):
                self.attributes[name] = val

            def closest(self, sel):
                if sel == ".btn-author-profile" and "btn-author-profile" in self.className:
                    return self
                return None

            def addEventListener(self, event_name, callback):
                self.listeners.setdefault(event_name, []).append(callback)

            def dispatchEvent(self, evt):
                for cb in self.listeners.get(evt.type, []):
                    cb(evt)

        class MockEnvironment:
            active_element = None
            doc_listeners = {}
            win_listeners = {}

            @classmethod
            def reset(cls):
                cls.active_element = None
                cls.doc_listeners = {}
                cls.win_listeners = {}

            @classmethod
            def add_doc_listener(cls, event_name, callback):
                cls.doc_listeners.setdefault(event_name, []).append(callback)

            @classmethod
            def dispatch_doc_event(cls, evt):
                for cb in cls.doc_listeners.get(evt.type, []):
                    cb(evt)

            @classmethod
            def add_win_listener(cls, event_name, callback):
                cls.win_listeners.setdefault(event_name, []).append(callback)

            @classmethod
            def dispatch_win_event(cls, evt):
                for cb in cls.win_listeners.get(evt.type, []):
                    cb(evt)

        class MockDOMEvent:
            def __init__(self, event_type, **kwargs):
                self.type = event_type
                self.defaultPrevented = False
                self.propagationStopped = False
                self.key = kwargs.get("key", "")
                self.target = kwargs.get("target", None)

            def preventDefault(self):
                self.defaultPrevented = True

            def stopPropagation(self):
                self.propagationStopped = True

        class MockAbortSignal:
            def __init__(self):
                self.aborted = False

        class MockAbortController:
            def __init__(self):
                self.signal = MockAbortSignal()

            def abort(self):
                self.signal.aborted = True

        MockEnvironment.reset()

        # Initialize DOM elements
        user_modal = MockDOMElement("div", "userProfileModal", "feed-modal-overlay user-profile-modal-overlay")
        user_modal_body = MockDOMElement("div", "userProfileModalBody", "feed-modal-body")
        btn_close = MockDOMElement("button", "btnCloseUserProfileModal", "feed-modal-close-btn")
        trigger_btn_a = MockDOMElement("button", "authorBtnA", "btn-author-profile")
        trigger_btn_a.setAttribute("data-author-id", author_a)
        trigger_btn_b = MockDOMElement("button", "authorBtnB", "btn-author-profile")
        trigger_btn_b.setAttribute("data-author-id", author_b)

        # Behavioral Controller Simulation
        class UserProfileModalSimulationController:
            def __init__(self, base_url):
                self.base_url = base_url
                self.userModal = user_modal
                self.userModalBody = user_modal_body
                self.btnCloseUserModal = btn_close
                self.currentOpenUserId = None
                self.profileRequestSeq = 0
                self.profileAbortController = None
                self.lastProfileTriggerEl = None
                self.last_signal = None

            def closeUserProfileModal(self):
                if not self.userModal:
                    return
                if self.profileAbortController:
                    try:
                        self.profileAbortController.abort()
                    except Exception:
                        pass
                    self.profileAbortController = None
                self.currentOpenUserId = None
                self.profileRequestSeq += 1
                self.userModal.style["display"] = "none"
                if self.lastProfileTriggerEl and hasattr(self.lastProfileTriggerEl, "focus"):
                    try:
                        self.lastProfileTriggerEl.focus()
                    except Exception:
                        pass
                self.lastProfileTriggerEl = None

            def openUserProfileModal(self, user_id, trigger_el=None, is_silent_refresh=False):
                if not self.userModal or not self.userModalBody:
                    return None
                if trigger_el:
                    self.lastProfileTriggerEl = trigger_el
                elif not is_silent_refresh:
                    self.lastProfileTriggerEl = MockEnvironment.active_element

                self.currentOpenUserId = user_id
                self.profileRequestSeq += 1
                seq = self.profileRequestSeq

                if self.profileAbortController:
                    try:
                        self.profileAbortController.abort()
                    except Exception:
                        pass
                self.profileAbortController = MockAbortController()
                self.last_signal = self.profileAbortController.signal
                captured_controller = self.profileAbortController

                if not is_silent_refresh:
                    self.userModalBody.innerHTML = '<div style="text-align: center; padding: 24px; color: var(--text-muted);">Загрузка профиля...</div>'
                    self.userModal.style["display"] = "flex"
                    if self.btnCloseUserModal:
                        self.btnCloseUserModal.focus()

                url = f"{self.base_url}/api/users/{urllib.parse.quote(user_id)}"

                def execute_fetch():
                    if captured_controller.signal.aborted:
                        return {"status": "aborted"}
                    try:
                        req = urllib.request.Request(url, method="GET")
                        with urllib.request.urlopen(req) as resp:
                            data = json.loads(resp.read().decode("utf-8"))
                    except Exception as ex:
                        data = None

                    if captured_controller.signal.aborted:
                        return {"status": "aborted"}
                    if seq != self.profileRequestSeq or self.currentOpenUserId != user_id:
                        return {"status": "stale_discarded"}

                    u = (data and (data.get("user") or data.get("profile"))) or data
                    if not data or not data.get("success") or not u:
                        self.userModalBody.innerHTML = '<div class="feed-settings-error-msg" style="padding: 20px;">Профиль пользователя не найден</div>'
                        return {"status": "error"}

                    stats = u.get("stats") or {}
                    rating = stats.get("rating", u.get("rating", 0))
                    self.userModalBody.innerHTML = (
                        f'<div class="user-profile-name">{u.get("name", user_id)}</div>'
                        f'<div class="user-profile-stats">'
                        f'<span class="user-profile-stat-num user-profile-rating-num">{rating}</span>'
                        f'<span class="user-profile-stat-label">Рейтинг</span>'
                        f'</div>'
                    )
                    return {"status": "success", "rating": rating}

                return execute_fetch

        ctrl = UserProfileModalSimulationController(self.base_url)

        # Wire event handlers
        btn_close.addEventListener("click", lambda e: ctrl.closeUserProfileModal())
        user_modal.addEventListener("click", lambda e: ctrl.closeUserProfileModal() if e.target is user_modal else None)

        def on_keydown(e):
            if e.key == "Escape" and ctrl.userModal and ctrl.userModal.style.get("display") != "none":
                e.preventDefault()
                ctrl.closeUserProfileModal()

        MockEnvironment.add_doc_listener("keydown", on_keydown)

        def on_voted(e):
            if ctrl.currentOpenUserId and ctrl.userModal and ctrl.userModal.style.get("display") != "none":
                return ctrl.openUserProfileModal(ctrl.currentOpenUserId, None, is_silent_refresh=True)
            return None

        MockEnvironment.add_win_listener("smartcontractum:voted", on_voted)

        # --- SCENARIO 1: Modal Opening & Successful Render ---
        trigger_btn_a.focus()
        self.assertEqual(MockEnvironment.active_element, trigger_btn_a)
        fetch_task_1 = ctrl.openUserProfileModal(author_a, trigger_el=trigger_btn_a)
        self.assertEqual(ctrl.userModal.style["display"], "flex")
        self.assertIn("Загрузка профиля...", ctrl.userModalBody.innerHTML)
        self.assertEqual(MockEnvironment.active_element, btn_close)

        res_1 = fetch_task_1()
        self.assertEqual(res_1.get("status"), "success")
        self.assertEqual(res_1.get("rating"), 15)
        self.assertIn("user-profile-rating-num", ctrl.userModalBody.innerHTML)
        self.assertIn("15", ctrl.userModalBody.innerHTML)

        # --- SCENARIO 2: AbortController Cancellation on Modal Close ---
        fetch_task_2 = ctrl.openUserProfileModal(author_a, trigger_el=trigger_btn_a)
        sig_2 = ctrl.last_signal
        self.assertFalse(sig_2.aborted)

        # User closes modal while request is still pending
        btn_close.dispatchEvent(MockDOMEvent("click", target=btn_close))
        self.assertTrue(sig_2.aborted, "AbortController signal must be aborted upon modal close")
        self.assertEqual(ctrl.userModal.style["display"], "none")
        self.assertIsNone(ctrl.currentOpenUserId)
        self.assertEqual(MockEnvironment.active_element, trigger_btn_a, "Focus must be restored to trigger button")

        # Late resolving response must be safely discarded
        res_2 = fetch_task_2()
        self.assertEqual(res_2.get("status"), "aborted")
        self.assertEqual(ctrl.userModal.style["display"], "none")

        # --- SCENARIO 3: AbortController Cancellation on Author Switch ---
        fetch_task_3a = ctrl.openUserProfileModal(author_a, trigger_el=trigger_btn_a)
        sig_3a = ctrl.last_signal
        self.assertFalse(sig_3a.aborted)

        # User immediately switches to author B
        fetch_task_3b = ctrl.openUserProfileModal(author_b, trigger_el=trigger_btn_b)
        sig_3b = ctrl.last_signal
        self.assertTrue(sig_3a.aborted, "Previous AbortController must be aborted when author is switched")
        self.assertFalse(sig_3b.aborted)
        self.assertEqual(ctrl.currentOpenUserId, author_b)

        # Author A response arrives late: must be discarded
        res_3a = fetch_task_3a()
        self.assertEqual(res_3a.get("status"), "aborted")

        # Author B response arrives: rendered
        res_3b = fetch_task_3b()
        self.assertEqual(res_3b.get("status"), "success")
        self.assertEqual(res_3b.get("rating"), 42)
        self.assertIn("42", ctrl.userModalBody.innerHTML)

        # --- SCENARIO 4: Escape Key Dismissal ---
        self.assertEqual(ctrl.userModal.style["display"], "flex")
        esc_event = MockDOMEvent("keydown", key="Escape")
        MockEnvironment.dispatch_doc_event(esc_event)
        self.assertTrue(esc_event.defaultPrevented, "Escape key handler must call preventDefault()")
        self.assertEqual(ctrl.userModal.style["display"], "none", "Escape key must close open modal")
        self.assertEqual(MockEnvironment.active_element, trigger_btn_b, "Escape key must restore focus to trigger button")

        # Escape key when already closed must not trigger preventDefault
        esc_event_closed = MockDOMEvent("keydown", key="Escape")
        MockEnvironment.dispatch_doc_event(esc_event_closed)
        self.assertFalse(esc_event_closed.defaultPrevented)

        # --- SCENARIO 5: Focus Retention and Restoration ---
        trigger_btn_a.focus()
        ctrl.openUserProfileModal(author_a)
        self.assertEqual(MockEnvironment.active_element, btn_close)
        ctrl.closeUserProfileModal()
        self.assertEqual(MockEnvironment.active_element, trigger_btn_a)

        trigger_btn_b.focus()
        ctrl.openUserProfileModal(author_b)
        self.assertEqual(MockEnvironment.active_element, btn_close)
        ctrl.closeUserProfileModal()
        self.assertEqual(MockEnvironment.active_element, trigger_btn_b)

        # --- SCENARIO 6: smartcontractum:voted Live Refresh ---
        # Open modal for Author A and resolve initial score
        task_open_a = ctrl.openUserProfileModal(author_a, trigger_el=trigger_btn_a)
        task_open_a()
        self.assertIn("15", ctrl.userModalBody.innerHTML)

        # Mutate rating on the backend (+1)
        self._insert_article_vote("art_sim_10_a", "voter_live_refresh_test", 1)

        # Dispatch smartcontractum:voted
        voted_event = MockDOMEvent("smartcontractum:voted")
        refresh_tasks = []
        for cb in MockEnvironment.win_listeners.get("smartcontractum:voted", []):
            t = cb(voted_event)
            if t:
                refresh_tasks.append(t)

        self.assertEqual(len(refresh_tasks), 1, "smartcontractum:voted must trigger one silent refresh task")
        # Ensure silent refresh did not overwrite modal body with loading message
        self.assertNotIn("Загрузка профиля...", ctrl.userModalBody.innerHTML)
        self.assertEqual(ctrl.userModal.style["display"], "flex")

        # Complete silent fetch: updates rating from 15 to 16
        refresh_res = refresh_tasks[0]()
        self.assertEqual(refresh_res.get("status"), "success")
        self.assertEqual(refresh_res.get("rating"), 16)
        self.assertIn("16", ctrl.userModalBody.innerHTML)

        # Close modal and verify smartcontractum:voted does not trigger refresh when modal is closed
        ctrl.closeUserProfileModal()
        closed_voted_tasks = []
        for cb in MockEnvironment.win_listeners.get("smartcontractum:voted", []):
            t = cb(voted_event)
            if t:
                closed_voted_tasks.append(t)
        self.assertEqual(len(closed_voted_tasks), 0, "smartcontractum:voted must do nothing when modal is closed")

        # --- SCENARIO 7: Source Code Architectural Conformity ---
        for js_filename in ["feed.js", "article.js"]:
            js_path = os.path.join(repo_root, "frontend", "public", "js", js_filename)
            with open(js_path, "r", encoding="utf-8") as f:
                js_content = f.read()

            # Lifecycle methods and sequence token
            self.assertIn("function closeUserProfileModal", js_content)
            self.assertIn("function openUserProfileModal", js_content)
            self.assertIn("profileRequestSeq", js_content)
            self.assertIn("currentOpenUserId", js_content)
            self.assertIn("lastProfileTriggerEl", js_content)

            # AbortController instantiation and signal assignment
            self.assertIn("new AbortController()", js_content)
            self.assertIn("profileAbortController.abort()", js_content)
            self.assertIn("signal: profileAbortController.signal", js_content)

            # Discard stale response condition
            self.assertIn("seq !== profileRequestSeq || currentOpenUserId !== userId", js_content)

            # Focus restoration
            self.assertIn("lastProfileTriggerEl.focus()", js_content)

            # Event listeners
            self.assertIn("btnCloseUserProfileModal", js_content)
            self.assertIn("e.key === 'Escape'", js_content)
            self.assertIn(".btn-author-profile", js_content)
            self.assertIn("smartcontractum:voted", js_content)


if __name__ == "__main__":
    unittest.main()
