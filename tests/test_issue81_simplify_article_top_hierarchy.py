#!/usr/bin/env python3
"""
tests/test_issue81_simplify_article_top_hierarchy.py

Automated test suite for Issue #81:
1. Lightweight navigation header:
   - Replaces heavy .article-top-bar with clean .article-nav-header.
   - Contains #btnBackToFeed with class .btn-back-feed-link, text "Лента", and SVG left arrow.
2. Removal of duplicate reaction buttons from top nav:
   - .article-nav-header must not contain like, vote capsule, or bookmark buttons.
   - Staged into #articleRailSlot for Issue #84 (Sticky Action Rail).
3. Back navigation functionality in article.js:
   - handleBack() checks sessionStorage ('sc_feed_url'), document.referrer, and falls back to feed.html.
   - Binds to #btnBackToFeed.
4. Modern topic chips:
   - .topic-badge / .meta-badge styled as pill chips (border-radius: 9999px, padding: 4px 12px,
     background: var(--surface-2), border: 1px solid var(--border-subtle), color: var(--text-secondary)).
   - Hover state uses var(--accent).
   - Rendered as clickable links to feed.html?topic=<id>.
5. Strict visual hierarchy in article.html:
   - Top nav -> Topics -> Title H1 -> Lead paragraph -> Author metadata row -> Cover image -> Content.
6. Article lead typography:
   - font-size: 1.15rem; color: var(--text-secondary); line-height: 1.6;
7. Theme color tokens:
   - --accent and --surface-2 defined in theme.css for light and dark themes.
8. Invariants:
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


class TestIssue81SimplifyArticleTopHierarchy(unittest.TestCase):
    """Test suite for article top simplification and visual hierarchy."""

    @classmethod
    def setUpClass(cls):
        cls.article_html = read_file("frontend/public/article.html")
        cls.article_css = read_file("frontend/public/css/article.css")
        cls.article_js = read_file("frontend/public/js/article.js")
        cls.theme_css = read_file("frontend/public/css/theme.css")
        cls.test_file_content = read_file("tests/test_issue81_simplify_article_top_hierarchy.py")

    def test_01_lightweight_navigation_header_structure(self):
        """Verify .article-nav-header exists and contains clean .btn-back-feed-link button."""
        self.assertIn('class="article-nav-header"', self.article_html)
        self.assertIn('id="articleNavHeader"', self.article_html)

        # Nav header element
        nav_match = re.search(r'<nav[^>]*class="[^"]*article-nav-header[^"]*"[^>]*>(.*?)</nav>', self.article_html, re.DOTALL)
        self.assertIsNotNone(nav_match, "Expected <nav class=\"article-nav-header\"> in article.html")
        nav_content = nav_match.group(1)

        # Button back link
        self.assertIn('id="btnBackToFeed"', nav_content)
        self.assertIn('class="btn-back-feed-link"', nav_content)
        self.assertIn('title="Вернуться к ленте публикаций"', nav_content)
        self.assertIn('aria-label="Вернуться к ленте публикаций"', nav_content)
        self.assertIn('<span>Лента</span>', nav_content)
        self.assertIn('<polyline points="12 19 5 12 12 5"></polyline>', nav_content)

    def test_02_nav_header_excludes_duplicate_reactions(self):
        """Verify top navigation header does not contain duplicate reaction buttons."""
        nav_match = re.search(r'<nav[^>]*class="[^"]*article-nav-header[^"]*"[^>]*>(.*?)</nav>', self.article_html, re.DOTALL)
        self.assertIsNotNone(nav_match)
        nav_content = nav_match.group(1)

        self.assertNotIn("btnArticleLike", nav_content)
        self.assertNotIn("voteArticleTop", nav_content)
        self.assertNotIn("btnArticleBookmark", nav_content)
        self.assertNotIn("btnCopyLink", nav_content)

        # Staged reaction buttons must still exist in DOM (for Issue #84 rail slot)
        self.assertIn('id="btnArticleLike"', self.article_html)
        self.assertIn('id="voteArticleTop"', self.article_html)
        self.assertIn('id="btnArticleBookmark"', self.article_html)

    def test_03_handle_back_session_storage_and_fallbacks(self):
        """Verify handleBack in article.js checks sessionStorage, referrer, and falls back to feed.html."""
        self.assertIn("function handleBack()", self.article_js)
        self.assertIn("sessionStorage.getItem('sc_feed_url')", self.article_js)
        self.assertIn("document.referrer", self.article_js)
        self.assertIn("window.history.back()", self.article_js)
        self.assertIn("window.location.href = 'feed.html'", self.article_js)
        self.assertIn("backBtnTop.addEventListener('click', handleBack)", self.article_js)

    def test_04_strict_visual_hierarchy_order_in_article_html(self):
        """Verify strict visual hierarchy: Nav -> Topics -> Title H1 -> Lead -> Meta -> Cover -> Content."""
        idx_nav = self.article_html.find('id="articleNavHeader"')
        if idx_nav == -1:
            idx_nav = self.article_html.find('class="article-nav-header"')
        idx_badges = self.article_html.find('id="articleBadges"')
        idx_title = self.article_html.find('id="articleTitle"')
        idx_lead = self.article_html.find('id="articleLead"')
        idx_meta = self.article_html.find('class="article-meta-row"')
        idx_cover = self.article_html.find('id="articleCoverContainer"')
        idx_content = self.article_html.find('id="articleBodyContent"')

        self.assertNotEqual(idx_nav, -1, "Nav header must be present")
        self.assertNotEqual(idx_badges, -1, "Badges container must be present")
        self.assertNotEqual(idx_title, -1, "Title element must be present")
        self.assertNotEqual(idx_lead, -1, "Lead element must be present")
        self.assertNotEqual(idx_meta, -1, "Meta row must be present")
        self.assertNotEqual(idx_cover, -1, "Cover container must be present")
        self.assertNotEqual(idx_content, -1, "Body content element must be present")

        self.assertTrue(
            idx_nav < idx_badges < idx_title < idx_lead < idx_meta < idx_cover < idx_content,
            f"Visual hierarchy violated: nav({idx_nav}) < badges({idx_badges}) < title({idx_title}) "
            f"< lead({idx_lead}) < meta({idx_meta}) < cover({idx_cover}) < content({idx_content})"
        )

    def test_05_topic_chips_pill_styling_in_article_css(self):
        """Verify .topic-badge and .meta-badge have pill shape, subtle border, surface background, and accent hover."""
        badge_rule_match = re.search(r'(?:\.meta-badge|\.topic-badge)[^{]*\{([^}]+)\}', self.article_css)
        self.assertIsNotNone(badge_rule_match, "Badge rule must exist in article.css")
        block = badge_rule_match.group(1)

        self.assertTrue(
            "border-radius: var(--radius-sm" in block or "border-radius: 9999px" in block,
            "Topic chips must have valid border-radius"
        )
        self.assertIn("border: 1px solid var(--border-subtle)", block)
        self.assertIn("background: var(--surface-2)", block)
        self.assertIn("color: var(--text-secondary)", block)
        self.assertIn("padding: 4px 12px", block)
        self.assertIn("font-size: 12.5px", block)

        # Hover state
        hover_match = re.search(r'(?:\.topic-badge|\.meta-badge):hover[^{]*\{([^}]+)\}', self.article_css)
        self.assertIsNotNone(hover_match, "Badge hover rule must exist in article.css")
        hover_block = hover_match.group(1)
        self.assertIn("color: var(--accent)", hover_block)
        self.assertIn("border-color: var(--accent)", hover_block)

    def test_06_topic_badge_rendering_in_article_js(self):
        """Verify article.js generates topic badges as links to feed.html?topic=<id> with proper classes."""
        self.assertIn("feed.html?topic=", self.article_js)
        self.assertIn("topicBadge.className = 'meta-badge topic-badge'", self.article_js)

    def test_07_article_lead_typography_in_article_css(self):
        """Verify .article-lead typography has font-size 1.15rem, text-secondary color, and 1.6 line-height."""
        lead_match = re.search(r'\.article-lead\s*\{([^}]+)\}', self.article_css)
        self.assertIsNotNone(lead_match, ".article-lead rule must exist in article.css")
        lead_block = lead_match.group(1)

        self.assertIn("font-size: 1.15rem", lead_block)
        self.assertIn("color: var(--text-secondary)", lead_block)
        self.assertIn("line-height: 1.6", lead_block)

    def test_08_theme_css_color_tokens(self):
        """Verify --accent and --surface-2 are defined in theme.css for light and dark themes."""
        # Light theme (:root)
        self.assertIn("--accent: #2563eb;", self.theme_css)
        self.assertIn("--surface-2: #f1f3f5;", self.theme_css)

        # Dark theme
        self.assertIn("--accent: #3861fb;", self.theme_css)
        self.assertIn("--surface-2: rgba(255, 255, 255, 0.06);", self.theme_css)

    def test_09_back_feed_link_hover_and_transition_styling(self):
        """Verify .btn-back-feed-link styling, transition, and SVG shift on hover in article.css."""
        self.assertIn(".btn-back-feed-link", self.article_css)
        self.assertIn(".btn-back-feed-link:hover", self.article_css)
        self.assertIn("transform: translateX(-2px)", self.article_css)

    def test_10_zero_emojis_no_em_dashes_offline_first(self):
        """Verify zero emojis, zero em dashes, and 100% offline-first in modified/new files."""
        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]|[\u2600-\u26ff]|[\u2700-\u27bf]")
        files_to_check = [
            (self.test_file_content, "test_issue81_simplify_article_top_hierarchy.py"),
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
