#!/usr/bin/env python3
"""
tests/test_issue169_full_profile_header.py

Automated test suite for Issue #169:
[P0][frontend] Full Profile: страница пользователя, header, cover, avatar, identity и статистика.

Invariants:
- Zero emojis
- Zero em dashes
- 100% offline-first
"""

import http.client
import json
import os
import re
import shutil
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request

import server
from server import create_server, init_db

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue169FullProfileHeader(unittest.TestCase):
    """Verifies all markup, styling, interaction, and invariants for Issue #169."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue169.db")
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

    def test_01_profile_html_structure_and_assets(self):
        """Verify profile.html exists, includes semantic markup, css, scripts, and shared header navigation."""
        profile_html_path = os.path.join(FRONTEND_DIR, "profile.html")
        self.assertTrue(os.path.exists(profile_html_path), "frontend/public/profile.html must exist")

        with open(profile_html_path, "r", encoding="utf-8") as f:
            html = f.read()

        # Offline font & styles
        self.assertIn("css/theme.css", html)
        self.assertIn("css/feed.css", html)
        self.assertIn("css/profile.css", html)
        self.assertIn("Onest", html)

        # Scripts
        self.assertIn("js/card.js", html)
        self.assertIn("js/profile.js", html)
        self.assertIn("js/profile-page.js", html)

        # Shared header
        self.assertIn("appHeader", html)
        self.assertTrue("app-header" in html or "feed-header" in html)
        self.assertIn("brand-logo", html)
        self.assertIn("SmartContractum", html)
        self.assertIn("headerNav", html)
        self.assertIn("btnThemeToggle", html)
        self.assertIn("headerNotificationsBtn", html)
        self.assertIn("headerLoginBtn", html)
        self.assertIn("header-search-input", html)

        # Core containers
        self.assertIn("profile-page-container", html)
        self.assertIn("profile-hero", html)
        self.assertIn("profile-stats-bar", html)
        self.assertIn("profile-content-area", html)

    def test_02_hero_block_geometry_and_classes(self):
        """Verify cover height (140-180px), avatar geometry (88-104px, overlap, border), and identity elements."""
        profile_css_path = os.path.join(FRONTEND_DIR, "css", "profile.css")
        with open(profile_css_path, "r", encoding="utf-8") as f:
            css = f.read()

        # Cover height check
        cover_match = re.search(r"\.profile-cover\s*\{[^}]*height:\s*(\d+)px", css)
        self.assertIsNotNone(cover_match, "profile.css must define height for .profile-cover")
        cover_height = int(cover_match.group(1))
        self.assertTrue(140 <= cover_height <= 180, f"Cover height ({cover_height}px) must be between 140px and 180px")

        # Avatar geometry check
        avatar_match = re.search(r"\.profile-avatar\s*\{[^}]*width:\s*(\d+)px[^}]*height:\s*(\d+)px", css)
        self.assertIsNotNone(avatar_match, "profile.css must define width and height for .profile-avatar")
        avatar_w = int(avatar_match.group(1))
        avatar_h = int(avatar_match.group(2))
        self.assertTrue(88 <= avatar_w <= 104, f"Avatar width ({avatar_w}px) must be between 88px and 104px")
        self.assertTrue(88 <= avatar_h <= 104, f"Avatar height ({avatar_h}px) must be between 88px and 104px")
        self.assertIn("margin-top: -", css, "Avatar must overlap lower edge of cover via negative margin")
        self.assertIn("border: 4px solid", css, "Avatar must have 4px solid border")

        # HTML elements check
        profile_html_path = os.path.join(FRONTEND_DIR, "profile.html")
        with open(profile_html_path, "r", encoding="utf-8") as f:
            html = f.read()

        self.assertIn('class="profile-cover"', html)
        self.assertIn('class="profile-avatar"', html)
        self.assertIn('class="profile-avatar-img"', html)
        self.assertIn('class="profile-name"', html)
        self.assertIn('class="profile-spec"', html)
        self.assertIn('class="profile-company"', html)
        self.assertIn('class="profile-bio"', html)
        self.assertIn('class="profile-actions"', html)
        self.assertIn('class="btn-profile-subscribe"', html)
        self.assertIn('class="btn-profile-edit"', html)
        self.assertIn('class="btn-profile-more"', html)

    def test_03_stats_bar_reputation_and_metrics(self):
        """Verify statistics & reputation bar displays rating with approved tooltip and all required counters."""
        profile_html_path = os.path.join(FRONTEND_DIR, "profile.html")
        with open(profile_html_path, "r", encoding="utf-8") as f:
            html = f.read()

        # Primary reputation metric with approved tooltip
        self.assertIn("profile-stat-rating", html)
        self.assertIn("Рейтинг складывается из оценок публикаций, ответов и комментариев. Лайки не учитываются", html)
        self.assertIn("Рейтинг", html)

        # Activity and social metrics
        self.assertIn("profileStatPublications", html)
        self.assertIn("Публикаций", html)
        self.assertIn("profileStatQuestions", html)
        self.assertIn("Вопросов", html)
        self.assertIn("profileStatAnswers", html)
        self.assertIn("Ответов", html)
        self.assertIn("profileStatSolutions", html)
        self.assertIn("Решений", html)
        self.assertIn("profileStatFollowers", html)
        self.assertIn("Подписчиков", html)
        self.assertIn("profileStatFollowing", html)
        self.assertIn("Подписок", html)

        # Account age
        self.assertIn("profile-account-age", html)
        self.assertIn("На платформе с", html)

    def test_04_profile_page_js_logic_and_simulation(self):
        """Verify profile-page.js reads userId, renders profile, handles own vs foreign actions, and toggles subscriptions."""
        profile_page_js_path = os.path.join(FRONTEND_DIR, "js", "profile-page.js")
        self.assertTrue(os.path.exists(profile_page_js_path), "js/profile-page.js must exist")

        with open(profile_page_js_path, "r", encoding="utf-8") as f:
            js = f.read()

        # URL extraction
        self.assertIn("window.location.search", js)
        self.assertIn("window.location.pathname", js)

        # API fetch
        self.assertIn("/api/users/", js)
        self.assertIn("/api/auth/status", js)
        self.assertIn("/api/subscriptions/toggle", js)

        # Own profile vs foreign profile separation
        self.assertIn("currentUser.id === p.id", js)
        self.assertIn("btnSubscribe.style.display = 'none'", js)
        self.assertIn("btnEdit.style.display = 'inline-flex'", js)

        # Copy profile link action
        self.assertIn("navigator.clipboard.writeText", js)

        # Edit profile modal interaction
        self.assertIn("openEditModal", js)
        self.assertIn("saveProfileEdit", js)
        self.assertIn("/api/user/profile", js)

    def test_05_http_endpoint_serving_profile_html_and_redirect(self):
        """Verify HTTP server serves profile.html on GET and redirects /user/:id via 302."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request("GET", "/profile.html")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        self.assertIn("text/html", resp.getheader("Content-Type", ""))
        body = resp.read().decode("utf-8")
        self.assertIn("profile-page-container", body)
        conn.close()

        # Verify /user/<id> redirects to /profile.html?id=<id>
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request("GET", "/user/vitalik_buterin")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 302)
        self.assertEqual(resp.getheader("Location"), "/profile.html?id=vitalik_buterin")
        resp.read()
        conn.close()

    def test_06_invariants_zero_emojis_zero_em_dashes_offline(self):
        """Verify 100% offline-first, zero emojis, and zero em dashes across all new and modified assets."""
        emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]', flags=re.UNICODE)

        files_to_check = [
            os.path.join(FRONTEND_DIR, "profile.html"),
            os.path.join(FRONTEND_DIR, "css", "profile.css"),
            os.path.join(FRONTEND_DIR, "js", "profile-page.js"),
        ]

        for filepath in files_to_check:
            self.assertTrue(os.path.exists(filepath), f"File {filepath} must exist")
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Zero emojis
            self.assertIsNone(
                emoji_pattern.search(content),
                f"Emoji found in {os.path.basename(filepath)}"
            )

            # Zero em dashes
            self.assertNotIn(
                "\u2014", content,
                f"Em dash found in {os.path.basename(filepath)}"
            )

            # Zero external CDN links
            clean_content = content.replace("http://www.w3.org/2000/svg", "")
            self.assertNotIn("http://", clean_content)
            self.assertNotIn("https://", clean_content)


if __name__ == "__main__":
    unittest.main()
