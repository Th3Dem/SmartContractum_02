#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for Editor UX Refinements (task-05-editor-ux-refinements):
1. Tool "Заголовок" in "+" menu: instant H2 conversion without submenu, universal H2 styling.
2. Button "Смотреть на источнике" in media element: explicit click listener, window.open, https:// normalization.
3. Replace 3-dots button with direct delete trash can button.
4. Drag & drop across full width from edge to edge (left handle vertical dragging, left: 0; right: 0; drop line).
5. Contextual bubble toolbar: strictly above selection without colors.
6. Clean up "+" menu: removed checklist and "Дополнительно" divider, table in main list.
"""

import os
import re
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, 'frontend', 'public')


class TestEditorUXRefinements(unittest.TestCase):
    """Verify all 6 UX Refinements in HTML, JS, and CSS."""

    def setUp(self):
        with open(os.path.join(FRONTEND_DIR, 'editor.html'), 'r', encoding='utf-8') as f:
            self.html = f.read()

        with open(os.path.join(FRONTEND_DIR, 'css', 'editor.css'), 'r', encoding='utf-8') as f:
            self.css = f.read()

        with open(os.path.join(FRONTEND_DIR, 'js', 'blocks.js'), 'r', encoding='utf-8') as f:
            self.blocks_js = f.read()

        with open(os.path.join(FRONTEND_DIR, 'js', 'core.js'), 'r', encoding='utf-8') as f:
            self.core_js = f.read()

        with open(os.path.join(FRONTEND_DIR, 'js', 'node-controls.js'), 'r', encoding='utf-8') as f:
            self.node_js = f.read()

        with open(os.path.join(FRONTEND_DIR, 'js', 'bubble.js'), 'r', encoding='utf-8') as f:
            self.bubble_js = f.read()

    # --------------------------------------------------------------------------
    # 1. TOOL "ЗАГОЛОВОК" IN "+" MENU
    # --------------------------------------------------------------------------
    def test_refinement_1_header_instant_conversion_and_styling(self):
        """1. Header in + menu: instant H2 conversion, no submenu, universal H2 styling."""
        # Check description in HTML
        header_item_match = re.search(
            r'<div class="block-menu-item" data-block="header"[^>]*>.*?<span class="block-menu-desc">([^<]+)</span>',
            self.html,
            re.DOTALL
        )
        self.assertIsNotNone(header_item_match)
        self.assertEqual(header_item_match.group(1).strip(), "Заголовок раздела")

        # Submenu element removed from HTML
        self.assertNotIn('id="header-submenu"', self.html)
        self.assertNotIn('class="header-submenu"', self.html)

        # In blocks.js: clicking header immediately converts to H2 and closes menu
        self.assertIn("this.insertHeader(2)", self.blocks_js)
        self.assertNotIn("toggleHeaderSubmenu", self.blocks_js)

        # In CSS: .ql-editor h2 styling (1.5rem / 24px, 700 font-weight, 1.3 line-height)
        h2_match = re.search(r'\.ql-editor\s+h2\s*\{([^}]+)\}', self.css)
        self.assertIsNotNone(h2_match, ".ql-editor h2 CSS rule not found")
        h2_props = h2_match.group(1)
        self.assertIn('font-size: 1.5rem', h2_props)
        self.assertIn('font-weight: 700', h2_props)
        self.assertIn('line-height: 1.3', h2_props)

        # Header submenu styles removed from CSS
        self.assertNotIn('.header-submenu', self.css)
        self.assertNotIn('.header-sub-item', self.css)

    # --------------------------------------------------------------------------
    # 2. BUTTON "СМОТРЕТЬ НА ИСТОЧНИКЕ" IN MEDIA ELEMENT
    # --------------------------------------------------------------------------
    def test_refinement_2_media_source_link_click_handler(self):
        """2. Fallback link in video element has explicit click listener opening new tab."""
        self.assertIn('MediaEmbedBlot', self.core_js)
        # Explicit click listener
        self.assertIn("linkEl.addEventListener('click'", self.core_js)
        self.assertIn("e.preventDefault()", self.core_js)
        self.assertIn("e.stopPropagation()", self.core_js)
        self.assertIn("window.open(originalUrl, '_blank', 'noopener,noreferrer')", self.core_js)

        # URL protocol normalization (prepend https:// if missing)
        self.assertIn("^https?:\\/\\/", self.core_js)
        self.assertIn("'https://' + originalUrl", self.core_js)

    # --------------------------------------------------------------------------
    # 3. REPLACE 3-DOTS BUTTON WITH TRASH/DELETE BUTTON
    # --------------------------------------------------------------------------
    def test_refinement_3_trash_button_direct_deletion(self):
        """3. Replace 3-dots button with direct delete trash button and remove dropdown."""
        # HTML elements
        self.assertIn('id="btn-node-direct-delete"', self.html)
        self.assertIn('title="Удалить блок"', self.html)
        self.assertIn('aria-label="Удалить блок"', self.html)
        self.assertIn('class="node__delete', self.html)
        # Polyline and path for trash can icon
        self.assertIn('<polyline points="3 6 5 6 21 6"></polyline>', self.html)
        self.assertNotIn('id="node-action-menu"', self.html)

        # node-controls.js click handling
        self.assertIn('btn-node-direct-delete', self.node_js)
        self.assertIn('this.deleteBlock()', self.node_js)

        # CSS hover styling with danger color #ef4444
        delete_hover_match = re.search(r'\.node__delete:hover\s*\{([^}]+)\}', self.css)
        self.assertIsNotNone(delete_hover_match, ".node__delete:hover rule not found in CSS")
        self.assertIn('#ef4444', delete_hover_match.group(1))

    # --------------------------------------------------------------------------
    # 4. DRAG & DROP ACROSS FULL WIDTH FROM EDGE TO EDGE
    # --------------------------------------------------------------------------
    def test_refinement_4_drag_and_drop_full_width(self):
        """4. Drag & Drop listens across editorCard/document and drop line spans full width."""
        # node-controls.js listeners on editorCard and document
        self.assertIn("this.editorCard.addEventListener('dragover'", self.node_js)
        self.assertIn("this.editorCard.addEventListener('drop'", self.node_js)
        self.assertIn("document.addEventListener('dragover'", self.node_js)
        self.assertIn("document.addEventListener('drop'", self.node_js)

        # Dynamic clientY comparison against block bounding rects
        self.assertIn("e.clientY >= rect.top && e.clientY <= rect.bottom", self.node_js)
        self.assertIn("isAbove", self.node_js)

        # CSS: .node-drop-line spans edge-to-edge (left: 0; right: 0;)
        drop_line_match = re.search(r'\.node-drop-line\s*\{([^}]+)\}', self.css)
        self.assertIsNotNone(drop_line_match, ".node-drop-line rule not found in CSS")
        props = drop_line_match.group(1)
        self.assertIn('left: 0', props)
        self.assertIn('right: 0', props)

    # --------------------------------------------------------------------------
    # 5. CONTEXTUAL BUBBLE TOOLBAR
    # --------------------------------------------------------------------------
    def test_refinement_5_bubble_toolbar_strictly_above_without_colors(self):
        """5. Contextual bubble toolbar strictly above selection without colors."""
        # Positioned strictly above selection in bubble.js
        self.assertIn("Math.max(10, bounds.top)", self.bubble_js)
        self.assertNotIn("placeBelow", self.bubble_js)
        self.assertNotIn("position-below", self.bubble_js)

        # Swatch listeners removed from bubble.js
        self.assertNotIn("color-swatch", self.bubble_js)
        self.assertNotIn("reset-text-color", self.bubble_js)
        self.assertNotIn("reset-bg-color", self.bubble_js)

        # HTML: bubble-more-menu contains alignment, but no color groups
        more_menu_match = re.search(r'<div id="bubble-more-menu"[^>]*>(.*?)</div>\s*</div>\s*</div>', self.html, re.DOTALL)
        self.assertIsNotNone(more_menu_match)
        more_menu_content = more_menu_match.group(1)
        self.assertIn('Выравнивание', more_menu_content)
        self.assertIn('data-align=', more_menu_content)
        self.assertNotIn('Цвет текста', more_menu_content)
        self.assertNotIn('Цвет фона (выделение)', more_menu_content)
        self.assertNotIn('data-color=', more_menu_content)
        self.assertNotIn('data-bg=', more_menu_content)

        # CSS: position-below class removed
        self.assertNotIn('.bubble-toolbar.position-below', self.css)

    # --------------------------------------------------------------------------
    # 6. CLEAN UP "+" MENU
    # --------------------------------------------------------------------------
    def test_refinement_6_clean_plus_menu(self):
        """6. Clean up '+' menu: checklist and 'Дополнительно' removed, table in main list."""
        menu_match = re.search(r'<div id="block-menu"[^>]*>(.*?)(?:<!-- Node Controls|<div id="node-controls")', self.html, re.DOTALL)
        self.assertIsNotNone(menu_match)
        block_menu_content = menu_match.group(1)

        # Checklist removed from block menu
        self.assertNotIn('data-block="checklist"', block_menu_content)
        self.assertNotIn('Чек-лист', block_menu_content)

        # "Дополнительно" divider and title removed from block menu
        self.assertNotIn('Дополнительно', block_menu_content)
        self.assertNotIn('block-menu-group-title', block_menu_content)

        # Table is kept in main block menu
        self.assertIn('data-block="table"', block_menu_content)
        self.assertIn('Таблица', block_menu_content)

        # blocks.js does not have checklist
        self.assertNotIn("case 'checklist':", self.blocks_js)
        self.assertIn("case 'table':", self.blocks_js)


if __name__ == '__main__':
    unittest.main()
