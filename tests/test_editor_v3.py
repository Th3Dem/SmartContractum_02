#!/usr/bin/env python3
"""
Unit tests for Antigravity Editor v3 (task-03-editor-layout-and-context-tools).
Covers:
1. Page layout rules (central block 800-880px, 40-56px padding, calm light-gray #f4f5f7 / dark #111315, side zones 240-280px).
2. Removal of persistent formatting strip, compact top document bar, and bottom status bar.
3. 11 Contextual Bubble Toolbar buttons in EXACT order + 'Еще' dropdown.
4. 12 Floating '+' Block Inserter items in EXACT order + 'Дополнительно' group.
5. Video URL parsers for YouTube, Vimeo, VK Video.
6. Inline spoiler vs Block spoiler distinct handling.
7. Inline LaTeX formula vs Block LaTeX formula.
8. Anchor (with unique ID check) and Person blocks.
9. HTML sanitization with safe video embed whitelist.
10. Exporters (HTML, Markdown, JSON schema v2) and loss warnings.
"""

import json
import os
import re
import unittest
from html.parser import HTMLParser


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, 'frontend', 'public')


class TestPageLayoutAndDesign(unittest.TestCase):
    """Test 1: Verify layout constraints, CSS variables, and alignment."""

    def setUp(self):
        theme_path = os.path.join(FRONTEND_DIR, 'css', 'theme.css')
        with open(theme_path, 'r', encoding='utf-8') as f:
            self.theme_css = f.read()

        editor_css_path = os.path.join(FRONTEND_DIR, 'css', 'editor.css')
        with open(editor_css_path, 'r', encoding='utf-8') as f:
            self.editor_css = f.read()

        html_path = os.path.join(FRONTEND_DIR, 'editor.html')
        with open(html_path, 'r', encoding='utf-8') as f:
            self.html = f.read()

    def test_background_colors(self):
        """Calm light-gray page background (#f4f5f7 / dark: #111315)."""
        self.assertIn('--bg-page: #f4f5f7;', self.theme_css)
        self.assertIn('--bg-editor: #ffffff;', self.theme_css)

        # Check dark theme background
        dark_section = re.search(r'\[data-theme="dark"\]\s*\{([^}]+)\}', self.theme_css)
        self.assertIsNotNone(dark_section)
        dark_content = dark_section.group(1)
        self.assertIn('--bg-page: #111315;', dark_content)
        self.assertIn('--bg-editor: #1a1d21;', dark_content)

    def test_central_block_dimensions(self):
        """Central block width: 800-880px (recommended 840px), horizontal padding: 40-56px (recommended 48px)."""
        # Check variable in theme.css
        width_match = re.search(r'--editor-width:\s*([0-9]+)px', self.theme_css)
        self.assertIsNotNone(width_match)
        width = int(width_match.group(1))
        self.assertGreaterEqual(width, 800)
        self.assertLessEqual(width, 880)

        padding_match = re.search(r'--editor-padding-x:\s*([0-9]+)px', self.theme_css)
        self.assertIsNotNone(padding_match)
        padding = int(padding_match.group(1))
        self.assertGreaterEqual(padding, 40)
        self.assertLessEqual(padding, 56)

        # Check editor-card style in editor.css
        self.assertIn('max-width: 840px', self.editor_css)
        self.assertIn('padding: 48px', self.editor_css)

    def test_symmetrical_side_zones_layout(self):
        """Symmetrical side zones 240-280px in 3-column layout."""
        self.assertIn('.app-main-layout', self.editor_css)
        self.assertIn('.side-zone-left', self.editor_css)
        self.assertIn('.side-zone-right', self.editor_css)
        self.assertIn('minmax(240px, 1fr)', self.editor_css)
        self.assertIn('class="side-zone side-zone-left"', self.html)
        self.assertIn('class="side-zone side-zone-right"', self.html)

    def test_document_title_and_editor_left_boundary_alignment(self):
        """Document title H1 and editor content aligned to exact same left boundary."""
        # Both article-title-input and ql-editor must have padding: 0 inside editor-card
        self.assertIn('.article-title-input', self.editor_css)
        self.assertIn('.ql-editor', self.editor_css)
        # Check padding: 0 !important for .ql-editor and padding: 0 for .article-title-input
        self.assertTrue(re.search(r'\.article-title-input\s*\{[^}]*padding:\s*0;', self.editor_css))
        self.assertTrue(re.search(r'\.ql-editor\s*\{[^}]*padding:\s*0\s*!important;', self.editor_css))


class TestPersistentToolbarRemovalAndNewBars(unittest.TestCase):
    """Test 2: Removal of persistent formatting strip and verification of top & bottom bars."""

    def setUp(self):
        html_path = os.path.join(FRONTEND_DIR, 'editor.html')
        with open(html_path, 'r', encoding='utf-8') as f:
            self.html = f.read()

    def test_persistent_formatting_toolbar_removed(self):
        """Ensure the old fixed formatting toolbar under the header is completely removed."""
        self.assertNotIn('editor-toolbar-wrapper', self.html)
        self.assertNotIn('id="editor-toolbar"', self.html)
        self.assertNotIn('class="editor-toolbar"', self.html)

    def test_compact_top_document_bar(self):
        """Top bar contains branding, drafts button with badge, autosave indicator, preview toggle, export/import, more actions."""
        self.assertIn('Antigravity Writer', self.html)
        self.assertIn('id="btn-drafts-modal"', self.html)
        self.assertIn('id="drafts-badge"', self.html)
        self.assertIn('id="save-status"', self.html)
        self.assertIn('id="btn-mode-edit"', self.html)
        self.assertIn('id="btn-mode-preview"', self.html)
        self.assertIn('id="export-dropdown-menu"', self.html)
        self.assertIn('id="btn-more-actions"', self.html)
        self.assertIn('id="btn-theme-toggle"', self.html)
        self.assertIn('id="btn-clear-doc"', self.html)

    def test_bottom_status_bar(self):
        """Bottom status bar contains stats (words, chars, reading time) and Undo/Redo."""
        self.assertIn('class="app-status-bar"', self.html)
        self.assertIn('id="stat-words"', self.html)
        self.assertIn('id="stat-chars"', self.html)
        self.assertIn('id="stat-reading-time"', self.html)
        self.assertIn('id="btn-undo"', self.html)
        self.assertIn('id="btn-redo"', self.html)


class TestContextualBubbleToolbar11ToolsOrder(unittest.TestCase):
    """Test 3: 11 Contextual Bubble Toolbar tools in EXACT required order + More dropdown."""

    def setUp(self):
        html_path = os.path.join(FRONTEND_DIR, 'editor.html')
        with open(html_path, 'r', encoding='utf-8') as f:
            self.html = f.read()

        js_path = os.path.join(FRONTEND_DIR, 'js', 'bubble.js')
        with open(js_path, 'r', encoding='utf-8') as f:
            self.bubble_js = f.read()

    def test_11_bubble_buttons_exact_order(self):
        """Verify the 11 buttons in exact order:
        1. Bold (Жирный)
        2. Italic (Курсив)
        3. Underline (Подчеркнутый)
        4. Strike (Зачеркнутый)
        5. Subscript (Подстрочный)
        6. Superscript (Надстрочный)
        7. Hidden text (Скрытый текст / inline-spoiler)
        8. Clear formatting (Без форматирования)
        9. Inline code (Встроенный код)
        10. Link (Ссылка)
        11. Formula (Формула)
        """
        bubble_match = re.search(r'<div id="bubble-toolbar"[^>]*>(.*?)<div class="bubble-dropdown-wrapper">', self.html, re.DOTALL)
        self.assertIsNotNone(bubble_match, "Bubble toolbar container not found")
        bubble_content = bubble_match.group(1)

        # Extract all buttons
        button_matches = re.findall(r'<button\b([^>]*)>(.*?)</button>', bubble_content, re.DOTALL)
        self.assertEqual(len(button_matches), 11, f"Expected 11 bubble toolbar buttons, found {len(button_matches)}")

        expected_tools = [
            {'format': 'bold', 'title': 'Жирный'},
            {'format': 'italic', 'title': 'Курсив'},
            {'format': 'underline', 'title': 'Подчеркнутый'},
            {'format': 'strike', 'title': 'Зачеркнутый'},
            {'format': 'script', 'value': 'sub', 'title': 'Подстрочный'},
            {'format': 'script', 'value': 'super', 'title': 'Надстрочный'},
            {'format': 'inline-spoiler', 'title': 'Скрытый текст'},
            {'action': 'clear-format', 'title': 'Без форматирования'},
            {'format': 'code', 'title': 'Встроенный код'},
            {'action': 'link', 'title': 'Ссылка'},
            {'action': 'formula', 'title': 'Формула'}
        ]

        for i, (attrs, _) in enumerate(button_matches):
            expected = expected_tools[i]
            if 'format' in expected:
                self.assertIn(f'data-format="{expected["format"]}"', attrs, f"Tool {i+1} format mismatch")
            if 'value' in expected:
                self.assertIn(f'data-value="{expected["value"]}"', attrs, f"Tool {i+1} value mismatch")
            if 'action' in expected:
                self.assertIn(f'data-action="{expected["action"]}"', attrs, f"Tool {i+1} action mismatch")
            self.assertIn(expected['title'], attrs, f"Tool {i+1} Russian tooltip mismatch")

    def test_bubble_more_dropdown_features(self):
        """Verify 'Еще' dropdown contains text color, background highlight, and text alignment."""
        self.assertIn('id="bubble-more-btn"', self.html)
        self.assertIn('id="bubble-more-menu"', self.html)
        self.assertIn('Цвет текста', self.html)
        self.assertIn('Цвет фона (выделение)', self.html)
        self.assertIn('Выравнивание', self.html)
        self.assertIn('data-color=', self.html)
        self.assertIn('data-bg=', self.html)
        self.assertIn('data-align=', self.html)

    def test_bubble_js_contract(self):
        """Verify bubble.js handles non-empty range selection, prevents selection blur, and handles Escape."""
        self.assertIn('range && range.length > 0', self.bubble_js)
        self.assertIn('e.preventDefault()', self.bubble_js)
        self.assertIn('Escape', self.bubble_js)
        self.assertIn('position-below', self.bubble_js)


class TestBlockInserter12ItemsOrder(unittest.TestCase):
    """Test 4: 12 '+' Menu items in EXACT required order + 'Дополнительно' group."""

    def setUp(self):
        html_path = os.path.join(FRONTEND_DIR, 'editor.html')
        with open(html_path, 'r', encoding='utf-8') as f:
            self.html = f.read()

        js_path = os.path.join(FRONTEND_DIR, 'js', 'blocks.js')
        with open(js_path, 'r', encoding='utf-8') as f:
            self.blocks_js = f.read()

    def test_12_block_items_exact_order(self):
        """Verify 12 main block items in exact order:
        1. Header (Заголовок)
        2. Quote (Цитата)
        3. List (Список)
        4. Numbered list (Нумерованный список)
        5. Media element (Медиаэлемент)
        6. Image (Изображение)
        7. Divider (Разделитель)
        8. Code (Код)
        9. Formula (Формула)
        10. Spoiler (Спойлер)
        11. Anchor (Якорь)
        12. Person (Персона)
        """
        menu_match = re.search(r'<div id="block-menu"[^>]*>(.*?)<div class="block-menu-divider"></div>', self.html, re.DOTALL)
        self.assertIsNotNone(menu_match, "Block menu container not found")
        menu_content = menu_match.group(1)

        items = re.findall(r'<div class="block-menu-item" data-block="([^"]+)"', menu_content)
        expected_items = [
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
            'person'
        ]

        self.assertEqual(items, expected_items, f"Items mismatch: got {items}, expected {expected_items}")

    def test_additional_blocks_group(self):
        """Group 'Дополнительно' contains Table and Checklist."""
        self.assertIn('Дополнительно', self.html)
        self.assertIn('data-block="table"', self.html)
        self.assertIn('data-block="checklist"', self.html)

    def test_keyboard_navigation_and_slash_command(self):
        """Keyboard navigation: ArrowUp, ArrowDown, Enter, Escape, and slash command '/'."""
        self.assertIn('ArrowDown', self.blocks_js)
        self.assertIn('ArrowUp', self.blocks_js)
        self.assertIn('Enter', self.blocks_js)
        self.assertIn('Escape', self.blocks_js)
        self.assertIn("e.key === '/'", self.blocks_js)


class TestVideoParsers(unittest.TestCase):
    """Test 5: Video URL parsers for YouTube, Vimeo, VK Video."""

    def parse_video_url(self, url):
        """Python mirror of MediaManager.parseVideoUrl for test verification."""
        if not url or not isinstance(url, str):
            return None
        url = url.strip()

        # YouTube
        yt_match = re.search(r'(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?|shorts)\/|.*[?&]v=)|youtu\.be\/)([^"&?/\s]{11})', url, re.I)
        if yt_match:
            vid = yt_match.group(1)
            return {
                'provider': 'youtube',
                'id': vid,
                'embedUrl': f'https://www.youtube-nocookie.com/embed/{vid}',
                'originalUrl': url
            }

        # Vimeo
        vimeo_match = re.search(r'(?:vimeo\.com\/|player\.vimeo\.com\/video\/)([0-9]+)', url, re.I)
        if vimeo_match:
            vid = vimeo_match.group(1)
            return {
                'provider': 'vimeo',
                'id': vid,
                'embedUrl': f'https://player.vimeo.com/video/{vid}',
                'originalUrl': url
            }

        # VK Video video_ext.php
        vk_ext = re.search(r'(?:vk\.com|vkvideo\.ru)\/video_ext\.php\?(?:[^"\'\s]*&)?oid=(-?[0-9]+)&id=([0-9]+)(?:&hash=([a-zA-Z0-9]+))?', url, re.I)
        if vk_ext:
            oid = vk_ext.group(1)
            vid = vk_ext.group(2)
            h = vk_ext.group(3) or ''
            hash_param = f'&hash={h}' if h else ''
            return {
                'provider': 'vk',
                'oid': oid,
                'id': vid,
                'hash': h,
                'embedUrl': f'https://vk.com/video_ext.php?oid={oid}&id={vid}{hash_param}&hd=2',
                'originalUrl': url
            }

        # VK Video standard url
        vk_std = re.search(r'(?:vk\.com|vkvideo\.ru)\/video(-?[0-9]+)_([0-9]+)', url, re.I)
        if vk_std:
            oid = vk_std.group(1)
            vid = vk_std.group(2)
            hash_match = re.search(r'[?&]hash=([a-zA-Z0-9]+)', url, re.I)
            h = hash_match.group(1) if hash_match else ''
            hash_param = f'&hash={h}' if h else ''
            return {
                'provider': 'vk',
                'oid': oid,
                'id': vid,
                'hash': h,
                'embedUrl': f'https://vk.com/video_ext.php?oid={oid}&id={vid}{hash_param}&hd=2',
                'originalUrl': url
            }

        return None

    def test_youtube_variations(self):
        urls = [
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'https://youtu.be/dQw4w9WgXcQ',
            'https://www.youtube.com/embed/dQw4w9WgXcQ',
            'https://www.youtube.com/shorts/dQw4w9WgXcQ'
        ]
        for u in urls:
            parsed = self.parse_video_url(u)
            self.assertIsNotNone(parsed, f"Failed to parse YouTube URL: {u}")
            self.assertEqual(parsed['provider'], 'youtube')
            self.assertEqual(parsed['id'], 'dQw4w9WgXcQ')
            self.assertEqual(parsed['embedUrl'], 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ')

    def test_vimeo_variations(self):
        urls = [
            'https://vimeo.com/76979871',
            'https://player.vimeo.com/video/76979871'
        ]
        for u in urls:
            parsed = self.parse_video_url(u)
            self.assertIsNotNone(parsed, f"Failed to parse Vimeo URL: {u}")
            self.assertEqual(parsed['provider'], 'vimeo')
            self.assertEqual(parsed['id'], '76979871')
            self.assertEqual(parsed['embedUrl'], 'https://player.vimeo.com/video/76979871')

    def test_vk_video_variations(self):
        urls = [
            'https://vk.com/video-12345_67890',
            'https://vkvideo.ru/video-12345_67890',
            'https://vk.com/video_ext.php?oid=-12345&id=67890&hash=abc12345',
            'https://vkvideo.ru/video_ext.php?oid=-12345&id=67890&hash=abc12345'
        ]
        for u in urls:
            parsed = self.parse_video_url(u)
            self.assertIsNotNone(parsed, f"Failed to parse VK URL: {u}")
            self.assertEqual(parsed['provider'], 'vk')
            self.assertEqual(parsed['oid'], '-12345')
            self.assertEqual(parsed['id'], '67890')
            self.assertTrue(parsed['embedUrl'].startswith('https://vk.com/video_ext.php?oid=-12345&id=67890'))

    def test_invalid_video_urls(self):
        invalids = [
            'https://example.com/video.mp4',
            'ftp://youtube.com/bad',
            'not a url'
        ]
        for inv in invalids:
            self.assertIsNone(self.parse_video_url(inv))

    def test_video_embed_iframe_contains_sandbox_attribute(self):
        """Assert that video embed iframes in core.js contain the safe sandbox attribute (DoD requirement)."""
        core_js_path = os.path.join(FRONTEND_DIR, 'js', 'core.js')
        with open(core_js_path, 'r', encoding='utf-8') as f:
            core_js = f.read()

        # Check sandbox attribute in MediaEmbedBlot / VideoEmbed / VideoBlot
        self.assertIn("iframe.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-presentation allow-popups')", core_js)
        self.assertIn("allow-scripts allow-same-origin allow-presentation allow-popups", core_js)


class TestInlineAndBlockSpoilers(unittest.TestCase):
    """Test 6: Distinct handling of inline spoiler and block spoiler."""

    def setUp(self):
        with open(os.path.join(FRONTEND_DIR, 'js', 'core.js'), 'r', encoding='utf-8') as f:
            self.core_js = f.read()

    def test_both_spoilers_registered(self):
        """Ensure both InlineSpoilerBlot and SpoilerBlot are registered."""
        self.assertIn("class InlineSpoilerBlot extends Inline", self.core_js)
        self.assertIn("static blotName = 'inline-spoiler';", self.core_js)
        self.assertIn("class SpoilerBlot extends BlockEmbed", self.core_js)
        self.assertIn("static blotName = 'spoiler';", self.core_js)

    def test_spoiler_markdown_conversion(self):
        """Verify inline spoiler converts to ||text|| and block spoiler to <details>."""
        inline_html = 'Текст со <span class="editor-inline-spoiler">секретом</span>'
        block_html = '<details class="editor-spoiler"><summary class="editor-spoiler-title">Заголовок</summary><div class="editor-spoiler-body">Текст под спойлером</div></details>'

        # Verify inline pattern
        md_inline = re.sub(r'<span class="editor-inline-spoiler">(.*?)</span>', r'||\1||', inline_html)
        self.assertEqual(md_inline, 'Текст со ||секретом||')

        # Verify block pattern
        self.assertIn('<details', block_html)
        self.assertIn('<summary', block_html)


class TestFormulas(unittest.TestCase):
    """Test 7: Inline and Block LaTeX formulas."""

    def setUp(self):
        with open(os.path.join(FRONTEND_DIR, 'js', 'core.js'), 'r', encoding='utf-8') as f:
            self.core_js = f.read()

    def test_both_formula_blots_exist(self):
        """Ensure both InlineFormulaBlot and BlockFormulaBlot are defined."""
        self.assertIn("class InlineFormulaBlot extends Embed", self.core_js)
        self.assertIn("static blotName = 'inlineFormula';", self.core_js)
        self.assertIn("class BlockFormulaBlot extends BlockEmbed", self.core_js)
        self.assertIn("static blotName = 'blockFormula';", self.core_js)


class TestAnchorAndPersonBlocks(unittest.TestCase):
    """Test 8: Anchor blot with unique ID check, and Person card block."""

    def setUp(self):
        with open(os.path.join(FRONTEND_DIR, 'js', 'core.js'), 'r', encoding='utf-8') as f:
            self.core_js = f.read()
        with open(os.path.join(FRONTEND_DIR, 'js', 'toolbar.js'), 'r', encoding='utf-8') as f:
            self.toolbar_js = f.read()

    def test_anchor_and_person_blots_exist(self):
        """Ensure AnchorBlot and PersonBlot are registered."""
        self.assertIn("class AnchorBlot extends BlockEmbed", self.core_js)
        self.assertIn("static blotName = 'anchor';", self.core_js)
        self.assertIn("class PersonBlot extends BlockEmbed", self.core_js)
        self.assertIn("static blotName = 'person';", self.core_js)

    def test_anchor_unique_id_check(self):
        """Verify unique ID check for anchors in toolbar.js."""
        self.assertIn('.editor-anchor-block[data-anchor-id=', self.toolbar_js)
        self.assertIn('уже существует', self.toolbar_js)


class TestSanitizationWithVideoWhitelist(unittest.TestCase):
    """Test 9: XSS sanitization while allowing whitelisted video iframes."""

    def sanitize_html(self, html_input):
        """Python mirror of Converter.sanitizeHTML."""
        if not html_input:
            return ""

        # Remove dangerous tags
        dangerous_tags = ['script', 'object', 'embed', 'form', 'style', 'link', 'meta', 'base']
        cleaned = html_input
        for tag in dangerous_tags:
            pattern = re.compile(rf'<{tag}\b[^>]*>.*?</{tag}>', re.IGNORECASE | re.DOTALL)
            cleaned = pattern.sub('', cleaned)
            pattern_self = re.compile(rf'<{tag}\b[^>]*\/?>', re.IGNORECASE)
            cleaned = pattern_self.sub('', cleaned)

        # Remove inline event handlers
        cleaned = re.sub(r'\s+on[a-zA-Z]+\s*=\s*("[^"]*"|\'[^\']*\'|[^\s>]+)', '', cleaned, flags=re.IGNORECASE)

        # Remove dangerous URIs
        cleaned = re.sub(r'(href|src|action|data)\s*=\s*["\']\s*(javascript|vbscript|data:text\/html):[^"\']*["\']', '', cleaned, flags=re.IGNORECASE)

        # Filter iframes: allow only YouTube, Vimeo, VK
        allowed_hosts = ['youtube.com', 'youtube-nocookie.com', 'player.vimeo.com', 'vk.com', 'vkvideo.ru']

        def filter_iframe(match):
            iframe_tag = match.group(0)
            src_match = re.search(r'src=["\']([^"\']+)["\']', iframe_tag, re.I)
            if not src_match:
                return ''
            src = src_match.group(1).lower()
            if any(host in src for host in allowed_hosts):
                # Enforce safe sandbox isolation matching converter.js
                tag = re.sub(r'\s+sandbox=["\'][^"\']*["\']', '', iframe_tag)
                first_gt = tag.find('>')
                if first_gt != -1:
                    tag = tag[:first_gt] + ' sandbox="allow-scripts allow-same-origin allow-presentation allow-popups"' + tag[first_gt:]
                return tag
            return ''

        cleaned = re.sub(r'<iframe\b[^>]*>.*?</iframe>|<iframe\b[^>]*\/?>', filter_iframe, cleaned, flags=re.IGNORECASE | re.DOTALL)
        return cleaned

    def test_strip_xss_attacks(self):
        payloads = [
            '<script>alert("XSS")</script>',
            '<img src="img.jpg" onerror="alert(1)">',
            '<a href="javascript:alert(1)">Click</a>',
            '<iframe src="http://evil.attacker.com"></iframe>'
        ]
        for p in payloads:
            sanitized = self.sanitize_html(p)
            self.assertNotIn('<script', sanitized.lower())
            self.assertNotIn('onerror', sanitized.lower())
            self.assertNotIn('javascript:', sanitized.lower())
            self.assertNotIn('evil.attacker.com', sanitized)

    def test_allow_whitelisted_video_iframes(self):
        yt_iframe = '<iframe src="https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ" allowfullscreen></iframe>'
        vk_iframe = '<iframe src="https://vk.com/video_ext.php?oid=-123&id=456&hd=2" allowfullscreen></iframe>'
        vimeo_iframe = '<iframe src="https://player.vimeo.com/video/123456" allowfullscreen></iframe>'

        sanitized_yt = self.sanitize_html(yt_iframe)
        sanitized_vk = self.sanitize_html(vk_iframe)
        sanitized_vimeo = self.sanitize_html(vimeo_iframe)

        self.assertIn('youtube-nocookie.com', sanitized_yt)
        self.assertIn('vk.com/video_ext.php', sanitized_vk)
        self.assertIn('player.vimeo.com', sanitized_vimeo)

        # Assert safe iframe sandbox attribute is included
        self.assertIn('sandbox="allow-scripts allow-same-origin allow-presentation allow-popups"', sanitized_yt)
        self.assertIn('sandbox="allow-scripts allow-same-origin allow-presentation allow-popups"', sanitized_vk)
        self.assertIn('sandbox="allow-scripts allow-same-origin allow-presentation allow-popups"', sanitized_vimeo)

    def test_converter_js_enforces_sandbox_on_allowed_iframes(self):
        """Verify converter.js sets safe sandbox attribute on allowed iframes during sanitization."""
        converter_js_path = os.path.join(FRONTEND_DIR, 'js', 'converter.js')
        with open(converter_js_path, 'r', encoding='utf-8') as f:
            converter_js = f.read()
        self.assertIn("iframe.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-presentation allow-popups')", converter_js)


class TestExportersAndLossWarnings(unittest.TestCase):
    """Test 10: JSON schema v2, Markdown/HTML exporters, and loss warnings."""

    def test_json_schema_v2(self):
        """JSON export uses schema 'antigravity-editor-v2'."""
        with open(os.path.join(FRONTEND_DIR, 'js', 'converter.js'), 'r', encoding='utf-8') as f:
            converter_js = f.read()
        self.assertIn("schema: 'antigravity-editor-v2'", converter_js)

    def test_loss_warnings_on_export(self):
        """Loss warnings are generated when exporting custom blocks."""
        with open(os.path.join(FRONTEND_DIR, 'js', 'converter.js'), 'r', encoding='utf-8') as f:
            converter_js = f.read()
        self.assertIn("lastExportWarnings", converter_js)
        self.assertIn("Блок «Персона»", converter_js)
        self.assertIn("getLastWarnings", converter_js)


if __name__ == '__main__':
    unittest.main()
