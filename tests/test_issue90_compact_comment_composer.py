#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Suite for Issue #90:
[P2][frontend] Компактный свернутый composer комментария.

Verifies:
1. Initial collapsed state of the comment composer (height 42-46px, avatar, placeholder, accessibility attributes).
2. Expanded state (toolbar, textarea with auto-resize, preview pane, action buttons).
3. CSS transitions, hover effects, and display toggling between states.
4. Auto-save and draft restoration from sessionStorage (key draft_comment_).
5. Hotkeys: Ctrl+Enter / Cmd+Enter for quick submission, Escape for collapsing empty composer.
6. Cancel button logic (collapses when empty, safeguards text when content is present).
7. Formatting toolbar (bold, italic, quote, code, markdown preview toggle).
8. Guest and authenticated avatar rendering and modal prompt on guest click.
"""

import os
import re
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(BASE_DIR, "frontend", "public", "article.html")
CSS_PATH = os.path.join(BASE_DIR, "frontend", "public", "css", "article.css")
JS_PATH = os.path.join(BASE_DIR, "frontend", "public", "js", "article.js")


class TestIssue90CompactCommentComposer(unittest.TestCase):
    """Automated verification suite for Issue #90."""

    @classmethod
    def setUpClass(cls):
        with open(HTML_PATH, "r", encoding="utf-8") as f:
            cls.html = f.read()
        with open(CSS_PATH, "r", encoding="utf-8") as f:
            cls.css = f.read()
        with open(JS_PATH, "r", encoding="utf-8") as f:
            cls.js = f.read()

    def test_01_composer_markup_and_accessibility_attributes(self):
        """Verify HTML markup for collapsed composer and accessibility roles."""
        # 1. Check form wrapper with role="region" and aria-expanded
        self.assertIn('id="commentForm"', self.html)
        self.assertIn('class="comment-form comment-composer is-collapsed"', self.html)
        self.assertIn('role="region"', self.html)
        self.assertIn('aria-label="Форма добавления комментария"', self.html)
        self.assertIn('aria-expanded="false"', self.html)

        # 2. Collapsed trigger elements
        self.assertIn('id="commentComposerTrigger"', self.html)
        self.assertIn('id="commentComposerAvatar"', self.html)
        self.assertIn('id="btnCommentComposerOpen"', self.html)

        # 3. Expanded body and formatting toolbar
        self.assertIn('id="commentComposerExpandedBody"', self.html)
        self.assertIn('id="commentComposerToolbar"', self.html)
        self.assertIn('id="btnCommentBold"', self.html)
        self.assertIn('id="btnCommentItalic"', self.html)
        self.assertIn('id="btnCommentQuote"', self.html)
        self.assertIn('id="btnCommentCode"', self.html)
        self.assertIn('id="btnCommentPreview"', self.html)

        # 4. Textarea, preview pane, and actions
        self.assertIn('id="commentTextInput"', self.html)
        self.assertIn('id="commentPreviewWrap"', self.html)
        self.assertIn('id="commentCharCount"', self.html)
        self.assertIn('id="btnCancelComment"', self.html)
        self.assertIn('id="btnSubmitComment"', self.html)

    def test_02_css_collapsed_trigger_and_transitions(self):
        """Verify CSS dimensions (42-46px height), hover effects, and transitions."""
        # Height 44px (within 42-46px range)
        self.assertIn('.comment-composer-trigger', self.css)
        trigger_height_match = re.search(r'\.comment-composer-trigger\s*\{[^}]*height:\s*44px', self.css)
        self.assertIsNotNone(trigger_height_match, ".comment-composer-trigger must define height: 44px")

        # Cursor pointer and hover border
        self.assertIn('cursor: pointer', self.css)
        self.assertIn('.comment-composer-trigger:hover', self.css)

        # Avatar container styling
        self.assertIn('.comment-composer-avatar', self.css)
        self.assertIn('border-radius: 50%', self.css)

        # Collapsed vs Expanded visibility rules
        self.assertIn('.comment-composer.is-collapsed .comment-composer-trigger', self.css)
        self.assertIn('.comment-composer.is-collapsed .comment-composer-expanded-body', self.css)
        self.assertIn('.comment-composer.is-expanded .comment-composer-trigger', self.css)
        self.assertIn('.comment-composer.is-expanded .comment-composer-expanded-body', self.css)

        # Slide down animation for smooth expansion
        self.assertIn('@keyframes composerSlideDown', self.css)

    def test_03_js_composer_state_toggling_logic(self):
        """Verify JS functions for expanding and collapsing composer."""
        self.assertIn('function expandCommentComposer', self.js)
        self.assertIn('function collapseCommentComposer', self.js)
        self.assertIn("form.classList.remove('is-collapsed')", self.js)
        self.assertIn("form.classList.add('is-expanded')", self.js)
        self.assertIn("form.setAttribute('aria-expanded', 'true')", self.js)
        self.assertIn("form.setAttribute('aria-expanded', 'false')", self.js)

    def test_04_js_cancel_button_and_empty_escape(self):
        """Verify cancel button logic and Escape hotkey behavior."""
        # Cancel button event listener
        self.assertIn('cancelBtn.addEventListener', self.js)
        # Draft save and collapse without blocking confirm modal (Issue #111)
        self.assertIn('saveCommentDraft', self.js)
        self.assertTrue('collapseCommentComposer()' in self.js)

        # Escape keydown listener
        self.assertIn("e.key === 'Escape'", self.js)

    def test_05_js_session_storage_draft_persistence(self):
        """Verify sessionStorage integration with key draft_comment_."""
        self.assertIn('draft_comment_', self.js)
        self.assertIn('sessionStorage.setItem', self.js)
        self.assertIn('sessionStorage.getItem', self.js)
        self.assertIn('sessionStorage.removeItem', self.js)

        # Verified draft functions exist
        self.assertIn('function saveCommentDraft', self.js)
        self.assertIn('function getCommentDraft', self.js)
        self.assertIn('function clearCommentDraft', self.js)

        # Restoration on initialization
        self.assertIn('getCommentDraft(articleId)', self.js)

    def test_06_js_hotkeys_ctrl_enter_quick_submission(self):
        """Verify Ctrl+Enter and Cmd+Enter shortcut for comment submission."""
        self.assertIn("(e.ctrlKey || e.metaKey) && e.key === 'Enter'", self.js)

    def test_07_js_formatting_toolbar_and_markdown_preview(self):
        """Verify formatting helpers (bold, italic, quote, code) and preview toggle."""
        self.assertIn('function applyFormat', self.js)
        self.assertIn('function renderCommentMarkdown', self.js)
        self.assertIn('function toggleCommentPreview', self.js)

        # Formatting actions
        self.assertIn("applyFormat('bold')", self.js)
        self.assertIn("applyFormat('italic')", self.js)
        self.assertIn("applyFormat('quote')", self.js)
        self.assertIn("applyFormat('code')", self.js)

    def test_08_js_avatar_and_guest_click_prompt(self):
        """Verify avatar dynamic updates in updateAuthUI and guest auth prompt."""
        self.assertIn('commentComposerAvatar', self.js)
        self.assertIn('comment-composer-avatar-img', self.js)
        self.assertIn('comment-composer-avatar-guest', self.js)
        self.assertIn("showToast('Войдите, чтобы оставить комментарий')", self.js)


if __name__ == '__main__':
    unittest.main()
