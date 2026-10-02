#!/usr/bin/env python3
"""
tests/test_issue88_article_cover_unified_ratio.py

Automated test suite for Issue #88:
1. Unified Cover Container & Image Styling:
   - .article-cover-container (#articleCoverContainer):
     width: 100%; max-width: 100%;
     aspect-ratio: 780 / 350 (exact 2.228:1 matching Editor and Feed);
     border-radius: var(--radius-lg, 12px);
     border: 1px solid var(--border-subtle);
     overflow: hidden;
     background: var(--surface-2);
     position: relative;
     box-sizing: border-box;
     margin: var(--space-4, 16px) 0 var(--space-6, 24px) 0;
   - .article-cover-img (#articleCoverImg):
     width: 100%; height: 100%;
     object-fit: cover; object-position: center;
     display: block; transition: opacity 0.2s ease-in;
2. Fast LCP Attributes in article.html:
   - #articleCoverImg has loading="eager" and fetchpriority="high".
   - Clean DOM hierarchy: .article-meta-row -> #articleCoverContainer -> content.
3. Absence & Loading Behavior in article.js:
   - Truthy coverImage: sets src, alt, and display: block.
   - Absent/falsy coverImage: sets display: none and removes src.
   - Clean hiding in CSS with margin 0 and height 0.
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


class TestIssue88ArticleCoverUnifiedRatio(unittest.TestCase):
    """Test suite for unified article cover display and ratio invariants."""

    @classmethod
    def setUpClass(cls):
        cls.article_html = read_file("frontend/public/article.html")
        cls.article_css = read_file("frontend/public/css/article.css")
        cls.article_js = read_file("frontend/public/js/article.js")
        cls.theme_css = read_file("frontend/public/css/theme.css")
        cls.test_file_content = read_file("tests/test_issue88_article_cover_unified_ratio.py")

    def test_01_cover_container_and_image_markup_in_article_html(self):
        """Verify #articleCoverContainer and #articleCoverImg have loading eager and fetchpriority high."""
        self.assertIn('id="articleCoverContainer"', self.article_html)
        self.assertIn('class="article-cover-container"', self.article_html)

        img_match = re.search(r'<img[^>]*id="articleCoverImg"[^>]*>', self.article_html)
        self.assertIsNotNone(img_match, "<img id=\"articleCoverImg\"> must exist in article.html")
        img_tag = img_match.group(0)

        self.assertIn('class="article-cover-img"', img_tag)
        self.assertIn('loading="eager"', img_tag)
        self.assertIn('fetchpriority="high"', img_tag)

    def test_02_cover_container_unified_aspect_ratio_in_article_css(self):
        """Verify .article-cover-container has 780 / 350 aspect-ratio, surface-2 bg, and subtle border."""
        container_rule = re.search(r'\.article-cover-container\s*\{([^}]+)\}', self.article_css)
        self.assertIsNotNone(container_rule, ".article-cover-container rule must exist in article.css")
        css_block = container_rule.group(1)

        self.assertIn("width: 100%", css_block)
        self.assertIn("max-width: 100%", css_block)
        self.assertIn("aspect-ratio: 780 / 350", css_block)
        self.assertIn("border-radius: var(--radius-lg, 12px)", css_block)
        self.assertIn("border: 1px solid var(--border-subtle)", css_block)
        self.assertIn("overflow: hidden", css_block)
        self.assertIn("background: var(--surface-2)", css_block)
        self.assertIn("position: relative", css_block)
        self.assertIn("box-sizing: border-box", css_block)
        self.assertIn("margin: var(--space-4, 16px) 0 var(--space-6, 24px) 0", css_block)

    def test_03_cover_image_fit_and_styling_in_article_css(self):
        """Verify .article-cover-img has 100% width/height, object-fit cover, center position, and opacity transition."""
        img_rule = re.search(r'\.article-cover-img\s*\{([^}]+)\}', self.article_css)
        self.assertIsNotNone(img_rule, ".article-cover-img rule must exist in article.css")
        css_block = img_rule.group(1)

        self.assertIn("width: 100%", css_block)
        self.assertIn("height: 100%", css_block)
        self.assertIn("object-fit: cover", css_block)
        self.assertIn("object-position: center", css_block)
        self.assertIn("display: block", css_block)
        self.assertIn("transition: opacity 0.2s ease-in", css_block)

    def test_04_cover_container_hidden_state_in_article_css(self):
        """Verify hidden cover container resets margin, padding, height, and border to zero gaps."""
        hidden_rule = re.search(r'\.article-cover-container\[style\*="display:\s*none"\]\s*\{([^}]+)\}', self.article_css)
        self.assertIsNotNone(hidden_rule, "Hidden cover container rule must exist in article.css")
        css_block = hidden_rule.group(1)

        self.assertIn("display: none !important", css_block)
        self.assertIn("margin: 0 !important", css_block)
        self.assertIn("padding: 0 !important", css_block)
        self.assertIn("height: 0 !important", css_block)

    def test_05_dom_hierarchy_order_in_article_html(self):
        """Verify DOM hierarchy: .article-meta-row precedes #articleCoverContainer, which precedes #articleBodyContent."""
        idx_meta = self.article_html.find('class="article-meta-row"')
        idx_cover = self.article_html.find('id="articleCoverContainer"')
        idx_content = self.article_html.find('id="articleBodyContent"')

        self.assertNotEqual(idx_meta, -1, "Meta row must exist")
        self.assertNotEqual(idx_cover, -1, "Cover container must exist")
        self.assertNotEqual(idx_content, -1, "Body content must exist")
        self.assertTrue(idx_meta < idx_cover < idx_content, "DOM order must be: meta row -> cover container -> body content")

    def test_06_cover_rendering_logic_in_article_js(self):
        """Verify article.js sets src/alt/block on coverImage presence, and hides/clears on absence."""
        self.assertIn("articleCoverContainer", self.article_js)
        self.assertIn("articleCoverImg", self.article_js)
        self.assertIn("if (article.coverImage)", self.article_js)
        self.assertIn("coverImg.src = article.coverImage;", self.article_js)
        self.assertIn("coverContainer.style.display = 'block';", self.article_js)
        self.assertIn("coverContainer.style.display = 'none';", self.article_js)
        self.assertIn("coverImg.removeAttribute('src');", self.article_js)

    def test_07_zero_emojis_no_em_dashes_offline_first(self):
        """Verify zero emojis, zero em dashes, and 100% offline-first in modified/new files."""
        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]|[\u2600-\u26ff]|[\u2700-\u27bf]")
        files_to_check = [
            (self.test_file_content, "test_issue88_article_cover_unified_ratio.py"),
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
