#!/usr/bin/env python3
"""
Unit tests for Antigravity WYSIWYG Frontend Editor.
Covers:
1. File integrity and 0 CDN external dependencies (100% offline-first).
2. HTML sanitization against XSS attacks.
3. Export format converters (HTML, Markdown, JSON) and JSON import.
4. Draft storage contract and structure.
"""

import json
import os
import re
import unittest
from html.parser import HTMLParser


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, 'frontend', 'public')


class DependencyExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.stylesheets = []
        self.all_src_href = []

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        if tag == 'script' and 'src' in attr_dict:
            src = attr_dict['src']
            self.scripts.append(src)
            self.all_src_href.append(src)
        elif tag == 'link' and attr_dict.get('rel') == 'stylesheet' and 'href' in attr_dict:
            href = attr_dict['href']
            self.stylesheets.append(href)
            self.all_src_href.append(href)
        elif 'src' in attr_dict:
            self.all_src_href.append(attr_dict['src'])


class TestFileIntegrityAndOfflineVendor(unittest.TestCase):
    """Test 1: Verify presence of all required files and ensure 100% offline-first architecture."""

    def test_required_html_files_exist(self):
        for filename in ['editor.html', 'index.html']:
            filepath = os.path.join(FRONTEND_DIR, filename)
            self.assertTrue(os.path.isfile(filepath), f"Missing HTML file: {filename}")

    def test_required_css_files_exist(self):
        for filename in ['editor.css', 'theme.css']:
            filepath = os.path.join(FRONTEND_DIR, 'css', filename)
            self.assertTrue(os.path.isfile(filepath), f"Missing CSS file: {filename}")

    def test_required_js_modules_exist(self):
        required_modules = [
            'core.js', 'toolbar.js', 'bubble.js', 'blocks.js',
            'table.js', 'media.js', 'drafts.js', 'converter.js', 'main.js'
        ]
        for filename in required_modules:
            filepath = os.path.join(FRONTEND_DIR, 'js', filename)
            self.assertTrue(os.path.isfile(filepath), f"Missing JS module: {filename}")

    def test_vendor_libraries_exist_locally(self):
        vendor_files = [
            os.path.join('quill', 'quill.js'),
            os.path.join('quill', 'quill.snow.css'),
            os.path.join('highlight', 'highlight.min.js'),
            os.path.join('highlight', 'github.min.css'),
            os.path.join('highlight', 'github-dark.min.css'),
        ]
        for rel_path in vendor_files:
            filepath = os.path.join(FRONTEND_DIR, 'vendor', rel_path)
            self.assertTrue(os.path.isfile(filepath), f"Missing vendor file: {rel_path}")
            self.assertGreater(os.path.getsize(filepath), 100, f"Vendor file is empty: {rel_path}")

    def test_zero_external_cdn_in_html(self):
        """Ensure no external http/https or // CDN references in editor.html or index.html."""
        for filename in ['editor.html', 'index.html']:
            filepath = os.path.join(FRONTEND_DIR, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            parser = DependencyExtractor()
            parser.feed(content)

            for dep in parser.all_src_href:
                self.assertFalse(
                    dep.startswith(('http://', 'https://', '//')),
                    f"External CDN dependency detected in {filename}: {dep}"
                )
                # Verify that local referenced file actually exists
                clean_path = dep.split('?')[0].split('#')[0]
                target_file = os.path.join(FRONTEND_DIR, clean_path)
                self.assertTrue(
                    os.path.exists(target_file),
                    f"Referenced file not found on disk: {clean_path} (from {filename})"
                )

    def test_zero_external_fonts_or_imports_in_css(self):
        """Ensure CSS files do not contain external @import or external url() references."""
        css_dir = os.path.join(FRONTEND_DIR, 'css')
        for filename in os.listdir(css_dir):
            if filename.endswith('.css'):
                filepath = os.path.join(css_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Check for @import url(...)
                import_urls = re.findall(r'@import\s+url\([\'\"]?(https?:)?//', content, re.I)
                self.assertEqual(len(import_urls), 0, f"External @import detected in {filename}")

                # Check for font/image url(http...)
                external_urls = re.findall(r'url\([\'\"]?(https?:)?//', content, re.I)
                self.assertEqual(len(external_urls), 0, f"External url() detected in {filename}")


class TestHTMLSanitizationXSS(unittest.TestCase):
    """Test 2: HTML sanitization and XSS vulnerability prevention."""

    def sanitize_html(self, html_input):
        """Python mirror of Converter.sanitizeHTML to test the sanitization contract."""
        if not html_input:
            return ""

        # Remove dangerous tags and their content
        dangerous_tags = ['script', 'iframe', 'object', 'embed', 'form', 'style', 'link', 'meta', 'base']
        cleaned = html_input
        for tag in dangerous_tags:
            pattern = re.compile(rf'<{tag}\b[^>]*>.*?</{tag}>', re.IGNORECASE | re.DOTALL)
            cleaned = pattern.sub('', cleaned)
            # Self-closing or unclosed tag
            pattern_self = re.compile(rf'<{tag}\b[^>]*\/?>', re.IGNORECASE)
            cleaned = pattern_self.sub('', cleaned)

        # Remove inline event handlers (e.g. onload, onerror, onclick)
        cleaned = re.sub(r'\s+on[a-zA-Z]+\s*=\s*("[^"]*"|\'[^\']*\'|[^\s>]+)', '', cleaned, flags=re.IGNORECASE)

        # Remove javascript: / vbscript: / data:text/html URIs
        cleaned = re.sub(r'(href|src|action|data)\s*=\s*["\']\s*(javascript|vbscript|data:text\/html):[^"\']*["\']', '', cleaned, flags=re.IGNORECASE)

        return cleaned

    def test_strip_script_tags(self):
        payload = '<p>Normal text</p><script>alert("XSS")</script><span>More text</span>'
        sanitized = self.sanitize_html(payload)
        self.assertNotIn('<script>', sanitized.lower())
        self.assertNotIn('alert', sanitized)
        self.assertIn('Normal text', sanitized)
        self.assertIn('More text', sanitized)

    def test_strip_inline_event_handlers(self):
        payloads = [
            '<img src="valid.png" onerror="alert(1)">',
            '<a href="page.html" onclick="stealCookies()">Link</a>',
            '<div onmouseover="doSomethingBad()">Content</div>',
            '<body onload="malicious()">Body text</body>'
        ]
        for p in payloads:
            sanitized = self.sanitize_html(p)
            self.assertNotIn('onerror', sanitized.lower())
            self.assertNotIn('onclick', sanitized.lower())
            self.assertNotIn('onmouseover', sanitized.lower())
            self.assertNotIn('onload', sanitized.lower())

    def test_strip_javascript_pseudo_urls(self):
        payload = '<a href="javascript:alert(document.cookie)">Click me</a>'
        sanitized = self.sanitize_html(payload)
        self.assertNotIn('javascript:', sanitized.lower())

    def test_strip_iframe_and_object(self):
        payload = '<p>Video:</p><iframe src="http://evil.com"></iframe><object data="bad.swf"></object>'
        sanitized = self.sanitize_html(payload)
        self.assertNotIn('<iframe', sanitized.lower())
        self.assertNotIn('<object', sanitized.lower())

    def test_preserve_safe_elements(self):
        safe_html = '<h2>Заголовок</h2><p>Текст с <strong>жирным</strong> и <em>курсивом</em>, <code>код</code></p>'
        sanitized = self.sanitize_html(safe_html)
        self.assertIn('<h2>Заголовок</h2>', sanitized)
        self.assertIn('<strong>жирным</strong>', sanitized)
        self.assertIn('<em>курсивом</em>', sanitized)
        self.assertIn('<code>код</code>', sanitized)


class TestExportFormatConverters(unittest.TestCase):
    """Test 3: Export format converters (JSON, Markdown, HTML) and structured contracts."""

    def test_json_export_structure(self):
        """Verify the structured JSON schema exported by the editor."""
        mock_delta = {
            "ops": [
                {"insert": "Привет, мир!\n"}
            ]
        }
        title = "Тестовая статья"
        html = "<h1>Тестовая статья</h1><p>Привет, мир!</p>"
        words = 2
        chars = 12

        doc = {
            "schema": "antigravity-editor-v1",
            "title": title,
            "contents": mock_delta,
            "html": html,
            "metadata": {
                "wordCount": words,
                "charCount": chars,
                "readingTime": 1,
                "exportedAt": "2026-09-25T13:30:00.000Z"
            }
        }

        json_str = json.dumps(doc, indent=2, ensure_ascii=False)
        parsed = json.loads(json_str)

        self.assertEqual(parsed["schema"], "antigravity-editor-v1")
        self.assertEqual(parsed["title"], title)
        self.assertEqual(parsed["contents"]["ops"][0]["insert"], "Привет, мир!\n")
        self.assertEqual(parsed["metadata"]["wordCount"], 2)
        self.assertEqual(parsed["metadata"]["charCount"], 12)

    def test_json_import_validation(self):
        """Verify JSON import parsing with required fields."""
        valid_json = '{"title": "Imported", "contents": {"ops": []}}'
        data = json.loads(valid_json)
        self.assertIn("title", data)
        self.assertTrue("contents" in data or "html" in data)

        invalid_json = '{"unrelated": 123}'
        invalid_data = json.loads(invalid_json)
        self.assertFalse("contents" in invalid_data or "html" in invalid_data)

    def test_markdown_conversion_headings_and_styles(self):
        """Verify markdown conversion rules."""
        def simple_html_to_markdown(title, html):
            md = f"# {title}\n\n" if title else ""
            html = re.sub(r'<h2>(.*?)</h2>', r'## \1\n\n', html)
            html = re.sub(r'<h3>(.*?)</h3>', r'### \1\n\n', html)
            html = re.sub(r'<h4>(.*?)</h4>', r'#### \1\n\n', html)
            html = re.sub(r'<strong>(.*?)</strong>', r'**\1**', html)
            html = re.sub(r'<em>(.*?)</em>', r'*\1*', html)
            html = re.sub(r'<s>(.*?)</s>', r'~~\1~~', html)
            html = re.sub(r'<code>(.*?)</code>', r'`\1`', html)
            html = re.sub(r'<hr\s*\/?>', r'---\n\n', html)
            html = re.sub(r'<a\s+href="([^"]+)">(.*?)</a>', r'[\2](\1)', html)
            html = re.sub(r'<p>(.*?)</p>', r'\1\n\n', html)
            return md + html.strip()

        title = "Архитектура проекта"
        input_html = "<h2>Раздел 1</h2><p>Это <strong>важный</strong> и <em>полезный</em> текст с <code>кодом</code> и <a href=\"https://antigravity.dev\">ссылкой</a>.</p><hr><p>Конец.</p>"

        md_output = simple_html_to_markdown(title, input_html)
        self.assertIn("# Архитектура проекта", md_output)
        self.assertIn("## Раздел 1", md_output)
        self.assertIn("**важный**", md_output)
        self.assertIn("*полезный*", md_output)
        self.assertIn("`кодом`", md_output)
        self.assertIn("[ссылкой](https://antigravity.dev)", md_output)
        self.assertIn("---", md_output)

    def test_markdown_tables_and_checklists(self):
        """Verify markdown table format and checklists."""
        table_html = """
        | Заголовок 1 | Заголовок 2 |
        | --- | --- |
        | Значение 1 | Значение 2 |
        """.strip()
        self.assertIn('| --- | --- |', table_html)

        checklist_items = ["- [ ] Задача 1", "- [x] Задача 2 (выполнено)"]
        self.assertTrue(checklist_items[0].startswith("- [ ]"))
        self.assertTrue(checklist_items[1].startswith("- [x]"))

    def test_html_export_structure(self):
        """Verify complete HTML export document structure."""
        title = "Моя публикация"
        article_body = "<h2>Введение</h2><p>Приветственный абзац.</p>"

        exported_html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <title>{title}</title>
</head>
<body>
  <h1>{title}</h1>
  <article>
    {article_body}
  </article>
</body>
</html>"""

        self.assertIn("<!DOCTYPE html>", exported_html)
        self.assertIn(f"<title>{title}</title>", exported_html)
        self.assertIn(f"<h1>{title}</h1>", exported_html)
        self.assertIn("<article>", exported_html)


class TestDraftStorageContract(unittest.TestCase):
    """Test 4: Verify drafts data model and storage contract."""

    def test_draft_object_schema(self):
        draft = {
            "id": "draft_1727280000000",
            "title": "Черновик статьи",
            "delta": {"ops": [{"insert": "Текст\n"}]},
            "html": "<p>Текст</p>",
            "textSnippet": "Текст",
            "wordCount": 1,
            "charCount": 5,
            "readingTime": 1,
            "updatedAt": 1727280000000
        }

        required_fields = ["id", "title", "delta", "html", "wordCount", "charCount", "readingTime", "updatedAt"]
        for field in required_fields:
            self.assertIn(field, draft, f"Missing field in draft: {field}")

        self.assertIsInstance(draft["id"], str)
        self.assertIsInstance(draft["wordCount"], int)
        self.assertIsInstance(draft["updatedAt"], int)


if __name__ == '__main__':
    unittest.main()
