#!/usr/bin/env python3
"""
tests/test_issue84_compact_sticky_action_rail.py

Automated test suite for Issue #84:
1. Desktop Sticky Action Rail:
   - In frontend/public/article.html, inside .article-rail-slot (#articleRailSlot), active action rail:
     #articleActionRail with role="toolbar", aria-label="Действия с публикацией".
   - 5 independent action items:
     * Like button with counter (#railBtnLike, .btn-rail-action, #railLikeCount)
     * Vote capsule (#railArticleVote, .rail-vote-wrapper)
     * Divider (.rail-divider)
     * Bookmark button (#railBtnBookmark, .btn-rail-action)
     * Comments button with counter (#railBtnComments, .btn-rail-action, #railCommentsCount)
     * Share button (#railBtnShare, .btn-rail-action)
2. CRITICAL INVARIANT:
   - Like button and Vote capsule are strictly separated and NOT merged.
3. Desktop styling in article.css:
   - .article-action-rail: sticky, top 100px, pill shape 9999px, blur backdrop, shadow.
   - .btn-rail-action: 38-42px rounded buttons, transition, hover background, active fill.
   - Like active state: heart filled with crimson/pink (#e11d48 / #ef4444).
   - Bookmark active state: bookmark filled with accent (#6366f1).
   - .rail-vote-wrapper: vertical capsule layout.
4. Mobile Bottom Action Bar:
   - In article.html: #mobileActionBar with all 5 actions.
   - In article.css: display: none on desktop, display: flex on mobile (< 768px), fixed bottom, height 56px, z-index 990.
5. JavaScript Integration in article.js:
   - Like sync and toggle across desktop, rail, and mobile.
   - Vote capsule sync into #railArticleVote and #mobileArticleVote.
   - Bookmark toggle and sync with sc_bookmarks in localStorage.
   - Comments button smooth scrolls to #commentsSection with scroll-margin-top: 80px.
   - Comments counter sync into #railCommentsCount and #mobileCommentsCount.
   - Share button copies link to clipboard.
6. Invariants:
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


class TestIssue84CompactStickyActionRail(unittest.TestCase):
    """Test suite for desktop sticky action rail and mobile bottom action bar."""

    @classmethod
    def setUpClass(cls):
        cls.article_html = read_file("frontend/public/article.html")
        cls.article_css = read_file("frontend/public/css/article.css")
        cls.article_js = read_file("frontend/public/js/article.js")
        cls.theme_css = read_file("frontend/public/css/theme.css")
        cls.test_file_content = read_file("tests/test_issue84_compact_sticky_action_rail.py")

    def test_01_desktop_action_rail_structure_and_aria(self):
        """Verify presence of all 5 action elements and accessibility in desktop action rail."""
        self.assertIn('id="articleActionRail"', self.article_html)
        self.assertIn('class="article-action-rail"', self.article_html)
        self.assertIn('role="toolbar"', self.article_html)
        self.assertIn('aria-label="Действия с публикацией"', self.article_html)

        # Confirm rail is inside #articleRailSlot
        rail_slot_idx = self.article_html.find('id="articleRailSlot"')
        self.assertNotEqual(rail_slot_idx, -1)
        rail_idx = self.article_html.find('id="articleActionRail"', rail_slot_idx)
        self.assertNotEqual(rail_idx, -1, "articleActionRail must be inside articleRailSlot")

        # 1. Like button with counter
        self.assertIn('id="railBtnLike"', self.article_html)
        self.assertIn('btn-rail-like', self.article_html)
        self.assertIn('id="railLikeCount"', self.article_html)

        # 2. Vote capsule container
        self.assertIn('id="railArticleVote"', self.article_html)
        self.assertIn('class="rail-vote-wrapper"', self.article_html)

        # Divider
        self.assertIn('class="rail-divider"', self.article_html)

        # 3. Bookmark button
        self.assertIn('id="railBtnBookmark"', self.article_html)
        self.assertIn('btn-rail-bookmark', self.article_html)

        # 4. Comments button with counter
        self.assertIn('id="railBtnComments"', self.article_html)
        self.assertIn('btn-rail-comments', self.article_html)
        self.assertIn('id="railCommentsCount"', self.article_html)

        # 5. Share button
        self.assertIn('id="railBtnShare"', self.article_html)
        self.assertIn('btn-rail-share', self.article_html)

    def test_02_strict_separation_between_like_and_vote(self):
        """CRITICAL INVARIANT: Verify Like button and Vote capsule are strictly separated."""
        rail_start = self.article_html.find('id="articleActionRail"')
        rail_end = self.article_html.find('</div>', self.article_html.find('id="railBtnShare"', rail_start))
        rail_block = self.article_html[rail_start:rail_end]

        like_pos = rail_block.find('id="railBtnLike"')
        vote_pos = rail_block.find('id="railArticleVote"')
        self.assertNotEqual(like_pos, -1)
        self.assertNotEqual(vote_pos, -1)
        self.assertNotEqual(like_pos, vote_pos)

        # Verify Like button is not inside Vote container and vice versa
        self.assertNotIn('railArticleVote', rail_block[:like_pos])
        self.assertNotIn('railBtnLike', rail_block[vote_pos:vote_pos + len('<div id="railArticleVote" class="rail-vote-wrapper" aria-label="Рейтинг публикации"></div>')])

        # In article.js, verify like and vote have separate synchronization logic
        self.assertIn("syncLikeButtons", self.article_js)
        self.assertIn("syncArticleVoteCapsules", self.article_js)

    def test_03_desktop_action_rail_styling_in_article_css(self):
        """Verify .article-action-rail, .btn-rail-action, and active states in article.css."""
        rail_match = re.search(r'\.article-action-rail\s*\{([^}]+)\}', self.article_css)
        self.assertIsNotNone(rail_match, ".article-action-rail rule must exist in article.css")
        css_block = rail_match.group(1)

        self.assertIn("position: sticky", css_block)
        self.assertTrue(
            "top: var(--reader-sticky-offset" in css_block or "top: 100px" in css_block,
            "Action rail must have sticky top offset"
        )
        self.assertTrue(
            "border-radius: var(--radius-md" in css_block or "border-radius: 9999px" in css_block,
            "Action rail container must have valid border-radius"
        )
        self.assertIn("var(--surface-1)", css_block)
        self.assertIn("backdrop-filter:", css_block)
        self.assertIn("border: 1px solid var(--border-subtle)", css_block)

        # Button styling
        btn_match = re.search(r'\.btn-rail-action\s*\{([^}]+)\}', self.article_css)
        self.assertIsNotNone(btn_match, ".btn-rail-action rule must exist in article.css")
        btn_block = btn_match.group(1)
        self.assertTrue(
            "border-radius: var(--radius-sm" in btn_block or "border-radius: 9999px" in btn_block,
            "Action rail buttons must have valid border-radius"
        )
        self.assertIn("cursor: pointer", btn_block)
        self.assertIn("transition:", btn_block)

        # Like active state (#e11d48 / #ef4444)
        self.assertTrue(
            "#e11d48" in self.article_css or "#ef4444" in self.article_css,
            "Like active state must style heart with crimson/pink color"
        )
        self.assertIn(".btn-rail-like.is-liked", self.article_css)

        # Bookmark active state (#6366f1)
        self.assertTrue(
            "#6366f1" in self.article_css or "var(--accent)" in self.article_css,
            "Bookmark active state must style bookmark with accent color"
        )
        self.assertIn(".btn-rail-bookmark.is-bookmarked", self.article_css)

        # Vertical vote layout
        self.assertIn(".rail-vote-wrapper", self.article_css)
        self.assertIn("flex-direction: column", self.article_css)

    def test_04_mobile_bottom_action_bar_markup_in_article_html(self):
        """Verify #mobileActionBar exists with all 5 actions."""
        self.assertIn('id="mobileActionBar"', self.article_html)
        self.assertIn('class="mobile-action-bar"', self.article_html)
        self.assertIn('id="mobileBtnLike"', self.article_html)
        self.assertIn('id="mobileLikeCount"', self.article_html)
        self.assertIn('id="mobileArticleVote"', self.article_html)
        self.assertIn('class="mobile-vote-wrapper"', self.article_html)
        self.assertIn('id="mobileBtnBookmark"', self.article_html)
        self.assertIn('id="mobileBtnComments"', self.article_html)
        self.assertIn('id="mobileCommentsCount"', self.article_html)
        self.assertIn('id="mobileBtnShare"', self.article_html)

    def test_05_mobile_bottom_action_bar_styling_and_media_queries(self):
        """Verify mobile action bar is hidden on desktop and fixed at bottom on mobile (< 768px)."""
        desktop_hidden = re.search(r'(#mobileActionBar|\.mobile-action-bar)[^{]*\{[^}]*display:\s*none', self.article_css)
        self.assertIsNotNone(desktop_hidden, "#mobileActionBar must be display: none by default on desktop")

        mobile_query = re.search(r'@media\s*\(\s*max-width:\s*767px\s*\)\s*\{([\s\S]+?)(?=\n@media|\Z)', self.article_css)
        self.assertIsNotNone(mobile_query, "Mobile media query (max-width: 767px) must exist in article.css")
        query_block = mobile_query.group(1)

        self.assertIn("display: flex", query_block)
        self.assertIn("position: fixed", query_block)
        self.assertIn("bottom: 0", query_block)
        self.assertIn("height: 56px", query_block)
        self.assertIn("z-index: 990", query_block)
        self.assertIn("backdrop-filter:", query_block)

    def test_06_like_button_sync_and_toggle_in_article_js(self):
        """Verify syncLikeButtons and toggleArticleLike handle rail and mobile buttons."""
        self.assertIn("railBtnLike", self.article_js)
        self.assertIn("mobileBtnLike", self.article_js)
        self.assertIn("railLikeCount", self.article_js)
        self.assertIn("mobileLikeCount", self.article_js)

        # Verify click listener wiring
        self.assertIn("railBtnLike.addEventListener('click'", self.article_js)
        self.assertIn("mobileBtnLike.addEventListener('click'", self.article_js)

    def test_07_bookmark_button_sync_and_storage_in_article_js(self):
        """Verify bookmark buttons sync with localStorage sc_bookmarks and handle click."""
        self.assertIn("railBtnBookmark", self.article_js)
        self.assertIn("mobileBtnBookmark", self.article_js)
        self.assertIn("sc_bookmarks", self.article_js)
        self.assertIn("is-bookmarked", self.article_js)

        # Verify click listener wiring
        self.assertIn("railBtnBookmark.addEventListener('click'", self.article_js)
        self.assertIn("mobileBtnBookmark.addEventListener('click'", self.article_js)

    def test_08_vote_capsule_rail_and_mobile_sync_in_article_js(self):
        """Verify syncArticleVoteCapsules renders into railArticleVote and mobileArticleVote."""
        self.assertIn("railArticleVote", self.article_js)
        self.assertIn("mobileArticleVote", self.article_js)

        fn_idx = self.article_js.find("function syncArticleVoteCapsules")
        self.assertNotEqual(fn_idx, -1)
        capsule_fn = self.article_js[fn_idx:fn_idx + 1600]
        self.assertIn("railArticleVote", capsule_fn)
        self.assertIn("mobileArticleVote", capsule_fn)

    def test_09_comments_button_smooth_scroll_and_counter_in_article_js(self):
        """Verify comments button smooth scrolls to #commentsSection and counter is synchronized."""
        self.assertIn("railBtnComments", self.article_js)
        self.assertIn("mobileBtnComments", self.article_js)
        self.assertIn("railCommentsCount", self.article_js)
        self.assertIn("mobileCommentsCount", self.article_js)

        # Smooth scrolling targeting commentsSection
        self.assertIn("scrollIntoView", self.article_js)
        self.assertIn("commentsSection", self.article_js)

        # CSS scroll-margin-top
        scroll_margin_match = re.search(r'#commentsSection[^{]*\{[^}]*scroll-margin-top:\s*80px', self.article_css)
        self.assertIsNotNone(scroll_margin_match, "#commentsSection must have scroll-margin-top: 80px in article.css")

    def test_10_zero_emojis_no_em_dashes_offline_first(self):
        """Verify zero emojis, zero em dashes, and 100% offline-first in modified/new files."""
        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]|[\u2600-\u26ff]|[\u2700-\u27bf]")
        files_to_check = [
            (self.test_file_content, "test_issue84_compact_sticky_action_rail.py"),
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
