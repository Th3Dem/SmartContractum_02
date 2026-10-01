#!/usr/bin/env python3
"""
tests/test_issue62_sc028_action_bar_and_vote_capsule.py

Comprehensive contract and regression test suite for Issue #62 (SC-028):
"Redesign action bar and voting capsule".

Acceptance Criteria verified:
1. Composition and Geometry of the Action Bar:
   - Order: Like -> Rating -> Comments -> Bookmark.
   - All 4 elements get a thin border visible immediately without hover (1px solid var(--border-color)).
   - All 4 elements must have identical height (36px) and matching border-radius (var(--radius-sm, 6px)).
   - Like, Comments, and Bookmark buttons are compact squares (aspect-ratio 1:1, width = height, 36px x 36px).
   - Rating capsule has width of 3 square buttons (3:1 ratio, 108px x 36px) with 3 equal zones inside (36px each):
     upvote arrow, score number, downvote arrow.
   - Icon sizes (~16px), centered.
   - Like and Comments counters placed inside frame with icon, no clipping for multi-digit numbers.
2. Like, Comments, Bookmark Frames and States:
   - Like: default neutral gray border; when liked, border turns red and heart turns red; no heavy solid fill.
   - Comments: default neutral gray border; on active/focus-visible, blue border response; navigates to discussion.
   - Bookmark: default neutral gray border; when bookmarked, border and icon turn amber/yellow; no heavy solid fill.
3. Rating Capsule Shape & Geometry:
   - Single horizontal rectangle with slight rounding: Up-arrow - score - Down-arrow.
   - Outer border continuous around entire capsule; no internal vertical dividing lines.
   - Arrows: slightly thicker, saturated silhouette in neutral gray by default.
4. Upvote Active State (Left Outer Border Highlight & Glow):
   - Up-arrow becomes green (var(--success-color, #10b981)).
   - Green highlight on nearest outer border section ONLY (left border, curves, fading toward center via mask).
   - Central score area and right half of capsule border remain neutral gray.
   - No vertical green line to the right of up-arrow.
5. Downvote Active State (Right Outer Border Highlight & Glow):
   - Down-arrow becomes red (var(--error-color, #ef4444)).
   - Red highlight on nearest outer border section ONLY (right border, curves, fading toward center via mask).
   - Central score area and left half of capsule border remain neutral gray.
   - No vertical red line to the left of down-arrow.
6. Soft Radial Glow Inside the Block:
   - Radial gradient glow centered exactly at active arrow icon, fading outward into background.
   - Purely radial character; no visible square, rectangular, or hard circular box boundaries.
   - Score area and opposite arrow have no visible color tint/fill.
   - Glow remains inside capsule (overflow: hidden).
   - Decorative layers have pointer-events: none.
7. Score Number and Independence:
   - Total score color depends only on score value (positive green, negative red, zero gray).
   - User vote indicates personal voice independent from score sign.
   - Respects prefers-reduced-motion.
8. Applied across feed cards, questions, article page reactions, comments/answers, editor preview.
9. Zero emojis, zero em dashes, 100% offline-first.
"""

import os
import re
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


def read_file(relative_path: str) -> str:
    full_path = os.path.join(PROJECT_ROOT, relative_path)
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()


class TestIssue62ActionBarAndVoteCapsule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.theme_css = read_file("frontend/public/css/theme.css")
        cls.feed_css = read_file("frontend/public/css/feed.css")
        cls.article_css = read_file("frontend/public/css/article.css")
        cls.editor_css = read_file("frontend/public/css/editor.css")
        cls.card_js = read_file("frontend/public/js/card.js")
        cls.votes_js = read_file("frontend/public/js/votes.js")
        cls.article_js = read_file("frontend/public/js/article.js")
        cls.article_html = read_file("frontend/public/article.html")
        cls.editor_html = read_file("frontend/public/editor.html")
        cls.feed_html = read_file("frontend/public/feed.html")

    # --------------------------------------------------------------------------
    # 1. Composition and Order: Like -> Rating -> Comments/Answers -> Bookmark
    # --------------------------------------------------------------------------
    def test_01_action_bar_order_feed_cards_and_questions(self):
        """Action bar order in card.js must be Like -> Rating -> Comments -> Bookmark."""
        # Regular article card left footer assembly
        self.assertIn(
            "footerLeftHtml = likeBtnHtml + voteCapsuleHtml + commentsBtnHtml + bookmarkHtml;",
            self.card_js,
            "Feed card actions order must be Like -> Rating -> Comments -> Bookmark"
        )
        # Question card left footer assembly
        self.assertIn(
            "footerLeftHtml = likeBtnHtml + voteCapsuleHtml + answersBtnHtml + bookmarkHtml;",
            self.card_js,
            "Question card actions order must be Like -> Rating -> Answers -> Bookmark"
        )

    def test_02_action_bar_order_article_page(self):
        """Action bar on article page must preserve Like -> Rating -> Bookmark order."""
        # Top actions in article.html
        like_pos = self.article_html.find('id="btnArticleLike"')
        vote_pos = self.article_html.find('id="voteArticleTop"')
        bm_pos = self.article_html.find('id="btnArticleBookmark"')
        self.assertNotEqual(like_pos, -1, "btnArticleLike must exist")
        self.assertNotEqual(vote_pos, -1, "voteArticleTop must exist")
        self.assertNotEqual(bm_pos, -1, "btnArticleBookmark must exist")
        self.assertTrue(like_pos < vote_pos < bm_pos, "Article top actions order must be Like -> Rating -> Bookmark")

        # Bottom actions in article.html
        like_bot_pos = self.article_html.find('id="btnArticleLikeBottom"')
        vote_bot_pos = self.article_html.find('id="voteArticleBottom"')
        bm_bot_pos = self.article_html.find('id="btnArticleBookmarkBottom"')
        self.assertNotEqual(like_bot_pos, -1, "btnArticleLikeBottom must exist")
        self.assertNotEqual(vote_bot_pos, -1, "voteArticleBottom must exist")
        self.assertNotEqual(bm_bot_pos, -1, "btnArticleBookmarkBottom must exist")
        self.assertTrue(like_bot_pos < vote_bot_pos < bm_bot_pos, "Article bottom actions order must be Like -> Rating -> Bookmark")

    def test_03_action_bar_order_editor_preview(self):
        """Editor preview card must match feed card order: Like -> Rating -> Comments -> Bookmark."""
        like_pos = self.editor_html.find('id="preview-card-like"')
        vote_pos = self.editor_html.find('id="preview-card-vote-capsule"')
        comm_pos = self.editor_html.find('id="preview-card-comments"')
        bm_pos = self.editor_html.find('id="preview-card-bookmark"')
        self.assertNotEqual(like_pos, -1, "preview-card-like must exist")
        self.assertNotEqual(vote_pos, -1, "preview-card-vote-capsule must exist")
        self.assertNotEqual(comm_pos, -1, "preview-card-comments must exist")
        self.assertNotEqual(bm_pos, -1, "preview-card-bookmark must exist")
        self.assertTrue(
            like_pos < vote_pos < comm_pos < bm_pos,
            "Editor preview card footer order must be Like -> Rating -> Comments -> Bookmark"
        )

    # --------------------------------------------------------------------------
    # 2. Geometry: 36px height, 1px border, 1:1 squares, 3:1 rating capsule
    # --------------------------------------------------------------------------
    def test_04_rating_capsule_3_to_1_geometry(self):
        """Rating capsule must have 3:1 ratio (108px x 36px) and matching 6px border-radius."""
        capsule_match = re.search(r'\.vote-capsule\s*\{([^}]+)\}', self.theme_css)
        self.assertIsNotNone(capsule_match, ".vote-capsule rule must exist in theme.css")
        css = capsule_match.group(1)
        self.assertIn("height: 36px;", css, "Capsule must have 36px height")
        self.assertIn("min-height: 36px;", css, "Capsule must have min-height: 36px")
        self.assertIn("width: 108px;", css, "Capsule must have 108px width (3 * 36px)")
        self.assertIn("min-width: 108px;", css, "Capsule must have min-width: 108px")
        self.assertIn("aspect-ratio: 3 / 1;", css, "Capsule must declare 3:1 aspect ratio")
        self.assertIn("border: 1px solid var(--border-color);", css, "Capsule must have 1px solid border")
        self.assertIn("border-radius: var(--radius-sm, 6px);", css, "Capsule must have matching radius-sm (6px)")
        self.assertIn("overflow: hidden;", css, "Capsule must have overflow: hidden to contain glow")

    def test_05_rating_capsule_three_equal_zones(self):
        """Inside rating capsule, 3 equal zones of 36px exist: up-button (32+4), score (28+8), down-button (32+4)."""
        # Outer padding and gap
        capsule_match = re.search(r'\.vote-capsule\s*\{([^}]+)\}', self.theme_css)
        capsule_css = capsule_match.group(1)
        self.assertIn("padding: 0 4px;", capsule_css)
        self.assertIn("gap: 4px;", capsule_css)

        # Button width 32px: 4px outer pad + 32px button = 36px zone
        btn_match = re.search(r'\.vote-btn\s*\{([^}]+)\}', self.theme_css)
        btn_css = btn_match.group(1)
        self.assertIn("width: 32px;", btn_css)
        self.assertIn("height: 32px;", btn_css)

        # Score width 28px: 4px gap + 28px score + 4px gap = 36px zone
        score_match = re.search(r'\.vote-score\s*\{([^}]+)\}', self.theme_css)
        score_css = score_match.group(1)
        self.assertIn("width: 28px;", score_css)
        self.assertIn("min-width: 28px;", score_css)

    def test_06_action_buttons_height_and_border_in_feed_css(self):
        """Action buttons in feed.css must have 36px height and 1px border visible immediately."""
        action_match = re.search(r'\.btn-card-action\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(action_match, ".btn-card-action rule must exist in feed.css")
        action_css = action_match.group(1)
        self.assertIn("height: 36px;", action_css)
        self.assertIn("min-height: 36px;", action_css)
        self.assertIn("min-width: 36px;", action_css)
        self.assertIn("border: 1px solid var(--border-color);", action_css)
        self.assertIn("border-radius: var(--radius-sm);", action_css)

    def test_07_bookmark_button_1_to_1_square(self):
        """Bookmark button must be a compact 1:1 square (36px x 36px)."""
        bm_match = re.search(r'\.btn-card-bookmark\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(bm_match, ".btn-card-bookmark rule must exist in feed.css")
        bm_css = bm_match.group(1)
        self.assertIn("width: 36px;", bm_css)
        self.assertIn("height: 36px;", bm_css)
        self.assertIn("min-width: 36px;", bm_css)
        self.assertIn("aspect-ratio: 1 / 1;", bm_css)
        self.assertIn("border: 1px solid var(--border-color);", bm_css)

    def test_08_multi_digit_counters_no_clipping(self):
        """Like and Comments buttons accommodate multi-digit counters without clipping."""
        like_match = re.search(r'\.btn-card-like\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(like_match)
        like_css = like_match.group(1)
        self.assertIn("min-width: 36px;", like_css)
        self.assertIn("height: 36px;", like_css)
        self.assertIn("padding: 0 6px;", like_css)

        comm_match = re.search(r'\.btn-card-comments\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(comm_match)
        comm_css = comm_match.group(1)
        self.assertIn("min-width: 36px;", comm_css)
        self.assertIn("height: 36px;", comm_css)
        self.assertIn("padding: 0 6px;", comm_css)

    # --------------------------------------------------------------------------
    # 3. Like, Comments, Bookmark Frames and States
    # --------------------------------------------------------------------------
    def test_09_like_active_and_default_states(self):
        """Like button turns red on border and icon when liked; reverts to gray on unlike."""
        self.assertIn(".btn-card-like.is-liked {", self.feed_css)
        like_active = re.search(r'\.btn-card-like\.is-liked\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(like_active)
        active_css = like_active.group(1)
        self.assertIn("border-color: #ef4444;", active_css, "Liked border must be red")
        self.assertIn("color: #ef4444;", active_css, "Liked text/icon must be red")
        self.assertIn("background: transparent;", active_css, "No heavy solid fill")

    def test_10_comments_active_click_blue_response(self):
        """Comments button provides blue border response on active/focus-visible."""
        comm_active = re.search(r'\.btn-card-comments:active,\s*\.btn-card-comments:focus-visible\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(comm_active, "Comments active/focus rule must exist")
        active_css = comm_active.group(1)
        self.assertIn("border-color: var(--accent-color, #3b82f6);", active_css)
        self.assertIn("color: var(--accent-color, #3b82f6);", active_css)

    def test_11_bookmark_active_amber_state(self):
        """Bookmark button turns amber/yellow on border and icon when bookmarked."""
        bm_active = re.search(r'\.btn-card-bookmark\.is-bookmarked\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(bm_active)
        active_css = bm_active.group(1)
        self.assertIn("border-color: #f59e0b;", active_css, "Bookmarked border must be amber")
        self.assertIn("color: #f59e0b;", active_css, "Bookmarked icon must be amber")
        self.assertIn("background: transparent;", active_css, "No heavy solid fill")

    # --------------------------------------------------------------------------
    # 4. Rating Capsule: Upvote Active State & Left Outer Border Highlight
    # --------------------------------------------------------------------------
    def test_12_upvote_arrow_and_left_outer_border_highlight(self):
        """Upvote sets green arrow and highlights only left outer border fading to center."""
        # Up arrow color
        self.assertIn(".vote-btn-up.is-voted {", self.theme_css)
        up_btn_css = re.search(r'\.vote-btn-up\.is-voted\s*\{([^}]+)\}', self.theme_css).group(1)
        self.assertIn("color: var(--success-color, #10b981);", up_btn_css)

        # Left outer border highlight via ::after with linear gradient mask
        up_after = re.search(r'\.vote-capsule\.has-voted-up::after\s*\{([^}]+)\}', self.theme_css)
        self.assertIsNotNone(up_after, "has-voted-up::after rule must exist for outer border highlight")
        after_css = up_after.group(1)
        self.assertIn("border: 1px solid var(--success-color, #10b981);", after_css)
        self.assertIn("mask: linear-gradient(to right,", after_css)
        self.assertIn("-webkit-mask: linear-gradient(to right,", after_css)

        # No vertical green divider inside
        self.assertNotIn("border-right: 1px solid var(--success-color", self.theme_css)
        self.assertNotIn("border-right: 1px solid #10b981", self.theme_css)

    # --------------------------------------------------------------------------
    # 5. Rating Capsule: Downvote Active State & Right Outer Border Highlight
    # --------------------------------------------------------------------------
    def test_13_downvote_arrow_and_right_outer_border_highlight(self):
        """Downvote sets red arrow and highlights only right outer border fading to center."""
        # Down arrow color
        self.assertIn(".vote-btn-down.is-voted {", self.theme_css)
        down_btn_css = re.search(r'\.vote-btn-down\.is-voted\s*\{([^}]+)\}', self.theme_css).group(1)
        self.assertIn("color: var(--danger-color, #ef4444);", down_btn_css)

        # Right outer border highlight via ::after with linear gradient mask to left
        down_after = re.search(r'\.vote-capsule\.has-voted-down::after\s*\{([^}]+)\}', self.theme_css)
        self.assertIsNotNone(down_after, "has-voted-down::after rule must exist for outer border highlight")
        after_css = down_after.group(1)
        self.assertIn("border: 1px solid var(--error-color, #ef4444);", after_css)
        self.assertIn("mask: linear-gradient(to left,", after_css)
        self.assertIn("-webkit-mask: linear-gradient(to left,", after_css)

        # No vertical red divider inside
        self.assertNotIn("border-left: 1px solid var(--error-color", self.theme_css)
        self.assertNotIn("border-left: 1px solid #ef4444", self.theme_css)

    # --------------------------------------------------------------------------
    # 6. Soft Radial Glow Inside the Block
    # --------------------------------------------------------------------------
    def test_14_soft_radial_glow_upvote_and_downvote(self):
        """Soft radial glow is centered at active arrow and gently dissolves into background."""
        # Upvote glow centered at left arrow
        glow_up = re.search(r'\.vote-capsule\.has-voted-up::before\s*\{([^}]+)\}', self.theme_css)
        self.assertIsNotNone(glow_up, "has-voted-up::before glow rule must exist")
        up_glow_css = glow_up.group(1)
        self.assertIn("radial-gradient(circle", up_glow_css)
        self.assertIn("at 20px 50%", up_glow_css, "Up glow must be centered at left arrow")
        self.assertIn("rgba(16, 185, 129", up_glow_css)

        # Downvote glow centered at right arrow
        glow_down = re.search(r'\.vote-capsule\.has-voted-down::before\s*\{([^}]+)\}', self.theme_css)
        self.assertIsNotNone(glow_down, "has-voted-down::before glow rule must exist")
        down_glow_css = glow_down.group(1)
        self.assertIn("radial-gradient(circle", down_glow_css)
        self.assertIn("calc(100% - 20px) 50%", down_glow_css, "Down glow must be centered at right arrow")
        self.assertIn("rgba(239, 68, 68", down_glow_css)

        # Decorative layers do not intercept clicks
        before_match = re.search(r'\.vote-capsule::before\s*\{([^}]+)\}', self.theme_css)
        self.assertIn("pointer-events: none;", before_match.group(1))
        after_match = re.search(r'\.vote-capsule::after\s*\{([^}]+)\}', self.theme_css)
        self.assertIn("pointer-events: none;", after_match.group(1))

        # No square background box on button inside capsule
        voted_btn_inside = re.search(r'\.vote-capsule \.vote-btn-up\.is-voted,\s*\.vote-capsule \.vote-btn-down\.is-voted\s*\{([^}]+)\}', self.theme_css)
        self.assertIsNotNone(voted_btn_inside)
        self.assertIn("background: transparent;", voted_btn_inside.group(1))

    # --------------------------------------------------------------------------
    # 7. Score Number and Independence
    # --------------------------------------------------------------------------
    def test_15_score_number_independence_from_user_vote(self):
        """Score number color reflects total sum sign independently from user vote direction."""
        # Positive score is green
        pos_match = re.search(r'\.vote-score\.is-positive\s*\{([^}]+)\}', self.theme_css)
        self.assertIn("var(--success-color, #10b981)", pos_match.group(1))

        # Negative score is red
        neg_match = re.search(r'\.vote-score\.is-negative\s*\{([^}]+)\}', self.theme_css)
        self.assertIn("var(--danger-color, #ef4444)", neg_match.group(1))

        # Zero score is neutral gray
        zero_match = re.search(r'\.vote-score\.is-zero\s*\{([^}]+)\}', self.theme_css)
        self.assertIn("var(--text-secondary)", zero_match.group(1))

    # --------------------------------------------------------------------------
    # 8. Prefers-Reduced-Motion and Accessibility
    # --------------------------------------------------------------------------
    def test_16_prefers_reduced_motion_compliance(self):
        """Transitions are disabled under prefers-reduced-motion: reduce."""
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.theme_css)
        prm_block = self.theme_css[self.theme_css.find("@media (prefers-reduced-motion: reduce)"):]
        self.assertIn(".vote-capsule", prm_block)
        self.assertIn("transition: none !important;", prm_block)

    # --------------------------------------------------------------------------
    # 9. Quality Standards: Zero emojis, Zero em dashes, 100% offline-first
    # --------------------------------------------------------------------------
    def test_17_zero_emojis(self):
        """No emojis in modified frontend source files."""
        emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]', flags=re.UNICODE)
        for content, name in [
            (self.theme_css, "theme.css"),
            (self.feed_css, "feed.css"),
            (self.article_css, "article.css"),
            (self.editor_css, "editor.css"),
            (self.card_js, "card.js"),
            (self.votes_js, "votes.js"),
            (self.editor_html, "editor.html"),
        ]:
            matches = emoji_pattern.findall(content)
            self.assertEqual(len(matches), 0, f"Found emojis in {name}: {matches}")

    def test_18_zero_em_dashes(self):
        """No em dashes (\\u2014) in modified frontend code."""
        em_dash = '\u2014'
        for content, name in [
            (self.theme_css, "theme.css"),
            (self.feed_css, "feed.css"),
            (self.article_css, "article.css"),
            (self.editor_css, "editor.css"),
            (self.card_js, "card.js"),
            (self.votes_js, "votes.js"),
        ]:
            self.assertNotIn(em_dash, content, f"Found em dash in {name}")


if __name__ == "__main__":
    unittest.main()
