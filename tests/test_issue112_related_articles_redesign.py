#!/usr/bin/env python3
"""
tests/test_issue112_related_articles_redesign.py

Automated test suite for Issue #112:
1. Section Positioning:
   - #relatedArticlesSection is placed before #commentsSection in reading hierarchy.
2. 2-Column Responsive Layout:
   - Desktop grid specifies 2 columns (repeat(2, 1fr)).
   - Mobile media query (<= 640px) specifies 1 column (1fr).
3. Human-Readable Topic Titles:
   - Technical topic slugs (e.g., smart-contracts-development) are converted to human-readable
     Russian names via PublicationConfig.getTopicById().
   - resolveTopicTitle helper exists and formats chips.
4. Card Geometry and Content Quality:
   - Aspect ratio 780 / 350 for cover image.
   - Standard radius var(--radius-md).
   - Strict self-exclusion preserved.
5. Project Invariants:
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


class TestIssue112RelatedArticlesRedesign(unittest.TestCase):
    """Test suite for Related Articles redesign (Issue #112)."""

    @classmethod
    def setUpClass(cls):
        cls.article_html = read_file("frontend/public/article.html")
        cls.article_css = read_file("frontend/public/css/article.css")
        cls.article_js = read_file("frontend/public/js/article.js")
        cls.theme_css = read_file("frontend/public/css/theme.css")
        cls.test_file_content = read_file("tests/test_issue112_related_articles_redesign.py")

    def test_01_section_positioning_before_comments(self):
        """Verify #relatedArticlesSection is located before #commentsSection in article.html."""
        related_idx = self.article_html.find('id="relatedArticlesSection"')
        comments_idx = self.article_html.find('id="commentsSection"')

        self.assertNotEqual(related_idx, -1, "relatedArticlesSection must exist")
        self.assertNotEqual(comments_idx, -1, "commentsSection must exist")
        self.assertLess(
            related_idx,
            comments_idx,
            "relatedArticlesSection must be positioned before commentsSection"
        )

    def test_02_two_column_desktop_and_one_column_mobile_grid(self):
        """Verify 2 columns on desktop and 1 column on mobile for .related-articles-grid."""
        # 2 columns on desktop
        desktop_grid_match = re.search(
            r'\.related-articles-grid\s*\{[^}]*grid-template-columns:\s*repeat\(2,\s*1fr\)',
            self.article_css
        )
        self.assertIsNotNone(desktop_grid_match, ".related-articles-grid must specify repeat(2, 1fr) for desktop")

        # 1 column on mobile
        mobile_grid_match = re.search(
            r'@media\s*\(max-width:\s*640px\)\s*\{[^}]*\.related-articles-grid\s*\{[^}]*grid-template-columns:\s*1fr',
            self.article_css
        )
        self.assertIsNotNone(mobile_grid_match, "Mobile media query must set 1 column for .related-articles-grid")

    def test_03_human_readable_topic_resolution(self):
        """Verify resolveTopicTitle maps technical slugs to human-readable titles via PublicationConfig."""
        self.assertIn("function resolveTopicTitle", self.article_js)
        self.assertIn("PublicationConfig.getTopicById", self.article_js)
        self.assertIn("resolveTopicTitle(topics[i])", self.article_js)

    def test_04_card_aspect_ratio_and_styling(self):
        """Verify 780:350 cover ratio, standard radii, and title clamp."""
        self.assertIn("aspect-ratio: 780 / 350", self.article_css)
        self.assertIn("border-radius: var(--radius-md)", self.article_css)
        self.assertIn("-webkit-line-clamp: 2", self.article_css)

    def test_05_strict_self_exclusion_maintained(self):
        """Verify getRelatedArticles maintains strict self-exclusion."""
        self.assertIn("function getRelatedArticles", self.article_js)
        self.assertIn("item.id === curId", self.article_js)

    def test_06_zero_emojis_no_em_dashes_offline_first(self):
        """Verify zero emojis, zero em dashes, and 100% offline-first."""
        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]|[\u2600-\u26ff]|[\u2700-\u27bf]")
        files_to_check = [
            (self.test_file_content, "test_issue112_related_articles_redesign.py"),
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
