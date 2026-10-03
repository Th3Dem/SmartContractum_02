#!/usr/bin/env python3
"""
tests/test_issue111_comment_composer_click_away.py

Automated test suite for Issue #111:
1. Automatic Collapse on Click Away / Pointerdown Outside:
   - Document pointerdown outside #commentForm collapses composer without losing draft.
   - Text is persisted via saveCommentDraft(articleId, ...).
2. Safe Draft Persistence in sessionStorage:
   - saveCommentDraft, getCommentDraft, clearCommentDraft integrate with draft_comment_<articleId>.
3. Visual Draft Indicator in Collapsed State:
   - When draft is present, updateComposerDraftUI applies .has-draft to #commentForm.
   - Placeholder button text updates to "Продолжить комментарий...".
   - CSS .comment-composer.has-draft provides accent indicator.
4. Non-Blocking Cancel Button:
   - Cancel button saves draft and collapses without any blocking window.confirm() dialog.
5. Escape Key Handling:
   - Escape key collapses composer and saves draft without modal prompts.
6. Clean State Reset on Submission:
   - On successful submission, clearCommentDraft is invoked, draft UI resets, and form collapses.
7. Project Invariants:
   - Zero emojis, zero em dashes, 100% offline-first.
"""

import os
import re
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def read_file(relative_path: str) -> str:
    full_path = os.path.join(PROJECT_ROOT, relative_path)
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()


class TestIssue111CommentComposerClickAway(unittest.TestCase):
    """Test suite for Comment Composer click-away collapse and draft safety."""

    @classmethod
    def setUpClass(cls):
        cls.article_html = read_file("frontend/public/article.html")
        cls.article_css = read_file("frontend/public/css/article.css")
        cls.article_js = read_file("frontend/public/js/article.js")
        cls.theme_css = read_file("frontend/public/css/theme.css")
        cls.test_file_content = read_file("tests/test_issue111_comment_composer_click_away.py")

    def test_01_pointerdown_click_outside_handler(self):
        """Verify pointerdown click-outside handler collapses composer and preserves draft."""
        self.assertIn("handleCommentClickOutside", self.article_js)
        self.assertIn("document.addEventListener('pointerdown'", self.article_js)
        self.assertIn("!form.contains(e.target)", self.article_js)
        self.assertIn("saveCommentDraft(articleId", self.article_js)
        self.assertIn("collapseCommentComposer()", self.article_js)

    def test_02_escape_key_collapse_without_modal(self):
        """Verify Escape key collapses composer and saves draft without modal."""
        self.assertIn("e.key === 'Escape'", self.article_js)
        self.assertIn("collapseCommentComposer()", self.article_js)

    def test_03_cancel_button_without_blocking_confirm(self):
        """Verify Cancel button collapses without blocking window.confirm()."""
        # Confirm no window.confirm is used in the comment composer cancel flow
        composer_idx = self.article_js.find("'btnCancelComment'")
        self.assertNotEqual(composer_idx, -1)
        # Search for the cancelBtn click listener inside the comment form logic
        listener_idx = self.article_js.find("cancelBtn.addEventListener('click'", composer_idx)
        self.assertNotEqual(listener_idx, -1)
        cancel_block = self.article_js[listener_idx:listener_idx + 400]
        self.assertNotIn("confirm(", cancel_block)
        self.assertIn("saveCommentDraft", cancel_block)
        self.assertIn("collapseCommentComposer()", cancel_block)

    def test_04_session_storage_draft_helpers(self):
        """Verify saveCommentDraft, getCommentDraft, and clearCommentDraft."""
        self.assertIn("function saveCommentDraft", self.article_js)
        self.assertIn("function getCommentDraft", self.article_js)
        self.assertIn("function clearCommentDraft", self.article_js)
        self.assertIn("sessionStorage.setItem('draft_comment_'", self.article_js)
        self.assertIn("sessionStorage.getItem('draft_comment_'", self.article_js)
        self.assertIn("sessionStorage.removeItem('draft_comment_'", self.article_js)

    def test_05_visual_draft_indicator_and_placeholder_update(self):
        """Verify draft indicator text 'Продолжить комментарий...' and .has-draft CSS."""
        self.assertIn("function updateComposerDraftUI", self.article_js)
        self.assertIn("Продолжить комментарий...", self.article_js)
        self.assertIn("has-draft", self.article_js)

        # CSS styles for .has-draft
        self.assertIn(".comment-composer.has-draft", self.article_css)
        self.assertIn(".comment-composer.has-draft .comment-composer-placeholder-btn", self.article_css)
        self.assertIn(".comment-composer.has-draft .comment-composer-trigger", self.article_css)

    def test_06_successful_submit_clears_draft(self):
        """Verify successful submission calls clearCommentDraft and collapses composer."""
        self.assertIn("clearCommentDraft(articleId)", self.article_js)
        self.assertIn("collapseCommentComposer()", self.article_js)

    def test_07_zero_emojis_no_em_dashes_offline_first(self):
        """Verify zero emojis, zero em dashes, and 100% offline-first."""
        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]|[\u2600-\u26ff]|[\u2700-\u27bf]")
        files_to_check = [
            (self.test_file_content, "test_issue111_comment_composer_click_away.py"),
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
