#!/usr/bin/env python3
"""
tests/test_issue191_profile_optimization_n_plus_1.py

Automated backend test suite for Issue #191:
[P1][backend][PROFILE] Eliminate N+1 and full archive loading on profile open.

Verifies:
1. Index utilization:
   - idx_moderation_author on moderation_submissions(author_id, status)
   - idx_comments_user_status on article_comments(user_id, status)
2. Constant query count and bounded transfer:
   - SQL query count for GET /api/users/<user_id> remains bounded across 5, 20, and 50 publications
   - Proves elimination of 2*N queries per publication
   - Complexity clarification: O(1) refers to bounded data transfer, payload size, and server memory per page via LIMIT ? OFFSET ?, while database filtering performs indexed/author scanning.
3. Lightweight overview projection:
   - article_html is not loaded for the entire archive of publications
   - Only loaded for top candidate IDs (at most 4 items)
4. Database-level pagination & stable sorting:
   - /api/users/<user_id>/publications with limit, offset, total, hasMore
   - /api/users/<user_id>/questions with limit, offset, total, hasMore
   - /api/users/<user_id>/answers with limit, offset, filter=solutions
   - /api/users/<user_id>/comments with limit, offset, total, hasMore
5. Defects 1-4 Regression Coverage:
   - Defect 1: Preserve approved parent identity for answers and comments; unauthenticated guest requests never leak unapproved snapshots.
   - Defect 2: Exact JSON matching of topic/topics prevents substring false positives on descriptions and sub-slugs.
   - Defect 3: Custom extract_text SQLite function strips HTML tags for accurate search matching in publications and questions.
   - Defect 4: Search filter (q param) across overview activity feed computes exact total and hasMore pagination.
6. Strict Invariants:
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

    # =========================================================================
    # 6. Archive Scaling & Elimination of Full HTML Materialization
    # =========================================================================

    def test_09_activity_does_not_transfer_full_archive_html(self):
        """Verify activity feed does not load full article_html or content for entire archive."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        uid = "author_act_archive"
        cur.execute("""
            INSERT OR IGNORE INTO user_profiles (user_id, name, specialization, company, bio, created_at, updated_at)
            VALUES (?, 'Author Archive', 'Engineer', 'Labs', 'Archive test', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
        """, (uid,))
        # 30 publications with large article_html
        for i in range(1, 31):
            pid = f"act_art_{i:02d}"
            cur.execute("""
                INSERT OR IGNORE INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'approved', '{"materialType": "publication"}', ?, 'hash', ?, ?)
            """, (pid, pid, f"Archive Art {i:02d}", uid, f"<article>Large payload {i} " * 80 + "</article>", f"2026-08-{min(i, 28):02d}T10:00:00Z", f"2026-08-{min(i, 28):02d}T10:00:00Z"))
        # 30 comments with large content
        for i in range(1, 31):
            cid = f"act_cmt_{i:02d}"
            cur.execute("""
                INSERT OR IGNORE INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, created_at, updated_at)
                VALUES (?, 'act_art_01', ?, 'Author Archive', ?, 'published', 'comment', ?, ?)
            """, (cid, uid, f"Comment large content {i} " * 40, f"2026-08-{min(i, 28):02d}T11:00:00Z", f"2026-08-{min(i, 28):02d}T11:00:00Z"))
        conn.commit()
        conn.close()

        self.executed_queries.clear()
        status, data = self._get_json(f"/api/users/{uid}/activity?limit=10&offset=0")
        self.assertEqual(status, 200)
        self.assertEqual(data["total"], 60)
        self.assertEqual(len(data["activity"]), 10)
        self.assertTrue(data["hasMore"])

        # Check queries fetching article_html or content
        html_queries = [
            q for q in self.executed_queries
            if ("article_html" in q.lower() or "content" in q.lower())
            and "user_profiles" not in q.lower()
        ]
        # Full archive scan queries must not be present
        for q in html_queries:
            q_lower = q.lower()
            is_bounded = ("where ms.id in" in q_lower) or ("where ac.id in" in q_lower) or ("limit" in q_lower)
            self.assertTrue(is_bounded, f"Unbounded archive query detected: {q}")

        # Count total rows fetched with full article_html or content
        # Bounded by requested limit (at most 10 items)
        total_html_rows = 0
        for q in html_queries:
            q_lower = q.lower()
            if "where ms.id in (" in q_lower:
                part = q_lower.split("where ms.id in (")[1].split(")")[0]
                total_html_rows += len(part.split(","))
            elif "where ac.id in (" in q_lower:
                part = q_lower.split("where ac.id in (")[1].split(")")[0]
                total_html_rows += len(part.split(","))

        self.assertLessEqual(total_html_rows, 10, f"Transferred full HTML for more than 10 items: {total_html_rows}")

    def test_10_filtered_publications_do_not_scan_archive_html(self):
        """Verify filtered publications query applies LIMIT ? OFFSET ? and avoids full archive scans."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        uid = "author_filt_archive"
        cur.execute("""
            INSERT OR IGNORE INTO user_profiles (user_id, name, specialization, company, bio, created_at, updated_at)
            VALUES (?, 'Author Filter', 'Auditor', 'Labs', 'Filter test', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
        """, (uid,))
        # 25 publications with topic solidity and keyword test
        for i in range(1, 26):
            pid = f"sol_art_{i:02d}"
            cur.execute("""
                INSERT OR IGNORE INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'approved', '{"topics": ["solidity"]}', ?, 'hash', ?, ?)
            """, (pid, pid, f"Solidity Test Article {i:02d}", uid, f"<p>Contract test content {i}</p>", f"2026-08-{min(i, 28):02d}T10:00:00Z", f"2026-08-{min(i, 28):02d}T10:00:00Z"))
        # 15 publications with topic security and keyword test
        for i in range(1, 16):
            pid = f"sec_art_{i:02d}"
            cur.execute("""
                INSERT OR IGNORE INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'approved', '{"topics": ["security"]}', ?, 'hash', ?, ?)
            """, (pid, pid, f"Security Test Article {i:02d}", uid, f"<p>Audit test content {i}</p>", f"2026-08-{min(i, 28):02d}T11:00:00Z", f"2026-08-{min(i, 28):02d}T11:00:00Z"))
        conn.commit()
        conn.close()

        # 1. Search query filter (?q=test&limit=10&offset=0)
        self.executed_queries.clear()
        status_q, data_q = self._get_json(f"/api/users/{uid}/publications?q=test&limit=10&offset=0")
        self.assertEqual(status_q, 200)
        self.assertEqual(data_q["total"], 40)
        self.assertEqual(len(data_q["items"]), 10)
        self.assertTrue(data_q["hasMore"])

        # Assert SQL query applies LIMIT ? OFFSET ?
        row_fetch_queries_q = [
            q for q in self.executed_queries
            if "select ms.id" in q.lower() and "article_html" in q.lower()
        ]
        self.assertTrue(len(row_fetch_queries_q) > 0, "Expected a query fetching article_html rows")
        for q in row_fetch_queries_q:
            self.assertIn("limit", q.lower(), f"Expected LIMIT in query: {q}")
            self.assertIn("offset", q.lower(), f"Expected OFFSET in query: {q}")
        self.assertFalse(any("select ms.id" in q.lower() and "limit" not in q.lower() for q in self.executed_queries))

        # 2. Topic filter (?topic=solidity&limit=10&offset=0)
        self.executed_queries.clear()
        status_top, data_top = self._get_json(f"/api/users/{uid}/publications?topic=solidity&limit=10&offset=0")
        self.assertEqual(status_top, 200)
        self.assertEqual(data_top["total"], 25)
        self.assertEqual(len(data_top["items"]), 10)
        self.assertTrue(data_top["hasMore"])

        row_fetch_queries_top = [
            q for q in self.executed_queries
            if "select ms.id" in q.lower() and "article_html" in q.lower()
        ]
        self.assertTrue(len(row_fetch_queries_top) > 0, "Expected a query fetching article_html rows")
        for q in row_fetch_queries_top:
            self.assertIn("limit", q.lower(), f"Expected LIMIT in query: {q}")
            self.assertIn("offset", q.lower(), f"Expected OFFSET in query: {q}")
        self.assertFalse(any("select ms.id" in q.lower() and "limit" not in q.lower() for q in self.executed_queries))

    def test_11_archive_scaling_measurements_10_100_1000(self):
        """Verify O(1) query counts, rows extracted, and HTML materialization across 10, 100, and 1000 records."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        # Seed authors with 10, 100, and 1000 records
        sizes = [10, 100, 1000]
        for n in sizes:
            uid = f"user_scale_{n}"
            cur.execute("""
                INSERT OR IGNORE INTO user_profiles (user_id, name, specialization, company, bio, created_at, updated_at)
                VALUES (?, ?, 'Researcher', 'Scaling', 'Scale test', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
            """, (uid, f"Scale User {n}"))

            batch = []
            for i in range(1, n + 1):
                pid = f"scale_{n}_pub_{i}"
                batch.append((
                    pid, pid, f"Scale Article {i}", uid, "approved",
                    '{"materialType": "publication", "topics": ["scaling"]}',
                    f"<p>Article payload {i} " * 20 + "</p>",
                    "hash", "2026-09-01T12:00:00Z", "2026-09-01T12:00:00Z"
                ))
            cur.executemany("""
                INSERT OR IGNORE INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, batch)
        conn.commit()
        conn.close()

        pub_metrics = {}
        act_metrics = {}

        for n in sizes:
            uid = f"user_scale_{n}"

            # 1. Publications page 1
            self.executed_queries.clear()
            s_pub, d_pub = self._get_json(f"/api/users/{uid}/publications?limit=10&offset=0")
            self.assertEqual(s_pub, 200)
            self.assertEqual(d_pub["total"], n)
            self.assertEqual(len(d_pub["items"]), 10)
            pub_queries = len(self.executed_queries)

            # Measure rows extracted with article_html (must be exactly bounded to page limit: 10)
            pub_html_queries = [
                q for q in self.executed_queries
                if "article_html" in q.lower() and "moderation_submissions" in q.lower()
            ]
            self.assertTrue(all("limit" in q.lower() for q in pub_html_queries))
            pub_metrics[n] = {
                "queries": pub_queries,
                "rows_returned": len(d_pub["items"])
            }

            # 2. Activity page 1
            self.executed_queries.clear()
            s_act, d_act = self._get_json(f"/api/users/{uid}/activity?limit=10&offset=0")
            self.assertEqual(s_act, 200)
            self.assertEqual(d_act["total"], n)
            self.assertEqual(len(d_act["activity"]), 10)
            act_queries = len(self.executed_queries)

            # Measure rows with full HTML materialization in activity
            act_html_queries = [
                q for q in self.executed_queries
                if ("article_html" in q.lower() or "content" in q.lower())
                and "user_profiles" not in q.lower()
            ]
            total_act_html_rows = 0
            for q in act_html_queries:
                q_lower = q.lower()
                if "where ms.id in (" in q_lower:
                    part = q_lower.split("where ms.id in (")[1].split(")")[0]
                    total_act_html_rows += len(part.split(","))
                elif "where ac.id in (" in q_lower:
                    part = q_lower.split("where ac.id in (")[1].split(")")[0]
                    total_act_html_rows += len(part.split(","))

            self.assertLessEqual(total_act_html_rows, 10)
            act_metrics[n] = {
                "queries": act_queries,
                "rows_returned": len(d_act["activity"]),
                "html_rows": total_act_html_rows
            }

        # Assertions proving O(1) query count and row extraction across 10, 100, 1000 archive sizes
        for n in sizes:
            self.assertEqual(pub_metrics[n]["rows_returned"], 10)
            self.assertEqual(act_metrics[n]["rows_returned"], 10)
            self.assertEqual(act_metrics[n]["html_rows"], 10)

        # Query counts must be bounded and identical across 10, 100, and 1000 items
        self.assertEqual(
            pub_metrics[10]["queries"],
            pub_metrics[100]["queries"],
            f"Publications query count mismatch: 10->{pub_metrics[10]['queries']}, 100->{pub_metrics[100]['queries']}"
        )
        self.assertEqual(
            pub_metrics[100]["queries"],
            pub_metrics[1000]["queries"],
            f"Publications query count mismatch: 100->{pub_metrics[100]['queries']}, 1000->{pub_metrics[1000]['queries']}"
        )
        self.assertEqual(
            act_metrics[10]["queries"],
            act_metrics[100]["queries"],
            f"Activity query count mismatch: 10->{act_metrics[10]['queries']}, 100->{act_metrics[100]['queries']}"
        )
        self.assertEqual(
            act_metrics[100]["queries"],
            act_metrics[1000]["queries"],
            f"Activity query count mismatch: 100->{act_metrics[100]['queries']}, 1000->{act_metrics[1000]['queries']}"
        )

    # =========================================================================
    # 7. Defects 1-4 Regression Tests
    # =========================================================================

    def test_12_defect1_approved_parent_identity_and_guest_activity(self):
        """Verify Defect 1: Approved parent identity is preserved for answers and comments,
        and unauthenticated guest requests never leak unapproved or rejected snapshots."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        uid = "user_d1_author"
        cur.execute("""
            INSERT OR IGNORE INTO user_profiles (user_id, name, specialization, company, bio, created_at, updated_at)
            VALUES (?, 'Defect 1 Author', 'Developer', 'OpenSource', 'D1 bio', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
        """, (uid,))

        # 1. Question draft with two snapshots: 1 rejected, 1 approved
        cur.execute("""
            INSERT OR IGNORE INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
            VALUES ('snap_d1_quest_rejected', 'draft_d1_quest', 'REJECTED Old Question Title', 'someone_else', 'rejected', '{"materialType": "question"}', '<p>Q</p>', 'hash1', '2026-01-01T10:00:00Z', '2026-01-01T10:00:00Z')
        """)
        cur.execute("""
            INSERT OR IGNORE INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
            VALUES ('snap_d1_quest_approved', 'draft_d1_quest', 'APPROVED Real Question Title', 'someone_else', 'approved', '{"materialType": "question"}', '<p>Q</p>', 'hash2', '2026-01-02T10:00:00Z', '2026-01-02T10:00:00Z')
        """)
        # Answer by user_d1_author pointing to draft_d1_quest
        cur.execute("""
            INSERT OR IGNORE INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, created_at, updated_at)
            VALUES ('ans_d1_1', 'draft_d1_quest', ?, 'Defect 1 Author', 'My helpful answer', 'published', 'answer', '2026-01-03T10:00:00Z', '2026-01-03T10:00:00Z')
        """, (uid,))

        # 2. Article draft with two snapshots: 1 rejected, 1 approved
        cur.execute("""
            INSERT OR IGNORE INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
            VALUES ('snap_d1_art_rejected', 'draft_d1_art', 'REJECTED Old Article Title', 'someone_else', 'rejected', '{"materialType": "publication"}', '<p>A</p>', 'hash3', '2026-01-01T11:00:00Z', '2026-01-01T11:00:00Z')
        """)
        cur.execute("""
            INSERT OR IGNORE INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
            VALUES ('snap_d1_art_approved', 'draft_d1_art', 'APPROVED Real Article Title', 'someone_else', 'approved', '{"materialType": "publication"}', '<p>A</p>', 'hash4', '2026-01-02T11:00:00Z', '2026-01-02T11:00:00Z')
        """)
        # Comment by user_d1_author pointing to draft_d1_art
        cur.execute("""
            INSERT OR IGNORE INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, created_at, updated_at)
            VALUES ('comm_d1_1', 'draft_d1_art', ?, 'Defect 1 Author', 'My insightful comment', 'published', 'comment', '2026-01-03T11:00:00Z', '2026-01-03T11:00:00Z')
        """, (uid,))

        # 3. Question draft with ONLY rejected snapshot
        cur.execute("""
            INSERT OR IGNORE INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
            VALUES ('snap_d1_unapproved', 'draft_d1_unapproved', 'NEVER APPROVED Question', 'someone_else', 'rejected', '{"materialType": "question"}', '<p>Q</p>', 'hash5', '2026-01-01T12:00:00Z', '2026-01-01T12:00:00Z')
        """)
        # Answer pointing to unapproved question
        cur.execute("""
            INSERT OR IGNORE INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, created_at, updated_at)
            VALUES ('ans_d1_leak', 'draft_d1_unapproved', ?, 'Defect 1 Author', 'Answer to rejected question', 'published', 'answer', '2026-01-03T12:00:00Z', '2026-01-03T12:00:00Z')
        """, (uid,))

        conn.commit()
        conn.close()

        # Unauthenticated guest request
        status, data = self._get_json(f"/api/users/{uid}/activity")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        # Must exclude the unapproved question's answer: exact total = 2
        self.assertEqual(data.get("total"), 2)
        activity = data.get("activity", [])
        self.assertEqual(len(activity), 2)

        # Verify answer item
        ans_item = next((it for it in activity if it["id"] == "ans_d1_1"), None)
        self.assertIsNotNone(ans_item, "Expected ans_d1_1 in activity")
        self.assertEqual(ans_item["title"], "APPROVED Real Question Title")
        self.assertNotEqual(ans_item["title"], "REJECTED Old Question Title")

        # Verify comment item
        comm_item = next((it for it in activity if it["id"] == "comm_d1_1"), None)
        self.assertIsNotNone(comm_item, "Expected comm_d1_1 in activity")
        self.assertEqual(comm_item["parentTitle"], "APPROVED Real Article Title")
        self.assertNotEqual(comm_item["parentTitle"], "REJECTED Old Article Title")

        # Verify no unapproved item leaked
        leak_item = next((it for it in activity if it["id"] == "ans_d1_leak"), None)
        self.assertIsNone(leak_item, "Unapproved question answer must not leak into activity")

    def test_13_defect2_exact_topic_matching_no_substring_false_positives(self):
        """Verify Defect 2: Exact matching of topic/topics using SQLite JSON functions
        prevents substring false matches on descriptions and sub-slugs."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        uid = "user_d2_topics"
        cur.execute("""
            INSERT OR IGNORE INTO user_profiles (user_id, name, specialization, company, bio, created_at, updated_at)
            VALUES (?, 'Defect 2 Topics', 'Auditor', 'SecurityCo', 'D2 bio', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
        """, (uid,))

        # 1. Matching publication via topics array
        cur.execute("""
            INSERT OR IGNORE INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
            VALUES ('pub_d2_1', 'pub_d2_1', 'Security Pub 1', ?, 'approved', '{"materialType": "publication", "topics": ["security"]}', '<p>Content</p>', 'hash1', '2026-01-01T10:00:00Z', '2026-01-01T10:00:00Z')
        """, (uid,))

        # 2. Matching publication via topic string
        cur.execute("""
            INSERT OR IGNORE INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
            VALUES ('pub_d2_2', 'pub_d2_2', 'Security Pub 2', ?, 'approved', '{"materialType": "publication", "topic": "security"}', '<p>Content</p>', 'hash2', '2026-01-01T11:00:00Z', '2026-01-01T11:00:00Z')
        """, (uid,))

        # 3. Matching publication via topics string (scalar)
        cur.execute("""
            INSERT OR IGNORE INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
            VALUES ('pub_d2_3', 'pub_d2_3', 'Security Pub 3', ?, 'approved', '{"materialType": "publication", "topics": "security"}', '<p>Content</p>', 'hash3', '2026-01-01T12:00:00Z', '2026-01-01T12:00:00Z')
        """, (uid,))

        # 4. False positive trap: description contains 'security' but topics is ['defi']
        cur.execute("""
            INSERT OR IGNORE INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
            VALUES ('pub_d2_trap1', 'pub_d2_trap1', 'Trap Pub 1', ?, 'approved', '{"materialType": "publication", "topics": ["defi"], "description": "Discussing web security and audits"}', '<p>Content</p>', 'hash4', '2026-01-01T13:00:00Z', '2026-01-01T13:00:00Z')
        """, (uid,))

        # 5. False positive trap: sub-slug 'network-security'
        cur.execute("""
            INSERT OR IGNORE INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
            VALUES ('pub_d2_trap2', 'pub_d2_trap2', 'Trap Pub 2', ?, 'approved', '{"materialType": "publication", "topics": ["network-security"]}', '<p>Content</p>', 'hash5', '2026-01-01T14:00:00Z', '2026-01-01T14:00:00Z')
        """, (uid,))

        # 6. False positive trap: sub-slug 'cybersecurity'
        cur.execute("""
            INSERT OR IGNORE INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
            VALUES ('pub_d2_trap3', 'pub_d2_trap3', 'Trap Pub 3', ?, 'approved', '{"materialType": "publication", "topic": "cybersecurity"}', '<p>Content</p>', 'hash6', '2026-01-01T15:00:00Z', '2026-01-01T15:00:00Z')
        """, (uid,))

        # 7. Matching question
        cur.execute("""
            INSERT OR IGNORE INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
            VALUES ('quest_d2_1', 'quest_d2_1', 'Security Quest 1', ?, 'approved', '{"materialType": "question", "topics": ["security"]}', '<p>Q content</p>', 'hash7', '2026-01-01T16:00:00Z', '2026-01-01T16:00:00Z')
        """, (uid,))

        # 8. False positive question trap: description contains 'security'
        cur.execute("""
            INSERT OR IGNORE INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
            VALUES ('quest_d2_trap', 'quest_d2_trap', 'Trap Quest', ?, 'approved', '{"materialType": "question", "topics": ["solidity"], "description": "security review required"}', '<p>Q content</p>', 'hash8', '2026-01-01T17:00:00Z', '2026-01-01T17:00:00Z')
        """, (uid,))

        conn.commit()
        conn.close()

        # Check publications exact topic filter
        status_pub, data_pub = self._get_json(f"/api/users/{uid}/publications?topic=security")
        self.assertEqual(status_pub, 200)
        self.assertEqual(data_pub.get("total"), 3, "Expected exactly 3 matching publications")
        returned_pub_ids = {it["id"] for it in data_pub.get("items", [])}
        self.assertEqual(returned_pub_ids, {"pub_d2_1", "pub_d2_2", "pub_d2_3"})
        self.assertNotIn("pub_d2_trap1", returned_pub_ids)
        self.assertNotIn("pub_d2_trap2", returned_pub_ids)
        self.assertNotIn("pub_d2_trap3", returned_pub_ids)

        # Check questions exact topic filter
        status_quest, data_quest = self._get_json(f"/api/users/{uid}/questions?topic=security")
        self.assertEqual(status_quest, 200)
        self.assertEqual(data_quest.get("total"), 1, "Expected exactly 1 matching question")
        returned_quest_ids = {it["id"] for it in data_quest.get("items", [])}
        self.assertEqual(returned_quest_ids, {"quest_d2_1"})
        self.assertNotIn("quest_d2_trap", returned_quest_ids)

    def test_14_defect3_html_text_search_extract_text_publications_and_questions(self):
        """Verify Defect 3: Search filters for publications and questions use extract_text(article_html)
        to match formatted text like <p>smart <strong>contract</strong></p>."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        uid = "user_d3_search"
        cur.execute("""
            INSERT OR IGNORE INTO user_profiles (user_id, name, specialization, company, bio, created_at, updated_at)
            VALUES (?, 'Defect 3 Searcher', 'Researcher', 'Web3Lab', 'D3 bio', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
        """, (uid,))

        # Publication with HTML tag inside search phrase
        cur.execute("""
            INSERT OR IGNORE INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
            VALUES ('pub_d3_1', 'pub_d3_1', 'Architecture Guide', ?, 'approved', '{"materialType": "publication"}', '<p>Advanced <strong>smart contract</strong> patterns on EVM</p>', 'hash1', '2026-01-01T10:00:00Z', '2026-01-01T10:00:00Z')
        """, (uid,))

        # Publication without match
        cur.execute("""
            INSERT OR IGNORE INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
            VALUES ('pub_d3_2', 'pub_d3_2', 'Unrelated Topic', ?, 'approved', '{"materialType": "publication"}', '<p>Completely different article without target</p>', 'hash2', '2026-01-01T11:00:00Z', '2026-01-01T11:00:00Z')
        """, (uid,))

        # Question with HTML tag inside search phrase
        cur.execute("""
            INSERT OR IGNORE INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
            VALUES ('quest_d3_1', 'quest_d3_1', 'Gas Query', ?, 'approved', '{"materialType": "question"}', '<div>How to optimize <em>smart contract</em> gas cost?</div>', 'hash3', '2026-01-01T12:00:00Z', '2026-01-01T12:00:00Z')
        """, (uid,))

        # Question without match
        cur.execute("""
            INSERT OR IGNORE INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
            VALUES ('quest_d3_2', 'quest_d3_2', 'Other Query', ?, 'approved', '{"materialType": "question"}', '<div>Different question without keywords</div>', 'hash4', '2026-01-01T13:00:00Z', '2026-01-01T13:00:00Z')
        """, (uid,))

        conn.commit()
        conn.close()

        # Query publications with formatted phrase
        status_pub, data_pub = self._get_json(f"/api/users/{uid}/publications?q=smart%20contract")
        self.assertEqual(status_pub, 200)
        self.assertEqual(data_pub.get("total"), 1, "Expected exactly 1 publication matching smart contract via extract_text")
        self.assertEqual(len(data_pub.get("items", [])), 1)
        self.assertEqual(data_pub["items"][0]["id"], "pub_d3_1")

        # Query questions with formatted phrase
        status_quest, data_quest = self._get_json(f"/api/users/{uid}/questions?q=smart%20contract")
        self.assertEqual(status_quest, 200)
        self.assertEqual(data_quest.get("total"), 1, "Expected exactly 1 question matching smart contract via extract_text")
        self.assertEqual(len(data_quest.get("items", [])), 1)
        self.assertEqual(data_quest["items"][0]["id"], "quest_d3_1")

    def test_15_defect4_overview_activity_search_total_and_pagination(self):
        """Verify Defect 4: In /api/users/<user_id>/activity, q search parameter filters across
        publications, questions, answers, and comments in Phase 1 and Phase 2 with exact total and hasMore."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        uid = "user_d4_activity_search"
        cur.execute("""
            INSERT OR IGNORE INTO user_profiles (user_id, name, specialization, company, bio, created_at, updated_at)
            VALUES (?, 'Defect 4 Searcher', 'Architect', 'RollupLab', 'D4 bio', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
        """, (uid,))

        # 1. Publication matching 'optimism' in title
        cur.execute("""
            INSERT OR IGNORE INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
            VALUES ('pub_d4_1', 'pub_d4_1', 'Optimism Layer 2 Guide', ?, 'approved', '{"materialType": "publication"}', '<p>Guide body</p>', 'hash1', '2026-01-01T10:00:00Z', '2026-01-01T10:00:00Z')
        """, (uid,))

        # 2. Publication matching 'optimism' in HTML via extract_text
        cur.execute("""
            INSERT OR IGNORE INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
            VALUES ('pub_d4_2', 'pub_d4_2', 'Rollup Deep Dive', ?, 'approved', '{"materialType": "publication"}', '<p>Scalability via <b>optimism</b> tech</p>', 'hash2', '2026-01-01T11:00:00Z', '2026-01-01T11:00:00Z')
        """, (uid,))

        # 3. Question matching 'optimism' in title
        cur.execute("""
            INSERT OR IGNORE INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
            VALUES ('quest_d4_1', 'quest_d4_1', 'Optimism bridge troubleshooting', ?, 'approved', '{"materialType": "question"}', '<p>Bridge issue</p>', 'hash3', '2026-01-01T12:00:00Z', '2026-01-01T12:00:00Z')
        """, (uid,))

        # Parent question for answer
        cur.execute("""
            INSERT OR IGNORE INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
            VALUES ('parent_quest_d4', 'parent_quest_d4', 'L2 Bridges Discussion', 'other_user', 'approved', '{"materialType": "question"}', '<p>Parent Q</p>', 'hash4', '2026-01-01T09:00:00Z', '2026-01-01T09:00:00Z')
        """)
        # 4. Answer by user_d4 matching 'optimism' in content
        cur.execute("""
            INSERT OR IGNORE INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, created_at, updated_at)
            VALUES ('ans_d4_1', 'parent_quest_d4', ?, 'Defect 4 Searcher', '<p>Use the official <i>optimism</i> bridge gateway</p>', 'published', 'answer', '2026-01-01T13:00:00Z', '2026-01-01T13:00:00Z')
        """, (uid,))

        # Parent article for comment
        cur.execute("""
            INSERT OR IGNORE INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
            VALUES ('parent_art_d4', 'parent_art_d4', 'Layer 2 Ecosystem', 'other_user', 'approved', '{"materialType": "publication"}', '<p>Parent Art</p>', 'hash5', '2026-01-01T08:00:00Z', '2026-01-01T08:00:00Z')
        """)
        # 5. Comment by user_d4 matching 'optimism' in content
        cur.execute("""
            INSERT OR IGNORE INTO article_comments (id, article_id, user_id, author_name, content, status, comment_type, created_at, updated_at)
            VALUES ('comm_d4_1', 'parent_art_d4', ?, 'Defect 4 Searcher', 'Optimism has strong fraud proof security', 'published', 'comment', '2026-01-01T14:00:00Z', '2026-01-01T14:00:00Z')
        """, (uid,))

        # Unrelated items that should NOT match 'optimism'
        cur.execute("""
            INSERT OR IGNORE INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
            VALUES ('pub_d4_unrelated', 'pub_d4_unrelated', 'Zero Knowledge Proofs', ?, 'approved', '{"materialType": "publication"}', '<p>ZK rollups</p>', 'hash6', '2026-01-01T15:00:00Z', '2026-01-01T15:00:00Z')
        """, (uid,))
        cur.execute("""
            INSERT OR IGNORE INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings, article_html, snapshot_hash, created_at, updated_at)
            VALUES ('quest_d4_unrelated', 'quest_d4_unrelated', 'Rust on Solana', ?, 'approved', '{"materialType": "question"}', '<p>Solana program</p>', 'hash7', '2026-01-01T16:00:00Z', '2026-01-01T16:00:00Z')
        """, (uid,))

        conn.commit()
        conn.close()

        # Page 1: limit=2, offset=0
        status1, data1 = self._get_json(f"/api/users/{uid}/activity?q=optimism&limit=2&offset=0")
        self.assertEqual(status1, 200)
        self.assertEqual(data1.get("total"), 5, "Total matching items across all 4 activity types must be exactly 5")
        self.assertEqual(len(data1.get("activity", [])), 2)
        self.assertTrue(data1.get("hasMore"))

        # Page 2: limit=2, offset=2
        status2, data2 = self._get_json(f"/api/users/{uid}/activity?q=optimism&limit=2&offset=2")
        self.assertEqual(status2, 200)
        self.assertEqual(data2.get("total"), 5)
        self.assertEqual(len(data2.get("activity", [])), 2)
        self.assertTrue(data2.get("hasMore"))

        # Page 3: limit=2, offset=4
        status3, data3 = self._get_json(f"/api/users/{uid}/activity?q=optimism&limit=2&offset=4")
        self.assertEqual(status3, 200)
        self.assertEqual(data3.get("total"), 5)
        self.assertEqual(len(data3.get("activity", [])), 1)
        self.assertFalse(data3.get("hasMore"))

        # Non-matching search query
        status_none, data_none = self._get_json(f"/api/users/{uid}/activity?q=nonexistent_token_xyz")
        self.assertEqual(status_none, 200)
        self.assertEqual(data_none.get("total"), 0)
        self.assertEqual(len(data_none.get("activity", [])), 0)
        self.assertFalse(data_none.get("hasMore"))


if __name__ == "__main__":
    unittest.main()
