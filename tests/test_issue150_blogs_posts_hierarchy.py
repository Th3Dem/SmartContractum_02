import json
import os
import re
import shutil
import tempfile
import threading
import time
import unittest
import urllib.request
from typing import Any, Dict

import server
from server import create_server, init_db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue150BlogsPostsHierarchy(unittest.TestCase):
    """
    Targeted tests for Issue #150:
    - Visual hierarchy on Blogs > Posts subtab: Header -> Tabs -> Toolbar -> Cards
    - Toolbar placement and ensureToolbarPlacement() logic
    - Compact vertical spacing in header, subtabs, and toolbar
    - Corporate Feed Card primary identity (Company logo + name clickable to blog)
    - Human author as secondary attribution (clickable to profile)
    - Subtle 'Блог компании' marker (not a heavy badge)
    - Independent navigation for Subscribe button and Author profile
    - Standard feed card geometry and invariants preservation
    """

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue150.db")
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

        card_js_path = os.path.join(FRONTEND_DIR, "js", "card.js")
        with open(card_js_path, "r", encoding="utf-8") as f:
            cls.card_js = f.read()

        feed_css_path = os.path.join(FRONTEND_DIR, "css", "feed.css")
        with open(feed_css_path, "r", encoding="utf-8") as f:
            cls.feed_css = f.read()

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "httpd"):
            cls.httpd.shutdown()
        if hasattr(cls, "temp_dir") and os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_blogs_posts_hierarchy_order(self):
        """
        Hierarchy check in DOM and CSS:
        Header ('Блоги компаний') -> Tabs ([Посты] / [Участники]) -> Toolbar Slot -> Cards Container.
        Top vertical spacing is compact.
        """
        comp_view_idx = self.feed_html.find('id="companiesView"')
        self.assertNotEqual(comp_view_idx, -1, "#companiesView must exist in feed.html")

        header_idx = self.feed_html.find('class="entity-view-header blogs-view-header"', comp_view_idx)
        self.assertNotEqual(header_idx, -1, ".blogs-view-header must exist in #companiesView")

        tabs_idx = self.feed_html.find('class="companies-subtabs-bar blogs-subtabs-bar"', header_idx)
        self.assertNotEqual(tabs_idx, -1, ".blogs-subtabs-bar must be placed after header")

        posts_view_idx = self.feed_html.find('id="blogsPostsView"', tabs_idx)
        self.assertNotEqual(posts_view_idx, -1, "#blogsPostsView must be placed after tabs bar")

        toolbar_slot_idx = self.feed_html.find('id="blogsPostsToolbarSlot"', posts_view_idx)
        self.assertNotEqual(toolbar_slot_idx, -1, "#blogsPostsToolbarSlot must exist inside #blogsPostsView")

        grid_idx = self.feed_html.find('id="companiesArticlesGrid"', toolbar_slot_idx)
        self.assertNotEqual(grid_idx, -1, "#companiesArticlesGrid must be placed after #blogsPostsToolbarSlot")

        # Strict ordering verification
        self.assertTrue(comp_view_idx < header_idx < tabs_idx < posts_view_idx < toolbar_slot_idx < grid_idx)

        # CSS compact spacing rules
        self.assertIn(".companies-feed-view", self.feed_css)
        self.assertIn("gap: 0", self.feed_css)
        self.assertIn("min-height: auto", self.feed_css)
        self.assertTrue("padding: 0 0 8px 0" in self.feed_css or "padding: 4px 0 8px 0" in self.feed_css)
        self.assertIn("padding-bottom: 6px", self.feed_css)
        self.assertIn(".blogs-posts-view .feed-stream-toolbar", self.feed_css)

    def test_02_toolbar_only_in_posts(self):
        """
        Verify feed.js implements ensureToolbarPlacement():
        - Moves stream toolbar and drawer into blogsPostsToolbarSlot when viewing posts
        - Sets search placeholder to 'Поиск публикаций компаний...'
        - Moves toolbar back to feedMainColumn before feedArticlesView on other tabs
        - Hides toolbar on participants subtab
        - Invokes ensureToolbarPlacement on tab and subtab transitions
        """
        self.assertIn("function ensureToolbarPlacement()", self.feed_js)
        self.assertIn("blogsPostsToolbarSlot", self.feed_js)
        self.assertIn("Поиск публикаций компаний...", self.feed_js)
        self.assertIn("feedMainColumn", self.feed_js)
        self.assertIn("feedArticlesView", self.feed_js)

        # Toolbar is hidden on participants subtab
        self.assertIn("state.companiesSubtab === 'participants'", self.feed_js)

        # Trigger points
        self.assertIn("ensureToolbarPlacement();", self.feed_js)
        # Check that switchTab calls ensureToolbarPlacement
        switch_tab_idx = self.feed_js.find("function switchTab(tabName)")
        self.assertNotEqual(switch_tab_idx, -1)
        next_fn_idx = self.feed_js.find("function updateFeedTitleUI()", switch_tab_idx)
        switch_tab_body = self.feed_js[switch_tab_idx:next_fn_idx]
        self.assertIn("ensureToolbarPlacement()", switch_tab_body)

        # Check that loadCompanies calls ensureToolbarPlacement
        load_comp_idx = self.feed_js.find("function loadCompanies(subtab)")
        self.assertNotEqual(load_comp_idx, -1)
        next_comp_fn_idx = self.feed_js.find("function renderCompaniesParticipantsList", load_comp_idx)
        load_comp_body = self.feed_js[load_comp_idx:next_comp_fn_idx]
        self.assertIn("ensureToolbarPlacement()", load_comp_body)

    def test_03_corporate_card_company_primary_identity(self):
        """
        Verify card.js and feed.css render company as the primary identity:
        - Logo and company name with data-company-id
        - Verified checkmark icon
        - Company name is prominent (font-weight: 700) and clickable
        """
        # Card JS structure
        self.assertIn("card-corporate-header", self.card_js)
        self.assertIn("company-card-info", self.card_js)
        self.assertIn("company-card-details", self.card_js)
        self.assertIn("company-card-title-group", self.card_js)
        self.assertIn("company-card-name", self.card_js)
        self.assertIn("verifiedIcon", self.card_js)

        # Feed CSS styling
        self.assertIn(".company-card-name {", self.feed_css)
        self.assertIn("font-weight: 700;", self.feed_css)
        self.assertIn("cursor: pointer;", self.feed_css)

    def test_04_human_author_preserved_secondary_attribution(self):
        """
        Verify human author is preserved as secondary attribution:
        - Label 'Автор:'
        - Clickable author button with class btn-author-profile
        - Submeta container for author and blog marker
        """
        self.assertIn("company-card-submeta", self.card_js)
        self.assertIn("card-secondary-author", self.card_js)
        self.assertIn("card-secondary-author-label", self.card_js)
        self.assertIn("btn-author-profile", self.card_js)
        self.assertIn("data-author-id", self.card_js)

        # Feed CSS styling
        self.assertIn(".card-secondary-author {", self.feed_css)
        self.assertIn(".card-secondary-author .author-name", self.feed_css)

    def test_05_compact_marker_not_heavy_badge(self):
        """
        Verify 'Блог компании' marker is subtle text, not a heavy badge:
        - Has class card-corporate-marker
        - Background is none, padding is 0, border is none
        """
        self.assertIn("card-corporate-marker", self.card_js)
        self.assertIn(".card-corporate-marker {", self.feed_css)

        # Check CSS rules for marker
        marker_start = self.feed_css.find(".card-corporate-marker {")
        self.assertNotEqual(marker_start, -1)
        marker_end = self.feed_css.find("}", marker_start)
        marker_css = self.feed_css[marker_start:marker_end]
        self.assertIn("background: none;", marker_css)
        self.assertIn("padding: 0;", marker_css)
        self.assertIn("border: none;", marker_css)

    def test_06_subscribe_button_independent_navigation(self):
        """
        Verify Subscribe button and author button have independent click handling:
        - Clicking subscribe button or author profile does not open company blog
        - CompInfo click and keydown handlers guard against nested action triggers
        - Subscribe button has compact ~28px height
        """
        guard_clause = "if (e.target.closest('.btn-author-profile') || e.target.closest('.btn-card-company-sub')) return;"
        self.assertIn(guard_clause, self.card_js)

        # Subscribe button element and handler
        self.assertIn("btn-card-company-sub", self.card_js)
        self.assertIn("options.onCompanySubscribeToggle", self.card_js)

        # CSS height
        sub_start = self.feed_css.find(".btn-card-company-sub {")
        self.assertNotEqual(sub_start, -1)
        sub_end = self.feed_css.find("}", sub_start)
        sub_css = self.feed_css[sub_start:sub_end]
        self.assertIn("height: 28px;", sub_css)

    def test_07_standard_feed_card_unbroken(self):
        """
        Verify standard feed card structure remains completely intact:
        - Regular author info with avatar
        - Cover container and image
        - Footer actions (like, comments, saves, share, report)
        """
        self.assertIn("author-avatar", self.card_js)
        self.assertIn("card-cover-container", self.card_js)
        self.assertIn("card-cover-img", self.card_js)
        self.assertIn("btn-card-like", self.card_js)
        self.assertIn("btn-card-comments", self.card_js)
        self.assertIn("btn-card-bookmark", self.card_js)
        self.assertIn("btn-card-share", self.card_js)
        self.assertIn("btn-card-report", self.card_js)

    def test_08_invariants_no_emojis_no_em_dashes(self):
        """
        Invariants:
        - 100% offline-first
        - Zero emojis
        - Zero em dashes (use hyphens instead)
        - No local machine paths or real IPs in frontend code
        """
        em_dash = chr(8212)
        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]", flags=re.UNICODE)

        # 1. Check card.js
        self.assertNotIn(em_dash, self.card_js, "card.js must not contain em dashes")
        self.assertEqual(len(emoji_pattern.findall(self.card_js)), 0, "card.js must not contain emojis")

        # 2. Check feed.css
        self.assertNotIn(em_dash, self.feed_css, "feed.css must not contain em dashes")
        self.assertEqual(len(emoji_pattern.findall(self.feed_css)), 0, "feed.css must not contain emojis")

        # 3. Check corporate blogs section in feed.html
        start = self.feed_html.find('id="companiesView"')
        end = self.feed_html.find('id="directionsFeedView"')
        blogs_html = self.feed_html[start:end]
        self.assertNotIn(em_dash, blogs_html, "Corporate blogs HTML must not contain em dashes")
        self.assertEqual(len(emoji_pattern.findall(blogs_html)), 0, "Corporate blogs HTML must not contain emojis")

        # 4. Check ensureToolbarPlacement and blogs logic in feed.js
        ensure_fn_start = self.feed_js.find("function ensureToolbarPlacement()")
        self.assertNotEqual(ensure_fn_start, -1)
        ensure_fn_slice = self.feed_js[ensure_fn_start:ensure_fn_start + 2500]
        self.assertNotIn(em_dash, ensure_fn_slice, "feed.js toolbar logic must not contain em dashes")
        self.assertEqual(len(emoji_pattern.findall(ensure_fn_slice)), 0, "feed.js toolbar logic must not contain emojis")

        # 5. Check no local user paths
        self.assertNotIn("/home/", blogs_html)
        self.assertNotIn("/home/", self.feed_css)


if __name__ == "__main__":
    unittest.main()
