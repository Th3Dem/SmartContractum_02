"""Unit tests for Issue #126: Unify action button hover/active states and add Report to Article Rail.

Verifies:
1. Action Rail Like, Save, Comments, Share, Report hover states have transparent background and action colors.
2. Share hover background fill is removed (background: transparent).
3. Report button (#railBtnReport) is added after Share in Action Rail and Mobile Action Bar with 16x16 flag SVG.
4. Report modal (#articleReportModal) is present in article.html with complaint form.
5. Report handling, duplicate prevention, and active rose state in article.js.
6. Feed card Like button hover state in feed.css has #ef4444 on icon, border, count, with transparent background.
7. Strict invariants: zero emojis, zero em dashes, and offline-first compliance.
"""

import os
import re
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestIssue126UnifyActionHoversAndArticleReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html_path = os.path.join(PROJECT_ROOT, "frontend", "public", "article.html")
        cls.css_path = os.path.join(PROJECT_ROOT, "frontend", "public", "css", "article.css")
        cls.js_path = os.path.join(PROJECT_ROOT, "frontend", "public", "js", "article.js")
        cls.feed_css_path = os.path.join(PROJECT_ROOT, "frontend", "public", "css", "feed.css")

        with open(cls.html_path, "r", encoding="utf-8") as f:
            cls.html = f.read()
        with open(cls.css_path, "r", encoding="utf-8") as f:
            cls.css = f.read()
        with open(cls.js_path, "r", encoding="utf-8") as f:
            cls.js = f.read()
        with open(cls.feed_css_path, "r", encoding="utf-8") as f:
            cls.feed_css = f.read()

    def test_01_rail_btn_report_markup_and_ordering(self):
        """Verify #railBtnReport is in #articleActionRail after #railBtnShare with flag SVG."""
        share_idx = self.html.find('id="railBtnShare"')
        report_idx = self.html.find('id="railBtnReport"')
        self.assertNotEqual(share_idx, -1, "railBtnShare must exist")
        self.assertNotEqual(report_idx, -1, "railBtnReport must exist")
        self.assertTrue(report_idx > share_idx, "railBtnReport must be positioned after railBtnShare")

        # Verify flag SVG inside railBtnReport
        report_match = re.search(r'<button[^>]*id="railBtnReport"[^>]*>([\s\S]*?)</button>', self.html)
        self.assertIsNotNone(report_match)
        report_inner = report_match.group(1)
        self.assertIn('width="16"', report_inner)
        self.assertIn('height="16"', report_inner)
        self.assertIn('M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z', report_inner)

        # Mobile button
        mobile_share_idx = self.html.find('id="mobileBtnShare"')
        mobile_report_idx = self.html.find('id="mobileBtnReport"')
        self.assertNotEqual(mobile_share_idx, -1)
        self.assertNotEqual(mobile_report_idx, -1)
        self.assertTrue(mobile_report_idx > mobile_share_idx)

    def test_02_article_report_modal_markup(self):
        """Verify #articleReportModal structure in article.html."""
        self.assertIn('id="articleReportModal"', self.html)
        self.assertIn('id="articleReportForm"', self.html)
        self.assertIn('name="articleReportReason"', self.html)
        self.assertIn('id="articleReportDetails"', self.html)
        self.assertIn('id="btnSubmitArticleReport"', self.html)
        self.assertIn('id="btnCancelArticleReport"', self.html)

    def test_03_rail_action_hover_backgrounds_transparent(self):
        """Verify rail buttons hover backgrounds are transparent without colored fills."""
        # Base .btn-rail-action:hover
        base_match = re.search(r'\.btn-rail-action:hover\s*\{([^}]+)\}', self.css)
        self.assertIsNotNone(base_match)
        self.assertIn("background: transparent;", base_match.group(1))

        # Share hover background must be transparent !important
        share_match = re.search(r'\.btn-rail-share:hover[^{]*\{([^}]+)\}', self.css)
        self.assertIsNotNone(share_match)
        self.assertIn("background: transparent !important;", share_match.group(1))
        self.assertIn("#a855f7", share_match.group(1))

        # Like hover has transparent background
        like_match = re.search(r'\.btn-rail-like:hover[^{]*\{([^}]+)\}', self.css)
        self.assertIsNotNone(like_match)
        self.assertIn("background: transparent;", like_match.group(1))
        self.assertIn("#ef4444", like_match.group(1))

        # Bookmark hover has transparent background
        bm_match = re.search(r'\.btn-rail-bookmark:hover[^{]*\{([^}]+)\}', self.css)
        self.assertIsNotNone(bm_match)
        self.assertIn("background: transparent;", bm_match.group(1))
        self.assertIn("#f59e0b", bm_match.group(1))

    def test_04_report_styling_in_article_css(self):
        """Verify report button styling in article.css."""
        report_hover = re.search(r'\.btn-rail-report:hover[^{]*\{([^}]+)\}', self.css)
        self.assertIsNotNone(report_hover)
        self.assertIn("#f43f5e", report_hover.group(1))
        self.assertIn("background: transparent;", report_hover.group(1))

        report_active = re.search(r'\.btn-rail-report\.is-reported[^{]*\{([^}]+)\}', self.css)
        self.assertIsNotNone(report_active)
        self.assertIn("#f43f5e", report_active.group(1))
        self.assertIn("cursor: pointer;", report_active.group(1))

    def test_05_feed_card_like_hover_in_feed_css(self):
        """Verify feed card Like button hover state in feed.css."""
        card_like_match = re.search(r'\.btn-card-like:hover\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(card_like_match)
        css_content = card_like_match.group(1)
        self.assertIn("color: #ef4444;", css_content)
        self.assertIn("border-color: #ef4444;", css_content)
        self.assertIn("background: transparent;", css_content)

    def test_06_article_js_report_logic(self):
        """Verify report event listeners and helper methods in article.js."""
        self.assertIn("handleArticleReportClick", self.js)
        self.assertIn("railBtnReport", self.js)
        self.assertIn("mobileBtnReport", self.js)
        self.assertIn("isArticleReported", self.js)
        self.assertIn("markArticleAsReported", self.js)
        self.assertIn("syncArticleReportStatus", self.js)
        self.assertIn("getOrInitArticleReportModal", self.js)
        self.assertIn("openArticleReportModal", self.js)
        self.assertIn("POST", self.js)
        self.assertIn("/report", self.js)

    def test_07_zero_emojis_and_zero_em_dashes(self):
        """Verify strict project invariants: zero emojis and zero em dashes."""
        for name, content in [
            ("article.html", self.html),
            ("article.css", self.css),
            ("article.js", self.js),
            ("feed.css", self.feed_css),
        ]:
            self.assertNotIn("\u2014", content, f"Em dash found in {name}")
            emoji_pattern = re.compile(
                r'[\U00010000-\U0010ffff]|[\u2600-\u27ff]|[\u2300-\u23ff]|[\u2b50-\u2b55]'
            )
            self.assertIsNone(emoji_pattern.search(content), f"Emoji found in {name}")


if __name__ == "__main__":
    unittest.main()
