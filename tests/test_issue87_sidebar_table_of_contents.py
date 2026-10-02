#!/usr/bin/env python3
"""
tests/test_issue87_sidebar_table_of_contents.py

Automated test suite for Issue #87:
1. Desktop Sidebar Table of Contents:
   - In frontend/public/article.html, inside .article-toc-slot (#articleTocSlot):
     #articleSidebarToc with role="navigation" or nav tag, aria-label="Содержание статьи",
     .sidebar-toc-title ("Содержание"), and #sidebarTocList (.sidebar-toc-list).
   - In frontend/public/css/article.css:
     * .article-sidebar-toc: sticky, top: 80px, width: 250px, max-height: calc(100vh - 120px),
       overflow-y: auto, padding: 16px, border-radius: var(--radius-lg, 12px),
       background: var(--surface-1), border: 1px solid var(--border-subtle).
     * .sidebar-toc-link: display: block, padding: 6px 10px, font-size: 13px,
       color: var(--text-secondary), border-left: 2px solid transparent, transition.
     * .sidebar-toc-link.is-active: color: var(--accent), border-left-color: var(--accent),
       font-weight: 600, background: var(--accent-subtle).
     * .sidebar-toc-link.toc-level-3: padding-left: 22px, font-size: 12.5px.
     * Heading scroll-margin-top: 80px on article headings.
2. Threshold & Intelligent Display:
   - In frontend/public/js/article.js:
     * Condition: if (headings.length < 3) { hide both sidebar and inline TOC; return; }
     * Populates both #sidebarTocList and #articleTocList for headings >= 3.
     * Uses IntersectionObserver with rootMargin '0px 0px -70% 0px' to track visible headings
       and toggle .is-active.
     * Smooth anchor navigation.
3. Mobile / Tablet Collapsible Accordion:
   - For viewports < 1200px:
     * .article-toc-slot is hidden (display: none).
     * Inside .article-main-slot, #articleTocBox is a collapsible accordion (<details class="article-toc-accordion">)
       displayed only when headings >= 3.
     * On desktop (>= 1200px), inline #articleTocBox is hidden (display: none !important).
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


class TestIssue87SidebarTableOfContents(unittest.TestCase):
    """Test suite for desktop sidebar table of contents and mobile accordion."""

    @classmethod
    def setUpClass(cls):
        cls.article_html = read_file("frontend/public/article.html")
        cls.article_css = read_file("frontend/public/css/article.css")
        cls.article_js = read_file("frontend/public/js/article.js")
        cls.theme_css = read_file("frontend/public/css/theme.css")
        cls.test_file_content = read_file("tests/test_issue87_sidebar_table_of_contents.py")

    def test_01_desktop_sidebar_toc_structure_and_aria(self):
        """Verify presence of sidebar TOC component in #articleTocSlot with correct accessibility."""
        self.assertIn('id="articleTocSlot"', self.article_html)
        self.assertIn('id="articleSidebarToc"', self.article_html)
        self.assertIn('class="article-sidebar-toc"', self.article_html)
        self.assertIn('aria-label="Содержание статьи"', self.article_html)

        # Confirm sidebar TOC is inside #articleTocSlot
        slot_idx = self.article_html.find('id="articleTocSlot"')
        self.assertNotEqual(slot_idx, -1)
        toc_idx = self.article_html.find('id="articleSidebarToc"', slot_idx)
        self.assertNotEqual(toc_idx, -1, "articleSidebarToc must be inside articleTocSlot")

        # Confirm title and list container
        self.assertIn('class="sidebar-toc-title"', self.article_html)
        self.assertIn("Содержание", self.article_html)
        self.assertIn('id="sidebarTocList"', self.article_html)
        self.assertIn('class="sidebar-toc-list"', self.article_html)

    def test_02_desktop_sidebar_toc_css_properties(self):
        """Verify .article-sidebar-toc styling rules in article.css."""
        sidebar_match = re.search(r'\.article-sidebar-toc\s*\{([^}]+)\}', self.article_css)
        self.assertIsNotNone(sidebar_match, ".article-sidebar-toc rule must exist in article.css")
        css_block = sidebar_match.group(1)

        self.assertIn("position: sticky", css_block)
        self.assertIn("top: 80px", css_block)
        self.assertIn("width: 250px", css_block)
        self.assertIn("max-height: calc(100vh - 120px)", css_block)
        self.assertIn("overflow-y: auto", css_block)
        self.assertIn("padding: 16px", css_block)
        self.assertIn("var(--surface-1)", css_block)
        self.assertIn("border: 1px solid var(--border-subtle)", css_block)

    def test_03_sidebar_toc_link_styling_and_levels(self):
        """Verify .sidebar-toc-link, active state, and H3 indentation in article.css."""
        link_match = re.search(r'\.sidebar-toc-link\s*\{([^}]+)\}', self.article_css)
        self.assertIsNotNone(link_match, ".sidebar-toc-link rule must exist in article.css")
        link_block = link_match.group(1)
        self.assertIn("display: block", link_block)
        self.assertIn("padding: 6px 10px", link_block)
        self.assertIn("font-size: 13px", link_block)
        self.assertIn("border-left: 2px solid transparent", link_block)

        # Active state (.is-active)
        active_match = re.search(r'\.sidebar-toc-link\.is-active\s*\{([^}]+)\}', self.article_css)
        self.assertIsNotNone(active_match, ".sidebar-toc-link.is-active rule must exist in article.css")
        active_block = active_match.group(1)
        self.assertIn("color: var(--accent)", active_block)
        self.assertIn("border-left-color: var(--accent)", active_block)
        self.assertIn("font-weight: 600", active_block)

        # Level 3 indentation
        l3_match = re.search(r'\.sidebar-toc-link\.toc-level-3\s*\{([^}]+)\}', self.article_css)
        self.assertIsNotNone(l3_match, ".sidebar-toc-link.toc-level-3 rule must exist in article.css")
        l3_block = l3_match.group(1)
        self.assertIn("padding-left: 22px", l3_block)
        self.assertIn("font-size: 12.5px", l3_block)

    def test_04_heading_scroll_margin_top(self):
        """Verify scroll-margin-top: 80px on article headings."""
        scroll_margin_match = re.search(
            r'(\.article-content\s+h[1-4]|#articleContent\s+h[1-4]|\.article-body-content\s+h[1-4])[^{]*\{[^}]*scroll-margin-top:\s*80px',
            self.article_css
        )
        self.assertIsNotNone(scroll_margin_match, "Article headings must have scroll-margin-top: 80px")

    def test_05_threshold_behavior_in_article_js(self):
        """Verify buildTableOfContents checks headings.length < 3 threshold."""
        fn_idx = self.article_js.find("function buildTableOfContents")
        self.assertNotEqual(fn_idx, -1, "buildTableOfContents function must exist")
        fn_block = self.article_js[fn_idx:fn_idx + 800]

        # Verify threshold is strictly < 3
        self.assertIn("headings.length < 3", fn_block)
        self.assertIn("tocBox.style.display = 'none'", fn_block)
        self.assertIn("sidebarToc.style.display = 'none'", fn_block)

    def test_06_intersection_observer_and_active_tracking_in_article_js(self):
        """Verify IntersectionObserver tracks visible headings and sets .is-active."""
        fn_idx = self.article_js.find("function buildTableOfContents")
        self.assertNotEqual(fn_idx, -1)
        fn_block = self.article_js[fn_idx:fn_idx + 3500]

        self.assertIn("IntersectionObserver", fn_block)
        self.assertIn("is-active", fn_block)
        self.assertIn("rootMargin", fn_block)
        self.assertIn("activeTocObserver", self.article_js)
        self.assertIn("activeTocObserver.disconnect()", self.article_js)

    def test_07_smooth_anchor_navigation_in_article_js(self):
        """Verify smooth scrolling and history state on TOC link click."""
        fn_idx = self.article_js.find("function buildTableOfContents")
        self.assertNotEqual(fn_idx, -1)
        fn_block = self.article_js[fn_idx:fn_idx + 3500]

        self.assertIn("scrollIntoView", fn_block)
        self.assertIn("behavior: 'smooth'", fn_block)
        self.assertIn("block: 'start'", fn_block)
        self.assertIn("history.pushState", fn_block)

    def test_08_mobile_tablet_collapsible_accordion_markup_and_css(self):
        """Verify inline #articleTocBox is a collapsible accordion and hidden on desktop."""
        self.assertIn('<details', self.article_html)
        self.assertIn('class="article-toc-box article-toc-accordion"', self.article_html)
        self.assertIn('<summary class="toc-header">', self.article_html)
        self.assertIn('class="toc-chevron"', self.article_html)

        # Accordion styling in article.css
        self.assertIn(".article-toc-accordion", self.article_css)
        self.assertIn("summary.toc-header", self.article_css)
        self.assertIn(".article-toc-accordion[open] .toc-chevron", self.article_css)

        # Hidden on desktop (>= 1200px)
        desktop_query = re.search(r'@media\s*\(\s*min-width:\s*1200px\s*\)\s*\{([\s\S]+?)(?=\n@media|\Z)', self.article_css)
        self.assertIsNotNone(desktop_query)
        desktop_block = desktop_query.group(1)
        self.assertTrue(
            "#articleTocBox" in desktop_block or ".article-toc-box" in desktop_block or ".article-toc-accordion" in desktop_block,
            "Inline accordion TOC must be hidden on desktop >= 1200px"
        )
        self.assertIn("display: none !important", desktop_block)

    def test_09_tablet_and_mobile_sidebar_hidden(self):
        """Verify .article-toc-slot is hidden on tablet and mobile viewports."""
        tablet_query = re.search(r'@media[^{]*768px[^{]*1199px[^{]*\{([\s\S]+?)(?=\n@media|\Z)', self.article_css)
        self.assertIsNotNone(tablet_query)
        tablet_block = tablet_query.group(1)
        self.assertIn(".article-toc-slot", tablet_block)
        self.assertIn("display: none", tablet_block)

        mobile_query = re.search(r'@media\s*\(\s*max-width:\s*767px\s*\)\s*\{([\s\S]+?)(?=\n@media|\Z)', self.article_css)
        self.assertIsNotNone(mobile_query)
        mobile_block = mobile_query.group(1)
        self.assertIn(".article-toc-slot", mobile_block)

    def test_10_zero_emojis_no_em_dashes_offline_first(self):
        """Verify zero emojis, zero em dashes, and 100% offline-first in modified/new files."""
        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]|[\u2600-\u26ff]|[\u2700-\u27bf]")
        files_to_check = [
            (self.test_file_content, "test_issue87_sidebar_table_of_contents.py"),
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
