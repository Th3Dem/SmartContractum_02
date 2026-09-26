#!/usr/bin/env python3
"""
Unit tests for Task 09: Spoiler, Code Block, and Placeholder Refinements
(task-09-spoiler-code-and-placeholder-fixes):
1. Inline Spoiler (Bubble Toolbar):
   - CSS .editor-inline-spoiler blur effect (filter: blur(4.5px)), subtle background, pointer cursor.
   - CSS .editor-inline-spoiler.is-revealed unblurred (filter: none), selectable, dashed border.
   - Preview mode matches blur/reveal behavior.
   - main.js binds click interaction to toggle .is-revealed in both edit and preview modes.
   - bubble.js toggles inline-spoiler format and sets .is-active when inside inline spoiler.
2. Code Block & Language Selector:
   - theme.css code block variables (light: #f8f9fa, dark: #0e121e).
   - editor.css overrides Quill Snow defaults for code container and pre.ql-syntax.
   - select.ql-ui positioned top: -26px, right: 0 with Onest font and custom SVG arrow.
   - Never overlaps code text due to reserved margin.
3. Block Spoiler Dynamic Placeholder:
   - blocks.js inserts spoiler with empty initial values (title: '', body: '').
   - core.js SpoilerBlot.create configures data-placeholder and input/keyup cleaners.
   - editor.css defines :empty::before placeholder styles using var(--text-placeholder).
   - converter.js details export fallback to 'Спойлер' when empty.
4. Regression and Offline-first Integrity.
"""

import os
import re
import unittest


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, 'frontend', 'public')


class TestInlineSpoilerRefinements(unittest.TestCase):
    """Test 1: Inline spoiler blur, reveal toggle, Blot implementation, and formatText."""

    @classmethod
    def setUpClass(cls):
        cls.editor_css_path = os.path.join(FRONTEND_DIR, 'css', 'editor.css')
        with open(cls.editor_css_path, 'r', encoding='utf-8') as f:
            cls.editor_css = f.read()

        cls.main_js_path = os.path.join(FRONTEND_DIR, 'js', 'main.js')
        with open(cls.main_js_path, 'r', encoding='utf-8') as f:
            cls.main_js = f.read()

        cls.bubble_js_path = os.path.join(FRONTEND_DIR, 'js', 'bubble.js')
        with open(cls.bubble_js_path, 'r', encoding='utf-8') as f:
            cls.bubble_js = f.read()

        cls.core_js_path = os.path.join(FRONTEND_DIR, 'js', 'core.js')
        with open(cls.core_js_path, 'r', encoding='utf-8') as f:
            cls.core_js = f.read()

    def test_inline_spoiler_blot_implementation(self):
        """Ensure InlineSpoilerBlot has static formats, formats(), format() unwrap, and registration."""
        self.assertIn("class InlineSpoilerBlot extends Inline", self.core_js)
        self.assertIn("static formats(domNode)", self.core_js)
        self.assertIn("formats()", self.core_js)
        self.assertIn("formats['inline-spoiler'] = true;", self.core_js)
        self.assertIn("if (name === this.statics.blotName && !value)", self.core_js)
        self.assertIn("this.unwrap();", self.core_js)
        self.assertIn("Quill.register(InlineSpoilerBlot, true);", self.core_js)
        self.assertIn("Quill.register('formats/inline-spoiler', InlineSpoilerBlot, true);", self.core_js)

    def test_inline_spoiler_css_blurred_by_default(self):
        """Ensure .editor-inline-spoiler has blur filter and proper styling without user-select: none."""
        match = re.search(r'\.editor-inline-spoiler\s*\{([^}]+)\}', self.editor_css)
        self.assertIsNotNone(match, ".editor-inline-spoiler rule must exist in editor.css")
        block = match.group(1)
        self.assertIn('filter: blur(5px);', block)
        self.assertIn('-webkit-filter: blur(5px);', block)
        self.assertIn('background-color: rgba(100, 116, 139, 0.15);', block)
        self.assertIn('cursor: pointer;', block)
        self.assertNotIn('user-select: none;', block)

    def test_inline_spoiler_css_revealed_state(self):
        """Ensure .editor-inline-spoiler.is-revealed clears blur with !important."""
        match = re.search(r'\.editor-inline-spoiler\.is-revealed[^{]*\{([^}]+)\}', self.editor_css)
        self.assertIsNotNone(match, ".editor-inline-spoiler.is-revealed rule must exist in editor.css")
        block = match.group(1)
        self.assertIn('filter: none !important;', block)
        self.assertIn('-webkit-filter: none !important;', block)
        self.assertIn('background-color: var(--bg-subtle);', block)
        self.assertIn('border-bottom: 1px dashed var(--border-color);', block)

    def test_preview_mode_inline_spoiler_styling(self):
        """Ensure .preview-mode inline spoiler rules match blur and reveal behavior."""
        preview_match = re.search(r'\.preview-mode\s+\.editor-inline-spoiler\s*\{([^}]+)\}', self.editor_css)
        self.assertIsNotNone(preview_match, ".preview-mode .editor-inline-spoiler rule must exist")
        self.assertIn('filter: blur(5px);', preview_match.group(1))
        self.assertIn('-webkit-filter: blur(5px);', preview_match.group(1))

        revealed_match = re.search(r'\.preview-mode\s+\.editor-inline-spoiler\.is-revealed[^{]*\{([^}]+)\}', self.editor_css)
        self.assertIsNotNone(revealed_match, ".preview-mode .editor-inline-spoiler.is-revealed rule must exist")
        self.assertIn('filter: none !important;', revealed_match.group(1))
        self.assertIn('-webkit-filter: none !important;', revealed_match.group(1))

    def test_main_js_binds_click_in_all_modes(self):
        """Ensure bindInlineSpoilerInteraction toggles is-revealed and data-revealed without preview-mode-only restriction."""
        method_match = re.search(r'bindInlineSpoilerInteraction\(\)\s*\{([\s\S]*?)\n\s{4}\}', self.main_js)
        self.assertIsNotNone(method_match, "bindInlineSpoilerInteraction method must exist in main.js")
        method_body = method_match.group(1)
        self.assertNotIn("if (this.mode === 'preview')", method_body,
                         "Inline spoiler toggle must not be restricted to preview mode")
        self.assertIn(".editor-inline-spoiler", method_body)
        self.assertIn("classList.remove('is-revealed')", method_body)
        self.assertIn("classList.add('is-revealed')", method_body)
        self.assertIn("setAttribute('data-revealed', 'true')", method_body)
        self.assertIn("removeAttribute('data-revealed')", method_body)

    def test_bubble_js_handles_inline_spoiler_format_and_active_state(self):
        """Ensure bubble.js handles inline-spoiler format click with formatText and updateActiveStates."""
        self.assertIn("format === 'inline-spoiler'", self.bubble_js)
        self.assertIn("this.editor.formatText(range.index, range.length, 'inline-spoiler', !isActive, 'user');", self.bubble_js)
        self.assertIn("this.editor.setSelection(range.index, range.length, 'silent');", self.bubble_js)
        self.assertIn(".editor-inline-spoiler", self.bubble_js)
        self.assertIn("btn.classList.toggle('is-active', isInsideInlineSpoiler)", self.bubble_js)


class TestCodeBlockRefinements(unittest.TestCase):
    """Test 2: Code block styling (theme.css light/dark and editor.css overrides)."""

    @classmethod
    def setUpClass(cls):
        cls.theme_css_path = os.path.join(FRONTEND_DIR, 'css', 'theme.css')
        with open(cls.theme_css_path, 'r', encoding='utf-8') as f:
            cls.theme_css = f.read()

        cls.editor_css_path = os.path.join(FRONTEND_DIR, 'css', 'editor.css')
        with open(cls.editor_css_path, 'r', encoding='utf-8') as f:
            cls.editor_css = f.read()

    def test_theme_css_code_block_variables(self):
        """Ensure theme.css defines clean light and dark palette for code blocks."""
        # Light theme in :root
        root_section = re.search(r':root\s*\{([^}]+)\}', self.theme_css)
        self.assertIsNotNone(root_section, ":root block must exist in theme.css")
        root_block = root_section.group(1)
        self.assertIn('--code-bg: #f8f9fa;', root_block)
        self.assertIn('--code-text: #24292f;', root_block)
        self.assertIn('--code-border: #e2e8f0;', root_block)

        # Dark theme in [data-theme="dark"]
        dark_section = re.search(r'\[data-theme="dark"\]\s*\{([^}]+)\}', self.theme_css)
        self.assertIsNotNone(dark_section, "Dark theme block must exist in theme.css")
        dark_block = dark_section.group(1)
        self.assertIn('--code-bg: #0e121e;', dark_block)
        self.assertIn('--code-text: #e6edf3;', dark_block)
        self.assertIn('--code-border: #222531;', dark_block)

    def test_editor_css_overrides_quill_code_block_container(self):
        """Ensure editor.css overrides Quill Snow dark defaults for code container and pre.ql-syntax."""
        container_rule = re.search(
            r'(\.ql-snow\s+\.ql-editor\s+\.ql-code-block-container[\s\S]*?)\{([^}]+)\}',
            self.editor_css
        )
        self.assertIsNotNone(container_rule, "Quill code block container override rule must exist")
        block = container_rule.group(2)
        self.assertIn('background-color: var(--code-bg);', block)
        self.assertIn('color: var(--code-text);', block)
        self.assertIn('border: 1px solid var(--code-border);', block)
        self.assertIn('font-family: var(--font-mono);', block)
        self.assertIn('position: relative;', block)
        self.assertIn('margin: 2.2em 0 1.2em 0;', block)

    def test_language_selector_styled_and_positioned_above_code(self):
        """Ensure language selector is positioned top: -26px with Onest font and does not overlap code."""
        selector_rule = re.search(
            r'(\.ql-code-block-container\s+select\.ql-ui[\s\S]*?)\{([^}]+)\}',
            self.editor_css
        )
        self.assertIsNotNone(selector_rule, "Language selector select.ql-ui rule must exist")
        block = selector_rule.group(2)
        self.assertIn('position: absolute;', block)
        self.assertIn('top: -26px;', block)
        self.assertIn('right: 0;', block)
        self.assertIn('height: 22px;', block)
        self.assertIn("font-family: 'Onest', sans-serif;", block)
        self.assertIn('font-size: 11px;', block)
        self.assertIn('font-weight: 500;', block)
        self.assertIn('background-color: var(--bg-hover);', block)
        self.assertIn('border: 1px solid var(--border-color);', block)
        self.assertIn('cursor: pointer;', block)
        self.assertIn('z-index: 5;', block)


class TestBlockSpoilerDynamicPlaceholder(unittest.TestCase):
    """Test 3: Block spoiler dynamic placeholder (:empty::before and empty initial values)."""

    @classmethod
    def setUpClass(cls):
        cls.blocks_js_path = os.path.join(FRONTEND_DIR, 'js', 'blocks.js')
        with open(cls.blocks_js_path, 'r', encoding='utf-8') as f:
            cls.blocks_js = f.read()

        cls.core_js_path = os.path.join(FRONTEND_DIR, 'js', 'core.js')
        with open(cls.core_js_path, 'r', encoding='utf-8') as f:
            cls.core_js = f.read()

        cls.editor_css_path = os.path.join(FRONTEND_DIR, 'css', 'editor.css')
        with open(cls.editor_css_path, 'r', encoding='utf-8') as f:
            cls.editor_css = f.read()

        cls.converter_js_path = os.path.join(FRONTEND_DIR, 'js', 'converter.js')
        with open(cls.converter_js_path, 'r', encoding='utf-8') as f:
            cls.converter_js = f.read()

    def test_blocks_js_inserts_empty_initial_spoiler_values(self):
        """Ensure '+' block menu inserts spoiler with empty strings rather than static placeholder text."""
        spoiler_insert_match = re.search(
            r"case 'spoiler':\s*this\.editor\.insertEmbed\(index,\s*'spoiler',\s*\{([^}]+)\}",
            self.blocks_js
        )
        self.assertIsNotNone(spoiler_insert_match, "Spoiler insertion block must exist in blocks.js")
        payload = spoiler_insert_match.group(1)
        self.assertIn("title: ''", payload)
        self.assertIn("body: ''", payload)

    def test_core_js_spoiler_blot_dynamic_placeholder(self):
        """Ensure SpoilerBlot sets data-placeholder attributes and attaches empty state cleanup listeners."""
        self.assertIn("summary.setAttribute('data-placeholder', 'Заголовок спойлера');", self.core_js)
        self.assertIn("body.setAttribute('data-placeholder', 'Скрытый текст спойлера...');", self.core_js)
        # Event listeners cleaning up <br> or empty content
        self.assertIn("el.innerHTML = '';", self.core_js)
        self.assertIn("el.addEventListener('keyup'", self.core_js)
        self.assertIn("el.addEventListener('input'", self.core_js)

    def test_editor_css_spoiler_placeholder_styles(self):
        """Ensure editor.css defines :empty::before styles using var(--text-placeholder)."""
        title_ph_match = re.search(r'\.editor-spoiler-title:empty::before\s*\{([^}]+)\}', self.editor_css)
        self.assertIsNotNone(title_ph_match, ".editor-spoiler-title:empty::before must exist")
        title_block = title_ph_match.group(1)
        self.assertIn('content: attr(data-placeholder);', title_block)
        self.assertIn('color: var(--text-placeholder);', title_block)
        self.assertIn('pointer-events: none;', title_block)

        body_ph_match = re.search(r'\.editor-spoiler-body:empty::before\s*\{([^}]+)\}', self.editor_css)
        self.assertIsNotNone(body_ph_match, ".editor-spoiler-body:empty::before must exist")
        body_block = body_ph_match.group(1)
        self.assertIn('content: attr(data-placeholder);', body_block)
        self.assertIn('color: var(--text-placeholder);', body_block)
        self.assertIn('pointer-events: none;', body_block)

    def test_converter_js_spoiler_fallback(self):
        """Ensure converter.js exports empty spoiler titles to default 'Спойлер'."""
        self.assertIn("(summary && summary.textContent.trim()) ? summary.textContent.trim() : 'Спойлер'", self.converter_js)


class TestOfflineFirstAndRegression(unittest.TestCase):
    """Test 4: Regression check on existing features and offline-first integrity."""

    def test_no_external_cdn_references_in_codebase(self):
        """Ensure 100% offline-first compliance (no http/https references to CDNs or fonts)."""
        target_files = [
            os.path.join(FRONTEND_DIR, 'css', 'editor.css'),
            os.path.join(FRONTEND_DIR, 'css', 'theme.css'),
            os.path.join(FRONTEND_DIR, 'js', 'main.js'),
            os.path.join(FRONTEND_DIR, 'js', 'core.js'),
            os.path.join(FRONTEND_DIR, 'js', 'blocks.js'),
            os.path.join(FRONTEND_DIR, 'js', 'bubble.js'),
            os.path.join(FRONTEND_DIR, 'js', 'converter.js'),
        ]
        external_url_pattern = re.compile(r'https?://(?!localhost|127\.0\.0\.1|www\.w3\.org)[^\s\'"<>]+')
        for file_path in target_files:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            # Allow XML namespaces like http://www.w3.org/2000/svg
            matches = [m for m in external_url_pattern.findall(content) if 'w3.org' not in m]
            self.assertEqual(len(matches), 0, f"Found external URLs in {file_path}: {matches}")

    def test_onest_font_usage(self):
        """Ensure Onest font is used across the system."""
        with open(os.path.join(FRONTEND_DIR, 'css', 'theme.css'), 'r', encoding='utf-8') as f:
            theme_css = f.read()
        self.assertIn("font-family: 'Onest'", theme_css)
        self.assertIn("--font-sans: 'Onest'", theme_css)


if __name__ == '__main__':
    unittest.main()
