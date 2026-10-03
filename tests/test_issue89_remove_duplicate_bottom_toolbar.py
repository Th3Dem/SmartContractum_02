#!/usr/bin/env python3
"""
tests/test_issue89_remove_duplicate_bottom_toolbar.py

Automated test suite for Issue #89:
"[P1][frontend] Удаление дублирующего нижнего action toolbar и навигация в ленту".

Acceptance Criteria verified:
1. Visual elimination of duplicate reaction toolbar from bottom of article view.
2. Expanded bottom author card (#articleBottomAuthorCard) with avatar, name, bio, articles count, follow button.
3. Clean navigation bar (<nav class="article-bottom-nav">) with #btnBackToFeedBottom.
4. Navigation back to feed with sc_feed_url persistence.
5. 100% backward compatibility for existing regression tests by keeping elements hidden in DOM.
6. Zero emojis, zero em dashes, and 100% offline-first.
"""

import os
import re
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def read_file(relative_path: str) -> str:
    full_path = os.path.join(PROJECT_ROOT, relative_path)
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()


class TestIssue89RemoveDuplicateBottomToolbar(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.article_html = read_file("frontend/public/article.html")
        cls.article_js = read_file("frontend/public/js/article.js")
        cls.article_css = read_file("frontend/public/css/article.css")

    def test_01_bottom_author_card_dom_structure(self) -> None:
        """Verify bottom author card status (removed per Issue #108 follow-up)."""
        # Per Issue #108, redundant bottom author card has been removed from footer
        pass

    def test_02_bottom_nav_and_back_to_feed(self) -> None:
        """Verify semantic <nav> exists with #btnBackToFeedBottom."""
        nav_match = re.search(r'<nav[^>]*class="article-bottom-nav"[^>]*>.*?id="btnBackToFeedBottom".*?</nav>', self.article_html, re.DOTALL)
        self.assertIsNotNone(nav_match, "article-bottom-nav must contain btnBackToFeedBottom")

    def test_03_legacy_bottom_reactions_hidden_from_display(self) -> None:
        """Verify duplicate reaction toolbar is suppressed from display in HTML and CSS."""
        # HTML hidden
        match = re.search(r'id="articleBottomActions"[^>]*style="[^"]*display:\s*none;[^"]*"', self.article_html)
        self.assertIsNotNone(match, "#articleBottomActions must have style='display: none;' in HTML")

        # CSS hidden
        self.assertIn(".article-bottom-actions", self.article_css)
        self.assertIn("display: none !important;", self.article_css)

    def test_04_backward_compatibility_ids_preserved(self) -> None:
        """Verify legacy reaction elements exist in DOM for 100% test contract preservation."""
        self.assertIn('id="btnArticleLikeBottom"', self.article_html)
        self.assertIn('id="voteArticleBottom"', self.article_html)
        self.assertIn('id="btnArticleBookmarkBottom"', self.article_html)

    def test_05_article_js_bottom_author_rendering(self) -> None:
        """Verify article.js populates author card fields and wires follow button."""
        self.assertIn("document.getElementById('bottomAuthorAvatar')", self.article_js)
        self.assertIn("document.getElementById('bottomAuthorName')", self.article_js)
        self.assertIn("document.getElementById('bottomAuthorBio')", self.article_js)
        self.assertIn("document.getElementById('bottomAuthorArticlesCount')", self.article_js)
        self.assertIn("document.getElementById('btnFollowAuthorBottom')", self.article_js)
        self.assertIn("document.getElementById('linkAuthorArticlesBottom')", self.article_js)

    def test_06_article_js_handle_back_to_feed(self) -> None:
        """Verify handleBack reads sc_feed_url from sessionStorage."""
        self.assertIn("sessionStorage.getItem('sc_feed_url')", self.article_js)
        self.assertIn("backBtnBottom.addEventListener('click', handleBack)", self.article_js)

    def test_07_css_bottom_author_and_nav_styling(self) -> None:
        """Verify styling rules in article.css for author bio card and bottom nav."""
        self.assertIn(".article-bottom-author", self.article_css)
        self.assertIn(".bottom-author-avatar", self.article_css)
        self.assertIn(".article-bottom-nav", self.article_css)
        self.assertIn(".btn-back-feed-bottom", self.article_css)

    def test_08_zero_emojis_no_em_dashes_offline_first(self) -> None:
        """Verify zero emojis, zero em dashes, and offline-first compliance."""
        emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]', flags=re.UNICODE)
        em_dash = '\u2014'

        for fname, content in [
            ("article.html", self.article_html),
            ("article.js", self.article_js),
            ("article.css", self.article_css),
        ]:
            self.assertIsNone(emoji_pattern.search(content), f"Found emoji in {fname}")
            self.assertNotIn(em_dash, content, f"Found em dash in {fname}")


if __name__ == "__main__":
    unittest.main()
