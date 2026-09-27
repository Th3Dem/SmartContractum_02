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
  6. Unified header in feed.html and all pages: #appHeader, brand SmartContractum (href="index.html"),
     2 navigation items («Дом» / #navIndex, «Лента» / #navFeed), login button #headerLoginBtn.
  7. Navigation and layout integrity: feed.html links to editor.html via #btnHeroWrite;
     index.html links to feed.html and editor.html.
  8. Color palette in theme.css: dark theme CMC Midnight Navy tokens and high-contrast
     light theme tokens.
  9. Two-column feed grid: #feedCardsContainer, .feed-card, .feed-filter-btn,
     sidebar with widgets.
 10. Editor visual alignment and theme fixes from task-15 & task-16.
"""

import json
import os
import re
import shutil
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request

import server

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

        # Page title and platform identity outside header are intact
        self.assertIn('<title>Лента публикаций — SmartContractum</title>', self.feed_html)
        self.assertIn('feed-main-container', self.feed_html)

    def test_header_navigation_links(self):
        """Verify unified 2 navigation links: Дом (#navIndex), Лента (#navFeed),
        active state on feed.html (#navFeed active is-active), and verify legacy items are absent."""
        header_match = re.search(r'<header[^>]*id=["\']appHeader["\'][^>]*>(.*?)</header>', self.feed_html, re.DOTALL)
        if not header_match:
            header_match = re.search(r'<header[^>]*class="[^"]*app-header[^"]*"[^>]*>(.*?)</header>', self.feed_html, re.DOTALL)
        self.assertIsNotNone(header_match)
        header_content = header_match.group(1)

        nav_match = re.search(r'<nav[^>]*class="[^"]*header-nav[^"]*"[^>]*>(.*?)</nav>', header_content, re.DOTALL)
        self.assertIsNotNone(nav_match, "header-nav not found inside header")
        nav_content = nav_match.group(1)

        # 1. Дом (#navIndex) with href="index.html"
        index_nav_match = re.search(
            r'<a[^>]*id=["\']navIndex["\'][^>]*href=["\']index\.html["\'][^>]*>[\s\S]*?Дом[\s\S]*?</a>|'
            r'<a[^>]*href=["\']index\.html["\'][^>]*id=["\']navIndex["\'][^>]*>[\s\S]*?Дом[\s\S]*?</a>',
            nav_content
        )
        self.assertIsNotNone(index_nav_match, "#navIndex with href='index.html' not found in header-nav")

        # 2. Лента (#navFeed) with href="feed.html"
        feed_nav_match = re.search(
            r'<a[^>]*id=["\']navFeed["\'][^>]*href=["\']feed\.html["\'][^>]*>[\s\S]*?Лента[\s\S]*?</a>|'
            r'<a[^>]*href=["\']feed\.html["\'][^>]*id=["\']navFeed["\'][^>]*>[\s\S]*?Лента[\s\S]*?</a>',
            nav_content
        )
        self.assertIsNotNone(feed_nav_match, "#navFeed with href='feed.html' not found in header-nav")

        # All items must have SVG icons inside .nav-icon-box
        nav_links = re.findall(r'<a\b[^>]*>(.*?)</a>', nav_content, re.DOTALL)
        self.assertEqual(len(nav_links), 2, f"Expected exactly 2 navigation links in header, got {len(nav_links)}")
        for link_html in nav_links:
            self.assertIn('nav-icon-box', link_html)
            self.assertIn('<svg', link_html)

        # Thematic SVG vector icons: house icon for Дом, publication feed icon for Лента
        self.assertIn('m3 9 9-7 9 7', index_nav_match.group(0), "House SVG icon must be in navIndex")
        self.assertIn('M4 22h16', feed_nav_match.group(0), "Feed SVG icon must be in navFeed")

        # On feed.html: #navFeed has class active is-active, #navIndex is not active
        nav_feed_tag = re.search(r'<a\b[^>]*id=["\']navFeed["\'][^>]*>', nav_content)
        self.assertIsNotNone(nav_feed_tag)
        self.assertIn('active', nav_feed_tag.group(0))
        self.assertIn('is-active', nav_feed_tag.group(0))

        nav_idx_tag = re.search(r'<a\b[^>]*id=["\']navIndex["\'][^>]*>', nav_content)
        self.assertIsNotNone(nav_idx_tag)
        self.assertNotIn('active', nav_idx_tag.group(0))

        # Legacy items remain absent
        self.assertNotIn('Эксперты', self.feed_html)
        self.assertNotIn('База знаний', self.feed_html)

        # Feed functional controls and filters are preserved
        self.assertIn('feed-filter-bar', self.feed_html)
        self.assertIn('feed-filter-btn', self.feed_html)
        self.assertIn('id="feedCardsContainer"', self.feed_html)

    def test_theme_toggle_switch_in_header(self):
        """Verify theme toggle button (#btnThemeToggle) is present in feed.html to the left of the login button,
        with proper switch role, track, thumb, and icons."""
        # Theme toggle button and track must be present in header to the left of #headerLoginBtn
        self.assertIn('id="btnThemeToggle"', self.feed_html, "#btnThemeToggle must exist in feed.html")
        self.assertIn('class="btn-theme-toggle"', self.feed_html)
        self.assertIn('role="switch"', self.feed_html)
        self.assertIn('theme-toggle-track', self.feed_html, "theme-toggle-track must exist in feed.html")
        self.assertIn('theme-toggle-thumb', self.feed_html, "theme-toggle-thumb must exist in feed.html")
        self.assertIn('theme-icon-moon', self.feed_html, "theme-icon-moon must exist in feed.html")
        self.assertIn('theme-icon-sun', self.feed_html, "theme-icon-sun must exist in feed.html")

        # Verify #btnThemeToggle is placed before #headerLoginBtn in DOM
        toggle_pos = self.feed_html.find('id="btnThemeToggle"')
        login_pos = self.feed_html.find('id="headerLoginBtn"')
        self.assertTrue(0 < toggle_pos < login_pos, "#btnThemeToggle must be placed to the left of #headerLoginBtn")

        # Early theme initialization script and data-theme attribute must be preserved
        self.assertIn('data-theme="dark"', self.feed_html)
        self.assertIn("localStorage.getItem('ag_theme')", self.feed_html)

    def test_user_login_button_in_header(self):
        """Verify user login button (#headerLoginBtn) is present in feed.html,
        while main layout container is preserved."""
        # Header user/login controls must be present
        self.assertIn('id="headerLoginBtn"', self.feed_html, "#headerLoginBtn must be present in feed.html")
        self.assertIn('header-login-action-btn', self.feed_html, ".header-login-action-btn must be present in feed.html")
        self.assertIn('header-user-bar', self.feed_html, ".header-user-bar must be present in feed.html")
        self.assertIn('btn-user-svg', self.feed_html, ".btn-user-svg must be present in feed.html")
        self.assertIn('Вход', self.feed_html)

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

        required_categories = ['Все', 'Разработка', 'Безопасность']
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

        # Widget 1: Поделитесь опытом / Создать публикацию with link to editor.html
        self.assertTrue('Поделитесь опытом' in sidebar_content or 'Создать публикацию' in sidebar_content)
        self.assertTrue(
            re.search(r'<a[^>]*href=["\']editor\.html["\'][^>]*>[\s\S]*?(?:Написать статью|Открыть редактор)[\s\S]*?</a>', sidebar_content),
            "Link to editor.html not found in sidebar widget"
        )

        # Widget 2: Темы / Популярные темы
        self.assertTrue('Темы' in sidebar_content or 'Популярные темы' in sidebar_content)
        self.assertTrue('widget-tags-cloud' in sidebar_content or 'widget-topics-list' in sidebar_content)

        # Widget 3: О платформе SmartContractum
        self.assertIn('О платформе', sidebar_content)
        self.assertIn('index.html', sidebar_content)


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
        - #appHeader and #headerNav are present across feed.html, editor.html, index.html.
        - feed.html links to editor.html via #btnHeroWrite.
        - index.html links to feed.html and editor.html via hero CTA buttons.
        - editor.html maintains document action bar and workspace under top header."""
        # 1. Top header and header nav are present on all pages
        for page_name, html in [('feed.html', self.feed_html), ('editor.html', self.editor_html), ('index.html', self.index_html)]:
            self.assertIn('id="appHeader"', html, f"#appHeader must exist in {page_name}")
            self.assertIn('class="app-header"', html, f"class 'app-header' must exist in {page_name}")
            self.assertIn('<header', html, f"<header> tag must exist in {page_name}")
            self.assertIn('id="headerNav"', html, f"#headerNav must exist in {page_name}")

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
        """Verify editor.html includes the top header (#appHeader, brand-logo,
        #headerNav, #headerLoginBtn) and #editorDocumentBar is docked below it."""
        # Top header and header elements must be present
        self.assertIn('id="appHeader"', self.editor_html, "#appHeader must exist in editor.html")
        self.assertIn('class="app-header"', self.editor_html, "class 'app-header' must exist in editor.html")
        self.assertIn('<header', self.editor_html, "<header> element must exist in editor.html")
        self.assertIn('id="headerNav"', self.editor_html, "#headerNav must exist in editor.html")
        self.assertIn('id="headerLoginBtn"', self.editor_html, "#headerLoginBtn must exist in editor.html")

        # #editorDocumentBar is present and is docked inside .app-container under #appHeader
        app_container_pos = self.editor_html.find('class="app-container"')
        self.assertNotEqual(app_container_pos, -1, "app-container not found in editor.html")
        header_pos = self.editor_html.find('id="appHeader"')
        self.assertNotEqual(header_pos, -1, "#appHeader not found in editor.html")
        doc_bar_pos = self.editor_html.find('id="editorDocumentBar"')
        self.assertNotEqual(doc_bar_pos, -1, "#editorDocumentBar not found in editor.html")
        self.assertTrue(header_pos > app_container_pos, "#appHeader must be inside .app-container")
        self.assertTrue(doc_bar_pos > header_pos, "#editorDocumentBar must be placed after #appHeader")

        # editor.css sets .editor-document-bar top: var(--header-height, 60px)
        doc_bar_css_match = re.search(r'\.editor-document-bar\s*\{([^}]+)\}', self.editor_css)
        self.assertIsNotNone(doc_bar_css_match, ".editor-document-bar rule not found in editor.css")
        self.assertTrue(
            re.search(r'top:\s*var\(--header-height,\s*60px\)', doc_bar_css_match.group(1)),
            ".editor-document-bar must have top: var(--header-height, 60px) in editor.css"
        )

    def test_editor_has_document_action_bar(self):
        """Verify editor.html has #editorDocumentBar containing #btn-drafts-modal, #drafts-badge,
        #save-status, and #btn-next-to-settings aligned with editor card."""
        bar_start = self.editor_html.find('id="editorDocumentBar"')
        self.assertNotEqual(bar_start, -1, "#editorDocumentBar not found in editor.html")
        bar_end = self.editor_html.find('class="app-main-layout"', bar_start)
        self.assertNotEqual(bar_end, -1, "app-main-layout boundary not found after editorDocumentBar")
        bar_content = self.editor_html[bar_start:bar_end]

        # Antigravity Writer removed per requirement 4
        self.assertNotIn('Antigravity Writer', bar_content, "Antigravity Writer must be removed from #editorDocumentBar")
        self.assertNotIn('brand-icon', bar_content)

        # Container alignment structure matching editor workspace container
        self.assertIn('class="editor-docbar-container"', bar_content)
        self.assertIn('class="editor-docbar-main"', bar_content)
        self.assertIn('class="editor-docbar-sidebar-spacer"', bar_content)

        # #btn-drafts-modal and save status in header-left
        self.assertIn('id="btn-drafts-modal"', bar_content, "#btn-drafts-modal not found in #editorDocumentBar")
        self.assertIn('id="drafts-badge"', bar_content, "#drafts-badge not found in #editorDocumentBar")
        self.assertIn('id="save-status"', bar_content, "#save-status not found in #editorDocumentBar")

        # #btn-next-to-settings in header-right (aligned to right edge of editor card)
        self.assertIn('id="btn-next-to-settings"', bar_content, "#btn-next-to-settings not found in #editorDocumentBar")
        self.assertIn('class="header-right"', bar_content)

        # Relative order: drafts button -> save status -> next-to-settings button
        drafts_pos = bar_content.find('id="btn-drafts-modal"')
        status_pos = bar_content.find('id="save-status"')
        next_pos = bar_content.find('id="btn-next-to-settings"')
        self.assertTrue(0 < drafts_pos < status_pos < next_pos, "Controls must be ordered: drafts -> status -> next button")

        # #btn-more-actions removed per requirement 10
        self.assertNotIn('id="btn-more-actions"', bar_content, "#btn-more-actions must be removed from #editorDocumentBar")

        # CSS alignment rules
        self.assertIn('.editor-docbar-container', self.editor_css)
        self.assertIn('.editor-docbar-main', self.editor_css)
        self.assertIn('.editor-docbar-sidebar-spacer', self.editor_css)

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
        """Verify editor.html has top header present (#appHeader, logo-title, #headerNav),
        forum_social.css is NOT linked, and editor workspace is intact."""
        # Top header container must exist in editor.html
        self.assertIn('id="appHeader"', self.editor_html, "#appHeader must exist in editor.html")
        self.assertIn('class="app-header"', self.editor_html, "class 'app-header' must exist in editor.html")
        self.assertIn('<header', self.editor_html, "<header> tag must exist in editor.html")
        self.assertIn('id="headerNav"', self.editor_html, "#headerNav must exist in editor.html")
        self.assertIn('class="logo-title"', self.editor_html, "logo-title must exist in editor.html")

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
    """Test Suite for task-19 & task-23: Unified header navigation, anti-shift 3-col grid, and identical typography."""

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
        """Verify header brand logo (.brand-logo, #appHeader) is present across all 3 pages
        (index.html, feed.html, editor.html), while valid page structures remain."""
        pages = [('index.html', self.index_html), ('feed.html', self.feed_html), ('editor.html', self.editor_html)]
        for name, html in pages:
            self.assertIn('class="brand-logo"', html, f"brand-logo missing in {name}")
            self.assertIn('id="appHeader"', html, f"appHeader missing in {name}")
            self.assertIn('class="app-header"', html, f"app-header missing in {name}")
            self.assertIn('<header', html, f"<header> tag missing in {name}")
            self.assertIn('<!DOCTYPE html>', html, f"<!DOCTYPE html> missing in {name}")
            self.assertIn('<title>', html, f"<title> missing in {name}")

    def test_unified_navigation_routing_and_active_states(self):
        """Verify #headerNav and all header navigation links (#navIndex, #navFeed)
        are present across all pages (index.html, feed.html, editor.html) with correct active states."""
        pages = [
            (self.index_html, 'index.html', True, False),
            (self.feed_html, 'feed.html', False, True),
            (self.editor_html, 'editor.html', False, False)
        ]

        for html, filename, index_active, feed_active in pages:
            self.assertIn('id="headerNav"', html, f"#headerNav must be in {filename}")
            self.assertIn('class="header-nav"', html, f"class 'header-nav' must be in {filename}")
            self.assertIn('id="navIndex"', html, f"#navIndex must be in {filename}")
            self.assertIn('id="navFeed"', html, f"#navFeed must be in {filename}")

            idx_match = re.search(r'<a\b[^>]*id=["\']navIndex["\'][^>]*>', html)
            self.assertIsNotNone(idx_match, f"#navIndex link not found in {filename}")
            if index_active:
                self.assertIn('active', idx_match.group(0), f"#navIndex must be active in {filename}")
                self.assertIn('is-active', idx_match.group(0), f"#navIndex must have is-active in {filename}")
            else:
                self.assertNotIn('active', idx_match.group(0), f"#navIndex must not be active in {filename}")

            feed_match = re.search(r'<a\b[^>]*id=["\']navFeed["\'][^>]*>', html)
            self.assertIsNotNone(feed_match, f"#navFeed link not found in {filename}")
            if feed_active:
                self.assertIn('active', feed_match.group(0), f"#navFeed must be active in {filename}")
                self.assertIn('is-active', feed_match.group(0), f"#navFeed must have is-active in {filename}")
            else:
                self.assertNotIn('active', feed_match.group(0), f"#navFeed must not be active in {filename}")

            self.assertIn('class="app-container"', html, f"app-container must exist in {filename}")

    def test_community_nav_item_present_on_all_pages(self):
        """Verify header navigation #headerNav and #navFeed are present across
        index.html, feed.html, and editor.html, while community feed remains accessible from index.html."""
        pages = [
            ('index.html', self.index_html),
            ('feed.html', self.feed_html),
            ('editor.html', self.editor_html),
        ]
        for filename, html in pages:
            self.assertIn('id="headerNav"', html, f"#headerNav must exist in {filename}")
            self.assertIn('id="navFeed"', html, f"#navFeed must exist in {filename}")

        # Community feed is accessible from index.html hero actions
        self.assertTrue(
            re.search(r'<a[^>]*href=["\']feed\.html["\']', self.index_html),
            "index.html must provide link to feed.html"
        )

    def test_stable_scrollbar_and_header_grid_layout_css(self):
        """Verify overflow-y: scroll, scrollbar-gutter: stable, --header-height: 60px,
        and header grid layout CSS rules in theme.css."""
        # html rule
        self.assertIn('overflow-y: scroll;', self.theme_css)
        self.assertIn('scrollbar-gutter: stable;', self.theme_css)

        # Header height set to 60px
        self.assertIn('--header-height: 60px;', self.theme_css, "--header-height must be 60px in theme.css")

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
            self.assertIsNotNone(m, "<header id='appHeader'> must exist")
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
        """Verify header buttons (#headerLoginBtn) and Onest typography consistency across all 3 pages."""
        # Header button IDs must be present across all 3 pages
        pages = [('index.html', self.index_html), ('feed.html', self.feed_html), ('editor.html', self.editor_html)]
        for name, html in pages:
            self.assertIn('id="headerLoginBtn"', html, f"headerLoginBtn must exist in {name}")
            self.assertIn('id="headerUserLabel"', html, f"headerUserLabel must exist in {name}")
            self.assertIn('Вход', html, f"Text 'Вход' must exist in {name}")
            self.assertIn('btn-user-arrow', html, f"btn-user-arrow must exist in {name}")
            self.assertIn('id="btnThemeToggle"', html, f"btnThemeToggle must exist in {name}")
            self.assertIn('theme-toggle-track', html, f"theme-toggle-track must exist in {name}")
            self.assertIn('theme-toggle-thumb', html, f"theme-toggle-thumb must exist in {name}")

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

        # Typography standards in theme.css strictly preserved
        self.assertIn('--font-sans:', self.theme_css)
        self.assertIn("'Onest'", self.theme_css)
        self.assertIn('font-family: var(--font-sans);', self.theme_css)

    def test_consistent_root_font_size_and_no_html_override_in_editor_css(self):
        """Verify root html font-size is strictly 16px in theme.css and editor.css does not override html font-size,
        preventing header font-size scaling discrepancies between index.html, feed.html, and editor.html."""
        # theme.css sets html font-size: 16px
        html_theme_match = re.search(r'html\s*\{([^}]+)\}', self.theme_css)
        self.assertIsNotNone(html_theme_match, "html block not found in theme.css")
        self.assertIn('font-size: 16px;', html_theme_match.group(1))

        # editor.css must NOT set font-size on html (which would break rem scale across pages)
        html_editor_match = re.search(r'(?<![a-zA-Z0-9_-])html\s*\{([^}]+)\}', self.editor_css)
        if html_editor_match:
            self.assertNotIn('font-size:', html_editor_match.group(1), "editor.css must not set font-size on html")



class TestArticleReadingPage(unittest.TestCase):
    """Test verification for article.html, article.css, and article.js (task-24)."""

    @classmethod
    def setUpClass(cls):
        cls.article_html_path = os.path.join(FRONTEND_DIR, 'article.html')
        cls.article_css_path = os.path.join(FRONTEND_DIR, 'css', 'article.css')
        cls.article_js_path = os.path.join(FRONTEND_DIR, 'js', 'article.js')
        cls.index_html_path = os.path.join(FRONTEND_DIR, 'index.html')

        with open(cls.article_html_path, 'r', encoding='utf-8') as f:
            cls.article_html = f.read()
        with open(cls.article_css_path, 'r', encoding='utf-8') as f:
            cls.article_css = f.read()
        with open(cls.article_js_path, 'r', encoding='utf-8') as f:
            cls.article_js = f.read()
        with open(cls.index_html_path, 'r', encoding='utf-8') as f:
            cls.index_html = f.read()

        cls.cdn_indicators = [
            'fonts.googleapis.com',
            'fonts.gstatic.com',
            'cdnjs.cloudflare.com',
            'cdn.jsdelivr.net',
            'unpkg.com',
            'ajax.googleapis.com',
            'stackpath.bootstrapcdn.com'
        ]

    def test_article_files_exist_and_non_empty(self):
        """Verify frontend/public/article.html, css/article.css, and js/article.js exist and have sufficient size."""
        for path, min_size in [
            (self.article_html_path, 3000),
            (self.article_css_path, 2000),
            (self.article_js_path, 2000),
        ]:
            self.assertTrue(os.path.isfile(path), f"Required file {path} must exist")
            file_size = os.path.getsize(path)
            self.assertGreater(file_size, min_size, f"File {path} is unexpectedly small ({file_size} bytes)")

    def test_article_offline_first_zero_cdn_references(self):
        """Ensure article.html, article.css, and article.js have zero CDN references."""
        for content, filename in [
            (self.article_html, 'article.html'),
            (self.article_css, 'css/article.css'),
            (self.article_js, 'js/article.js'),
        ]:
            for cdn in self.cdn_indicators:
                self.assertNotIn(cdn, content, f"Forbidden external CDN reference '{cdn}' found in {filename}")

    def test_article_offline_first_zero_external_links(self):
        """Ensure article.html and article.css have zero external http/https resource URLs."""
        url_pattern = re.compile(r'https?://(?!localhost|127\.0\.0\.1|www\.w3\.org)[^\s\'"<>]+')
        for content, filename in [
            (self.article_html, 'article.html'),
            (self.article_css, 'css/article.css'),
            (self.article_js, 'js/article.js'),
        ]:
            matches = [m for m in url_pattern.findall(content) if 'w3.org' not in m]
            self.assertEqual(len(matches), 0, f"External URLs found in {filename}: {matches}")

    def test_article_scripts_and_stylesheets_are_local(self):
        """Verify that all stylesheet and script references in article.html point to local files."""
        stylesheet_hrefs = re.findall(r'<link[^>]*rel=["\']stylesheet["\'][^>]*href=["\']([^"\']+)["\']', self.article_html)
        self.assertGreater(len(stylesheet_hrefs), 0, "No stylesheet links found in article.html")
        for href in stylesheet_hrefs:
            self.assertFalse(href.startswith(('http://', 'https://', '//')),
                             f"Stylesheet href '{href}' must not be an external absolute URL")

        script_srcs = re.findall(r'<script[^>]*src=["\']([^"\']+)["\']', self.article_html)
        self.assertGreater(len(script_srcs), 0, "No script tags with src found in article.html")
        for src in script_srcs:
            self.assertFalse(src.startswith(('http://', 'https://', '//')),
                             f"Script src '{src}' must not be an external absolute URL")

    def test_article_strict_onest_font(self):
        """Verify Onest font family in article.html and article.css without disallowed fonts."""
        self.assertIn("'Onest'", self.article_html, "article.html must declare 'Onest' font family")
        disallowed_pattern = re.compile(
            r'font-family:\s*[^;]*\b(?:Inter|Manrope|JetBrains Mono)\b',
            re.IGNORECASE
        )
        for content, filename in [
            (self.article_html, 'article.html'),
            (self.article_css, 'css/article.css'),
        ]:
            matches = disallowed_pattern.findall(content)
            self.assertEqual(len(matches), 0, f"Disallowed font family found in {filename}: {matches}")

    def test_article_zero_emojis(self):
        """Verify zero emoji characters in article.html, article.css, and article.js."""
        emoji_pattern = re.compile(
            r'[\U0001F600-\U0001F64F]'
            r'|[\U0001F300-\U0001F5FF]'
            r'|[\U0001F680-\U0001F6FF]'
            r'|[\U0001F1E0-\U0001F1FF]'
            r'|[\U00002702-\U000027B0]'
            r'|[\U000024C2-\U0001F251]'
            r'|[\U0001F900-\U0001F9FF]'
            r'|[\U0001FA70-\U0001FAFF]'
        )
        for content, filename in [
            (self.article_html, 'article.html'),
            (self.article_css, 'css/article.css'),
            (self.article_js, 'js/article.js'),
        ]:
            emojis = emoji_pattern.findall(content)
            self.assertEqual(len(emojis), 0, f"Emojis found in {filename}: {emojis}")

    def test_article_unified_header_markup(self):
        """Verify unified #appHeader in article.html is identical in structure to index.html."""
        def extract_header_lines(html):
            m = re.search(r'<header[^>]*id=["\']appHeader["\'][^>]*>([\s\S]*?)</header>', html)
            self.assertIsNotNone(m, "<header id='appHeader'> must exist")
            lines = [l.strip() for l in m.group(1).splitlines() if l.strip()]
            normalized = '\n'.join(lines)
            return re.sub(r'class="nav-link[^"]*"', 'class="nav-link"', normalized)

        h_index = extract_header_lines(self.index_html)
        h_article = extract_header_lines(self.article_html)
        self.assertEqual(h_index, h_article, "Header in article.html differs from index.html")

    def test_article_essential_ui_elements(self):
        """Verify all essential UI elements for article reader are present in article.html."""
        required_elements = [
            'id="btnBackToFeed"',
            'id="btnArticleBookmark"',
            'id="btnCopyLink"',
            'id="articleLoadingState"',
            'id="articleErrorState"',
            'id="articleContentWrap"',
            'id="articleBadges"',
            'id="articleTitle"',
            'id="articleLead"',
            'id="articleAuthorName"',
            'id="articleAuthorAvatar"',
            'id="articlePublishDate"',
            'id="articleReadingTime"',
            'id="articleTocBox"',
            'id="articleTocList"',
            'id="articleBodyContent"',
            'id="articleTagsWrap"',
            'id="articleTagsList"',
            'id="btnBackToFeedBottom"',
            'id="btnArticleBookmarkBottom"',
        ]
        for elem in required_elements:
            self.assertIn(elem, self.article_html, f"Essential element '{elem}' must exist in article.html")

    def test_article_reading_layout_container_width(self):
        """Verify comfortable reading container width (max-width <= 800px) in article.css."""
        container_match = re.search(r'\.article-page-container\s*\{([^}]+)\}', self.article_css)
        self.assertIsNotNone(container_match, ".article-page-container rule not found in article.css")
        css_block = container_match.group(1)
        self.assertIn('max-width:', css_block)
        max_w = re.search(r'max-width:\s*(\d+)px', css_block)
        self.assertIsNotNone(max_w)
        width_val = int(max_w.group(1))
        self.assertTrue(680 <= width_val <= 800, f"Reading container width {width_val}px is outside 680-800px range")


class TestArticlesApiEndpoints(unittest.TestCase):
    """Integration test suite for GET /api/articles and GET /api/articles/<id> endpoints."""

    @classmethod
    def setUpClass(cls):
        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, 'integration_articles_test.db')

        cls.server = server.create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR)
        cls.port = cls.server.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"

        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.05)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=2)
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def _get_json(self, path: str):
        if '?' in path:
            base_p, query_str = path.split('?', 1)
            parts = []
            for item in query_str.split('&'):
                if '=' in item:
                    k, v = item.split('=', 1)
                    parts.append(f"{urllib.parse.quote(k)}={urllib.parse.quote(v)}")
                else:
                    parts.append(urllib.parse.quote(item))
            path = f"{base_p}?{'&'.join(parts)}"
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req) as resp:
                resp_body = resp.read().decode("utf-8")
                return resp.status, json.loads(resp_body)
        except urllib.error.HTTPError as e:
            resp_body = e.read().decode("utf-8")
            e.close()
            return e.code, json.loads(resp_body)

    def test_get_articles_list_returns_approved_articles(self):
        """GET /api/articles returns 200, success=True, and list of approved articles."""
        status_code, data = self._get_json("/api/articles")
        self.assertEqual(status_code, 200)
        self.assertTrue(data.get("success"))
        articles = data.get("articles", [])
        self.assertGreaterEqual(len(articles), 4)
        for art in articles:
            self.assertIn("id", art)
            self.assertIn("title", art)
            self.assertIn("description", art)
            self.assertIn("topics", art)
            self.assertIn("readingTime", art)
            self.assertIn("author", art)

    def test_get_articles_filter_by_topic(self):
        """GET /api/articles?topic=... filters articles correctly."""
        status_code, data = self._get_json("/api/articles?topic=smart-contracts-development")
        self.assertEqual(status_code, 200)
        self.assertTrue(data.get("success"))
        articles = data.get("articles", [])
        self.assertGreaterEqual(len(articles), 1)
        for art in articles:
            self.assertIn("smart-contracts-development", art.get("topics", []))

    def test_get_articles_filter_by_audience(self):
        """GET /api/articles?audience=... filters articles by audience."""
        status_code, data = self._get_json("/api/articles?audience=architects-integrators")
        self.assertEqual(status_code, 200)
        self.assertTrue(data.get("success"))
        articles = data.get("articles", [])
        self.assertGreaterEqual(len(articles), 1)
        for art in articles:
            self.assertEqual(art.get("targetAudience"), "architects-integrators")

    def test_get_articles_filter_by_format(self):
        """GET /api/articles?format=... filters articles by format."""
        status_code, data = self._get_json("/api/articles?format=tutorial")
        self.assertEqual(status_code, 200)
        self.assertTrue(data.get("success"))
        articles = data.get("articles", [])
        self.assertGreaterEqual(len(articles), 1)
        for art in articles:
            self.assertEqual(art.get("format"), "tutorial")

    def test_get_articles_filter_by_complexity(self):
        """GET /api/articles?complexity=... filters articles by complexity."""
        status_code, data = self._get_json("/api/articles?complexity=hard")
        self.assertEqual(status_code, 200)
        self.assertTrue(data.get("success"))
        articles = data.get("articles", [])
        self.assertGreaterEqual(len(articles), 1)
        for art in articles:
            self.assertEqual(art.get("complexity"), "hard")

    def test_get_articles_search(self):
        """GET /api/articles?search=... performs search query across articles."""
        status_code, data = self._get_json("/api/articles?search=рубля")
        self.assertEqual(status_code, 200)
        self.assertTrue(data.get("success"))
        articles = data.get("articles", [])
        self.assertGreaterEqual(len(articles), 1)
        found_in_results = any("рубл" in a["title"].lower() or "рубл" in a["description"].lower() for a in articles)
        self.assertTrue(found_in_results)

    def test_get_articles_by_ids(self):
        """GET /api/articles?ids=art-01,art-02 returns matching articles for bookmarks."""
        status_code, data = self._get_json("/api/articles?ids=art-01,art-02")
        self.assertEqual(status_code, 200)
        self.assertTrue(data.get("success"))
        articles = data.get("articles", [])
        self.assertEqual(len(articles), 2)
        returned_ids = {a["id"] for a in articles}
        self.assertEqual(returned_ids, {"art-01", "art-02"})

    def test_get_articles_pagination(self):
        """GET /api/articles?limit=2&offset=1 limits and offsets results correctly."""
        status_code, data = self._get_json("/api/articles?limit=2&offset=1")
        self.assertEqual(status_code, 200)
        self.assertTrue(data.get("success"))
        articles = data.get("articles", [])
        self.assertLessEqual(len(articles), 2)
        self.assertEqual(data.get("limit"), 2)
        self.assertEqual(data.get("offset"), 1)
        self.assertGreaterEqual(data.get("total"), 4)

    def test_get_article_by_id_success(self):
        """GET /api/articles/art-01 returns complete publication data."""
        status_code, data = self._get_json("/api/articles/art-01")
        self.assertEqual(status_code, 200)
        self.assertTrue(data.get("success"))
        art = data.get("article", {})
        self.assertEqual(art.get("id"), "art-01")
        self.assertIn("title", art)
        self.assertIn("html", art)
        self.assertIn("author", art)
        self.assertIn("readingTime", art)
        self.assertIn("topics", art)
        self.assertIn("keywords", art)

    def test_get_article_by_query_param(self):
        """GET /api/articles?id=art-01 returns article data as fallback."""
        status_code, data = self._get_json("/api/articles?id=art-01")
        self.assertEqual(status_code, 200)
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("article", {}).get("id"), "art-01")

    def test_get_article_not_found(self):
        """GET /api/articles/non-existent-id returns 404."""
        status_code, data = self._get_json("/api/articles/non-existent-id")
        self.assertEqual(status_code, 404)
        self.assertFalse(data.get("success"))

    def test_unapproved_and_draft_articles_are_hidden(self):
        """Unapproved submissions (pending or rejected) must never appear in /api/articles or /api/articles/<id>."""
        conn = server.get_db_connection(self.db_path)
        with conn:
            conn.execute("""
                INSERT INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, idempotency_key, snapshot_hash, created_at, updated_at
                ) VALUES (
                    'sub_pending_hidden', 'draft_pending_hidden', 'Неопубликованная статья',
                    'author_secret', 'pending_moderation', '{"topics":["security"],"description":"Секретный драфт статьи"}',
                    '<p>Секретный драфт</p>', 'idemp_hidden_01', 'hash_01',
                    '2026-09-27T00:00:00Z', '2026-09-27T00:00:00Z'
                )
            """)
        conn.close()

        # Check list endpoint does not contain it
        status_code, list_data = self._get_json("/api/articles")
        self.assertEqual(status_code, 200)
        found_in_list = any(a.get("id") == "sub_pending_hidden" or a.get("draftId") == "draft_pending_hidden"
                            for a in list_data.get("articles", []))
        self.assertFalse(found_in_list, "Pending moderation submission must not appear in public /api/articles")

        # Check direct GET /api/articles/<id> returns 404
        status_code, detail_data = self._get_json("/api/articles/sub_pending_hidden")
        self.assertEqual(status_code, 404, "Direct retrieval of unapproved submission must return 404")
        self.assertFalse(detail_data.get("success"))


class TestFeedRefinementsAndPolish(unittest.TestCase):
    """Test Suite for task-25: Feed refinements, layout compactness, calm badges, and sidebar polish."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(FRONTEND_DIR, 'feed.html'), 'r', encoding='utf-8') as f:
            cls.feed_html = f.read()
        with open(os.path.join(FRONTEND_DIR, 'css', 'feed.css'), 'r', encoding='utf-8') as f:
            cls.feed_css = f.read()
        with open(os.path.join(FRONTEND_DIR, 'js', 'feed.js'), 'r', encoding='utf-8') as f:
            cls.feed_js = f.read()
        with open(os.path.join(FRONTEND_DIR, 'js', 'article.js'), 'r', encoding='utf-8') as f:
            cls.article_js = f.read()
        with open(os.path.join(PROJECT_ROOT, 'server.py'), 'r', encoding='utf-8') as f:
            cls.server_py = f.read()

    def test_saved_tab_in_subnav(self):
        """Verify #feedSavedTab is located in #feedSubnavBar for task-26."""
        subnav_match = re.search(r'<nav class="feed-subnav-bar" id="feedSubnavBar"[^>]*>(.*?)</nav>', self.feed_html, re.DOTALL)
        self.assertIsNotNone(subnav_match, "#feedSubnavBar container not found")
        subnav_content = subnav_match.group(1)
        self.assertIn('id="feedSavedTab"', subnav_content, "#feedSavedTab must be located within #feedSubnavBar")
        self.assertIn('id="tabFeedAll"', subnav_content, "#tabFeedAll must be located within #feedSubnavBar")
        self.assertIn('id="tabFeedMy"', subnav_content, "#tabFeedMy must be located within #feedSubnavBar")

    def test_feed_period_select_wrap_initial_hidden(self):
        """Verify #feedPeriodSelectWrap exists and is hidden by default when sort is newest."""
        self.assertIn('id="feedPeriodSelectWrap"', self.feed_html)
        self.assertIn('updatePeriodVisibility', self.feed_js)

    def test_calm_metadata_badges_no_red_hard_complexity(self):
        """Verify complexity 'hard' badge does not use red/error colors and uses calm neutral styling."""
        hard_match = re.search(r'\.meta-badge\.complexity-hard\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(hard_match, ".meta-badge.complexity-hard rule not found in feed.css")
        rules = hard_match.group(1)
        disallowed_reds = ['#ef4444', '#f87171', '#dc2626', '#b91c1c', 'rgb(239, 68, 68)', 'rgba(239, 68, 68', 'red']
        for red in disallowed_reds:
            self.assertNotIn(red, rules.lower(), f"Red color '{red}' must not be used for complexity-hard badge")

    def test_sidebar_topics_widget_subtitle_and_structure(self):
        """Verify sidebar topics widget has subtitle 'Количество опубликованных статей' and toggle button logic."""
        self.assertIn('Количество опубликованных статей', self.feed_html)
        self.assertIn('btnToggleAllSidebarTopics', self.feed_js)
        self.assertIn('widget-topic-title', self.feed_css)
        self.assertIn('widget-topic-count', self.feed_css)

    def test_sidebar_experience_widget_secondary_button(self):
        """Verify 'Поделитесь опытом' widget uses .btn-secondary and concise copy."""
        self.assertIn('btn-secondary btn-widget-write', self.feed_html)
        self.assertNotIn('btn-primary btn-widget-write', self.feed_html)

    def test_no_fictitious_titles_in_codebase(self):
        """Verify 'Главный архитектор ПКСК' is removed and demo articles are labelled (демо)."""
        self.assertNotIn('Главный архитектор ПКСК', self.server_py)
        self.assertNotIn('Главный архитектор ПКСК', self.feed_js)
        self.assertNotIn('Главный архитектор ПКСК', self.article_js)
        self.assertIn('(демо)', self.server_py)

    def test_bookmark_tooltips(self):
        """Verify bookmark buttons have tooltips 'Сохранить статью' and 'Убрать из сохраненного'."""
        self.assertIn('Сохранить статью', self.feed_js)
        self.assertIn('Убрать из сохраненного', self.feed_js)

    def test_card_hierarchy_badges_below_title(self):
        """Verify in feed.js that .card-meta contains author-info, and .card-meta-badges is below .card-title."""
        card_gen_match = re.search(r'function createCardElement\(item\)\s*\{([\s\S]*?)\n  \}', self.feed_js)
        self.assertIsNotNone(card_gen_match, "createCardElement function not found")
        fn_code = card_gen_match.group(1)
        self.assertIn('<div class="card-meta">', fn_code)
        self.assertIn('<h2 class="card-title">', fn_code)
        self.assertIn('<div class="card-meta-badges">', fn_code)

        title_pos = fn_code.find('<h2 class="card-title">')
        badges_pos = fn_code.find('<div class="card-meta-badges">')
        self.assertTrue(0 < title_pos < badges_pos, ".card-meta-badges must be rendered under .card-title")


class TestTask26SecondLevelMenuSubscriptionsAndMyFeed(unittest.TestCase):
    """Comprehensive test suite for task-26: Second level menu, sticky scroll, subscriptions, and My Feed."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(FRONTEND_DIR, 'feed.html'), 'r', encoding='utf-8') as f:
            cls.feed_html = f.read()
        with open(os.path.join(FRONTEND_DIR, 'css', 'feed.css'), 'r', encoding='utf-8') as f:
            cls.feed_css = f.read()
        with open(os.path.join(FRONTEND_DIR, 'js', 'feed.js'), 'r', encoding='utf-8') as f:
            cls.feed_js = f.read()
        with open(os.path.join(FRONTEND_DIR, 'article.html'), 'r', encoding='utf-8') as f:
            cls.article_html = f.read()
        with open(os.path.join(FRONTEND_DIR, 'js', 'article.js'), 'r', encoding='utf-8') as f:
            cls.article_js = f.read()
        with open(os.path.join(PROJECT_ROOT, 'server.py'), 'r', encoding='utf-8') as f:
            cls.server_py = f.read()

        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, 'task26_test.db')

        cls.server = server.create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR)
        cls.port = cls.server.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"

        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.05)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_subnav_bar_markup_under_header(self):
        """Verify #feedSubnavBar is placed directly under #appHeader with all required controls."""
        header_end = self.feed_html.find('</header>')
        subnav_start = self.feed_html.find('<nav class="feed-subnav-bar" id="feedSubnavBar"')
        self.assertTrue(0 < header_end < subnav_start, "#feedSubnavBar must appear directly under #appHeader")

        # Controls in subnav
        self.assertIn('id="tabFeedAll"', self.feed_html)
        self.assertIn('id="tabFeedMy"', self.feed_html)
        self.assertIn('id="feedSearchInput"', self.feed_html)
        self.assertIn('id="btnFeedFiltersToggle"', self.feed_html)
        self.assertIn('id="feedSavedTab"', self.feed_html)
        self.assertIn('id="btnHeroWrite"', self.feed_html)

        # Personal tabs have .personal-tab class
        self.assertIn('feed-subnav-tab personal-tab', self.feed_html)
        self.assertIn('feed-saved-btn personal-tab', self.feed_html)

    def test_subnav_bar_css_sticky_and_opaque(self):
        """Verify .feed-subnav-bar in feed.css has position: sticky, top: 56px, and opaque backgrounds."""
        subnav_rule = re.search(r'\.feed-subnav-bar\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(subnav_rule, ".feed-subnav-bar rule not found in feed.css")
        rules = subnav_rule.group(1)
        self.assertIn('position: sticky', rules)
        self.assertIn('top: 56px', rules)
        self.assertIn('z-index: 99', rules)
        self.assertIn('background-color: #0b1329', rules)

        light_subnav = re.search(r'\[data-theme="light"\]\s*\.feed-subnav-bar\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(light_subnav, "[data-theme='light'] .feed-subnav-bar rule not found in feed.css")
        self.assertIn('background-color: #ffffff', light_subnav.group(1))

    def test_direct_toolbar_and_no_duplicate_controls(self):
        """Verify direct toolbar above articles and removal of duplicate controls block."""
        self.assertIn('id="feedDirectToolbar"', self.feed_html)
        self.assertIn('id="feedResultsCount"', self.feed_html)
        self.assertIn('id="feedSortSelect"', self.feed_html)
        self.assertIn('id="btnManageSubscriptions"', self.feed_html)

        # Old hero card and controls section are not in feed.html
        self.assertNotIn('feed-hero-card', self.feed_html)
        self.assertNotIn('feed-controls-section', self.feed_html)

    def test_modals_markup_in_feed_html(self):
        """Verify Unified Filters Modal, Subscriptions Modal, and Auth Modal in feed.html."""
        # 1. Filters Modal
        self.assertIn('id="feedFiltersModal"', self.feed_html)
        self.assertIn('id="filterTopicSearchInput"', self.feed_html)
        self.assertIn('id="modalTopicsFilterBar"', self.feed_html)
        self.assertIn('id="feedAudienceSelect"', self.feed_html)
        self.assertIn('id="feedFormatSelect"', self.feed_html)
        self.assertIn('id="feedComplexitySelect"', self.feed_html)
        self.assertIn('id="btnApplyFilters"', self.feed_html)
        self.assertIn('id="feedResetFiltersBtn"', self.feed_html)

        # 2. Subscriptions Modal
        self.assertIn('id="subscriptionsModal"', self.feed_html)
        self.assertIn('id="tabSubsAuthors"', self.feed_html)
        self.assertIn('id="tabSubsTopics"', self.feed_html)
        self.assertIn('id="tabSubsTags"', self.feed_html)
        self.assertIn('id="subsSearchInput"', self.feed_html)
        self.assertIn('id="subsListContainer"', self.feed_html)

        # 3. Auth Modal
        self.assertIn('id="authModal"', self.feed_html)
        self.assertIn('id="btnAuthLoginDemo"', self.feed_html)
        self.assertIn('id="authUserIdInput"', self.feed_html)
        self.assertIn('id="btnAuthLoginSubmit"', self.feed_html)

    def test_card_scroll_margin_and_cover_aspect_ratio(self):
        """Verify .feed-card has scroll-margin-top: 130px and cover container has 780/440 aspect ratio."""
        card_match = re.search(r'\.feed-card\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(card_match)
        self.assertIn('scroll-margin-top: 130px', card_match.group(1))

        cover_match = re.search(r'\.card-cover-container\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(cover_match)
        self.assertIn('aspect-ratio: 780 / 440', cover_match.group(1))

    def test_no_dashed_borders_in_feed_css(self):
        """Verify no dashed borders exist in feed.css (empty state and sidebar toggle use solid borders)."""
        self.assertNotIn('border: 1px dashed', self.feed_css)
        self.assertNotIn('dashed', self.feed_css)

    def test_article_page_author_subscribe_element(self):
        """Verify article.html contains #btnSubscribeAuthor and article.js binds subscription logic."""
        self.assertIn('id="btnSubscribeAuthor"', self.article_html)
        self.assertIn('btn-author-subscribe', self.article_html)
        self.assertIn('/api/subscriptions', self.article_js)
        self.assertIn('/api/subscriptions/toggle', self.article_js)

    def test_api_auth_lifecycle(self):
        """Verify GET /api/auth/status, POST /api/auth/login, and POST /api/auth/logout."""
        # 1. Status without cookie
        req = urllib.request.Request(f"{self.base_url}/api/auth/status")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            self.assertTrue(data.get("success"))
            self.assertFalse(data.get("authenticated"))

        # 2. Login as demo user
        login_payload = json.dumps({"userId": "test_user_01", "name": "Тестовый Пользователь"}).encode('utf-8')
        login_req = urllib.request.Request(
            f"{self.base_url}/api/auth/login",
            data=login_payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(login_req) as resp:
            login_data = json.loads(resp.read().decode('utf-8'))
            self.assertTrue(login_data.get("success"))
            self.assertTrue(login_data.get("authenticated"))
            self.assertEqual(login_data["user"]["id"], "test_user_01")
            cookie_header = resp.headers.get("Set-Cookie")
            self.assertIsNotNone(cookie_header)
            self.assertIn("sc_session=test_user_01", cookie_header)

        # 3. Status with cookie
        status_req = urllib.request.Request(
            f"{self.base_url}/api/auth/status",
            headers={"Cookie": "sc_session=test_user_01"}
        )
        with urllib.request.urlopen(status_req) as resp:
            status_data = json.loads(resp.read().decode('utf-8'))
            self.assertTrue(status_data.get("authenticated"))
            self.assertEqual(status_data["user"]["id"], "test_user_01")

        # 4. Logout
        logout_req = urllib.request.Request(
            f"{self.base_url}/api/auth/logout",
            data=b"{}",
            headers={"Content-Type": "application/json", "Cookie": "sc_session=test_user_01"}
        )
        with urllib.request.urlopen(logout_req) as resp:
            logout_data = json.loads(resp.read().decode('utf-8'))
            self.assertTrue(logout_data.get("success"))
            self.assertFalse(logout_data.get("authenticated"))

    def test_api_subscriptions_and_tag_normalization(self):
        """Verify GET /api/subscriptions, POST /api/subscriptions/toggle with normalization, and entities catalog."""
        # 1. Unauthenticated toggle returns 401
        toggle_payload = json.dumps({"targetType": "topic", "targetId": "smart-contracts-development"}).encode('utf-8')
        toggle_req = urllib.request.Request(
            f"{self.base_url}/api/subscriptions/toggle",
            data=toggle_payload,
            headers={"Content-Type": "application/json"}
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(toggle_req)
        self.assertEqual(ctx.exception.code, 401)

        # 2. Toggle topic subscription for user_sub_test
        auth_header = {"Cookie": "sc_session=user_sub_test", "Content-Type": "application/json"}
        toggle_req2 = urllib.request.Request(
            f"{self.base_url}/api/subscriptions/toggle",
            data=json.dumps({"targetType": "topic", "targetId": "smart-contracts-development", "targetTitle": "Разработка смарт-контрактов"}).encode('utf-8'),
            headers=auth_header
        )
        with urllib.request.urlopen(toggle_req2) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            self.assertTrue(data.get("success"))
            self.assertTrue(data.get("subscribed"))

        # 3. Toggle tag subscription with dirty input (leading #, extra spaces, mixed case)
        toggle_tag_req = urllib.request.Request(
            f"{self.base_url}/api/subscriptions/toggle",
            data=json.dumps({"targetType": "tag", "targetId": "   #Цифровой   Рубль  ", "targetTitle": "#Цифровой  рубль"}).encode('utf-8'),
            headers=auth_header
        )
        with urllib.request.urlopen(toggle_tag_req) as resp:
            tag_data = json.loads(resp.read().decode('utf-8'))
            self.assertTrue(tag_data.get("success"))
            self.assertTrue(tag_data.get("subscribed"))
            self.assertEqual(tag_data.get("targetId"), "цифровой рубль")

        # 4. GET /api/subscriptions returns both
        subs_req = urllib.request.Request(
            f"{self.base_url}/api/subscriptions",
            headers={"Cookie": "sc_session=user_sub_test"}
        )
        with urllib.request.urlopen(subs_req) as resp:
            subs_data = json.loads(resp.read().decode('utf-8'))
            self.assertTrue(subs_data.get("success"))
            self.assertEqual(len(subs_data["subscriptions"]["topics"]), 1)
            self.assertEqual(len(subs_data["subscriptions"]["tags"]), 1)
            self.assertEqual(subs_data["subscriptions"]["tags"][0]["id"], "цифровой рубль")

        # 5. GET /api/subscriptions/entities returns catalog with isSubscribed flags
        ent_req = urllib.request.Request(
            f"{self.base_url}/api/subscriptions/entities",
            headers={"Cookie": "sc_session=user_sub_test"}
        )
        with urllib.request.urlopen(ent_req) as resp:
            ent_data = json.loads(resp.read().decode('utf-8'))
            self.assertTrue(ent_data.get("success"))
            self.assertIn("authors", ent_data)
            self.assertIn("topics", ent_data)
            self.assertIn("tags", ent_data)
            sub_topic = next((t for t in ent_data["topics"] if t["id"] == "smart-contracts-development"), None)
            self.assertIsNotNone(sub_topic)
            self.assertTrue(sub_topic.get("isSubscribed"))

    def test_api_my_feed_access_control_and_reason_attachment(self):
        """Verify GET /api/articles?tab=my requires auth and returns articles with subscriptionReason."""
        # 1. Unauthenticated tab=my returns 401
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(f"{self.base_url}/api/articles?tab=my")
        self.assertEqual(ctx.exception.code, 401)

        # 2. Authenticated user with 0 subscriptions returns noSubscriptions: True
        zero_user_req = urllib.request.Request(
            f"{self.base_url}/api/articles?tab=my",
            headers={"Cookie": "sc_session=user_zero_subs"}
        )
        with urllib.request.urlopen(zero_user_req) as resp:
            zero_data = json.loads(resp.read().decode('utf-8'))
            self.assertTrue(zero_data.get("success"))
            self.assertEqual(zero_data.get("total"), 0)
            self.assertTrue(zero_data.get("noSubscriptions"))

        # 3. user_demo has seeded subscriptions and returns matched articles with subscriptionReason
        demo_req = urllib.request.Request(
            f"{self.base_url}/api/articles?tab=my",
            headers={"Cookie": "sc_session=user_demo"}
        )
        with urllib.request.urlopen(demo_req) as resp:
            demo_data = json.loads(resp.read().decode('utf-8'))
            self.assertTrue(demo_data.get("success"))
            self.assertGreater(demo_data.get("total"), 0)
            self.assertFalse(demo_data.get("noSubscriptions"))
            for art in demo_data.get("articles", []):
                self.assertIsNotNone(art.get("subscriptionReason"))
                self.assertTrue(art["subscriptionReason"].startswith("Вы подписаны"))


if __name__ == '__main__':
    unittest.main()

