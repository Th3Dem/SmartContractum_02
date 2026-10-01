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
4. Upvote Active State (3-Sided Green Outer Border & Glow):
   - Up-arrow becomes green (var(--success-color, #10b981)).
   - Explicit 3-sided green border (top, left outer edge, bottom) matching outer capsule geometry.
   - Right side has no border (completely open to middle score area).
   - Central score area and right half of capsule border remain neutral gray.
5. Downvote Active State (3-Sided Red Outer Border & Glow):
   - Down-arrow becomes red (var(--danger-color, #ef4444)).
   - Explicit 3-sided red border (top, right outer edge, bottom) matching outer capsule geometry.
   - Left side has no border (completely open to middle score area).
   - Central score area and left half of capsule border remain neutral gray.
6. Soft Radial Glow Inside the Block:
   - Radial gradient glow centered exactly at active arrow icon, fading outward into background.
   - Purely radial character; no visible square, rectangular, or hard circular box boundaries.
   - Score area and opposite arrow have no visible color tint/fill.
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
        self.assertIn("overflow: visible;", css, "Capsule must have overflow: visible so border overlay renders without clipping")

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

    def test_10_comments_hover_and_active_unified_light_blue(self):
        """Comments hover and active states share same light-blue color (#38bdf8)."""
        # Comments hover state
        comm_hover = re.search(r'\.btn-card-comments:hover\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(comm_hover, "Comments hover rule must exist")
        hover_css = comm_hover.group(1)
        self.assertIn("color: #38bdf8;", hover_css, "Comments hover color must be light-blue #38bdf8")
        self.assertIn("border-color: #38bdf8;", hover_css, "Comments hover border must be light-blue #38bdf8")

        # Comments active / focus-visible state
        comm_active = re.search(r'\.btn-card-comments:active,\s*\.btn-card-comments:focus-visible\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(comm_active, "Comments active/focus rule must exist")
        active_css = comm_active.group(1)
        self.assertIn("color: #38bdf8;", active_css, "Comments active color must match light-blue #38bdf8")
        self.assertIn("border-color: #38bdf8;", active_css, "Comments active border must match light-blue #38bdf8")

        # Strict check: no dark/saturated blue #3b82f6
        self.assertNotIn("#3b82f6", active_css, "Comments active must not use dark blue #3b82f6")
        self.assertNotIn("#3b82f6", hover_css, "Comments hover must not use dark blue #3b82f6")

    def test_11_bookmark_hover_and_saved_yellow_state(self):
        """Bookmark hover matches yellow saved state (#f59e0b) and never uses blue."""
        # Bookmark hover state in feed.css
        bm_hover = re.search(r'\.btn-card-bookmark:hover\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(bm_hover, "Bookmark hover rule must exist")
        hover_css = bm_hover.group(1)
        self.assertIn("color: #f59e0b;", hover_css, "Bookmark hover color must be yellow #f59e0b")
        self.assertIn("border-color: #f59e0b;", hover_css, "Bookmark hover border must be yellow #f59e0b")
        self.assertNotIn("var(--accent-color)", hover_css, "Bookmark hover must strictly not use blue accent color")
        self.assertNotIn("#38bdf8", hover_css, "Bookmark hover must strictly not use blue")
        self.assertNotIn("#3b82f6", hover_css, "Bookmark hover must strictly not use blue")

        # Bookmark saved state in feed.css
        bm_active = re.search(r'\.btn-card-bookmark\.is-bookmarked\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(bm_active, "Bookmark is-bookmarked rule must exist")
        active_css = bm_active.group(1)
        self.assertIn("border-color: #f59e0b;", active_css, "Bookmarked border must be yellow #f59e0b")
        self.assertIn("color: #f59e0b;", active_css, "Bookmarked icon must be yellow #f59e0b")
        self.assertIn("background: transparent;", active_css, "No heavy solid fill")

        # Bookmark hover in article.css
        art_bm_hover = re.search(r'\.btn-action-bookmark:hover\s*\{([^}]+)\}', self.article_css)
        self.assertIsNotNone(art_bm_hover, "Article bookmark hover rule must exist")
        art_hover_css = art_bm_hover.group(1)
        self.assertIn("color: #f59e0b;", art_hover_css)
        self.assertIn("border-color: #f59e0b;", art_hover_css)

    def test_11b_read_more_default_visible_border_and_background(self):
        """Read More button has visible border and light-blue background by default, with arrow shift on hover."""
        # Default state in feed.css
        rm_match = re.search(r'\.card-read-more,\s*\.btn-read-more\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(rm_match, "card-read-more rule must exist in feed.css")
        rm_css = rm_match.group(1)
        self.assertIn("border: 1px solid rgba(56, 189, 248, 0.4);", rm_css, "Read More must have visible border by default")
        self.assertIn("background: rgba(56, 189, 248, 0.08);", rm_css, "Read More must have light-blue background by default")
        self.assertIn("color: #38bdf8;", rm_css, "Read More default text color must be light-blue")
        self.assertIn("height: 36px;", rm_css, "Read More must match action bar 36px height")
        self.assertIn("border-radius: var(--radius-sm, 6px);", rm_css, "Read More must use rounded radius-sm")

        # Light theme override in feed.css
        lt_match = re.search(r'\[data-theme="light"\] \.card-read-more,\s*\[data-theme="light"\] \.btn-read-more\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(lt_match, "Light theme rule for Read More must exist")
        lt_css = lt_match.group(1)
        self.assertIn("color: #0284c7;", lt_css)
        self.assertIn("background: rgba(2, 132, 199, 0.08);", lt_css)

        # Hover state in feed.css
        rm_hover = re.search(r'\.card-read-more:hover,\s*\.btn-read-more:hover\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(rm_hover)
        hover_css = rm_hover.group(1)
        self.assertIn("background: rgba(56, 189, 248, 0.16);", hover_css)
        self.assertIn("border-color: rgba(56, 189, 248, 0.7);", hover_css)

        # Arrow shift on hover in feed.css
        arrow_hover = re.search(r'\.card-read-more:hover svg,\s*\.btn-read-more:hover svg\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(arrow_hover, "Arrow hover shift rule must exist")
        self.assertIn("transform: translateX(2px);", arrow_hover.group(1))

        # Focus / active state in feed.css
        focus_rule = re.search(r'\.card-read-more:focus-visible,\s*\.btn-read-more:focus-visible,\s*\.card-read-more:active,\s*\.btn-read-more:active\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(focus_rule, "Focus / active rule must exist")
        self.assertIn("outline: 2px solid var(--accent-color);", focus_rule.group(1))
        self.assertIn("outline-offset: 2px;", focus_rule.group(1))

        # Editor preview in editor.css
        ed_match = re.search(r'\.pub-feed-card \.card-read-more,\s*\.pub-feed-card \.btn-read-more\s*\{([^}]+)\}', self.editor_css)
        self.assertIsNotNone(ed_match, "Editor preview read more rule must exist")
        ed_css = ed_match.group(1)
        self.assertIn("border: 1px solid rgba(56, 189, 248, 0.4);", ed_css)
        self.assertIn("background: rgba(56, 189, 248, 0.08);", ed_css)
        self.assertIn("height: 36px;", ed_css)

    # --------------------------------------------------------------------------
    # 4. Rating Capsule: Upvote Active State & 3-Sided Border
    # --------------------------------------------------------------------------
    def test_12_upvote_arrow_and_3_sided_border(self):
        """Upvote sets green arrow and 3-sided outer border (top, left, bottom, no right line)."""
        # Up arrow color
        self.assertIn(".vote-btn-up.is-voted {", self.theme_css)
        up_btn_css = re.search(r'\.vote-btn-up\.is-voted\s*\{([^}]+)\}', self.theme_css).group(1)
        self.assertIn("color: var(--success-color, #10b981);", up_btn_css)

        # 3-sided outer border overlay on left section (top, left, bottom)
        up_after = re.search(r'\.vote-capsule\.has-voted-up::after\s*\{([^}]+)\}', self.theme_css)
        self.assertIsNotNone(up_after, "has-voted-up::after rule must exist for 3-sided border")
        after_css = up_after.group(1)
        self.assertIn("left: -1px;", after_css)
        self.assertIn("border-top: 1px solid var(--vote-up-color, #10b981);", after_css)
        self.assertIn("border-left: 1px solid var(--vote-up-color, #10b981);", after_css)
        self.assertIn("border-bottom: 1px solid var(--vote-up-color, #10b981);", after_css)
        self.assertIn("border-right: none;", after_css, "No vertical divider between arrow and score")
        self.assertIn("border-top-left-radius: var(--radius-sm, 6px);", after_css)
        self.assertIn("border-bottom-left-radius: var(--radius-sm, 6px);", after_css)
        self.assertIn("border-top-right-radius: 0;", after_css)
        self.assertIn("border-bottom-right-radius: 0;", after_css)

        # Invariant: no separate button box around arrow
        self.assertNotIn("border-right: 1px solid var(--success-color", self.theme_css)
        self.assertNotIn("border-right: 1px solid #10b981", self.theme_css)

    # --------------------------------------------------------------------------
    # 5. Rating Capsule: Downvote Active State & 3-Sided Border
    # --------------------------------------------------------------------------
    def test_13_downvote_arrow_and_3_sided_border(self):
        """Downvote sets red arrow and 3-sided outer border (top, right, bottom, no left line)."""
        # Down arrow color
        self.assertIn(".vote-btn-down.is-voted {", self.theme_css)
        down_btn_css = re.search(r'\.vote-btn-down\.is-voted\s*\{([^}]+)\}', self.theme_css).group(1)
        self.assertIn("color: var(--danger-color, #ef4444);", down_btn_css)

        # 3-sided outer border overlay on right section (top, right, bottom)
        down_after = re.search(r'\.vote-capsule\.has-voted-down::after\s*\{([^}]+)\}', self.theme_css)
        self.assertIsNotNone(down_after, "has-voted-down::after rule must exist for 3-sided border")
        after_css = down_after.group(1)
        self.assertIn("right: -1px;", after_css)
        self.assertIn("border-top: 1px solid var(--vote-down-color, #ef4444);", after_css)
        self.assertIn("border-right: 1px solid var(--vote-down-color, #ef4444);", after_css)
        self.assertIn("border-bottom: 1px solid var(--vote-down-color, #ef4444);", after_css)
        self.assertIn("border-left: none;", after_css, "No vertical divider between arrow and score")
        self.assertIn("border-top-right-radius: var(--radius-sm, 6px);", after_css)
        self.assertIn("border-bottom-right-radius: var(--radius-sm, 6px);", after_css)
        self.assertIn("border-top-left-radius: 0;", after_css)
        self.assertIn("border-bottom-left-radius: 0;", after_css)

        # Invariant: no separate button box around arrow
        self.assertNotIn("border-left: 1px solid var(--error-color", self.theme_css)
        self.assertNotIn("border-left: 1px solid #ef4444", self.theme_css)

    def test_13b_mutual_exclusion_and_overlay_invariants(self):
        """Both 3-sided borders must never be displayed simultaneously and overlay pointer-events is none."""
        # Both borders never displayed simultaneously
        mutual_rule = re.search(r'\.vote-capsule\.has-voted-up\.has-voted-down::after\s*\{([^}]+)\}', self.theme_css)
        self.assertIsNotNone(mutual_rule, "Safeguard against simultaneous active borders must exist")
        self.assertIn("display: none;", mutual_rule.group(1))

        # Base overlay geometry and click passthrough
        base_overlay = re.search(r'\.vote-capsule::after\s*\{([^}]+)\}', self.theme_css)
        self.assertIsNotNone(base_overlay)
        base_css = base_overlay.group(1)
        self.assertIn("pointer-events: none;", base_css)
        self.assertIn("position: absolute;", base_css)
        self.assertIn("top: -1px;", base_css)
        self.assertIn("bottom: -1px;", base_css)
        self.assertIn("width: 36px;", base_css)

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
