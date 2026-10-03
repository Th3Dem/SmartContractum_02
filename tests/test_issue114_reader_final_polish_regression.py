"""
Regression and comprehensive audit tests for Issue #114:
Second UX/UI polish package for publication reader page.

Verifies:
1. Geometry unification: no capsule/pill borders on buttons, chips, action rail.
2. Topics relocated strictly to footer below keywords.
3. Author metadata in header with circular avatar, no duplicate bottom author card.
4. Action Rail unified with feed card controls (16x16 SVG icons, like, score, bookmark, share).
5. TOC and Action Rail sticky synchronization (--reader-sticky-offset).
6. Comment Composer click-away/escape collapse and draft preservation.
7. Related articles 2-column grid placed before comments with human-readable Russian topics.
8. Cover crop and focal point consistency (780:350, dynamic object-position).
9. Responsive layout and bottom navigation.
10. Code cleanliness: zero emojis, zero em dashes.
"""

import os
import re
import unittest


class TestIssue114ReaderFinalPolishRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.frontend_dir = os.path.join(cls.root_dir, "frontend", "public")

        with open(os.path.join(cls.frontend_dir, "article.html"), "r", encoding="utf-8") as f:
            cls.article_html = f.read()

        with open(os.path.join(cls.frontend_dir, "css", "article.css"), "r", encoding="utf-8") as f:
            cls.article_css = f.read()

        with open(os.path.join(cls.frontend_dir, "js", "article.js"), "r", encoding="utf-8") as f:
            cls.article_js = f.read()

        with open(os.path.join(cls.frontend_dir, "js", "card.js"), "r", encoding="utf-8") as f:
            cls.card_js = f.read()

        with open(os.path.join(cls.frontend_dir, "js", "publication.js"), "r", encoding="utf-8") as f:
            cls.publication_js = f.read()

    def test_geometry_unification_no_pills(self):
        """Ensure no pill/capsule radius (9999px / --radius-full) on non-avatar controls."""
        # No 9999px in article.css
        self.assertNotIn("9999px", self.article_css)
        self.assertNotIn("--radius-full", self.article_css)

        # Standard radius tokens used
        self.assertIn("var(--radius-sm", self.article_css)
        self.assertIn("var(--radius-md", self.article_css)

    def test_topics_relocated_to_footer_below_keywords(self):
        """Verify topics are strictly rendered in footer below keywords, not in header."""
        # Header badges container must be hidden or empty
        self.assertIn('id="articleBadges"', self.article_html)

        # Footer taxonomies structure
        kw_idx = self.article_html.find('id="articleTagsWrap"')
        top_idx = self.article_html.find('id="articleTopicsWrap"')
        self.assertNotEqual(kw_idx, -1)
        self.assertNotEqual(top_idx, -1)
        self.assertLess(kw_idx, top_idx, "Keywords container must precede Topics container in footer")

        # article.js renders topic chips with feed link
        self.assertIn('feed.html?topic=', self.article_js)
        self.assertIn('feed.html?search=', self.article_js)
        self.assertIn('article-topic-item', self.article_js)
        self.assertIn('article-tag-item', self.article_js)

    def test_author_meta_and_removal_of_bottom_card(self):
        """Verify single author meta in header and complete absence of bottom duplicate author card."""
        # Header avatar circle and name
        self.assertIn('article-author-avatar', self.article_html)
        self.assertIn('id="articleAuthorAvatar"', self.article_html)
        self.assertIn('id="articleAuthorName"', self.article_html)
        self.assertIn('id="btnSubscribeAuthor"', self.article_html)

        # No bottom duplicate author card in HTML
        self.assertNotIn('id="articleAuthorBottomCard"', self.article_html)
        self.assertNotIn('article-author-bottom-card', self.article_html)

    def test_action_rail_controls_unification(self):
        """Verify action rail icons (16x16), like, rating, bookmark, comments, share."""
        # Standard SVG size in action rail
        self.assertIn('width="16" height="16"', self.article_html)

        # Separate like and rating controls
        self.assertIn('id="railBtnLike"', self.article_html)
        self.assertIn('id="railArticleVote"', self.article_html)

        # Bookmark, comments, share
        self.assertIn('id="railBtnBookmark"', self.article_html)
        self.assertIn('id="railBtnComments"', self.article_html)
        self.assertIn('id="railBtnShare"', self.article_html)

    def test_sticky_toc_and_rail_synchronization(self):
        """Verify TOC and Rail share sticky offset and viewport max-height constraint."""
        self.assertIn('--reader-sticky-offset: calc(var(--header-height, 60px) + 24px);', self.article_css)
        self.assertIn('top: var(--reader-sticky-offset', self.article_css)
        self.assertIn('max-height: calc(100vh - var(--reader-sticky-offset', self.article_css)
        self.assertIn('overflow-y: auto;', self.article_css)

    def test_comment_composer_click_away_and_draft_persistence(self):
        """Verify click outside collapses composer and preserves draft in sessionStorage."""
        self.assertIn('pointerdown', self.article_js)
        self.assertIn('sessionStorage.setItem', self.article_js)
        self.assertIn('sessionStorage.getItem', self.article_js)
        self.assertIn('has-draft', self.article_js)
        self.assertNotIn('window.confirm', self.article_js)

    def test_related_articles_before_comments_and_two_columns(self):
        """Verify related articles section precedes comments and uses 2 columns on desktop."""
        rel_idx = self.article_html.find('id="relatedArticlesSection"')
        comm_idx = self.article_html.find('id="commentsSection"')
        self.assertNotEqual(rel_idx, -1)
        self.assertNotEqual(comm_idx, -1)
        self.assertLess(rel_idx, comm_idx, "Related articles section must precede comments section")

        # 2-column grid in CSS
        self.assertIn('grid-template-columns: repeat(2, 1fr);', self.article_css)

        # Human-readable Russian topics mapped via PublicationConfig
        self.assertIn('PublicationConfig.getTopicById', self.article_js)

    def test_cover_crop_and_focal_point_sync(self):
        """Verify cover aspect ratio 780:350 and dynamic object-position."""
        self.assertIn('aspect-ratio: 780 / 350;', self.article_css)
        self.assertIn('coverImg.style.objectPosition', self.article_js)
        self.assertIn('style="object-position: ', self.card_js)
        self.assertIn('this.coverPosition =', self.publication_js)

    def test_responsive_layout_breakpoints(self):
        """Verify media queries for desktop, tablet, and mobile."""
        self.assertIn('@media (min-width: 1200px)', self.article_css)
        self.assertIn('@media (min-width: 768px) and (max-width: 1199px)', self.article_css)
        self.assertIn('@media (max-width: 767px)', self.article_css)

    def test_bottom_navigation_return_to_feed(self):
        """Verify return to feed navigation button in reader footer."""
        self.assertIn('id="btnBackToFeedBottom"', self.article_html)
        self.assertIn('article-bottom-nav', self.article_html)
        self.assertIn('btnBackToFeedBottom', self.article_js)

    def test_zero_emojis_and_em_dashes_in_reader_bundle(self):
        """Verify zero emojis and zero em dashes in reader frontend code."""
        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]", flags=re.UNICODE)
        for name, content in [
            ("article.html", self.article_html),
            ("article.css", self.article_css),
            ("article.js", self.article_js),
            ("card.js", self.card_js),
            ("publication.js", self.publication_js)
        ]:
            self.assertFalse("\u2014" in content, f"Em dash found in {name}")
            emojis = emoji_pattern.findall(content)
            self.assertEqual(len(emojis), 0, f"Emojis found in {name}: {emojis}")


if __name__ == "__main__":
    unittest.main()
