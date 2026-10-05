#!/usr/bin/env python3
"""
tests/test_issue184_profile_themes_avatar_layout.py

Comprehensive automated test suite for Issue #184:
[P1][frontend][PROFILE] Темы (--bg-page vs --bg-body), размещение аватара без перекрытия, мобильная верстка

Verifies:
1. Theme variables: usage of --bg-page on .profile-page, elimination of --bg-body.
2. Avatar geometry and placement: no overlap with name, bio, or actions across all breakpoints.
3. Real inter-block spacing within #profileMainContent.
4. Compact cover height (120-160px desktop, compact on mobile).
5. Compact stats bar without repeating tab metrics; duplicate reputation passport hidden; date shown once.
6. Empty expertise and topics widgets hidden for visitors; owner prompt supported; no fake "Участник сообщества".
7. Zero horizontal overflow across 320, 375, 768, 1024, 1440 px.
8. Invariants: zero emojis, zero em dashes (\u2014), offline-first architecture.
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
import urllib.parse
import urllib.request

import server
from server import create_server, init_db

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")
CSS_PATH = os.path.join(FRONTEND_DIR, "css", "profile.css")
HTML_PATH = os.path.join(FRONTEND_DIR, "profile.html")
PAGE_JS_PATH = os.path.join(FRONTEND_DIR, "js", "profile-page.js")
PROFILE_JS_PATH = os.path.join(FRONTEND_DIR, "js", "profile.js")
THEME_CSS_PATH = os.path.join(FRONTEND_DIR, "css", "theme.css")


class TestIssue184ProfileThemesAvatarLayout(unittest.TestCase):
    """Test suite verifying Issue #184 implementation and acceptance criteria."""

    @classmethod
    def setUpClass(cls):
        with open(CSS_PATH, "r", encoding="utf-8") as f:
            cls.css = f.read()
        with open(HTML_PATH, "r", encoding="utf-8") as f:
            cls.html = f.read()
        with open(PAGE_JS_PATH, "r", encoding="utf-8") as f:
            cls.page_js = f.read()
        with open(PROFILE_JS_PATH, "r", encoding="utf-8") as f:
            cls.profile_js = f.read()
        with open(THEME_CSS_PATH, "r", encoding="utf-8") as f:
            cls.theme_css = f.read()

        cls.orig_db_path = server.DEFAULT_DB_PATH
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue184.db")
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
        server.DEFAULT_DB_PATH = cls.orig_db_path
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    @classmethod
    def _seed_test_data(cls, conn):
        cur = conn.cursor()
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # User 1: Profile exists, specialization is NULL
        cur.execute("""
            INSERT OR REPLACE INTO user_profiles (user_id, name, specialization, company, bio, website, avatar, created_at, updated_at)
            VALUES ('user_no_spec_null', 'Алиса Без Спецификации', NULL, 'OpenOrg', 'Тестовая биография', '', NULL, ?, ?)
        """, (now, now))

        # User 2: Profile exists, specialization is empty string
        cur.execute("""
            INSERT OR REPLACE INTO user_profiles (user_id, name, specialization, company, bio, website, avatar, created_at, updated_at)
            VALUES ('user_no_spec_empty', 'Борис Пустая Спецификация', '', 'OpenOrg', 'Тестовая биография', '', NULL, ?, ?)
        """, (now, now))

        # User 3: Profile exists, specialization is whitespace only
        cur.execute("""
            INSERT OR REPLACE INTO user_profiles (user_id, name, specialization, company, bio, website, avatar, created_at, updated_at)
            VALUES ('user_no_spec_whitespace', 'Виктор Пробелы', '   ', 'OpenOrg', 'Тестовая биография', '', NULL, ?, ?)
        """, (now, now))

        # User 4: User has no row in user_profiles, exists via session
        cur.execute("""
            INSERT OR REPLACE INTO sessions (token, user_id, user_name, user_role, expires_at, created_at)
            VALUES ('sess_user_no_profile', 'user_no_profile_row', 'Дмитрий Без Профиля', 'user', '2030-01-01', ?)
        """, (now,))

        # User 5: User with actual specialization
        cur.execute("""
            INSERT OR REPLACE INTO user_profiles (user_id, name, specialization, company, bio, website, avatar, created_at, updated_at)
            VALUES ('user_with_spec', 'Елена Эксперт', 'Senior Smart Contract Auditor', 'SecurityLab', 'Биография эксперта', '', NULL, ?, ?)
        """, (now, now))

        conn.commit()

    def _get_json(self, path: str):
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req) as resp:
            data = resp.read().decode("utf-8")
            return resp.status, json.loads(data) if data else {}

    # =========================================================================
    # 1. Theme Variables & Color Token Integrity
    # =========================================================================

    def test_theme_bg_page_token_used_and_bg_body_eliminated(self):
        """Verify .profile-page uses var(--bg-page) and --bg-body is completely absent."""
        self.assertNotIn("var(--bg-body", self.css, "profile.css must not use nonexistent --bg-body")
        self.assertNotIn("--bg-body", self.css, "profile.css must not reference --bg-body")

        profile_page_rule = re.search(r"\.profile-page\s*\{([^}]+)\}", self.css)
        self.assertIsNotNone(profile_page_rule, ".profile-page rule must exist in profile.css")
        rule_body = profile_page_rule.group(1)
        self.assertIn("var(--bg-page)", rule_body, ".profile-page must use background: var(--bg-page)")

    def test_card_and_surface_theme_tokens_consistency(self):
        """Verify hero, content area, sidebar widgets, and stats bar use var(--bg-card, var(--bg-surface))."""
        self.assertIn(".profile-hero", self.css)
        self.assertIn(".profile-content-area", self.css)
        self.assertIn(".profile-widget", self.css)
        self.assertIn(".profile-stats-bar", self.css)

        # Check content area card styles
        content_area_match = re.search(r"\.profile-content-area\s*\{([^}]+)\}", self.css)
        self.assertIsNotNone(content_area_match, ".profile-content-area rule must exist")
        self.assertIn("var(--bg-card", content_area_match.group(1))

        # Check buttons use high-contrast text
        sub_btn_match = re.search(r"\.btn-profile-subscribe\s*\{([^}]+)\}", self.css)
        self.assertIsNotNone(sub_btn_match, ".btn-profile-subscribe rule must exist")
        self.assertIn("#ffffff", sub_btn_match.group(1), "Subscribe button must have readable white text on primary accent")

        quick_btn_match = re.search(r"\.btn-quick-profile-open\s*\{([^}]+)\}", self.css)
        self.assertIsNotNone(quick_btn_match, ".btn-quick-profile-open rule must exist")
        self.assertIn("#ffffff", quick_btn_match.group(1), "Quick profile open button must have high-contrast white text")

    def test_subscribed_button_contrast_in_light_theme(self):
        """Verify subscribed button contrast in light theme and absence of !important on base color."""
        sub_btn_match = re.search(r"\.btn-profile-subscribe\s*\{([^}]+)\}", self.css)
        self.assertIsNotNone(sub_btn_match, ".btn-profile-subscribe rule must exist")
        base_body = sub_btn_match.group(1)
        self.assertNotIn("!important", base_body, "Base .btn-profile-subscribe must not use !important on color")
        self.assertIn("color: #ffffff", base_body, "Base .btn-profile-subscribe must specify color: #ffffff")

        subscribed_match = re.search(r"\.btn-profile-subscribe\.is-subscribed\s*\{([^}]+)\}", self.css)
        self.assertIsNotNone(subscribed_match, ".btn-profile-subscribe.is-subscribed rule must exist")
        sub_body = subscribed_match.group(1)
        self.assertIn("var(--text-secondary)", sub_body, ".btn-profile-subscribe.is-subscribed must specify var(--text-secondary)")

        light_sub_match = re.search(r"\[data-theme=[\"']light[\"']\]\s*\.btn-profile-subscribe\.is-subscribed\s*\{([^}]+)\}", self.css)
        self.assertIsNotNone(light_sub_match, "[data-theme=\"light\"] .btn-profile-subscribe.is-subscribed rule must exist")
        light_body = light_sub_match.group(1)
        self.assertIn("var(--text-primary)", light_body, "Light theme subscribed button must specify var(--text-primary)")

    # =========================================================================
    # 2. Avatar Placement & Geometric Overlap Prevention
    # =========================================================================

    def test_avatar_geometry_and_flex_wrap_prevents_overlap(self):
        """Verify avatar positioning eliminates margin collapse and guarantees no overlap with author info."""
        # .profile-identity-wrap must be a flex container to prevent margin collapsing
        identity_match = re.search(r"\.profile-identity-wrap\s*\{([^}]+)\}", self.css)
        self.assertIsNotNone(identity_match, ".profile-identity-wrap must exist")
        self.assertIn("display: flex", identity_match.group(1), ".profile-identity-wrap must be flex to avoid margin collapse")
        self.assertIn("flex-direction: column", identity_match.group(1))

        # .profile-avatar-wrap must match avatar height with positive margin-bottom
        wrap_match = re.search(r"\.profile-avatar-wrap\s*\{([^}]+)\}", self.css)
        self.assertIsNotNone(wrap_match, ".profile-avatar-wrap must exist")
        wrap_body = wrap_match.group(1)

        w_match = re.search(r"width:\s*(\d+)px", wrap_body)
        h_match = re.search(r"height:\s*(\d+)px", wrap_body)
        top_match = re.search(r"margin-top:\s*-(\d+)px", wrap_body)
        bottom_match = re.search(r"margin-bottom:\s*(\d+)px", wrap_body)

        self.assertIsNotNone(w_match)
        self.assertIsNotNone(h_match)
        self.assertIsNotNone(top_match)
        self.assertIsNotNone(bottom_match)

        wrap_w = int(w_match.group(1))
        wrap_h = int(h_match.group(1))
        neg_top = int(top_match.group(1))
        pos_bottom = int(bottom_match.group(1))

        self.assertEqual(wrap_w, 96, "Desktop avatar wrap width must be 96px")
        self.assertEqual(wrap_h, 96, "Desktop avatar wrap height must be 96px matching full avatar height")
        self.assertEqual(neg_top, 48, "Desktop negative margin must be exactly half height (-48px) to straddle cover")
        self.assertTrue(pos_bottom >= 12, "Desktop positive margin-bottom must guarantee separation from name")

        # Geometric proof:
        # Top of wrap starts at -48px relative to identity container.
        # Bottom of wrap ends at (-48 + 96) = +48px.
        # With margin-bottom >= 12px, next element starts at (+48 + 12) = +60px.
        # Avatar ends at +48px, so distance between avatar bottom and .profile-main-row is >= 12px.
        avatar_bottom = -neg_top + wrap_h
        next_element_top = avatar_bottom + pos_bottom
        clearance = next_element_top - avatar_bottom
        self.assertTrue(clearance >= 12, f"Clearance between avatar and author name must be >= 12px, was {clearance}px")

    def test_mobile_avatar_geometry_prevents_overlap(self):
        """Verify responsive breakpoints maintain wrap height == avatar height and positive margin-bottom."""
        # 640px breakpoint
        m640_wrap = re.search(r"@media\s*\([^)]*max-width:\s*640px\)[^{]*\{[\s\S]*?\.profile-avatar-wrap\s*\{([^}]+)\}", self.css)
        self.assertIsNotNone(m640_wrap, "640px breakpoint must style .profile-avatar-wrap")
        m640_h = int(re.search(r"height:\s*(\d+)px", m640_wrap.group(1)).group(1))
        m640_top = int(re.search(r"margin-top:\s*-(\d+)px", m640_wrap.group(1)).group(1))
        m640_bottom = int(re.search(r"margin-bottom:\s*(\d+)px", m640_wrap.group(1)).group(1))
        self.assertEqual(m640_top, m640_h // 2, "640px margin-top must be half height")
        self.assertTrue(m640_bottom >= 10, "640px margin-bottom must be positive")

        # 375px breakpoint
        m375_wrap = re.search(r"@media\s*\([^)]*max-width:\s*375px\)[^{]*\{[\s\S]*?\.profile-avatar-wrap\s*\{([^}]+)\}", self.css)
        self.assertIsNotNone(m375_wrap, "375px breakpoint must style .profile-avatar-wrap")
        m375_h = int(re.search(r"height:\s*(\d+)px", m375_wrap.group(1)).group(1))
        m375_top = int(re.search(r"margin-top:\s*-(\d+)px", m375_wrap.group(1)).group(1))
        m375_bottom = int(re.search(r"margin-bottom:\s*(\d+)px", m375_wrap.group(1)).group(1))
        self.assertEqual(m375_top, m375_h // 2, "375px margin-top must be half height")
        self.assertTrue(m375_bottom >= 10, "375px margin-bottom must be positive")

        # 320px breakpoint
        m320_wrap = re.search(r"@media\s*\([^)]*max-width:\s*320px\)[^{]*\{[\s\S]*?\.profile-avatar-wrap\s*\{([^}]+)\}", self.css)
        self.assertIsNotNone(m320_wrap, "320px breakpoint must style .profile-avatar-wrap")
        m320_h = int(re.search(r"height:\s*(\d+)px", m320_wrap.group(1)).group(1))
        m320_top = int(re.search(r"margin-top:\s*-(\d+)px", m320_wrap.group(1)).group(1))
        m320_bottom = int(re.search(r"margin-bottom:\s*(\d+)px", m320_wrap.group(1)).group(1))
        self.assertEqual(m320_top, m320_h // 2, "320px margin-top must be half height")
        self.assertTrue(m320_bottom >= 8, "320px margin-bottom must be positive")

    # =========================================================================
    # 3. Inter-block Spacing & Real Gaps
    # =========================================================================

    def test_profile_main_content_has_real_gap(self):
        """Verify #profileMainContent defines flex column layout and gap to separate hero, stats, and content."""
        main_content_match = re.search(r"#profileMainContent\s*\{([^}]+)\}", self.css)
        self.assertIsNotNone(main_content_match, "#profileMainContent rule must exist in profile.css")
        body = main_content_match.group(1)
        self.assertIn("display: flex", body)
        self.assertIn("flex-direction: column", body)
        self.assertIn("gap: 20px", body)

    # =========================================================================
    # 4. Compact Cover Height
    # =========================================================================

    def test_cover_height_compact_and_responsive(self):
        """Verify desktop cover height is 120-160px and becomes more compact on mobile screens."""
        desktop_cover = re.search(r"\.profile-cover\s*\{[^}]*height:\s*(\d+)px", self.css)
        self.assertIsNotNone(desktop_cover)
        desktop_h = int(desktop_cover.group(1))
        self.assertTrue(120 <= desktop_h <= 160, f"Desktop cover height ({desktop_h}px) must be between 120px and 160px")

        # Tablet (768px)
        m768_cover = re.search(r"@media\s*\([^)]*max-width:\s*768px\)[^{]*\{[\s\S]*?\.profile-cover\s*\{[^}]*height:\s*(\d+)px", self.css)
        self.assertIsNotNone(m768_cover)
        m768_h = int(m768_cover.group(1))
        self.assertTrue(m768_h <= desktop_h, "Tablet cover must be more compact than desktop")

        # Mobile (480px / 375px / 320px)
        m480_cover = re.search(r"@media\s*\([^)]*max-width:\s*480px\)[^{]*\{[\s\S]*?\.profile-cover\s*\{[^}]*height:\s*(\d+)px", self.css)
        self.assertIsNotNone(m480_cover)
        m480_h = int(m480_cover.group(1))
        self.assertTrue(m480_h <= 110, "Mobile 480px cover must be <= 110px")

        m320_cover = re.search(r"@media\s*\([^)]*max-width:\s*320px\)[^{]*\{[\s\S]*?\.profile-cover\s*\{[^}]*height:\s*(\d+)px", self.css)
        self.assertIsNotNone(m320_cover)
        m320_h = int(m320_cover.group(1))
        self.assertTrue(m320_h <= 90, "Mobile 320px cover must be <= 90px")

    # =========================================================================
    # 5. Non-Duplication of Stats and Dates
    # =========================================================================

    def test_stats_bar_compact_and_duplicates_hidden(self):
        """Verify stats bar is a single row displaying rating, solutions, followers, following, with tab metrics hidden."""
        # Stats bar layout is flex, not a 2-row multi-column grid
        stats_bar_match = re.search(r"\.profile-stats-bar\s*\{([^}]+)\}", self.css)
        self.assertIsNotNone(stats_bar_match)
        self.assertIn("display: flex", stats_bar_match.group(1))

        # Hidden class hides duplicate publication, question, answer, and date tiles from bar
        self.assertIn(".profile-stat-hidden", self.css)
        hidden_rule = re.search(r"\.profile-stat-hidden\s*\{([^}]+)\}", self.css)
        self.assertIsNotNone(hidden_rule)
        self.assertIn("display: none", hidden_rule.group(1))

        # Account age in stats bar is hidden because it is in "About" sidebar
        age_rule = re.search(r"\.profile-account-age\s*\{([^}]+)\}", self.css)
        self.assertIsNotNone(age_rule)
        self.assertIn("display: none", age_rule.group(1))

        # Duplicate reputation widget is hidden
        rep_rule = re.search(r"\.profile-widget-reputation\s*\{([^}]+)\}", self.css)
        self.assertIsNotNone(rep_rule)
        self.assertIn("display: none", rep_rule.group(1))

    # =========================================================================
    # 6. Expertise and Topics Handling
    # =========================================================================

    def test_specialization_logic_in_profile_page_js(self):
        """Verify specialization is only shown when present and not defaulted to fake expertise."""
        self.assertIn("if (p.specialization && p.specialization.trim())", self.page_js)
        # Should hide spec if empty
        self.assertIn("specEl.style.display = 'none'", self.page_js)

    def test_empty_widgets_hidden_for_visitor(self):
        """Verify renderSidebar hides expertise and topics widgets when empty for visitors."""
        self.assertIn("if (widgetExp) widgetExp.style.display = 'none'", self.page_js)
        self.assertIn("if (widgetTopics) widgetTopics.style.display = 'none'", self.page_js)

    def test_get_user_profile_without_specialization_returns_empty_string(self):
        """Verify GET /api/users/<id> for a user without specialization returns specialization='' and not 'Участник сообщества'."""
        test_cases = [
            ("user_no_spec_null", "User with NULL specialization"),
            ("user_no_spec_empty", "User with empty string specialization"),
            ("user_no_spec_whitespace", "User with whitespace-only specialization"),
            ("user_no_profile_row", "User without user_profiles row"),
        ]

        for uid, desc in test_cases:
            with self.subTest(user_id=uid, description=desc):
                status, data = self._get_json(f"/api/users/{uid}")
                self.assertEqual(status, 200)
                self.assertTrue(data.get("success", False))

                profile = data.get("profile", {})
                self.assertEqual(
                    profile.get("specialization"),
                    "",
                    f"Profile specialization must be empty string for {desc}"
                )
                self.assertNotEqual(
                    profile.get("specialization"),
                    "Участник сообщества",
                    f"Profile specialization must not be 'Участник сообщества' for {desc}"
                )

                user = data.get("user", {})
                self.assertEqual(
                    user.get("specialization"),
                    "",
                    f"User specialization must be empty string for {desc}"
                )
                self.assertNotEqual(
                    user.get("specialization"),
                    "Участник сообщества",
                    f"User specialization must not be 'Участник сообщества' for {desc}"
                )

        # Also verify user with genuine specialization is preserved
        status, data = self._get_json("/api/users/user_with_spec")
        self.assertEqual(status, 200)
        self.assertEqual(data.get("profile", {}).get("specialization"), "Senior Smart Contract Auditor")


    # =========================================================================
    # 7. Zero Horizontal Overflow & Word Wrapping
    # =========================================================================

    def test_zero_horizontal_overflow_and_word_breaking(self):
        """Verify layout and text rules prevent horizontal page scrolling on long words/URLs."""
        self.assertIn("overflow-x: hidden", self.css)
        self.assertIn("word-break: break-word", self.css)
        self.assertIn("overflow-wrap: anywhere", self.css)
        self.assertIn("word-break: break-all", self.css)

    # =========================================================================
    # 8. Project Invariants
    # =========================================================================

    def test_invariants_zero_emojis(self):
        """Verify zero emojis in modified CSS, HTML, and JS files."""
        emoji_pattern = re.compile(
            r"[\U0001F600-\U0001F64F"  # Emoticons
            r"\U0001F300-\U0001F5FF"  # Misc Symbols and Pictographs
            r"\U0001F680-\U0001F6FF"  # Transport and Map
            r"\U0001F1E0-\U0001F1FF"  # Regional indicator symbols
            r"\U00002702-\U000027B0"  # Dingbats
            r"\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
            r"\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
            r"]"
        )
        for name, content in [("profile.css", self.css), ("profile.html", self.html), ("profile-page.js", self.page_js)]:
            matches = emoji_pattern.findall(content)
            self.assertEqual(len(matches), 0, f"Found emoji in {name}: {matches}")

    def test_invariants_zero_em_dashes(self):
        """Verify zero em dashes in profile CSS, HTML, and JS files."""
        for name, content in [("profile.css", self.css), ("profile.html", self.html), ("profile-page.js", self.page_js)]:
            self.assertNotIn("\u2014", content, f"Found em dash in {name}")

    def test_invariants_offline_first(self):
        """Verify no external CDN or HTTP resources are imported in CSS or HTML."""
        self.assertNotIn("@import url('https://", self.css)
        self.assertNotIn("@import url(\"https://", self.css)
        self.assertNotIn("<link rel=\"stylesheet\" href=\"https://", self.html)
        self.assertNotIn("<script src=\"https://", self.html)


if __name__ == "__main__":
    unittest.main()
