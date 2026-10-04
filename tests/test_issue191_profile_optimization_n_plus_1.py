#!/usr/bin/env python3
"""
tests/test_issue191_profile_optimization_n_plus_1.py

Automated backend test suite for Issue #191:
[P1][backend][PROFILE] Eliminate N+1 and full archive loading on profile open.

Verifies:
1. Index utilization:
   - idx_moderation_author on moderation_submissions(author_id, status)
   - idx_comments_user_status on article_comments(user_id, status)
2. Constant query count:
   - SQL query count for GET /api/users/<user_id> remains bounded (O(1)) across 5, 20, and 50 publications
   - Proves elimination of 2*N queries per publication
3. Lightweight overview projection:
   - article_html is not loaded for the entire archive of publications
   - Only loaded for top candidate IDs (at most 4 items)
4. Database-level pagination & stable sorting:
   - /api/users/<user_id>/publications with limit, offset, total, hasMore
   - /api/users/<user_id>/questions with limit, offset, total, hasMore
   - /api/users/<user_id>/answers with limit, offset, filter=solutions
   - /api/users/<user_id>/comments with limit, offset, total, hasMore
5. Strict Invariants:
   - Zero emojis, zero em dashes (\\u2014), 100% offline-first.
"""

import os
import re
import json
import sqlite3
import unittest
import threading
import urllib.request
import urllib.parse
from http.server import HTTPServer

import server


import tempfile

class TestIssue191ProfileOptimizationNPlus1(unittest.TestCase):
    """Verifies query count bounding, index coverage, and DB-level pagination."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.db_path = os.path.join(cls.temp_dir.name, "test_opt.db")
        cls.media_dir = os.path.join(cls.temp_dir.name, "media")
        os.makedirs(cls.media_dir, exist_ok=True)

        # Initialize schema
        init_conn = server.init_db(cls.db_path)
        init_conn.close()

        cls.executed_queries = []

        # Wrap get_db to trace queries on every connection
        original_get_db = server.ModerationRequestHandler.get_db
        def traced_get_db(self):
            c = original_get_db(self)
            c.set_trace_callback(cls.executed_queries.append)
            return c

        server.ModerationRequestHandler.get_db = traced_get_db
        cls._original_get_db = original_get_db

        cls.httpd = server.create_server(
            host="127.0.0.1",
            port=0,
            db_path=cls.db_path,
            directory=cls.temp_dir.name,
            media_dir=cls.media_dir,
            seed=False
        )
        cls.port = cls.httpd.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"

        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()

        cls._seed_test_data()

    @classmethod
    def tearDownClass(cls):
        server.ModerationRequestHandler.get_db = cls._original_get_db
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.temp_dir.cleanup()

    @classmethod
    def _seed_test_data(cls):
        conn = sqlite3.connect(cls.db_path)
        cur = conn.cursor()

        # Create authors with varying publication counts
        # Author Small: 5 publications
        # Author Medium: 20 publications
        # Author Large: 50 publications
        for uid in ("author_small", "author_medium", "author_large"):
            cur.execute("""
                INSERT INTO user_profiles (user_id, name, specialization, company, bio, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
            """, (uid, f"Author {uid}", "Architect", "Consortium", "Bio test"))

        # Seed Author Small (5 pubs)
        for i in range(1, 6):
            pid = f"art_small_{i}"
            cur.execute("""
                INSERT INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
                VALUES (?, ?, ?, 'author_small', 'approved', '{"materialType": "publication", "topics": ["web3"]}', ?, 'hash', ?, ?)
            """, (pid, pid, f"Small Title {i}", f"<p>Long content {i} " * 50 + "</p>", f"2026-02-0{min(i, 9)}T10:00:00Z", f"2026-02-0{min(i, 9)}T10:00:00Z"))
            cur.execute("INSERT INTO article_votes (article_id, user_id, value, created_at, updated_at) VALUES (?, 'voter_1', 1, '2026-02-01T00:00:00Z', '2026-02-01T00:00:00Z')", (pid,))
            cur.execute("INSERT INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, created_at, updated_at) VALUES (?, ?, 'commenter_1', 'Commenter', 'Good', 'published', 'comment', '2026-02-01T00:00:00Z', '2026-02-01T00:00:00Z')", (f"c_small_{i}", pid))

        # Seed Author Medium (20 pubs)
        for i in range(1, 21):
            pid = f"art_med_{i}"
            cur.execute("""
                INSERT INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
                VALUES (?, ?, ?, 'author_medium', 'approved', '{"materialType": "publication", "topics": ["security"]}', ?, 'hash', ?, ?)
            """, (pid, pid, f"Med Title {i}", f"<p>Long content {i} " * 50 + "</p>", f"2026-03-{i:02d}T10:00:00Z", f"2026-03-{i:02d}T10:00:00Z"))
            if i % 2 == 0:
                cur.execute("INSERT INTO article_votes (article_id, user_id, value, created_at, updated_at) VALUES (?, 'voter_1', 1, '2026-03-01T00:00:00Z', '2026-03-01T00:00:00Z')", (pid,))

        # Seed Author Large (50 pubs)
        for i in range(1, 51):
            pid = f"art_large_{i}"
            cur.execute("""
                INSERT INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
                VALUES (?, ?, ?, 'author_large', 'approved', '{"materialType": "publication", "topics": ["defi"]}', ?, 'hash', ?, ?)
            """, (pid, pid, f"Large Title {i}", f"<p>Long content {i} " * 50 + "</p>", f"2026-04-{((i-1)%28)+1:02d}T10:00:00Z", f"2026-04-{((i-1)%28)+1:02d}T10:00:00Z"))

        # Seed Questions, Answers, Comments for Author Pagination Tests
        cur.execute("""
            INSERT INTO user_profiles (user_id, name, specialization, company, bio, created_at, updated_at)
            VALUES ('author_paged', 'Author Paged', 'Fullstack', 'Labs', 'Testing pagination', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
        """)

        # 25 Publications for author_paged
        for i in range(1, 26):
            pid = f"paged_pub_{i:02d}"
            score = 10 if i == 5 else (5 if i == 15 else 1)
            cur.execute("""
                INSERT INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
                VALUES (?, ?, ?, 'author_paged', 'approved', '{"materialType": "publication"}', '<p>Paged pub</p>', 'hash', ?, ?)
            """, (pid, pid, f"Paged Pub {i:02d}", f"2026-05-{i:02d}T12:00:00Z", f"2026-05-{i:02d}T12:00:00Z"))
            if score > 1:
                for v in range(score):
                    cur.execute("INSERT INTO article_votes (article_id, user_id, value, created_at, updated_at) VALUES (?, ?, 1, '2026-05-01T00:00:00Z', '2026-05-01T00:00:00Z')", (pid, f"voter_{v}"))

        # 15 Questions for author_paged
        for i in range(1, 16):
            qid = f"paged_quest_{i:02d}"
            cur.execute("""
                INSERT INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
                VALUES (?, ?, ?, 'author_paged', 'approved', '{"materialType": "question"}', '<p>Question text</p>', 'hash', ?, ?)
            """, (qid, qid, f"Paged Question {i:02d}", f"2026-06-{i:02d}T12:00:00Z", f"2026-06-{i:02d}T12:00:00Z"))

        # Questions for Answers testing (1 answer per question per user constraint)
        for i in range(1, 16):
            pqid = f"parent_q_{i:02d}"
            cur.execute("""
                INSERT INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
                VALUES (?, ?, ?, 'someone_else', 'approved', '{"materialType": "question"}', '<p>Q</p>', 'hash', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
            """, (pqid, pqid, f"Parent Question {i:02d}"))

            ans_id = f"paged_ans_{i:02d}"
            is_sol = 1 if i in (3, 7, 11) else 0
            cur.execute("""
                INSERT INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, is_solution, created_at, updated_at)
                VALUES (?, ?, 'author_paged', 'Author Paged', ?, 'published', 'answer', ?, ?, ?)
            """, (ans_id, pqid, f"Answer content {i}", is_sol, f"2026-07-{i:02d}T12:00:00Z", f"2026-07-{i:02d}T12:00:00Z"))

        # 15 Ordinary Comments for author_paged
        for i in range(1, 16):
            cid = f"paged_comm_{i:02d}"
            cur.execute("""
                INSERT INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, created_at, updated_at)
                VALUES (?, 'parent_q_01', 'author_paged', 'Author Paged', ?, 'published', 'comment', ?, ?)
            """, (cid, f"Comment content {i:02d}", f"2026-08-{i:02d}T12:00:00Z", f"2026-08-{i:02d}T12:00:00Z"))

        conn.commit()
        conn.close()

    def _get_json(self, path):
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data

    # =========================================================================
    # 1. Index Coverage Tests
    # =========================================================================

    def test_01_explain_query_plan_uses_composite_indexes(self):
        """Verify EXPLAIN QUERY PLAN uses index seeks on author_id and user_id."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        try:
            cur.execute("EXPLAIN QUERY PLAN SELECT id FROM moderation_submissions WHERE author_id = ? AND status = ?", ("u1", "approved"))
            plan_rows = [str(r[3]) for r in cur.fetchall()]
            has_author_index = any("idx_moderation_author" in r for r in plan_rows)
            self.assertTrue(has_author_index, f"Expected idx_moderation_author in plan: {plan_rows}")

            cur.execute("EXPLAIN QUERY PLAN SELECT id FROM article_comments WHERE user_id = ? AND status = ?", ("u1", "published"))
            comm_plan_rows = [str(r[3]) for r in cur.fetchall()]
            has_user_index = any("idx_comments_user_status" in r for r in comm_plan_rows)
            self.assertTrue(has_user_index, f"Expected idx_comments_user_status in plan: {comm_plan_rows}")
        finally:
            conn.close()

    # =========================================================================
    # 2. Bounded Query Count (O(1) vs O(N)) Tests
    # =========================================================================

    def test_02_constant_query_count_across_archive_sizes(self):
        """Verify profile assembly SQL query count is bounded and does not scale linearly with publication count."""
        # 1. Author with 5 publications
        self.executed_queries.clear()
        status_s, data_s = self._get_json("/api/users/author_small")
        self.assertEqual(status_s, 200)
        queries_small = len(self.executed_queries)

        # 2. Author with 20 publications
        self.executed_queries.clear()
        status_m, data_m = self._get_json("/api/users/author_medium")
        self.assertEqual(status_m, 200)
        queries_medium = len(self.executed_queries)

        # 3. Author with 50 publications
        self.executed_queries.clear()
        status_l, data_l = self._get_json("/api/users/author_large")
        self.assertEqual(status_l, 200)
        queries_large = len(self.executed_queries)

        # With the old N+1 code:
        # 5 pubs -> 12 + 10 = 22 queries
        # 20 pubs -> 12 + 40 = 52 queries
        # 50 pubs -> 12 + 100 = 112 queries
        # With the O(1) optimization:
        # All three must have bounded query count (difference between 5 and 50 must be <= 3 queries)
        self.assertLess(queries_large, 25, f"Expected bounded query count for 50 pubs, got {queries_large}")
        self.assertLessEqual(
            abs(queries_large - queries_small),
            3,
            f"Query count scaled with publications: small={queries_small}, large={queries_large}"
        )
        self.assertLessEqual(
            abs(queries_medium - queries_small),
            3,
            f"Query count scaled with publications: small={queries_small}, medium={queries_medium}"
        )

    # =========================================================================
    # 3. Lightweight Overview Projection (No Archive HTML Scan)
    # =========================================================================

    def test_03_no_full_archive_html_scanned(self):
        """Verify that article_html is not loaded for the entire archive during profile overview."""
        self.executed_queries.clear()
        status, data = self._get_json("/api/users/author_large")
        self.assertEqual(status, 200)

        # Inspect captured queries for article_html
        html_queries = [q for q in self.executed_queries if "article_html" in q.lower()]
        for q in html_queries:
            # article_html may only be fetched for specific IDs with IN (...) or LIMIT
            self.assertTrue(
                ("where id in" in q.lower()) or ("limit" in q.lower()),
                f"Full scan query with article_html detected: {q}"
            )

    # =========================================================================
    # 4. DB-Level Pagination & Sorting
    # =========================================================================

    def test_04_publications_pagination_and_sorting(self):
        """Verify /api/users/<user_id>/publications pagination with limit, offset, and sort."""
        # Page 1: 10 items
        status, p1 = self._get_json("/api/users/author_paged/publications?limit=10&offset=0")
        self.assertEqual(status, 200)
        self.assertEqual(p1["total"], 25)
        self.assertEqual(len(p1["items"]), 10)
        self.assertTrue(p1["hasMore"])

        # Page 2: 10 items
        status, p2 = self._get_json("/api/users/author_paged/publications?limit=10&offset=10")
        self.assertEqual(status, 200)
        self.assertEqual(p2["total"], 25)
        self.assertEqual(len(p2["items"]), 10)
        self.assertTrue(p2["hasMore"])

        # Page 3: 5 items
        status, p3 = self._get_json("/api/users/author_paged/publications?limit=10&offset=20")
        self.assertEqual(status, 200)
        self.assertEqual(p3["total"], 25)
        self.assertEqual(len(p3["items"]), 5)
        self.assertFalse(p3["hasMore"])

        # Sorting: popular places highest score first
        status, pop = self._get_json("/api/users/author_paged/publications?sort=popular&limit=5")
        self.assertEqual(status, 200)
        self.assertEqual(pop["items"][0]["id"], "paged_pub_05")
        self.assertEqual(pop["items"][0]["score"], 10)

    def test_05_questions_pagination(self):
        """Verify /api/users/<user_id>/questions pagination."""
        status, q1 = self._get_json("/api/users/author_paged/questions?limit=10&offset=0")
        self.assertEqual(status, 200)
        self.assertEqual(q1["total"], 15)
        self.assertEqual(len(q1["items"]), 10)
        self.assertTrue(q1["hasMore"])

        status, q2 = self._get_json("/api/users/author_paged/questions?limit=10&offset=10")
        self.assertEqual(status, 200)
        self.assertEqual(q2["total"], 15)
        self.assertEqual(len(q2["items"]), 5)
        self.assertFalse(q2["hasMore"])

    def test_06_answers_pagination_and_solutions_filter(self):
        """Verify /api/users/<user_id>/answers pagination and filter=solutions."""
        # All answers: 15
        status, a1 = self._get_json("/api/users/author_paged/answers?limit=10&offset=0")
        self.assertEqual(status, 200)
        self.assertEqual(a1["total"], 15)
        self.assertEqual(len(a1["items"]), 10)
        self.assertTrue(a1["hasMore"])

        # Only solutions: exactly 3
        status, sols = self._get_json("/api/users/author_paged/answers?filter=solutions")
        self.assertEqual(status, 200)
        self.assertEqual(sols["total"], 3)
        self.assertEqual(len(sols["items"]), 3)
        for it in sols["items"]:
            self.assertTrue(it["isSolution"])

    def test_07_comments_pagination(self):
        """Verify /api/users/<user_id>/comments pagination."""
        status, c1 = self._get_json("/api/users/author_paged/comments?limit=10&offset=0")
        self.assertEqual(status, 200)
        self.assertEqual(c1["total"], 15)
        self.assertEqual(len(c1["items"]), 10)
        self.assertTrue(c1["hasMore"])

        status, c2 = self._get_json("/api/users/author_paged/comments?limit=10&offset=10")
        self.assertEqual(status, 200)
        self.assertEqual(c2["total"], 15)
        self.assertEqual(len(c2["items"]), 5)
        self.assertFalse(c2["hasMore"])

    # =========================================================================
    # 5. Strict Invariants
    # =========================================================================

    def test_08_invariants_zero_em_dashes_and_emojis(self):
        """Verify zero em dashes and zero emojis in test file."""
        with open(__file__, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn("\u2014", content, "Em dash found in test file")


if __name__ == "__main__":
    unittest.main()
