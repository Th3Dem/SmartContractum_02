#!/usr/bin/env python3
"""
Test Suite: Design System, Onest Font, and Strict SVG Vector Iconography
Verification for task-07-design-system-and-onest-font:
  1. Local offline-first Onest font files in vendor/fonts/onest/
  2. Local @font-face and --font-sans definition in theme.css and editor.css
  3. Zero emojis in editor.html
  4. Sleek SVG vector icons across header, 13 block menu items, sidebar, status bar, modals
  5. Minimalist design system button specs and left-alignment of article title & editor
"""

import os
import re
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, 'frontend', 'public')


class TestDesignSystemAndIcons(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.editor_html_path = os.path.join(FRONTEND_DIR, 'editor.html')
        with open(cls.editor_html_path, 'r', encoding='utf-8') as f:
            cls.editor_html = f.read()

        cls.theme_css_path = os.path.join(FRONTEND_DIR, 'css', 'theme.css')
        with open(cls.theme_css_path, 'r', encoding='utf-8') as f:
            cls.theme_css = f.read()

        cls.editor_css_path = os.path.join(FRONTEND_DIR, 'css', 'editor.css')
        with open(cls.editor_css_path, 'r', encoding='utf-8') as f:
            cls.editor_css = f.read()

        cls.fonts_dir = os.path.join(FRONTEND_DIR, 'vendor', 'fonts', 'onest')

    # =========================================================================
    # 1. ONEST FONT FAMILY (100% OFFLINE-FIRST)
    # =========================================================================
    def test_onest_font_files_exist_locally(self):
        """Verify Onest woff2 font files exist in vendor/fonts/onest/ with non-zero size."""
        self.assertTrue(os.path.isdir(self.fonts_dir), f"Directory {self.fonts_dir} does not exist")

        required_fonts = [
            'onest-cyrillic.woff2',
            'onest-latin.woff2',
            'onest-cyrillic-ext.woff2'
        ]
        for font_file in required_fonts:
            full_path = os.path.join(self.fonts_dir, font_file)
            self.assertTrue(os.path.isfile(full_path), f"Font file {font_file} is missing")
            file_size = os.path.getsize(full_path)
            self.assertGreater(file_size, 5000, f"Font file {font_file} is too small ({file_size} bytes)")

    def test_font_face_and_theme_configuration(self):
        """Verify @font-face is defined locally and Onest is configured in theme.css and editor.css."""
        # Check theme.css @font-face
        self.assertIn("@font-face", self.theme_css)
        self.assertIn("font-family: 'Onest'", self.theme_css)
        self.assertIn("url('../vendor/fonts/onest/onest-cyrillic.woff2')", self.theme_css)
        self.assertIn("url('../vendor/fonts/onest/onest-latin.woff2')", self.theme_css)
        self.assertIn("url('../vendor/fonts/onest/onest-cyrillic-ext.woff2')", self.theme_css)

        # Check --font-sans definition
        self.assertIn("--font-sans: 'Onest'", self.theme_css)
        self.assertIn("--letter-spacing-base: -0.01em", self.theme_css)

        # Check editor.css font and letter-spacing
        self.assertIn("letter-spacing: -0.01em;", self.editor_css)
        self.assertIn("font-family: var(--font-sans);", self.editor_css)

    def test_zero_runtime_cdn_calls(self):
        """Verify zero external font CDN calls (100% offline-first)."""
        for css_content, filename in [(self.theme_css, 'theme.css'), (self.editor_css, 'editor.css'), (self.editor_html, 'editor.html')]:
            self.assertNotIn('fonts.googleapis.com', css_content, f"Found Google Fonts CDN call in {filename}")
            self.assertNotIn('fonts.gstatic.com', css_content, f"Found Google Fonts CDN call in {filename}")

    # =========================================================================
    # 2. ZERO EMOJIS IN EDITOR.HTML
    # =========================================================================
    def test_zero_emojis_in_editor_html(self):
        """Verify zero emojis in editor.html (no 📁, 📤, 🌐, 📝, 💾, 📥, 🌓, ⌨️, 🗑️, ✨, 💡, 📋, 🖼️, 👤, ⚓)."""
        forbidden_emojis = [
            '📁', '📤', '🌐', '📝', '💾', '📥', '🌓', '⌨️', '⌨', '🗑️', '🗑',
            '✨', '💡', '📋', '🖼️', '🖼', '👤', '⚓', '✏️', '✏', '👁️', '👁',
            '⏱️', '⏱', '🔤', '⚡', '📊', '💻', '🔄'
        ]
        for emoji in forbidden_emojis:
            self.assertNotIn(emoji, self.editor_html, f"Forbidden emoji '{emoji}' found in editor.html")

        # Full Unicode range check for emojis
        emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]|[\u2b50]')
        matches = emoji_pattern.findall(self.editor_html)
        self.assertEqual(len(matches), 0, f"Unexpected emoji characters found in editor.html: {matches}")

    # =========================================================================
    # 3. SLEEK SVG VECTOR ICONS
    # =========================================================================
    def test_header_svg_icons(self):
        """Verify header buttons have clean SVG vector icons, Antigravity Writer and more actions removed."""
        # Main Header Branding: SmartContractum in #appHeader
        header_match = re.search(r'<header[^>]*id=["\']appHeader["\'][^>]*>(.*?)</header>', self.editor_html, re.DOTALL)
        self.assertIsNotNone(header_match, "appHeader not found")
        self.assertIn('SmartContractum', header_match.group(1))

        # Antigravity Writer removed from sub-bar per requirement 4
        self.assertNotIn('Antigravity Writer', self.editor_html)

        # Drafts button in editor document bar
        drafts_btn_match = re.search(r'<button id="btn-drafts-modal"[^>]*>(.*?)</button>', self.editor_html, re.DOTALL)
        self.assertIsNotNone(drafts_btn_match, "btn-drafts-modal not found")
        self.assertIn('<svg', drafts_btn_match.group(1))

        # Mode toggle removed from header by user request
        self.assertNotIn('id="mode-toggle"', self.editor_html)

        # More actions 3-dot dropdown button removed per requirement 10
        self.assertNotIn('id="btn-more-actions"', self.editor_html)

        # Clear document button moved to status bar with clean SVG icon per requirement 11
        clear_btn_match = re.search(r'<button[^>]*id="btn-clear-doc"[^>]*>(.*?)</button>', self.editor_html, re.DOTALL)
        self.assertIsNotNone(clear_btn_match, "btn-clear-doc not found in editor.html")
        self.assertIn('<svg', clear_btn_match.group(1), "btn-clear-doc missing SVG icon")

        # Global theme toggle in main header
        self.assertIn('id="btnThemeToggle"', self.editor_html)

        # Verify #btn-export-dropdown and #export-dropdown-menu are NOT present
        self.assertNotIn('id="btn-export-dropdown"', self.editor_html)
        self.assertNotIn('id="export-dropdown-menu"', self.editor_html)

    def test_block_menu_all_13_items_have_unified_svg_icons(self):
        """Verify all 13 items in '+' block menu have unified 18x18 SVG vector icons."""
        menu_match = re.search(r'<div id="block-menu"[^>]*>(.*?)(?:<!-- Node Controls|<div id="node-controls")', self.editor_html, re.DOTALL)
        self.assertIsNotNone(menu_match, "Block menu container not found")
        menu_content = menu_match.group(1)

        expected_blocks = [
            'header',
            'blockquote',
            'bullet-list',
            'ordered-list',
            'media',
            'image',
            'divider',
            'code-block',
            'formula',
            'spoiler',
            'anchor',
            'person',
            'table'
        ]

        for block_name in expected_blocks:
            item_pattern = rf'<div class="block-menu-item" data-block="{block_name}"[^>]*>(.*?)</div>\s*(?:<!--|<div class="block-menu-item"|</div>)'
            item_match = re.search(item_pattern, menu_content, re.DOTALL)
            self.assertIsNotNone(item_match, f"Block item data-block='{block_name}' not found")
            item_html = item_match.group(1)

            # Check that .block-menu-icon contains SVG with width="18" height="18"
            icon_match = re.search(r'<div class="block-menu-icon"[^>]*>(.*?)</div>', item_html, re.DOTALL)
            self.assertIsNotNone(icon_match, f"Icon container for {block_name} not found")
            icon_content = icon_match.group(1)

            self.assertIn('<svg', icon_content, f"Block '{block_name}' missing SVG icon")
            self.assertIn('width="18"', icon_content, f"Block '{block_name}' SVG not width 18")
            self.assertIn('height="18"', icon_content, f"Block '{block_name}' SVG not height 18")
            self.assertIn('stroke-width="2"', icon_content, f"Block '{block_name}' SVG not stroke-width 2")

    def test_sidebar_widget_svg_icons(self):
        """Verify sidebar widgets: Typograph, Author Guide, and Checklist in right sidebar with clean SVG icons."""
        # Right sidebar container
        right_zone_match = re.search(r'<aside[^>]*class="[^"]*side-zone-right[^"]*"[^>]*>(.*?)</aside>', self.editor_html, re.DOTALL)
        self.assertIsNotNone(right_zone_match, "side-zone-right not found")
        right_content = right_zone_match.group(1)

        # Order of 3 widgets in right sidebar: Typograph -> Author Guide -> Checklist
        pos_typo = right_content.find('id="widget-typograph"')
        pos_guide = right_content.find('id="widget-author-guide"')
        pos_check = right_content.find('id="widget-checklist"')
        self.assertTrue(0 <= pos_typo < pos_guide < pos_check, "Widgets must be ordered: Typograph, Author Guide, Checklist")

        # 1. Typograph Widget: has thematic SVG icon in header, no redundant SVG in button, status has SVG
        typo_widget_match = re.search(r'<div[^>]*id="widget-typograph"[^>]*>(.*?)</div>\s*<!-- Card 2', right_content, re.DOTALL)
        self.assertIsNotNone(typo_widget_match, "widget-typograph not found in right sidebar")
        typo_content = typo_widget_match.group(1)
        self.assertIn('<span class="widget-icon">', typo_content)
        self.assertIn('<svg', typo_content)

        typo_btn_match = re.search(r'<button[^>]*id="btn-typograph"[^>]*>(.*?)</button>', typo_content, re.DOTALL)
        self.assertIsNotNone(typo_btn_match, "btn-typograph not found")
        self.assertNotIn('<svg', typo_btn_match.group(1), "btn-typograph should not contain redundant SVG icon")
        self.assertIn('id="typograph-status"', typo_content)

        # 2. Author guide widget: header has thematic SVG icon, tips have clean SVG icons
        guide_widget_match = re.search(r'<div[^>]*id="widget-author-guide"[^>]*>(.*?)</div>\s*<!-- Card 3', right_content, re.DOTALL)
        self.assertIsNotNone(guide_widget_match, "widget-author-guide not found in right sidebar")
        guide_header_match = re.search(r'<div[^>]*class="[^"]*widget-header[^"]*"[^>]*>(.*?)</div>', guide_widget_match.group(1), re.DOTALL)
        self.assertIsNotNone(guide_header_match, "widget-header not found in widget-author-guide")
        self.assertIn('<svg', guide_header_match.group(1), "widget-author-guide header must have thematic SVG icon")
        tip_svgs = re.findall(r'<span class="guide-tip-icon">\s*<svg[^>]*stroke-width="2"', guide_widget_match.group(1))
        self.assertEqual(len(tip_svgs), 4, f"Expected 4 tip SVG icons with stroke-width 2, found {len(tip_svgs)}")

        # 3. Checklist widget: header with thematic SVG icon
        check_widget_match = re.search(r'<div[^>]*id="widget-checklist"[^>]*>(.*?)</aside>', self.editor_html, re.DOTALL)
        self.assertIsNotNone(check_widget_match, "widget-checklist not found in right sidebar")
        self.assertIn('<span class="widget-icon">', check_widget_match.group(1))
        self.assertIn('<svg', check_widget_match.group(1))

    def test_status_bar_and_table_action_bar_svg_icons(self):
        """Verify status bar stats and table action bar have SVG icons."""
        # Stats items in footer status bar
        footer_match = re.search(r'<footer class="app-status-bar"[^>]*>(.*?)</footer>', self.editor_html, re.DOTALL)
        self.assertIsNotNone(footer_match, "app-status-bar not found")
        footer_content = footer_match.group(1)

        # 3 stat items: words, chars, reading time
        stats_items_with_svg = len(re.findall(r'<div class="doc-stats-item"[^>]*>.*?<svg', footer_content, re.DOTALL))
        self.assertEqual(stats_items_with_svg, 3, f"Expected 3 stats items with SVG in status bar, found {stats_items_with_svg}")

        # Undo and Redo buttons in history controls
        self.assertIn('<button type="button" class="status-btn" id="btn-undo"', footer_content)
        self.assertIn('<button type="button" class="status-btn" id="btn-redo"', footer_content)
        history_svgs = len(re.findall(r'<div class="history-controls">.*?<svg.*?<svg', footer_content, re.DOTALL))
        self.assertEqual(history_svgs, 1, "Expected undo and redo SVGs in history controls")

        # Table action bar delete buttons
        table_bar_match = re.search(r'<div id="table-action-bar"[^>]*>(.*?)</div>', self.editor_html, re.DOTALL)
        self.assertIsNotNone(table_bar_match, "table-action-bar not found")
        self.assertIn('<svg', table_bar_match.group(1))

    def test_modals_svg_close_buttons(self):
        """Verify all modal close buttons have SVG icons, ensuring drafts, shortcuts, image,
        and publication modals close buttons have SVGs, and deleted export buttons are absent."""
        # Check all modal-close-btn have <svg
        close_btns = re.findall(r'<button class="modal-close-btn"[^>]*>(.*?)</button>', self.editor_html, re.DOTALL)
        self.assertGreaterEqual(len(close_btns), 10, f"Expected at least 10 modals, found {len(close_btns)}")
        for idx, btn_html in enumerate(close_btns):
            self.assertIn('<svg', btn_html, f"Modal close button #{idx + 1} does not have SVG")

        # Explicitly verify close buttons for drafts, shortcuts, image, publication modals
        for modal_id in ['drafts-modal', 'shortcuts-modal', 'image-modal', 'publication-modal']:
            pattern = rf'<div[^>]*id="{modal_id}"[\s\S]*?<button[^>]*class="modal-close-btn"[^>]*>([\s\S]*?)</button>'
            btn_match = re.search(pattern, self.editor_html)
            self.assertIsNotNone(btn_match, f"modal-close-btn in {modal_id} not found")
            self.assertIn('<svg', btn_match.group(1), f"modal-close-btn in {modal_id} missing SVG icon")

        # Ensure deleted export modal and buttons are absent
        self.assertNotIn('id="export-modal"', self.editor_html)
        self.assertNotIn('id="export-copy-btn"', self.editor_html)
        self.assertNotIn('id="export-download-btn"', self.editor_html)

    # =========================================================================
    # 4. MINIMALIST DESIGN SYSTEM & ALIGNMENT
    # =========================================================================
    def test_button_design_system_in_css(self):
        """Verify .btn, .btn-icon, .bubble-btn have compact height, 8px radius, clean border, flex alignment."""
        # .btn styling
        self.assertIn('.btn {', self.editor_css)
        self.assertIn('height: 34px;', self.editor_css)
        self.assertIn('border-radius: var(--radius-md);', self.editor_css)
        self.assertIn('display: inline-flex;', self.editor_css)
        self.assertIn('align-items: center;', self.editor_css)
        self.assertIn('justify-content: center;', self.editor_css)

        # .bubble-btn styling
        self.assertIn('.bubble-btn {', self.editor_css)
        self.assertIn('width: 32px;', self.editor_css)
        self.assertIn('height: 32px;', self.editor_css)
        self.assertIn('border-radius: var(--radius-md);', self.editor_css)

        # .block-menu-icon styling (32x32px, subtle background, centered)
        self.assertIn('.block-menu-icon {', self.editor_css)
        self.assertIn('width: 32px;', self.editor_css)
        self.assertIn('height: 32px;', self.editor_css)
        self.assertIn('background-color: var(--bg-hover);', self.editor_css)

    def test_article_title_and_editor_exact_alignment(self):
        """Verify #article-title and .ql-editor are aligned to the exact same left line (padding: 0)."""
        self.assertIn('.article-title-container {', self.editor_css)
        self.assertIn('padding: 0;', self.editor_css)

        self.assertIn('.article-title-input {', self.editor_css)
        self.assertIn('padding: 0;', self.editor_css)

        self.assertIn('.ql-editor {', self.editor_css)
        self.assertIn('padding: 0 !important;', self.editor_css)


if __name__ == '__main__':
    unittest.main()
