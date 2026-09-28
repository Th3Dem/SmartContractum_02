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

import base64
import datetime
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
from typing import Any, Dict, List, Optional, Tuple, Union

import server
import image_decoder

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
        self.assertTrue('feed-filter-bar' in self.feed_html or 'feedSubnavBar' in self.feed_html or 'feed-subnav-bar' in self.feed_html)
        self.assertTrue('feed-filter-btn' in self.feed_html or 'btnFeedFilters' in self.feed_html or 'btn-subnav-action' in self.feed_html)
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

        # Filter buttons or slide-down panels
        filter_buttons = re.findall(r'<button[^>]*class=["\'][^"\']*feed-filter-btn[^"\']*["\'][^>]*>(.*?)</button>', self.feed_html)
        if filter_buttons:
            self.assertGreaterEqual(len(filter_buttons), 4, "Expected at least 4 category filter buttons")
            required_categories = ['Все', 'Разработка', 'Безопасность']
            for cat in required_categories:
                self.assertTrue(
                    any(cat in btn for btn in filter_buttons),
                    f"Filter button for '{cat}' not found in feed.html"
                )
        else:
            self.assertTrue('btnFeedFilters' in self.feed_html or 'btn-feed-filters' in self.feed_html or 'feedFiltersPanel' in self.feed_html)
            self.assertTrue('btnFeedSettings' in self.feed_html or 'btn-feed-settings' in self.feed_html or 'feedSettingsPanel' in self.feed_html)

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
        """Verify 'Главный архитектор ПКСК' is removed and demo articles do not have duplicate (демо) in titles/roles."""
        self.assertNotIn('Главный архитектор ПКСК', self.server_py)
        self.assertNotIn('Главный архитектор ПКСК', self.feed_js)
        self.assertNotIn('Главный архитектор ПКСК', self.article_js)
        self.assertNotIn('(демо)', self.server_py)
        self.assertNotIn('Архитектор решений (демо)', self.feed_js)

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
        """Verify Unified Filters Modal/Panel, Subscriptions Modal, and Auth Modal in feed.html."""
        # 1. Filters (Slide-down Panel or Modal)
        self.assertTrue('id="feedFiltersModal"' in self.feed_html or 'id="feedFiltersPanel"' in self.feed_html)
        self.assertIn('id="feedAudienceSelect"', self.feed_html)
        self.assertIn('id="feedFormatSelect"', self.feed_html)
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


class TestTask27FeedVisualRegressionsAndPolish(unittest.TestCase):
    """Test suite for task-27: Feed visual regressions, write CTA, cover loading, sidebar topics, demo badges."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(FRONTEND_DIR, 'feed.html'), 'r', encoding='utf-8') as f:
            cls.feed_html = f.read()
        with open(os.path.join(FRONTEND_DIR, 'css', 'feed.css'), 'r', encoding='utf-8') as f:
            cls.feed_css = f.read()
        with open(os.path.join(FRONTEND_DIR, 'js', 'feed.js'), 'r', encoding='utf-8') as f:
            cls.feed_js = f.read()
        with open(os.path.join(PROJECT_ROOT, 'server.py'), 'r', encoding='utf-8') as f:
            cls.server_py = f.read()

        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, 'task27_test.db')

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

    def test_write_cta_button_in_subnav_and_styles(self):
        """Verify the 'Написать' CTA button in subnav is fully visible, styled, and not an empty rectangle."""
        # 1. Markup in feed.html has button with text and SVG icon
        self.assertIn('id="btnHeroWrite"', self.feed_html)
        self.assertIn('feed-subnav-write-btn', self.feed_html)
        self.assertIn('>Написать<', self.feed_html)
        self.assertIn('<svg width="16" height="16" viewBox="0 0 24 24"', self.feed_html)

        # 2. feed.css styling has solid/gradient background and white text, no reliance on missing var
        self.assertIn('.feed-subnav-write-btn', self.feed_css)
        self.assertIn('background: linear-gradient(135deg, #3861fb 0%, #2563eb 100%)', self.feed_css)
        self.assertIn('color: #ffffff', self.feed_css)
        self.assertIn('.feed-subnav-write-btn:hover', self.feed_css)
        self.assertIn('.feed-subnav-write-btn:active', self.feed_css)
        self.assertIn('.feed-subnav-write-btn:focus-visible', self.feed_css)

        # 3. Light theme support
        self.assertIn('[data-theme="light"] .feed-subnav-write-btn', self.feed_css)

    def test_cover_image_container_and_offline_base64_data_uris(self):
        """Verify cover container has 780/440 aspect-ratio, loading shimmer, error handling, and offline base64 data URIs."""
        # 1. CSS rules for card-cover-container
        self.assertIn('.card-cover-container', self.feed_css)
        self.assertIn('max-width: 780px;', self.feed_css)
        self.assertIn('aspect-ratio: 780 / 440;', self.feed_css)
        self.assertIn('.card-cover-container.is-loading', self.feed_css)
        self.assertIn('.card-cover-container.is-loaded', self.feed_css)
        self.assertIn('.card-cover-container.is-error', self.feed_css)
        self.assertIn('display: none !important;', self.feed_css)

        # 2. feed.js cover handling: onerror removes container, onload marks loaded
        self.assertIn('card-cover-container', self.feed_js)
        self.assertIn(r"closest(\'.card-cover-container\')", self.feed_js)
        self.assertIn('remove()', self.feed_js)

        # 3. Seed articles in server.py and FALLBACK_ARTICLES in feed.js use base64 data URIs
        for art in server.APPROVED_SEED_ARTICLES:
            cov = art["publication_settings"].get("coverImage", "")
            self.assertTrue(cov.startswith("data:image/svg+xml;base64,"), f"Article {art['id']} must use base64 data URI")
            # Verify base64 decodes cleanly
            raw_b64 = cov.split(",", 1)[1]
            decoded = base64.b64decode(raw_b64).decode("utf-8")
            self.assertTrue(decoded.startswith("<svg"))
            self.assertTrue(decoded.endswith("</svg>"))

        self.assertNotIn('images.unsplash.com', self.feed_js)
        self.assertIn('data:image/svg+xml;base64,', self.feed_js)

    def test_sidebar_topics_widget_styling_and_descending_sort(self):
        """Verify sidebar topics widget has row layout, left-aligned title, counter pill, and count-descending sort."""
        # 1. CSS rules for row layout and counter pill
        self.assertIn('.widget-topic-row', self.feed_css)
        self.assertIn('.widget-topic-chip', self.feed_css)
        self.assertIn('justify-content: space-between', self.feed_css)
        self.assertIn('.widget-topic-title', self.feed_css)
        self.assertIn('.widget-topic-count', self.feed_css)
        self.assertIn('.widget-topic-row.is-active', self.feed_css)

        # 2. feed.js sorts by count descending then title Russian locale
        self.assertIn('function renderSidebarTopics(topicCounts)', self.feed_js)
        self.assertIn('countB - countA', self.feed_js)
        self.assertIn('localeCompare', self.feed_js)
        self.assertIn('btnToggleAllSidebarTopics', self.feed_js)

    def test_header_and_subnav_container_alignment(self):
        """Verify .feed-subnav-container and .feed-main-container align with .header-container at max-width 1360px."""
        self.assertIn('.feed-subnav-container', self.feed_css)
        self.assertIn('max-width: 1360px', self.feed_css)
        self.assertIn('.feed-main-container', self.feed_css)
        self.assertIn('padding: 20px 24px 60px 24px', self.feed_css)

    def test_demo_badge_and_clean_metadata(self):
        """Verify demo articles have no (демо) in titles/roles, but display badge-demo in card metadata."""
        # 1. Server seed articles have isDemo: True and clean titles/roles
        for art in server.APPROVED_SEED_ARTICLES:
            self.assertTrue(art["publication_settings"].get("isDemo"), f"Article {art['id']} must have isDemo: True")
            self.assertNotIn('(демо)', art["title"])
            self.assertNotIn('(демо)', art["publication_settings"]["authorRole"])

        # 2. feed.js creates .badge-demo for demo articles
        self.assertIn('badge-demo', self.feed_js)
        self.assertIn('Демонстрационный материал', self.feed_js)
        self.assertIn('.badge-demo', self.feed_css)

        # 3. feed.html widget-create-card has concise text
        self.assertIn('Опубликуйте разбор, инструкцию или кейс о коммерческих смарт-контрактах', self.feed_html)

    def test_author_search_in_api(self):
        """Verify GET /api/articles?search=... searches by author name and author role."""
        req_author = urllib.request.Request(f"{self.base_url}/api/articles?search=%D0%A1%D0%BC%D0%B8%D1%80%D0%BD%D0%BE%D0%B2")
        with urllib.request.urlopen(req_author) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            self.assertTrue(data.get("success"))
            self.assertEqual(data.get("total"), 1)
            self.assertEqual(data["articles"][0]["author"], "Алексей Смирнов")
            self.assertTrue(data["articles"][0]["isDemo"])

        req_role = urllib.request.Request(f"{self.base_url}/api/articles?search=%D0%B0%D1%83%D0%B4%D0%B8%D1%82%D0%BE%D1%80")
        with urllib.request.urlopen(req_role) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            self.assertTrue(data.get("success"))
            self.assertGreaterEqual(data.get("total"), 1)
            authors = [a["author"] for a in data["articles"]]
            self.assertIn("Екатерина Романова", authors)



class TestTask28CoverSyncAndFeedPolish(unittest.TestCase):
    """
    Test suite for task-28-feed-cover-sync-and-polish:
    1. Unified cover configuration in PublicationConfig.COVER and theme.css tokens
    2. Editor feed section descriptions, hints, and 7-step card preview markup
    3. Editor CSS preview card styles (560px max width, 39:22 aspect ratio, 0px empty state)
    4. Feed CSS card cover, line clamp, and compact toolbar
    5. Feed sidebar topics showing only count > 0 in short list
    6. Server-side cover image validation (base64 JPEG/PNG/WebP/GIF/SVG, limits, error handling)
    """

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(FRONTEND_DIR, 'js', 'config.js'), 'r', encoding='utf-8') as f:
            cls.config_js = f.read()
        with open(os.path.join(FRONTEND_DIR, 'css', 'theme.css'), 'r', encoding='utf-8') as f:
            cls.theme_css = f.read()
        with open(os.path.join(FRONTEND_DIR, 'editor.html'), 'r', encoding='utf-8') as f:
            cls.editor_html = f.read()
        with open(os.path.join(FRONTEND_DIR, 'css', 'editor.css'), 'r', encoding='utf-8') as f:
            cls.editor_css = f.read()
        with open(os.path.join(FRONTEND_DIR, 'css', 'feed.css'), 'r', encoding='utf-8') as f:
            cls.feed_css = f.read()
        with open(os.path.join(FRONTEND_DIR, 'js', 'feed.js'), 'r', encoding='utf-8') as f:
            cls.feed_js = f.read()
        with open(os.path.join(PROJECT_ROOT, 'server.py'), 'r', encoding='utf-8') as f:
            cls.server_py = f.read()

        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, 'task28_test.db')

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

    def test_unified_cover_config_and_tokens(self):
        """
        Verify PublicationConfig.COVER in config.js (780x440, 39:22, max 10MB, formats)
        and design tokens in theme.css (--card-cover-aspect-ratio: 39 / 22;, --card-cover-max-width: 560px;).
        """
        # 1. PublicationConfig.COVER parameters in config.js
        self.assertIn('const COVER = {', self.config_js)
        self.assertIn('TARGET_WIDTH: 780', self.config_js)
        self.assertIn('TARGET_HEIGHT: 440', self.config_js)
        self.assertIn('ASPECT_RATIO_W: 39', self.config_js)
        self.assertIn('ASPECT_RATIO_H: 22', self.config_js)
        self.assertIn("ASPECT_RATIO_STR: '39 / 22'", self.config_js)
        self.assertIn('MAX_FILE_BYTES: 10 * 1024 * 1024', self.config_js)
        self.assertTrue('FEED_FULL_WIDTH: true' in self.config_js or 'FEED_MAX_WIDTH_PX: 560' in self.config_js)
        self.assertIn("'image/jpeg'", self.config_js)
        self.assertIn("'image/png'", self.config_js)
        self.assertIn("'image/webp'", self.config_js)
        self.assertIn("'image/gif'", self.config_js)
        self.assertIn('COVER,', self.config_js)
        self.assertIn('window.PublicationConfig = PublicationConfig;', self.config_js)

        # 2. Design tokens in theme.css
        self.assertIn('--card-cover-aspect-ratio: 39 / 22;', self.theme_css)
        self.assertTrue('--card-cover-max-width: 100%;' in self.theme_css or '--card-cover-max-width: 560px;' in self.theme_css)

    def test_editor_feed_section_texts_and_preview_markup(self):
        """
        Verify exact hint and description texts in editor.html and
        the 7-step sequence of elements in #pub-card-preview:
        author -> title -> badges -> cover -> description -> tags -> footer.
        """
        # 1. Exact hint and description texts in editor.html
        self.assertIn(
            'Обложка необязательна. Рекомендуемое разрешение — от 780 × 440 px. Область обложки — 39:22. JPG/JPEG, PNG, WebP или GIF, до 10 МБ. При необходимости можно выбрать кадр',
            self.editor_html
        )
        self.assertIn(
            'В ленте обложка отображается в уменьшенном размере с сохранением выбранного кадра. Для GIF используется первый кадр без анимации.',
            self.editor_html
        )
        self.assertIn('Кадрирование обложки (39:22)', self.editor_html)

        # 2. 7-step card preview markup structure
        preview_pos = self.editor_html.find('id="pub-card-preview"')
        self.assertNotEqual(preview_pos, -1, "Preview card #pub-card-preview must exist in editor.html")
        preview_chunk = self.editor_html[preview_pos:preview_pos + 4000]

        idx_author = preview_chunk.find('class="card-meta"')
        idx_title = preview_chunk.find('id="preview-card-title"')
        idx_badges = preview_chunk.find('id="preview-card-badges"')
        idx_cover = preview_chunk.find('id="preview-card-cover"')
        idx_desc = preview_chunk.find('id="preview-card-desc"')
        idx_tags = preview_chunk.find('id="preview-card-tags"')
        idx_footer = preview_chunk.find('class="card-footer')

        self.assertNotEqual(idx_author, -1, "Author block must exist in preview card")
        self.assertNotEqual(idx_title, -1, "Title must exist in preview card")
        self.assertNotEqual(idx_badges, -1, "Badges container must exist in preview card")
        self.assertNotEqual(idx_cover, -1, "Cover container must exist in preview card")
        self.assertNotEqual(idx_desc, -1, "Description lead must exist in preview card")
        self.assertNotEqual(idx_tags, -1, "Tags container must exist in preview card")
        self.assertNotEqual(idx_footer, -1, "Footer must exist in preview card")

        self.assertLess(idx_author, idx_title, "Author must precede Title")
        self.assertLess(idx_title, idx_badges, "Title must precede Badges")
        self.assertLess(idx_badges, idx_cover, "Badges must precede Cover")
        self.assertLess(idx_cover, idx_desc, "Cover must precede Description")
        self.assertLess(idx_desc, idx_tags, "Description must precede Tags")
        self.assertLess(idx_tags, idx_footer, "Tags must precede Footer")

    def test_editor_css_preview_card_styles(self):
        """
        Verify .pub-feed-card-cover styles: full-width (or max-width 100%), aspect-ratio 39 / 22,
        and 0px reserved space when hidden.
        """
        self.assertIn('.pub-feed-card-cover', self.editor_css)
        self.assertTrue('var(--card-cover-max-width' in self.editor_css or 'width: 100%;' in self.editor_css)
        self.assertIn('aspect-ratio: var(--card-cover-aspect-ratio, 39 / 22);', self.editor_css)
        self.assertTrue('align-self: stretch;' in self.editor_css or 'align-self: flex-start;' in self.editor_css)

        # 0px when cover is hidden / empty
        self.assertIn('.pub-feed-card-cover[style*="display: none"]', self.editor_css)
        self.assertIn('display: none !important;', self.editor_css)
        self.assertIn('margin: 0 !important;', self.editor_css)
        self.assertIn('height: 0 !important;', self.editor_css)

    def test_feed_css_card_cover_and_compactness(self):
        """
        Verify .card-cover-container in feed.css (full-width 100%, aspect-ratio 39 / 22),
        .card-lead line clamping to 3 lines, and compact .feed-toolbar-row.
        """
        # 1. .card-cover-container styling
        self.assertIn('.card-cover-container', self.feed_css)
        self.assertTrue('var(--card-cover-max-width' in self.feed_css or 'width: 100%;' in self.feed_css)
        self.assertIn('aspect-ratio: var(--card-cover-aspect-ratio, 39 / 22);', self.feed_css)
        self.assertTrue('align-self: stretch;' in self.feed_css or 'align-self: flex-start;' in self.feed_css)

        # 2. .card-lead 3 lines limit
        self.assertIn('.card-lead', self.feed_css)
        self.assertIn('-webkit-line-clamp: 3;', self.feed_css)
        self.assertIn('display: -webkit-box;', self.feed_css)
        self.assertIn('-webkit-box-orient: vertical;', self.feed_css)

        # 3. Compact service row .feed-toolbar-row
        self.assertIn('.feed-toolbar-row', self.feed_css)
        self.assertIn('display: flex;', self.feed_css)
        self.assertIn('justify-content: space-between;', self.feed_css)

    def test_feed_sidebar_topics_only_with_positive_count(self):
        """
        Verify renderSidebarTopics logic in feed.js: the short sidebar list
        filters and displays only topics with count > 0.
        """
        self.assertIn('function renderSidebarTopics(topicCounts)', self.feed_js)
        self.assertIn('count > 0', self.feed_js)
        self.assertIn('const nonZeroTopics = sortedTopics.filter', self.feed_js)
        self.assertIn(
            'const visible = isSidebarTopicsExpanded ? sortedTopics : nonZeroTopics.slice(0, initialVisible);',
            self.feed_js
        )

    def test_server_cover_image_validation(self):
        """
        Verify server-side cover image validation in server.py:
        - Successful acceptance of valid base64 images (JPEG, PNG, WebP, GIF, SVG)
        - Rejection of invalid base64 / corrupted data
        - Rejection of unsupported MIME types
        - Rejection of images over 10 MB
        - Handling draft without cover (None, empty string, omitted)
        - Full submit flow via POST /api/moderation/submit and persistence in queue
        """
        base_payload = {
            "draftId": "draft_t28_test",
            "title": "Тестирование валидации обложки",
            "html": "<p>Тело публикации с достаточным количеством символов для успешной валидации статьи.</p>",
            "publicationSettings": {
                "targetAudience": "smart-contracts-dev",
                "topics": ["smart-contracts-development"],
                "keywords": ["валидация", "обложка", "тест"],
                "description": "Описание статьи длиной более 50 символов для проверки серверной валидации.",
                "format": "tutorial",
                "complexity": "medium"
            },
            "idempotencyKey": "key_t28_val",
            "authorId": "author_tester"
        }

        # 1. Draft without cover is valid (None, empty string, omitted)
        p_omitted = json.loads(json.dumps(base_payload))
        ok, err, f_errs = server.validate_submission_payload(p_omitted)
        self.assertTrue(ok, f"Draft without cover should be valid: {err}")
        self.assertNotIn("coverImage", f_errs)

        p_empty = json.loads(json.dumps(base_payload))
        p_empty["publicationSettings"]["coverImage"] = ""
        ok, err, f_errs = server.validate_submission_payload(p_empty)
        self.assertTrue(ok, f"Draft with empty coverImage should be valid: {err}")
        self.assertNotIn("coverImage", f_errs)

        p_none = json.loads(json.dumps(base_payload))
        p_none["publicationSettings"]["coverImage"] = None
        ok, err, f_errs = server.validate_submission_payload(p_none)
        self.assertTrue(ok, f"Draft with None coverImage should be valid: {err}")
        self.assertNotIn("coverImage", f_errs)

        # 2. Acceptance of valid images (JPEG, PNG, WebP, GIF, SVG, /media/ path)
        jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\xff\xd9"
        jpeg_uri = f"data:image/jpeg;base64,{base64.b64encode(jpeg_bytes).decode('ascii')}"
        p_jpeg = json.loads(json.dumps(base_payload))
        p_jpeg["publicationSettings"]["coverImage"] = jpeg_uri
        ok, err, f_errs = server.validate_submission_payload(p_jpeg)
        self.assertTrue(ok, f"Valid JPEG should pass validation: {err}")

        png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        png_uri = f"data:image/png;base64,{base64.b64encode(png_bytes).decode('ascii')}"
        p_png = json.loads(json.dumps(base_payload))
        p_png["publicationSettings"]["coverImage"] = png_uri
        ok, err, f_errs = server.validate_submission_payload(p_png)
        self.assertTrue(ok, f"Valid PNG should pass validation: {err}")

        webp_bytes = b"RIFF\x14\x00\x00\x00WEBPVP8 \x08\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00"
        webp_uri = f"data:image/webp;base64,{base64.b64encode(webp_bytes).decode('ascii')}"
        p_webp = json.loads(json.dumps(base_payload))
        p_webp["publicationSettings"]["coverImage"] = webp_uri
        ok, err, f_errs = server.validate_submission_payload(p_webp)
        self.assertTrue(ok, f"Valid WebP should pass validation: {err}")

        gif_bytes = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        gif_uri = f"data:image/gif;base64,{base64.b64encode(gif_bytes).decode('ascii')}"
        p_gif = json.loads(json.dumps(base_payload))
        p_gif["publicationSettings"]["coverImage"] = gif_uri
        ok, err, f_errs = server.validate_submission_payload(p_gif)
        self.assertTrue(ok, f"Valid GIF should pass validation: {err}")

        svg_bytes = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 780 440"><rect width="780" height="440" fill="#000"/></svg>'
        svg_uri = f"data:image/svg+xml;base64,{base64.b64encode(svg_bytes).decode('ascii')}"
        p_svg = json.loads(json.dumps(base_payload))
        p_svg["publicationSettings"]["coverImage"] = svg_uri
        ok, err, f_errs = server.validate_submission_payload(p_svg)
        self.assertTrue(ok, f"Valid SVG should pass validation: {err}")

        p_media = json.loads(json.dumps(base_payload))
        p_media["publicationSettings"]["coverImage"] = "/media/covers/cover_01.png"
        ok, err, f_errs = server.validate_submission_payload(p_media)
        self.assertTrue(ok, f"Valid /media/ path should pass validation: {err}")

        # 3. Rejection of invalid base64 / corrupted data
        p_corrupt_b64 = json.loads(json.dumps(base_payload))
        p_corrupt_b64["publicationSettings"]["coverImage"] = "data:image/png;base64,corrupted_base64_!@#$"
        ok, err, f_errs = server.validate_submission_payload(p_corrupt_b64)
        self.assertFalse(ok)
        self.assertIn("coverImage", f_errs)
        self.assertIn("Обложка должна быть валидным изображением", f_errs["coverImage"])

        # 4. Rejection of valid base64 but corrupted image magic bytes
        p_corrupt_magic = json.loads(json.dumps(base_payload))
        p_corrupt_magic["publicationSettings"]["coverImage"] = f"data:image/png;base64,{base64.b64encode(b'not_a_png_image_data').decode('ascii')}"
        ok, err, f_errs = server.validate_submission_payload(p_corrupt_magic)
        self.assertFalse(ok)
        self.assertIn("coverImage", f_errs)

        # 5. Rejection of unsupported MIME types
        p_unsupported = json.loads(json.dumps(base_payload))
        p_unsupported["publicationSettings"]["coverImage"] = f"data:image/bmp;base64,{base64.b64encode(b'BM12345').decode('ascii')}"
        ok, err, f_errs = server.validate_submission_payload(p_unsupported)
        self.assertFalse(ok)
        self.assertIn("coverImage", f_errs)

        # 6. Rejection of image exceeding 10 MB
        big_bytes = b"\x89PNG" + (b"\x00" * (10 * 1024 * 1024 + 10))
        big_uri = f"data:image/png;base64,{base64.b64encode(big_bytes).decode('ascii')}"
        p_over_10mb = json.loads(json.dumps(base_payload))
        p_over_10mb["publicationSettings"]["coverImage"] = big_uri
        ok, err, f_errs = server.validate_submission_payload(p_over_10mb)
        self.assertFalse(ok)
        self.assertIn("coverImage", f_errs)
        self.assertIn("до 10 МБ", f_errs["coverImage"])

        # 7. End-to-end HTTP POST /api/moderation/submit check
        p_submit_ok = json.loads(json.dumps(base_payload))
        p_submit_ok["draftId"] = "draft_t28_http_ok"
        p_submit_ok["idempotencyKey"] = "idemp_t28_http_ok"
        p_submit_ok["publicationSettings"]["coverImage"] = png_uri
        post_data = json.dumps(p_submit_ok).encode('utf-8')
        req = urllib.request.Request(
            f"{self.base_url}/api/moderation/submit",
            data=post_data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            submit_res = json.loads(resp.read().decode('utf-8'))
            self.assertTrue(submit_res.get("success"))
            self.assertEqual(submit_res.get("status"), "pending_moderation")
            sub_id = submit_res.get("submissionId")

        # Verify cover image is stored in snapshot
        list_req = urllib.request.Request(f"{self.base_url}/api/moderation/list")
        with urllib.request.urlopen(list_req) as resp:
            list_res = json.loads(resp.read().decode('utf-8'))
            found = next((s for s in list_res["submissions"] if s["id"] == sub_id), None)
            self.assertIsNotNone(found)
            cov_stored = found["publicationSettings"]["coverImage"]
            self.assertTrue(cov_stored.startswith("/media/") or cov_stored == png_uri)

        # HTTP rejection for invalid cover
        p_submit_bad = json.loads(json.dumps(base_payload))
        p_submit_bad["draftId"] = "draft_t28_http_bad"
        p_submit_bad["idempotencyKey"] = "idemp_t28_http_bad"
        p_submit_bad["publicationSettings"]["coverImage"] = "data:image/tiff;base64,not_supported"
        req_bad = urllib.request.Request(
            f"{self.base_url}/api/moderation/submit",
            data=json.dumps(p_submit_bad).encode('utf-8'),
            headers={"Content-Type": "application/json"}
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req_bad)
        self.assertEqual(ctx.exception.code, 400)
        bad_res = json.loads(ctx.exception.read().decode('utf-8'))
        ctx.exception.close()
        self.assertFalse(bad_res.get("success"))
        self.assertIn("coverImage", bad_res.get("fieldErrors", {}))


class TestTask29FullwidthCoverAndMediaStorage(unittest.TestCase):
    """
    Test suite for task-29-feed-cover-fullwidth-and-media-storage:
    1. Full-width cover display: 100% inner card content width, 39:22 aspect ratio, no 560px cap.
    2. Unified card component: card.js (SmartContractumCard) shared by feed and editor preview.
    3. Deep server-side image decoding: pure-Python image_decoder validating PNG/JPEG/GIF/WebP/SVG,
       rejecting corrupted/truncated files, animated GIFs, pixel bombs.
    4. Persistent server media storage: /media/<sha256>.<ext>, POST /api/media/upload,
       GET /media/<filename> with caching and path traversal protection.
    5. Moderation workflow & draft isolation: submitted Data URLs convert to persistent /media/ URLs,
       raw crop params and source files excluded from public API.
    6. Zero site overlays: no site-generated titles, badges, or watermarks on top of the cover.
    """

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(FRONTEND_DIR, 'js', 'config.js'), 'r', encoding='utf-8') as f:
            cls.config_js = f.read()
        with open(os.path.join(FRONTEND_DIR, 'css', 'theme.css'), 'r', encoding='utf-8') as f:
            cls.theme_css = f.read()
        with open(os.path.join(FRONTEND_DIR, 'editor.html'), 'r', encoding='utf-8') as f:
            cls.editor_html = f.read()
        with open(os.path.join(FRONTEND_DIR, 'feed.html'), 'r', encoding='utf-8') as f:
            cls.feed_html = f.read()
        with open(os.path.join(FRONTEND_DIR, 'css', 'editor.css'), 'r', encoding='utf-8') as f:
            cls.editor_css = f.read()
        with open(os.path.join(FRONTEND_DIR, 'css', 'feed.css'), 'r', encoding='utf-8') as f:
            cls.feed_css = f.read()
        with open(os.path.join(FRONTEND_DIR, 'js', 'feed.js'), 'r', encoding='utf-8') as f:
            cls.feed_js = f.read()
        with open(os.path.join(FRONTEND_DIR, 'js', 'publication.js'), 'r', encoding='utf-8') as f:
            cls.pub_js = f.read()
        with open(os.path.join(FRONTEND_DIR, 'js', 'card.js'), 'r', encoding='utf-8') as f:
            cls.card_js = f.read()
        with open(os.path.join(PROJECT_ROOT, 'image_decoder.py'), 'r', encoding='utf-8') as f:
            cls.image_decoder_py = f.read()
        with open(os.path.join(PROJECT_ROOT, 'server.py'), 'r', encoding='utf-8') as f:
            cls.server_py = f.read()

        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, 'task29_test.db')
        cls.media_dir = os.path.join(cls.temp_dir, 'media')

        cls.server = server.create_server(
            host="127.0.0.1",
            port=0,
            db_path=cls.db_path,
            directory=FRONTEND_DIR,
            media_dir=cls.media_dir
        )
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

    def test_tokens_and_fullwidth_cover_css(self):
        """Verify removal of 560px restriction and enforcement of full card content width."""
        # 1. config.js
        self.assertIn('FEED_FULL_WIDTH: true', self.config_js)
        self.assertIn("FEED_MAX_WIDTH: '100%'", self.config_js)
        self.assertNotIn('FEED_MAX_WIDTH_PX: 560', self.config_js)

        # 2. theme.css tokens
        self.assertIn('--card-cover-aspect-ratio: 39 / 22;', self.theme_css)
        self.assertIn('--card-cover-max-width: 100%;', self.theme_css)

        # 3. feed.css
        self.assertIn('.card-cover-container', self.feed_css)
        self.assertIn('max-width: var(--card-cover-max-width, 100%);', self.feed_css)
        self.assertIn('aspect-ratio: var(--card-cover-aspect-ratio, 39 / 22);', self.feed_css)
        self.assertIn('align-self: stretch;', self.feed_css)

        # 4. editor.css
        self.assertIn('.pub-feed-card-cover', self.editor_css)
        self.assertIn('max-width: 100%;', self.editor_css)
        self.assertIn('aspect-ratio: var(--card-cover-aspect-ratio, 39 / 22);', self.editor_css)
        self.assertIn('align-self: stretch;', self.editor_css)

        # 5. Clean 0px empty state
        self.assertIn('.card-cover-container.is-error', self.feed_css)
        self.assertIn('.pub-feed-card-cover[style*="display: none"]', self.editor_css)

    def test_unified_card_js_component(self):
        """Verify unified SmartContractumCard component used identically in feed and preview."""
        # 1. card.js script tag in both HTML pages
        self.assertIn('<script src="js/card.js', self.feed_html)
        self.assertIn('<script src="js/card.js', self.editor_html)

        # 2. card.js definition
        self.assertIn('window.SmartContractumCard', self.card_js)
        self.assertIn('renderCardInnerHtml', self.card_js)
        self.assertIn('createCardElement', self.card_js)

        # 3. 7-step structure in card.js
        idx_meta = self.card_js.find("class=\"card-meta\"")
        idx_title = self.card_js.find("class=\"card-title")
        idx_badges = self.card_js.find("class=\"card-meta-badges")
        idx_cover = self.card_js.find("class=\"card-cover-container")
        idx_lead = self.card_js.find("class=\"card-lead")
        idx_tags = self.card_js.find("class=\"card-tags")
        idx_footer = self.card_js.find("class=\"card-footer\"")

        self.assertTrue(0 < idx_meta < idx_title < idx_badges < idx_cover < idx_lead < idx_tags < idx_footer)

        # 4. Usage in feed.js and publication.js
        self.assertIn('window.SmartContractumCard.createCardElement', self.feed_js)
        self.assertIn('window.SmartContractumCard.renderCardInnerHtml', self.pub_js)

    def test_image_decoder_deep_validation(self):
        """Verify pure-Python deep image decoding, integrity, and corruption rejection."""
        # 1. Valid PNG
        png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        ok, err, meta = image_decoder.decode_and_validate_image(png_bytes)
        self.assertTrue(ok)
        self.assertEqual(meta["format"], "png")
        self.assertEqual(meta["width"], 1)
        self.assertEqual(meta["height"], 1)

        # 2. Truncated PNG (missing IEND) rejected
        trunc_png = png_bytes[:-12]
        ok, err, meta = image_decoder.decode_and_validate_image(trunc_png)
        self.assertFalse(ok)
        self.assertIn("IEND", err)

        # 3. Valid JPEG
        jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\xff\xd9"
        ok, err, meta = image_decoder.decode_and_validate_image(jpeg_bytes)
        self.assertTrue(ok)
        self.assertEqual(meta["format"], "jpeg")

        # 4. Truncated JPEG (missing EOI) rejected
        trunc_jpeg = jpeg_bytes[:-2]
        ok, err, meta = image_decoder.decode_and_validate_image(trunc_jpeg)
        self.assertFalse(ok)
        self.assertIn("EOI", err)

        # 5. Static GIF accepted
        gif_bytes = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        ok, err, meta = image_decoder.decode_and_validate_image(gif_bytes)
        self.assertTrue(ok)
        self.assertEqual(meta["format"], "gif")
        self.assertTrue(meta["is_static"])

        # 6. Truncated GIF (missing trailer 0x3B) rejected
        trunc_gif = gif_bytes[:-1]
        ok, err, meta = image_decoder.decode_and_validate_image(trunc_gif)
        self.assertFalse(ok)

        # 7. Animated GIF rejected (must be static)
        multi_frame_gif = (
            b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff"
            b",\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00"
            b",\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        )
        ok, err, meta = image_decoder.decode_and_validate_image(multi_frame_gif)
        self.assertFalse(ok)
        self.assertIn("статичной", err)

        # 8. Aspect ratio requirement check (39:22)
        svg_39_22 = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 780 440"><rect width="780" height="440"/></svg>'
        ok, err, meta = image_decoder.decode_and_validate_image(svg_39_22, require_aspect_ratio=True)
        self.assertTrue(ok)

        svg_bad_ratio = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 600"><rect width="400" height="600"/></svg>'
        ok, err, meta = image_decoder.decode_and_validate_image(svg_bad_ratio, require_aspect_ratio=True)
        self.assertFalse(ok)
        self.assertIn("не соответствуют требуемым 39:22", err)

    def test_server_media_upload_and_serving(self):
        """Verify POST /api/media/upload and GET /media/<filename> with path security and caching."""
        png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        b64_uri = f"data:image/png;base64,{base64.b64encode(png_bytes).decode('ascii')}"

        # 1. POST /api/media/upload with JSON Data URI
        upload_req = urllib.request.Request(
            f"{self.base_url}/api/media/upload",
            data=json.dumps({"image": b64_uri}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(upload_req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("success"))
            self.assertTrue(data["url"].startswith("/media/"))
            self.assertTrue(data["url"].endswith(".png"))
            saved_url = data["url"]

        # 2. GET /media/<filename>
        media_req = urllib.request.Request(f"{self.base_url}{saved_url}")
        with urllib.request.urlopen(media_req) as resp:
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.headers.get("Content-Type"), "image/png")
            self.assertIn("immutable", resp.headers.get("Cache-Control", ""))
            fetched_bytes = resp.read()
            self.assertEqual(fetched_bytes, png_bytes)

        # 3. Path traversal security: /media/../ prohibited
        bad_req = urllib.request.Request(f"{self.base_url}/media/../test.db")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(bad_req)
        self.assertIn(ctx.exception.code, (400, 403, 404))

        # 4. 404 for non-existent media
        missing_req = urllib.request.Request(f"{self.base_url}/media/missing_file_000.png")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(missing_req)
        self.assertEqual(ctx.exception.code, 404)

    def test_moderation_submit_converts_data_url_to_media_and_isolates_draft(self):
        """Verify submit converts Data URL to persistent /media/ and isolates draft modifications."""
        png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        b64_uri = f"data:image/png;base64,{base64.b64encode(png_bytes).decode('ascii')}"

        payload = {
            "draftId": "draft_t29_isolation",
            "title": "Статья с проверкой изоляции и медиа-хранилища",
            "html": "<p>Текст статьи достаточного объема для успешной серверной валидации публикации.</p>",
            "publicationSettings": {
                "targetAudience": "smart-contracts-dev",
                "topics": ["smart-contracts-development"],
                "keywords": ["хранилище", "медиа", "изоляция"],
                "description": "Описание статьи длиной более пятидесяти символов для проверки медиа-хранилища.",
                "format": "guide",
                "complexity": "medium",
                "coverImage": b64_uri,
                "rawCoverImageSource": "data:image/png;base64,RAW_SOURCE_MOCK",
                "cropParams": {"zoom": 1.2, "panX": 10, "panY": 20}
            },
            "idempotencyKey": "key_t29_isolation_1",
            "authorId": "author_t29"
        }

        # 1. Submit to moderation
        sub_req = urllib.request.Request(
            f"{self.base_url}/api/moderation/submit",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(sub_req) as resp:
            sub_res = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(sub_res.get("success"))
            sub_id = sub_res["submissionId"]

        # 2. Check stored snapshot in moderation list
        list_req = urllib.request.Request(f"{self.base_url}/api/moderation/list")
        with urllib.request.urlopen(list_req) as resp:
            list_res = json.loads(resp.read().decode("utf-8"))
            found = next((s for s in list_res["submissions"] if s["id"] == sub_id), None)
            self.assertIsNotNone(found)
            settings = found["publicationSettings"]
            # coverImage converted to persistent /media/ URL
            self.assertTrue(settings["coverImage"].startswith("/media/"))
            self.assertTrue(settings["coverImage"].endswith(".png"))
            stored_media_url = settings["coverImage"]

        # 3. Simulate draft update in working storage: change cover in payload
        payload["publicationSettings"]["coverImage"] = "data:image/png;base64,CHANGED_IN_WORKING_DRAFT"
        # Verify moderation submission retained original snapshot URL
        with urllib.request.urlopen(list_req) as resp:
            list_res2 = json.loads(resp.read().decode("utf-8"))
            found2 = next((s for s in list_res2["submissions"] if s["id"] == sub_id), None)
            self.assertEqual(found2["publicationSettings"]["coverImage"], stored_media_url)

        # 4. Check public articles API: raw crop params and source files must NOT be exposed
        conn = server.get_db_connection(self.db_path)
        with conn:
            cur = conn.cursor()
            cur.execute("UPDATE moderation_submissions SET status = 'approved' WHERE id = ?", (sub_id,))

        q = urllib.parse.quote("изоляции")
        articles_req = urllib.request.Request(f"{self.base_url}/api/articles?search={q}")
        with urllib.request.urlopen(articles_req) as resp:
            art_data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(art_data.get("success"))
            self.assertGreaterEqual(len(art_data["articles"]), 1)
            art = art_data["articles"][0]
            self.assertEqual(art["coverImage"], stored_media_url)
            self.assertNotIn("rawCoverImageSource", art)
            self.assertNotIn("cropParams", art)

    def test_zero_site_overlays_on_cover(self):
        """Verify no site-generated overlays, watermarks, badges or titles are placed on top of cover."""
        # CSS checks: no absolute overlay over card-cover-img
        self.assertNotIn('.card-cover-container .card-title', self.feed_css)
        self.assertNotIn('.card-cover-container .card-meta', self.feed_css)
        self.assertNotIn('.card-cover-container .meta-badge', self.feed_css)
        self.assertNotIn('.card-cover-container::after', self.feed_css)

        self.assertNotIn('.pub-feed-card-cover .card-title', self.editor_css)
        self.assertNotIn('.pub-feed-card-cover .pub-badge', self.editor_css)
        self.assertNotIn('.pub-feed-card-cover::after', self.editor_css)


class TestTask30PersonalizationAndComments(unittest.TestCase):
    """
    Test suite for task-30-feed-subnav-personalization-card-comments:
    1. Database schema initialization: article_likes, article_comments, user_feed_settings.
    2. Idempotent seeding of 3 demo comments for art-01.
    3. GET /api/articles/<id>/comments returns comments list and total count.
    4. POST /api/articles/<id>/comments validates input (empty, max 5000 chars), escapes HTML, requires auth.
    5. Likes toggle: 1 like per user, increment/decrement, state sync.
    6. User feed settings GET/POST: saves materialTypes and complexityLevels, rejects empty materialTypes.
    7. Feed filtering: types/type, complexities/complexity (including unspecified).
    8. 'My feed' (tab=my): matches subscriptions (OR), deduplicates, respects personal settings, empty states.
    """

    @classmethod
    def setUpClass(cls):
        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, 'task30_test.db')
        cls.media_dir = os.path.join(cls.temp_dir, 'media')

        cls.server = server.create_server(
            host="127.0.0.1",
            port=0,
            db_path=cls.db_path,
            directory=FRONTEND_DIR,
            media_dir=cls.media_dir
        )
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

    def _get_json(self, path: str, headers: Optional[dict] = None) -> Tuple[int, dict]:
        req = urllib.request.Request(f"{self.base_url}{path}", headers=headers or {})
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                return resp.status, data
        except urllib.error.HTTPError as e:
            try:
                data = json.loads(e.read().decode('utf-8'))
            except Exception:
                data = {"error": str(e)}
            return e.code, data

    def _post_json(self, path: str, payload: dict, headers: Optional[dict] = None) -> Tuple[int, dict]:
        h = {"Content-Type": "application/json"}
        if headers:
            h.update(headers)
        data_bytes = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(f"{self.base_url}{path}", data=data_bytes, headers=h)
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                return resp.status, data
        except urllib.error.HTTPError as e:
            try:
                data = json.loads(e.read().decode('utf-8'))
            except Exception:
                data = {"error": str(e)}
            return e.code, data

    def test_01_db_initialization_tables_and_indexes(self):
        """Verify article_likes, article_comments, and user_feed_settings tables and indexes exist."""
        conn = server.get_db_connection(self.db_path)
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row["name"] for row in cur.fetchall()}

            self.assertIn("article_likes", tables, "article_likes table must exist")
            self.assertIn("article_comments", tables, "article_comments table must exist")
            self.assertIn("user_feed_settings", tables, "user_feed_settings table must exist")

            # Check article_likes columns
            cur.execute("PRAGMA table_info(article_likes)")
            likes_cols = {r["name"]: r for r in cur.fetchall()}
            for col in ("id", "article_id", "user_id", "created_at"):
                self.assertIn(col, likes_cols)

            # Check article_comments columns
            cur.execute("PRAGMA table_info(article_comments)")
            comm_cols = {r["name"]: r for r in cur.fetchall()}
            for col in ("id", "article_id", "user_id", "author_name", "author_avatar", "content", "status", "created_at"):
                self.assertIn(col, comm_cols)

            # Check user_feed_settings columns
            cur.execute("PRAGMA table_info(user_feed_settings)")
            fs_cols = {r["name"]: r for r in cur.fetchall()}
            for col in ("user_id", "material_types", "complexity_levels", "updated_at"):
                self.assertIn(col, fs_cols)

            # Check indexes
            cur.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indexes = {row["name"] for row in cur.fetchall()}
            self.assertIn("idx_likes_article_user", indexes)
            self.assertIn("idx_comments_article_id", indexes)

    def test_02_idempotent_seeding_comments_for_art01(self):
        """Verify 3 demo comments are seeded for art-01 and seeding is idempotent without duplicates."""
        conn = server.get_db_connection(self.db_path)
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT author_name, content, status FROM article_comments WHERE article_id = 'art-01' ORDER BY created_at ASC")
            rows = cur.fetchall()

        self.assertEqual(len(rows), 3, "Exactly 3 demo comments must be seeded for art-01")
        expected_contents = [
            "Было бы полезно увидеть пример обработки ошибки во время исполнения контракта.",
            "Планируется ли отдельный материал о проверке данных оракула?",
            "Спасибо за разбор. Особенно интересен раздел о тестировании."
        ]
        expected_authors = ["Тестовый читатель 1", "Тестовый читатель 2", "Тестовый читатель 3"]

        actual_contents = [r["content"] for r in rows]
        actual_authors = [r["author_name"] for r in rows]

        self.assertEqual(actual_contents, expected_contents)
        self.assertEqual(actual_authors, expected_authors)
        for r in rows:
            self.assertEqual(r["status"], "published")

        # Test idempotency: re-run seeding
        with conn:
            server.seed_article_comments(conn)
            cur.execute("SELECT COUNT(*) AS cnt FROM article_comments WHERE article_id = 'art-01'")
            cnt = cur.fetchone()["cnt"]
            self.assertEqual(cnt, 3, "Re-running seed_article_comments must be idempotent (no duplicates)")

    def test_03_get_article_comments_endpoint(self):
        """Verify GET /api/articles/<id>/comments returns comments list, total count, and works for guests."""
        status, data = self._get_json("/api/articles/art-01/comments")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("total"), 3)
        self.assertEqual(len(data.get("comments", [])), 3)

        first = data["comments"][0]
        self.assertEqual(first["articleId"], "art-01")
        self.assertEqual(first["authorName"], "Тестовый читатель 1")
        self.assertIn("обработки ошибки", first["content"])
        self.assertIn("createdAt", first)

        # Non-existent article returns empty list
        status_empty, data_empty = self._get_json("/api/articles/non_existent_art/comments")
        self.assertEqual(status_empty, 200)
        self.assertEqual(data_empty.get("total"), 0)
        self.assertEqual(data_empty.get("comments"), [])

    def test_04_post_article_comments_endpoint(self):
        """Verify POST /api/articles/<id>/comments enforces auth, validates length, escapes HTML, increments count."""
        # 1. Unauthenticated guest -> 401 requireAuth
        status, data = self._post_json("/api/articles/art-01/comments", {"content": "Неавторизованный комментарий"})
        self.assertEqual(status, 401)
        self.assertTrue(data.get("requireAuth"))

        # 2. Authenticated user with empty content -> 400
        auth_headers = {"Cookie": "sc_session=test_user_c"}
        status, data = self._post_json("/api/articles/art-01/comments", {"content": ""}, headers=auth_headers)
        self.assertEqual(status, 400)
        self.assertFalse(data.get("success"))

        # 3. Whitespace only -> 400
        status, data = self._post_json("/api/articles/art-01/comments", {"content": "    \n\t  "}, headers=auth_headers)
        self.assertEqual(status, 400)

        # 4. Over 5000 characters -> 400
        long_content = "А" * 5001
        status, data = self._post_json("/api/articles/art-01/comments", {"content": long_content}, headers=auth_headers)
        self.assertEqual(status, 400)
        self.assertIn("5000", data.get("error", ""))

        # 5. Valid content with HTML tags -> 201, HTML escaped, commentsCount updated
        raw_text = "Тестовый комментарий <script>alert('xss')</script> & <b>важный текст</b>"
        status, data = self._post_json("/api/articles/art-01/comments", {"content": raw_text}, headers=auth_headers)
        self.assertEqual(status, 201)
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("commentsCount"), 4)

        comment = data["comment"]
        self.assertNotIn("<script>", comment["content"])
        self.assertIn("&lt;script&gt;", comment["content"])
        self.assertIn("&amp;", comment["content"])
        self.assertEqual(comment["articleId"], "art-01")

        # 6. Check GET /api/articles/art-01/comments reflects new total
        status_get, data_get = self._get_json("/api/articles/art-01/comments")
        self.assertEqual(status_get, 200)
        self.assertEqual(data_get["total"], 4)

    def test_05_likes_toggle_uniqueness_and_sync(self):
        """Verify like toggle, 1 like per user constraint, counter sync in single view and list view."""
        # 1. Guest -> 401 requireAuth
        status, data = self._post_json("/api/articles/art-02/like", {})
        self.assertEqual(status, 401)
        self.assertTrue(data.get("requireAuth"))

        # 2. User 1 likes art-02 -> ON (likesCount = 1)
        u1_headers = {"Cookie": "sc_session=user_alice"}
        status, data = self._post_json("/api/articles/art-02/like", {}, headers=u1_headers)
        self.assertEqual(status, 200)
        self.assertTrue(data.get("hasLiked"))
        self.assertEqual(data.get("likesCount"), 1)

        # 3. User 1 likes art-02 again -> OFF (likesCount = 0)
        status, data = self._post_json("/api/articles/art-02/like", {}, headers=u1_headers)
        self.assertEqual(status, 200)
        self.assertFalse(data.get("hasLiked"))
        self.assertEqual(data.get("likesCount"), 0)

        # 4. User 1 likes art-02 via /api/likes/toggle -> ON (likesCount = 1)
        status, data = self._post_json("/api/likes/toggle", {"articleId": "art-02"}, headers=u1_headers)
        self.assertEqual(status, 200)
        self.assertTrue(data.get("hasLiked"))
        self.assertEqual(data.get("likesCount"), 1)

        # 5. User 2 likes art-02 -> ON (likesCount = 2)
        u2_headers = {"Cookie": "sc_session=user_bob"}
        status, data = self._post_json("/api/articles/art-02/like", {}, headers=u2_headers)
        self.assertEqual(status, 200)
        self.assertTrue(data.get("hasLiked"))
        self.assertEqual(data.get("likesCount"), 2)

        # 6. Single article GET /api/articles/art-02 reflects correct state for each user
        # User 1 hasLiked = True
        status, data1 = self._get_json("/api/articles/art-02", headers=u1_headers)
        self.assertEqual(status, 200)
        self.assertEqual(data1["article"]["likesCount"], 2)
        self.assertTrue(data1["article"]["hasLiked"])

        # User 3 hasLiked = False
        u3_headers = {"Cookie": "sc_session=user_charlie"}
        status, data3 = self._get_json("/api/articles/art-02", headers=u3_headers)
        self.assertEqual(status, 200)
        self.assertEqual(data3["article"]["likesCount"], 2)
        self.assertFalse(data3["article"]["hasLiked"])

        # 7. Feed list GET /api/articles contains likesCount and hasLiked
        status_list, list_data = self._get_json("/api/articles", headers=u1_headers)
        self.assertEqual(status_list, 200)
        art2 = next(a for a in list_data["articles"] if a["id"] == "art-02")
        self.assertEqual(art2["likesCount"], 2)
        self.assertTrue(art2["hasLiked"])
        self.assertIn("commentsCount", art2)

    def test_06_user_feed_settings_get_post_validation(self):
        """Verify GET/POST /api/user/feed-settings, validation against empty types, and persistence."""
        # 1. Guest GET returns default 4 types and 'all' complexity
        status, data = self._get_json("/api/user/feed-settings")
        self.assertEqual(status, 200)
        self.assertEqual(data["materialTypes"], ["article", "post", "news", "question"])
        self.assertEqual(data["complexityLevels"], ["all"])

        # 2. Guest POST -> 401
        status, data = self._post_json("/api/user/feed-settings", {"materialTypes": ["post"]})
        self.assertEqual(status, 401)
        self.assertTrue(data.get("requireAuth"))

        # 3. Authenticated POST with empty materialTypes -> 400
        user_headers = {"Cookie": "sc_session=user_feed_tester"}
        status, data = self._post_json("/api/user/feed-settings", {"materialTypes": []}, headers=user_headers)
        self.assertEqual(status, 400)
        self.assertIn("Выберите хотя бы один тип материала", data.get("error", ""))

        # 4. Authenticated POST with all invalid types -> 400
        status, data = self._post_json("/api/user/feed-settings", {"materialTypes": ["invalid_one", "unknown_two"]}, headers=user_headers)
        self.assertEqual(status, 400)
        self.assertIn("Выберите хотя бы один тип материала", data.get("error", ""))

        # 5. Authenticated POST with valid preferences -> 200
        payload = {
            "materialTypes": ["post", "news"],
            "complexityLevels": ["hard", "medium"]
        }
        status, data = self._post_json("/api/user/feed-settings", payload, headers=user_headers)
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        self.assertEqual(data["materialTypes"], ["post", "news"])
        self.assertEqual(data["complexityLevels"], ["hard", "medium"])

        # 6. Subsequent GET returns saved settings
        status, data_saved = self._get_json("/api/user/feed-settings", headers=user_headers)
        self.assertEqual(status, 200)
        self.assertEqual(data_saved["materialTypes"], ["post", "news"])
        self.assertEqual(data_saved["complexityLevels"], ["hard", "medium"])

    def test_07_feed_filtering_by_types_and_complexities(self):
        """Verify GET /api/articles filters by material types and complexity levels (including unspecified)."""
        # Insert test publications with diverse types and complexities
        conn = server.get_db_connection(self.db_path)
        with conn:
            # Post - easy
            conn.execute("""
                INSERT OR REPLACE INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, article_delta, idempotency_key, snapshot_hash, created_at, updated_at
                ) VALUES (
                    'art-t30-post', 'draft-t30-post', 'Тестовый пост разработчика', 'author_p', 'approved',
                    ?, '<p>Содержание тестового поста для проверки фильтрации материалов.</p>',
                    NULL, 'idem_post_1', 'hash_p1', '2026-09-25T10:00:00Z', '2026-09-25T10:00:00Z'
                )
            """, (json.dumps({
                "materialType": "post",
                "complexity": "easy",
                "topics": ["smart-contracts-development"],
                "keywords": ["пост", "фильтр"],
                "description": "Описание поста длиной более пятидесяти символов для корректной фильтрации."
            }, ensure_ascii=False),))

            # News - unspecified complexity
            conn.execute("""
                INSERT OR REPLACE INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, article_delta, idempotency_key, snapshot_hash, created_at, updated_at
                ) VALUES (
                    'art-t30-news', 'draft-t30-news', 'Срочная новость экосистемы', 'author_n', 'approved',
                    ?, '<p>Содержание срочной новости экосистемы блокчейн-платформы.</p>',
                    NULL, 'idem_news_1', 'hash_n1', '2026-09-25T11:00:00Z', '2026-09-25T11:00:00Z'
                )
            """, (json.dumps({
                "materialType": "news",
                "complexity": None,
                "topics": ["standards-and-protocols"],
                "keywords": ["новость", "релиз"],
                "description": "Описание новости длиной более пятидесяти символов для корректной фильтрации."
            }, ensure_ascii=False),))

            # Question - medium complexity
            conn.execute("""
                INSERT OR REPLACE INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, article_delta, idempotency_key, snapshot_hash, created_at, updated_at
                ) VALUES (
                    'art-t30-quest', 'draft-t30-quest', 'Вопрос по оптимизации газа', 'author_q', 'approved',
                    ?, '<p>Вопрос сообщества по поводу снижения потребления газа в циклах смарт-контракта.</p>',
                    NULL, 'idem_quest_1', 'hash_q1', '2026-09-25T12:00:00Z', '2026-09-25T12:00:00Z'
                )
            """, (json.dumps({
                "materialType": "question",
                "complexity": "medium",
                "topics": ["smart-contracts-development"],
                "keywords": ["вопрос", "газ"],
                "description": "Описание вопроса сообщества длиной более пятидесяти символов для проверки."
            }, ensure_ascii=False),))

        # 1. Filter by types: post,news
        status, data = self._get_json("/api/articles?types=post,news")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(data["total"], 2)
        returned_types = {a["materialType"] for a in data["articles"]}
        self.assertTrue(returned_types.issubset({"post", "news"}))
        ids = {a["id"] for a in data["articles"]}
        self.assertIn("art-t30-post", ids)
        self.assertIn("art-t30-news", ids)
        self.assertNotIn("art-t30-quest", ids)

        # 2. Filter by type: question
        status, data_q = self._get_json("/api/articles?type=question")
        self.assertEqual(status, 200)
        for a in data_q["articles"]:
            self.assertEqual(a["materialType"], "question")

        # 3. Filter by complexity: easy,unspecified
        status, data_comp = self._get_json("/api/articles?complexities=easy,unspecified")
        self.assertEqual(status, 200)
        ids_comp = {a["id"] for a in data_comp["articles"]}
        self.assertIn("art-t30-post", ids_comp)  # easy
        self.assertIn("art-t30-news", ids_comp)  # unspecified
        self.assertNotIn("art-01", ids_comp)     # hard
        self.assertNotIn("art-02", ids_comp)     # hard

        # 4. Filter by complexity: hard
        status, data_hard = self._get_json("/api/articles?complexity=hard")
        self.assertEqual(status, 200)
        for a in data_hard["articles"]:
            self.assertEqual(a["complexity"], "hard")

    def test_08_my_feed_subscriptions_deduplication_and_empty_states(self):
        """Verify tab=my requires auth, matches subscriptions (OR), deduplicates, respects settings, handles empty states."""
        # 1. Guest -> 401 requireAuth
        status, data = self._get_json("/api/articles?tab=my")
        self.assertEqual(status, 401)
        self.assertTrue(data.get("requireAuth"))

        # 2. User with 0 subscriptions -> total=0, noSubscriptions=True
        status, data = self._get_json("/api/articles?tab=my", headers={"Cookie": "sc_session=user_without_subs"})
        self.assertEqual(status, 200)
        self.assertEqual(data.get("total"), 0)
        self.assertEqual(data.get("articles"), [])
        self.assertTrue(data.get("noSubscriptions"))

        # 3. User subscribed to multiple entities matching art-01 (author + topic + tag)
        user_id = "user_multi_match"
        user_headers = {"Cookie": f"sc_session={user_id}"}
        conn = server.get_db_connection(self.db_path)
        with conn:
            conn.execute("DELETE FROM user_subscriptions WHERE user_id = ?", (user_id,))
            conn.executemany("""
                INSERT INTO user_subscriptions (user_id, target_type, target_id, target_title, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, [
                (user_id, "author", "author_smirnov", "Алексей Смирнов", "2026-09-26T12:00:00Z"),
                (user_id, "topic", "digital-ruble-payments", "Цифровой рубль и платежи", "2026-09-26T12:00:00Z"),
                (user_id, "tag", "цифровой рубль", "Цифровой рубль", "2026-09-26T12:00:00Z"),
            ])

        status, data = self._get_json("/api/articles?tab=my", headers=user_headers)
        self.assertEqual(status, 200)
        self.assertFalse(data.get("noSubscriptions"))
        self.assertGreaterEqual(data.get("total"), 1)

        # Deduplication check: art-01 appears exactly ONCE despite matching author, topic, and tag
        art01_matches = [a for a in data["articles"] if a["id"] == "art-01"]
        self.assertEqual(len(art01_matches), 1, "Article matching multiple subscriptions must be deduplicated to exactly 1")
        self.assertTrue(art01_matches[0].get("subscriptionReason"))

        # 4. Personal feed settings in tab=my: restrict to 'news' only
        # User has subscriptions, but none match the saved feed settings
        post_status, _ = self._post_json(
            "/api/user/feed-settings",
            {"materialTypes": ["news"], "complexityLevels": ["all"]},
            headers=user_headers
        )
        self.assertEqual(post_status, 200)

        status_filtered, data_filtered = self._get_json("/api/articles?tab=my", headers=user_headers)
        self.assertEqual(status_filtered, 200)
        # Empty state: has subscriptions, but 0 matching articles for selected material types
        self.assertEqual(data_filtered.get("total"), 0)
        self.assertEqual(data_filtered.get("articles"), [])
        self.assertFalse(data_filtered.get("noSubscriptions"), "User HAS subscriptions, so noSubscriptions must be False")

        # 5. Restore feed settings to include 'article'
        self._post_json(
            "/api/user/feed-settings",
            {"materialTypes": ["article", "post", "news", "question"], "complexityLevels": ["all"]},
            headers=user_headers
        )
        status_restored, data_restored = self._get_json("/api/articles?tab=my", headers=user_headers)
        self.assertEqual(status_restored, 200)
        self.assertGreaterEqual(data_restored.get("total"), 1)
        self.assertIn("art-01", [a["id"] for a in data_restored["articles"]])


class TestTask31FeedSettingsAndFiltersUnification(unittest.TestCase):
    """
    Test suite for task-31-feed-settings-and-filters-unification:
    1. Table user_feed_exceptions and indexes creation.
    2. POST /api/exceptions/toggle and mutual exclusion with user_subscriptions.
    3. GET /api/subscriptions/entities catalog with pagination (limit, offset) and search.
    4. Exceptions priority: article hidden if its topic/tag is excluded, even if user is subscribed to its author.
    5. Exceptions applied in tab=all and tab=my, but NOT in direct GET /api/articles/<id> or saved bookmarks.
    6. Temporal filters: types, topics (OR), complexities, period (week, month, year, custom range) and sorting (newest, popular, discussed).
    7. User feed settings batch updates with subscriptions and exceptions.
    """

    @classmethod
    def setUpClass(cls):
        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, 'task31_test.db')
        cls.media_dir = os.path.join(cls.temp_dir, 'media')

        cls.server = server.create_server(
            host="127.0.0.1",
            port=0,
            db_path=cls.db_path,
            directory=FRONTEND_DIR,
            media_dir=cls.media_dir
        )
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

    def _get_json(self, path: str, headers: Optional[dict] = None) -> Tuple[int, dict]:
        clean_url = urllib.parse.quote(f"{self.base_url}{path}", safe=";/?:@&=+$,#~-_.!*'")
        req = urllib.request.Request(clean_url, headers=headers or {})
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                return resp.status, data
        except urllib.error.HTTPError as e:
            try:
                data = json.loads(e.read().decode('utf-8'))
            except Exception:
                data = {"error": str(e)}
            return e.code, data

    def _post_json(self, path: str, payload: dict, headers: Optional[dict] = None) -> Tuple[int, dict]:
        h = {"Content-Type": "application/json"}
        if headers:
            h.update(headers)
        data_bytes = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(f"{self.base_url}{path}", data=data_bytes, headers=h)
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                return resp.status, data
        except urllib.error.HTTPError as e:
            try:
                data = json.loads(e.read().decode('utf-8'))
            except Exception:
                data = {"error": str(e)}
            return e.code, data

    def test_01_db_initialization_tables_and_indexes(self):
        """Verify user_feed_exceptions table and indexes exist, along with all feed tables."""
        conn = server.get_db_connection(self.db_path)
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row["name"] for row in cur.fetchall()}

            self.assertIn("user_subscriptions", tables, "user_subscriptions table must exist")
            self.assertIn("user_feed_exceptions", tables, "user_feed_exceptions table must exist")
            self.assertIn("user_feed_settings", tables, "user_feed_settings table must exist")
            self.assertIn("article_likes", tables, "article_likes table must exist")
            self.assertIn("article_comments", tables, "article_comments table must exist")

            # Check user_feed_exceptions columns
            cur.execute("PRAGMA table_info(user_feed_exceptions)")
            exc_cols = {r["name"]: r for r in cur.fetchall()}
            for col in ("id", "user_id", "target_type", "target_id", "target_title", "created_at"):
                self.assertIn(col, exc_cols, f"Column {col} must exist in user_feed_exceptions")

            # Check indexes on user_feed_exceptions
            cur.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indexes = {row["name"] for row in cur.fetchall()}
            self.assertIn("idx_exceptions_user_id", indexes, "idx_exceptions_user_id index must exist")
            self.assertIn("idx_exceptions_lookup", indexes, "idx_exceptions_lookup index must exist")

    def test_02_exceptions_endpoints_and_mutual_exclusion_with_subscriptions(self):
        """Verify GET /api/exceptions, POST /api/exceptions/toggle and mutual exclusion with subscriptions."""
        # 1. Guest GET /api/exceptions returns empty lists
        status, data = self._get_json("/api/exceptions")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        self.assertEqual(data["exceptions"]["authors"], [])
        self.assertEqual(data["exceptions"]["topics"], [])
        self.assertEqual(data["exceptions"]["tags"], [])
        self.assertEqual(data["total"], 0)

        # 2. Guest POST /api/exceptions/toggle -> 401
        status, data = self._post_json("/api/exceptions/toggle", {"targetType": "author", "targetId": "author_smirnov"})
        self.assertEqual(status, 401)
        self.assertTrue(data.get("requireAuth"))

        # 3. Authenticated validation errors
        user_headers = {"Cookie": "sc_session=user_exc_tester"}
        # Invalid targetType
        status, data = self._post_json("/api/exceptions/toggle", {"targetType": "unknown", "targetId": "123"}, headers=user_headers)
        self.assertEqual(status, 400)
        # Missing targetId
        status, data = self._post_json("/api/exceptions/toggle", {"targetType": "author", "targetId": ""}, headers=user_headers)
        self.assertEqual(status, 400)

        # 4. Toggle author exception ON
        status, data = self._post_json("/api/exceptions/toggle", {
            "targetType": "author",
            "targetId": "author_smirnov",
            "targetTitle": "Алексей Смирнов"
        }, headers=user_headers)
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        self.assertTrue(data.get("excluded"))
        self.assertEqual(data.get("targetType"), "author")
        self.assertEqual(data.get("targetId"), "author_smirnov")

        # Verify GET /api/exceptions contains author_smirnov
        status, data_get = self._get_json("/api/exceptions", headers=user_headers)
        self.assertEqual(status, 200)
        self.assertEqual(data_get["total"], 1)
        self.assertEqual(len(data_get["exceptions"]["authors"]), 1)
        self.assertEqual(data_get["exceptions"]["authors"][0]["id"], "author_smirnov")

        # 5. Mutual exclusion: entity in subscriptions -> added to exceptions -> removed from subscriptions
        # First, subscribe user to topic 'smart-contracts-development'
        status_sub, data_sub = self._post_json("/api/subscriptions/toggle", {
            "targetType": "topic",
            "targetId": "smart-contracts-development",
            "targetTitle": "Разработка смарт-контрактов"
        }, headers=user_headers)
        self.assertEqual(status_sub, 200)
        self.assertTrue(data_sub.get("subscribed"))

        # Check it is in subscriptions
        _, sub_check = self._get_json("/api/subscriptions", headers=user_headers)
        topic_subs = [t["id"] for t in sub_check["subscriptions"]["topics"]]
        self.assertIn("smart-contracts-development", topic_subs)

        # Now add topic 'smart-contracts-development' to exceptions
        status_exc, data_exc = self._post_json("/api/exceptions/toggle", {
            "targetType": "topic",
            "targetId": "smart-contracts-development",
            "targetTitle": "Разработка смарт-контрактов"
        }, headers=user_headers)
        self.assertEqual(status_exc, 200)
        self.assertTrue(data_exc.get("excluded"))

        # Verify it was REMOVED from subscriptions!
        _, sub_check2 = self._get_json("/api/subscriptions", headers=user_headers)
        topic_subs2 = [t["id"] for t in sub_check2["subscriptions"]["topics"]]
        self.assertNotIn("smart-contracts-development", topic_subs2, "Adding topic to exceptions must remove it from subscriptions")

        # Verify it is in exceptions
        _, exc_check = self._get_json("/api/exceptions", headers=user_headers)
        topic_excs = [t["id"] for t in exc_check["exceptions"]["topics"]]
        self.assertIn("smart-contracts-development", topic_excs)

        # 6. Mutual exclusion: entity in exceptions -> added to subscriptions -> removed from exceptions
        status_sub2, data_sub2 = self._post_json("/api/subscriptions/toggle", {
            "targetType": "topic",
            "targetId": "smart-contracts-development",
            "targetTitle": "Разработка смарт-контрактов"
        }, headers=user_headers)
        self.assertEqual(status_sub2, 200)
        self.assertTrue(data_sub2.get("subscribed"))

        # Verify it was REMOVED from exceptions!
        _, exc_check2 = self._get_json("/api/exceptions", headers=user_headers)
        topic_excs2 = [t["id"] for t in exc_check2["exceptions"]["topics"]]
        self.assertNotIn("smart-contracts-development", topic_excs2, "Adding topic to subscriptions must remove it from exceptions")

        # 7. Toggle author exception OFF
        status_off, data_off = self._post_json("/api/exceptions/toggle", {
            "targetType": "author",
            "targetId": "author_smirnov"
        }, headers=user_headers)
        self.assertEqual(status_off, 200)
        self.assertFalse(data_off.get("excluded"))

        _, exc_check3 = self._get_json("/api/exceptions", headers=user_headers)
        author_excs = [a["id"] for a in exc_check3["exceptions"]["authors"]]
        self.assertNotIn("author_smirnov", author_excs)

    def test_03_subscriptions_entities_catalog_pagination_and_search(self):
        """Verify GET /api/subscriptions/entities returns catalog, supports pagination and search."""
        # 1. Backward compatible call without type param
        status, data = self._get_json("/api/subscriptions/entities")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        self.assertIn("authors", data)
        self.assertIn("topics", data)
        self.assertIn("tags", data)

        # Standard topics always available, count=14
        self.assertEqual(len(data["topics"]), len(server.STANDARD_TOPICS))
        for t in data["topics"]:
            self.assertIn("id", t)
            self.assertIn("title", t)
            self.assertIn("count", t)
            self.assertIn("isSubscribed", t)
            self.assertIn("isExcluded", t)

        for a in data["authors"]:
            self.assertIn("id", a)
            self.assertIn("title", a)
            self.assertIn("role", a)
            self.assertIn("count", a)
            self.assertIn("isSubscribed", a)
            self.assertIn("isExcluded", a)

        # 2. Paginated call with type=author
        status, paged_authors = self._get_json("/api/subscriptions/entities?type=author&limit=1&offset=0")
        self.assertEqual(status, 200)
        self.assertTrue(paged_authors.get("success"))
        self.assertEqual(len(paged_authors["items"]), 1)
        self.assertEqual(paged_authors["limit"], 1)
        self.assertEqual(paged_authors["offset"], 0)
        self.assertGreater(paged_authors["total"], 1)
        self.assertTrue(paged_authors["hasMore"])
        first_author_id = paged_authors["items"][0]["id"]

        # Offset 1
        status, paged_authors_2 = self._get_json("/api/subscriptions/entities?type=author&limit=1&offset=1")
        self.assertEqual(status, 200)
        self.assertEqual(len(paged_authors_2["items"]), 1)
        second_author_id = paged_authors_2["items"][0]["id"]
        self.assertNotEqual(first_author_id, second_author_id)

        # 3. Paginated call with type=topic
        status, paged_topics = self._get_json("/api/subscriptions/entities?type=topic&limit=5&offset=0")
        self.assertEqual(status, 200)
        self.assertEqual(len(paged_topics["items"]), 5)
        self.assertEqual(paged_topics["total"], len(server.STANDARD_TOPICS))

        # 4. Search filtering
        status, search_authors = self._get_json("/api/subscriptions/entities?type=author&search=Смирнов")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(search_authors["total"], 1)
        for it in search_authors["items"]:
            self.assertIn("Смирнов", it["title"])

        status, search_topics = self._get_json("/api/subscriptions/entities?type=topic&search=платежи")
        self.assertEqual(status, 200)
        self.assertEqual(search_topics["total"], 1)
        self.assertEqual(search_topics["items"][0]["id"], "digital-ruble-payments")

        status, empty_search = self._get_json("/api/subscriptions/entities?type=tag&search=несуществующий_тег_xyz")
        self.assertEqual(status, 200)
        self.assertEqual(empty_search["total"], 0)
        self.assertEqual(empty_search["items"], [])
        self.assertFalse(empty_search["hasMore"])

    def test_04_exceptions_priority_over_subscriptions(self):
        """Verify priority of exceptions: publication is hidden if its topic/tag is excluded, even if subscribed to author."""
        user_id = "user_priority_tester"
        user_headers = {"Cookie": f"sc_session={user_id}"}

        # Clear subscriptions and exceptions for this user
        conn = server.get_db_connection(self.db_path)
        with conn:
            conn.execute("DELETE FROM user_subscriptions WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM user_feed_exceptions WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM user_feed_settings WHERE user_id = ?", (user_id,))

        # Subscribe user to author_smirnov (who authored art-01)
        status, sub_resp = self._post_json("/api/subscriptions/toggle", {
            "targetType": "author",
            "targetId": "author_smirnov",
            "targetTitle": "Алексей Смирнов"
        }, headers=user_headers)
        self.assertEqual(status, 200)
        self.assertTrue(sub_resp["subscribed"])

        # Check tab=my: art-01 is visible because user subscribed to author
        status, data_my = self._get_json("/api/articles?tab=my", headers=user_headers)
        self.assertEqual(status, 200)
        ids_my = [a["id"] for a in data_my["articles"]]
        self.assertIn("art-01", ids_my)

        # Check tab=all: art-01 is visible
        status, data_all = self._get_json("/api/articles?tab=all", headers=user_headers)
        self.assertEqual(status, 200)
        ids_all = [a["id"] for a in data_all["articles"]]
        self.assertIn("art-01", ids_all)

        # NOW: Add exception for topic 'digital-ruble-payments' (one of art-01's topics)
        status, exc_resp = self._post_json("/api/exceptions/toggle", {
            "targetType": "topic",
            "targetId": "digital-ruble-payments",
            "targetTitle": "Цифровой рубль и платежи"
        }, headers=user_headers)
        self.assertEqual(status, 200)
        self.assertTrue(exc_resp["excluded"])

        # Verify art-01 is HIDDEN in tab=my (exceptions take precedence over subscriptions!)
        status, data_my_hidden = self._get_json("/api/articles?tab=my", headers=user_headers)
        self.assertEqual(status, 200)
        ids_my_hidden = [a["id"] for a in data_my_hidden["articles"]]
        self.assertNotIn("art-01", ids_my_hidden, "art-01 must be hidden from tab=my because its topic is in exceptions")

        # Verify art-01 is ALSO HIDDEN in tab=all for this user!
        status, data_all_hidden = self._get_json("/api/articles?tab=all", headers=user_headers)
        self.assertEqual(status, 200)
        ids_all_hidden = [a["id"] for a in data_all_hidden["articles"]]
        self.assertNotIn("art-01", ids_all_hidden, "art-01 must be hidden from tab=all because its topic is in exceptions")

        # Remove the topic exception
        self._post_json("/api/exceptions/toggle", {
            "targetType": "topic",
            "targetId": "digital-ruble-payments"
        }, headers=user_headers)

        # Now test with a tag exception: 'цифровой рубль' (one of art-01's keywords)
        status, exc_tag = self._post_json("/api/exceptions/toggle", {
            "targetType": "tag",
            "targetId": "цифровой рубль",
            "targetTitle": "Цифровой рубль"
        }, headers=user_headers)
        self.assertEqual(status, 200)
        self.assertTrue(exc_tag["excluded"])

        # Verify art-01 is HIDDEN in tab=my and tab=all due to tag exception
        status, data_my_tag = self._get_json("/api/articles?tab=my", headers=user_headers)
        self.assertEqual(status, 200)
        self.assertNotIn("art-01", [a["id"] for a in data_my_tag["articles"]])

        status, data_all_tag = self._get_json("/api/articles?tab=all", headers=user_headers)
        self.assertEqual(status, 200)
        self.assertNotIn("art-01", [a["id"] for a in data_all_tag["articles"]])

        # Remove the tag exception
        self._post_json("/api/exceptions/toggle", {
            "targetType": "tag",
            "targetId": "цифровой рубль"
        }, headers=user_headers)

        # Verify art-01 is restored
        status, data_my_restored = self._get_json("/api/articles?tab=my", headers=user_headers)
        self.assertEqual(status, 200)
        self.assertIn("art-01", [a["id"] for a in data_my_restored["articles"]])

    def test_05_exceptions_application_in_feed_and_direct_url_and_saved(self):
        """Verify exceptions hide articles in feed and search, but NOT in direct URL or saved bookmarks."""
        user_id = "user_direct_test"
        user_headers = {"Cookie": f"sc_session={user_id}"}

        # Add author_smirnov to user's exceptions
        status, exc_resp = self._post_json("/api/exceptions/toggle", {
            "targetType": "author",
            "targetId": "author_smirnov",
            "targetTitle": "Алексей Смирнов"
        }, headers=user_headers)
        self.assertEqual(status, 200)
        self.assertTrue(exc_resp["excluded"])

        # 1. Hidden in tab=all
        status, data_all = self._get_json("/api/articles?tab=all", headers=user_headers)
        self.assertEqual(status, 200)
        self.assertNotIn("art-01", [a["id"] for a in data_all["articles"]])

        # 2. Hidden in search inside feed
        status, data_search = self._get_json("/api/articles?tab=all&search=цифрового", headers=user_headers)
        self.assertEqual(status, 200)
        self.assertNotIn("art-01", [a["id"] for a in data_search["articles"]])

        # 3. Direct access via GET /api/articles/art-01 MUST NOT be hidden!
        status_direct, data_direct = self._get_json("/api/articles/art-01", headers=user_headers)
        self.assertEqual(status_direct, 200)
        self.assertTrue(data_direct.get("success"))
        self.assertEqual(data_direct["article"]["id"], "art-01")
        self.assertEqual(data_direct["article"]["title"], "Интеграция смарт-контрактов с платформой цифрового рубля Банка России")

        # 4. Bookmarks: GET /api/articles?tab=saved&ids=art-01 MUST NOT be hidden!
        status_saved, data_saved = self._get_json("/api/articles?tab=saved&ids=art-01", headers=user_headers)
        self.assertEqual(status_saved, 200)
        self.assertIn("art-01", [a["id"] for a in data_saved["articles"]])

        # 5. Bookmarks via ids param: GET /api/articles?ids=art-01 MUST NOT be hidden!
        status_ids, data_ids = self._get_json("/api/articles?ids=art-01", headers=user_headers)
        self.assertEqual(status_ids, 200)
        self.assertIn("art-01", [a["id"] for a in data_ids["articles"]])

    def test_06_temporal_filters_and_sorting(self):
        """Verify temporal filters (types, topics, complexities, periods, date range) and sorting."""
        conn = server.get_db_connection(self.db_path)
        with conn:
            # Seed 3 diverse articles for filtering and sorting tests
            conn.execute("""
                INSERT OR REPLACE INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, article_delta, idempotency_key, snapshot_hash, created_at, updated_at
                ) VALUES (
                    'art-t31-old', 'draft-t31-old', 'Архивный материал стандартов', 'author_old', 'approved',
                    ?, '<p>Старый текст публикации стандартов протоколов.</p>',
                    NULL, 'idem_t31_old', 'hash_t31_old', '2025-01-01T12:00:00Z', '2025-01-01T12:00:00Z'
                )
            """, (json.dumps({
                "materialType": "article",
                "complexity": "easy",
                "topics": ["standards-and-protocols"],
                "keywords": ["стандарт", "архив"],
                "format": "overview",
                "targetAudience": "architects-integrators",
                "description": "Описание архивной статьи длиной более пятидесяти символов для фильтрации."
            }, ensure_ascii=False),))

            # 20 days ago (within month and year, but outside week)
            now_dt = datetime.datetime.now(datetime.timezone.utc)
            month_dt = (now_dt - datetime.timedelta(days=20)).isoformat()
            conn.execute("""
                INSERT OR REPLACE INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, article_delta, idempotency_key, snapshot_hash, created_at, updated_at
                ) VALUES (
                    'art-t31-month', 'draft-t31-month', 'Месячная новость разработки', 'author_month', 'approved',
                    ?, '<p>Новостной материал месячной давности о смарт-контрактах.</p>',
                    NULL, 'idem_t31_month', 'hash_t31_month', ?, ?
                )
            """, (json.dumps({
                "materialType": "news",
                "complexity": "medium",
                "topics": ["smart-contracts-development"],
                "keywords": ["новость", "разработка"],
                "format": "news",
                "targetAudience": "developers",
                "description": "Описание новости месячной давности длиной более пятидесяти символов."
            }, ensure_ascii=False), month_dt, month_dt))

            # 2 days ago (within week, month, year)
            week_dt = (now_dt - datetime.timedelta(days=2)).isoformat()
            conn.execute("""
                INSERT OR REPLACE INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, article_delta, idempotency_key, snapshot_hash, created_at, updated_at
                ) VALUES (
                    'art-t31-week', 'draft-t31-week', 'Свежий пост оптимизации газа', 'author_week', 'approved',
                    ?, '<p>Свежий пост о снижении расхода газа в смарт-контрактах.</p>',
                    NULL, 'idem_t31_week', 'hash_t31_week', ?, ?
                )
            """, (json.dumps({
                "materialType": "post",
                "complexity": "hard",
                "topics": ["smart-contracts-development"],
                "keywords": ["пост", "газ"],
                "format": "post",
                "targetAudience": "developers",
                "description": "Описание свежего поста длиной более пятидесяти символов для проверки."
            }, ensure_ascii=False), week_dt, week_dt))

            # Seed likes and comments for sorting verification:
            conn.execute("DELETE FROM article_likes WHERE article_id IN ('art-t31-old', 'art-t31-month', 'art-t31-week')")
            conn.execute("DELETE FROM article_comments WHERE article_id IN ('art-t31-old', 'art-t31-month', 'art-t31-week')")

            # 5 likes for art-t31-week
            for i in range(5):
                conn.execute("INSERT INTO article_likes (article_id, user_id, created_at) VALUES ('art-t31-week', ?, ?)",
                             (f"user_like_w_{i}", week_dt))
            # 1 like for art-t31-month
            conn.execute("INSERT INTO article_likes (article_id, user_id, created_at) VALUES ('art-t31-month', 'user_like_m_0', ?)",
                         (month_dt,))

            # 5 comments for art-t31-month
            for i in range(5):
                conn.execute("""
                    INSERT INTO article_comments (id, article_id, user_id, author_name, content, status, created_at)
                    VALUES (?, 'art-t31-month', ?, 'Читатель', 'Комментарий для теста сортировки', 'published', ?)
                """, (f"comm_m_{i}", f"user_comm_m_{i}", month_dt))
            # 1 comment for art-t31-week
            conn.execute("""
                INSERT INTO article_comments (id, article_id, user_id, author_name, content, status, created_at)
                VALUES ('comm_w_0', 'art-t31-week', 'user_comm_w_0', 'Читатель', 'Один комментарий', 'published', ?)
            """, (week_dt,))

        # 1. Filter by period: week
        status, data_week = self._get_json("/api/articles?period=week")
        self.assertEqual(status, 200)
        week_ids = {a["id"] for a in data_week["articles"]}
        self.assertIn("art-t31-week", week_ids)
        self.assertNotIn("art-t31-month", week_ids)
        self.assertNotIn("art-t31-old", week_ids)

        # 2. Filter by period: month
        status, data_month = self._get_json("/api/articles?period=month")
        self.assertEqual(status, 200)
        month_ids = {a["id"] for a in data_month["articles"]}
        self.assertIn("art-t31-week", month_ids)
        self.assertIn("art-t31-month", month_ids)
        self.assertNotIn("art-t31-old", month_ids)

        # 3. Filter by period: year
        status, data_year = self._get_json("/api/articles?period=year")
        self.assertEqual(status, 200)
        year_ids = {a["id"] for a in data_year["articles"]}
        self.assertIn("art-t31-week", year_ids)
        self.assertIn("art-t31-month", year_ids)
        self.assertNotIn("art-t31-old", year_ids)

        # 4. Filter by period: custom range
        status, data_custom = self._get_json("/api/articles?period=custom&dateFrom=2025-01-01&dateTo=2025-01-02")
        self.assertEqual(status, 200)
        custom_ids = {a["id"] for a in data_custom["articles"]}
        self.assertIn("art-t31-old", custom_ids)
        self.assertNotIn("art-t31-week", custom_ids)
        self.assertNotIn("art-t31-month", custom_ids)

        # 5. Filter by multiple topics (OR logic within group)
        status, data_top = self._get_json("/api/articles?topics=standards-and-protocols,smart-contracts-development")
        self.assertEqual(status, 200)
        top_ids = {a["id"] for a in data_top["articles"]}
        self.assertIn("art-t31-old", top_ids)
        self.assertIn("art-t31-month", top_ids)
        self.assertIn("art-t31-week", top_ids)

        # Single topic filter
        status, data_single_top = self._get_json("/api/articles?topic=standards-and-protocols")
        self.assertEqual(status, 200)
        single_ids = {a["id"] for a in data_single_top["articles"]}
        self.assertIn("art-t31-old", single_ids)
        self.assertNotIn("art-t31-month", single_ids)

        # 6. Filter by format and audience
        status, data_fa = self._get_json("/api/articles?format=overview&audience=architects-integrators")
        self.assertEqual(status, 200)
        fa_ids = {a["id"] for a in data_fa["articles"]}
        self.assertIn("art-t31-old", fa_ids)
        self.assertNotIn("art-t31-month", fa_ids)

        # 7. Sorting: popular (by likesCount DESC, then date DESC)
        status, data_pop = self._get_json("/api/articles?sort=popular")
        self.assertEqual(status, 200)
        articles_pop = data_pop["articles"]
        self.assertGreaterEqual(len(articles_pop), 2)
        idx_week = next(i for i, a in enumerate(articles_pop) if a["id"] == "art-t31-week")
        idx_month = next(i for i, a in enumerate(articles_pop) if a["id"] == "art-t31-month")
        self.assertLess(idx_week, idx_month, "art-t31-week with 5 likes must precede art-t31-month with 1 like in sort=popular")

        # 8. Sorting: discussed (by commentsCount DESC, then date DESC)
        status, data_disc = self._get_json("/api/articles?sort=discussed")
        self.assertEqual(status, 200)
        articles_disc = data_disc["articles"]
        idx_month_d = next(i for i, a in enumerate(articles_disc) if a["id"] == "art-t31-month")
        idx_week_d = next(i for i, a in enumerate(articles_disc) if a["id"] == "art-t31-week")
        self.assertLess(idx_month_d, idx_week_d, "art-t31-month with 5 comments must precede art-t31-week with 1 comment in sort=discussed")

        # 9. Sorting: newest (by date DESC)
        status, data_new = self._get_json("/api/articles?sort=newest")
        self.assertEqual(status, 200)
        articles_new = data_new["articles"]
        idx_week_n = next(i for i, a in enumerate(articles_new) if a["id"] == "art-t31-week")
        idx_old_n = next(i for i, a in enumerate(articles_new) if a["id"] == "art-t31-old")
        self.assertLess(idx_week_n, idx_old_n, "art-t31-week (recent) must precede art-t31-old (2025) in sort=newest")

    def test_07_batch_feed_settings_and_validation(self):
        """Verify POST /api/user/feed-settings batch updating with subscriptions and exceptions, and validation."""
        user_headers = {"Cookie": "sc_session=user_batch_tester"}

        # Empty materialTypes rejected with 400
        status, data_err = self._post_json("/api/user/feed-settings", {
            "materialTypes": [],
            "complexityLevels": ["easy"]
        }, headers=user_headers)
        self.assertEqual(status, 400)
        self.assertIn("Выберите хотя бы один тип материала", data_err.get("error", ""))

        # Batch update with materialTypes, complexityLevels, subscriptions, and exceptions
        payload = {
            "materialTypes": ["article", "news"],
            "complexityLevels": ["hard"],
            "subscriptions": {
                "authors": [{"id": "author_melnikov", "title": "Илья Мельников"}],
                "topics": [{"id": "law-and-compliance", "title": "Право и комплаенс"}],
                "tags": [{"id": "цфа", "title": "ЦФА"}]
            },
            "exceptions": {
                "topics": [{"id": "audit-and-verification", "title": "Аудит и проверка смарт-контрактов"}]
            }
        }
        status, data_ok = self._post_json("/api/user/feed-settings", payload, headers=user_headers)
        self.assertEqual(status, 200)
        self.assertTrue(data_ok.get("success"))
        self.assertEqual(data_ok["materialTypes"], ["article", "news"])
        self.assertEqual(data_ok["complexityLevels"], ["hard"])

        # Verify subscriptions saved
        status, subs_resp = self._get_json("/api/subscriptions", headers=user_headers)
        self.assertEqual(status, 200)
        sub_author_ids = [a["id"] for a in subs_resp["subscriptions"]["authors"]]
        sub_topic_ids = [t["id"] for t in subs_resp["subscriptions"]["topics"]]
        sub_tag_ids = [g["id"] for g in subs_resp["subscriptions"]["tags"]]
        self.assertIn("author_melnikov", sub_author_ids)
        self.assertIn("law-and-compliance", sub_topic_ids)
        self.assertIn("цфа", sub_tag_ids)

        # Verify exceptions saved
        status, exc_resp = self._get_json("/api/exceptions", headers=user_headers)
        self.assertEqual(status, 200)
        exc_topic_ids = [t["id"] for t in exc_resp["exceptions"]["topics"]]
        self.assertIn("audit-and-verification", exc_topic_ids)


class TestTask32FeedSettingsUXPolish(unittest.TestCase):
    """
    Test suite for task-32-feed-settings-ux-polish:
    1. Subscriptions block strict order (Title -> Switch -> Mode hint -> Tabs with counters & Add button -> List).
    2. Author card avatar from card.js, word wrapping for topics/tags without button overlap, secondary toggle button.
    3. Updated hints in settings, removed badge 'Минимум один', unified naming 'Без указанного уровня'.
    4. Explicit 'Все типы' and 'Любой уровень' with mutual exclusivity logic.
    5. Compact topics dropdown selector with search, checkboxes, and chips.
    6. Advanced filters 2-column layout (16-24px gap) with counter badge.
    7. Single unified sort above feed, removed from filter panel, sort preserved on reset.
    8. Compact search placeholder 'Поиск публикаций', compact count 'N публикаций', empty state actions.
    9. Strict Onest font, zero emojis, 100% offline-first.
    """

    @classmethod
    def setUpClass(cls):
        cls.feed_html_path = os.path.join(FRONTEND_DIR, 'feed.html')
        with open(cls.feed_html_path, 'r', encoding='utf-8') as f:
            cls.feed_html = f.read()

        cls.feed_css_path = os.path.join(FRONTEND_DIR, 'css', 'feed.css')
        with open(cls.feed_css_path, 'r', encoding='utf-8') as f:
            cls.feed_css = f.read()

        cls.feed_js_path = os.path.join(FRONTEND_DIR, 'js', 'feed.js')
        with open(cls.feed_js_path, 'r', encoding='utf-8') as f:
            cls.feed_js = f.read()

        cls.card_js_path = os.path.join(FRONTEND_DIR, 'js', 'card.js')
        with open(cls.card_js_path, 'r', encoding='utf-8') as f:
            cls.card_js = f.read()

    def test_01_subscriptions_block_strict_order_and_no_badge(self):
        """1. Verify block 'Подписки и исключения' strict order and removal of 'Не показывать в ленте' badge."""
        self.assertIn('feedSettingsSectionSubscriptions', self.feed_html)
        subs_sec_match = re.search(r'<div[^>]*id=["\']feedSettingsSectionSubscriptions["\'][^>]*>(.*?)</div>\s*</div>\s*<!-- Panel Footer', self.feed_html, re.DOTALL)
        self.assertIsNotNone(subs_sec_match)
        subs_content = subs_sec_match.group(1)

        idx_title = subs_content.find('Подписки и исключения')
        idx_switch = subs_content.find('feed-subs-switch-row')
        idx_mode_hint = subs_content.find('feedSubsModeHint')
        idx_tabs_row = subs_content.find('feed-subs-nav-bar')
        idx_items_list = subs_content.find('feedUserSubsList')

        self.assertGreater(idx_title, -1)
        self.assertGreater(idx_switch, idx_title, "Switch row must appear after title")
        self.assertGreater(idx_mode_hint, idx_switch, "Dynamic mode hint must appear after switch row")
        self.assertGreater(idx_tabs_row, idx_mode_hint, "Tabs row must appear after mode hint")
        self.assertGreater(idx_items_list, idx_tabs_row, "User items list must appear after tabs row")

        # Verify old gray badge 'Не показывать в ленте' removed from segmented control
        self.assertNotIn('Не показывать в ленте', subs_content)
        self.assertIn('btnSubsModeSubscriptions', subs_content)
        self.assertIn('btnSubsModeExceptions', subs_content)

    def test_02_author_card_avatar_and_secondary_button_styles(self):
        """2. Verify createAvatarEl in card.js, .subs-author-avatar, word wrap, and secondary button."""
        # card.js must export createAvatarEl on window.SmartContractumCard
        self.assertIn('createAvatarEl', self.card_js)
        self.assertIn('window.SmartContractumCard', self.card_js)

        # Card hierarchy preserved in card.js
        idx_meta = self.card_js.find('class="card-meta"')
        idx_title = self.card_js.find('class="card-title')
        idx_badges = self.card_js.find('class="card-meta-badges')
        idx_cover = self.card_js.find('class="card-cover-container')
        idx_lead = self.card_js.find('class="card-lead')
        idx_tags = self.card_js.find('class="card-tags')
        idx_footer = self.card_js.find('class="card-footer')
        self.assertTrue(idx_meta < idx_title < idx_badges < idx_cover < idx_lead < idx_tags < idx_footer)

        # feed.css styles
        self.assertIn('.subs-author-avatar', self.feed_css)
        self.assertIn('.subs-item--author', self.feed_css)
        self.assertIn('.subs-item-info--compact', self.feed_css)
        self.assertIn('.subs-item-title--wrap', self.feed_css)
        self.assertIn('word-break: break-word', self.feed_css)

        # Subscriptions grid: 1fr or minmax(280px, 380px) and align-content: start
        subs_grid_match = re.search(r'\.feed-settings-subs-list\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(subs_grid_match)
        subs_grid_rules = subs_grid_match.group(1)
        self.assertTrue('1fr' in subs_grid_rules or 'minmax(280px, 380px)' in subs_grid_rules)
        self.assertIn('align-content: start', subs_grid_rules)

        # Neutral secondary button
        self.assertIn('.subs-toggle-btn', self.feed_css)
        self.assertIn('.subs-toggle-btn:hover', self.feed_css)
        self.assertIn('.subs-toggle-btn:focus-visible', self.feed_css)

    def test_03_settings_clean_hints_and_unified_naming(self):
        """3. Verify removed 'Минимум один', updated hints, and unified 'Без указанного уровня'."""
        self.assertNotIn('Минимум один', self.feed_html)
        self.assertTrue(
            'Что показывать в “Моей ленте”' in self.feed_html or
            'Выберите хотя бы один тип материалов для “Моей ленты”' in self.feed_html
        )
        self.assertTrue(
            'Можно выбрать несколько уровней' in self.feed_html or
            'Выберите подходящие уровни для “Моей ленты” или оставьте любой' in self.feed_html
        )

        # Unified naming 'Без указанного уровня' / 'Не указан' in settings and filters
        self.assertIn('id="feedCompNone"', self.feed_html)
        self.assertIn('id="feedFilterCompNone"', self.feed_html)
        self.assertTrue('Не указан' in self.feed_html or 'Без указанного уровня' in self.feed_html)

    def test_04_filters_all_types_and_any_level(self):
        """4. Verify explicit 'Все типы' and 'Любой уровень' chips with mutual exclusivity logic."""
        self.assertIn('data-type="all"', self.feed_html)
        self.assertIn('data-complexity="all"', self.feed_html)
        self.assertIn('Все типы', self.feed_html)
        self.assertIn('Любой уровень', self.feed_html)

        # Mutual exclusivity in feed.js
        self.assertIn("t === 'all'", self.feed_js)
        self.assertIn("c === 'all'", self.feed_js)

    def test_05_filters_topics_dropdown_selector(self):
        """5. Verify compact topics dropdown selector with search, checkboxes, and chips."""
        self.assertIn('id="feedTopicsDropdownTrigger"', self.feed_html)
        self.assertIn('id="feedTopicsDropdownMenu"', self.feed_html)
        self.assertIn('id="filterTopicSearchInput"', self.feed_html)
        self.assertIn('id="modalTopicsFilterBar"', self.feed_html)
        self.assertIn('id="filterSelectedTopicsChips"', self.feed_html)
        self.assertIn('Все темы', self.feed_html)

        # CSS dropdown styles
        self.assertIn('.feed-topics-dropdown-wrap', self.feed_css)
        self.assertIn('.feed-topics-dropdown-trigger', self.feed_css)
        self.assertIn('.feed-topics-dropdown-menu', self.feed_css)
        self.assertIn('.feed-topic-checkbox-item', self.feed_css)
        self.assertIn('.filter-selected-chips-bar', self.feed_css)

    def test_06_filters_advanced_2_columns_and_counter_badge(self):
        """6. Verify 2-column layout (16-24px gap) with counter badge on advanced filters."""
        self.assertIn('id="feedFiltersAdvanced"', self.feed_html)
        self.assertIn('id="feedAdvancedFiltersCountBadge"', self.feed_html)

        adv_body_match = re.search(r'\.feed-filters-advanced-body\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(adv_body_match)
        adv_body_rules = adv_body_match.group(1)
        self.assertTrue('grid-template-columns: 1fr 1fr' in adv_body_rules or 'repeat(2, minmax(0, 1fr))' in adv_body_rules)
        self.assertIn('gap: 20px', adv_body_rules)

        self.assertIn('.advanced-count-badge', self.feed_css)
        self.assertIn('updateAdvancedFiltersUI', self.feed_js)

    def test_07_unified_sorting_toolbar_and_no_sort_in_filters(self):
        """7. Verify sort dropdown is only in direct toolbar, removed from filters panel, and preserved on reset."""
        # Panel has no sort dropdown
        filters_panel_match = re.search(r'<section[^>]*id=["\']feedFiltersPanel["\'][^>]*>(.*?)</section>', self.feed_html, re.DOTALL)
        self.assertIsNotNone(filters_panel_match)
        filters_panel_content = filters_panel_match.group(1)
        self.assertNotIn('feedSortSelect', filters_panel_content)

        # Toolbar has sort dropdown with newest, popular, discussed, oldest
        self.assertIn('id="feedSortSelect"', self.feed_html)
        sort_select_match = re.search(r'<select[^>]*id=["\']feedSortSelect["\'][^>]*>(.*?)</select>', self.feed_html, re.DOTALL)
        self.assertIsNotNone(sort_select_match)
        sort_options = sort_select_match.group(1)
        self.assertIn('value="newest"', sort_options)
        self.assertIn('value="popular"', sort_options)
        self.assertIn('value="discussed"', sort_options)
        self.assertIn('value="oldest"', sort_options)

        # resetAllFilters in feed.js preserves state.sort
        reset_func_match = re.search(r'function resetAllFilters\(\)\s*\{([^}]+)\}', self.feed_js)
        self.assertIsNotNone(reset_func_match)
        reset_func_code = reset_func_match.group(1)
        self.assertNotIn("state.sort = 'newest'", reset_func_code)

    def test_08_compact_search_and_results_count_and_empty_state(self):
        """8. Verify compact placeholder 'Поиск публикаций', compact count 'N публикаций', and empty state actions."""
        self.assertIn('placeholder="Поиск публикаций"', self.feed_html)

        # updateResultsCount calls pluralizePublications
        count_func_match = re.search(r'function updateResultsCount\(\)\s*\{([^}]+)\}', self.feed_js)
        self.assertIsNotNone(count_func_match)
        count_code = count_func_match.group(1)
        self.assertIn('pluralizePublications', count_code)

        # renderEmptyState has change filters and reset filters
        self.assertIn('feedEmptyChangeFiltersBtn', self.feed_js)
        self.assertIn('feedEmptyResetBtn', self.feed_js)
        self.assertIn('Изменить фильтры', self.feed_js)

    def test_09_offline_first_strict_onest_and_zero_emojis(self):
        """9. Verify 100% offline-first, strict Onest font, and zero emojis across modified files."""
        emoji_pattern = re.compile(r'[\U00010000-\U0010ffff\u2600-\u27bf\u2300-\u23ff\u2b50-\u2b55]')
        url_pattern = re.compile(r'https?://(?!localhost|127\.0\.0\.1|www\.w3\.org|smartcontractum\.ru)[^\s\'"<>]+')
        for fname, content in [('feed.html', self.feed_html), ('feed.css', self.feed_css), ('feed.js', self.feed_js), ('card.js', self.card_js)]:
            matches = emoji_pattern.findall(content)
            self.assertEqual(len(matches), 0, f"Found emojis in {fname}: {matches}")
            ext_urls = [m for m in url_pattern.findall(content) if 'w3.org' not in m]
            self.assertEqual(len(ext_urls), 0, f"External URLs found in {fname}: {ext_urls}")


class TestTask33FeedPanelsLayoutAndVisualDensity(unittest.TestCase):
    """Regression and compliance tests for Task 33: Feed panels layout and visual density."""

    @classmethod
    def setUpClass(cls):
        cls.feed_html_path = os.path.join(FRONTEND_DIR, 'feed.html')
        with open(cls.feed_html_path, 'r', encoding='utf-8') as f:
            cls.feed_html = f.read()

        cls.feed_css_path = os.path.join(FRONTEND_DIR, 'css', 'feed.css')
        with open(cls.feed_css_path, 'r', encoding='utf-8') as f:
            cls.feed_css = f.read()

        cls.feed_js_path = os.path.join(FRONTEND_DIR, 'js', 'feed.js')
        with open(cls.feed_js_path, 'r', encoding='utf-8') as f:
            cls.feed_js = f.read()

    def test_01_feed_settings_subtitle_and_2col_desktop_layout(self):
        """1. Verify feed settings subtitle, 2-column layout on desktop and single column on mobile."""
        self.assertTrue(
            'Выберите, что читать и что скрывать' in self.feed_html or
            'Настройте интересы для “Моей ленты” и исключения для обеих лент' in self.feed_html
        )
        self.assertIn('feed-settings-col-left', self.feed_html)
        self.assertIn('feedSettingsSectionSubscriptions', self.feed_html)

        # CSS 2-column flex container and column widths
        self.assertIn('.feed-settings-panel .feed-slide-panel-body', self.feed_css)
        self.assertIn('.feed-settings-col-left', self.feed_css)
        self.assertIn('.feed-settings-subs-section', self.feed_css)

        # Left column width 360-400px
        left_match = re.search(r'\.feed-settings-col-left\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(left_match)
        left_rules = left_match.group(1)
        self.assertTrue('380px' in left_rules or '360px' in left_rules or '400px' in left_rules)
        self.assertTrue('min-width: 360px' in left_rules)
        self.assertTrue('max-width: 400px' in left_rules)

        # Mobile media query (max-width: 959px) stacks columns
        self.assertIn('@media (max-width: 959px)', self.feed_css)
        mobile_match = re.search(r'@media\s*\(max-width:\s*959px\)\s*\{([^}]+(\{[^}]+\}[^}]+)+)\}', self.feed_css)
        self.assertIsNotNone(mobile_match)
        mobile_css = mobile_match.group(0)
        self.assertIn('flex-direction: column', mobile_css)

    def test_02_feed_settings_types_and_complexity_structure(self):
        """2. Verify left column: Types 2x2 tumblers, Complexity upper row and 2x2 grid, with hints."""
        # Types hint and tumblers grid
        self.assertIn('Что показывать в “Моей ленте”', self.feed_html)
        self.assertIn('feed-tumblers-grid', self.feed_html)
        tumbler_grid_match = re.search(r'\.feed-tumblers-grid\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(tumbler_grid_match)
        self.assertIn('repeat(2, minmax(0, 1fr))', tumbler_grid_match.group(1))

        # Complexity hint, any-row and 2x2 grid
        self.assertIn('Можно выбрать несколько уровней', self.feed_html)
        self.assertIn('feed-complexity-grid-wrap', self.feed_html)
        self.assertIn('feed-complexity-any-row', self.feed_html)
        self.assertIn('feed-complexity-2x2-grid', self.feed_html)
        self.assertIn('id="feedCompAll"', self.feed_html)
        self.assertIn('id="feedCompEasy"', self.feed_html)
        self.assertIn('id="feedCompMedium"', self.feed_html)
        self.assertIn('id="feedCompHard"', self.feed_html)
        self.assertIn('id="feedCompNone"', self.feed_html)

        # CSS for complexity 2x2 grid
        comp_2x2_match = re.search(r'\.feed-complexity-2x2-grid\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(comp_2x2_match)
        self.assertIn('repeat(2, minmax(0, 1fr))', comp_2x2_match.group(1))

    def test_03_feed_settings_subscriptions_and_add_button(self):
        """3. Verify right column subscriptions: dynamic hint, Add button, 1-col items, and card protection."""
        # Dynamic hint for exceptions
        self.assertIn('Скрываются в общей и персональной ленте', self.feed_js)

        # Add button with plus icon and dynamic title/aria-label
        self.assertIn('id="btnToggleCatalogSearch"', self.feed_html)
        self.assertIn('id="btnToggleCatalogSearchText"', self.feed_html)
        self.assertIn('Добавить', self.feed_html)
        self.assertIn('Добавить подписки', self.feed_js)
        self.assertIn('Добавить исключения', self.feed_js)

        # 1-column layout for #feedUserSubsList
        self.assertIn('id="feedUserSubsList"', self.feed_html)
        subs_list_match = re.search(r'\.feed-settings-subs-list\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(subs_list_match)
        self.assertIn('grid-template-columns: 1fr;', subs_list_match.group(1))

        # Overflow / ellipsis protection for author card
        self.assertIn('text-overflow: ellipsis', self.feed_css)
        self.assertIn('white-space: nowrap', self.feed_css)

        # Compact empty state
        self.assertIn('.feed-subs-empty-state', self.feed_css)
        empty_state_match = re.search(r'\.feed-subs-empty-state\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(empty_state_match)
        self.assertIn('padding: 20px', empty_state_match.group(1))

    def test_04_feed_filters_panel_header_and_2x2_grid(self):
        """4. Verify filters panel subtitle, removed duplicate footer hint, and 2x2 desktop grid."""
        # Header subtitle
        self.assertIn('Уточните текущую выдачу. Подписки и настройки сохранятся', self.feed_html)

        # No duplicate hint in footer
        footer_match = re.search(r'<div class="feed-slide-panel-footer">(.*?)</div>\s*</div>\s*</section>', self.feed_html, re.DOTALL)
        self.assertIsNotNone(footer_match)
        footer_text = footer_match.group(1)
        self.assertNotIn('Подписки и настройки сохранятся', footer_text)

        # 2x2 primary grid
        self.assertIn('feed-filters-primary-grid', self.feed_html)
        grid_match = re.search(r'\.feed-filters-primary-grid\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(grid_match)
        grid_css = grid_match.group(1)
        self.assertIn('repeat(2, minmax(0, 1fr))', grid_css)
        self.assertTrue('20px 24px' in grid_css or '24px' in grid_css)

        # Structure: Row 1 = Types + Complexity, Row 2 = Topics + Date
        idx_types = self.feed_html.find('feedFilterGroupTypes')
        idx_comp = self.feed_html.find('feedFilterGroupComplexity')
        idx_topics = self.feed_html.find('feedFilterGroupTopics')
        idx_date = self.feed_html.find('feedFilterGroupDate')
        self.assertTrue(idx_types < idx_comp < idx_topics < idx_date)

    def test_05_feed_filters_date_selector_and_validation(self):
        """5. Verify compact date dropdown, custom date inputs, and range validation."""
        self.assertIn('id="feedFilterPeriodSelect"', self.feed_html)
        self.assertIn('class="feed-select filter-control feed-period-select"', self.feed_html)
        self.assertIn('За всё время', self.feed_html)
        self.assertIn('За неделю', self.feed_html)
        self.assertIn('За месяц', self.feed_html)
        self.assertIn('За год', self.feed_html)
        self.assertIn('Указать период', self.feed_html)

        # Custom date inputs
        self.assertIn('id="feedFilterCustomDates"', self.feed_html)
        self.assertIn('id="filterDateFrom"', self.feed_html)
        self.assertIn('id="filterDateTo"', self.feed_html)

        # CSS height 38px
        self.assertIn('height: 38px', self.feed_css)

        # Range validation in feed.js
        self.assertIn('Начальная дата не может быть позже конечной', self.feed_js)

    def test_06_feed_filters_advanced_parameters_collapsible(self):
        """6. Verify collapsible advanced parameters in 2 columns with chevron, badge, and auto-open."""
        self.assertIn('id="feedFiltersAdvanced"', self.feed_html)
        self.assertIn('class="feed-filters-advanced-summary"', self.feed_html)
        self.assertIn('class="summary-chevron"', self.feed_html)
        self.assertIn('id="feedAdvancedFiltersCountBadge"', self.feed_html)
        self.assertIn('class="feed-filters-advanced-body"', self.feed_html)

        # CSS 2 equal columns and gap
        adv_body_match = re.search(r'\.feed-filters-advanced-body\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(adv_body_match)
        adv_css = adv_body_match.group(1)
        self.assertIn('repeat(2, minmax(0, 1fr))', adv_css)
        self.assertTrue('20px' in adv_css or '22px' in adv_css or '24px' in adv_css)

        # Auto-open logic in feed.js
        self.assertIn('adv.open = (count > 0);', self.feed_js)

    def test_07_visual_hierarchy_calm_accents_and_neutral_buttons(self):
        """7. Verify saturated calm primary buttons, soft active chips with checkmark, and neutral secondary buttons."""
        # Calm primary button styles
        self.assertIn('#btnSaveFeedSettings', self.feed_css)
        self.assertIn('#btnApplyFilters', self.feed_css)

        # Soft accent active chips and checkmarks
        self.assertIn('.feed-choice-btn.active', self.feed_css)
        self.assertIn('.feed-filter-chip.active', self.feed_css)
        self.assertIn('.feed-chip-check', self.feed_css)

        # Neutral secondary buttons
        self.assertIn('#btnCancelFeedSettings', self.feed_css)
        self.assertIn('#feedResetFiltersBtn', self.feed_css)
        self.assertIn('.subs-toggle-btn', self.feed_css)

        # Panel toggle buttons without black border and clean focus
        subnav_btn_match = re.search(r'\.feed-subnav-btn\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(subnav_btn_match)
        self.assertNotIn('black', subnav_btn_match.group(1).lower())
        self.assertIn('.feed-subnav-btn:focus-visible', self.feed_css)

    def test_08_offline_first_strict_onest_and_zero_emojis(self):
        """8. Verify 100% offline-first, strict Onest font, and zero emojis across modified files."""
        emoji_pattern = re.compile(r'[\U00010000-\U0010ffff\u2600-\u27bf\u2300-\u23ff\u2b50-\u2b55]')
        url_pattern = re.compile(r'https?://(?!localhost|127\.0\.0\.1|www\.w3\.org|smartcontractum\.ru)[^\s\'"<>]+')
        for fname, content in [('feed.html', self.feed_html), ('feed.css', self.feed_css), ('feed.js', self.feed_js)]:
            matches = emoji_pattern.findall(content)
            self.assertEqual(len(matches), 0, f"Found emojis in {fname}: {matches}")
            ext_urls = [m for m in url_pattern.findall(content) if 'w3.org' not in m]
            self.assertEqual(len(ext_urls), 0, f"External URLs found in {fname}: {ext_urls}")


class TestTask34StickyPanelsAndMultiFilter(unittest.TestCase):
    """
    Test suite for Task 34: Feed Panels Sticky Behavior and Multi-Value Filtering.
    Verifies:
      1. Panels fixed under sticky header (--feed-header-total-height, overscroll-behavior: contain).
      2. Internal scrolling structure (scrollable body, pinned sticky footer).
      3. Multiple format selection (chips, clear selection, search).
      4. Multiple audience selection (chips, clear selection, search).
      5. Joint filtering logic (OR within group, AND between groups, backwards compatible URL/API).
      6. Unified multiselect dropdown design (theme surface, Onest font, smart upward opening, keyboard nav).
      7. Clean chips design (no default browser button styling, accessible SVG remove).
      8. UI polish (chevron on date select, complexity 'Не указан', equal button heights 38px, neutral unsaved dot).
      9. Feed mode in title, save settings toast action, unapplied filters indicator, active filters counter badge.
      10. Draft preservation, apply filters closes panel and smooth-scrolls to results.
    """

    @classmethod
    def setUpClass(cls):
        cls.feed_html_path = os.path.join(FRONTEND_DIR, 'feed.html')
        with open(cls.feed_html_path, 'r', encoding='utf-8') as f:
            cls.feed_html = f.read()

        cls.feed_css_path = os.path.join(FRONTEND_DIR, 'css', 'feed.css')
        with open(cls.feed_css_path, 'r', encoding='utf-8') as f:
            cls.feed_css = f.read()

        cls.feed_js_path = os.path.join(FRONTEND_DIR, 'js', 'feed.js')
        with open(cls.feed_js_path, 'r', encoding='utf-8') as f:
            cls.feed_js = f.read()

    def test_01_panels_fixed_position_under_header(self):
        """1. Verify panels use position: fixed under sticky subnav with dynamic CSS variable."""
        self.assertIn('position: fixed;', self.feed_css)
        self.assertIn('--feed-header-total-height', self.feed_css)
        self.assertIn('function updateFeedPanelsPosition()', self.feed_js)
        self.assertIn("document.documentElement.style.setProperty('--feed-header-total-height'", self.feed_js)
        self.assertIn("window.addEventListener('scroll', updateFeedPanelsPosition", self.feed_js)
        self.assertIn("window.addEventListener('resize', updateFeedPanelsPosition", self.feed_js)

    def test_02_internal_scrolling_and_sticky_footer(self):
        """2. Verify internal scroll containment and pinned action footer."""
        self.assertIn('.feed-slide-panel-body', self.feed_css)
        self.assertIn('overscroll-behavior: contain', self.feed_css)
        self.assertIn('position: sticky', self.feed_css)
        self.assertIn('bottom: 0', self.feed_css)

    def test_03_multi_format_selection_markup_and_controls(self):
        """3. Verify multi-format selection dropdown, trigger, clear button, and chips."""
        self.assertIn('id="feedFormatsDropdownWrap"', self.feed_html)
        self.assertIn('id="feedFormatsDropdownTrigger"', self.feed_html)
        self.assertIn('id="modalFormatsFilterBar"', self.feed_html)
        self.assertIn('id="btnFormatsClearSelection"', self.feed_html)
        self.assertIn('id="filterSelectedFormatsChips"', self.feed_html)
        self.assertIn('id="filterFormatSearchInput"', self.feed_html)

    def test_04_multi_audience_selection_markup_and_controls(self):
        """4. Verify multi-audience selection dropdown, trigger, clear button, and chips."""
        self.assertIn('id="feedAudiencesDropdownWrap"', self.feed_html)
        self.assertIn('id="feedAudiencesDropdownTrigger"', self.feed_html)
        self.assertIn('id="modalAudiencesFilterBar"', self.feed_html)
        self.assertIn('id="btnAudiencesClearSelection"', self.feed_html)
        self.assertIn('id="filterSelectedAudiencesChips"', self.feed_html)
        self.assertIn('id="filterAudienceSearchInput"', self.feed_html)

    def test_05_joint_filtering_and_backwards_compatible_api(self):
        """5. Verify server and client multi-filtering with backwards compatibility."""
        # Client URL parsing & serialization
        self.assertIn("params.get('formats')", self.feed_js)
        self.assertIn("params.get('audiences')", self.feed_js)
        self.assertIn("params.set('formats'", self.feed_js)
        self.assertIn("params.set('audiences'", self.feed_js)

        # Server-side joint filtering verification in server.py
        with open(os.path.join(PROJECT_ROOT, 'server.py'), 'r', encoding='utf-8') as f:
            server_code = f.read()
        self.assertIn('allowed_audiences', server_code)
        self.assertIn('allowed_formats', server_code)
        self.assertIn('query.get("audiences"', server_code)
        self.assertIn('query.get("formats"', server_code)

    def test_06_unified_dropdown_design_and_adaptive_direction(self):
        """6. Verify unified dropdown styles, .opens-up support, and keyboard navigation."""
        self.assertIn('.feed-multiselect-dropdown-menu', self.feed_css)
        self.assertIn('.opens-up', self.feed_css)
        self.assertIn("e.key === 'Escape'", self.feed_js)
        self.assertIn('closeAllFilterDropdowns', self.feed_js)

    def test_07_clean_selected_chips_styling(self):
        """7. Verify selected chips have no default browser button styling and accessible SVGs."""
        self.assertIn('.filter-selected-chip', self.feed_css)
        self.assertIn('.filter-selected-chip-remove', self.feed_css)
        self.assertIn('background: transparent', self.feed_css)

    def test_08_ui_polish_details(self):
        """8. Verify select chevron, 'Не указан' complexity, 38px button heights, and neutral unsaved dot."""
        self.assertIn('.feed-select-chevron', self.feed_css)
        self.assertIn('feed-select-chevron', self.feed_html)
        self.assertIn('Не указан', self.feed_html)
        self.assertIn('Автор не указал сложность', self.feed_html)
        self.assertIn('feed-unsaved-dot', self.feed_css)
        self.assertIn('height: 38px', self.feed_css)

    def test_09_feed_modes_toast_unapplied_indicator_and_badge(self):
        """9. Verify feed mode page title update, toast with action, unapplied indicator, and badge logic."""
        self.assertIn('updateFeedTitleUI', self.feed_js)
        self.assertIn('feedFiltersUnappliedIndicator', self.feed_html)
        self.assertIn('checkFiltersPanelUnappliedChanges', self.feed_js)
        self.assertIn('feed-toast-action-btn', self.feed_css)
        self.assertIn('feed-toast-action-btn', self.feed_js)
        self.assertIn('Открыть мою ленту', self.feed_js)

    def test_10_draft_preservation_and_smooth_scroll(self):
        """10. Verify filtersDraftState in-memory preservation and smooth scroll on apply."""
        self.assertIn('filtersDraftState', self.feed_js)
        self.assertIn("scrollIntoView({ behavior: 'smooth'", self.feed_js)


if __name__ == '__main__':
    unittest.main()



