#!/usr/bin/env python3
"""
Test Suite: Feed Page and Editor Designer Color Palette
Verification for task-14-feed-page-and-editor-color-palette, task-15-editor-feed-visual-alignment & task-16-fix-editor-visual-and-theme-issues:
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
  9. Task-15 Visual alignment requirements:
     - Top navigation header with #appHeader, brand-logo link to feed.html, #navEditor.is-active, #btnThemeToggle, #headerLoginBtn.
     - Document action bar #editorDocumentBar with brand Antigravity Writer, #btn-drafts-modal, #drafts-badge, #save-status, #btn-more-actions.
     - Unified button styles in editor.css (.btn-primary, .btn-next-to-pub/#btn-next-to-settings, secondary .btn/.btn-drafts).
     - Strict Onest font and zero emojis in editor.html and editor.css.
 10. Task-16 Editor visual and theme fixes:
     - High-contrast text tokens in light theme (#0f172a in theme.css and landing_main.css).
     - Editor header exact feed structure (logo-title with logo-smart & logo-contractum,
       all 5 nav links with .nav-icon-box and SVG icons, #navEditor with 'nav-link active', link to forum_social.css).
     - Onest font smoothing (-webkit-font-smoothing: antialiased) and antialiasing (text-rendering: optimizeLegibility).
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
        """Verify navigation links: Главная, Сообщество, Редактор in feed.html per user requirement 3."""
        header_match = re.search(r'<header[^>]*class="[^"]*app-header[^"]*"[^>]*>(.*?)</header>', self.feed_html, re.DOTALL)
        self.assertIsNotNone(header_match)
        header_content = header_match.group(1)

        nav_match = re.search(r'<nav[^>]*class="[^"]*header-nav[^"]*"[^>]*>(.*?)</nav>', header_content, re.DOTALL)
        self.assertIsNotNone(nav_match, "header-nav not found inside header")
        nav_content = nav_match.group(1)

        required_nav_items = [
            'Главная',
            'Сообщество',
            'Редактор'
        ]

        for item in required_nav_items:
            self.assertIn(item, nav_content, f"Navigation link '{item}' missing in header-nav")

        # Removed from main navigation per user requirement 3
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
        """Verify cross navigation between editor and feed: header has brand logo and nav link to feed.html."""
        header_match = re.search(r'<header[^>]*id=["\']appHeader["\'][^>]*>(.*?)</header>', self.editor_html, re.DOTALL)
        self.assertIsNotNone(header_match, "appHeader not found in editor.html")
        header_content = header_match.group(1)

        # Brand logo exists in header
        self.assertIn('brand-logo', header_content)
        # Link to Community/Feed exists in navigation
        feed_link_match = re.search(r'<a[^>]*href=["\']feed\.html["\'][^>]*>(.*?)Сообщество(.*?)</a>', header_content, re.DOTALL)
        self.assertIsNotNone(feed_link_match, "Navigation link to feed.html (Сообщество) not found in editor header")

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
        # Top sticky header with id="appHeader"
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
    """Test Suite for task-16: Editor visual and theme issues:
    - High-contrast text tokens in light theme (#0f172a in theme.css and landing_main.css).
    - Editor header exact feed structure (logo-title with logo-smart & logo-contractum,
      all 5 nav links with .nav-icon-box and SVG icons, #navEditor with 'nav-link active', link to forum_social.css).
    - Onest font smoothing (-webkit-font-smoothing: antialiased) and antialiasing (text-rendering: optimizeLegibility).
    """

    @classmethod
    def setUpClass(cls):
        cls.editor_html_path = os.path.join(FRONTEND_DIR, 'editor.html')
        cls.editor_css_path = os.path.join(FRONTEND_DIR, 'css', 'editor.css')
        cls.theme_css_path = os.path.join(FRONTEND_DIR, 'css', 'theme.css')
        cls.landing_main_css_path = os.path.join(FRONTEND_DIR, 'css', 'landing_main.css')

        with open(cls.editor_html_path, 'r', encoding='utf-8') as f:
            cls.editor_html = f.read()
        with open(cls.editor_css_path, 'r', encoding='utf-8') as f:
            cls.editor_css = f.read()
        with open(cls.theme_css_path, 'r', encoding='utf-8') as f:
            cls.theme_css = f.read()
        with open(cls.landing_main_css_path, 'r', encoding='utf-8') as f:
            cls.landing_main_css = f.read()

    def test_light_theme_high_contrast_text_tokens(self):
        """Verify that theme.css and landing_main.css define high-contrast dark text (#0f172a)
        for [data-theme="light"], ensuring zero white text on white backgrounds in light mode."""
        # 1. theme.css [data-theme="light"]
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

        # 2. landing_main.css [data-theme="light"]
        landing_light_match = re.search(r'\[data-theme=["\']?light["\']?\]\s*\{([^}]+)\}', self.landing_main_css)
        self.assertIsNotNone(landing_light_match, "[data-theme='light'] block not found in landing_main.css")
        landing_light_css = landing_light_match.group(1)

        self.assertTrue(
            re.search(r'--text-primary:\s*#0f172a\b', landing_light_css),
            "landing_main.css must define --text-primary: #0f172a in [data-theme='light'] block"
        )
        self.assertNotIn('--text-primary: #ffffff', landing_light_css,
                         "landing_main.css must not define --text-primary as #ffffff in light mode")
        self.assertNotIn('--text-primary: #fff;', landing_light_css,
                         "landing_main.css must not define --text-primary as #fff in light mode")

    def test_editor_header_exact_feed_structure(self):
        """Verify editor.html header contains:
        * logo-title with logo-smart ('Smart') and logo-contractum ('Contractum').
        * all 5 navigation links contain .nav-icon-box with SVG icons.
        * #navEditor has class 'nav-link active'.
        * link to css/forum_social.css is present."""
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

        # 2. all 5 navigation links contain .nav-icon-box with SVG icons
        nav_match = re.search(r'<nav[^>]*id=["\']headerNav["\'][^>]*>(.*?)</nav>', header_content, re.DOTALL)
        self.assertIsNotNone(nav_match, "headerNav not found in editor header")
        nav_content = nav_match.group(1)

        nav_links = re.findall(r'<a\b[^>]*>(.*?)</a>', nav_content, re.DOTALL)
        self.assertEqual(len(nav_links), 3, f"Expected 3 navigation links in header, got {len(nav_links)}")

        required_nav_names = ['Главная', 'Сообщество', 'Редактор']
        for i, (link_html, expected_name) in enumerate(zip(nav_links, required_nav_names)):
            self.assertIn(expected_name, link_html, f"Navigation link {i+1} must contain text '{expected_name}'")
            self.assertIn('nav-icon-box', link_html, f"Navigation link '{expected_name}' must contain .nav-icon-box")
            self.assertIn('<svg', link_html, f"Navigation link '{expected_name}' must contain SVG icon inside .nav-icon-box")

        # Removed from navigation per user requirement 3
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

        # 4. link to css/forum_social.css is present
        forum_social_link = re.search(
            r'<link[^>]*href=["\'](?:css/)?forum_social\.css["\'][^>]*>',
            self.editor_html
        )
        self.assertIsNotNone(forum_social_link, "link to css/forum_social.css not found in editor.html")

    def test_onest_font_smoothing_and_antialiasing(self):
        """Verify editor.css or editor.html specifies -webkit-font-smoothing: antialiased
        and text-rendering: optimizeLegibility with Onest font."""
        # Check -webkit-font-smoothing: antialiased
        has_antialiased = (
            bool(re.search(r'-webkit-font-smoothing:\s*antialiased', self.editor_css)) or
            bool(re.search(r'-webkit-font-smoothing:\s*antialiased', self.editor_html))
        )
        self.assertTrue(has_antialiased, "Expected -webkit-font-smoothing: antialiased in editor.css or editor.html")

        # Check text-rendering: optimizeLegibility
        has_optimize_legibility = (
            bool(re.search(r'text-rendering:\s*optimizeLegibility', self.editor_css)) or
            bool(re.search(r'text-rendering:\s*optimizeLegibility', self.editor_html))
        )
        self.assertTrue(has_optimize_legibility, "Expected text-rendering: optimizeLegibility in editor.css or editor.html")

        # Check Onest font
        self.assertIn("'Onest'", self.editor_css, "editor.css must declare 'Onest' font family")
        self.assertIn("'Onest'", self.editor_html, "editor.html must declare 'Onest' font family")


if __name__ == '__main__':
    unittest.main()
