#!/usr/bin/env python3
"""
Test Suite: Feed Page and Editor Designer Color Palette
Verification for task-14-feed-page-and-editor-color-palette:
  1. Verification that frontend/public/feed.html exists.
  2. 100% Offline-First check: Ensure feed.html, landing_main.css, forum_social.css, hero_constellation.css
     have zero external http/https references to Google Fonts, CDNs, or external scripts.
  3. Strict Onest font usage in feed.html, landing_main.css, and forum_social.css.
  4. Header menu in feed.html: verify brand logo SmartContractum (with SVG icon),
     navigation links (Главная, Сообщество, Эксперты, База знаний, Редактор),
     theme toggle (#btnThemeToggle), and user login button.
  5. Navigation to editor: verify nav link 'Редактор' has href="editor.html",
     and CTA #btnHeroWrite has href="editor.html".
  6. Cross-navigation in editor.html: verify brand link has href="feed.html" and title="В ленту публикаций".
  7. Editor designer color palette: verify theme.css dark theme defines:
     --bg-page: #0b1426, --bg-editor: #171924, --border-color: #222531,
     --accent-color: #3861fb, --success-color: #16c784,
     and editor.html defaults to data-theme="dark".
  8. Emojis check: verify zero emojis in feed.html.
"""

import os
import re
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, 'frontend', 'public')


class TestFeedPageExistenceAndOfflineIntegrity(unittest.TestCase):
    """Test 1 & 2: Verification of feed.html presence and 100% Offline-First compliance."""

    @classmethod
    def setUpClass(cls):
        cls.feed_html_path = os.path.join(FRONTEND_DIR, 'feed.html')
        cls.landing_main_css_path = os.path.join(FRONTEND_DIR, 'css', 'landing_main.css')
        cls.forum_social_css_path = os.path.join(FRONTEND_DIR, 'css', 'forum_social.css')
        cls.hero_constellation_css_path = os.path.join(FRONTEND_DIR, 'css', 'hero_constellation.css')

        with open(cls.feed_html_path, 'r', encoding='utf-8') as f:
            cls.feed_html = f.read()
        with open(cls.landing_main_css_path, 'r', encoding='utf-8') as f:
            cls.landing_main_css = f.read()
        with open(cls.forum_social_css_path, 'r', encoding='utf-8') as f:
            cls.forum_social_css = f.read()
        with open(cls.hero_constellation_css_path, 'r', encoding='utf-8') as f:
            cls.hero_constellation_css = f.read()

    def test_feed_html_exists(self):
        """Verify that frontend/public/feed.html exists and is not empty."""
        self.assertTrue(os.path.isfile(self.feed_html_path), "frontend/public/feed.html must exist")
        file_size = os.path.getsize(self.feed_html_path)
        self.assertGreater(file_size, 5000, f"feed.html is unexpectedly small ({file_size} bytes)")

    def test_offline_first_zero_external_references(self):
        """Ensure feed.html and related stylesheets have zero external references to Google Fonts, CDNs, or scripts."""
        checked_files = [
            (self.feed_html, 'feed.html'),
            (self.landing_main_css, 'landing_main.css'),
            (self.forum_social_css, 'forum_social.css'),
            (self.hero_constellation_css, 'hero_constellation.css'),
        ]

        cdn_indicators = [
            'fonts.googleapis.com',
            'fonts.gstatic.com',
            'cdnjs.cloudflare.com',
            'cdn.jsdelivr.net',
            'unpkg.com',
            'ajax.googleapis.com',
            'stackpath.bootstrapcdn.com'
        ]

        for content, filename in checked_files:
            for cdn in cdn_indicators:
                self.assertNotIn(cdn, content, f"Forbidden external CDN reference '{cdn}' found in {filename}")

        # Regex for external http/https urls (excluding standard XML namespaces and metadata domain)
        url_pattern = re.compile(r'https?://(?!localhost|127\.0\.0\.1|www\.w3\.org|smartcontractum\.ru)[^\s\'"<>]+')
        for content, filename in checked_files:
            matches = [m for m in url_pattern.findall(content) if 'w3.org' not in m]
            self.assertEqual(len(matches), 0, f"External URLs found in {filename}: {matches}")

    def test_feed_scripts_and_stylesheets_are_local(self):
        """Verify that all link[rel=stylesheet] and script[src] references in feed.html point to local files."""
        # Find stylesheet links
        stylesheet_hrefs = re.findall(r'<link[^>]*rel=["\']stylesheet["\'][^>]*href=["\']([^"\']+)["\']', self.feed_html)
        self.assertGreater(len(stylesheet_hrefs), 0, "No stylesheet links found in feed.html")
        for href in stylesheet_hrefs:
            self.assertFalse(href.startswith(('http://', 'https://', '//')),
                             f"Stylesheet href '{href}' must not be an external absolute URL")

        # Find script sources
        script_srcs = re.findall(r'<script[^>]*src=["\']([^"\']+)["\']', self.feed_html)
        self.assertGreater(len(script_srcs), 0, "No script tags with src found in feed.html")
        for src in script_srcs:
            self.assertFalse(src.startswith(('http://', 'https://', '//')),
                             f"Script src '{src}' must not be an external absolute URL")


class TestFeedTypographyAndOnestFont(unittest.TestCase):
    """Test 3: Strict Onest font usage in feed.html, landing_main.css, and forum_social.css."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(FRONTEND_DIR, 'feed.html'), 'r', encoding='utf-8') as f:
            cls.feed_html = f.read()
        with open(os.path.join(FRONTEND_DIR, 'css', 'landing_main.css'), 'r', encoding='utf-8') as f:
            cls.landing_main_css = f.read()
        with open(os.path.join(FRONTEND_DIR, 'css', 'forum_social.css'), 'r', encoding='utf-8') as f:
            cls.forum_social_css = f.read()

    def test_strict_onest_font_usage(self):
        """Verify that Onest font family is explicitly declared and applied in feed.html and CSS files."""
        # feed.html inline style or head styles
        self.assertIn("'Onest'", self.feed_html, "feed.html must declare 'Onest' font family")

        # landing_main.css
        self.assertIn("'Onest'", self.landing_main_css, "landing_main.css must use 'Onest' font family")

        # forum_social.css
        self.assertIn("'Onest'", self.forum_social_css, "forum_social.css must use 'Onest' font family")

    def test_no_legacy_disallowed_font_families(self):
        """Verify that legacy font families (Inter, Manrope, JetBrains Mono) are not used in font-family rules."""
        disallowed_fonts_pattern = re.compile(
            r'font-family:\s*[^;]*\b(?:Inter|Manrope|JetBrains Mono)\b',
            re.IGNORECASE
        )

        for content, filename in [
            (self.feed_html, 'feed.html'),
            (self.landing_main_css, 'landing_main.css'),
            (self.forum_social_css, 'forum_social.css')
        ]:
            matches = disallowed_fonts_pattern.findall(content)
            self.assertEqual(len(matches), 0, f"Disallowed font family found in {filename}: {matches}")


class TestFeedHeaderMenuAndNavigation(unittest.TestCase):
    """Test 4 & 5: Header menu components and navigation to editor in feed.html."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(FRONTEND_DIR, 'feed.html'), 'r', encoding='utf-8') as f:
            cls.feed_html = f.read()

    def test_header_brand_logo_and_icon(self):
        """Verify brand logo SmartContractum with SVG icon and link in feed.html header."""
        # Header container
        header_match = re.search(r'<header[^>]*class="[^"]*app-header[^"]*"[^>]*>(.*?)</header>', self.feed_html, re.DOTALL)
        self.assertIsNotNone(header_match, "app-header element not found in feed.html")
        header_content = header_match.group(1)

        # Brand logo
        self.assertIn('class="brand-logo"', header_content)
        self.assertIn('Smart', header_content)
        self.assertIn('Contractum', header_content)

        # Brand logo SVG icon
        self.assertIn('class="smart-contract-logo-svg"', header_content)
        self.assertIn('<svg', header_content)

    def test_header_navigation_links(self):
        """Verify navigation links: Главная, Сообщество, Эксперты, База знаний, Редактор in feed.html."""
        header_match = re.search(r'<header[^>]*class="[^"]*app-header[^"]*"[^>]*>(.*?)</header>', self.feed_html, re.DOTALL)
        self.assertIsNotNone(header_match)
        header_content = header_match.group(1)

        nav_match = re.search(r'<nav[^>]*class="[^"]*header-nav[^"]*"[^>]*>(.*?)</nav>', header_content, re.DOTALL)
        self.assertIsNotNone(nav_match, "header-nav not found inside header")
        nav_content = nav_match.group(1)

        required_nav_items = [
            'Главная',
            'Сообщество',
            'Эксперты',
            'База знаний',
            'Редактор'
        ]

        for item in required_nav_items:
            self.assertIn(item, nav_content, f"Navigation link '{item}' missing in header-nav")

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
        self.assertIn('Войти', self.feed_html)

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
        cta_match = re.search(r'<a[^>]*id="btnHeroWrite"[^>]*href="editor\.html"[^>]*>|<a[^>]*href="editor\.html"[^>]*id="btnHeroWrite"[^>]*>', self.feed_html)
        self.assertIsNotNone(cta_match, "CTA button #btnHeroWrite with href='editor.html' not found")


class TestEditorCrossNavigationAndColorPalette(unittest.TestCase):
    """Test 6 & 7: Cross-navigation in editor.html and designer color palette in theme.css."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(FRONTEND_DIR, 'editor.html'), 'r', encoding='utf-8') as f:
            cls.editor_html = f.read()
        with open(os.path.join(FRONTEND_DIR, 'css', 'theme.css'), 'r', encoding='utf-8') as f:
            cls.theme_css = f.read()

    def test_cross_navigation_in_editor(self):
        """Verify brand link in editor.html has href='feed.html' and title='В ленту публикаций'."""
        brand_match = re.search(r'<a[^>]*class="brand"[^>]*>(.*?)</a>', self.editor_html, re.DOTALL)
        self.assertIsNotNone(brand_match, "Brand link not found in editor.html")
        brand_tag = brand_match.group(0)

        self.assertIn('href="feed.html"', brand_tag, "Brand link in editor.html must link to feed.html")
        self.assertIn('title="В ленту публикаций"', brand_tag, "Brand link in editor.html must have title='В ленту публикаций'")

    def test_editor_defaults_to_dark_theme(self):
        """Verify editor.html root element defaults to data-theme='dark'."""
        html_root_match = re.search(r'<html\b([^>]*)>', self.editor_html)
        self.assertIsNotNone(html_root_match, "html root tag not found in editor.html")
        attrs = html_root_match.group(1)
        self.assertIn('data-theme="dark"', attrs, "editor.html root element must have data-theme='dark'")

    def test_editor_designer_color_palette(self):
        """Verify theme.css dark theme defines required CoinMarketCap Midnight Navy palette tokens."""
        dark_section_match = re.search(r'\[data-theme="dark"\]\s*\{([^}]+)\}', self.theme_css)
        self.assertIsNotNone(dark_section_match, "[data-theme='dark'] block not found in theme.css")
        dark_css = dark_section_match.group(1)

        expected_tokens = {
            '--bg-page': '#0b1426',
            '--bg-editor': '#171924',
            '--border-color': '#222531',
            '--accent-color': '#3861fb',
            '--success-color': '#16c784'
        }

        for var_name, hex_val in expected_tokens.items():
            pattern = rf'{re.escape(var_name)}:\s*{re.escape(hex_val)};'
            self.assertTrue(
                re.search(pattern, dark_css),
                f"CSS variable '{var_name}' with value '{hex_val}' not found in [data-theme='dark'] block of theme.css"
            )


class TestZeroEmojisInFeedPage(unittest.TestCase):
    """Test 8: Strict zero emojis check in feed.html per GEMINI.md."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(FRONTEND_DIR, 'feed.html'), 'r', encoding='utf-8') as f:
            cls.feed_html = f.read()

    def test_zero_emojis_in_feed_html(self):
        """Verify zero emojis in feed.html across common list and full Unicode ranges."""
        forbidden_emojis = [
            '📁', '📤', '🌐', '📝', '💾', '📥', '🌓', '⌨️', '⌨', '🗑️', '🗑',
            '✨', '💡', '📋', '🖼️', '🖼', '👤', '⚓', '✏️', '✏', '👁️', '👁',
            '⏱️', '⏱', '🔤', '⚡', '📊', '💻', '🔄', '🔥', '🚀', '💬', '❤️',
            '👍', '🎉', '🌟', '💎', '🔒', '🛡️', '⚙️', '🔍'
        ]

        for emoji in forbidden_emojis:
            self.assertNotIn(emoji, self.feed_html, f"Forbidden emoji '{emoji}' found in feed.html")

        # Full Unicode range check for emoji symbols and pictographs
        emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]|[\u2b50]')
        matches = emoji_pattern.findall(self.feed_html)
        self.assertEqual(len(matches), 0, f"Unexpected emoji characters found in feed.html: {matches}")


if __name__ == '__main__':
    unittest.main()
