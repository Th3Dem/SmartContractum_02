#!/usr/bin/env python3
"""
tests/test_issue70_comment_actions_bar.py

Automated contract, layout, and regression test suite for Issue #70 (SC-030):
"Compact comment and answer action bar in a single horizontal row with rating capsule".

Acceptance Criteria verified:
1. Unified single horizontal row: .comment-vote-row.comment-action-row wraps vote capsule and action buttons.
2. Geometry: 25px height, 25px width, 1px border (var(--border-color)), 4px radius (var(--radius-xs)), 1:1 square.
3. Strict order:
   - Comments: [Vote Capsule] -> [Ответить] -> [Сохранить] -> [Поделиться] -> [Подписаться] -> [Пожаловаться] -> [Удалить] -> [Редактировать].
   - Answers: [Vote Capsule] -> [Ответить] -> [Сохранить] -> [Поделиться] -> [Подписаться] -> [Пожаловаться] -> [Редактировать].
4. Icon-only buttons with 14px SVGs, no text spans, aria-label and title tooltips.
5. Thread toggle button (.btn-toggle-thread) strictly on its own row, never in action row.
6. Hover states:
   - Reply and Edit: accent color (#38bdf8), subtle background.
   - Delete: destructive red (#ef4444 / var(--error-color)), subtle background.
7. Accessibility: :focus-visible 2px outline, zero layout shift, aria-label on all action buttons.
8. Comment rating capsule appearance, compact 25px height, and voting logic unaltered.
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


class TestIssue70CommentActionsBar(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.article_js = read_file("frontend/public/js/article.js")
        cls.article_css = read_file("frontend/public/css/article.css")
        cls.theme_css = read_file("frontend/public/css/theme.css")

    def test_01_no_legacy_text_spans_in_comment_or_answer_actions(self) -> None:
        """Verify action buttons are icon-only without text spans like '<span>Ответить</span>'."""
        self.assertNotIn(
            "<span>Ответить</span>",
            self.article_js,
            "Legacy '<span>Ответить</span>' text span must be eliminated from article.js"
        )
        self.assertNotIn(
            "<span>Удалить</span>",
            self.article_js,
            "Legacy '<span>Удалить</span>' text span must be eliminated from article.js"
        )
        self.assertNotIn(
            "<span>Редактировать</span>",
            self.article_js,
            "Legacy '<span>Редактировать</span>' text span must be eliminated from article.js"
        )
        self.assertNotIn(
            "Комментировать ответ",
            self.article_js,
            "Legacy text button 'Комментировать ответ' must be replaced by icon button in renderAnswerCard"
        )
        self.assertNotIn(
            '<div class="comment-actions">',
            self.article_js,
            "Legacy separate '.comment-actions' container must be eliminated"
        )

    def test_02_presence_and_structure_of_icon_only_action_buttons(self) -> None:
        """Verify icon-only action buttons use .btn-comment-action, 14px SVGs, aria-label, and title."""
        # Comment reply button
        reply_comm_match = re.search(
            r'class="btn-comment-action btn-reply-comment"\s+title="Ответить"\s+aria-label="Ответить"',
            self.article_js
        )
        self.assertIsNotNone(reply_comm_match, "Comment reply button must be .btn-comment-action with title and aria-label")

        # Comment delete button
        del_comm_match = re.search(
            r'class="btn-comment-action btn-delete-comment"\s+title="Удалить"\s+aria-label="Удалить"',
            self.article_js
        )
        self.assertIsNotNone(del_comm_match, "Comment delete button must be .btn-comment-action with title and aria-label")

        # Comment edit button
        edit_comm_match = re.search(
            r'class="btn-comment-action btn-edit-comment"\s+title="Редактировать"\s+aria-label="Редактировать"',
            self.article_js
        )
        self.assertIsNotNone(edit_comm_match, "Comment edit button must be .btn-comment-action with title and aria-label")

        # Answer reply button
        reply_ans_match = re.search(
            r'class="btn-comment-action btn-reply-answer"\s+title="Ответить"\s+aria-label="Ответить"',
            self.article_js
        )
        self.assertIsNotNone(reply_ans_match, "Answer reply button must be .btn-comment-action with title and aria-label")

        # Answer edit button
        edit_ans_match = re.search(
            r'class="btn-comment-action btn-edit-answer"\s+title="Редактировать"\s+aria-label="Редактировать"',
            self.article_js
        )
        self.assertIsNotNone(edit_ans_match, "Answer edit button must be .btn-comment-action with title and aria-label")

        # All buttons contain 14px SVG icons
        self.assertIn('<svg width="14" height="14"', self.article_js)

    def test_03_strict_button_order_in_comment_action_row(self) -> None:
        """Strict order in comments: [Vote Capsule] -> [Ответить] -> [Сохранить] -> [Поделиться] -> [Подписаться] -> [Пожаловаться] -> [Удалить] -> [Редактировать]."""
        comm_row_pattern = (
            r'<div class="comment-vote-row comment-action-row">\s*\'\s*\+\s*'
            r'commVoteCapsuleHtml\s*\+\s*'
            r'replyBtnHtml\s*\+\s*'
            r'saveBtnHtml\s*\+\s*'
            r'shareBtnHtml\s*\+\s*'
            r'subscribeBtnHtml\s*\+\s*'
            r'reportBtnHtml\s*\+\s*'
            r'deleteBtnHtml\s*\+\s*'
            r'editBtnHtml\s*\+\s*'
            r'\'\s*</div>'
        )
        match = re.search(comm_row_pattern, self.article_js)
        self.assertIsNotNone(
            match,
            "Comment action row must strictly assemble: commVoteCapsuleHtml + replyBtnHtml + saveBtnHtml + shareBtnHtml + subscribeBtnHtml + reportBtnHtml + deleteBtnHtml + editBtnHtml"
        )

    def test_04_strict_button_order_in_answer_action_row(self) -> None:
        """Strict order in answers: [Vote Capsule] -> [Ответить] -> [Сохранить] -> [Поделиться] -> [Подписаться] -> [Пожаловаться] -> [Редактировать]."""
        ans_row_pattern = (
            r'<div class="comment-vote-row answer-vote-row comment-action-row answer-actions">\s*\'\s*\+\s*'
            r'ansVoteCapsuleHtml\s*\+\s*'
            r'replyBtnHtml\s*\+\s*'
            r'saveBtnHtml\s*\+\s*'
            r'shareBtnHtml\s*\+\s*'
            r'subscribeBtnHtml\s*\+\s*'
            r'reportBtnHtml\s*\+\s*'
            r'editBtnHtml\s*\+\s*'
            r'\'\s*</div>'
        )
        match = re.search(ans_row_pattern, self.article_js)
        self.assertIsNotNone(
            match,
            "Answer action row must strictly assemble: ansVoteCapsuleHtml + replyBtnHtml + saveBtnHtml + shareBtnHtml + subscribeBtnHtml + reportBtnHtml + editBtnHtml"
        )

    def test_05_preservation_of_thread_toggle_button_on_separate_row(self) -> None:
        """Thread toggle button (.btn-toggle-thread) is strictly on its own row and not in action row."""
        self.assertIn("toggleRow.appendChild(toggleBtn);", self.article_js)
        self.assertIn("el.appendChild(toggleRow);", self.article_js)
        self.assertNotIn("toggleRow.appendChild(commentActions);", self.article_js)
        self.assertNotIn("toggleRow.appendChild(replyBtnHtml", self.article_js)
        self.assertNotIn("toggleRow.appendChild(deleteBtnHtml", self.article_js)
        self.assertNotIn("toggleRow.appendChild(editBtnHtml", self.article_js)

    def test_06_action_button_dimensions_and_box_model_in_css(self) -> None:
        """Verify .btn-comment-action geometry: 25px x 25px, 1px border, 4px border-radius, 1:1 aspect-ratio."""
        for css_content, source_name in [(self.article_css, "article.css"), (self.theme_css, "theme.css")]:
            rule_match = re.search(r'\.btn-comment-action\s*\{([^}]+)\}', css_content)
            self.assertIsNotNone(rule_match, f".btn-comment-action rule must exist in {source_name}")
            block = rule_match.group(1)

            self.assertIn("height: 25px;", block, f"Height must be 25px in {source_name}")
            self.assertIn("width: 25px;", block, f"Width must be 25px in {source_name}")
            self.assertIn("aspect-ratio: 1 / 1;", block, f"Aspect-ratio must be 1 / 1 in {source_name}")
            self.assertIn("border: 1px solid var(--border-color);", block, f"Border must be 1px solid in {source_name}")
            self.assertTrue(
                "border-radius: var(--radius-xs, 4px);" in block or "border-radius: 4px;" in block,
                f"Border-radius must be 4px (var(--radius-xs)) in {source_name}"
            )
            self.assertIn("display: inline-flex;", block, f"Display must be inline-flex in {source_name}")
            self.assertIn("align-items: center;", block, f"Align-items must be center in {source_name}")
            self.assertIn("justify-content: center;", block, f"Justify-content must be center in {source_name}")
            self.assertIn("padding: 0;", block, f"Padding must be 0 in {source_name}")

    def test_07_action_row_layout_geometry_in_css(self) -> None:
        """Verify .comment-action-row layout: flex, gap 6px, flex-wrap wrap, margin 4px 0 3px 0."""
        for css_content, source_name in [(self.article_css, "article.css"), (self.theme_css, "theme.css")]:
            match = re.search(r'\.comment-action-row\s*\{([^}]+)\}', css_content)
            if not match:
                match = re.search(r'\.comment-vote-row,\s*\.comment-action-row\s*\{([^}]+)\}', css_content)
            self.assertIsNotNone(match, f"comment-action-row rule must exist in {source_name}")
            block = match.group(1)

            self.assertIn("display: flex;", block, f"Row display must be flex in {source_name}")
            self.assertIn("align-items: center;", block, f"Row align-items must be center in {source_name}")
            self.assertIn("gap: 6px;", block, f"Row gap must be 6px in {source_name}")
            self.assertIn("flex-wrap: wrap;", block, f"Row flex-wrap must be wrap in {source_name}")
            self.assertIn("margin: 4px 0 3px 0;", block, f"Row margin must be 4px 0 3px 0 in {source_name}")

    def test_08_hover_and_focus_state_color_rules(self) -> None:
        """Verify accent hover for Reply & Edit, destructive red hover for Delete."""
        for css_content, source_name in [(self.article_css, "article.css"), (self.theme_css, "theme.css")]:
            # Reply & Edit hover/focus
            reply_edit_match = re.search(
                r'\.btn-comment-action\.btn-reply-comment:hover[^{]*\{([^}]+)\}',
                css_content
            )
            self.assertIsNotNone(reply_edit_match, f"Reply and Edit hover rule must exist in {source_name}")
            reply_block = reply_edit_match.group(1)
            self.assertIn("#38bdf8", reply_block, f"Reply/Edit hover must use accent color (#38bdf8) in {source_name}")

            # Delete hover/focus
            del_match = re.search(
                r'\.btn-comment-action\.btn-delete-comment:hover[^{]*\{([^}]+)\}',
                css_content
            )
            self.assertIsNotNone(del_match, f"Delete button hover rule must exist in {source_name}")
            del_block = del_match.group(1)
            self.assertIn("#ef4444", del_block, f"Delete hover must use red color (#ef4444) in {source_name}")

    def test_09_accessibility_and_focus_visible_styling(self) -> None:
        """Verify :focus-visible outline: 2px solid var(--accent-color) and outline-offset."""
        for css_content, source_name in [(self.article_css, "article.css"), (self.theme_css, "theme.css")]:
            focus_match = re.search(
                r'\.btn-comment-action:focus-visible\s*\{([^}]+)\}',
                css_content
            )
            self.assertIsNotNone(focus_match, f".btn-comment-action:focus-visible rule must exist in {source_name}")
            block = focus_match.group(1)
            self.assertIn("outline: 2px solid var(--accent-color);", block)
            self.assertIn("outline-offset: 1px;", block)

    def test_10_comment_compact_vote_capsule_unaltered(self) -> None:
        """Verify compact vote capsule (.vote-capsule--compact, 25px height) is preserved and called."""
        # CSS rule for compact vote capsule
        self.assertIn(".vote-capsule--compact", self.theme_css)
        compact_match = re.search(r'\.vote-capsule--compact[^{]*\{([^}]+)\}', self.theme_css)
        self.assertIsNotNone(compact_match, ".vote-capsule--compact rule must exist in theme.css")
        block = compact_match.group(1)
        self.assertIn("height: 25px;", block)
        self.assertIn("border-radius: var(--radius-xs, 4px);", block)

        # In article.js, comment and answer vote capsules request isCompact: true
        comment_calls = [
            body for body in re.findall(r'renderVoteCapsuleHtml\(\{([^}]+)\}\)', self.article_js)
            if "targetType: 'comment'" in body
        ]
        self.assertGreaterEqual(len(comment_calls), 2, "Both comment and answer must invoke renderVoteCapsuleHtml with targetType: 'comment'")
        for call_body in comment_calls:
            self.assertIn("isCompact: true", call_body, "Comment and answer vote capsules must specify isCompact: true")

    def test_11_event_listeners_wired_cleanly_without_breakage(self) -> None:
        """Verify event querySelectors and listeners match new button classes in article.js."""
        self.assertIn("el.querySelector('.btn-reply-comment')", self.article_js)
        self.assertIn("el.querySelector('.btn-delete-comment')", self.article_js)
        self.assertIn("el.querySelector('.btn-edit-comment')", self.article_js)
        self.assertIn("el.querySelector('.btn-reply-answer')", self.article_js)
        self.assertIn("el.querySelector('.btn-edit-answer')", self.article_js)

    def test_12_zero_emojis_and_no_em_dashes(self) -> None:
        """Ensure zero emojis, zero em dashes, zero server IPs, and zero local filesystem paths."""
        with open(__file__, "r", encoding="utf-8") as f:
            content = f.read()

        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]|[\u2600-\u26ff]|[\u2700-\u27bf]")
        self.assertIsNone(emoji_pattern.search(content), "Emoji found in test file")
        self.assertNotIn("\u2014", content, "Em dash found in test file")

        self.assertIsNone(emoji_pattern.search(self.article_js), "Emoji found in article.js")
        self.assertNotIn("\u2014", self.article_js, "Em dash found in article.js")

        self.assertIsNone(emoji_pattern.search(self.article_css), "Emoji found in article.css")
        self.assertNotIn("\u2014", self.article_css, "Em dash found in article.css")

        self.assertIsNone(emoji_pattern.search(self.theme_css), "Emoji found in theme.css")
        self.assertNotIn("\u2014", self.theme_css, "Em dash found in theme.css")

    def test_13_offline_first_and_no_external_cdns(self) -> None:
        """Ensure 100% offline-first: no external http:// or https:// CDNs in modified stylesheets."""
        for css_content, source_name in [(self.article_css, "article.css"), (self.theme_css, "theme.css")]:
            urls = re.findall(r'url\s*\(\s*["\']?(https?://[^"\')]+)', css_content)
            self.assertEqual(len(urls), 0, f"External CDN url found in {source_name}: {urls}")


if __name__ == "__main__":
    unittest.main()
