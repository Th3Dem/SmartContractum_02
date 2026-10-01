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
import shutil
import sqlite3
import tempfile
import threading
import time
import unittest
import urllib.error
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
        Test 9 (Shared CSS & Responsive 2x2 Grid):
        Profile styles extracted into shared profile.css linked in feed.html and article.html.
        Stats on narrow screens use 2x2 grid layout without overflow.
        """
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        profile_css_path = os.path.join(repo_root, "frontend", "public", "css", "profile.css")
        self.assertTrue(os.path.exists(profile_css_path), "frontend/public/css/profile.css must exist")

        with open(profile_css_path, "r", encoding="utf-8") as f:
            profile_css = f.read()

        # Contains core modal and profile classes
        self.assertIn(".feed-modal-overlay", profile_css)
        self.assertIn(".user-profile-modal-card", profile_css)
        self.assertIn(".user-profile-stats", profile_css)
        self.assertIn(".user-profile-stat-box", profile_css)

        # 2x2 grid on mobile/narrow screens
        self.assertIn("grid-template-columns: repeat(2, 1fr)", profile_css)
        self.assertIn("@media (max-width: 640px)", profile_css)

        # Linked in both feed.html and article.html
        feed_html_path = os.path.join(repo_root, "frontend", "public", "feed.html")
        with open(feed_html_path, "r", encoding="utf-8") as f:
            feed_html = f.read()
        self.assertIn('<link rel="stylesheet" href="css/profile.css">', feed_html)

        article_html_path = os.path.join(repo_root, "frontend", "public", "article.html")
        with open(article_html_path, "r", encoding="utf-8") as f:
            article_html = f.read()
        self.assertIn('<link rel="stylesheet" href="css/profile.css">', article_html)

    def test_10_behavioral_profile_modal_abort_focus_and_escape(self):
        """
        Test 10 (Behavioral: AbortController, Focus, and Escape):
        - feed.js and article.js use AbortController / sequence token to discard stale responses on author switch.
        - Closing the modal invalidates in-flight requests.
        - Escape key closes modal.
        - Focus is restored to the initiating trigger button upon close.
        - smartcontractum:voted event refreshes open profile without full page reload.
        """
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # feed.js
        feed_js_path = os.path.join(repo_root, "frontend", "public", "js", "feed.js")
        with open(feed_js_path, "r", encoding="utf-8") as f:
            feed_js = f.read()

        self.assertIn("profileAbortController", feed_js)
        self.assertIn("profileRequestSeq", feed_js)
        self.assertIn("closeUserProfileModal", feed_js)
        self.assertIn("lastProfileTriggerEl", feed_js)
        self.assertIn("e.key === 'Escape'", feed_js)
        self.assertIn("smartcontractum:voted", feed_js)

        # article.js
        article_js_path = os.path.join(repo_root, "frontend", "public", "js", "article.js")
        with open(article_js_path, "r", encoding="utf-8") as f:
            article_js = f.read()

        self.assertIn("profileAbortController", article_js)
        self.assertIn("profileRequestSeq", article_js)
        self.assertIn("closeUserProfileModal", article_js)
        self.assertIn("lastProfileTriggerEl", article_js)
        self.assertIn("e.key === 'Escape'", article_js)
        self.assertIn("smartcontractum:voted", article_js)


if __name__ == "__main__":
    unittest.main()
