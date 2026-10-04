"""Targeted test suite for Issue #158.

Issue #158: [P1][frontend][BUG] Filters: восстановить работу dropdown controls во всех Filter Drawer.

Invariants:
- Zero emojis
- Zero em dashes (use hyphens instead)
- 100% offline-first compliance
- No hardcoded local machine paths or IP addresses
"""

import os
import re
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue158FilterDrawerDropdowns(unittest.TestCase):
    """Targeted tests for filter drawer dropdown positioning and containing block fixes."""

    @classmethod
    def setUpClass(cls):
        html_path = os.path.join(FRONTEND_DIR, "feed.html")
        with open(html_path, "r", encoding="utf-8") as f:
            cls.feed_html = f.read()

        css_path = os.path.join(FRONTEND_DIR, "css", "feed.css")
        with open(css_path, "r", encoding="utf-8") as f:
            cls.feed_css = f.read()

        js_path = os.path.join(FRONTEND_DIR, "js", "feed.js")
        with open(js_path, "r", encoding="utf-8") as f:
            cls.feed_js = f.read()

    def test_01_css_drawer_wrap_open_overflow_visible(self):
        """Verify .feed-filters-drawer-wrap.is-open has overflow: visible."""
        match = re.search(
            r"\.feed-filters-drawer-wrap\.is-open\s*\{([^}]+)\}",
            self.feed_css,
        )
        self.assertIsNotNone(match, ".feed-filters-drawer-wrap.is-open rule must exist in feed.css")
        block = match.group(1)
        self.assertIn("overflow: visible;", block)
        self.assertIn("grid-template-rows: 1fr;", block)

    def test_02_css_drawer_panel_transform_none_and_overflow_visible(self):
        """Verify .feed-filters-drawer-wrap.is-open > #feedFiltersPanel has transform: none and overflow: visible."""
        match = re.search(
            r"\.feed-filters-drawer-wrap\.is-open\s*>\s*#feedFiltersPanel\s*\{([^}]+)\}",
            self.feed_css,
        )
        self.assertIsNotNone(match, ".feed-filters-drawer-wrap.is-open > #feedFiltersPanel rule must exist in feed.css")
        block = match.group(1)
        self.assertIn("opacity: 1;", block)
        self.assertIn("transform: none;", block)
        self.assertIn("overflow: visible;", block)

    def test_03_css_filter_panel_body_overflow_visible(self):
        """Verify feed-slide-panel-body within #feedFiltersPanel has overflow: visible."""
        match = re.search(
            r"(?:#feedFiltersPanel|\.feed-filters-drawer-wrap\.is-open).*?\.feed-slide-panel-body\s*\{([^}]+)\}",
            self.feed_css,
        )
        self.assertIsNotNone(match, "Rule for #feedFiltersPanel .feed-slide-panel-body must exist in feed.css")
        block = match.group(1)
        self.assertIn("overflow: visible;", block)

    def test_04_css_dropdown_menus_fixed_position_and_z_index(self):
        """Verify dropdown menus have position: fixed and z-index: 1050."""
        match = re.search(
            r"\.feed-multiselect-dropdown-menu,\s*\.feed-topics-dropdown-menu,\s*\.feed-date-dropdown-menu\s*\{([^}]+)\}",
            self.feed_css,
        )
        self.assertIsNotNone(match, "Shared dropdown menu rules must exist in feed.css")
        block = match.group(1)
        self.assertIn("position: fixed;", block)
        self.assertIn("z-index: 1050;", block)

    def test_05_js_position_dropdown_uses_viewport_and_no_restrictive_footer(self):
        """Verify positionDropdownMenu computes spaceBelow with window.innerHeight and avoids restrictive footerTop."""
        func_start = self.feed_js.find("function positionDropdownMenu(menu, trigger)")
        self.assertNotEqual(func_start, -1, "positionDropdownMenu must be defined in feed.js")
        func_end = self.feed_js.find("function openDropdownMenu", func_start)
        func_body = self.feed_js[func_start:func_end]

        # Must compute spaceBelow with window.innerHeight
        self.assertIn("const spaceBelow = Math.max(0, window.innerHeight - rect.bottom - 8);", func_body)
        self.assertIn("const spaceAbove = Math.max(0, rect.top - headerBottom - 8);", func_body)

        # Must NOT use footerTop for spaceBelow calculation
        self.assertNotIn("footerTop", func_body)
        self.assertNotIn("panelFooter", func_body)

    def test_06_js_position_dropdown_no_premature_body_rect_closure(self):
        """Verify positionDropdownMenu removes premature closure against bodyRect.bottom."""
        func_start = self.feed_js.find("function positionDropdownMenu(menu, trigger)")
        self.assertNotEqual(func_start, -1)
        func_end = self.feed_js.find("function openDropdownMenu", func_start)
        func_body = self.feed_js[func_start:func_end]

        # Must NOT check rect.bottom < bodyRect.top || rect.top > bodyRect.bottom
        self.assertNotIn("bodyRect", func_body)
        self.assertNotIn("panelBody.getBoundingClientRect", func_body)

        # Must check viewport bounds against headerBottom and window.innerHeight
        self.assertIn("if (rect.bottom < headerBottom || rect.top > window.innerHeight)", func_body)

    def test_07_js_close_panel_and_switch_tab_call_close_all_dropdowns(self):
        """Verify closeFeedFiltersPanel and switchTab invoke closeAllFilterDropdowns."""
        # 1. closeFeedFiltersPanel
        close_start = self.feed_js.find("function closeFeedFiltersPanel()")
        self.assertNotEqual(close_start, -1, "closeFeedFiltersPanel must exist in feed.js")
        close_end = self.feed_js.find("function toggleFeedFiltersPanel()", close_start)
        close_body = self.feed_js[close_start:close_end]
        self.assertIn("closeAllFilterDropdowns();", close_body)

        # 2. switchTab
        switch_start = self.feed_js.find("function switchTab(tabName)")
        self.assertNotEqual(switch_start, -1, "switchTab must exist in feed.js")
        switch_end = self.feed_js.find("function renderQuestionsPills()", switch_start)
        switch_body = self.feed_js[switch_start:switch_end]
        self.assertIn("closeAllFilterDropdowns();", switch_body)

    def test_08_html_and_js_all_four_filter_dropdowns_exist_and_init(self):
        """Verify all 4 dropdown triggers and menus exist in feed.html and are initialized in feed.js."""
        dropdowns = [
            ("Topics", "feedTopicsDropdownTrigger", "feedTopicsDropdownMenu"),
            ("Date", "feedDateDropdownTrigger", "feedDateDropdownMenu"),
            ("Formats", "feedFormatsDropdownTrigger", "feedFormatsDropdownMenu"),
            ("Audiences", "feedAudiencesDropdownTrigger", "feedAudiencesDropdownMenu"),
        ]

        for name, trigger_id, menu_id in dropdowns:
            # HTML element existence
            self.assertIn(f'id="{trigger_id}"', self.feed_html, f"{name} trigger must exist in feed.html")
            self.assertIn(f'id="{menu_id}"', self.feed_html, f"{name} menu must exist in feed.html")

            # JS wiring existence
            self.assertIn(trigger_id, self.feed_js, f"{name} trigger must be referenced in feed.js")
            self.assertIn(menu_id, self.feed_js, f"{name} menu must be referenced in feed.js")

    def test_09_invariants_offline_zero_emojis_zero_em_dashes(self):
        """Verify strict invariants: zero emojis, zero em dashes in modified features, and offline-first compliance."""
        em_dash = chr(8212)
        emoji_pattern = re.compile(
            r"[\U00010000-\U0010ffff]|[\u2600-\u27ff]|[\u2300-\u23ff]|[\u2b50-\u2b55]|[\u203c-\u2049]"
        )

        # Entire feed.css must have zero em dashes and zero emojis
        self.assertNotIn(em_dash, self.feed_css, "feed.css must not contain em dashes")
        self.assertEqual(len(emoji_pattern.findall(self.feed_css)), 0, "feed.css must not contain emojis")

        # Entire feed.js must have zero emojis
        self.assertEqual(len(emoji_pattern.findall(self.feed_js)), 0, "feed.js must not contain emojis")

        # Modified functions in feed.js must not contain em dashes
        func_pos_start = self.feed_js.find("function positionDropdownMenu(menu, trigger)")
        func_pos_end = self.feed_js.find("function openDropdownMenu", func_pos_start)
        self.assertNotIn(em_dash, self.feed_js[func_pos_start:func_pos_end], "positionDropdownMenu must not contain em dashes")

        func_close_start = self.feed_js.find("function closeFeedFiltersPanel()")
        func_close_end = self.feed_js.find("function toggleFeedFiltersPanel()", func_close_start)
        self.assertNotIn(em_dash, self.feed_js[func_close_start:func_close_end], "closeFeedFiltersPanel must not contain em dashes")

        func_tab_start = self.feed_js.find("function switchTab(tabName)")
        func_tab_end = self.feed_js.find("function updateFeedTitleUI()", func_tab_start)
        self.assertNotIn(em_dash, self.feed_js[func_tab_start:func_tab_end], "switchTab must not contain em dashes")

        dropdown_start = self.feed_js.find("let activeDropdownMenu = null;")
        dropdown_end = self.feed_js.find("function initAuthControls()", dropdown_start)
        self.assertNotIn(em_dash, self.feed_js[dropdown_start:dropdown_end], "filter dropdown logic must not contain em dashes")

        # Check for remote CDN leaks or non-offline URL dependencies in feed.css and feed.js
        external_url_pattern = re.compile(r"https?://(?!localhost|127\.0\.0\.1|www\.w3\.org|smartcontractum\.ru)[^\s\'\"<>]+")
        self.assertEqual(external_url_pattern.findall(self.feed_css), [], "feed.css contains external CDN URLs")
        self.assertEqual(external_url_pattern.findall(self.feed_js), [], "feed.js contains external CDN URLs")


if __name__ == "__main__":
    unittest.main()
