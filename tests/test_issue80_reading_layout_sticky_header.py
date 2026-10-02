#!/usr/bin/env python3
"""
tests/test_issue80_reading_layout_sticky_header.py

Automated test suite for Issue #80:
1. Fix sticky header root cause:
   - Ensure html, body, and .app-body do NOT specify overflow-x: hidden in article.css.
   - Verify .app-header in theme.css has position: sticky, top: 0, z-index: 1000.
2. Modern Reading Shell layout in article.html and article.css:
   - .article-reading-shell (max-width: 1160px, display: flex, justify-content: center, gap: 24px)
   - .article-rail-slot (width: 56px, flex-shrink: 0, prepared for Issue #84)
   - .article-main-slot (max-width: 740px, width: 100%, flex: 1 1 auto, min-width: 0)
   - .article-toc-slot (width: 260px, flex-shrink: 0, prepared for Issue #87)
3. Responsive behavior:
   - Desktop (>= 1200px): full 3-slot shell active.
   - Tablet (768px - 1199px): side slots hidden (display: none), main slot centered.
   - Mobile (< 768px): single reading column (display: block, width: 100%, padding 12px), zero horizontal overflow.
4. Invariants:
   - Zero emojis.
   - Zero em dashes.
   - 100% offline-first.
"""

import os
import re
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def read_file(relative_path: str) -> str:
    full_path = os.path.join(PROJECT_ROOT, relative_path)
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()


def extract_media_query_block(css_content: str, pattern: str) -> str:
    m = re.search(pattern, css_content)
    if not m:
        return ""
    brace_start = css_content.find("{", m.end() - 1)
    if brace_start == -1:
        return ""
    depth = 1
    i = brace_start + 1
    while i < len(css_content) and depth > 0:
        if css_content[i] == "{":
            depth += 1
        elif css_content[i] == "}":
            depth -= 1
        i += 1
    return css_content[brace_start + 1 : i - 1]


class TestIssue80ReadingLayoutStickyHeader(unittest.TestCase):
    """Test suite for reading layout shell and sticky header invariants."""

    @classmethod
    def setUpClass(cls):
        cls.article_html = read_file("frontend/public/article.html")
        cls.article_css = read_file("frontend/public/css/article.css")
        cls.theme_css = read_file("frontend/public/css/theme.css")

    def test_01_no_overflow_x_hidden_on_html_and_body_in_article_css(self):
        """Verify html, body, and .app-body do NOT have overflow-x: hidden in article.css."""
        html_body_matches = re.findall(r'(?:html|body|\.app-body)[^{]*\{([^}]+)\}', self.article_css)
        self.assertTrue(len(html_body_matches) > 0, "Expected at least one html/body rule in article.css")
        for block in html_body_matches:
            self.assertNotIn("overflow-x: hidden", block, "overflow-x: hidden must NOT be set on html/body/.app-body")

    def test_02_app_header_sticky_properties_in_theme_css(self):
        """Verify .app-header in theme.css has position: sticky, top: 0, and z-index: 1000."""
        header_match = re.search(r'\.app-header\s*\{([^}]+)\}', self.theme_css)
        self.assertIsNotNone(header_match, ".app-header rule must exist in theme.css")
        block = header_match.group(1)
        self.assertIn("position: sticky", block)
        self.assertIn("top: 0", block)
        self.assertIn("z-index: 1000", block)
        self.assertIn('class="app-header"', self.article_html)
        self.assertIn('id="appHeader"', self.article_html)

    def test_03_reading_shell_and_slots_present_in_article_html(self):
        """Verify .article-reading-shell, .article-rail-slot, .article-main-slot, and .article-toc-slot exist in article.html."""
        self.assertIn("article-reading-shell", self.article_html)
        self.assertIn("article-rail-slot", self.article_html)
        self.assertIn("article-main-slot", self.article_html)
        self.assertIn("article-toc-slot", self.article_html)

        rail_idx = self.article_html.find("article-rail-slot")
        main_idx = self.article_html.find("article-main-slot")
        toc_idx = self.article_html.find("article-toc-slot")
        self.assertTrue(rail_idx < main_idx < toc_idx, "Slots must be in order: rail slot -> main slot -> toc slot")

        main_slice = self.article_html[main_idx:toc_idx]
        self.assertIn("btnBackToFeed", main_slice)
        self.assertIn("articleContentWrap", main_slice)
        self.assertIn("comments", main_slice)

    def test_04_reading_shell_dimensions_and_flex_layout_in_article_css(self):
        """Verify .article-reading-shell max-width (1160px), padding, display flex, and gap in article.css."""
        shell_match = re.search(r'\.article-reading-shell\s*\{([^}]+)\}', self.article_css)
        self.assertIsNotNone(shell_match, ".article-reading-shell rule must exist in article.css")
        block = shell_match.group(1)
        self.assertIn("max-width: 1160px", block)
        self.assertIn("display: flex", block)
        self.assertIn("justify-content: center", block)
        self.assertIn("align-items: flex-start", block)
        self.assertIn("gap: var(--space-6, 24px)", block)
        self.assertIn("padding: 0 var(--space-4, 16px)", block)

    def test_05_slots_dimensions_in_article_css(self):
        """Verify slot widths in article.css: rail (56px), main (740px), toc (260px)."""
        rail_match = re.search(r'\.article-rail-slot\s*\{([^}]+)\}', self.article_css)
        self.assertIsNotNone(rail_match, ".article-rail-slot rule must exist in article.css")
        self.assertIn("width: 56px", rail_match.group(1))
        self.assertIn("flex-shrink: 0", rail_match.group(1))

        main_match = re.search(r'\.article-main-slot\s*\{([^}]+)\}', self.article_css)
        self.assertIsNotNone(main_match, ".article-main-slot rule must exist in article.css")
        main_block = main_match.group(1)
        self.assertIn("max-width: 740px", main_block)
        self.assertIn("width: 100%", main_block)
        self.assertIn("flex: 1 1 auto", main_block)
        self.assertIn("min-width: 0", main_block)

        toc_match = re.search(r'\.article-toc-slot\s*\{([^}]+)\}', self.article_css)
        self.assertIsNotNone(toc_match, ".article-toc-slot rule must exist in article.css")
        self.assertIn("width: 260px", toc_match.group(1))
        self.assertIn("flex-shrink: 0", toc_match.group(1))

    def test_06_desktop_breakpoint_layout(self):
        """Verify desktop media query (>= 1200px) preserves 3-slot shell with active side slots."""
        content = extract_media_query_block(self.article_css, r'@media\s*\(\s*min-width:\s*1200px\s*\)')
        self.assertTrue(len(content) > 0, "Desktop query (min-width: 1200px) must exist in article.css")
        self.assertIn(".article-reading-shell", content)
        self.assertIn(".article-rail-slot", content)
        self.assertIn(".article-main-slot", content)
        self.assertIn(".article-toc-slot", content)

    def test_07_tablet_breakpoint_layout(self):
        """Verify tablet media query (768px - 1199px) hides side slots and centers main slot."""
        content = extract_media_query_block(self.article_css, r'@media\s*\(\s*min-width:\s*768px\s*\)\s*and\s*\(\s*max-width:\s*1199px\s*\)')
        self.assertTrue(len(content) > 0, "Tablet query (min-width: 768px) and (max-width: 1199px) must exist in article.css")
        self.assertIn(".article-rail-slot", content)
        self.assertIn(".article-toc-slot", content)
        self.assertIn("display: none", content)
        self.assertIn(".article-main-slot", content)
        self.assertIn("max-width: 740px", content)

    def test_08_mobile_breakpoint_layout(self):
        """Verify mobile media query (< 768px) sets block layout with zero overflow."""
        content = extract_media_query_block(self.article_css, r'@media\s*\(\s*max-width:\s*767px\s*\)')
        self.assertTrue(len(content) > 0, "Mobile query (max-width: 767px) must exist in article.css")
        self.assertIn(".article-reading-shell", content)
        self.assertIn("display: block", content)
        self.assertIn("padding: 0 var(--space-3, 12px)", content)
        self.assertIn(".article-main-slot", content)
        self.assertIn("width: 100%", content)
        self.assertIn("max-width: 100%", content)

    def test_09_spacing_tokens_in_theme_css(self):
        """Verify spacing tokens --space-4, --space-6, and --space-3 are defined in theme.css."""
        self.assertIn("--space-3: 12px;", self.theme_css)
        self.assertIn("--space-4: 16px;", self.theme_css)
        self.assertIn("--space-6: 24px;", self.theme_css)

    def test_10_zero_emojis_no_em_dashes_offline_first(self):
        """Verify zero emojis, zero em dashes, and 100% offline-first in modified/new files."""
        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]|[\u2600-\u26ff]|[\u2700-\u27bf]")
        files_to_check = [
            (read_file("tests/test_issue80_reading_layout_sticky_header.py"), "test_issue80_reading_layout_sticky_header.py"),
            (self.article_html, "article.html"),
            (self.article_css, "article.css"),
            (self.theme_css, "theme.css")
        ]
        for content, name in files_to_check:
            self.assertIsNone(emoji_pattern.search(content), f"Emoji found in {name}")
            self.assertNotIn("\u2014", content, f"Em dash found in {name}")

        for css_content, source_name in [
            (self.article_css, "article.css"),
            (self.theme_css, "theme.css")
        ]:
            urls = re.findall(r'url\s*\(\s*["\']?(https?://[^"\')]+)', css_content)
            self.assertEqual(len(urls), 0, f"External CDN url found in {source_name}: {urls}")


if __name__ == "__main__":
    unittest.main()
