#!/usr/bin/env python3
"""
tests/test_issue173_quick_profile_redesign.py

Automated test suite for Issue #173:
Quick Profile: redesign of compact modal card and transition to full profile.

Acceptance Criteria:
1. Modal card rendering in profile.js:
   - Does NOT render long scrollable publications list (.user-profile-articles-title, .user-profile-articles-list).
   - Renders compact reputation & activity summary with rating box and meta-metrics line.
   - Rating box has approved tooltip: "Сумма оценок публикаций, ответов и комментариев. Лайки не учитываются".
   - Meta-line renders pluralized counts: e.g. "N публикаций · M ответов · K решений".
   - Real avatar: renders <img> when avatar is present, fallback initials when null.
   - Title link: user name renders as link to profile.html?id=:id.
   - Foreign profile: subscribe button (.btn-quick-profile-subscribe) with toggle state, and primary CTA "Открыть профиль →" (.btn-quick-profile-open).
   - Own profile: subscribe button hidden, primary CTA displayed.
   - Modal title is neutral: "Профиль пользователя" (not "Профиль эксперта").
2. CSS in profile.css:
   - Modal card max-width is 460px.
   - Body padding is 20px 24px.
   - Rules present for .user-profile-rating-box, .user-profile-meta-line, .quick-profile-actions, .btn-quick-profile-open, .btn-quick-profile-subscribe.
   - Backward compatibility classes retained (.user-profile-modal-card, .user-profile-stats, .user-profile-stat-box, .user-profile-rating-num).
3. Invariants:
   - 100% offline-first.
   - Zero emojis.
   - Zero em dashes (use hyphen or colon).
"""

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
from typing import Any, Dict, Optional, Tuple

import server
from server import create_server, init_db

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue173QuickProfileRedesign(unittest.TestCase):
    """Verifies all requirements for Issue #173 Quick Profile redesign."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue173.db")
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

    def _login(self, user_id: str, name: str = "Test User") -> str:
        url = f"{self.base_url}/api/auth/login"
        body = json.dumps({"userId": user_id, "name": name, "role": "user"}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST"
        )
        with urllib.request.urlopen(req) as resp:
            return resp.headers.get("Set-Cookie", "")

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
            e.close()
            return e.code, json.loads(res_body) if res_body else {}

    def _insert_user_profile(self, user_id: str, name: str, specialization: str = "", company: str = "", bio: str = "", avatar: Optional[str] = None) -> None:
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO user_profiles (user_id, name, specialization, company, bio, avatar, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """, (user_id, name, specialization, company, bio, avatar))
        conn.close()

    # Issues #271 and #272 replaced the central quick profile modal with the author mini card
    # (non-modal popover in profile.js). The checks below keep the intent of #173 on the new card.

    def _profile_js(self):
        with open(os.path.join(FRONTEND_DIR, "js", "profile.js"), "r", encoding="utf-8") as f:
            return f.read()

    def _render_fn(self):
        code = self._profile_js()
        idx = code.find("function render(p, userId)")
        self.assertNotEqual(idx, -1)
        return code[idx:idx + 5000]

    def test_01_profile_js_removes_publications_list_and_renders_cta(self):
        """The card has no publications list and links to the full profile."""
        render_fn = self._render_fn()
        self.assertNotIn("articlesHtml", render_fn)
        self.assertNotIn("user-profile-articles-list", render_fn)
        self.assertIn("profile.html?id=", render_fn)
        self.assertIn("Перейти в профиль", render_fn)
        self.assertIn("author-card-name", render_fn)

    def test_02_reputation_summary_and_pluralized_activity_line(self):
        """Rating with its explanation and the four profile metrics."""
        render_fn = self._render_fn()
        self.assertIn("author-card-rating", render_fn)
        self.assertIn("Сумма оценок публикаций, ответов и комментариев. Лайки не учитываются", render_fn)
        for label in ("Подписчики", "Публикации", "Вопросы", "Комментарии"):
            self.assertIn(label, render_fn)

    def test_03_avatar_real_image_and_fallback(self):
        """Real avatar image with initials underneath as the fallback."""
        render_fn = self._render_fn()
        self.assertIn("author-card-avatar-img", render_fn)
        self.assertIn("author-card-initials", render_fn)
        self.assertIn("p.avatar", render_fn)

    def test_04_foreign_vs_own_profile_actions(self):
        """Subscribe for other people, no subscribe on the own profile."""
        code = self._profile_js()
        self.assertIn("author-card-subscribe", code)
        self.assertIn("is-subscribed", code)
        self.assertIn("Вы подписаны", code)
        self.assertIn("Подписаться", code)
        self.assertIn("isOwn", code)
        self.assertIn("Это ваш профиль", code)
        self.assertIn("/api/subscriptions/toggle", code)

    def test_05_modal_title_neutral_in_all_templates(self):
        """No generic modal title and no old modal markup; the card is labelled by the author name."""
        for p in ["feed.html", "article.html", "profile.html"]:
            with open(os.path.join(FRONTEND_DIR, p), "r", encoding="utf-8") as f:
                content = f.read()
            self.assertNotIn("userProfileModalTitle", content)
            self.assertNotIn("Профиль эксперта", content)
        js_code = self._profile_js()
        self.assertNotIn("Профиль пользователя'", js_code)
        self.assertIn("card.setAttribute('aria-labelledby', 'authorCardName');", js_code)

    def test_06_css_compact_geometry_and_classes(self):
        """Verify profile.css defines max-width: 460px, padding: 20px 24px, and action styles."""
        profile_css_path = os.path.join(FRONTEND_DIR, "css", "profile.css")
        with open(profile_css_path, "r", encoding="utf-8") as f:
            css = f.read()

        # Geometry
        self.assertIn("max-width: 460px", css)
        self.assertIn("padding: 20px 24px", css)

        # Classes
        self.assertIn(".user-profile-rating-box", css)
        self.assertIn(".user-profile-meta-line", css)
        self.assertIn(".quick-profile-actions", css)
        self.assertIn(".btn-quick-profile-open", css)
        self.assertIn(".btn-quick-profile-subscribe", css)

        # Retained compatibility
        self.assertIn(".user-profile-modal-card", css)
        self.assertIn(".user-profile-stats", css)
        self.assertIn(".user-profile-stat-box", css)
        self.assertIn(".user-profile-rating-num", css)

    def test_07_api_is_own_profile_field(self):
        """Verify GET /api/users/:id includes isOwnProfile flag when authenticated."""
        user_alice = "alice_quick_173"
        user_bob = "bob_quick_173"
        self._insert_user_profile(user_alice, "Alice Quick")
        self._insert_user_profile(user_bob, "Bob Quick")

        cookie_alice = self._login(user_alice, "Alice Quick")

        # Alice views Alice: isOwnProfile is True
        status, data_alice = self._get_json(f"/api/users/{user_alice}", cookie=cookie_alice)
        self.assertEqual(status, 200)
        self.assertTrue(data_alice.get("isOwnProfile"))

        # Alice views Bob: isOwnProfile is False
        status, data_bob = self._get_json(f"/api/users/{user_bob}", cookie=cookie_alice)
        self.assertEqual(status, 200)
        self.assertFalse(data_bob.get("isOwnProfile"))

    def test_08_invariants_zero_emojis_zero_em_dashes_offline(self):
        """Verify zero emojis, zero em dashes, and 100% offline-first in modified files."""
        emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]', flags=re.UNICODE)
        files = [
            os.path.join(FRONTEND_DIR, "js", "profile.js"),
            os.path.join(FRONTEND_DIR, "css", "profile.css"),
            os.path.join(FRONTEND_DIR, "article.html"),
            os.path.join(FRONTEND_DIR, "profile.html"),
        ]

        for filepath in files:
            self.assertTrue(os.path.exists(filepath), f"{filepath} must exist")
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIsNone(
                emoji_pattern.search(content),
                f"Emoji found in {os.path.basename(filepath)}"
            )

            self.assertNotIn(
                "\u2014", content,
                f"Em dash found in {os.path.basename(filepath)}"
            )

            # Offline check: no external asset fetches
            clean_content = content.replace("http://www.w3.org/2000/svg", "")
            self.assertNotIn("http://", clean_content)
            self.assertNotIn("https://", clean_content)

        # The old modal markup is gone from the feed (Issues #271, #272)
        with open(os.path.join(FRONTEND_DIR, "feed.html"), "r", encoding="utf-8") as f:
            self.assertNotIn('id="userProfileModal"', f.read())

if __name__ == "__main__":
    unittest.main()
