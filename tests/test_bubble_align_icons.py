#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for Task 06: Bubble Toolbar Text Alignment Icons & Removal of 'Еще' dropdown.
"""

import os
import re
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, 'frontend', 'public')


class TestBubbleAlignIcons(unittest.TestCase):
    """Verify alignment icons in bubble toolbar and removal of more dropdown."""

    def setUp(self):
        with open(os.path.join(FRONTEND_DIR, 'editor.html'), 'r', encoding='utf-8') as f:
            self.html = f.read()

        with open(os.path.join(FRONTEND_DIR, 'css', 'editor.css'), 'r', encoding='utf-8') as f:
            self.css = f.read()

        with open(os.path.join(FRONTEND_DIR, 'js', 'bubble.js'), 'r', encoding='utf-8') as f:
            self.bubble_js = f.read()

    def test_bubble_html_more_dropdown_removed(self):
        """Verify #bubble-more-btn, #bubble-more-menu, and dropdown wrapper are completely removed."""
        self.assertNotIn('id="bubble-more-btn"', self.html)
        self.assertNotIn('id="bubble-more-menu"', self.html)
        self.assertNotIn('bubble-dropdown-wrapper', self.html)
        self.assertNotIn('bubble-more-btn', self.html)
        self.assertNotIn('bubble-more-menu', self.html)
        self.assertNotIn('bubble-align-btn', self.html)

    def test_bubble_html_align_buttons_structure(self):
        """Verify 4 align buttons are present directly in #bubble-toolbar after divider."""
        toolbar_match = re.search(r'<div id="bubble-toolbar"[^>]*>(.*?)</div>\s*<!-- Floating Contextual Table Action Bar', self.html, re.DOTALL)
        self.assertIsNotNone(toolbar_match, "Bubble toolbar container not found")
        toolbar_content = toolbar_match.group(1)

        # Split at divider
        parts = toolbar_content.split('<div class="bubble-divider"></div>')
        self.assertEqual(len(parts), 2, "Expected exactly one bubble-divider inside #bubble-toolbar")
        align_part = parts[1]

        # Extract all buttons in align section
        buttons = re.findall(r'<button\b([^>]*)>(.*?)</button>', align_part, re.DOTALL)
        self.assertEqual(len(buttons), 4, f"Expected 4 buttons after divider, found {len(buttons)}")

        expected_align_buttons = [
            {
                'format': 'align',
                'value': '',
                'title': 'По левому краю',
                'aria-label': 'По левому краю',
                'lines': ['x1="3" y1="6" x2="21" y2="6"', 'x1="3" y1="12" x2="15" y2="12"', 'x1="3" y1="18" x2="18" y2="18"']
            },
            {
                'format': 'align',
                'value': 'center',
                'title': 'По центру',
                'aria-label': 'По центру',
                'lines': ['x1="3" y1="6" x2="21" y2="6"', 'x1="6" y1="12" x2="18" y2="12"', 'x1="4" y1="18" x2="20" y2="18"']
            },
            {
                'format': 'align',
                'value': 'right',
                'title': 'По правому краю',
                'aria-label': 'По правому краю',
                'lines': ['x1="3" y1="6" x2="21" y2="6"', 'x1="9" y1="12" x2="21" y2="12"', 'x1="6" y1="18" x2="21" y2="18"']
            },
            {
                'format': 'align',
                'value': 'justify',
                'title': 'По ширине',
                'aria-label': 'По ширине',
                'lines': ['x1="3" y1="6" x2="21" y2="6"', 'x1="3" y1="12" x2="21" y2="12"', 'x1="3" y1="18" x2="21" y2="18"']
            }
        ]

        for i, (attrs, body) in enumerate(buttons):
            expected = expected_align_buttons[i]
            self.assertIn('class="bubble-btn"', attrs, f"Button {i+1} must have class bubble-btn")
            self.assertIn(f'data-format="{expected["format"]}"', attrs, f"Button {i+1} format mismatch")
            self.assertIn(f'data-value="{expected["value"]}"', attrs, f"Button {i+1} value mismatch")
            self.assertIn(f'title="{expected["title"]}"', attrs, f"Button {i+1} title mismatch")
            self.assertIn(f'aria-label="{expected["aria-label"]}"', attrs, f"Button {i+1} aria-label mismatch")

            # Check SVG size and coordinates
            self.assertIn('<svg width="15" height="15" viewBox="0 0 24 24"', body)
            for line_coord in expected['lines']:
                self.assertIn(line_coord, body)

    def test_bubble_js_no_more_references(self):
        """Verify bubble.js has no references to moreBtn, moreMenu, or bubble-align-btn."""
        self.assertNotIn('bubble-more-btn', self.bubble_js)
        self.assertNotIn('bubble-more-menu', self.bubble_js)
        self.assertNotIn('moreBtn', self.bubble_js)
        self.assertNotIn('moreMenu', self.bubble_js)
        self.assertNotIn('bubble-align-btn', self.bubble_js)

    def test_bubble_js_align_handlers(self):
        """Verify bubble.js handles alignment format and active states."""
        # Align click format
        self.assertIn("if (format === 'align')", self.bubble_js)
        self.assertIn("this.editor.format('align', value || false);", self.bubble_js)
        self.assertIn("this.updateActiveStates(range);", self.bubble_js)

        # Active state toggle logic for align
        self.assertIn("if (fmt === 'align')", self.bubble_js)
        self.assertIn("const currentAlign = formats.align || '';", self.bubble_js)
        self.assertIn("btn.classList.toggle('is-active', (val || '') === currentAlign);", self.bubble_js)

    def test_bubble_css_clean_and_consistent(self):
        """Verify editor.css has no obsolete more-menu styles and contains .bubble-btn."""
        self.assertNotIn('.bubble-more-btn', self.css)
        self.assertNotIn('.bubble-more-menu', self.css)
        self.assertNotIn('.more-menu-group', self.css)
        self.assertNotIn('.more-menu-title', self.css)
        self.assertNotIn('.bubble-align-btn', self.css)
        self.assertNotIn('.align-button-group', self.css)

        # Ensure .bubble-btn and active state are defined
        self.assertIn('.bubble-btn', self.css)
        self.assertIn('.bubble-btn.is-active', self.css)


if __name__ == '__main__':
    unittest.main()
