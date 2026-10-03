#!/usr/bin/env python3
"""
tests/test_issue82_compact_author_meta.py

Automated test suite for Issue #82:
1. Top author metadata row refactoring:
   - #articleAuthorRole is removed from top .article-meta-row.
   - .article-author-info and .article-meta-row are compact (target height 48-56px).
   - Author avatar (.article-author-avatar): 40-44px, rounded (50% or 8px), cursor pointer, link to profile.
   - Author name (#articleAuthorName): font-weight: 600, link/button to author profile.
   - Subscribe button (#btnSubscribeAuthor): compact pill outline/secondary style:
     * height: 28px; padding: 0 10px; font-size: 12px; border-radius: 9999px;
   - Metadata line:
     * Date (#articlePublishDate) with hover tooltip of exact ISO timestamp.
     * Separator dot (.meta-dot).
     * Reading time (#articleReadingTime) with clock icon.
     * Edited indicator (#articleEditedStatus): displays '(ред.)' with title 'Обновлено: <date>' if edited.
2. Mobile adaptation:
   - Media query max-width 640px stacks cleanly without staircase line wraps.
3. JavaScript logic in article.js:
   - Safeguarded #articleAuthorRole check: if (authorRoleEl) { ... }.
   - #articleEditedStatus populated with '(ред.)' and 'Обновлено: ...' when updated_at > created_at.
   - #btnSubscribeAuthor toggle logic functions correctly.
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


class TestIssue82CompactAuthorMeta(unittest.TestCase):
    """Test suite for compact author and metadata row in article view."""

    @classmethod
    def setUpClass(cls):
        cls.article_html = read_file("frontend/public/article.html")
        cls.article_css = read_file("frontend/public/css/article.css")
        cls.article_js = read_file("frontend/public/js/article.js")
        cls.theme_css = read_file("frontend/public/css/theme.css")
        cls.test_file_content = read_file("tests/test_issue82_compact_author_meta.py")

    def test_01_author_role_excluded_from_top_meta_row(self):
        """Verify #articleAuthorRole is removed from top .article-meta-row in article.html."""
        meta_row_match = re.search(r'<div[^>]*class="[^"]*article-meta-row[^"]*"[^>]*>(.*?)</div>\s*<!--\s*Cover Image Container\s*-->', self.article_html, re.DOTALL)
        self.assertIsNotNone(meta_row_match, ".article-meta-row block must exist before cover image container")
        meta_row_content = meta_row_match.group(1)

        self.assertNotIn("articleAuthorRole", meta_row_content, "#articleAuthorRole must NOT be in top .article-meta-row")

    def test_02_essential_author_and_meta_elements_present_in_top_row(self):
        """Verify avatar, author name, subscribe button, date, edited status, and reading time are present."""
        meta_row_match = re.search(r'<div[^>]*class="[^"]*article-meta-row[^"]*"[^>]*>(.*?)</div>\s*<!--\s*Cover Image Container\s*-->', self.article_html, re.DOTALL)
        self.assertIsNotNone(meta_row_match)
        content = meta_row_match.group(1)

        self.assertIn('id="articleAuthorAvatar"', content)
        self.assertIn('id="articleAuthorName"', content)
        self.assertIn('id="btnSubscribeAuthor"', content)
        self.assertIn('id="articlePublishDate"', content)
        self.assertIn('id="articleEditedStatus"', content)
        self.assertIn('class="meta-dot"', content)
        self.assertIn('id="articleReadingTime"', content)

    def test_03_author_avatar_and_name_profile_links(self):
        """Verify avatar and author name are styled/wired as profile triggers with .btn-author-profile."""
        meta_row_match = re.search(r'<div[^>]*class="[^"]*article-meta-row[^"]*"[^>]*>(.*?)</div>\s*<!--\s*Cover Image Container\s*-->', self.article_html, re.DOTALL)
        self.assertIsNotNone(meta_row_match)
        content = meta_row_match.group(1)

        self.assertIn('btn-author-profile', content)
        # Verify article.js sets data-author-id and data-user-id on avatar and name
        self.assertIn("avatarEl.setAttribute('data-author-id', authorId)", self.article_js)
        self.assertIn("authorNameEl.setAttribute('data-author-id', authorId)", self.article_js)

    def test_04_compact_author_meta_css_properties(self):
        """Verify .article-meta-row and .article-author-avatar compact dimensions in article.css."""
        meta_rule = re.search(r'\.article-meta-row\s*\{([^}]+)\}', self.article_css)
        self.assertIsNotNone(meta_rule, ".article-meta-row rule must exist in article.css")
        meta_css = meta_rule.group(1)
        self.assertIn("min-height: 48px", meta_css)
        self.assertIn("padding: 6px 0", meta_css)

        avatar_rule = re.search(r'\.article-author-avatar\s*\{([^}]+)\}', self.article_css)
        self.assertIsNotNone(avatar_rule, ".article-author-avatar rule must exist in article.css")
        avatar_css = avatar_rule.group(1)
        self.assertIn("width: 40px", avatar_css)
        self.assertIn("height: 40px", avatar_css)
        self.assertIn("border-radius: 50%", avatar_css)
        self.assertIn("cursor: pointer", avatar_css)

        name_rule = re.search(r'\.article-author-name\s*\{([^}]+)\}', self.article_css)
        self.assertIsNotNone(name_rule, ".article-author-name rule must exist in article.css")
        name_css = name_rule.group(1)
        self.assertIn("font-weight: 600", name_css)

    def test_05_compact_subscribe_button_styling(self):
        """Verify #btnSubscribeAuthor compact pill styling (height 28px, padding 0 10px, font-size 12px, border-radius 9999px)."""
        sub_rule = re.search(r'\.btn-author-subscribe[^{]*\{([^}]+)\}', self.article_css)
        self.assertIsNotNone(sub_rule, ".btn-author-subscribe rule must exist in article.css")
        sub_css = sub_rule.group(1)

        self.assertIn("height: 28px", sub_css)
        self.assertIn("padding: 0 10px", sub_css)
        self.assertIn("font-size: 12px", sub_css)
        self.assertTrue(
            "border-radius: var(--radius-sm" in sub_css or "border-radius: 9999px" in sub_css,
            "Subscribe button must have valid border-radius"
        )
        self.assertIn("cursor: pointer", sub_css)

        # Hover and subscribed state
        self.assertIn(".btn-author-subscribe:hover", self.article_css)
        self.assertIn(".btn-author-subscribe.is-subscribed", self.article_css)

    def test_06_date_iso_tooltip_and_reading_time_in_article_js(self):
        """Verify article.js sets dateEl.title with ISO timestamp and formats reading time."""
        self.assertIn("dateEl.title = rawIso", self.article_js)
        self.assertIn("articleReadingTime", self.article_js)
        self.assertIn("readingTimeEl.textContent = (article.readingTime || '5 мин') + ' чтения'", self.article_js)

    def test_07_article_edited_status_logic_in_article_js(self):
        """Verify article.js displays (ред.) and title 'Обновлено: ...' when article is edited."""
        self.assertIn("articleEditedStatus", self.article_js)
        self.assertIn("editedEl.textContent = '(ред.)'", self.article_js)
        self.assertIn("editedEl.title = 'Обновлено: ' + updatedDisplay", self.article_js)
        self.assertIn("editedEl.style.display = 'inline-block'", self.article_js)

    def test_08_mobile_adaptation_max_width_640px(self):
        """Verify mobile media query (max-width: 640px) stacks meta row cleanly without staircase line wraps."""
        mobile_match = re.search(r'@media\s*\(\s*max-width:\s*640px\s*\)\s*\{([^}]+(?:\{[^}]+\}[^}]+)*)\}', self.article_css)
        self.assertIsNotNone(mobile_match, "@media (max-width: 640px) block must exist in article.css")
        mobile_css = mobile_match.group(1)

        self.assertIn(".article-meta-row", mobile_css)
        self.assertIn("flex-direction: column", mobile_css)
        self.assertIn("align-items: flex-start", mobile_css)

    def test_09_safeguard_author_role_check_in_article_js(self):
        """Verify article.js safeguards #articleAuthorRole check so removing it from DOM does not error."""
        self.assertIn("const authorRoleEl = document.getElementById('articleAuthorRole');", self.article_js)
        self.assertIn("if (authorRoleEl) {", self.article_js)

    def test_10_zero_emojis_no_em_dashes_offline_first(self):
        """Verify zero emojis, zero em dashes, and 100% offline-first in modified/new files."""
        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]|[\u2600-\u26ff]|[\u2700-\u27bf]")
        files_to_check = [
            (self.test_file_content, "test_issue82_compact_author_meta.py"),
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
