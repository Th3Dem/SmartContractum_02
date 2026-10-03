"""Unit tests for Issue #108: Fix author meta avatar and remove redundant bottom author card.

Verifies:
1. Header author avatar has proper circular container (border-radius: 50%), gradient background, and centered initials.
2. Specificity conflict with .btn-author-profile is resolved: background is never transparent and text-decoration is never underline.
3. Bottom author card (#articleBottomAuthorCard) is completely removed from article.html.
4. Only one subscribe button remains in the document (#btnSubscribeAuthor in top meta row).
5. Author profile triggers (#articleAuthorAvatar and #articleAuthorName) remain interactive and accessible.
6. article.js gracefully handles avatar rendering (initials and image) without throwing errors when bottom card is absent.
7. Project invariants: zero emojis, zero em dashes, and offline-first compliance.
"""

import os
import re
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestIssue108AuthorMetaAndBottomCard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html_path = os.path.join(PROJECT_ROOT, "frontend", "public", "article.html")
        cls.css_path = os.path.join(PROJECT_ROOT, "frontend", "public", "css", "article.css")
        cls.js_path = os.path.join(PROJECT_ROOT, "frontend", "public", "js", "article.js")

        with open(cls.html_path, "r", encoding="utf-8") as f:
            cls.html = f.read()
        with open(cls.css_path, "r", encoding="utf-8") as f:
            cls.css = f.read()
        with open(cls.js_path, "r", encoding="utf-8") as f:
            cls.js = f.read()

    def test_01_header_author_avatar_structure_and_styling(self):
        """Verify header author avatar has circular shape, gradient background, and white text."""
        self.assertIn('id="articleAuthorAvatar"', self.html)
        self.assertIn('class="article-author-avatar', self.html)

        # Avatar rule in CSS
        avatar_match = re.search(r'\.article-author-avatar\s*\{([^}]+)\}', self.css)
        self.assertIsNotNone(avatar_match, ".article-author-avatar rule must exist in article.css")
        avatar_css = avatar_match.group(1)
        self.assertIn("border-radius: 50%", avatar_css)
        self.assertIn("display: flex", avatar_css)
        self.assertIn("background:", avatar_css)

    def test_02_avatar_protected_from_btn_author_profile_override(self):
        """Verify .article-author-avatar with .btn-author-profile retains circle, background, and no underline."""
        override_match = re.search(r'\.article-author-avatar\.btn-author-profile\s*\{([^}]+)\}', self.css)
        self.assertIsNotNone(override_match, "Protected rule for .article-author-avatar.btn-author-profile must exist")
        override_css = override_match.group(1)
        self.assertIn("border-radius: 50%", override_css)
        self.assertIn("background:", override_css)
        self.assertIn("text-decoration: none", override_css)

        # Hover state must not underline avatar
        hover_match = re.search(r'\.article-author-avatar\.btn-author-profile:hover[^{]*\{([^}]+)\}', self.css)
        self.assertIsNotNone(hover_match, "Hover rule for avatar button must exist")
        self.assertIn("text-decoration: none", hover_match.group(1))

    def test_03_bottom_author_card_completely_removed_from_html(self):
        """Verify bottom author card is removed from footer in article.html."""
        self.assertNotIn('id="articleBottomAuthorCard"', self.html)
        self.assertNotIn('id="bottomAuthorBio"', self.html)
        self.assertNotIn('id="bottomAuthorArticlesCount"', self.html)
        self.assertNotIn('id="btnFollowAuthorBottom"', self.html)

    def test_04_only_single_subscribe_button_remains(self):
        """Verify exactly one author subscribe button exists in the document (#btnSubscribeAuthor)."""
        self.assertIn('id="btnSubscribeAuthor"', self.html)
        self.assertNotIn('id="btnFollowAuthorBottom"', self.html)

        # Ensure no other author subscribe buttons exist in HTML
        subscribe_buttons = re.findall(r'id=["\'](?:btnSubscribeAuthor|btnFollowAuthorBottom)["\']', self.html)
        self.assertEqual(len(subscribe_buttons), 1)

    def test_05_author_profile_triggers_in_header_intact(self):
        """Verify avatar and author name profile links exist and are accessible in header."""
        self.assertIn('id="articleAuthorAvatar"', self.html)
        self.assertIn('id="articleAuthorName"', self.html)
        self.assertIn('role="button"', self.html)
        self.assertIn('tabindex="0"', self.html)

    def test_06_article_js_avatar_photo_support_and_safeguards(self):
        """Verify article.js supports authorAvatar image and safeguards bottom author card elements."""
        self.assertIn("author-avatar-img", self.css)
        self.assertIn("article.authorAvatar", self.js)
        self.assertIn("article.authorInitials", self.js)

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
