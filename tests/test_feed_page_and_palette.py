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
  6. Unified header in feed.html: #appHeader, brand SmartContractum (href="index.html"),
     2 navigation items (#navIndex, #navEditor),
     theme toggle #btnThemeToggle, login button #headerLoginBtn.
  7. Cross-navigation: feed.html -> editor.html via #navEditor and #btnHeroWrite;
     editor.html -> index.html via brand logo link.
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
    """Test 6 & 7: Unified header menu components and navigation in feed.html."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(FRONTEND_DIR, 'feed.html'), 'r', encoding='utf-8') as f:
            cls.feed_html = f.read()

    def test_header_brand_logo_and_icon(self):
        """Verify brand logo SmartContractum with SVG icon, href='index.html', and title in feed.html header."""
        header_match = re.search(r'<header[^>]*id=["\']appHeader["\'][^>]*>(.*?)</header>', self.feed_html, re.DOTALL)
        if not header_match:
            header_match = re.search(r'<header[^>]*class="[^"]*app-header[^"]*"[^>]*>(.*?)</header>', self.feed_html, re.DOTALL)
        self.assertIsNotNone(header_match, "appHeader element not found in feed.html")
        header_content = header_match.group(1)

        # Brand logo link points to index.html
        brand_match = re.search(r'<a[^>]*class=["\'][^"\']*brand-logo[^"\']*["\'][^>]*>', header_content)
        self.assertIsNotNone(brand_match, "brand-logo link not found in header")
        brand_tag = brand_match.group(0)
        self.assertIn('href="index.html"', brand_tag, "Brand logo link must point to index.html")

        # Brand name components
        self.assertIn('Smart', header_content)
        self.assertIn('Contractum', header_content)

        # Brand logo SVG icon
        self.assertIn('class="smart-contract-logo-svg"', header_content)
        self.assertIn('<svg', header_content)

    def test_header_navigation_links(self):
        """Verify unified 2 navigation links: Главная (#navIndex), Редактор (#navEditor),
        and verify Сообщество (#navCommunity) is absent from header-nav."""
        header_match = re.search(r'<header[^>]*id=["\']appHeader["\'][^>]*>(.*?)</header>', self.feed_html, re.DOTALL)
        if not header_match:
            header_match = re.search(r'<header[^>]*class="[^"]*app-header[^"]*"[^>]*>(.*?)</header>', self.feed_html, re.DOTALL)
        self.assertIsNotNone(header_match)
        header_content = header_match.group(1)

        nav_match = re.search(r'<nav[^>]*class="[^"]*header-nav[^"]*"[^>]*>(.*?)</nav>', header_content, re.DOTALL)
        self.assertIsNotNone(nav_match, "header-nav not found inside header")
        nav_content = nav_match.group(1)

        # 1. Главная (#navIndex) with href="index.html"
        index_nav_match = re.search(
            r'<a[^>]*id=["\']navIndex["\'][^>]*href=["\']index\.html["\'][^>]*>[\s\S]*?Главная[\s\S]*?</a>|'
            r'<a[^>]*href=["\']index\.html["\'][^>]*id=["\']navIndex["\'][^>]*>[\s\S]*?Главная[\s\S]*?</a>',
            nav_content
        )
        self.assertIsNotNone(index_nav_match, "#navIndex with href='index.html' not found in header-nav")

        # 2. Редактор (#navEditor) with href="editor.html"
        editor_nav_match = re.search(
            r'<a[^>]*id=["\']navEditor["\'][^>]*href=["\']editor\.html["\'][^>]*>[\s\S]*?Редактор[\s\S]*?</a>|'
            r'<a[^>]*href=["\']editor\.html["\'][^>]*id=["\']navEditor["\'][^>]*>[\s\S]*?Редактор[\s\S]*?</a>',
            nav_content
        )
        self.assertIsNotNone(editor_nav_match, "#navEditor with href='editor.html' not found in header-nav")

        # All items must have SVG icons inside .nav-icon-box
        nav_links = re.findall(r'<a\b[^>]*>(.*?)</a>', nav_content, re.DOTALL)
        self.assertEqual(len(nav_links), 2, f"Expected exactly 2 navigation links in header, got {len(nav_links)}")
        for link_html in nav_links:
            self.assertIn('nav-icon-box', link_html)
            self.assertIn('<svg', link_html)

        # Legacy items and Сообщество (#navCommunity) removed
        self.assertNotIn('navCommunity', nav_content, "#navCommunity must not be in header-nav")
        self.assertNotIn('Сообщество', nav_content, "Text 'Сообщество' must not be in header-nav")
        self.assertNotIn('Эксперты', nav_content)
        self.assertNotIn('База знаний', nav_content)

    def test_theme_toggle_switch_in_header(self):
        """Verify theme toggle button (#btnThemeToggle) exists with role='switch' and SVG icons."""
        toggle_match = re.search(r'<button[^>]*id="btnThemeToggle"[^>]*>(.*?)</button>', self.feed_html, re.DOTALL)
        self.assertIsNotNone(toggle_match, "#btnThemeToggle button not found in feed.html")
        toggle_content = toggle_match.group(0)

        self.assertIn('role="switch"', toggle_content)
        self.assertIn('aria-label="Переключить тему оформления"', toggle_content)
        self.assertIn('theme-icon-moon', toggle_content)
        self.assertIn('theme-icon-sun', toggle_content)

    def test_user_login_button_in_header(self):
        """Verify user login button exists in feed.html header."""
        self.assertIn('id="headerLoginBtn"', self.feed_html)
        self.assertIn('header-login-action-btn', self.feed_html)
        self.assertIn('btn-user-svg', self.feed_html)
        self.assertTrue('Войти' in self.feed_html or 'Вход' in self.feed_html, "Login button text not found")

    def test_navigation_to_editor(self):
        """Verify nav link 'Редактор' and CTA #btnHeroWrite have href='editor.html'."""
        # 1. Nav link 'Редактор'
        editor_nav_match = re.search(
            r'<a[^>]*href=["\']editor\.html["\'][^>]*id=["\']navEditor["\'][^>]*>[\s\S]*?Редактор[\s\S]*?</a>|'
            r'<a[^>]*id=["\']navEditor["\'][^>]*href=["\']editor\.html["\'][^>]*>[\s\S]*?Редактор[\s\S]*?</a>',
            self.feed_html
        )
        self.assertIsNotNone(editor_nav_match, "Nav link 'Редактор' with href='editor.html' not found")

        # 2. Hero CTA write button (#btnHeroWrite)
        cta_match = re.search(
            r'<a[^>]*id="btnHeroWrite"[^>]*href="editor\.html"[^>]*>|<a[^>]*href="editor\.html"[^>]*id="btnHeroWrite"[^>]*>',
            self.feed_html
        )
        self.assertIsNotNone(cta_match, "CTA button #btnHeroWrite with href='editor.html' not found")


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
        with open(os.path.join(FRONTEND_DIR, 'css', 'theme.css'), 'r', encoding='utf-8') as f:
            cls.theme_css = f.read()

    def test_cross_navigation_between_feed_and_editor(self):
        """Verify cross-navigation: feed.html links to editor.html, and editor.html header has brand logo linking to index.html with Сообщество absent."""
        # 1. feed.html -> editor.html
        self.assertTrue(
            re.search(r'<a[^>]*id=["\']navEditor["\'][^>]*href=["\']editor\.html["\']|<a[^>]*href=["\']editor\.html["\'][^>]*id=["\']navEditor["\']', self.feed_html),
            "feed.html must link to editor.html via #navEditor"
        )
        self.assertTrue(
            re.search(r'<a[^>]*id=["\']btnHeroWrite["\'][^>]*href=["\']editor\.html["\']|<a[^>]*href=["\']editor\.html["\'][^>]*id=["\']btnHeroWrite["\']', self.feed_html),
            "feed.html must link to editor.html via #btnHeroWrite"
        )

        # 2. editor.html -> index.html via brand logo link
        editor_header_match = re.search(r'<header[^>]*id=["\']appHeader["\'][^>]*>(.*?)</header>', self.editor_html, re.DOTALL)
        self.assertIsNotNone(editor_header_match, "appHeader not found in editor.html")
        editor_header = editor_header_match.group(1)

        # Logo links to index.html
        logo_link_match = re.search(r'<a[^>]*href=["\']index\.html["\'][^>]*class=["\'][^"\']*brand-logo[^"\']*["\']|<a[^>]*class=["\'][^"\']*brand-logo[^"\']*["\'][^>]*href=["\']index\.html["\']', editor_header)
        self.assertIsNotNone(logo_link_match, "Brand logo in editor.html must link to index.html")

        # Nav link Сообщество was removed from editor.html header
        self.assertNotIn('Сообщество', editor_header, "Navigation link 'Сообщество' must not be in editor.html header")
        self.assertNotIn('navCommunity', editor_header, "id 'navCommunity' must not be in editor.html header")

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
        """Verify editor.html contains the full top header with id='appHeader', brand-logo,
        nav link #navEditor with active class, theme toggle #btnThemeToggle, and login button #headerLoginBtn."""
        header_match = re.search(r'<header[^>]*id=["\']appHeader["\'][^>]*>(.*?)</header>', self.editor_html, re.DOTALL)
        self.assertIsNotNone(header_match, "Top header with id='appHeader' not found in editor.html")
        header_content = header_match.group(1)

        # Brand-logo in header
        brand_logo_match = re.search(
            r'<a[^>]*class=["\'][^"\']*brand-logo[^"\']*["\']',
            header_content
        )
        self.assertIsNotNone(brand_logo_match, "brand-logo link not found in editor top header")

        # Nav link #navEditor with class "is-active" or "active"
        nav_editor_match = re.search(
            r'<a[^>]*id=["\']navEditor["\'][^>]*class=["\'][^"\']*\b(?:is-active|active)\b[^"\']*["\']|'
            r'<a[^>]*class=["\'][^"\']*\b(?:is-active|active)\b[^"\']*["\'][^>]*id=["\']navEditor["\']',
            header_content
        )
        self.assertIsNotNone(nav_editor_match, "Nav link #navEditor with active class not found in editor top header")

        # Theme toggle button #btnThemeToggle
        self.assertIn('id="btnThemeToggle"', header_content, "#btnThemeToggle button not found in editor top header")

        # User login button #headerLoginBtn
        self.assertIn('id="headerLoginBtn"', header_content, "#headerLoginBtn button not found in editor top header")

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
        """Verify editor.html header contains:
        * logo-title with logo-smart ('Smart') and logo-contractum ('Contractum').
        * all 2 navigation links contain .nav-icon-box with SVG icons.
        * #navEditor with 'nav-link active'.
        * #navCommunity and 'Сообщество' absent from headerNav.
        * forum_social.css is NOT linked."""
        # Top header container
        header_match = re.search(r'<header[^>]*id=["\']appHeader["\'][^>]*>(.*?)</header>', self.editor_html, re.DOTALL)
        self.assertIsNotNone(header_match, "appHeader element not found in editor.html")
        header_content = header_match.group(1)

        # 1. logo-title with logo-smart ("Smart") and logo-contractum ("Contractum")
        logo_title_pattern = re.compile(
            r'<span[^>]*class=["\'][^"\']*logo-title[^"\']*["\'][^>]*>\s*'
            r'<span[^>]*class=["\'][^"\']*logo-smart[^"\']*["\'][^>]*>\s*Smart\s*</span>\s*'
            r'<span[^>]*class=["\'][^"\']*logo-contractum[^"\']*["\'][^>]*>\s*Contractum\s*</span>\s*'
            r'</span>',
            re.DOTALL
        )
        self.assertIsNotNone(
            logo_title_pattern.search(header_content),
            "logo-title containing logo-smart ('Smart') and logo-contractum ('Contractum') not found in editor header"
        )

        # 2. all 2 navigation links contain .nav-icon-box with SVG icons
        nav_match = re.search(r'<nav[^>]*id=["\']headerNav["\'][^>]*>(.*?)</nav>', header_content, re.DOTALL)
        self.assertIsNotNone(nav_match, "headerNav not found in editor header")
        nav_content = nav_match.group(1)

        nav_links = re.findall(r'<a\b[^>]*>(.*?)</a>', nav_content, re.DOTALL)
        self.assertEqual(len(nav_links), 2, f"Expected 2 navigation links in header, got {len(nav_links)}")

        required_nav_names = ['Главная', 'Редактор']
        for i, (link_html, expected_name) in enumerate(zip(nav_links, required_nav_names)):
            self.assertIn(expected_name, link_html, f"Navigation link {i+1} must contain text '{expected_name}'")
            self.assertIn('nav-icon-box', link_html, f"Navigation link '{expected_name}' must contain .nav-icon-box")
            self.assertIn('<svg', link_html, f"Navigation link '{expected_name}' must contain SVG icon inside .nav-icon-box")

        # Removed from navigation
        self.assertNotIn('Сообщество', nav_content, "Text 'Сообщество' must not be in editor headerNav")
        self.assertNotIn('navCommunity', nav_content, "#navCommunity must not be in editor headerNav")
        self.assertNotIn('Эксперты', nav_content)
        self.assertNotIn('База знаний', nav_content)

        # 3. #navEditor has class "nav-link active"
        nav_editor_match = re.search(r'<a\b[^>]*id=["\']navEditor["\'][^>]*>', header_content)
        self.assertIsNotNone(nav_editor_match, "Nav link #navEditor not found in header")
        nav_editor_tag = nav_editor_match.group(0)
        class_match = re.search(r'class=["\']([^"\']+)["\']', nav_editor_tag)
        self.assertIsNotNone(class_match, "#navEditor has no class attribute")
        classes = class_match.group(1).split()
        self.assertIn('nav-link', classes, "#navEditor must have class 'nav-link'")
        self.assertIn('active', classes, "#navEditor must have class 'active'")

        # 4. link to css/forum_social.css must NOT be present
        self.assertNotIn('forum_social.css', self.editor_html, "forum_social.css must not be linked in editor.html")

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
        """Verify brand logo links to index.html with title='На главную' on all 3 pages."""
        pages = [('index.html', self.index_html), ('feed.html', self.feed_html), ('editor.html', self.editor_html)]
        for name, html in pages:
            brand_match = re.search(r'<a[^>]*class=["\'][^"\']*brand-logo[^"\']*["\'][^>]*>', html)
            self.assertIsNotNone(brand_match, f"brand-logo not found in {name}")
            brand_tag = brand_match.group(0)
            self.assertIn('href="index.html"', brand_tag, f"brand-logo must have href='index.html' in {name}")
            self.assertIn('title="На главную"', brand_tag, f"brand-logo must have title='На главную' in {name}")

    def test_unified_navigation_routing_and_active_states(self):
        """Verify exactly 2 navigation items in #headerNav (Главная #navIndex, Редактор #navEditor),
        correct routing, active states (index -> #navIndex, editor -> #navEditor, feed -> none active),
        and absence of #navCommunity / 'Сообщество' in #headerNav across all pages."""
        pages = [
            (self.index_html, 'index.html', 'navIndex'),
            (self.feed_html, 'feed.html', None),
            (self.editor_html, 'editor.html', 'navEditor')
        ]

        for html, filename, active_id in pages:
            # Extract headerNav
            nav_match = re.search(r'<nav[^>]*id=["\']headerNav["\'][^>]*>([\s\S]*?)</nav>', html)
            self.assertIsNotNone(nav_match, f"#headerNav not found in {filename}")
            nav_content = nav_match.group(1)

            # Exactly 2 navigation links
            nav_links = re.findall(r'<a\b[^>]*>(.*?)</a>', nav_content, re.DOTALL)
            self.assertEqual(len(nav_links), 2, f"Expected exactly 2 navigation links in #headerNav in {filename}, got {len(nav_links)}")

            # Check navIndex points to index.html with text 'Главная'
            idx_m = re.search(r'<a\b[^>]*id=["\']navIndex["\'][^>]*>([\s\S]*?)</a>', nav_content)
            self.assertIsNotNone(idx_m, f"navIndex not found in #headerNav in {filename}")
            self.assertIn('href="index.html"', idx_m.group(0))
            self.assertIn('Главная', idx_m.group(1))

            # Check navEditor points to editor.html with text 'Редактор'
            ed_m = re.search(r'<a\b[^>]*id=["\']navEditor["\'][^>]*>([\s\S]*?)</a>', nav_content)
            self.assertIsNotNone(ed_m, f"navEditor not found in #headerNav in {filename}")
            self.assertIn('href="editor.html"', ed_m.group(0))
            self.assertIn('Редактор', ed_m.group(1))

            # Explicit check: #navCommunity and text 'Сообщество' are absent from #headerNav
            self.assertNotIn('navCommunity', nav_content, f"Forbidden #navCommunity found in #headerNav in {filename}")
            self.assertNotIn('Сообщество', nav_content, f"Forbidden text 'Сообщество' found in #headerNav in {filename}")

            # Active item checks
            all_nav_ids = ['navIndex', 'navEditor']
            for nav_id in all_nav_ids:
                link_m = re.search(rf'<a\b[^>]*id=["\']{nav_id}["\'][^>]*>', nav_content)
                self.assertIsNotNone(link_m, f"{nav_id} not found in {filename}")
                if nav_id == active_id:
                    self.assertTrue(
                        re.search(r'\b(?:active|is-active)\b', link_m.group(0)),
                        f"{nav_id} must be active in {filename}"
                    )
                else:
                    self.assertFalse(
                        re.search(r'\b(?:active|is-active)\b', link_m.group(0)),
                        f"{nav_id} must NOT be active in {filename}"
                    )

    def test_community_nav_item_absent_on_all_pages(self):
        """Explicit verification that 'Сообщество' (#navCommunity) is absent from #headerNav
        across all pages: index.html, feed.html, and editor.html."""
        pages = [
            ('index.html', self.index_html),
            ('feed.html', self.feed_html),
            ('editor.html', self.editor_html),
        ]
        for filename, html in pages:
            nav_match = re.search(r'<nav[^>]*id=["\']headerNav["\'][^>]*>([\s\S]*?)</nav>', html)
            self.assertIsNotNone(nav_match, f"#headerNav not found in {filename}")
            nav_content = nav_match.group(1)

            self.assertNotIn('navCommunity', nav_content, f"#navCommunity must not exist in #headerNav of {filename}")
            self.assertNotIn('Сообщество', nav_content, f"'Сообщество' must not exist in #headerNav of {filename}")

    def test_stable_scrollbar_and_header_grid_layout_css(self):
        """Verify overflow-y: scroll, scrollbar-gutter: stable, and 3-column grid for .header-container."""
        # html rule
        self.assertIn('overflow-y: scroll;', self.theme_css)
        self.assertIn('scrollbar-gutter: stable;', self.theme_css)

        # 3-column grid in .header-container
        grid_match = re.search(r'\.header-container\s*\{([^}]+)\}', self.theme_css)
        self.assertIsNotNone(grid_match, ".header-container rule not found in theme.css")
        container_css = grid_match.group(1)
        self.assertIn('display: grid;', container_css)
        self.assertIn('grid-template-columns: 260px 1fr 260px;', container_css)
        self.assertIn('align-items: center;', container_css)

        # brand-logo justify-self: start
        brand_css = re.search(r'\.brand-logo\s*\{([^}]+)\}', self.theme_css).group(1)
        self.assertIn('justify-self: start;', brand_css)

        # header-nav justify-self: center
        nav_css = re.search(r'\.header-nav\s*\{([^}]+)\}', self.theme_css).group(1)
        self.assertIn('justify-self: center;', nav_css)

        # header-right-group justify-self: end and gap: 14px
        right_css = re.search(r'\.header-right-group\s*\{([^}]+)\}', self.theme_css).group(1)
        self.assertIn('justify-self: end;', right_css)
        self.assertIn('gap: 14px;', right_css)

    def test_exact_header_markup_identity(self):
        """Verify 100% markup identity across index.html, feed.html, and editor.html headers."""
        def extract_header_lines(html):
            m = re.search(r'<header[^>]*id=["\']appHeader["\'][^>]*>([\s\S]*?)</header>', html)
            lines = [l.strip() for l in m.group(1).splitlines() if l.strip()]
            normalized = '\n'.join(lines)
            return re.sub(r'class="nav-link[^"]*"', 'class="nav-link"', normalized)

        h_index = extract_header_lines(self.index_html)
        h_feed = extract_header_lines(self.feed_html)
        h_editor = extract_header_lines(self.editor_html)

        self.assertEqual(h_index, h_feed, "Header in feed.html differs from index.html")
        self.assertEqual(h_index, h_editor, "Header in editor.html differs from index.html")

    def test_no_conflicting_nav_link_overrides_in_editor_css(self):
        """Verify duplicate .nav-link overrides are removed from editor.css."""
        self.assertNotIn('.nav-link.is-active', self.editor_css)
        self.assertNotIn('.nav-link.active', self.editor_css)

    def test_header_buttons_and_typography_consistency(self):
        """Verify Onest font, font-size: 0.92rem, and font-weight: 600 applied to header items and login button."""
        # Login button structure and text across all 3 pages
        pages = [('index.html', self.index_html), ('feed.html', self.feed_html), ('editor.html', self.editor_html)]
        for name, html in pages:
            self.assertIn('id="headerLoginBtn"', html, f"headerLoginBtn missing in {name}")
            self.assertIn('id="headerUserDot"', html, f"headerUserDot missing in {name}")
            self.assertIn('id="headerUserLabel"', html, f"headerUserLabel missing in {name}")
            self.assertIn('Войти / Регистрация', html, f"Text 'Войти / Регистрация' missing in {name}")
            self.assertIn('btn-user-arrow', html, f"btn-user-arrow missing in {name}")
            self.assertIn('id="btnThemeToggle"', html, f"btnThemeToggle missing in {name}")
            self.assertIn('theme-toggle-track', html, f"theme-toggle-track missing in {name}")

        # CSS font checks
        login_btn_css = re.search(r'\.header-login-action-btn\s*\{([^}]+)\}', self.theme_css).group(1)
        self.assertIn('font-family: var(--font-sans);', login_btn_css)
        self.assertIn('font-size: 0.92rem;', login_btn_css)
        self.assertIn('font-weight: 600;', login_btn_css)

        user_label_css = re.search(r'\.btn-user-label\s*\{([^}]+)\}', self.theme_css).group(1)
        self.assertIn('font-family: var(--font-sans);', user_label_css)
        self.assertIn('font-size: 0.92rem;', user_label_css)
        self.assertIn('font-weight: 600;', user_label_css)

        nav_link_css = re.search(r'\.nav-link\s*\{([^}]+)\}', self.theme_css).group(1)
        self.assertIn('font-family: var(--font-sans);', nav_link_css)
        self.assertIn('font-size: 0.92rem;', nav_link_css)
        self.assertIn('font-weight: 600;', nav_link_css)


if __name__ == '__main__':
    unittest.main()
