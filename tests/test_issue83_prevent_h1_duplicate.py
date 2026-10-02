#!/usr/bin/env python3
"""
tests/test_issue83_prevent_h1_duplicate.py

Automated test suite for Issue #83:
1. Intelligent H1 duplicate detection and warning banner in Editor:
   - In editor.js / publication.js:
     * normalizeHeading(text) -> lowercase, trim, remove markdown #, strip HTML, collapse spaces.
     * checkH1Duplicate() -> compares title input value with first heading/element of editor content.
     * If first element is an H1 and matches title, displays non-blocking warning banner:
       #h1DuplicateWarningBanner with text:
       "Первый заголовок в тексте статьи совпадает с названием публикации. Рекомендуется преобразовать его в подзаголовок H2 или удалить из текста, чтобы избежать дублирования."
     * Action buttons:
       1. "Сделать H2" (.btn-convert-h2 / #btnConvertH2) -> replaces first H1 with H2.
       2. "Удалить из текста" (.btn-remove-duplicate-h1 / #btnRemoveDuplicateH1) -> removes duplicate heading.
       3. "Оставить" (.btn-dismiss-h1-warning / #btnDismissH1Warning) -> closes banner.
     * Triggers check on paste event and input.
2. Banner markup and CSS:
   - #h1DuplicateWarningBanner placed between title container and editor in editor.html.
   - Clean styling with warning background, border, flex layout, and dark theme support in editor.css.
3. Defensive rendering in Reader (article.js):
   - preventDuplicateH1InBody(bodyEl, articleTitle) checks if first element is H1 matching article title.
   - Safely downgrades first H1 to H2 before building Table of Contents.
4. Invariants:
   - Zero emojis.
   - Zero em dashes.
   - 100% offline-first.
"""

import os
import re
import unittest
from html.parser import HTMLParser

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def read_file(relative_path: str) -> str:
    full_path = os.path.join(PROJECT_ROOT, relative_path)
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()


def python_normalize_heading(text: str) -> str:
    """Python mirror of normalizeHeading specification for testing equivalence."""
    if not text:
        return ""
    s = re.sub(r'<[^>]*>', ' ', str(text))
    s = re.sub(r'^#+\s*', '', s)
    s = s.lower()
    s = re.sub(r'[.,\/#!$%\^&\*;:{}=\-_`~()?"\'«»\u2013\u2014]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


class TestIssue83PreventH1Duplicate(unittest.TestCase):
    """Test suite for H1 duplicate detection in Editor and defensive rendering in Reader."""

    @classmethod
    def setUpClass(cls):
        cls.editor_html = read_file("frontend/public/editor.html")
        cls.editor_css = read_file("frontend/public/css/editor.css")
        cls.editor_js = read_file("frontend/public/js/editor.js")
        cls.publication_js = read_file("frontend/public/js/publication.js")
        cls.article_js = read_file("frontend/public/js/article.js")
        cls.theme_css = read_file("frontend/public/css/theme.css")
        cls.test_file_content = read_file("tests/test_issue83_prevent_h1_duplicate.py")

    def test_01_normalization_algorithm_edge_cases(self):
        """Verify heading normalization algorithm across markdown, HTML, casing, spaces, and punctuation."""
        cases = [
            ("# Мой заголовок статьи", "мой заголовок статьи"),
            ("<h1>Мой заголовок статьи</h1>", "мой заголовок статьи"),
            ("  Мой   заголовок   статьи.  ", "мой заголовок статьи"),
            ("МОЙ ЗАГОЛОВОК СТАТЬИ!", "мой заголовок статьи"),
            ("### Мой заголовок статьи: часть 1", "мой заголовок статьи часть 1"),
            ("«Мой заголовок статьи»", "мой заголовок статьи"),
            ("", ""),
            (None, "")
        ]
        for raw, expected in cases:
            self.assertEqual(python_normalize_heading(raw), expected, f"Failed for {raw}")

        # Verify JavaScript implementation exists in editor.js, publication.js, and article.js
        for code, fname in [
            (self.editor_js, "editor.js"),
            (self.publication_js, "publication.js"),
            (self.article_js, "article.js")
        ]:
            needle = "normalizeHeading(text)" if fname == "publication.js" else "function normalizeHeading"
            self.assertIn(needle, code, f"normalizeHeading must be defined in {fname}")
            self.assertIn("replace(/^#+\\s*/", code, f"Heading hash stripping must be in {fname}")
            self.assertIn("toLowerCase()", code, f"Lowercasing must be in {fname}")

    def test_02_warning_banner_markup_in_editor_html(self):
        """Verify #h1DuplicateWarningBanner exists with correct text, action buttons, and DOM position."""
        self.assertIn('id="h1DuplicateWarningBanner"', self.editor_html)
        self.assertIn('class="h1-duplicate-warning-banner"', self.editor_html)

        banner_match = re.search(r'<div[^>]*id="h1DuplicateWarningBanner"[^>]*>(.*?)</div>\s*<!--\s*Quill Canvas\s*-->', self.editor_html, re.DOTALL)
        self.assertIsNotNone(banner_match, "Banner must be positioned before Quill canvas")
        banner_content = banner_match.group(1)

        # Check message text
        self.assertIn("Первый заголовок в тексте статьи совпадает с названием публикации", banner_content)
        self.assertIn("Рекомендуется преобразовать его в подзаголовок H2 или удалить из текста", banner_content)

        # Check action buttons
        self.assertIn('id="btnConvertH2"', banner_content)
        self.assertIn('class="btn-banner-action btn-convert-h2"', banner_content)
        self.assertIn("Сделать H2", banner_content)

        self.assertIn('id="btnRemoveDuplicateH1"', banner_content)
        self.assertIn('class="btn-banner-action btn-remove-duplicate-h1"', banner_content)
        self.assertIn("Удалить из текста", banner_content)

        self.assertIn('id="btnDismissH1Warning"', banner_content)
        self.assertIn('class="btn-banner-action btn-dismiss-h1-warning"', banner_content)
        self.assertIn("Оставить", banner_content)

    def test_03_warning_banner_styling_in_editor_css(self):
        """Verify .h1-duplicate-warning-banner and action button CSS rules in editor.css."""
        banner_rule = re.search(r'\.h1-duplicate-warning-banner\s*\{([^}]+)\}', self.editor_css)
        self.assertIsNotNone(banner_rule, ".h1-duplicate-warning-banner rule must exist in editor.css")
        banner_css = banner_rule.group(1)

        self.assertIn("display: flex", banner_css)
        self.assertIn("border-radius:", banner_css)
        self.assertIn("var(--warning-subtle", banner_css)

        # Action buttons
        self.assertIn(".btn-banner-action", self.editor_css)
        self.assertIn(".btn-banner-action.btn-convert-h2", self.editor_css)
        self.assertIn(".btn-banner-action.btn-remove-duplicate-h1", self.editor_css)
        self.assertIn(".btn-banner-action.btn-dismiss-h1-warning", self.editor_css)

        # Dark theme support
        self.assertIn('[data-theme="dark"] .h1-duplicate-warning-banner', self.editor_css)

    def test_04_editor_js_detection_logic(self):
        """Verify checkH1Duplicate checks first block and displays banner only on matching H1."""
        self.assertIn("function checkH1Duplicate", self.editor_js)
        self.assertIn("bannerEl.style.display = 'flex'", self.editor_js)
        self.assertIn("bannerEl.style.display = 'none'", self.editor_js)

        # Check that publication.js also implements checkH1Duplicate
        self.assertIn("checkH1Duplicate()", self.publication_js)
        self.assertIn("this.duplicateH1Element", self.publication_js)

    def test_05_convert_and_remove_actions_in_editor_js(self):
        """Verify convertFirstH1ToH2 and removeFirstH1 implementation in editor.js and publication.js."""
        # editor.js
        self.assertIn("function convertFirstH1ToH2", self.editor_js)
        self.assertIn("document.createElement('h2')", self.editor_js)
        self.assertIn("firstEl.replaceWith(h2)", self.editor_js)
        self.assertIn("function removeFirstH1", self.editor_js)
        self.assertIn("firstEl.remove()", self.editor_js)

        # publication.js
        self.assertIn("convertH1ToH2()", self.publication_js)
        self.assertIn("removeDuplicateH1()", self.publication_js)
        self.assertIn("dismissH1Warning()", self.publication_js)

    def test_06_paste_and_input_event_wiring_in_publication_js(self):
        """Verify publication.js wires checkH1Duplicate to title input and editor paste events."""
        self.assertIn("this.checkH1Duplicate()", self.publication_js)
        self.assertIn("paste", self.publication_js)
        self.assertIn("btnConvertH2", self.publication_js)
        self.assertIn("btnRemoveDuplicateH1", self.publication_js)
        self.assertIn("btnDismissH1Warning", self.publication_js)

    def test_07_reader_defensive_rendering_in_article_js(self):
        """Verify article.js implements preventDuplicateH1InBody and safely downgrades matching first H1."""
        self.assertIn("function preventDuplicateH1InBody", self.article_js)
        self.assertIn("el.tagName === 'H1'", self.article_js)
        self.assertIn("const h2 = document.createElement('h2');", self.article_js)
        self.assertIn("el.replaceWith(h2)", self.article_js)

        # Verify it is invoked on bodyEl inside populateArticle
        body_idx = self.article_js.find("bodyEl.innerHTML = sanitized")
        prevent_idx = self.article_js.find("preventDuplicateH1InBody(bodyEl, article.title)", body_idx)
        self.assertNotEqual(prevent_idx, -1, "preventDuplicateH1InBody must be called on bodyEl")

    def test_08_reader_table_of_contents_receives_downgraded_h2(self):
        """Verify preventDuplicateH1InBody is executed BEFORE buildTableOfContents."""
        prevent_idx = self.article_js.find("preventDuplicateH1InBody(bodyEl, article.title)")
        toc_idx = self.article_js.find("buildTableOfContents(bodyEl)")
        self.assertNotEqual(prevent_idx, -1)
        self.assertNotEqual(toc_idx, -1)
        self.assertLess(prevent_idx, toc_idx, "preventDuplicateH1InBody must execute before buildTableOfContents")

    def test_09_script_inclusion_in_editor_html(self):
        """Verify editor.js is included via script tag in editor.html."""
        self.assertIn('<script src="js/editor.js?v=3"></script>', self.editor_html)

    def test_10_zero_emojis_no_em_dashes_offline_first(self):
        """Verify zero emojis, zero em dashes, and 100% offline-first in modified/new files."""
        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]|[\u2600-\u26ff]|[\u2700-\u27bf]")
        files_to_check = [
            (self.test_file_content, "test_issue83_prevent_h1_duplicate.py"),
            (self.editor_html, "editor.html"),
            (self.editor_css, "editor.css"),
            (self.editor_js, "editor.js"),
            (self.publication_js, "publication.js"),
            (self.article_js, "article.js"),
            (self.theme_css, "theme.css")
        ]
        for content, name in files_to_check:
            self.assertIsNone(emoji_pattern.search(content), f"Emoji found in {name}")
            self.assertNotIn("\u2014", content, f"Em dash found in {name}")

        for css_content, source_name in [
            (self.editor_css, "editor.css"),
            (self.theme_css, "theme.css")
        ]:
            urls = re.findall(r'url\s*\(\s*["\']?(https?://[^"\')]+)', css_content)
            self.assertEqual(len(urls), 0, f"External CDN url found in {source_name}: {urls}")


if __name__ == "__main__":
    unittest.main()
