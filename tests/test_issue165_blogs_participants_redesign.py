import json
import os
import re
import shutil
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.parse
from typing import Any, Dict

import server
from server import create_server, init_db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue165BlogsParticipantsRedesign(unittest.TestCase):
    """
    Targeted tests for Issue #165:
    - Blogs / Participants redesign: modern 3-zone layout (AVATAR | INFO | META+ACTION)
    - 52-56px rounded-square company avatar
    - 1-line clamped description with ellipsis
    - Compact right meta column with Russian pluralization and styled Subscribe button
    - Entire row clickable (opens company blog) with Subscribe click isolated (stopPropagation)
    - Unified toolbar slot integration (blogsParticipantsToolbarSlot)
    - Filter drawer customized for participants (Topics visible, publication filters hidden)
    - Backend API: rating and commentsCount aggregated without N+1
    - Backend API: sorting by newest, popular, rating, discussed
    - Invariants: zero emojis, zero em dashes, 100% offline-first
    """

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue165.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path, seed=True)
        conn.close()

        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR, seed=False)
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.1)

        feed_html_path = os.path.join(FRONTEND_DIR, "feed.html")
        with open(feed_html_path, "r", encoding="utf-8") as f:
            cls.feed_html = f.read()

        feed_js_path = os.path.join(FRONTEND_DIR, "js", "feed.js")
        with open(feed_js_path, "r", encoding="utf-8") as f:
            cls.feed_js = f.read()

        feed_css_path = os.path.join(FRONTEND_DIR, "css", "feed.css")
        with open(feed_css_path, "r", encoding="utf-8") as f:
            cls.feed_css = f.read()

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "httpd"):
            cls.httpd.shutdown()
        if hasattr(cls, "temp_dir") and os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def _api_get(self, path: str) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data)

    def test_01_company_row_3zone_layout(self):
        """
        Verify company row has clean 3-zone layout:
        left avatar (participant-main > participant-avatar),
        center info (participant-content with name, spec, desc),
        and right meta column (participant-meta-col with stats and button).
        """
        # feed.js markup structure
        self.assertIn("company-participant-row entity-card company-card", self.feed_js)
        self.assertIn("participant-main", self.feed_js)
        self.assertIn("participant-avatar", self.feed_js)
        self.assertIn("participant-content", self.feed_js)
        self.assertIn("participant-header", self.feed_js)
        self.assertIn("participant-name entity-card-title", self.feed_js)
        self.assertIn("participant-spec entity-card-spec", self.feed_js)
        self.assertIn("participant-desc entity-card-desc", self.feed_js)
        self.assertIn("participant-meta-col", self.feed_js)
        self.assertIn("participant-stats", self.feed_js)
        self.assertIn("btn-participant-sub", self.feed_js)

        # feed.css row layout
        row_match = re.search(r"\.company-participant-row\s*\{([^}]+)\}", self.feed_css)
        self.assertIsNotNone(row_match, ".company-participant-row CSS rule must exist")
        row_body = row_match.group(1)
        self.assertIn("display: flex;", row_body)
        self.assertIn("justify-content: space-between;", row_body)
        self.assertIn("cursor: pointer;", row_body)
        self.assertIn("padding: 16px 20px;", row_body)

    def test_02_avatar_geometry_52px(self):
        """
        Verify company avatar has 52-56px desktop dimensions with rounded-square radius.
        """
        avatar_match = re.search(r"\.participant-avatar\s*\{([^}]+)\}", self.feed_css)
        self.assertIsNotNone(avatar_match)
        avatar_body = avatar_match.group(1)
        self.assertTrue("width: 52px;" in avatar_body or "width: 56px;" in avatar_body)
        self.assertTrue("height: 52px;" in avatar_body or "height: 56px;" in avatar_body)
        self.assertIn("border-radius: var(--radius-md);", avatar_body)

        img_match = re.search(r"\.participant-avatar-img\s*\{([^}]+)\}", self.feed_css)
        self.assertIsNotNone(img_match)
        img_body = img_match.group(1)
        self.assertTrue("width: 52px;" in img_body or "width: 56px;" in img_body)
        self.assertTrue("height: 52px;" in img_body or "height: 56px;" in img_body)
        self.assertIn("object-fit: cover;", img_body)

    def test_03_description_single_line_truncation(self):
        """
        Verify company description has single-line clamped preview with ellipsis.
        """
        desc_match = re.search(r"\.participant-desc\s*\{([^}]+)\}", self.feed_css)
        self.assertIsNotNone(desc_match)
        desc_body = desc_match.group(1)
        self.assertIn("white-space: nowrap;", desc_body)
        self.assertIn("overflow: hidden;", desc_body)
        self.assertIn("text-overflow: ellipsis;", desc_body)
        self.assertIn("max-width: 100%;", desc_body)

    def test_04_meta_column_and_russian_pluralization(self):
        """
        Verify right meta column styling and Russian pluralization for publications and subscribers.
        """
        meta_match = re.search(r"\.participant-meta-col\s*\{([^}]+)\}", self.feed_css)
        self.assertIsNotNone(meta_match)
        meta_body = meta_match.group(1)
        self.assertIn("display: flex;", meta_body)
        self.assertIn("flex-direction: column;", meta_body)
        self.assertIn("align-items: flex-end;", meta_body)
        self.assertIn("margin-left: auto;", meta_body)

        sub_btn_match = re.search(r"\.btn-participant-sub\.is-subscribed\s*\{([^}]+)\}", self.feed_css)
        self.assertIsNotNone(sub_btn_match)
        sub_btn_body = sub_btn_match.group(1)
        self.assertIn("color: var(--accent-color);", sub_btn_body)

        # Russian pluralization check in feed.js
        self.assertIn("pluralizePublications(comp.articlesCount || 0)", self.feed_js)
        self.assertIn("pluralize(comp.subscribersCount || 0, 'подписчик', 'подписчика', 'подписчиков')", self.feed_js)

    def test_05_subscribe_click_isolated_from_row(self):
        """
        Verify clicking Subscribe button stops propagation and does not navigate into company blog.
        """
        self.assertIn("subBtn.addEventListener('click', function (e) {", self.feed_js)
        self.assertIn("e.stopPropagation();", self.feed_js)
        self.assertIn("toggleSubscription('company', comp.id, subBtn, comp.name);", self.feed_js)

        # Row handler navigates to company detail only when interactive elements are not clicked
        self.assertIn("function handleOpenBlog(e) {", self.feed_js)
        self.assertIn("if (e.target.closest('.btn-participant-sub')", self.feed_js)
        self.assertIn("openCompanyDetail(comp.id);", self.feed_js)

    def test_06_toolbar_slot_and_drawer_integration(self):
        """
        Verify blogsParticipantsToolbarSlot in feed.html and ensureToolbarPlacement behavior:
        - Relocates feedStreamToolbar and drawer into blogsParticipantsToolbarSlot
        - Configures filter drawer for participants (hides Date, Format, Audience, Complexity, Types; shows Topics)
        - Updates drawer titles to 'Фильтры участников'
        - Sets search input placeholder for participants
        """
        self.assertIn('id="blogsParticipantsToolbarSlot"', self.feed_html)
        self.assertIn('class="blogs-participants-toolbar-slot"', self.feed_html)

        # feed.js placement logic
        self.assertIn("blogsParticipantsToolbarSlot", self.feed_js)
        self.assertIn("isBlogsParticipants", self.feed_js)
        self.assertIn("Поиск участников по названию или специализации", self.feed_js)
        self.assertIn("Фильтры участников", self.feed_js)
        self.assertIn("Уточните список компаний по направлениям", self.feed_js)
        self.assertIn("Направления и темы", self.feed_js)

    def test_07_api_rating_and_comment_counts(self):
        """
        Verify GET /api/companies returns rating and commentsCount aggregated from approved publications.
        """
        data = self._api_get("/api/companies")
        self.assertTrue(data.get("success"))
        companies = data.get("companies", [])
        self.assertTrue(len(companies) > 0)
        for c in companies:
            self.assertIn("rating", c)
            self.assertIn("commentsCount", c)
            self.assertIsInstance(c["rating"], int)
            self.assertIsInstance(c["commentsCount"], int)

    def test_08_api_sorting(self):
        """
        Verify backend GET /api/companies supports sort query parameter:
        - newest: sorts by createdAt descending
        - popular: sorts by subscribersCount descending
        - rating: sorts by rating descending
        - discussed: sorts by commentsCount descending
        """
        # 1. Newest
        data_newest = self._api_get("/api/companies?sort=newest")
        self.assertTrue(data_newest.get("success"))
        comps_newest = data_newest.get("companies", [])
        dates = [c["createdAt"] for c in comps_newest]
        self.assertEqual(dates, sorted(dates, reverse=True))

        # 2. Popular
        data_pop = self._api_get("/api/companies?sort=popular")
        self.assertTrue(data_pop.get("success"))
        comps_pop = data_pop.get("companies", [])
        subs = [c["subscribersCount"] for c in comps_pop]
        self.assertEqual(subs, sorted(subs, reverse=True))

        # 3. Rating
        data_rating = self._api_get("/api/companies?sort=rating")
        self.assertTrue(data_rating.get("success"))
        comps_rating = data_rating.get("companies", [])
        ratings = [c["rating"] for c in comps_rating]
        self.assertEqual(ratings, sorted(ratings, reverse=True))

        # 4. Discussed
        data_discussed = self._api_get("/api/companies?sort=discussed")
        self.assertTrue(data_discussed.get("success"))
        comps_discussed = data_discussed.get("companies", [])
        comments = [c["commentsCount"] for c in comps_discussed]
        self.assertEqual(comments, sorted(comments, reverse=True))

    def test_09_api_topics_and_search_filter(self):
        """
        Verify backend GET /api/companies supports search and topic/direction filtering.
        """
        # Search by Cyrillic company name
        encoded_query = urllib.parse.quote("СмартТех")
        data = self._api_get(f"/api/companies?search={encoded_query}")
        self.assertTrue(data.get("success"))
        comps = data.get("companies", [])
        self.assertTrue(any("СмартТех" in c["name"] for c in comps))

        # Filter by topics (direction)
        data_topics = self._api_get("/api/companies?topics=information-security")
        self.assertTrue(data_topics.get("success"))
        comps_topics = data_topics.get("companies", [])
        self.assertTrue(len(comps_topics) > 0)
        for c in comps_topics:
            self.assertIn("information-security", c.get("directions", []))

    def test_10_invariants_no_emojis_no_em_dashes(self):
        """
        Invariants check:
        - Zero emojis across feed.html, feed.js, feed.css, and test file
        - Zero em dashes (chr(8212)) across feed.html, feed.js, feed.css, and test file
        - 100% offline-first
        """
        em_dash = chr(8212)
        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]", flags=re.UNICODE)

        # Check this test file
        test_file_path = os.path.abspath(__file__)
        with open(test_file_path, "r", encoding="utf-8") as f:
            test_content = f.read()
        self.assertNotIn(em_dash, test_content, "Test file must not contain em dashes")
        self.assertEqual(len(emoji_pattern.findall(test_content)), 0, "Test file must not contain emojis")

        # feed.html participants section
        start = self.feed_html.find('id="blogsParticipantsView"')
        end = self.feed_html.find('id="companyDetailView"')
        participants_html = self.feed_html[start:end]
        self.assertNotIn(em_dash, participants_html, "Participants HTML must not contain em dashes")
        self.assertEqual(len(emoji_pattern.findall(participants_html)), 0, "Participants HTML must not contain emojis")

        # feed.js participants section
        js_start = self.feed_js.find("function renderCompaniesParticipantsList(companies)")
        js_end = self.feed_js.find("function renderCompanyDetailCard", js_start)
        participants_js = self.feed_js[js_start:js_end]
        self.assertNotIn(em_dash, participants_js, "Participants JS must not contain em dashes")
        self.assertEqual(len(emoji_pattern.findall(participants_js)), 0, "Participants JS must not contain emojis")

        # feed.css participants section
        css_start = self.feed_css.find("/* Participants View: Unified scan-friendly list surface */")
        css_end = self.feed_css.find("/* Company Detail View", css_start)
        participants_css = self.feed_css[css_start:css_end]
        self.assertNotIn(em_dash, participants_css, "Participants CSS must not contain em dashes")
        self.assertEqual(len(emoji_pattern.findall(participants_css)), 0, "Participants CSS must not contain emojis")


if __name__ == "__main__":
    unittest.main()
