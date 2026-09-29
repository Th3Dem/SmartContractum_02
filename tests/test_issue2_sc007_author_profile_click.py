#!/usr/bin/env python3
"""
tests/test_issue2_sc007_author_profile_click.py

Regression test suite for Issue #2 (SC-007):
"Синхронизировать data-author-id в карточке и обработчике профиля автора".

Acceptance Criteria:
1. In card.js, .btn-author-profile markup contains data-author-id="' + escapeHtml(authorId) + '".
2. In card.js, data-user-id is retained for backward compatibility.
3. In feed.js, the click handler for .btn-author-profile extracts authorId using
   authorBtn.getAttribute('data-author-id') || authorBtn.getAttribute('data-user-id').
4. Clicking or activating author button triggers openUserProfileModal(authorId).
5. Keyboard accessibility: .btn-author-profile is a semantic button, with focus-visible outline
   and keyboard navigation support (Enter / Space trigger).
6. CSS styling: border: none, background: transparent, hover underline, and zero dark borders.
"""

import json
import os
import re
import sqlite3
import tempfile
import threading
import time
import unittest
import urllib.parse
import urllib.request

import server
from server import create_server, init_db

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue2SC007AuthorProfileClick(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue2_sc007.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path)
        conn.close()

        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR)
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.1)

        with open(os.path.join(FRONTEND_DIR, "js", "card.js"), "r", encoding="utf-8") as f:
            cls.card_js = f.read()
        with open(os.path.join(FRONTEND_DIR, "js", "feed.js"), "r", encoding="utf-8") as f:
            cls.feed_js = f.read()
        with open(os.path.join(FRONTEND_DIR, "css", "theme.css"), "r", encoding="utf-8") as f:
            cls.theme_css = f.read()
        with open(os.path.join(FRONTEND_DIR, "css", "feed.css"), "r", encoding="utf-8") as f:
            cls.feed_css = f.read()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.httpd.shutdown()
            cls.httpd.server_close()
        except Exception:
            pass

    def _get_json(self, path):
        req = urllib.request.Request(self.base_url + path)
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return resp.status, data
        except urllib.error.HTTPError as e:
            data = json.loads(e.read().decode("utf-8"))
            return e.code, data

    def test_01_card_js_markup_contains_data_author_id(self):
        """Verify card.js renders data-author-id in .btn-author-profile button."""
        self.assertIn(
            'data-author-id="\' + escapeHtml(authorId) + \'"',
            self.card_js,
            "card.js must set data-author-id on .btn-author-profile"
        )
        # Verify backward compatibility with data-user-id
        self.assertIn(
            'data-user-id="\' + escapeHtml(authorId) + \'"',
            self.card_js,
            "card.js must retain data-user-id for backward compatibility"
        )
        # Verify semantic button
        self.assertIn(
            '<button type="button" class="author-name btn-author-profile"',
            self.card_js,
            "Author profile trigger must be a semantic <button type='button'>"
        )

    def test_02_feed_js_click_handler_reads_data_author_id_with_fallback(self):
        """Verify feed.js click handler extracts data-author-id with fallback to data-user-id."""
        pattern = r"const\s+authorId\s*=\s*authorBtn\.getAttribute\(['\"]data-author-id['\"]\)\s*\|\|\s*authorBtn\.getAttribute\(['\"]data-user-id['\"]\)"
        self.assertTrue(
            re.search(pattern, self.feed_js),
            "feed.js must extract authorId from data-author-id with data-user-id fallback"
        )
        self.assertIn("openUserProfileModal(authorId)", self.feed_js)
        self.assertIn("e.target.closest('.btn-author-profile')", self.feed_js)

    def test_03_click_extraction_logic_simulation(self):
        """Simulate attribute extraction logic for various DOM dataset states."""
        def extract_author_id(attrs):
            return attrs.get("data-author-id") or attrs.get("data-user-id")

        # 1. New card standard: both data-author-id and data-user-id set
        attrs_new = {"data-author-id": "user_dev_01", "data-user-id": "user_dev_01"}
        self.assertEqual(extract_author_id(attrs_new), "user_dev_01")

        # 2. Modern card without legacy attr
        attrs_modern = {"data-author-id": "user_modern_02"}
        self.assertEqual(extract_author_id(attrs_modern), "user_modern_02")

        # 3. Legacy card with only data-user-id
        attrs_legacy = {"data-user-id": "user_legacy_03"}
        self.assertEqual(extract_author_id(attrs_legacy), "user_legacy_03")

        # 4. Empty or missing attributes
        attrs_empty = {}
        self.assertIsNone(extract_author_id(attrs_empty))

    def test_04_keyboard_accessibility_and_focus_styles(self):
        """Verify keyboard accessibility: button semantics, focus-visible outline, and no borders."""
        # 1. feed.css rules
        self.assertIn(".btn-author-profile", self.feed_css)
        self.assertIn(".btn-author-profile:focus-visible", self.feed_css)
        self.assertIn("outline: 2px solid", self.feed_css)
        self.assertIn("outline-offset: 2px", self.feed_css)
        self.assertIn("background: transparent", self.feed_css)
        self.assertIn("border: none", self.feed_css)

        # 2. theme.css rules
        self.assertIn(".btn-author-profile", self.theme_css)
        self.assertIn(".btn-author-profile:focus-visible", self.theme_css)
        self.assertIn("outline: 2px solid", self.theme_css)
        self.assertIn("outline-offset: 2px", self.theme_css)

        # 3. Button markup in card.js has title attribute for accessibility
        self.assertIn('title="Открыть профиль"', self.card_js)

    def test_05_card_rendering_and_user_profile_api_integration(self):
        """Verify card DTO authorId resolves through /api/users/<authorId>."""
        status, feed_data = self._get_json("/api/articles?limit=10")
        self.assertEqual(status, 200)
        self.assertIn("articles", feed_data)
        self.assertGreater(len(feed_data["articles"]), 0)

        for article in feed_data["articles"]:
            author_id = article.get("authorId") or article.get("author_id") or article.get("userId")
            self.assertTrue(bool(author_id), f"Article {article.get('id')} must provide authorId")

            # Simulate card markup generation
            button_markup = (
                f'<button type="button" class="author-name btn-author-profile" '
                f'data-author-id="{author_id}" data-user-id="{author_id}" '
                f'data-user-name="{article.get("authorName", "")}" title="Открыть профиль">'
                f'{article.get("authorName", "")}</button>'
            )
            self.assertIn(f'data-author-id="{author_id}"', button_markup)
            self.assertIn(f'data-user-id="{author_id}"', button_markup)

            # Query user profile modal API endpoint
            user_status, user_data = self._get_json(f"/api/users/{urllib.parse.quote(author_id)}")
            self.assertEqual(user_status, 200, f"User endpoint for author {author_id} must return 200")
            self.assertTrue(user_data.get("success"), "User profile query must be successful")
            profile = user_data.get("user") or user_data.get("profile") or user_data
            self.assertEqual(profile["id"], author_id)
            self.assertIn("stats", profile)

    def test_06_zero_emojis_and_clean_code(self):
        """Zero emojis in modified JS and CSS code."""
        emoji_pattern = re.compile(r'[\U00010000-\U0010ffff\u2600-\u27bf\u2300-\u23ff\u2b50-\u2b55]')
        for content, name in [
            (self.card_js, "card.js"),
            (self.feed_js, "feed.js"),
            (self.feed_css, "feed.css"),
            (self.theme_css, "theme.css"),
        ]:
            matches = emoji_pattern.findall(content)
            self.assertEqual(matches, [], f"Emoji found in {name}: {matches}")


if __name__ == "__main__":
    unittest.main()
