"""Targeted tests for Issue #136 and Issue #137.

Issue #136: Move filter panel under toolbar into document flow and modernize sort dropdown.
Issue #137: Rebuild 2nd-level subnav and stabilize sticky subnav geometry on scroll.

Rules:
- Zero emojis
- Zero em dashes (use hyphens - instead)
- 100% offline-first
"""

import os
import re
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEED_HTML_PATH = os.path.join(BASE_DIR, "frontend", "public", "feed.html")
FEED_CSS_PATH = os.path.join(BASE_DIR, "frontend", "public", "css", "feed.css")
FEED_JS_PATH = os.path.join(BASE_DIR, "frontend", "public", "js", "feed.js")


class TestIssue136And137SubnavAndToolbar(unittest.TestCase):
    """Targeted tests for subnav restructuring, sticky geometry, in-flow drawer, and sort listbox."""

    @classmethod
    def setUpClass(cls):
        with open(FEED_HTML_PATH, "r", encoding="utf-8") as f:
            cls.feed_html = f.read()
        with open(FEED_CSS_PATH, "r", encoding="utf-8") as f:
            cls.feed_css = f.read()
        with open(FEED_JS_PATH, "r", encoding="utf-8") as f:
            cls.feed_js = f.read()

    def test_01_subnav_two_level_structure(self):
        """Subnav container has main group on left and personal group on right."""
        self.assertIn('feed-subnav-main', self.feed_html)
        self.assertIn('feed-subnav-personal', self.feed_html)

        idx_main = self.feed_html.find('feed-subnav-main')
        idx_personal = self.feed_html.find('feed-subnav-personal')
        self.assertLess(idx_main, idx_personal)

        main_chunk = self.feed_html[idx_main:idx_personal]
        self.assertIn('id="btnCreateDropdown"', main_chunk)
        self.assertIn('id="tabFeedAll"', main_chunk)
        self.assertIn('id="tabFeedQuestions"', main_chunk)
        self.assertIn('id="tabFeedSubscriptions"', main_chunk)
        self.assertIn('id="tabFeedDirections"', main_chunk)
        self.assertIn('id="tabFeedCompanies"', main_chunk)

        personal_chunk = self.feed_html[idx_personal:idx_personal + 1000]
        self.assertIn('id="feedSavedTab"', personal_chunk)
        self.assertIn('feed-saved-count', personal_chunk)

    def test_02_subnav_sticky_geometry_and_amber_badge(self):
        """Sticky subnav uses --header-height, fixed 54px height, and amber saved count badge."""
        self.assertIn('top: var(--header-height, 60px)', self.feed_css)
        self.assertIn('height: 54px', self.feed_css)

        # Amber badge color token #f59e0b
        self.assertIn('#f59e0b', self.feed_css)
        self.assertIn('.feed-saved-count', self.feed_css)

        # Legacy cyan/sky badge colors removed from feed-saved-count
        self.assertNotIn('.feed-saved-count {\n  display: inline-flex;\n  align-items: center;\n  justify-content: center;\n  min-width: 18px;\n  height: 18px;\n  padding: 0 5px;\n  border-radius: 999px;\n  font-size: 0.72rem;\n  font-weight: 700;\n  background: #38bdf8', self.feed_css)

    def test_03_filter_drawer_in_document_flow(self):
        """Filter panel is enclosed in .feed-filters-drawer-wrap directly under toolbar in feed.html."""
        self.assertIn('feed-filters-drawer-wrap', self.feed_html)
        drawer_match = re.search(r'id=["\']feedStreamToolbar["\'].*?class=["\']feed-filters-drawer-wrap["\']', self.feed_html, re.DOTALL)
        self.assertIsNotNone(drawer_match, "Drawer wrap must follow feedStreamToolbar directly")

        # CSS checks for accordion drawer
        self.assertIn('grid-template-rows: 0fr', self.feed_css)
        self.assertIn('grid-template-rows: 1fr', self.feed_css)
        self.assertIn('.feed-filters-drawer-wrap.is-open', self.feed_css)
        self.assertIn('prefers-reduced-motion', self.feed_css)

    def test_04_modernized_custom_sort_listbox(self):
        """Toolbar contains custom sort trigger and listbox menu synchronized with visually hidden select."""
        self.assertIn('id="feedSortCustomTrigger"', self.feed_html)
        self.assertIn('id="feedSortCurrentLabel"', self.feed_html)
        self.assertIn('id="feedSortCustomMenu"', self.feed_html)
        self.assertIn('role="listbox"', self.feed_html)
        self.assertIn('role="option"', self.feed_html)
        self.assertIn('feedSortSelect', self.feed_html)
        self.assertIn('visually-hidden-select', self.feed_html)

        # Check JS sync functions exist
        self.assertIn('initCustomSortDropdown', self.feed_js)
        self.assertIn('updateSortUI', self.feed_js)
        self.assertIn('SORT_LABELS', self.feed_js)

    def test_05_zero_emojis_compliance(self):
        """Ensure zero emojis in modified files."""
        emoji_pattern = re.compile(
            r'[\U00010000-\U0010ffff]|[\u2600-\u27ff]|[\u2300-\u23ff]|[\u2b50-\u2b55]|[\u203c-\u2049]'
        )
        for name, content in [("feed.html", self.feed_html), ("feed.css", self.feed_css), ("feed.js", self.feed_js)]:
            matches = emoji_pattern.findall(content)
            self.assertEqual(len(matches), 0, f"Found emojis in {name}: {matches[:5]}")

    def test_06_zero_em_dashes_compliance(self):
        """Ensure zero em dashes (\\u2014) in new and modified features."""
        for name, content in [("feed.css", self.feed_css), ("feed.js", self.feed_js)]:
            count = content.count('\u2014')
            self.assertEqual(count, 0, f"Found {count} em dashes in {name}")

        subnav_start = self.feed_html.find('feed-subnav-bar')
        subnav_end = self.feed_html.find('</nav>', subnav_start)
        subnav_chunk = self.feed_html[subnav_start:subnav_end]
        self.assertEqual(subnav_chunk.count('\u2014'), 0, "Found em dash in subnav")

        toolbar_start = self.feed_html.find('feedStreamToolbar')
        toolbar_end = self.feed_html.find('feedActiveChipsBar', toolbar_start)
        toolbar_chunk = self.feed_html[toolbar_start:toolbar_end]
        self.assertEqual(toolbar_chunk.count('\u2014'), 0, "Found em dash in toolbar and drawer")


if __name__ == "__main__":
    unittest.main()
