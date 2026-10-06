#!/usr/bin/env python3
"""
tests/test_issue172_full_profile_sidebar.py

Automated test suite for Issue #172:
[P1][frontend] Full Profile: desktop sidebar (о пользователе, экспертиза, репутация, направления)

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
from tests.backend_source import BACKEND_FILES, backend_source_file

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue172FullProfileSidebar(unittest.TestCase):
    """Verifies desktop sidebar markup, widgets, topics aggregation, API support, and invariants."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue172.db")
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

        # 1. Author with full data and publications with topics
        author_full_id = "user_igor"
        t0 = (now - datetime.timedelta(days=90)).isoformat()
        cur.execute("""
            INSERT OR REPLACE INTO user_profiles (user_id, name, specialization, company, bio, website, avatar, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?)
        """, (
            author_full_id,
            "Игорь Семенов",
            "Senior Smart Contract Security Researcher",
            "DefiShield",
            "Аудирую смарт-контракты и пишу статьи о безопасности EVM.",
            "https://defishield.io/igor",
            t0,
            t0
        ))

        # Add publications with topics for author_full_id
        t1 = (now - datetime.timedelta(days=20)).isoformat()
        cur.execute("""
            INSERT INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'approved', ?, 'h_igor_1', ?, ?)
        """, (
            "art_igor_1",
            "draft_igor_1",
            author_full_id,
            "Reentrancy attacks in 2026: cross-contract view",
            "<p>Detailed analysis of read-only reentrancy.</p>",
            json.dumps({"materialType": "article", "topics": ["security", "defi"]}),
            t1,
            t1
        ))

        t2 = (now - datetime.timedelta(days=10)).isoformat()
        cur.execute("""
            INSERT INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'approved', ?, 'h_igor_2', ?, ?)
        """, (
            "art_igor_2",
            "draft_igor_2",
            author_full_id,
            "Formal verification of ERC-20 invariants",
            "<p>Using Certora to mathematically prove balance conservation.</p>",
            json.dumps({"materialType": "article", "topics": ["security", "verification"]}),
            t2,
            t2
        ))

        # Question for author_full_id
        t3 = (now - datetime.timedelta(days=5)).isoformat()
        cur.execute("""
            INSERT INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'approved', ?, 'h_igor_3', ?, ?)
        """, (
            "quest_igor_1",
            "draft_igor_3",
            author_full_id,
            "Is transient storage TSTORE safe in sub-calls?",
            "<p>Question about clearing transient memory.</p>",
            json.dumps({"materialType": "question", "topics": ["evm", "security"]}),
            t3,
            t3
        ))

        # 2. Author with minimal/missing data (no bio, no website, no company)
        author_min_id = "user_minimal"
        cur.execute("""
            INSERT OR REPLACE INTO user_profiles (user_id, name, specialization, company, bio, website, avatar, created_at, updated_at)
            VALUES (?, ?, '', '', '', '', NULL, ?, ?)
        """, (
            author_min_id,
            "Михаил Новичков",
            t0,
            t0
        ))

        # 3. Separate user for profile edit testing
        author_editor_id = "user_editor"
        cur.execute("""
            INSERT OR REPLACE INTO user_profiles (user_id, name, specialization, company, bio, website, avatar, created_at, updated_at)
            VALUES (?, ?, 'Junior Auditor', 'OldCo', 'Старая биография', 'https://oldco.example.com', NULL, ?, ?)
        """, (author_editor_id, "Редактор Профиля", t0, t0))

        # Session for authenticated user testing
        t_exp = (now + datetime.timedelta(days=30)).isoformat()
        cur.execute("""
            INSERT OR REPLACE INTO sessions (token, user_id, user_name, user_role, expires_at, created_at)
            VALUES ('sess_igor', ?, 'Игорь Семенов', 'user', ?, ?)
        """, (author_full_id, t_exp, t0))

        cur.execute("""
            INSERT OR REPLACE INTO sessions (token, user_id, user_name, user_role, expires_at, created_at)
            VALUES ('sess_editor', ?, 'Редактор Профиля', 'user', ?, ?)
        """, (author_editor_id, t_exp, t0))

        conn.commit()

    def _api_get(self, path):
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

    def _api_post(self, path, payload, session_token=None):
        url = f"{self.base_url}{path}"
        body_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body_bytes, method="POST")
        req.add_header("Content-Type", "application/json; charset=utf-8")
        if session_token:
            req.add_header("Cookie", f"sc_session={session_token}")
            req.add_header("Authorization", f"Bearer {session_token}")
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

    # =========================================================================
    # Backend API Tests
    # =========================================================================

    def test_api_user_profile_returns_website_and_aggregated_topics(self):
        """Verifies GET /api/users/:id returns website and real aggregated topics from publications."""
        status, data = self._api_get("/api/users/user_igor")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))

        profile = data.get("profile", {})
        self.assertEqual(profile.get("website"), "https://defishield.io/igor")
        self.assertEqual(profile.get("company"), "DefiShield")
        self.assertEqual(profile.get("bio"), "Аудирую смарт-контракты и пишу статьи о безопасности EVM.")

        # Topics should be aggregated from publications: security (3), defi (1), verification (1), evm (1)
        topics = profile.get("topics", [])
        self.assertTrue(len(topics) >= 3)
        top_topic = topics[0]
        self.assertEqual(top_topic["id"], "security")
        self.assertEqual(top_topic["count"], 3)

    def test_api_user_profile_minimal_user_handles_missing_fields(self):
        """Verifies GET /api/users/:id handles missing bio/website/company gracefully."""
        status, data = self._api_get("/api/users/user_minimal")
        self.assertEqual(status, 200)
        profile = data.get("profile", {})
        self.assertEqual(profile.get("bio"), "")
        self.assertEqual(profile.get("website"), "")
        self.assertEqual(profile.get("company"), "")
        self.assertEqual(profile.get("topics"), [])

    def test_api_post_user_profile_saves_website(self):
        """Verifies POST /api/user/profile updates website and profile data."""
        payload = {
            "name": "Редактор Профиля Обновленный",
            "specialization": "Security Principal",
            "company": "SmartShield Labs",
            "website": "https://smartshield.io",
            "bio": "Обновленная биография эксперта."
        }
        status, data = self._api_post("/api/user/profile", payload, session_token="sess_editor")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        self.assertEqual(data["profile"]["website"], "https://smartshield.io")
        self.assertEqual(data["profile"]["company"], "SmartShield Labs")

    # =========================================================================
    # Frontend Markup Tests
    # =========================================================================

    def test_frontend_markup_profile_sidebar_structure(self):
        """Verifies profile.html contains two-column layout and the 4 required sidebar widgets."""
        html_path = os.path.join(FRONTEND_DIR, "profile.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        # Two-column layout elements
        self.assertIn('class="profile-layout-columns"', html)
        self.assertIn('id="profileLayoutColumns"', html)
        self.assertIn('class="profile-main-column"', html)
        self.assertIn('id="profileMainColumn"', html)

        # Aside container
        self.assertIn('<aside class="profile-sidebar"', html)
        self.assertIn('id="profileSidebar"', html)

        # Widget 1: About
        self.assertIn('profile-widget-about', html)
        self.assertIn('id="sidebarUserBio"', html)
        self.assertIn('id="sidebarUserCompanyRow"', html)
        self.assertIn('id="sidebarUserCompany"', html)
        self.assertIn('id="sidebarUserWebsiteRow"', html)
        self.assertIn('id="sidebarUserWebsite"', html)
        self.assertIn('id="sidebarUserRegistrationRow"', html)
        self.assertIn('id="sidebarUserRegistration"', html)

        # Widget 2: Expertise
        self.assertIn('profile-widget-expertise', html)
        self.assertIn('id="sidebarUserSpecialization"', html)

        # Widget 3: Topics
        self.assertIn('profile-widget-topics', html)
        self.assertIn('id="sidebarUserTopics"', html)

        # Widget 4: Reputation
        self.assertIn('profile-widget-reputation', html)
        self.assertIn('id="sidebarReputationRating"', html)
        self.assertIn('id="sidebarReputationSolutions"', html)
        self.assertIn('id="sidebarReputationPubs"', html)
        self.assertIn('id="sidebarReputationQuestions"', html)

        # Edit modal website field
        self.assertIn('id="editProfileWebsite"', html)

    # =========================================================================
    # Frontend Script Tests
    # =========================================================================

    def test_frontend_profile_script_renders_sidebar_and_topics(self):
        """Verifies profile.js and profile-page.js have aggregateUserTopics and renderSidebar."""
        profile_js_path = os.path.join(FRONTEND_DIR, "js", "profile.js")
        with open(profile_js_path, "r", encoding="utf-8") as f:
            profile_js = f.read()

        self.assertIn("aggregateUserTopics", profile_js)
        self.assertIn("window.SmartContractumProfile", profile_js)

        page_js_path = os.path.join(FRONTEND_DIR, "js", "profile-page.js")
        with open(page_js_path, "r", encoding="utf-8") as f:
            page_js = f.read()

        self.assertIn("function renderSidebar", page_js)
        self.assertIn("renderSidebar: renderSidebar", page_js)
        self.assertIn("sidebarUserBio", page_js)
        self.assertIn("sidebarUserCompanyRow", page_js)
        self.assertIn("sidebarUserWebsiteRow", page_js)
        self.assertIn("sidebarUserRegistration", page_js)
        self.assertIn("sidebarUserSpecialization", page_js)
        self.assertIn("sidebarUserTopics", page_js)
        self.assertIn("sidebarReputationRating", page_js)
        self.assertIn("editProfileWebsite", page_js)

    # =========================================================================
    # Frontend CSS Tests
    # =========================================================================

    def test_frontend_css_sidebar_rules_and_media_queries(self):
        """Verifies profile.css includes two-column rules, sidebar width, sticky position, and responsive rules."""
        css_path = os.path.join(FRONTEND_DIR, "css", "profile.css")
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()

        # Desktop layout
        self.assertIn(".profile-layout-columns", css)
        self.assertIn(".profile-main-column", css)
        self.assertIn(".profile-sidebar", css)
        self.assertIn(".profile-widget", css)
        self.assertIn(".profile-widget-title", css)
        self.assertIn(".profile-widget-body", css)
        self.assertIn(".profile-sidebar-bio", css)
        self.assertIn(".profile-sidebar-meta-list", css)
        self.assertIn(".profile-sidebar-meta-item", css)
        self.assertIn(".profile-sidebar-link", css)
        self.assertIn(".profile-sidebar-expertise-list", css)
        self.assertIn(".profile-expertise-badge", css)
        self.assertIn(".profile-sidebar-topics-list", css)
        self.assertIn(".profile-sidebar-topic-pill", css)
        self.assertIn(".profile-sidebar-reputation-grid", css)
        self.assertIn(".profile-reputation-cell", css)

        # Responsive stacking
        self.assertIn("@media (max-width: 1024px)", css)
        self.assertIn("flex-direction: column", css)
        self.assertIn("@media (max-width: 768px)", css)

    # =========================================================================
    # Strict Invariant Tests
    # =========================================================================

    def test_invariants_zero_emojis(self):
        """Verifies ZERO emojis in all files modified or created for Issue #172."""
        emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]')
        files_to_check = [
            *BACKEND_FILES,
            os.path.join(FRONTEND_DIR, "profile.html"),
            os.path.join(FRONTEND_DIR, "js", "profile.js"),
            os.path.join(FRONTEND_DIR, "js", "profile-page.js"),
            os.path.join(FRONTEND_DIR, "css", "profile.css"),
            os.path.abspath(__file__)
        ]
        for fpath in files_to_check:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
                matches = emoji_pattern.findall(content)
                self.assertEqual(len(matches), 0, f"Found emojis in {fpath}: {matches}")

    def test_invariants_zero_em_dashes(self):
        """Verifies ZERO em dashes in all files modified or created for Issue #172."""
        em_dash = "\u2014"
        files_to_check = [
            os.path.join(FRONTEND_DIR, "profile.html"),
            os.path.join(FRONTEND_DIR, "js", "profile.js"),
            os.path.join(FRONTEND_DIR, "js", "profile-page.js"),
            os.path.join(FRONTEND_DIR, "css", "profile.css"),
            os.path.abspath(__file__)
        ]
        for fpath in files_to_check:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
                self.assertNotIn(em_dash, content, f"Found em dash in {fpath}")

    def test_invariants_offline_first(self):
        """Verifies 100% offline-first architecture with zero external CDN dependencies."""
        files_to_check = [
            os.path.join(FRONTEND_DIR, "profile.html"),
            os.path.join(FRONTEND_DIR, "js", "profile.js"),
            os.path.join(FRONTEND_DIR, "js", "profile-page.js"),
            os.path.join(FRONTEND_DIR, "css", "profile.css")
        ]
        url_pattern = re.compile(r'https?://[^\s"\'<>]+')
        for fpath in files_to_check:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
                urls = url_pattern.findall(content)
                for u in urls:
                    self.assertTrue(
                        "localhost" in u or "127.0.0.1" in u or "schema.org" in u or "w3.org" in u or "myblog.io" in u or "openZeppelin" in u.lower(),
                        f"External CDN or remote URL detected in {fpath}: {u}"
                    )


if __name__ == "__main__":
    unittest.main()
