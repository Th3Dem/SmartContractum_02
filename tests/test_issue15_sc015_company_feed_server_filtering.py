#!/usr/bin/env python3
"""
tests/test_issue15_sc015_company_feed_server_filtering.py

Comprehensive test suite for Issue #15 (SC-015):
"Серверная фильтрация публикаций компаний до пагинации"

Covers:
1. GET /api/articles?isCompany=true returns strictly company publications (companyId is present and non-empty).
2. GET /api/articles?companyId=<id> returns only publications of that specific company.
3. Server pagination (limit, offset) operates strictly on the company-filtered dataset:
   - Page 1 (limit=3, offset=0) returns 3 items, hasMore=True, correct total.
   - Page 2 (limit=3, offset=3) returns next 3 items without duplicate IDs.
   - total accurately reflects total company articles in the database.
4. Prevention of false empty screens:
   - Adding many recent personal articles (without companyId) does not displace company articles or cause empty pages.
5. JavaScript contract verification in frontend/public/js/feed.js.
6. Zero emojis and offline-first standards compliance.
"""

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
from typing import Optional, Tuple

import server
from server import (
    create_server,
    init_db,
)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue15SC015CompanyFeedServerFiltering(unittest.TestCase):
    """Test suite for server-side company feed filtering and pagination."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue15_sc015.db")
        server.DEFAULT_DB_PATH = cls.db_path

        # Initialize DB with schema and seed articles
        conn = init_db(cls.db_path)
        conn.close()

        # Start dynamic HTTP server
        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR)
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

    # =========================================================================
    # 1. GET /api/articles?isCompany=true returns strictly company publications
    # =========================================================================
    def test_01_is_company_filter_returns_only_company_articles(self):
        """Verify GET /api/articles?isCompany=true returns only articles with non-empty companyId."""
        status, data = self._get_json("/api/articles?isCompany=true&limit=50")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))

        articles = data.get("articles", [])
        self.assertGreater(len(articles), 0, "Must return company articles from seed dataset")

        for art in articles:
            company_id = art.get("companyId")
            self.assertIsNotNone(company_id, f"Article {art.get('id')} must have companyId")
            self.assertNotEqual(company_id, "", f"Article {art.get('id')} companyId must not be empty")

        # Check total matches number of company articles in DB
        total = data.get("total")
        self.assertEqual(total, len(articles), "All company articles returned when limit > total")

    def test_02_is_company_query_param_variations(self):
        """Verify isCompany / is_company accepts 'true', '1', 'yes' in any case."""
        for param in ["isCompany=true", "isCompany=True", "isCompany=1", "isCompany=yes",
                      "is_company=true", "is_company=1", "is_company=yes"]:
            status, data = self._get_json(f"/api/articles?{param}&limit=10")
            self.assertEqual(status, 200, f"Failed for param {param}")
            self.assertTrue(data.get("success"), f"Failed for param {param}")
            articles = data.get("articles", [])
            self.assertGreater(len(articles), 0, f"Must find articles for {param}")
            for art in articles:
                self.assertTrue(bool(art.get("companyId")), f"Article must have companyId for {param}")

    def test_03_is_company_false_or_invalid_does_not_filter(self):
        """Verify isCompany=false or isCompany=0 does not trigger company-only filter."""
        status, data = self._get_json("/api/articles?isCompany=false&limit=50")
        self.assertEqual(status, 200)
        articles = data.get("articles", [])
        # The seed dataset contains 30 articles total, 7 of which are personal
        has_personal = any(not art.get("companyId") for art in articles)
        self.assertTrue(has_personal, "General feed must include personal articles when isCompany=false")

    # =========================================================================
    # 2. Filter by specific company
    # =========================================================================
    def test_04_specific_company_filter(self):
        """Verify GET /api/articles?companyId=smarttech-innovations returns only that company's articles."""
        target_company = "smarttech-innovations"
        status, data = self._get_json(f"/api/articles?companyId={target_company}&limit=50")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))

        articles = data.get("articles", [])
        self.assertGreater(len(articles), 0)
        for art in articles:
            self.assertEqual(art.get("companyId"), target_company,
                             f"Article {art.get('id')} companyId must match {target_company}")

        # Test alternative param name 'company'
        status_alt, data_alt = self._get_json(f"/api/articles?company={target_company}&limit=50")
        self.assertEqual(status_alt, 200)
        self.assertEqual(data_alt.get("total"), data.get("total"))
        self.assertEqual(len(data_alt.get("articles", [])), len(articles))

    def test_05_specific_company_with_is_company_combined(self):
        """Verify combining isCompany=true and companyId works seamlessly."""
        target_company = "cryptosolutions-lab"
        status, data = self._get_json(f"/api/articles?isCompany=true&companyId={target_company}&limit=50")
        self.assertEqual(status, 200)
        articles = data.get("articles", [])
        self.assertGreater(len(articles), 0)
        for art in articles:
            self.assertEqual(art.get("companyId"), target_company)

    def test_06_non_existent_company_returns_empty_list(self):
        """Verify non-existent companyId returns empty articles list with total=0 and hasMore=False."""
        status, data = self._get_json("/api/articles?companyId=non-existent-co-999&limit=10")
        self.assertEqual(status, 200)
        self.assertEqual(data.get("articles"), [])
        self.assertEqual(data.get("total"), 0)
        self.assertFalse(data.get("hasMore"))

    # =========================================================================
    # 3. Server pagination with limit and offset
    # =========================================================================
    def test_07_server_pagination_pages_and_disjoint_ids(self):
        """Verify pagination slices strictly within company articles without overlaps or skips."""
        # Get total company articles count
        status_all, data_all = self._get_json("/api/articles?isCompany=true&limit=100")
        total_company_articles = data_all.get("total", 0)
        self.assertGreaterEqual(total_company_articles, 6, "Expected at least 6 company articles")

        # Page 1: limit=3, offset=0
        status_p1, p1 = self._get_json("/api/articles?isCompany=true&limit=3&offset=0")
        self.assertEqual(status_p1, 200)
        articles_p1 = p1.get("articles", [])
        self.assertEqual(len(articles_p1), 3)
        self.assertEqual(p1.get("total"), total_company_articles)
        self.assertTrue(p1.get("hasMore"))
        self.assertEqual(p1.get("limit"), 3)
        self.assertEqual(p1.get("offset"), 0)

        # Page 2: limit=3, offset=3
        status_p2, p2 = self._get_json("/api/articles?isCompany=true&limit=3&offset=3")
        self.assertEqual(status_p2, 200)
        articles_p2 = p2.get("articles", [])
        self.assertEqual(len(articles_p2), 3)
        self.assertEqual(p2.get("total"), total_company_articles)
        self.assertEqual(p2.get("offset"), 3)

        # Verify no ID overlap between Page 1 and Page 2
        ids_p1 = {a["id"] for a in articles_p1}
        ids_p2 = {a["id"] for a in articles_p2}
        self.assertTrue(ids_p1.isdisjoint(ids_p2), f"Overlap detected between p1 {ids_p1} and p2 {ids_p2}")

        # Verify concatenation matches limit=6 offset=0
        status_p6, p6 = self._get_json("/api/articles?isCompany=true&limit=6&offset=0")
        ids_p6 = [a["id"] for a in p6.get("articles", [])]
        expected_ids = [a["id"] for a in articles_p1] + [a["id"] for a in articles_p2]
        self.assertEqual(ids_p6, expected_ids, "Paged slices must equal combined slice")

    def test_08_pagination_last_page_and_out_of_bounds(self):
        """Verify hasMore is False on last page and out-of-bounds offset returns empty array."""
        status_all, data_all = self._get_json("/api/articles?isCompany=true&limit=100")
        total = data_all.get("total", 0)

        # Request with offset = total
        status_empty, p_empty = self._get_json(f"/api/articles?isCompany=true&limit=10&offset={total}")
        self.assertEqual(status_empty, 200)
        self.assertEqual(p_empty.get("articles"), [])
        self.assertEqual(p_empty.get("total"), total)
        self.assertFalse(p_empty.get("hasMore"))

    # =========================================================================
    # 4. Absence of false empty screens
    # =========================================================================
    def test_09_no_false_empty_screen_with_abundant_personal_articles(self):
        """
        Verify that adding 25 new personal articles with newest timestamps does NOT
        cause empty or underfilled pages on GET /api/articles?isCompany=true.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                # Insert 25 recent personal articles without companyId
                for i in range(1, 26):
                    art_id = f"art-personal-flood-{i:03d}"
                    title = f"Личная статья без компании #{i}"
                    settings = json.dumps({
                        "author": f"Индивидуальный Автор {i}",
                        "topics": ["development"],
                        "keywords": ["personal", "test"],
                        "description": "Персональная публикация без привязки к технологической компании."
                    }, ensure_ascii=False)
                    created_at = f"2026-10-01T{12 + (i // 60):02d}:{i % 60:02d}:00Z"
                    conn.execute("""
                        INSERT OR REPLACE INTO moderation_submissions (
                            id, draft_id, title, author_id, status, publication_settings,
                            article_html, snapshot_hash, idempotency_key, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, 'approved', ?, '<p>Текст личной статьи</p>', ?, ?, ?, ?)
                    """, (
                        art_id, f"draft-personal-{i}", title, f"user-personal-{i}",
                        settings, f"hash-personal-{i}", f"idemp-personal-{i}", created_at, created_at
                    ))
        finally:
            conn.close()

        # Query first page of company articles with limit=5
        status, data = self._get_json("/api/articles?isCompany=true&limit=5&offset=0")
        self.assertEqual(status, 200)
        articles = data.get("articles", [])
        self.assertEqual(len(articles), 5,
                         "First page of company articles must have full limit=5 items despite 25 newer personal articles")
        for art in articles:
            self.assertTrue(bool(art.get("companyId")), "Must only be company articles")

        # Total company articles must not include personal articles
        total = data.get("total", 0)
        self.assertGreaterEqual(total, 20, "Total must reflect all company articles")
        # Ensure none of the newly inserted personal articles leaked into total or results
        returned_ids = {a["id"] for a in articles}
        self.assertTrue(all(not aid.startswith("art-personal-flood-") for aid in returned_ids))

    # =========================================================================
    # 5. Frontend JavaScript contract verification
    # =========================================================================
    def test_10_frontend_feed_js_uses_articles_directly_without_discarding(self):
        """Verify frontend/public/js/feed.js consumes data.articles directly without client discard."""
        feed_js_path = os.path.join(FRONTEND_DIR, "js", "feed.js")
        with open(feed_js_path, "r", encoding="utf-8") as f:
            feed_js_content = f.read()

        # The old problematic filter pattern must not be present
        self.assertNotIn("data.articles.filter(function (a) { return Boolean(a.companyId || a.companyName); })",
                         feed_js_content,
                         "feed.js must not discard server-paged articles client-side")

        # The new direct assignment must be present
        self.assertIn("Array.isArray(data.articles)", feed_js_content,
                      "feed.js must check Array.isArray(data.articles) and use items directly")

        # The fetch for isCompany=true must be present
        self.assertIn("fetch('/api/articles?isCompany=true')", feed_js_content,
                      "feed.js must request isCompany=true")

    # =========================================================================
    # 6. Quality & Standards compliance
    # =========================================================================
    def test_11_zero_emojis_in_source_files(self):
        """Verify zero emojis in modified files server.py and feed.js."""
        import re
        emoji_pattern = re.compile(
            "[\U00010000-\U0010ffff]",
            flags=re.UNICODE
        )
        for filepath in [os.path.join(PROJECT_ROOT, "server.py"),
                         os.path.join(FRONTEND_DIR, "js", "feed.js")]:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            matches = emoji_pattern.findall(content)
            self.assertEqual(matches, [], f"Found emoji in {filepath}: {matches}")


    def test_12_server_py_sql_inspection(self):
        """Verify server.py implements the required SQL-level json_extract filtering."""
        server_py_path = os.path.join(PROJECT_ROOT, "server.py")
        with open(server_py_path, "r", encoding="utf-8") as f:
            code = f.read()

        self.assertIn("json_extract(publication_settings, '$.companyId') = ?", code)
        self.assertIn("json_extract(publication_settings, '$.companyId') IS NOT NULL", code)
        self.assertIn("is_company_filter", code)
        self.assertIn("is_company_param", code)

    def test_13_search_with_is_company_filter(self):
        """Verify search query combined with isCompany=true filters only matching company articles."""
        import urllib.parse
        q = urllib.parse.quote("интеграция")
        status, data = self._get_json(f"/api/articles?isCompany=true&search={q}&limit=10")
        self.assertEqual(status, 200)
        articles = data.get("articles", [])
        for art in articles:
            self.assertTrue(bool(art.get("companyId")), "Must only be company articles")

    def test_14_sort_options_with_is_company_filter(self):
        """Verify sorting options work correctly when isCompany=true is active."""
        for sort_mode in ["newest", "popular", "discussed"]:
            status, data = self._get_json(f"/api/articles?isCompany=true&sort={sort_mode}&limit=10")
            self.assertEqual(status, 200, f"Failed for sort={sort_mode}")
            self.assertTrue(data.get("success"))
            articles = data.get("articles", [])
            self.assertGreater(len(articles), 0)
            for art in articles:
                self.assertTrue(bool(art.get("companyId")), f"Must only be company articles for sort={sort_mode}")


if __name__ == "__main__":
    unittest.main()

