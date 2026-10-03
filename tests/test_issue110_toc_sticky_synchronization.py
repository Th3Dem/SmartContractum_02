#!/usr/bin/env python3
"""
tests/test_issue110_toc_sticky_synchronization.py

Automated test suite for Issue #110:
1. Unified Sticky Top Offset:
   - CSS variable --reader-sticky-offset defined (calc(var(--header-height, 60px) + 24px)).
   - Both .article-action-rail and .article-sidebar-toc utilize position: sticky and
     top: var(--reader-sticky-offset...).
2. Vertical Slot Alignment & Full-Height Tracking:
   - Both .article-rail-slot and .article-toc-slot have align-self: stretch and padding-top: 24px,
     ensuring left rail, center content, and right TOC start at the exact same horizontal baseline.
3. Internal Scroll for Long TOC:
   - .article-sidebar-toc has max-height: calc(100vh - var(--reader-sticky-offset...) - 24px)
     and overflow-y: auto.
   - Clean custom scrollbar defined (scrollbar-width: thin, ::-webkit-scrollbar).
4. Refined Visual Styling:
   - Standard geometry: border-radius: var(--radius-md, 8px), border: 1px solid var(--border-subtle),
     and subtle shadow without exaggerated floating elevation.
   - Clean title element "Оглавление" in #articleSidebarToc.
5. Non-Jumping Active Item Indication:
   - Base .sidebar-toc-link has border-left: 2px solid transparent, box-sizing: border-box.
   - .sidebar-toc-link.is-active colors border-left with var(--accent) without altering width or triggering layout shifts.
6. Responsive Integrity:
   - Desktop retains sidebar TOC and rail slot; mobile and tablet hide slots and retain inline accordion TOC.
7. Project Invariants:
   - Zero emojis, zero em dashes, 100% offline-first.
"""

import os
import re
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def read_file(relative_path: str) -> str:
    full_path = os.path.join(PROJECT_ROOT, relative_path)
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()


class TestIssue110TocStickySynchronization(unittest.TestCase):
    """Test suite for Table of Contents sticky synchronization and Action Rail alignment."""

    @classmethod
    def setUpClass(cls):
        cls.article_html = read_file("frontend/public/article.html")
        cls.article_css = read_file("frontend/public/css/article.css")
        cls.article_js = read_file("frontend/public/js/article.js")
        cls.theme_css = read_file("frontend/public/css/theme.css")
        cls.test_file_content = read_file("tests/test_issue110_toc_sticky_synchronization.py")

    def test_01_reader_sticky_offset_variable_definition(self):
        """Verify --reader-sticky-offset variable is declared in article.css."""
        self.assertIn("--reader-sticky-offset", self.article_css)
        self.assertTrue(
            re.search(r'--reader-sticky-offset:\s*calc\(\s*var\(--header-height,\s*60px\)\s*\+\s*24px\)', self.article_css),
            "--reader-sticky-offset must calculate calc(var(--header-height, 60px) + 24px)"
        )

    def test_02_action_rail_and_toc_unified_sticky_top(self):
        """Verify both .article-action-rail and .article-sidebar-toc use --reader-sticky-offset."""
        rail_match = re.search(r'\.article-action-rail\s*\{([^}]+)\}', self.article_css)
        self.assertIsNotNone(rail_match, ".article-action-rail rule must exist in article.css")
        rail_block = rail_match.group(1)
        self.assertIn("position: sticky", rail_block)
        self.assertIn("var(--reader-sticky-offset", rail_block)

        toc_match = re.search(r'\.article-sidebar-toc\s*\{([^}]+)\}', self.article_css)
        self.assertIsNotNone(toc_match, ".article-sidebar-toc rule must exist in article.css")
        toc_block = toc_match.group(1)
        self.assertIn("position: sticky", toc_block)
        self.assertIn("var(--reader-sticky-offset", toc_block)

    def test_03_slots_stretch_and_padding_top_alignment(self):
        """Verify rail and toc slots align-self: stretch and padding-top: 24px."""
        rail_slot_match = re.search(r'\.article-rail-slot\s*\{([^}]+)\}', self.article_css)
        self.assertIsNotNone(rail_slot_match, ".article-rail-slot rule must exist")
        rail_slot_block = rail_slot_match.group(1)
        self.assertIn("align-self: stretch", rail_slot_block)
        self.assertIn("padding-top: 24px", rail_slot_block)

        toc_slot_match = re.search(r'\.article-toc-slot\s*\{([^}]+)\}', self.article_css)
        self.assertIsNotNone(toc_slot_match, ".article-toc-slot rule must exist")
        toc_slot_block = toc_slot_match.group(1)
        self.assertIn("align-self: stretch", toc_slot_block)
        self.assertIn("padding-top: 24px", toc_slot_block)

    def test_04_sidebar_toc_max_height_and_scrollable(self):
        """Verify .article-sidebar-toc has dynamic max-height and overflow-y: auto."""
        toc_match = re.search(r'\.article-sidebar-toc\s*\{([^}]+)\}', self.article_css)
        self.assertIsNotNone(toc_match)
        toc_block = toc_match.group(1)
        self.assertIn("max-height:", toc_block)
        self.assertIn("calc(100vh - var(--reader-sticky-offset", toc_block)
        self.assertIn("overflow-y: auto", toc_block)

        # Custom scrollbar styling
        self.assertIn("scrollbar-width: thin", toc_block)
        self.assertIn(".article-sidebar-toc::-webkit-scrollbar", self.article_css)

    def test_05_sidebar_toc_visual_style_and_title(self):
        """Verify standard radius, subtle border, and title 'Оглавление'."""
        toc_match = re.search(r'\.article-sidebar-toc\s*\{([^}]+)\}', self.article_css)
        self.assertIsNotNone(toc_match)
        toc_block = toc_match.group(1)
        self.assertIn("border-radius: var(--radius-md", toc_block)
        self.assertIn("border: 1px solid var(--border-subtle)", toc_block)

        # Title element in HTML
        self.assertIn('class="sidebar-toc-title"', self.article_html)
        self.assertIn("Оглавление", self.article_html)

    def test_06_non_jumping_active_item_layout(self):
        """Verify .sidebar-toc-link has pre-allocated 2px border and box-sizing to prevent jumps."""
        link_match = re.search(r'\.sidebar-toc-link\s*\{([^}]+)\}', self.article_css)
        self.assertIsNotNone(link_match)
        link_block = link_match.group(1)
        self.assertIn("border-left: 2px solid transparent", link_block)
        self.assertIn("box-sizing: border-box", link_block)

        active_match = re.search(r'\.sidebar-toc-link\.is-active\s*\{([^}]+)\}', self.article_css)
        self.assertIsNotNone(active_match)
        active_block = active_match.group(1)
        self.assertIn("border-left-color: var(--accent)", active_block)

    def test_07_mobile_accordion_preserved(self):
        """Verify inline collapsible TOC accordion is preserved for mobile viewports."""
        self.assertIn('class="article-toc-box article-toc-accordion"', self.article_html)
        self.assertIn('.article-toc-accordion', self.article_css)

    def test_08_zero_emojis_no_em_dashes_offline_first(self):
        """Verify zero emojis, zero em dashes, and 100% offline-first."""
        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]|[\u2600-\u26ff]|[\u2700-\u27bf]")
        files_to_check = [
            (self.test_file_content, "test_issue110_toc_sticky_synchronization.py"),
            (self.article_html, "article.html"),
            (self.article_css, "article.css"),
            (self.article_js, "article.js"),
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
