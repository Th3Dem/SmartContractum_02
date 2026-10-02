"""
Tests for Issue #66 (SC-029): Question Editor layout, document bar, and CTA unification with Editor.

Verifications:
1. question-editor.html contains #editorDocumentBar with #btn-drafts-modal, #save-status, #btn-submit-question.
2. #btn-submit-question has class .btn-next-to-pub and is disabled by default.
3. Old bottom action bar is removed from the form card.
4. Title character counter container exists.
5. Max-width 940px is applied to question container and document bar in CSS.
6. Card styling matches 16px radius, editor background tokens, and desktop padding.
7. question-editor.js implements dynamic readiness check, title counter, unified autosave statuses, and draft badge.
8. Zero emojis and no em dashes in files.
"""

import os
import re
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue66QuestionEditorLayoutAndCTA(unittest.TestCase):
    """Automated unit and contract tests for Issue #66."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(FRONTEND_DIR, "question-editor.html"), "r", encoding="utf-8") as f:
            cls.html = f.read()
        with open(os.path.join(FRONTEND_DIR, "css", "question-editor.css"), "r", encoding="utf-8") as f:
            cls.css = f.read()
        with open(os.path.join(FRONTEND_DIR, "js", "question-editor.js"), "r", encoding="utf-8") as f:
            cls.js = f.read()

    # 1. Document Bar in question-editor.html
    def test_01_document_bar_elements_and_hierarchy(self):
        """question-editor.html contains #editorDocumentBar with required controls."""
        self.assertIn('id="editorDocumentBar"', self.html)
        self.assertIn('class="editor-document-bar"', self.html)
        self.assertIn('class="editor-docbar-container"', self.html)
        self.assertIn('class="editor-docbar-main"', self.html)
        self.assertIn('id="btn-drafts-modal"', self.html)
        self.assertIn('id="drafts-badge"', self.html)
        self.assertIn('id="save-status"', self.html)
        self.assertIn('id="save-status-text"', self.html)
        self.assertIn('Все изменения сохранены', self.html)

        # Submit CTA button in document bar
        btn_match = re.search(r'<button[^>]*id=["\']btn-submit-question["\'][^>]*>', self.html)
        self.assertIsNotNone(btn_match, "#btn-submit-question not found in question-editor.html")
        btn_tag = btn_match.group(0)

        self.assertIn("btn-next-to-pub", btn_tag, "#btn-submit-question must have class btn-next-to-pub")
        self.assertIn("btn-primary", btn_tag, "#btn-submit-question must have class btn-primary")
        self.assertIn("disabled", btn_tag, "#btn-submit-question must be disabled by default")
        self.assertIn('title="Добавьте вопрос и его описание"', btn_tag)

    # 2. Old bottom action bar removal
    def test_02_old_bottom_action_bar_removed(self):
        """Old duplicate bottom action bar is removed from the form card."""
        self.assertNotIn('class="question-form-footer"', self.html)
        self.assertNotIn('class="question-submit-btn"', self.html)
        self.assertNotIn('id="questionAutosaveStatus"', self.html)
        self.assertNotIn('id="btnSubmitQuestion"', self.html)

        # Form ends cleanly with questionFormError
        form_match = re.search(r'<div id=["\']questionFormError["\'][^>]*></div>\s*</form>', self.html)
        self.assertIsNotNone(form_match, "Form must end cleanly after questionFormError container")

    # 3. Dynamic character counter container
    def test_03_title_character_counter_container(self):
        """Dynamic character counter container exists next to or within the title label group."""
        self.assertIn('id="title-char-counter"', self.html)
        self.assertIn('class="char-counter"', self.html)
        self.assertIn('0 / 250', self.html)

    # 4. Base width 940px in CSS
    def test_04_max_width_940px_layout_in_css(self):
        """CSS applies max-width: 940px to question container and document bar container."""
        # Check question-container
        container_match = re.search(r'\.question-container\s*\{[^}]*max-width:\s*940px', self.css)
        self.assertIsNotNone(container_match, ".question-container must have max-width: 940px")

        # Check editor-docbar-container
        docbar_container_match = re.search(r'\.editor-docbar-container\s*\{[^}]*max-width:\s*940px', self.css)
        self.assertIsNotNone(docbar_container_match, ".editor-docbar-container must have max-width: 940px")

        # Check editor-docbar-main
        docbar_main_match = re.search(r'\.editor-docbar-main\s*\{[^}]*max-width:\s*940px', self.css)
        self.assertIsNotNone(docbar_main_match, ".editor-docbar-main must have max-width: 940px")

    # 5. Form card styling matching .editor-card tokens
    def test_05_editor_card_tokens_in_css(self):
        """Form card has border-radius 16px, background #171924, and 32px 36px padding."""
        card_match = re.search(r'\.question-form-card\s*\{([^}]+)\}', self.css)
        self.assertIsNotNone(card_match, ".question-form-card rule not found")
        card_rules = card_match.group(1)

        self.assertIn("border-radius: 16px", card_rules)
        self.assertIn("padding: 32px 36px", card_rules)
        self.assertIn("#171924", card_rules)

        # Light theme override
        light_card_match = re.search(r'\[data-theme=["\']light["\']\]\s*\.question-form-card\s*\{([^}]+)\}', self.css)
        self.assertIsNotNone(light_card_match, "[data-theme='light'] .question-form-card not found")
        self.assertIn("#ffffff", light_card_match.group(1))

    # 6. Document bar tokens, Green CTA, and Save Status styles in CSS
    def test_06_cta_button_and_save_status_styles_in_css(self):
        """CSS includes styles for sticky docbar, green CTA, and 4 save status states."""
        # Document bar sticky height
        self.assertIn(".editor-document-bar", self.css)
        self.assertIn("height: 52px", self.css)
        self.assertIn("position: sticky", self.css)
        self.assertIn("backdrop-filter: blur(16px)", self.css)

        # Green CTA styles
        self.assertIn(".btn-next-to-pub", self.css)
        self.assertIn("#btn-submit-question", self.css)
        self.assertIn("#10b981", self.css)
        self.assertIn("#059669", self.css)
        self.assertIn("border-radius: 9px", self.css)
        self.assertIn("height: 38px", self.css)
        self.assertIn("grayscale(40%)", self.css)

        # Save status states
        self.assertIn(".save-status", self.css)
        self.assertIn(".save-dot", self.css)
        self.assertIn(".status-saved", self.css)
        self.assertIn(".status-unsaved", self.css)
        self.assertIn(".status-saving", self.css)
        self.assertIn(".status-error", self.css)
        self.assertIn("#16c784", self.css)
        self.assertIn("#f59e0b", self.css)
        self.assertIn("#38bdf8", self.css)
        self.assertIn("#ef4444", self.css)
        self.assertIn("pulse-dot", self.css)

        # Security notice banner subtle amber styling
        sec_banner_match = re.search(r'\.question-security-banner\s*\{([^}]+)\}', self.css)
        self.assertIsNotNone(sec_banner_match)
        sec_rules = sec_banner_match.group(1)
        self.assertIn("border-radius: 10px", sec_rules)
        self.assertIn("padding: 10px 14px", sec_rules)

        # Title char counter styles
        self.assertIn(".char-counter", self.css)
        self.assertIn("font-size: 0.8rem", self.css)

    # 7. Dynamic readiness, counter, and autosave in question-editor.js
    def test_07_question_editor_js_wiring_readiness_and_counter(self):
        """question-editor.js wires #btn-submit-question, dynamic readiness, counter, and statuses."""
        self.assertIn("btn-submit-question", self.js)
        self.assertIn("title-char-counter", self.js)
        self.assertIn("updateSubmitReadiness", self.js)
        self.assertIn("updateTitleCounter", self.js)
        self.assertIn("updateDraftsBadge", self.js)
        self.assertIn("drafts-badge", self.js)
        self.assertIn("save-status", self.js)
        self.assertIn("save-status-text", self.js)

        # Dynamic readiness logic: title >= 5, quill >= 15
        self.assertIn("MIN_TITLE_LEN", self.js)
        self.assertIn("MIN_DETAILS_LEN", self.js)
        self.assertIn("Опубликовать вопрос", self.js)
        self.assertIn("Добавьте вопрос и его описание", self.js)

        # Unified save status texts
        self.assertIn("Все изменения сохранены", self.js)
        self.assertIn("Сохранение...", self.js)
        self.assertIn("Ошибка сохранения", self.js)

    # 8. Code Standards: Zero emojis and no em dashes
    def test_08_code_standards_zero_emojis_and_no_em_dashes(self):
        """Target files must contain zero emojis and no em dashes."""
        test_file_path = os.path.abspath(__file__)
        with open(test_file_path, "r", encoding="utf-8") as f:
            test_content = f.read()

        files_to_check = [
            ("question-editor.html", self.html),
            ("question-editor.css", self.css),
            ("question-editor.js", self.js),
            ("test_issue66_question_editor_layout_and_cta.py", test_content)
        ]

        for fname, content in files_to_check:
            self.assertNotIn("\u2014", content, f"Em dash found in {fname}")
            emojis = re.findall(r'[\U00010000-\U0010ffff]', content)
            self.assertEqual(len(emojis), 0, f"Emoji found in {fname}: {emojis}")


if __name__ == "__main__":
    unittest.main()
