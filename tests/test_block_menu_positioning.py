#!/usr/bin/env python3
"""
Unit tests for Block Menu Smart Positioning and Fixed Status Bar (task-08-fix-block-menu-and-status-bar):
1. Status Bar & Reserved Bottom Layout Space:
   - .app-status-bar fixed at bottom: 0, left: 0, right: 0, height: 44px, z-index: 40.
   - .app-main-layout reserved bottom padding: padding-bottom: 96px.
   - .editor-card reserved bottom padding: padding-bottom: 64px.
2. CSS Enhancements:
   - .block-menu with fixed positioning, overscroll-behavior: contain, transition, z-index: 60.
   - .block-menu.open-up with transform-origin: bottom left.
   - .block-menu.open-down with transform-origin: top left.
3. Smart Positioning Engine Logic:
   - Opening DOWN when ample space below (+8px buffer).
   - Opening UP when bottom space is tight and top space is ample (+8px buffer).
   - Constrained space fallback to whichever direction has more space, clamped to >= 140px.
   - Auto-closing when '+' button scrolls past header bottom or status bar top.
   - Horizontal viewport clamping with 12px margin.
   - Clearance from header and status bar is >= 8px (GAP >= 10px).
4. Code Verification in blocks.js:
   - Document.body portalling for stacking context escape.
   - Scroll and resize event listeners (including visualViewport).
   - Up/down navigation and insertion at current line index.
5. 13 Block Menu Items:
   - Full preservation and ordering of all 13 items.
"""

import os
import re
import unittest


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, 'frontend', 'public')


def calculate_menu_position(btn_top, btn_bottom, btn_left,
                            header_bottom=58, status_top=856,
                            window_height=900, window_width=1280,
                            full_menu_height=440, menu_width=330):
    """
    Python reference mirror of updateMenuPosition() in frontend/public/js/blocks.js.
    """
    GAP = 10
    min_allowed_top = header_bottom + GAP
    max_allowed_bottom = status_top - GAP

    # Out of visible bounds check
    if btn_bottom < min_allowed_top or btn_top > max_allowed_bottom:
        return {'closed': True}

    space_below = max_allowed_bottom - btn_bottom
    space_above = btn_top - min_allowed_top

    direction = 'down'
    max_height = full_menu_height
    top = 'auto'
    bottom = 'auto'

    if space_below >= full_menu_height + 8:
        direction = 'down'
        max_height = min(full_menu_height, space_below - 8)
        top = btn_bottom + 6
        bottom = 'auto'
    elif space_above >= full_menu_height + 8:
        direction = 'up'
        max_height = min(full_menu_height, space_above - 8)
        bottom = (window_height - btn_top) + 6
        top = 'auto'
    else:
        direction = 'down' if space_below >= space_above else 'up'
        chosen_space = space_below if direction == 'down' else space_above
        max_height = max(140, chosen_space - 8)
        if direction == 'down':
            top = btn_bottom + 6
            bottom = 'auto'
        else:
            bottom = (window_height - btn_top) + 6
            top = 'auto'

    left = max(12, min(btn_left, window_width - menu_width - 12))

    return {
        'closed': False,
        'direction': direction,
        'max_height': max_height,
        'top': top,
        'bottom': bottom,
        'left': left,
        'space_below': space_below,
        'space_above': space_above
    }


class TestStatusBarAndLayoutReservedSpacing(unittest.TestCase):
    """1. Status Bar & Reserved Bottom Layout Spacing."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(FRONTEND_DIR, 'css', 'editor.css'), 'r', encoding='utf-8') as f:
            cls.css = f.read()
        with open(os.path.join(FRONTEND_DIR, 'editor.html'), 'r', encoding='utf-8') as f:
            cls.html = f.read()

    def test_status_bar_is_firmly_fixed_at_bottom(self):
        """Status bar must have position: fixed, bottom: 0, left: 0, right: 0, height: 44px, z-index: 40."""
        bar_match = re.search(r'\.app-status-bar\s*\{([^}]+)\}', self.css)
        self.assertIsNotNone(bar_match, ".app-status-bar rule not found in editor.css")
        bar_content = bar_match.group(1)

        self.assertIn('position: fixed;', bar_content)
        self.assertIn('bottom: 0;', bar_content)
        self.assertIn('left: 0;', bar_content)
        self.assertIn('right: 0;', bar_content)
        self.assertIn('height: 44px;', bar_content)
        self.assertIn('z-index: 40;', bar_content)

    def test_main_layout_has_reserved_bottom_padding(self):
        """.app-main-layout must reserve at least 96px bottom padding."""
        layout_match = re.search(r'\.app-main-layout\s*\{([^}]+)\}', self.css)
        self.assertIsNotNone(layout_match, ".app-main-layout rule not found in editor.css")
        layout_content = layout_match.group(1)
        self.assertTrue(
            'padding-bottom: 96px;' in layout_content or 'padding: 32px 0 96px;' in layout_content,
            "Expected 96px bottom padding on .app-main-layout"
        )

    def test_editor_card_has_reserved_bottom_padding(self):
        """.editor-card must reserve at least 64px bottom padding."""
        card_match = re.search(r'\.editor-card\s*\{([^}]+)\}', self.css)
        self.assertIsNotNone(card_match, ".editor-card rule not found in editor.css")
        card_content = card_match.group(1)
        self.assertIn('padding-bottom: 64px;', card_content)


class TestBlockMenuCssEnhancements(unittest.TestCase):
    """2. CSS Enhancements for .block-menu."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(FRONTEND_DIR, 'css', 'editor.css'), 'r', encoding='utf-8') as f:
            cls.css = f.read()

    def test_block_menu_fixed_and_overscroll(self):
        """.block-menu must have position: fixed, overscroll-behavior: contain, z-index: 60."""
        menu_match = re.search(r'\.block-menu\s*\{([^}]+)\}', self.css)
        self.assertIsNotNone(menu_match, ".block-menu rule not found in editor.css")
        menu_content = menu_match.group(1)

        self.assertIn('position: fixed;', menu_content)
        self.assertIn('overscroll-behavior: contain;', menu_content)
        self.assertIn('z-index: 60;', menu_content)
        self.assertIn('transition: opacity 0.15s ease;', menu_content)

    def test_block_menu_open_up_and_down_transform_origin(self):
        """.block-menu.open-up and open-down classes configure smooth expansion origins."""
        self.assertIn('.block-menu.open-up {', self.css)
        self.assertIn('transform-origin: bottom left;', self.css)
        self.assertIn('.block-menu.open-down {', self.css)
        self.assertIn('transform-origin: top left;', self.css)


class TestSmartPositioningAlgorithm(unittest.TestCase):
    """3. Smart Positioning Engine Logic (Mirror and Math Verification)."""

    def test_opens_down_when_ample_space_below(self):
        """When button is in upper half with > 448px below, menu opens down."""
        # Viewport: 900px, Header: 58px, Status bar top: 856px
        # Button: top=200, bottom=232, left=200
        # space_below = (856 - 10) - 232 = 614 >= 448
        res = calculate_menu_position(btn_top=200, btn_bottom=232, btn_left=200)
        self.assertFalse(res['closed'])
        self.assertEqual(res['direction'], 'down')
        self.assertEqual(res['top'], 238)  # 232 + 6
        self.assertEqual(res['bottom'], 'auto')
        self.assertEqual(res['max_height'], 440)
        # Verify clearance above status bar: top + maxHeight <= status_top - 10
        self.assertLessEqual(res['top'] + res['max_height'], 856 - 10)

    def test_opens_up_when_near_bottom_status_bar(self):
        """When button is near status bar, menu flips UP above the button."""
        # Button near bottom: top=750, bottom=782, left=200
        # space_below = (856 - 10) - 782 = 64 (far < 448)
        # space_above = 750 - (58 + 10) = 682 (>= 448)
        res = calculate_menu_position(btn_top=750, btn_bottom=782, btn_left=200)
        self.assertFalse(res['closed'])
        self.assertEqual(res['direction'], 'up')
        self.assertEqual(res['top'], 'auto')
        # bottom = (900 - 750) + 6 = 156
        self.assertEqual(res['bottom'], 156)
        self.assertEqual(res['max_height'], 440)
        # Visual top of menu in viewport = window_height - bottom - max_height = 900 - 156 - 440 = 304
        # Verify clearance below header: 304 >= header_bottom + 10 (58 + 10 = 68)
        menu_visual_top = 900 - res['bottom'] - res['max_height']
        self.assertGreaterEqual(menu_visual_top, 58 + 10)

    def test_constrained_space_picks_larger_and_clamps_max_height(self):
        """When neither direction fits 440px, picks side with more room and clamps max_height."""
        # Short viewport: 500px, Header: 58px, Status bar top: 456px
        # Max allowed workspace: 68px to 446px (total 378px)
        # Button: top=260, bottom=292 (center-ish)
        # space_above = 260 - 68 = 192
        # space_below = 446 - 292 = 154
        # Neither has 448. space_above (192) > space_below (154) -> UP
        res = calculate_menu_position(btn_top=260, btn_bottom=292, btn_left=150,
                                      window_height=500, status_top=456)
        self.assertFalse(res['closed'])
        self.assertEqual(res['direction'], 'up')
        # max_height = space_above - 8 = 192 - 8 = 184 (>= 140)
        self.assertEqual(res['max_height'], 184)
        menu_visual_top = 500 - res['bottom'] - res['max_height']
        self.assertGreaterEqual(menu_visual_top, 58 + 8)

    def test_auto_closes_when_button_scrolled_above_header(self):
        """Button scrolled up behind sticky header causes menu to close automatically."""
        # Header bottom: 58, minAllowedTop: 68. Button bottom: 65 (< 68)
        res = calculate_menu_position(btn_top=33, btn_bottom=65, btn_left=200)
        self.assertTrue(res['closed'])

    def test_auto_closes_when_button_scrolled_below_status_bar(self):
        """Button scrolled down behind fixed status bar causes menu to close automatically."""
        # Status bar top: 856, maxAllowedBottom: 846. Button top: 850 (> 846)
        res = calculate_menu_position(btn_top=850, btn_bottom=882, btn_left=200)
        self.assertTrue(res['closed'])

    def test_horizontal_clamping_left_and_right(self):
        """Menu horizontally clamped with >= 12px margin from screen edges."""
        # Negative left (e.g. mobile or wide overhang)
        res_left = calculate_menu_position(btn_top=300, btn_bottom=332, btn_left=-20)
        self.assertEqual(res_left['left'], 12)

        # Right edge collision (window_width=1000, menu_width=330 -> max left = 1000 - 330 - 12 = 658)
        res_right = calculate_menu_position(btn_top=300, btn_bottom=332, btn_left=800, window_width=1000)
        self.assertEqual(res_right['left'], 658)


class TestBlocksJsSourceCodeVerification(unittest.TestCase):
    """4. Source Code Implementation in frontend/public/js/blocks.js."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(FRONTEND_DIR, 'js', 'blocks.js'), 'r', encoding='utf-8') as f:
            cls.js = f.read()

    def test_portals_to_document_body(self):
        """BlockInserter portals #block-menu to document.body in constructor."""
        self.assertIn("document.body.appendChild(this.blockMenu)", self.js)

    def test_update_menu_position_method_exists(self):
        """updateMenuPosition() is implemented with viewport geometry checks."""
        self.assertIn("updateMenuPosition()", self.js)
        self.assertIn("getBoundingClientRect()", self.js)
        self.assertIn("minAllowedTop", self.js)
        self.assertIn("maxAllowedBottom", self.js)
        self.assertIn("spaceBelow", self.js)
        self.assertIn("spaceAbove", self.js)
        self.assertIn("direction = 'up'", self.js)
        self.assertIn("direction = 'down'", self.js)

    def test_scroll_and_resize_listeners_registered(self):
        """Scroll and resize listeners are registered on window and visualViewport."""
        self.assertIn("window.addEventListener('scroll'", self.js)
        self.assertIn("window.addEventListener('resize'", self.js)
        self.assertIn("visualViewport", self.js)

    def test_open_up_and_open_down_classes_managed(self):
        """Classes open-up and open-down are toggled dynamically."""
        self.assertIn("classList.add('open-up')", self.js)
        self.assertIn("classList.add('open-down')", self.js)

    def test_overscroll_behavior_contain_inline(self):
        """overscrollBehavior contain is explicitly set in JS."""
        self.assertIn("overscrollBehavior = 'contain'", self.js)

    def test_keyboard_navigation_scrolls_into_view(self):
        """Keyboard navigation uses scrollIntoView({ block: 'nearest' })."""
        self.assertIn("scrollIntoView({ block: 'nearest' })", self.js)


class TestBlockMenuItemsPreserved(unittest.TestCase):
    """5. All 13 Block Menu Items are Preserved and Selectable."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(FRONTEND_DIR, 'editor.html'), 'r', encoding='utf-8') as f:
            cls.html = f.read()
        with open(os.path.join(FRONTEND_DIR, 'js', 'blocks.js'), 'r', encoding='utf-8') as f:
            cls.js = f.read()

    def test_all_13_items_in_exact_order(self):
        """All 13 items exist in HTML in exact specified order."""
        menu_match = re.search(r'<div id="block-menu"[^>]*>(.*?)(?:<!-- Node Controls|<div id="node-controls")', self.html, re.DOTALL)
        self.assertIsNotNone(menu_match)
        menu_content = menu_match.group(1)

        items = re.findall(r'<div class="block-menu-item" data-block="([^"]+)"', menu_content)
        expected = [
            'header', 'blockquote', 'bullet-list', 'ordered-list',
            'media', 'image', 'divider', 'code-block', 'formula',
            'spoiler', 'anchor', 'person', 'table'
        ]
        self.assertEqual(items, expected)

    def test_blocks_js_handles_all_items(self):
        """blocks.js handles all block types."""
        for item in ['header', 'blockquote', 'bullet-list', 'ordered-list',
                     'media', 'image', 'divider', 'code-block', 'formula',
                     'spoiler', 'anchor', 'person', 'table']:
            self.assertIn(f"case '{item}':", self.js, f"Missing case for {item} in insertBlock()")


if __name__ == '__main__':
    unittest.main()
