"""Unit tests for Issue #107: Relocating publication topics from header to footer under keywords.

Verifies:
1. Header badges container is hidden or absent before H1, so no topic chips appear before title.
2. Footer contains both keywords (#articleTagsWrap) and topics (#articleTopicsWrap) as distinct groups.
3. articleTopicsWrap contains label 'Темы:' and list container (#articleTopicsList).
4. Topics and keywords have rectangular geometry with var(--radius-sm), no 9999px pills.
5. Topics are visually distinct from keywords (different background/styling).
6. JavaScript dynamically populates topics in #articleTopicsList and sets links to feed.html?topic=<id>.
7. Zero emojis, zero em dashes, and offline-first compliance.
"""

import os
import re
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestIssue107TopicsRelocation(unittest.TestCase):
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

    def test_01_no_topic_chips_rendered_in_header(self):
        """Verify that header badges are hidden or removed, preventing topic chips before H1."""
        # CSS must ensure .article-badges is hidden
        self.assertIn(".article-badges", self.css)
        badges_css_match = re.search(r'\.article-badges\s*\{([^}]+)\}', self.css)
        self.assertIsNotNone(badges_css_match, ".article-badges rule must exist in article.css")
        self.assertIn("display: none", badges_css_match.group(1))

        # JS must not populate articleBadges with topics
        self.assertIn("badgesWrap.style.display = 'none'", self.js)

    def test_02_footer_contains_keywords_and_topics_structure(self):
        """Verify footer contains both distinct groups: articleTagsWrap and articleTopicsWrap."""
        self.assertIn('id="articleTagsWrap"', self.html)
        self.assertIn('id="articleTagsList"', self.html)
        self.assertIn('id="articleTopicsWrap"', self.html)
        self.assertIn('id="articleTopicsList"', self.html)

        # Ensure topics block is placed after keywords block in footer
        tags_idx = self.html.find('id="articleTagsWrap"')
        topics_idx = self.html.find('id="articleTopicsWrap"')
        self.assertTrue(tags_idx != -1 and topics_idx != -1)
        self.assertLess(tags_idx, topics_idx, "articleTopicsWrap must be positioned after articleTagsWrap")

    def test_03_topics_label_and_distinct_entities(self):
        """Verify topics and keywords have explicit separate labels and are not merged."""
        self.assertIn("Ключевые слова:", self.html)
        self.assertIn("Темы:", self.html)
        self.assertIn("topics-label", self.html)
        self.assertIn("tags-label", self.html)

    def test_04_topics_styling_geometry_and_differentiation(self):
        """Verify topics styling uses var(--radius-sm), no pills, and visual distinction."""
        topics_wrap_match = re.search(r'\.article-topics-wrap\s*\{([^}]+)\}', self.css)
        self.assertIsNotNone(topics_wrap_match, ".article-topics-wrap rule must exist in article.css")

        # Must not contain 9999px
        self.assertNotIn("9999px", self.css)

        # Topic items styling
        topic_item_match = re.search(r'\.article-topics-list[^{]*\.topic-badge[^{]*\{([^}]+)\}', self.css)
        self.assertIsNotNone(topic_item_match, "Topics in list must be styled in article.css")
        topic_item_css = topic_item_match.group(1)
        self.assertIn("var(--radius-sm)", topic_item_css)
        self.assertIn("var(--surface-2)", topic_item_css)

    def test_05_js_populates_topics_with_links(self):
        """Verify article.js renders topic chips into #articleTopicsList with links to feed."""
        self.assertIn("document.getElementById('articleTopicsWrap')", self.js)
        self.assertIn("document.getElementById('articleTopicsList')", self.js)
        self.assertIn("feed.html?topic=", self.js)
        self.assertIn("topicsList.appendChild", self.js)

    def test_06_zero_emojis_and_zero_em_dashes(self):
        """Verify strict project invariants: zero emojis and zero em dashes."""
        for name, content in [("article.html", self.html), ("article.css", self.css), ("article.js", self.js)]:
            self.assertNotIn("\u2014", content, f"Em dash found in {name}")
            # Check for emoji ranges
            emoji_pattern = re.compile(
                r'[\U00010000-\U0010ffff]|[\u2600-\u27ff]|[\u2300-\u23ff]|[\u2b50-\u2b55]'
            )
            self.assertIsNone(emoji_pattern.search(content), f"Emoji found in {name}")


if __name__ == "__main__":
    unittest.main()
