#!/usr/bin/env python3
"""
Test Suite: Feed Page and Editor Designer Color Palette
Verification for:
  - task-14-feed-page-and-editor-color-palette
  - task-15-editor-feed-visual-alignment
  - task-16-fix-editor-visual-and-theme-issues
  - task-18-clean-native-feed-redesign

Key test requirements:
  1. Verification that frontend/public/feed.html, frontend/public/css/feed.css,
     and frontend/public/js/feed.js exist and are not empty.
  2. Legacy file cleanliness: forum_social.css, landing_main.css, hero_constellation.css,
     forum_social.js, and landing_main.js are physically absent and not imported
     in feed.html and editor.html.
  3. 100% Offline-First check: Ensure feed.html, feed.css, theme.css, and editor.html
     have zero external http/https references to Google Fonts or CDNs.
  4. Strict Onest font usage in feed.html and feed.css.
  5. Zero emojis (0 emojis) in feed.html, editor.html, and related assets.
  6. Complete removal of top header menu from feed.html and all pages: #appHeader, #headerNav,
     #btnThemeToggle, #headerLoginBtn completely absent.
  7. Navigation and layout integrity: feed.html links to editor.html via #btnHeroWrite;
     index.html links to feed.html and editor.html.
  8. Color palette in theme.css: dark theme CMC Midnight Navy tokens and high-contrast
     light theme tokens.
  9. Two-column feed grid: #feedCardsContainer, .feed-card, .feed-filter-btn,
     sidebar with widgets.
 10. Editor visual alignment and theme fixes from task-15 & task-16.
"""

import os
import re
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, 'frontend', 'public')


class TestFeedPageExistenceAndCleanliness(unittest.TestCase):
    """Test 1 & 2: Verification of native feed files existence and legacy files absence."""

    @classmethod
    def setUpClass(cls):
        cls.feed_html_path = os.path.join(FRONTEND_DIR, 'feed.html')
        cls.feed_css_path = os.path.join(FRONTEND_DIR, 'css', 'feed.css')
        cls.feed_js_path = os.path.join(FRONTEND_DIR, 'js', 'feed.js')
        cls.editor_html_path = os.path.join(FRONTEND_DIR, 'editor.html')

        with open(cls.feed_html_path, 'r', encoding='utf-8') as f:
            cls.feed_html = f.read()
        with open(cls.editor_html_path, 'r', encoding='utf-8') as f:
            cls.editor_html = f.read()

        cls.legacy_files = [
            os.path.join(FRONTEND_DIR, 'css', 'forum_social.css'),
            os.path.join(FRONTEND_DIR, 'css', 'landing_main.css'),
            os.path.join(FRONTEND_DIR, 'css', 'hero_constellation.css'),
            os.path.join(FRONTEND_DIR, 'js', 'forum_social.js'),
            os.path.join(FRONTEND_DIR, 'js', 'landing_main.js'),
        ]

    def test_native_feed_files_exist(self):
        """Verify frontend/public/feed.html, css/feed.css, and js/feed.js exist and are not empty."""
        for path, min_size in [
            (self.feed_html_path, 5000),
            (self.feed_css_path, 1000),
            (self.feed_js_path, 1000),
        ]:
            self.assertTrue(os.path.isfile(path), f"Required native file {path} must exist")
            file_size = os.path.getsize(path)
            self.assertGreater(file_size, min_size, f"File {path} is unexpectedly small ({file_size} bytes)")

    def test_legacy_files_physically_absent(self):
        """Verify legacy files (forum_social.*, landing_main.*, hero_constellation.*) are physically absent."""
        for path in self.legacy_files:
            self.assertFalse(
                os.path.exists(path),
                f"Legacy file {path} must be completely removed from the filesystem"
            )

    def test_legacy_files_not_imported_in_html(self):
        """Verify legacy files are not referenced or imported in feed.html and editor.html."""
        legacy_names = [
            'forum_social.css',
            'landing_main.css',
            'hero_constellation.css',
            'forum_social.js',
            'landing_main.js'
        ]

        for html_content, filename in [
            (self.feed_html, 'feed.html'),
            (self.editor_html, 'editor.html')
        ]:
            for legacy_name in legacy_names:
                self.assertNotIn(
                    legacy_name,
                    html_content,
                    f"Forbidden reference to legacy file '{legacy_name}' found in {filename}"
                )


class TestOfflineFirstIntegrity(unittest.TestCase):
    """Test 3: 100% Offline-First check for feed.html, feed.css, theme.css, and editor.html."""

    @classmethod
    def setUpClass(cls):
        cls.feed_html_path = os.path.join(FRONTEND_DIR, 'feed.html')
        cls.feed_css_path = os.path.join(FRONTEND_DIR, 'css', 'feed.css')
        cls.theme_css_path = os.path.join(FRONTEND_DIR, 'css', 'theme.css')
        cls.editor_html_path = os.path.join(FRONTEND_DIR, 'editor.html')

        with open(cls.feed_html_path, 'r', encoding='utf-8') as f:
            cls.feed_html = f.read()
        with open(cls.feed_css_path, 'r', encoding='utf-8') as f:
            cls.feed_css = f.read()
        with open(cls.theme_css_path, 'r', encoding='utf-8') as f:
            cls.theme_css = f.read()
        with open(cls.editor_html_path, 'r', encoding='utf-8') as f:
            cls.editor_html = f.read()

        cls.cdn_indicators = [
            'fonts.googleapis.com',
            'fonts.gstatic.com',
            'cdnjs.cloudflare.com',
            'cdn.jsdelivr.net',
            'unpkg.com',
            'ajax.googleapis.com',
            'stackpath.bootstrapcdn.com'
        ]

    def test_offline_first_zero_cdn_references(self):
        """Ensure feed.html, feed.css, theme.css, and editor.html have zero CDN references."""
        checked_files = [
            (self.feed_html, 'feed.html'),
            (self.feed_css, 'css/feed.css'),
            (self.theme_css, 'css/theme.css'),
            (self.editor_html, 'editor.html'),
        ]

        for content, filename in checked_files:
            for cdn in self.cdn_indicators:
                self.assertNotIn(cdn, content, f"Forbidden external CDN reference '{cdn}' found in {filename}")

    def test_offline_first_zero_external_links_in_feed_and_css(self):
        """Ensure feed.html, feed.css, and theme.css have zero external http/https resource URLs."""
        url_pattern = re.compile(r'https?://(?!localhost|127\.0\.0\.1|www\.w3\.org|smartcontractum\.ru)[^\s\'"<>]+')
        for content, filename in [
            (self.feed_html, 'feed.html'),
            (self.feed_css, 'css/feed.css'),
            (self.theme_css, 'css/theme.css')
        ]:
            matches = [m for m in url_pattern.findall(content) if 'w3.org' not in m]
            self.assertEqual(len(matches), 0, f"External URLs found in {filename}: {matches}")

    def test_feed_scripts_and_stylesheets_are_local(self):
        """Verify that all link[rel=stylesheet] and script[src] references in feed.html point to local files."""
        stylesheet_hrefs = re.findall(r'<link[^>]*rel=["\']stylesheet["\'][^>]*href=["\']([^"\']+)["\']', self.feed_html)
        self.assertGreater(len(stylesheet_hrefs), 0, "No stylesheet links found in feed.html")
        for href in stylesheet_hrefs:
            self.assertFalse(href.startswith(('http://', 'https://', '//')),
                             f"Stylesheet href '{href}' must not be an external absolute URL")

        script_srcs = re.findall(r'<script[^>]*src=["\']([^"\']+)["\']', self.feed_html)
        self.assertGreater(len(script_srcs), 0, "No script tags with src found in feed.html")
        for src in script_srcs:
            self.assertFalse(src.startswith(('http://', 'https://', '//')),
                             f"Script src '{src}' must not be an external absolute URL")


class TestFeedTypographyAndOnestFont(unittest.TestCase):
    """Test 4: Strict Onest font usage in feed.html and feed.css."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(FRONTEND_DIR, 'feed.html'), 'r', encoding='utf-8') as f:
            cls.feed_html = f.read()
        with open(os.path.join(FRONTEND_DIR, 'css', 'feed.css'), 'r', encoding='utf-8') as f:
            cls.feed_css = f.read()
        with open(os.path.join(FRONTEND_DIR, 'css', 'theme.css'), 'r', encoding='utf-8') as f:
            cls.theme_css = f.read()

    def test_strict_onest_font_usage(self):
        """Verify that Onest font family is explicitly declared and applied in feed.html, feed.css, and theme.css."""
        self.assertIn("'Onest'", self.feed_html, "feed.html must declare 'Onest' font family")
        self.assertTrue(
            "'Onest'" in self.feed_css or "var(--font-sans)" in self.feed_css,
            "feed.css must declare 'Onest' or use var(--font-sans)"
        )
        self.assertIn("font-family: 'Onest'", self.theme_css, "theme.css must declare @font-face for 'Onest'")
        self.assertIn("--font-sans: 'Onest'", self.theme_css, "theme.css must configure --font-sans with 'Onest'")

    def test_no_legacy_disallowed_font_families(self):
        """Verify that legacy font families (Inter, Manrope, JetBrains Mono) are not used in font-family rules."""
        disallowed_fonts_pattern = re.compile(
            r'font-family:\s*[^;]*\b(?:Inter|Manrope|JetBrains Mono)\b',
            re.IGNORECASE
        )

        for content, filename in [
            (self.feed_html, 'feed.html'),
            (self.feed_css, 'css/feed.css')
        ]:
            matches = disallowed_fonts_pattern.findall(content)
            self.assertEqual(len(matches), 0, f"Disallowed font family found in {filename}: {matches}")


class TestFeedHeaderMenuAndNavigation(unittest.TestCase):
    """Test 6 & 7: Complete removal of top header menu and navigation in feed.html (task-22)."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(FRONTEND_DIR, 'feed.html'), 'r', encoding='utf-8') as f:
            cls.feed_html = f.read()

    def test_header_brand_logo_and_icon(self):
        """Verify #appHeader and top brand logo are completely removed from feed.html,
        while page title and platform identity are preserved."""
        # Top header and brand-logo element must be completely absent (task-22)
        self.assertNotIn('id="appHeader"', self.feed_html, "#appHeader must not be present in feed.html")
        self.assertNotIn('class="app-header"', self.feed_html, "class 'app-header' must not be present in feed.html")
        self.assertNotIn('<header', self.feed_html, "<header> element must not be present in feed.html")
        self.assertNotIn('class="brand-logo"', self.feed_html, ".brand-logo must not be present in feed.html")
        self.assertNotIn('class="smart-contract-logo-svg"', self.feed_html, "header logo SVG must not be present in feed.html")

        # Page title and platform identity outside header are intact
        self.assertIn('<title>Лента публикаций — SmartContractum</title>', self.feed_html)
        self.assertIn('feed-main-container', self.feed_html)

    def test_header_navigation_links(self):
        """Verify header navigation (#headerNav, #navIndex, #navCommunity, #navEditor)
        is completely removed from feed.html, while feed functional controls remain intact."""
        # Header navigation container and links must be completely absent (task-22)
        self.assertNotIn('id="headerNav"', self.feed_html, "#headerNav must be removed from feed.html")
        self.assertNotIn('class="header-nav"', self.feed_html, "class 'header-nav' must be removed from feed.html")
        self.assertNotIn('id="navIndex"', self.feed_html, "#navIndex must be removed from feed.html")
        self.assertNotIn('id="navCommunity"', self.feed_html, "#navCommunity must be removed from feed.html")
        self.assertNotIn('id="navEditor"', self.feed_html, "#navEditor must be removed from feed.html")

        # Legacy items remain absent
        self.assertNotIn('Эксперты', self.feed_html)
        self.assertNotIn('База знаний', self.feed_html)

        # Feed functional controls and filters are preserved
        self.assertIn('feed-filter-bar', self.feed_html)
        self.assertIn('feed-filter-btn', self.feed_html)
        self.assertIn('id="feedCardsContainer"', self.feed_html)

    def test_theme_toggle_switch_in_header(self):
        """Verify theme toggle button (#btnThemeToggle) is completely removed from feed.html,
        while theme attribute and initialization script remain intact."""
        # Theme toggle button and track must be completely removed from header (task-22)
        self.assertNotIn('id="btnThemeToggle"', self.feed_html, "#btnThemeToggle must be removed from feed.html")
        self.assertNotIn('theme-toggle-track', self.feed_html, "theme-toggle-track must be removed from feed.html")
        self.assertNotIn('theme-icon-moon', self.feed_html, "theme-icon-moon must be removed from feed.html")
        self.assertNotIn('theme-icon-sun', self.feed_html, "theme-icon-sun must be removed from feed.html")

        # Early theme initialization script and data-theme attribute must be preserved
        self.assertIn('data-theme="dark"', self.feed_html)
        self.assertIn("localStorage.getItem('ag_theme')", self.feed_html)

    def test_user_login_button_in_header(self):
        """Verify user login button (#headerLoginBtn) is completely removed from feed.html,
        while main layout container is preserved."""
        # Header user/login controls must be completely absent (task-22)
        self.assertNotIn('id="headerLoginBtn"', self.feed_html, "#headerLoginBtn must be removed from feed.html")
        self.assertNotIn('header-login-action-btn', self.feed_html, ".header-login-action-btn must be removed from feed.html")
        self.assertNotIn('header-user-bar', self.feed_html, ".header-user-bar must be removed from feed.html")
        self.assertNotIn('btn-user-svg', self.feed_html, ".btn-user-svg must be removed from feed.html")

        # Main layout structure is intact
        self.assertIn('class="app-container"', self.feed_html)
        self.assertIn('class="feed-main-container"', self.feed_html)

    def test_navigation_to_editor(self):
        """Verify CTA #btnHeroWrite links to editor.html, while header #navEditor is completely removed."""
        # Header #navEditor is absent (task-22)
        self.assertNotIn('id="navEditor"', self.feed_html, "#navEditor must be removed from feed.html")

        # Hero CTA write button (#btnHeroWrite) links to editor.html
        cta_match = re.search(
            r'<a[^>]*id="btnHeroWrite"[^>]*href="editor\.html"[^>]*>|<a[^>]*href="editor\.html"[^>]*id="btnHeroWrite"[^>]*>',
            self.feed_html
        )
        self.assertIsNotNone(cta_match, "CTA button #btnHeroWrite with href='editor.html' not found in feed.html")
        self.assertIn('Написать', self.feed_html)


class TestFeedTwoColumnGridAndWidgets(unittest.TestCase):
    """Test 9: Centered 2-column feed grid, cards container, filter buttons, and sidebar widgets."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(FRONTEND_DIR, 'feed.html'), 'r', encoding='utf-8') as f:
            cls.feed_html = f.read()
        with open(os.path.join(FRONTEND_DIR, 'css', 'feed.css'), 'r', encoding='utf-8') as f:
            cls.feed_css = f.read()
        with open(os.path.join(FRONTEND_DIR, 'js', 'feed.js'), 'r', encoding='utf-8') as f:
            cls.feed_js = f.read()

    def test_two_column_grid_structure(self):
        """Verify 2-column grid layout in feed.html and feed.css."""
        # feed.html layout classes
        self.assertIn('feed-main-container', self.feed_html, "feed.html must contain .feed-main-container")
        self.assertIn('feed-layout-grid', self.feed_html, "feed.html must contain .feed-layout-grid")
        self.assertIn('feed-main-column', self.feed_html, "feed.html must contain .feed-main-column")
        self.assertIn('feed-sidebar-column', self.feed_html, "feed.html must contain .feed-sidebar-column")

        # feed.css grid definition
        grid_match = re.search(r'\.feed-layout-grid\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(grid_match, ".feed-layout-grid rule not found in feed.css")
        grid_css = grid_match.group(1)
        self.assertIn('display: grid', grid_css)
        self.assertIn('grid-template-columns', grid_css)

    def test_feed_cards_container_and_filter_buttons(self):
        """Verify #feedCardsContainer, .feed-filter-btn category filters, and .feed-card card styles."""
        # Cards container
        self.assertIn('id="feedCardsContainer"', self.feed_html, "#feedCardsContainer not found in feed.html")

        # Filter buttons
        filter_buttons = re.findall(r'<button[^>]*class=["\'][^"\']*feed-filter-btn[^"\']*["\'][^>]*>(.*?)</button>', self.feed_html)
        self.assertGreaterEqual(len(filter_buttons), 4, "Expected at least 4 category filter buttons")

        required_categories = ['Все', 'Разработка', 'Безопасность', 'Дизайн']
        for cat in required_categories:
            self.assertTrue(
                any(cat in btn for btn in filter_buttons),
                f"Filter button for '{cat}' not found in feed.html"
            )

        # Card styles in feed.css
        self.assertIn('.feed-card', self.feed_css, ".feed-card styles must be defined in feed.css")
        self.assertIn('.card-meta', self.feed_css, ".card-meta styles must be defined in feed.css")

        # Dynamic cards rendering in feed.js
        self.assertIn('feedCardsContainer', self.feed_js, "feed.js must manage feedCardsContainer")
        self.assertIn('feed-card', self.feed_js, "feed.js must render .feed-card elements")

    def test_feed_sidebar_widgets(self):
        """Verify sidebar contains required widgets (Создать публикацию, Популярные темы, О платформе)."""
        sidebar_match = re.search(r'<aside[^>]*class="[^"]*feed-sidebar-column[^"]*"[^>]*>(.*?)</aside>', self.feed_html, re.DOTALL)
        self.assertIsNotNone(sidebar_match, "feed-sidebar-column not found in feed.html")
        sidebar_content = sidebar_match.group(1)

        # Widget 1: Создать публикацию with link to editor.html
        self.assertIn('Создать публикацию', sidebar_content)
        self.assertTrue(
            re.search(r'<a[^>]*href=["\']editor\.html["\'][^>]*>[\s\S]*?Открыть редактор[\s\S]*?</a>', sidebar_content),
            "Link to editor.html not found in sidebar widget"
        )

        # Widget 2: Популярные темы
        self.assertIn('Популярные темы', sidebar_content)
        self.assertIn('widget-tags-cloud', sidebar_content)

        # Widget 3: О платформе SmartContractum
        self.assertIn('О платформе', sidebar_content)
        self.assertIn('ПКСК ЦБ РФ', sidebar_content)
        self.assertIn('Offline-First', sidebar_content)


class TestCrossNavigationAndColorPalette(unittest.TestCase):
    """Test 7 & 8: Cross-navigation between feed and editor, and theme color palette."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(FRONTEND_DIR, 'feed.html'), 'r', encoding='utf-8') as f:
            cls.feed_html = f.read()
        with open(os.path.join(FRONTEND_DIR, 'editor.html'), 'r', encoding='utf-8') as f:
            cls.editor_html = f.read()
        with open(os.path.join(FRONTEND_DIR, 'index.html'), 'r', encoding='utf-8') as f:
            cls.index_html = f.read()
        with open(os.path.join(FRONTEND_DIR, 'css', 'theme.css'), 'r', encoding='utf-8') as f:
            cls.theme_css = f.read()

    def test_cross_navigation_between_feed_and_editor(self):
        """Verify cross-navigation and layout integrity:
        - #appHeader and #headerNav are completely removed across feed.html, editor.html, index.html.
        - feed.html links to editor.html via #btnHeroWrite.
        - index.html links to feed.html and editor.html via hero CTA buttons.
        - editor.html maintains document action bar and workspace without top header."""
        # 1. Top header and header nav are completely absent on all pages (task-22)
        for page_name, html in [('feed.html', self.feed_html), ('editor.html', self.editor_html), ('index.html', self.index_html)]:
            self.assertNotIn('id="appHeader"', html, f"#appHeader must not exist in {page_name}")
            self.assertNotIn('class="app-header"', html, f"class 'app-header' must not exist in {page_name}")
            self.assertNotIn('<header', html, f"<header> tag must not exist in {page_name}")
            self.assertNotIn('id="headerNav"', html, f"#headerNav must not exist in {page_name}")

        # 2. feed.html -> editor.html via CTA #btnHeroWrite
        self.assertTrue(
            re.search(r'<a[^>]*id=["\']btnHeroWrite["\'][^>]*href=["\']editor\.html["\']|<a[^>]*href=["\']editor\.html["\'][^>]*id=["\']btnHeroWrite["\']', self.feed_html),
            "feed.html must link to editor.html via #btnHeroWrite"
        )

        # 3. index.html -> feed.html & editor.html via hero actions
        self.assertTrue(
            re.search(r'<a[^>]*href=["\']feed\.html["\']', self.index_html),
            "index.html must link to feed.html"
        )
        self.assertTrue(
            re.search(r'<a[^>]*href=["\']editor\.html["\']', self.index_html),
            "index.html must link to editor.html"
        )

        # 4. editor.html preserves functional layout (#editorDocumentBar and editor workspace)
        self.assertIn('id="editorDocumentBar"', self.editor_html, "#editorDocumentBar must exist in editor.html")
        self.assertIn('id="editorSidebar"', self.editor_html, "#editorSidebar must exist in editor.html")

    def test_both_pages_default_to_dark_theme(self):
        """Verify both feed.html and editor.html root elements default to data-theme='dark'."""
        for html_content, filename in [
            (self.feed_html, 'feed.html'),
            (self.editor_html, 'editor.html')
        ]:
            html_tag_match = re.search(r'<html\b([^>]*)>', html_content)
            self.assertIsNotNone(html_tag_match, f"html tag not found in {filename}")
            attrs = html_tag_match.group(1)
            self.assertIn('data-theme="dark"', attrs, f"{filename} root element must have data-theme='dark'")

    def test_theme_color_palette_tokens(self):
        """Verify theme.css defines dark and light theme tokens."""
        # 1. Dark Theme (CoinMarketCap Midnight Navy)
        dark_match = re.search(r'\[data-theme=["\']?dark["\']?\]\s*\{([^}]+)\}', self.theme_css)
        self.assertIsNotNone(dark_match, "[data-theme='dark'] block not found in theme.css")
        dark_css = dark_match.group(1)

        expected_dark_tokens = {
            '--bg-page': '#0b1426',
            '--bg-editor': '#171924',
            '--border-color': '#222531',
            '--accent-color': '#3861fb',
            '--success-color': '#16c784'
        }
        for var_name, hex_val in expected_dark_tokens.items():
            pattern = rf'{re.escape(var_name)}:\s*{re.escape(hex_val)};'
            self.assertTrue(
                re.search(pattern, dark_css),
                f"CSS variable '{var_name}' with value '{hex_val}' not found in [data-theme='dark'] in theme.css"
            )

        # 2. Light Theme (High Contrast Dark Text)
        light_match = re.search(r'\[data-theme=["\']?light["\']?\]\s*\{([^}]+)\}', self.theme_css)
        self.assertIsNotNone(light_match, "[data-theme='light'] block not found in theme.css")
        light_css = light_match.group(1)

        self.assertTrue(
            re.search(r'--text-primary:\s*#0f172a\b', light_css),
            "theme.css must define --text-primary: #0f172a in [data-theme='light'] block"
        )


class TestZeroEmojisInInterface(unittest.TestCase):
    """Test 5: Strict zero emojis check across feed.html, editor.html, and CSS/JS assets."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(FRONTEND_DIR, 'feed.html'), 'r', encoding='utf-8') as f:
            cls.feed_html = f.read()
        with open(os.path.join(FRONTEND_DIR, 'editor.html'), 'r', encoding='utf-8') as f:
            cls.editor_html = f.read()
        with open(os.path.join(FRONTEND_DIR, 'css', 'feed.css'), 'r', encoding='utf-8') as f:
            cls.feed_css = f.read()
        with open(os.path.join(FRONTEND_DIR, 'js', 'feed.js'), 'r', encoding='utf-8') as f:
            cls.feed_js = f.read()
        with open(os.path.join(FRONTEND_DIR, 'css', 'editor.css'), 'r', encoding='utf-8') as f:
            cls.editor_css = f.read()

        cls.forbidden_emojis = [
            '📁', '📤', '🌐', '📝', '💾', '📥', '🌓', '⌨️', '⌨', '🗑️', '🗑',
            '✨', '💡', '📋', '🖼️', '🖼', '👤', '⚓', '✏️', '✏', '👁️', '👁',
            '⏱️', '⏱', '🔤', '⚡', '📊', '💻', '🔄', '🔥', '🚀', '💬', '❤️',
            '👍', '🎉', '🌟', '💎', '🔒', '🛡️', '⚙️', '🔍'
        ]
        cls.emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]|[\u2b50]')

    def test_zero_emojis_in_html(self):
        """Verify zero emojis in feed.html and editor.html."""
        for filename, content in [('feed.html', self.feed_html), ('editor.html', self.editor_html)]:
            for emoji in self.forbidden_emojis:
                self.assertNotIn(emoji, content, f"Forbidden emoji '{emoji}' found in {filename}")
            matches = self.emoji_pattern.findall(content)
            self.assertEqual(len(matches), 0, f"Unexpected emoji characters found in {filename}: {matches}")

    def test_zero_emojis_in_styles_and_scripts(self):
        """Verify zero emojis in feed.css, feed.js, and editor.css."""
        for filename, content in [('feed.css', self.feed_css), ('feed.js', self.feed_js), ('editor.css', self.editor_css)]:
            for emoji in self.forbidden_emojis:
                self.assertNotIn(emoji, content, f"Forbidden emoji '{emoji}' found in {filename}")
            matches = self.emoji_pattern.findall(content)
            self.assertEqual(len(matches), 0, f"Unexpected emoji characters found in {filename}: {matches}")


class TestEditorFeedVisualAlignment(unittest.TestCase):
    """Test Suite for task-15: Editor visual alignment with feed page, top navigation header,
    document action bar, unified button design, zero emojis, and Onest font."""

    @classmethod
    def setUpClass(cls):
        cls.editor_html_path = os.path.join(FRONTEND_DIR, 'editor.html')
        cls.editor_css_path = os.path.join(FRONTEND_DIR, 'css', 'editor.css')
        with open(cls.editor_html_path, 'r', encoding='utf-8') as f:
            cls.editor_html = f.read()
        with open(cls.editor_css_path, 'r', encoding='utf-8') as f:
            cls.editor_css = f.read()

    def test_editor_has_top_navigation_header(self):
        """Verify editor.html completely excludes the top header (#appHeader, brand-logo,
        #headerNav, #btnThemeToggle, #headerLoginBtn) and #editorDocumentBar is the first primary layout element."""
        # Strict requirement: #appHeader and all header elements must be completely absent (task-22)
        self.assertNotIn('id="appHeader"', self.editor_html, "#appHeader must be completely removed from editor.html")
        self.assertNotIn('class="app-header"', self.editor_html, "class 'app-header' must be removed from editor.html")
        self.assertNotIn('<header', self.editor_html, "<header> element must be completely removed from editor.html")
        self.assertNotIn('id="headerNav"', self.editor_html, "#headerNav must be completely removed from editor.html")
        self.assertNotIn('id="btnThemeToggle"', self.editor_html, "#btnThemeToggle must be completely removed from editor.html")
        self.assertNotIn('id="headerLoginBtn"', self.editor_html, "#headerLoginBtn must be completely removed from editor.html")

        # #editorDocumentBar is present and is the first layout element inside .app-container
        app_container_pos = self.editor_html.find('class="app-container"')
        self.assertNotEqual(app_container_pos, -1, "app-container not found in editor.html")
        doc_bar_pos = self.editor_html.find('id="editorDocumentBar"')
        self.assertNotEqual(doc_bar_pos, -1, "#editorDocumentBar not found in editor.html")
        self.assertTrue(doc_bar_pos > app_container_pos, "#editorDocumentBar must be inside .app-container")

        # Ensure no header elements between app-container and editorDocumentBar
        between_content = self.editor_html[app_container_pos:doc_bar_pos]
        self.assertNotIn('<header', between_content, "No <header> element allowed before #editorDocumentBar")

        # editor.css sets .editor-document-bar top: 0
        doc_bar_css_match = re.search(r'\.editor-document-bar\s*\{([^}]+)\}', self.editor_css)
        self.assertIsNotNone(doc_bar_css_match, ".editor-document-bar rule not found in editor.css")
        self.assertTrue(
            re.search(r'top:\s*0\b', doc_bar_css_match.group(1)),
            ".editor-document-bar must have top: 0 in editor.css"
        )

    def test_editor_has_document_action_bar(self):
        """Verify editor.html has #editorDocumentBar containing #btn-drafts-modal, #drafts-badge,
        and #save-status; Antigravity Writer and #btn-more-actions are removed."""
        bar_start = self.editor_html.find('id="editorDocumentBar"')
        self.assertNotEqual(bar_start, -1, "#editorDocumentBar not found in editor.html")
        bar_end = self.editor_html.find('class="app-main-layout"', bar_start)
        self.assertNotEqual(bar_end, -1, "app-main-layout boundary not found after editorDocumentBar")
        bar_content = self.editor_html[bar_start:bar_end]

        # Antigravity Writer removed per requirement 4
        self.assertNotIn('Antigravity Writer', bar_content, "Antigravity Writer must be removed from #editorDocumentBar")
        self.assertNotIn('brand-icon', bar_content)

        # #btn-drafts-modal
        self.assertIn('id="btn-drafts-modal"', bar_content, "#btn-drafts-modal not found in #editorDocumentBar")

        # #drafts-badge
        self.assertIn('id="drafts-badge"', bar_content, "#drafts-badge not found in #editorDocumentBar")

        # #save-status
        self.assertIn('id="save-status"', bar_content, "#save-status not found in #editorDocumentBar")

        # #btn-more-actions removed per requirement 10
        self.assertNotIn('id="btn-more-actions"', bar_content, "#btn-more-actions must be removed from #editorDocumentBar")

    def test_editor_buttons_design_and_palette(self):
        """Verify editor.css defines the unified button styles:
        - .btn-primary with linear-gradient containing #3861fb and border-radius 9px.
        - .btn-next-to-pub / #btn-next-to-settings with emerald gradient containing #10b981 / #059669 and box-shadow.
        - secondary buttons (.btn, .btn-drafts) with background #171924, border #222531, and hover border #38bdf8."""

        # 1. .btn-primary with linear-gradient containing #3861fb and border-radius 9px
        btn_primary_match = re.search(r'\.btn-primary\s*\{([^}]+)\}', self.editor_css)
        self.assertIsNotNone(btn_primary_match, ".btn-primary rule block not found in editor.css")
        primary_css = btn_primary_match.group(1)
        self.assertIn('linear-gradient', primary_css, ".btn-primary must use linear-gradient")
        self.assertIn('#3861fb', primary_css, ".btn-primary gradient must contain #3861fb")
        self.assertTrue(re.search(r'border-radius:\s*9px', primary_css), ".btn-primary must have border-radius: 9px")

        # 2. .btn-next-to-pub / #btn-next-to-settings with emerald gradient containing #10b981 / #059669 and box-shadow
        next_pub_match = re.search(r'([^{]*\.btn-next-to-pub[^{]*)\{([^}]+)\}', self.editor_css)
        self.assertIsNotNone(next_pub_match, ".btn-next-to-pub rule block not found in editor.css")
        next_pub_selectors = next_pub_match.group(1)
        next_pub_css = next_pub_match.group(2)
        self.assertTrue('#btn-next-to-settings' in next_pub_selectors or '.btn-next-to-pub' in next_pub_selectors,
                        "#btn-next-to-settings or .btn-next-to-pub not found in next-to-pub selectors")
        self.assertIn('#10b981', next_pub_css, ".btn-next-to-pub gradient must contain #10b981")
        self.assertIn('#059669', next_pub_css, ".btn-next-to-pub gradient must contain #059669")
        self.assertIn('box-shadow', next_pub_css, ".btn-next-to-pub must have box-shadow")

        # 3. secondary buttons (.btn, .btn-drafts) with background #171924, border #222531, and hover border #38bdf8
        btn_match = re.search(r'(?<![a-zA-Z0-9_-])\.btn\s*\{([^}]+)\}', self.editor_css)
        self.assertIsNotNone(btn_match, ".btn rule block not found in editor.css")
        btn_css = btn_match.group(1)
        self.assertTrue(re.search(r'background(?:-color)?:\s*#171924', btn_css),
                        ".btn must have background #171924")
        self.assertTrue(re.search(r'border(?:-color)?:\s*(?:1px\s+solid\s+)?#222531', btn_css),
                        ".btn must have border #222531")

        btn_hover_match = re.search(r'(?<![a-zA-Z0-9_-])\.btn:hover\s*\{([^}]+)\}', self.editor_css)
        self.assertIsNotNone(btn_hover_match, ".btn:hover rule block not found in editor.css")
        btn_hover_css = btn_hover_match.group(1)
        self.assertTrue(re.search(r'border-color:\s*#38bdf8', btn_hover_css),
                        ".btn:hover must have hover border-color #38bdf8")

        # .btn-drafts exists and inherits .btn styling
        self.assertIn('.btn-drafts', self.editor_css, ".btn-drafts selector must be present in editor.css")
        self.assertIn('class="btn btn-drafts"', self.editor_html,
                      "Drafts button in editor.html must have class 'btn btn-drafts'")

    def test_editor_zero_emojis_and_onest_font(self):
        """Verify editor.html and editor.css contain zero emoji characters and strictly use Onest font."""
        forbidden_emojis = [
            '📁', '📤', '🌐', '📝', '💾', '📥', '🌓', '⌨️', '⌨', '🗑️', '🗑',
            '✨', '💡', '📋', '🖼️', '🖼', '👤', '⚓', '✏️', '✏', '👁️', '👁',
            '⏱️', '⏱', '🔤', '⚡', '📊', '💻', '🔄', '🔥', '🚀', '💬', '❤️',
            '👍', '🎉', '🌟', '💎', '🔒', '🛡️', '⚙️', '🔍'
        ]
        emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]|[\u2b50]')

        for filename, content in [('editor.html', self.editor_html), ('editor.css', self.editor_css)]:
            for emoji in forbidden_emojis:
                self.assertNotIn(emoji, content, f"Forbidden emoji '{emoji}' found in {filename}")
            matches = emoji_pattern.findall(content)
            self.assertEqual(len(matches), 0, f"Unexpected emoji characters found in {filename}: {matches}")

        # Strict Onest font usage
        self.assertIn("'Onest'", self.editor_html, "editor.html must declare 'Onest' font family")
        self.assertIn("'Onest'", self.editor_css, "editor.css must declare 'Onest' font family")

        disallowed_fonts_pattern = re.compile(
            r'font-family:\s*[^;]*\b(?:Inter|Manrope|JetBrains Mono)\b',
            re.IGNORECASE
        )
        for filename, content in [('editor.html', self.editor_html), ('editor.css', self.editor_css)]:
            matches = disallowed_fonts_pattern.findall(content)
            self.assertEqual(len(matches), 0, f"Disallowed legacy font found in {filename}: {matches}")


class TestEditorVisualAndThemeIssues(unittest.TestCase):
    """Test Suite for task-16 & task-18: Editor visual and theme fixes:
    - High-contrast text tokens in light theme (#0f172a in theme.css).
    - Editor header exact feed structure (logo-title with logo-smart & logo-contractum,
      all 2 nav links with .nav-icon-box and SVG icons, #navEditor with 'nav-link active',
      and legacy forum_social.css NOT linked).
    - Onest font smoothing (-webkit-font-smoothing: antialiased) and antialiasing (text-rendering: optimizeLegibility).
    """

    @classmethod
    def setUpClass(cls):
        cls.editor_html_path = os.path.join(FRONTEND_DIR, 'editor.html')
        cls.editor_css_path = os.path.join(FRONTEND_DIR, 'css', 'editor.css')
        cls.theme_css_path = os.path.join(FRONTEND_DIR, 'css', 'theme.css')

        with open(cls.editor_html_path, 'r', encoding='utf-8') as f:
            cls.editor_html = f.read()
        with open(cls.editor_css_path, 'r', encoding='utf-8') as f:
            cls.editor_css = f.read()
        with open(cls.theme_css_path, 'r', encoding='utf-8') as f:
            cls.theme_css = f.read()

    def test_light_theme_high_contrast_text_tokens(self):
        """Verify that theme.css defines high-contrast dark text (#0f172a)
        for [data-theme="light"], ensuring zero white text on white backgrounds in light mode."""
        theme_light_match = re.search(r'\[data-theme=["\']?light["\']?\]\s*\{([^}]+)\}', self.theme_css)
        self.assertIsNotNone(theme_light_match, "[data-theme='light'] block not found in theme.css")
        theme_light_css = theme_light_match.group(1)

        self.assertTrue(
            re.search(r'--text-primary:\s*#0f172a\b', theme_light_css),
            "theme.css must define --text-primary: #0f172a in [data-theme='light'] block"
        )
        self.assertNotIn('--text-primary: #ffffff', theme_light_css,
                         "theme.css must not define --text-primary as #ffffff in light mode")
        self.assertNotIn('--text-primary: #fff;', theme_light_css,
                         "theme.css must not define --text-primary as #fff in light mode")

    def test_editor_header_exact_feed_structure(self):
        """Verify editor.html has top header completely removed (#appHeader, logo-title, #headerNav),
        forum_social.css is NOT linked, and editor workspace is intact."""
        # Top header container must be completely absent in editor.html (task-22)
        self.assertNotIn('id="appHeader"', self.editor_html, "#appHeader must not exist in editor.html")
        self.assertNotIn('class="app-header"', self.editor_html, "class 'app-header' must not exist in editor.html")
        self.assertNotIn('<header', self.editor_html, "<header> tag must not exist in editor.html")
        self.assertNotIn('id="headerNav"', self.editor_html, "#headerNav must not exist in editor.html")
        self.assertNotIn('class="logo-title"', self.editor_html, "logo-title must not exist in editor.html")

        # forum_social.css must NOT be linked
        self.assertNotIn('forum_social.css', self.editor_html, "forum_social.css must not be linked in editor.html")

        # Core editor workspace elements remain intact
        self.assertIn('id="editorDocumentBar"', self.editor_html, "#editorDocumentBar must exist in editor.html")
        self.assertIn('id="editorSidebar"', self.editor_html, "#editorSidebar must exist in editor.html")
        self.assertIn('id="editor-card"', self.editor_html, "#editor-card must exist in editor.html")
        self.assertIn('id="btn-drafts-modal"', self.editor_html, "#btn-drafts-modal must exist in editor.html")
        self.assertIn('id="btn-next-to-settings"', self.editor_html, "#btn-next-to-settings must exist in editor.html")

    def test_onest_font_smoothing_and_antialiasing(self):
        """Verify editor.css or editor.html specifies -webkit-font-smoothing: antialiased
        and text-rendering: optimizeLegibility with Onest font."""
        # Check -webkit-font-smoothing: antialiased
        has_antialiased = (
            bool(re.search(r'-webkit-font-smoothing:\s*antialiased', self.editor_css)) or
            bool(re.search(r'-webkit-font-smoothing:\s*antialiased', self.editor_html)) or
            bool(re.search(r'-webkit-font-smoothing:\s*antialiased', self.theme_css))
        )
        self.assertTrue(has_antialiased, "Expected -webkit-font-smoothing: antialiased")

        # Check text-rendering: optimizeLegibility
        has_optimize_legibility = (
            bool(re.search(r'text-rendering:\s*optimizeLegibility', self.editor_css)) or
            bool(re.search(r'text-rendering:\s*optimizeLegibility', self.editor_html)) or
            bool(re.search(r'text-rendering:\s*optimizeLegibility', self.theme_css))
        )
        self.assertTrue(has_optimize_legibility, "Expected text-rendering: optimizeLegibility")

        # Check Onest font
        self.assertIn("'Onest'", self.editor_css, "editor.css must declare 'Onest' font family")
        self.assertIn("'Onest'", self.editor_html, "editor.html must declare 'Onest' font family")


class TestTask19UnifiedHeaderNavigationAndLayout(unittest.TestCase):
    """Test Suite for task-19: Unified header navigation, anti-shift 3-col grid, and identical typography."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(FRONTEND_DIR, 'index.html'), 'r', encoding='utf-8') as f:
            cls.index_html = f.read()
        with open(os.path.join(FRONTEND_DIR, 'feed.html'), 'r', encoding='utf-8') as f:
            cls.feed_html = f.read()
        with open(os.path.join(FRONTEND_DIR, 'editor.html'), 'r', encoding='utf-8') as f:
            cls.editor_html = f.read()
        with open(os.path.join(FRONTEND_DIR, 'css', 'theme.css'), 'r', encoding='utf-8') as f:
            cls.theme_css = f.read()
        with open(os.path.join(FRONTEND_DIR, 'css', 'editor.css'), 'r', encoding='utf-8') as f:
            cls.editor_css = f.read()

    def test_unified_brand_logo_across_all_pages(self):
        """Verify header brand logo (.brand-logo, #appHeader) is completely removed from all 3 pages
        (index.html, feed.html, editor.html), while valid page structures remain."""
        pages = [('index.html', self.index_html), ('feed.html', self.feed_html), ('editor.html', self.editor_html)]
        for name, html in pages:
            self.assertNotIn('class="brand-logo"', html, f"brand-logo must be removed from {name}")
            self.assertNotIn("class='brand-logo'", html, f"brand-logo must be removed from {name}")
            self.assertNotIn('id="appHeader"', html, f"appHeader must be removed from {name}")
            self.assertNotIn('class="app-header"', html, f"app-header must be removed from {name}")
            self.assertNotIn('<header', html, f"<header> tag must be removed from {name}")
            self.assertIn('<!DOCTYPE html>', html, f"<!DOCTYPE html> missing in {name}")
            self.assertIn('<title>', html, f"<title> missing in {name}")

    def test_unified_navigation_routing_and_active_states(self):
        """Verify #headerNav and all header navigation links (#navIndex, #navCommunity, #navEditor)
        are completely removed across all pages (index.html, feed.html, editor.html)."""
        pages = [
            (self.index_html, 'index.html'),
            (self.feed_html, 'feed.html'),
            (self.editor_html, 'editor.html')
        ]

        for html, filename in pages:
            # #headerNav and header-nav must be completely absent (task-22)
            self.assertNotIn('id="headerNav"', html, f"#headerNav must be removed from {filename}")
            self.assertNotIn('class="header-nav"', html, f"class 'header-nav' must be removed from {filename}")
            self.assertNotIn('id="navIndex"', html, f"#navIndex must be removed from {filename}")
            self.assertNotIn('id="navCommunity"', html, f"#navCommunity must be removed from {filename}")
            self.assertNotIn('id="navEditor"', html, f"#navEditor must be removed from {filename}")

            # App container is intact
            self.assertIn('class="app-container"', html, f"app-container must exist in {filename}")

    def test_community_nav_item_present_on_all_pages(self):
        """Verify header navigation #headerNav and #navCommunity are completely absent across
        index.html, feed.html, and editor.html, while community feed remains accessible from index.html."""
        pages = [
            ('index.html', self.index_html),
            ('feed.html', self.feed_html),
            ('editor.html', self.editor_html),
        ]
        for filename, html in pages:
            self.assertNotIn('id="headerNav"', html, f"#headerNav must not exist in {filename}")
            self.assertNotIn('id="navCommunity"', html, f"#navCommunity must not exist in {filename}")

        # Community feed is accessible from index.html hero actions
        self.assertTrue(
            re.search(r'<a[^>]*href=["\']feed\.html["\']', self.index_html),
            "index.html must provide link to feed.html"
        )

    def test_stable_scrollbar_and_header_grid_layout_css(self):
        """Verify overflow-y: scroll, scrollbar-gutter: stable, --header-height: 0px,
        and obsolete header CSS rules are removed from theme.css."""
        # html rule
        self.assertIn('overflow-y: scroll;', self.theme_css)
        self.assertIn('scrollbar-gutter: stable;', self.theme_css)

        # Header height set to 0px
        self.assertIn('--header-height: 0px;', self.theme_css, "--header-height must be 0px in theme.css")

        # Dead CSS rules removed from theme.css (task-22)
        self.assertNotIn('.header-container', self.theme_css, ".header-container must be removed from theme.css")
        self.assertNotIn('.header-nav', self.theme_css, ".header-nav must be removed from theme.css")
        self.assertNotIn('.header-right-group', self.theme_css, ".header-right-group must be removed from theme.css")
        self.assertNotIn('.btn-theme-toggle', self.theme_css, ".btn-theme-toggle must be removed from theme.css")
        self.assertNotIn('.header-user-bar', self.theme_css, ".header-user-bar must be removed from theme.css")

    def test_exact_header_markup_identity(self):
        """Verify header markup is 100% absent across index.html, feed.html, and editor.html."""
        pages = [
            ('index.html', self.index_html),
            ('feed.html', self.feed_html),
            ('editor.html', self.editor_html),
        ]
        for name, html in pages:
            m = re.search(r'<header[^>]*id=["\']appHeader["\'][^>]*>([\s\S]*?)</header>', html)
            self.assertIsNone(m, f"<header id='appHeader'> must be completely absent in {name}")
            m_tag = re.search(r'<header\b[^>]*>', html)
            self.assertIsNone(m_tag, f"<header> tag must not exist in {name}")

    def test_no_conflicting_nav_link_overrides_in_editor_css(self):
        """Verify duplicate .nav-link overrides are removed from editor.css."""
        self.assertNotIn('.nav-link.is-active', self.editor_css)
        self.assertNotIn('.nav-link.active', self.editor_css)

    def test_header_buttons_and_typography_consistency(self):
        """Verify header buttons (#headerLoginBtn, #btnThemeToggle) and their dead CSS rules
        are completely removed across all 3 pages, while Onest typography is strictly preserved in theme.css."""
        # Header button IDs must be absent across all 3 pages
        pages = [('index.html', self.index_html), ('feed.html', self.feed_html), ('editor.html', self.editor_html)]
        for name, html in pages:
            self.assertNotIn('id="headerLoginBtn"', html, f"headerLoginBtn must not exist in {name}")
            self.assertNotIn('id="headerUserDot"', html, f"headerUserDot must not exist in {name}")
            self.assertNotIn('id="headerUserLabel"', html, f"headerUserLabel must not exist in {name}")
            self.assertNotIn('id="btnThemeToggle"', html, f"btnThemeToggle must not exist in {name}")
            self.assertNotIn('theme-toggle-track', html, f"theme-toggle-track must not exist in {name}")

        # Obsolete CSS classes for header buttons removed from theme.css
        self.assertNotIn('.header-login-action-btn', self.theme_css, ".header-login-action-btn must be removed from theme.css")
        self.assertNotIn('.btn-user-label', self.theme_css, ".btn-user-label must be removed from theme.css")
        self.assertNotIn('.nav-link', self.theme_css, ".nav-link must be removed from theme.css")

        # Typography standards in theme.css strictly preserved
        self.assertIn('--font-sans:', self.theme_css)
        self.assertIn("'Onest'", self.theme_css)
        self.assertIn('font-family: var(--font-sans);', self.theme_css)


if __name__ == '__main__':
    unittest.main()
