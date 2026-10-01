#!/usr/bin/env python3
"""
tests/test_issue34_sc029_independent_votes_db_api.py

Comprehensive test suite for Issue #34:
"Рейтинг 1/3: независимые голоса +-1, база данных и API голосования".

Must Prove Checklist:
1. State transitions: 0->+1, 0->-1, +1->0, -1->0, +1->-1, -1->+1 with exact delta (+-2).
2. Idempotency: repeated requests return identical results without duplicating votes or distorting sum.
3. Security and authorization: guest gets 401, self-vote gets 403, hidden/deleted/invalid gets 404/400.
4. Entity independence: article, question, answer, comment have separate votes and valid DTOs.
5. Migration idempotency: repeated init_db / init_moderation_db preserves all data and schema.
6. Coexistence: like and vote are completely independent.
7. Sorting: sort=rating and tab=top sort by score (including negative), sort=popular and focus preserve likes.
8. Canonical ID alias: voting via draft_id resolves to canonical article_id.

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
from server import create_server, init_db, init_moderation_db

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue34IndependentVotesDbApi(unittest.TestCase):
    """Verifies backend database schema, voting endpoints, DTOs, and feed sorting for Issue #34."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_votes.db")
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
                        created_at: str = "2026-10-01T10:00:00Z"):
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, idempotency_key, snapshot_hash, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                art_id, draft_id, title, author_id, status,
                json.dumps({"materialType": material_type, "topics": ["testing"]}, ensure_ascii=False),
                f"<p>{title}</p>", f"idemp_{art_id}", f"hash_{art_id}", created_at, created_at
            ))
        conn.close()

    def _insert_comment(self, comment_id: str, article_id: str, user_id: str, content: str,
                        comment_type: str = "comment", status: str = "published",
                        parent_answer_id: Optional[str] = None, parent_comment_id: Optional[str] = None,
                        created_at: str = "2026-10-01T10:05:00Z"):
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO article_comments (
                    id, article_id, user_id, author_name, content, status,
                    comment_type, is_solution, parent_answer_id, parent_comment_id,
                    revision, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, 1, ?)
            """, (
                comment_id, article_id, user_id, f"User_{user_id}", content, status,
                comment_type, parent_answer_id, parent_comment_id, created_at
            ))
        conn.close()

    def test_01_state_transitions(self):
        """Invariant 1: Transitions 0->+1, +1->-1, -1->+1, +1->0, 0->-1, -1->0 give exact sums."""
        art_id = "art_trans_01"
        self._insert_article(art_id, "draft_trans_01", "author_bob", "Transitions Article")
        cookie_u1 = self._login("user_trans_1", "User 1")
        cookie_u2 = self._login("user_trans_2", "User 2")

        # Initial state: 0 -> +1
        status, data = self._post_json(f"/api/articles/{art_id}/vote", {"value": 1}, cookie_u1)
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])
        self.assertEqual(data["score"], 1)
        self.assertEqual(data["myVote"], 1)
        self.assertEqual(data["targetId"], art_id)
        self.assertEqual(data["targetType"], "article")
        self.assertTrue(data["canVote"])

        # Second user votes +1: score becomes 2
        status, data = self._post_json(f"/api/articles/{art_id}/vote", {"value": 1}, cookie_u2)
        self.assertEqual(status, 200)
        self.assertEqual(data["score"], 2)

        # Transition +1 -> -1 (delta -2): User 1 flips vote
        status, data = self._post_json(f"/api/articles/{art_id}/vote", {"value": -1}, cookie_u1)
        self.assertEqual(status, 200)
        self.assertEqual(data["score"], 0)  # +1 (u2) + (-1) (u1) = 0
        self.assertEqual(data["myVote"], -1)

        # Transition -1 -> +1 (delta +2): User 1 flips back
        status, data = self._post_json(f"/api/articles/{art_id}/vote", {"value": 1}, cookie_u1)
        self.assertEqual(status, 200)
        self.assertEqual(data["score"], 2)
        self.assertEqual(data["myVote"], 1)

        # Transition +1 -> 0 (delta -1): User 1 withdraws vote
        status, data = self._post_json(f"/api/articles/{art_id}/vote", {"value": 0}, cookie_u1)
        self.assertEqual(status, 200)
        self.assertEqual(data["score"], 1)  # only u2 (+1) remaining
        self.assertEqual(data["myVote"], 0)

        # Transition 0 -> -1: User 1 downvotes
        status, data = self._post_json(f"/api/articles/{art_id}/vote", {"value": -1}, cookie_u1)
        self.assertEqual(status, 200)
        self.assertEqual(data["score"], 0)
        self.assertEqual(data["myVote"], -1)

        # Transition -1 -> 0 (delta +1): User 1 clears downvote
        status, data = self._post_json(f"/api/articles/{art_id}/vote", {"value": 0}, cookie_u1)
        self.assertEqual(status, 200)
        self.assertEqual(data["score"], 1)
        self.assertEqual(data["myVote"], 0)

        # Now test the same transitions on a comment
        comm_id = "comm_trans_01"
        self._insert_comment(comm_id, art_id, "author_bob", "Transitions Comment")
        status, data = self._post_json(f"/api/comments/{comm_id}/vote", {"value": 1}, cookie_u1)
        self.assertEqual(status, 200)
        self.assertEqual(data["score"], 1)
        self.assertEqual(data["myVote"], 1)
        self.assertEqual(data["targetId"], comm_id)
        self.assertEqual(data["targetType"], "comment")

        # Flip +1 -> -1 on comment
        status, data = self._post_json(f"/api/comments/{comm_id}/vote", {"value": -1}, cookie_u1)
        self.assertEqual(status, 200)
        self.assertEqual(data["score"], -1)
        self.assertEqual(data["myVote"], -1)

        # Reset comment vote to 0
        status, data = self._post_json(f"/api/comments/{comm_id}/vote", {"value": 0}, cookie_u1)
        self.assertEqual(status, 200)
        self.assertEqual(data["score"], 0)
        self.assertEqual(data["myVote"], 0)

    def test_02_idempotency_and_uniqueness(self):
        """Invariant 2: Repeated identical vote does not distort sum or create duplicate rows."""
        art_id = "art_idemp_01"
        self._insert_article(art_id, "draft_idemp_01", "author_bob", "Idempotency Article")
        cookie_u1 = self._login("user_idemp_1", "User Idemp")

        # Vote +1 twice
        status1, data1 = self._post_json(f"/api/articles/{art_id}/vote", {"value": 1}, cookie_u1)
        status2, data2 = self._post_json(f"/api/articles/{art_id}/vote", {"value": 1}, cookie_u1)
        self.assertEqual(status1, 200)
        self.assertEqual(status2, 200)
        self.assertEqual(data1["score"], 1)
        self.assertEqual(data2["score"], 1)
        self.assertEqual(data2["myVote"], 1)

        # Check DB row count in article_votes
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS cnt FROM article_votes WHERE article_id = ? AND user_id = ?", (art_id, "user_idemp_1"))
        self.assertEqual(cur.fetchone()[0], 1)
        conn.close()

        # Vote 0 twice when already 0
        self._post_json(f"/api/articles/{art_id}/vote", {"value": 0}, cookie_u1)
        status0, data0 = self._post_json(f"/api/articles/{art_id}/vote", {"value": 0}, cookie_u1)
        self.assertEqual(status0, 200)
        self.assertEqual(data0["score"], 0)
        self.assertEqual(data0["myVote"], 0)

        # Comment idempotency
        comm_id = "comm_idemp_01"
        self._insert_comment(comm_id, art_id, "author_bob", "Idemp Comment")
        self._post_json(f"/api/comments/{comm_id}/vote", {"value": -1}, cookie_u1)
        status_c, data_c = self._post_json(f"/api/comments/{comm_id}/vote", {"value": -1}, cookie_u1)
        self.assertEqual(status_c, 200)
        self.assertEqual(data_c["score"], -1)
        self.assertEqual(data_c["myVote"], -1)

    def test_03_security_and_authorization(self):
        """Invariant 3: Guest 401, self-vote 403, hidden/deleted/invalid 404/400."""
        art_id = "art_sec_01"
        draft_id = "draft_sec_01"
        author_id = "author_sec"
        self._insert_article(art_id, draft_id, author_id, "Security Article", status="approved")
        comm_id = "comm_sec_01"
        self._insert_comment(comm_id, art_id, author_id, "Security Comment", status="published")

        cookie_author = self._login(author_id, "Author Sec")
        cookie_other = self._login("user_sec_other", "Other Sec")

        # 1. Guest receives 401 AUTH_REQUIRED with requireAuth
        status, data = self._post_json(f"/api/articles/{art_id}/vote", {"value": 1}, cookie=None)
        self.assertEqual(status, 401)
        self.assertEqual(data.get("code"), "AUTH_REQUIRED")
        self.assertTrue(data.get("requireAuth"))

        status, data = self._post_json(f"/api/comments/{comm_id}/vote", {"value": 1}, cookie=None)
        self.assertEqual(status, 401)
        self.assertEqual(data.get("code"), "AUTH_REQUIRED")
        self.assertTrue(data.get("requireAuth"))

        # 2. Self-voting on article receives 403 SELF_VOTE_FORBIDDEN
        status, data = self._post_json(f"/api/articles/{art_id}/vote", {"value": 1}, cookie_author)
        self.assertEqual(status, 403)
        self.assertEqual(data.get("code"), "SELF_VOTE_FORBIDDEN")

        # 3. Self-voting on comment receives 403 SELF_VOTE_FORBIDDEN
        status, data = self._post_json(f"/api/comments/{comm_id}/vote", {"value": 1}, cookie_author)
        self.assertEqual(status, 403)
        self.assertEqual(data.get("code"), "SELF_VOTE_FORBIDDEN")

        # 4. Non-existent article returns 404 NOT_FOUND
        status, data = self._post_json("/api/articles/non_existent_id/vote", {"value": 1}, cookie_other)
        self.assertEqual(status, 404)
        self.assertEqual(data.get("code"), "NOT_FOUND")

        # 5. Non-approved article (draft or pending) returns 404 NOT_FOUND
        unapproved_id = "art_sec_draft"
        self._insert_article(unapproved_id, "draft_sec_d", author_id, "Draft Article", status="draft")
        status, data = self._post_json(f"/api/articles/{unapproved_id}/vote", {"value": 1}, cookie_other)
        self.assertEqual(status, 404)
        self.assertEqual(data.get("code"), "NOT_FOUND")

        # 6. Non-existent comment returns 404 NOT_FOUND
        status, data = self._post_json("/api/comments/non_existent_comm/vote", {"value": 1}, cookie_other)
        self.assertEqual(status, 404)
        self.assertEqual(data.get("code"), "NOT_FOUND")

        # 7. Deleted comment returns 400 COMMENT_DELETED
        del_comm_id = "comm_sec_deleted"
        self._insert_comment(del_comm_id, art_id, "someone_else", "Deleted content", status="deleted")
        status, data = self._post_json(f"/api/comments/{del_comm_id}/vote", {"value": 1}, cookie_other)
        self.assertEqual(status, 400)
        self.assertEqual(data.get("code"), "COMMENT_DELETED")

        # 8. Comment with unapproved parent article returns 404 NOT_FOUND
        orphan_comm_id = "comm_sec_orphan"
        self._insert_comment(orphan_comm_id, unapproved_id, "someone_else", "Orphan comment", status="published")
        status, data = self._post_json(f"/api/comments/{orphan_comm_id}/vote", {"value": 1}, cookie_other)
        self.assertEqual(status, 404)
        self.assertEqual(data.get("code"), "NOT_FOUND")

        # 8b. Comments DTO under unapproved parent article must have canVote == False
        status, comm_dto = self._get_json(f"/api/articles/{unapproved_id}/comments", cookie_other)
        self.assertEqual(status, 200)
        for c in comm_dto.get("comments", []):
            self.assertFalse(c.get("canVote"), "Comments under unapproved article must have canVote=False")

        # 9. Invalid payload validations: bool, float, string, out of bounds
        invalid_values = [2, -2, 10, "1", "-1", "up", 1.0, -1.0, True, False, None]
        for iv in invalid_values:
            status, data = self._post_json(f"/api/articles/{art_id}/vote", {"value": iv}, cookie_other)
            self.assertEqual(status, 400, f"Expected 400 for article value {iv}")
            self.assertEqual(data.get("code"), "INVALID_VOTE_VALUE")

            status, data = self._post_json(f"/api/comments/{comm_id}/vote", {"value": iv}, cookie_other)
            self.assertEqual(status, 400, f"Expected 400 for comment value {iv}")
            self.assertEqual(data.get("code"), "INVALID_VOTE_VALUE")

        # Missing "value" key
        status, data = self._post_json(f"/api/articles/{art_id}/vote", {}, cookie_other)
        self.assertEqual(status, 400)
        self.assertEqual(data.get("code"), "INVALID_VOTE_VALUE")

    def test_04_entity_independence_and_dto(self):
        """Invariant 4: Article, Question, Answer, and Comment have independent votes and valid DTOs."""
        question_id = "quest_indep_01"
        self._insert_article(question_id, "draft_q_01", "author_alice", "Independent Question",
                             status="approved", material_type="question")

        answer_id = "ans_indep_01"
        self._insert_comment(answer_id, question_id, "author_bob", "Independent Answer", comment_type="answer")

        nested_comm_id = "comm_indep_nested"
        self._insert_comment(nested_comm_id, question_id, "author_charlie", "Nested Comment",
                             comment_type="comment", parent_answer_id=answer_id)

        cookie_voter1 = self._login("voter_1", "Voter 1")
        cookie_voter2 = self._login("voter_2", "Voter 2")

        # Voter 1 upvotes question (+1)
        self._post_json(f"/api/articles/{question_id}/vote", {"value": 1}, cookie_voter1)
        # Voter 1 downvotes answer (-1)
        self._post_json(f"/api/comments/{answer_id}/vote", {"value": -1}, cookie_voter1)
        # Voter 2 upvotes nested comment (+1)
        self._post_json(f"/api/comments/{nested_comm_id}/vote", {"value": 1}, cookie_voter2)

        # Check question DTO via GET /api/articles/<id>
        status, q_dto = self._get_json(f"/api/articles/{question_id}", cookie_voter1)
        self.assertEqual(status, 200)
        art = q_dto["article"]
        self.assertEqual(art["score"], 1)
        self.assertEqual(art["myVote"], 1)
        self.assertTrue(art["canVote"])

        # Check as author_alice (author of question)
        cookie_alice = self._login("author_alice", "Alice")
        status, q_dto_alice = self._get_json(f"/api/articles/{question_id}", cookie_alice)
        self.assertEqual(status, 200)
        self.assertEqual(q_dto_alice["article"]["score"], 1)
        self.assertEqual(q_dto_alice["article"]["myVote"], 0)
        self.assertFalse(q_dto_alice["article"]["canVote"])

        # Check as guest
        status, q_dto_guest = self._get_json(f"/api/articles/{question_id}")
        self.assertEqual(status, 200)
        self.assertEqual(q_dto_guest["article"]["score"], 1)
        self.assertEqual(q_dto_guest["article"]["myVote"], 0)
        self.assertFalse(q_dto_guest["article"]["canVote"])

        # Check comments DTO via GET /api/articles/<id>/comments for voter 1
        status, c_dto = self._get_json(f"/api/articles/{question_id}/comments", cookie_voter1)
        self.assertEqual(status, 200)
        answers = c_dto["answers"]
        self.assertEqual(len(answers), 1)
        ans = answers[0]
        self.assertEqual(ans["id"], answer_id)
        self.assertEqual(ans["score"], -1)
        self.assertEqual(ans["myVote"], -1)
        self.assertTrue(ans["canVote"])

        nested = ans["comments"][0]
        self.assertEqual(nested["id"], nested_comm_id)
        self.assertEqual(nested["score"], 1)  # voted by voter 2
        self.assertEqual(nested["myVote"], 0)  # voter 1 hasn't voted
        self.assertTrue(nested["canVote"])

        # Check comments DTO for author of answer (author_bob)
        cookie_bob = self._login("author_bob", "Bob")
        status, c_dto_bob = self._get_json(f"/api/articles/{question_id}/comments", cookie_bob)
        self.assertEqual(status, 200)
        ans_bob = c_dto_bob["answers"][0]
        self.assertFalse(ans_bob["canVote"])  # author cannot vote on own answer

    def test_05_migration_idempotency(self):
        """Invariant 5: Repeated init_db and init_moderation_db calls preserve data and schema."""
        art_id = "art_mig_01"
        self._insert_article(art_id, "draft_mig_01", "author_bob", "Migration Article")
        cookie = self._login("user_mig_1", "User Mig")
        self._post_json(f"/api/articles/{art_id}/vote", {"value": 1}, cookie)

        # Call init_db and init_moderation_db multiple times
        conn1 = init_db(self.db_path, seed=False)
        conn1.close()
        conn2 = init_moderation_db(self.db_path, seed=False)
        conn2.close()

        # Verify vote is still intact
        status, data = self._get_json(f"/api/articles/{art_id}", cookie)
        self.assertEqual(status, 200)
        self.assertEqual(data["article"]["score"], 1)
        self.assertEqual(data["article"]["myVote"], 1)

        # Verify indices exist
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indices = {r[0] for r in cur.fetchall()}
        self.assertIn("idx_article_votes_target", indices)
        self.assertIn("idx_article_votes_user", indices)
        self.assertIn("idx_comment_votes_target", indices)
        self.assertIn("idx_comment_votes_user", indices)
        conn.close()

    def test_06_likes_and_votes_coexistence(self):
        """Invariant 6: Liking and voting operate completely independently."""
        art_id = "art_coex_01"
        self._insert_article(art_id, "draft_coex_01", "author_bob", "Coexistence Article")
        cookie = self._login("user_coex_1", "User Coex")

        # 1. Like the article
        status, like_res = self._post_json(f"/api/articles/{art_id}/like", {}, cookie)
        self.assertEqual(status, 200)
        self.assertTrue(like_res["hasLiked"])
        self.assertEqual(like_res["likesCount"], 1)

        # Score remains 0
        status, art_dto = self._get_json(f"/api/articles/{art_id}", cookie)
        self.assertEqual(art_dto["article"]["likesCount"], 1)
        self.assertTrue(art_dto["article"]["hasLiked"])
        self.assertEqual(art_dto["article"]["score"], 0)
        self.assertEqual(art_dto["article"]["myVote"], 0)

        # 2. Downvote the article (-1) while retaining like
        status, vote_res = self._post_json(f"/api/articles/{art_id}/vote", {"value": -1}, cookie)
        self.assertEqual(status, 200)
        self.assertEqual(vote_res["score"], -1)
        self.assertEqual(vote_res["myVote"], -1)

        # LikesCount is still 1
        status, art_dto = self._get_json(f"/api/articles/{art_id}", cookie)
        self.assertEqual(art_dto["article"]["likesCount"], 1)
        self.assertTrue(art_dto["article"]["hasLiked"])
        self.assertEqual(art_dto["article"]["score"], -1)
        self.assertEqual(art_dto["article"]["myVote"], -1)

        # 3. Unlike the article
        status, unlike_res = self._post_json(f"/api/articles/{art_id}/like", {}, cookie)
        self.assertEqual(status, 200)
        self.assertFalse(unlike_res["hasLiked"])
        self.assertEqual(unlike_res["likesCount"], 0)

        # Score remains -1, myVote remains -1
        status, art_dto = self._get_json(f"/api/articles/{art_id}", cookie)
        self.assertEqual(art_dto["article"]["likesCount"], 0)
        self.assertFalse(art_dto["article"]["hasLiked"])
        self.assertEqual(art_dto["article"]["score"], -1)
        self.assertEqual(art_dto["article"]["myVote"], -1)

    def test_07_feed_sorting_rating_popular_top(self):
        """Invariant 7: sort=rating and tab=top sort by score; sort=popular sorts by likes."""
        a1 = "art_sort_01"  # score +5, likes 1
        a2 = "art_sort_02"  # score -2, likes 10
        a3 = "art_sort_03"  # score 0, likes 5
        self._insert_article(a1, "draft_s1", "author_bob", "Article 1 High Score", created_at="2026-10-01T10:00:00Z")
        self._insert_article(a2, "draft_s2", "author_bob", "Article 2 High Likes Neg Score", created_at="2026-10-01T10:01:00Z")
        self._insert_article(a3, "draft_s3", "author_bob", "Article 3 Mid Likes Zero Score", created_at="2026-10-01T10:02:00Z")

        # Set votes directly
        conn = sqlite3.connect(self.db_path)
        with conn:
            # a1: 5 upvotes
            for i in range(5):
                conn.execute("INSERT OR REPLACE INTO article_votes (article_id, user_id, value, created_at, updated_at) VALUES (?, ?, 1, '2026-10-01T10:00:00Z', '2026-10-01T10:00:00Z')", (a1, f"voter_{i}"))
            # a2: 2 downvotes
            for i in range(2):
                conn.execute("INSERT OR REPLACE INTO article_votes (article_id, user_id, value, created_at, updated_at) VALUES (?, ?, -1, '2026-10-01T10:00:00Z', '2026-10-01T10:00:00Z')", (a2, f"voter_{i}"))
            # Likes: a1 has 1 like, a2 has 10 likes, a3 has 5 likes
            conn.execute("INSERT OR REPLACE INTO article_likes (article_id, user_id, created_at) VALUES (?, ?, '2026-10-01T10:00:00Z')", (a1, "liker_0"))
            for i in range(10):
                conn.execute("INSERT OR REPLACE INTO article_likes (article_id, user_id, created_at) VALUES (?, ?, '2026-10-01T10:00:00Z')", (a2, f"liker_{i}"))
            for i in range(5):
                conn.execute("INSERT OR REPLACE INTO article_likes (article_id, user_id, created_at) VALUES (?, ?, '2026-10-01T10:00:00Z')", (a3, f"liker_{i}"))
        conn.close()

        # 1. sort=rating -> ordered by score DESC: a1 (+5), a3 (0), a2 (-2)
        status, res = self._get_json(f"/api/articles?ids={a1},{a2},{a3}&sort=rating")
        self.assertEqual(status, 200)
        items = res["articles"]
        self.assertEqual([x["id"] for x in items], [a1, a3, a2])

        # 2. sort=popular -> ordered by likesCount DESC: a2 (10), a3 (5), a1 (1)
        status, res = self._get_json(f"/api/articles?ids={a1},{a2},{a3}&sort=popular")
        self.assertEqual(status, 200)
        items = res["articles"]
        self.assertEqual([x["id"] for x in items], [a2, a3, a1])

        # 3. tab=top (no explicit sort) -> ordered by score DESC: a1 (+5), a3 (0), a2 (-2)
        status, res = self._get_json(f"/api/articles?ids={a1},{a2},{a3}&tab=top&period=all")
        self.assertEqual(status, 200)
        items = res["articles"]
        self.assertEqual([x["id"] for x in items], [a1, a3, a2])

        # 4. tab=top when all articles have score=0: strictly sorts by commentsCount/createdAt, NOT likesCount
        z1 = "art_zero_likes_high"
        z2 = "art_zero_comm_high"
        self._insert_article(z1, "draft_z1", "author_bob", "Zero Score High Likes", created_at="2026-10-01T10:10:00Z")
        self._insert_article(z2, "draft_z2", "author_bob", "Zero Score High Comm", created_at="2026-10-01T10:15:00Z")
        conn = sqlite3.connect(self.db_path)
        with conn:
            for i in range(50):
                conn.execute("INSERT OR REPLACE INTO article_likes (article_id, user_id, created_at) VALUES (?, ?, '2026-10-01T10:10:00Z')", (z1, f"liker_z1_{i}"))
            conn.execute("INSERT OR REPLACE INTO article_likes (article_id, user_id, created_at) VALUES (?, ?, '2026-10-01T10:15:00Z')", (z2, "liker_z2_0"))
            for i in range(5):
                conn.execute("INSERT OR REPLACE INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, created_at) VALUES (?, ?, ?, 'Commer', 'comm', 'published', 'comment', '2026-10-01T10:20:00Z')", (f"comm_z2_{i}", z2, f"u_z2_{i}"))
        conn.close()

        status, res_z = self._get_json(f"/api/articles?ids={z1},{z2}&tab=top&period=all")
        self.assertEqual(status, 200)
        items_z = res_z["articles"]
        self.assertEqual([x["id"] for x in items_z], [z2, z1], "tab=top must prioritize commentsCount over likes when scores are 0")

    def test_08_canonical_id_alias(self):
        """Invariant 8: Voting via draft_id resolves to canonical article_id."""
        canonical_id = "art_canon_01"
        draft_id = "draft_canon_01"
        self._insert_article(canonical_id, draft_id, "author_bob", "Canonical ID Article")
        cookie_u = self._login("user_canon_1", "User Canon")

        # Vote via draft_id in URL
        status, res = self._post_json(f"/api/articles/{draft_id}/vote", {"value": 1}, cookie_u)
        self.assertEqual(status, 200)
        self.assertEqual(res["targetId"], canonical_id)
        self.assertEqual(res["score"], 1)
        self.assertEqual(res["myVote"], 1)

        # Database verification: stored under canonical_id, not draft_id
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT article_id FROM article_votes WHERE user_id = ?", ("user_canon_1",))
        stored_rows = cur.fetchall()
        self.assertEqual(len(stored_rows), 1)
        self.assertEqual(stored_rows[0][0], canonical_id)
        conn.close()

        # Follow-up vote via canonical_id updates the existing vote instead of inserting duplicate
        status, res2 = self._post_json(f"/api/articles/{canonical_id}/vote", {"value": -1}, cookie_u)
        self.assertEqual(status, 200)
        self.assertEqual(res2["targetId"], canonical_id)
        self.assertEqual(res2["score"], -1)
        self.assertEqual(res2["myVote"], -1)

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM article_votes WHERE user_id = ?", ("user_canon_1",))
        self.assertEqual(cur.fetchone()[0], 1)
        conn.close()


if __name__ == "__main__":
    unittest.main()
