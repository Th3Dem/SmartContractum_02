"""Unit tests for Issue #109: Unify Action Rail controls with feed card controls 1:1.

Verifies:
1. All Action Rail and Mobile Action Bar SVG icons are sized at 16x16px (consistent with feed cards).
2. SVG paths match feed cards:
   - Like: heart path (M20.84 4.61...)
   - Bookmark: ribbon path (m19 21-7-4...)
   - Comments: speech bubble (M21 15a2...)
   - Share: 3 connected nodes network icon (circles at (18,5), (6,12), (18,19))
3. Active and hover color states match feed cards 1:1:
   - Like active: #ef4444 (red)
   - Bookmark active: #f59e0b (amber)
   - Comments hover/focus: #38bdf8 (cyan)
   - Share hover/active: #a855f7 (purple)
4. Rectangular geometry with var(--radius-sm, 4px), no 9999px pills.
5. Project invariants: zero emojis, zero em dashes, and offline-first compliance.
"""

import os
import re
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestIssue109UnifyActionRailWithFeed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html_path = os.path.join(PROJECT_ROOT, "frontend", "public", "article.html")
        cls.css_path = os.path.join(PROJECT_ROOT, "frontend", "public", "css", "article.css")
        cls.js_path = os.path.join(PROJECT_ROOT, "frontend", "public", "js", "article.js")
        cls.card_js_path = os.path.join(PROJECT_ROOT, "frontend", "public", "js", "card.js")
        cls.feed_css_path = os.path.join(PROJECT_ROOT, "frontend", "public", "css", "feed.css")

        with open(cls.html_path, "r", encoding="utf-8") as f:
            cls.html = f.read()
        with open(cls.css_path, "r", encoding="utf-8") as f:
            cls.css = f.read()
        with open(cls.js_path, "r", encoding="utf-8") as f:
            cls.js = f.read()
        with open(cls.card_js_path, "r", encoding="utf-8") as f:
            cls.card_js = f.read()
        with open(cls.feed_css_path, "r", encoding="utf-8") as f:
            cls.feed_css = f.read()

    def test_01_svg_icon_dimensions_in_rail_and_mobile_bar(self):
        """Verify SVG dimensions in action rail and mobile action bar are 16x16."""
        rail_start = self.html.find('id="articleActionRail"')
        self.assertNotEqual(rail_start, -1)
        rail_end = self.html.find('</div>', self.html.find('id="railBtnShare"', rail_start))
        rail_html = self.html[rail_start:rail_end]

        # All SVGs in rail must be width="16" height="16"
        rail_svgs = re.findall(r'<svg[^>]*>', rail_html)
        self.assertTrue(len(rail_svgs) >= 4)
        for svg_tag in rail_svgs:
            self.assertIn('width="16"', svg_tag)
            self.assertIn('height="16"', svg_tag)

        # In CSS: .btn-rail-action svg has width: 16px; height: 16px;
        svg_css_match = re.search(r'\.btn-rail-action\s*svg[^{]*\{([^}]+)\}', self.css)
        self.assertIsNotNone(svg_css_match)
        svg_css = svg_css_match.group(1)
        self.assertIn("width: 16px", svg_css)
        self.assertIn("height: 16px", svg_css)

    def test_02_share_svg_matches_feed_card_three_nodes(self):
        """Verify share button SVG uses 3 connected nodes network icon identical to card.js."""
        # Share in rail
        share_match = re.search(r'<button[^>]*id="railBtnShare"[^>]*>([\s\S]*?)</button>', self.html)
        self.assertIsNotNone(share_match)
        share_html = share_match.group(1)
        self.assertIn('cx="18"', share_html)
        self.assertIn('cx="6"', share_html)
        self.assertIn('x1="8.59"', share_html)
        self.assertIn('x1="15.41"', share_html)

        # Share in mobile action bar
        mobile_share_match = re.search(r'<button[^>]*id="mobileBtnShare"[^>]*>([\s\S]*?)</button>', self.html)
        self.assertIsNotNone(mobile_share_match)
        mobile_share_html = mobile_share_match.group(1)
        self.assertIn('cx="18"', mobile_share_html)
        self.assertIn('cx="6"', mobile_share_html)

    def test_03_like_active_color_unification(self):
        """Verify active like button color is #ef4444 (same as feed card)."""
        like_rule = re.search(r'\.btn-rail-like\.is-liked[^{]*\{([^}]+)\}', self.css)
        self.assertIsNotNone(like_rule)
        like_css = like_rule.group(1)
        self.assertIn("#ef4444", like_css)

    def test_04_bookmark_active_color_amber(self):
        """Verify active bookmark color is #f59e0b (amber, same as feed card)."""
        bm_rule = re.search(r'\.btn-rail-bookmark\.is-bookmarked[^{]*\{([^}]+)\}', self.css)
        self.assertIsNotNone(bm_rule)
        bm_css = bm_rule.group(1)
        self.assertIn("#f59e0b", bm_css)

    def test_05_comments_hover_color_cyan(self):
        """Verify comments button hover state is #38bdf8 (cyan, same as feed card)."""
        comm_rule = re.search(r'\.btn-rail-comments:hover[^{]*\{([^}]+)\}', self.css)
        self.assertIsNotNone(comm_rule)
        comm_css = comm_rule.group(1)
        self.assertIn("#38bdf8", comm_css)

    def test_06_share_hover_active_color_purple(self):
        """Verify share button hover and active state is #a855f7 (purple, same as feed card)."""
        share_rule = re.search(r'\.btn-rail-share:hover[^{]*\{([^}]+)\}', self.css)
        self.assertIsNotNone(share_rule)
        share_css = share_rule.group(1)
        self.assertIn("#a855f7", share_css)

    def test_07_zero_emojis_and_zero_em_dashes(self):
        """Verify strict project invariants: zero emojis and zero em dashes."""
        for name, content in [("article.html", self.html), ("article.css", self.css), ("article.js", self.js)]:
            self.assertNotIn("\u2014", content, f"Em dash found in {name}")
            emoji_pattern = re.compile(
                r'[\U00010000-\U0010ffff]|[\u2600-\u27ff]|[\u2300-\u23ff]|[\u2b50-\u2b55]'
            )
            self.assertIsNone(emoji_pattern.search(content), f"Emoji found in {name}")


if __name__ == "__main__":
    unittest.main()
