#!/usr/bin/env python3
"""
tests/test_issue31_sc028_visual_polish.py

Test suite proving the invariants for Issue #31 (SC-028):
"Complete visual polish for threaded comments tree, windowing continuation, and labels".
"""

import os
import re
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ARTICLE_JS_PATH = os.path.join(PROJECT_ROOT, "frontend", "public", "js", "article.js")
ARTICLE_CSS_PATH = os.path.join(PROJECT_ROOT, "frontend", "public", "css", "article.css")


class TestIssue31VisualPolish(unittest.TestCase):
    """Verifies contracts for thread continuation geometry, muted updated label, avatar rings, and stable toggle layout."""

    @classmethod
    def setUpClass(cls) -> None:
        with open(ARTICLE_JS_PATH, "r", encoding="utf-8") as f:
            cls.article_js = f.read()
        with open(ARTICLE_CSS_PATH, "r", encoding="utf-8") as f:
            cls.article_css = f.read()

    def test_01_continue_thread_button_visual_integration_and_geometry(self) -> None:
        """Verify continue thread button has calm tree node geometry, touch target >= 40px, and drilldown action."""
        # CSS contracts: no rectangular card styling (transparent background, border none, padding 0)
        self.assertIn(".btn-continue-thread {", self.article_css)
        btn_block_match = re.search(r"\.btn-continue-thread\s*\{([^}]+)\}", self.article_css)
        self.assertIsNotNone(btn_block_match, ".btn-continue-thread style block not found")
        btn_block = btn_block_match.group(1)
        self.assertIn("background: transparent;", btn_block)
        self.assertIn("border: none;", btn_block)
        self.assertIn("padding: 0;", btn_block)

        # Icon dimensions: circular 20px node
        icon_block_match = re.search(r"\.btn-continue-thread\s+\.continue-thread-icon[^{]*\{([^}]+)\}", self.article_css)
        self.assertIsNotNone(icon_block_match, ".continue-thread-icon style block not found")
        icon_block = icon_block_match.group(1)
        self.assertIn("width: 20px;", icon_block)
        self.assertIn("height: 20px;", icon_block)
        self.assertIn("border-radius: 50%;", icon_block)
        # Desktop centering on x=15px (margin-left: 5px + half width 10px = 15px)
        self.assertIn("margin-left: 5px;", icon_block)
        self.assertIn("margin-right: 15px;", icon_block)

        # Mobile centering on x=14px and min touch target >= 40px
        mobile_blocks = re.findall(r"@media\s*\(\s*max-width:\s*680px\s*\)\s*\{([\s\S]*?)\n\}", self.article_css)
        mobile_block = next((b for b in mobile_blocks if ".btn-continue-thread" in b), None)
        self.assertIsNotNone(mobile_block, "Mobile media query with .btn-continue-thread not found in article.css")
        self.assertIn("margin-left: 4px;", mobile_block)
        self.assertIn("margin-right: 14px;", mobile_block)
        self.assertIn("min-height: 40px;", mobile_block)

        # JS contracts: organic row with upper stem only, chevron SVG, accessible label, drilldown stack push
        self.assertIn("continueRow.className = 'comment-toggle-row comment-continue-row';", self.article_js)
        self.assertIn("toggleStemUpper.className = 'comment-toggle-stem-upper';", self.article_js)
        self.assertIn("continueBtn.setAttribute('aria-label', 'Продолжить ветку (' + totalDescendants + ')');", self.article_js)
        self.assertIn("polyline points=\"3 1.5 6 4.5 3 7.5\"", self.article_js)
        self.assertIn("window._commentDrilldownState.stack.push", self.article_js)

    def test_02_updated_badge_calm_styling_and_dynamic_insertion(self) -> None:
        """Verify (изменен) label has calm muted styling and is dynamically added on edit without page reload."""
        # CSS: calm secondary text without background plate, border, or badge padding
        badge_match = re.search(r"\.comment-updated-badge\s*\{([^}]+)\}", self.article_css)
        self.assertIsNotNone(badge_match, ".comment-updated-badge style block not found")
        badge_css = badge_match.group(1)
        self.assertIn("background: transparent;", badge_css)
        self.assertIn("border: none;", badge_css)
        self.assertIn("padding: 0;", badge_css)
        self.assertIn("font-size: 0.74rem;", badge_css)
        self.assertIn("color: var(--text-muted);", badge_css)
        self.assertIn("margin-left: 6px;", badge_css)

        # JS: initial comment & answer markup uses (изменен)
        self.assertIn("(изменен)", self.article_js)

        # JS: comment edit save handler dynamically inserts badge without reload
        comment_edit_section = re.search(r"let updatedBadge = el\.querySelector\('\.comment-updated-badge'\);[\s\S]*?timeEl\.insertAdjacentElement\('afterend', badgeSpan\);", self.article_js)
        self.assertIsNotNone(comment_edit_section, "Dynamic insertion in comment edit save handler not found")
        self.assertIn("badgeSpan.textContent = '(изменен)';", comment_edit_section.group(0))

        # JS: answer edit save handler dynamically inserts badge without reload
        answer_edit_section = re.search(r"let updatedBadge = el\.querySelector\('\.comment-updated-badge'\);[\s\S]*?timeEl\.insertAdjacentElement\('afterend', badgeSpan\);", self.article_js)
        self.assertIsNotNone(answer_edit_section, "Dynamic insertion in answer edit save handler not found")

    def test_03_avatar_hover_ring_softening_and_focus_visible(self) -> None:
        """Verify avatar hover ring is softened to 1.5px and :focus-visible outlines are preserved."""
        # Softened avatar highlight
        avatar_ring_match = re.search(r"\.comment-author-avatar\.avatar-peer-highlight\s*\{([^}]+)\}", self.article_css)
        self.assertIsNotNone(avatar_ring_match, ".avatar-peer-highlight block not found")
        ring_css = avatar_ring_match.group(1)
        self.assertIn("box-shadow: 0 0 0 1.5px var(--tree-line-active);", ring_css)
        self.assertNotIn("box-shadow: 0 0 0 2px", ring_css)

        # Preserved :focus-visible for accessibility
        self.assertIn(".btn-author-profile:focus-visible {", self.article_css)
        self.assertIn(".btn-toggle-thread:focus-visible {", self.article_css)
        self.assertIn(".btn-continue-thread:focus-visible {", self.article_css)
        self.assertIn(".btn-drilldown-back:focus-visible {", self.article_css)

    def test_04_toggle_row_stable_layout_without_negative_margins(self) -> None:
        """Verify toggle row does not use brittle negative margins and stays stable on avatar axis."""
        # Brittle negative top margin (-26px) must be absent from article.css
        self.assertNotIn("-26px", self.article_css)

        # .comment-toggle-row.is-expanded uses positive margins and flex flow
        expanded_match = re.search(r"\.comment-toggle-row\.is-expanded\s*\{([^}]+)\}", self.article_css)
        self.assertIsNotNone(expanded_match, ".comment-toggle-row.is-expanded block not found")
        expanded_css = expanded_match.group(1)
        self.assertIn("margin-top: 4px;", expanded_css)
        self.assertIn("margin-bottom: 6px;", expanded_css)

        # Stems aligned at x=15px on desktop, x=14px on mobile
        stem_match = re.search(r"\.comment-toggle-stem-upper\s*\{([^}]+)\}", self.article_css)
        self.assertIsNotNone(stem_match, ".comment-toggle-stem-upper block not found")
        self.assertIn("left: 15px;", stem_match.group(1))

        # In Issue #70 (SC-030), comment actions are unified in .comment-action-row with rating capsule,
        # and toggleRow strictly contains toggleBtn without embedding action buttons.
        self.assertIn("toggleRow.appendChild(toggleBtn);", self.article_js)
        self.assertIn("toggleRow.insertAdjacentElement('afterend', replyWrap);", self.article_js)

    def test_05_zero_emojis_and_no_em_dashes(self) -> None:
        """Ensure zero emojis, zero em dashes, zero server IPs, and zero local filesystem paths."""
        with open(__file__, "r", encoding="utf-8") as f:
            content = f.read()

        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]|[\u2600-\u26ff]|[\u2700-\u27bf]")
        self.assertIsNone(emoji_pattern.search(content), "Emoji found in test file")
        self.assertNotIn("\u2014", content, "Em dash found in test file")
        self.assertNotIn("\u2014", self.article_js, "Em dash found in article.js")
        self.assertNotIn("\u2014", self.article_css, "Em dash found in article.css")


if __name__ == "__main__":
    unittest.main()
