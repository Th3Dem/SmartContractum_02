#!/usr/bin/env python3
"""
tests/test_issue263_formulas.py

Issue #263: formulas in articles were shown as raw LaTeX ($$...$$, \\(...\\)).
They are now drawn with the vendored KaTeX (frontend/public/vendor/katex,
no CDN) by js/formula-render.js in the article, the editor and the formula
dialog. The storage format does not change: saved HTML keeps the LaTeX text
and data-latex, without KaTeX markup.

Static checks always run. The browser checks run with RUN_BROWSER_SMOKE=1 and
Playwright; set PLAYWRIGHT_CDP_URL to drive an already running Chromium.
"""

import os
import re
import shutil
import sys
import tempfile
import threading
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

import server
from server import create_server, init_db

FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")
BROWSER_SMOKE = True  # collected by tests/run_browser_smoke.py
KATEX_DIR = os.path.join(FRONTEND_DIR, "vendor", "katex")
PAGES = ("article.html", "editor.html", "question-editor.html")


def read(rel_path):
    with open(os.path.join(FRONTEND_DIR, rel_path), encoding="utf-8") as f:
        return f.read()


class TestIssue263Static(unittest.TestCase):
    def test_katex_is_vendored_with_its_woff2_fonts(self):
        for name in ("katex.min.js", "katex.min.css", "LICENSE"):
            self.assertTrue(os.path.isfile(os.path.join(KATEX_DIR, name)), name)
        css = read("vendor/katex/katex.min.css")
        fonts = set(re.findall(r"url\((fonts/[^)]+\.woff2)\)", css))
        self.assertGreater(len(fonts), 10)
        for font in fonts:
            self.assertTrue(os.path.isfile(os.path.join(KATEX_DIR, font)), font)

    def test_vendored_files_make_no_network_requests(self):
        js = read("vendor/katex/katex.min.js")
        urls = set(re.findall(r"https?://[^\"'\s)]+", js))
        self.assertTrue(urls <= {"http://www.w3.org/1998/Math/MathML", "http://www.w3.org/2000/svg"}, urls)
        self.assertNotRegex(read("vendor/katex/katex.min.css"), r"url\(\s*['\"]?(https?:)?//")

    def test_pages_load_katex_and_the_renderer(self):
        for page in PAGES:
            with self.subTest(page=page):
                html = read(page)
                self.assertIn('<link rel="stylesheet" href="vendor/katex/katex.min.css">', html)
                katex = html.index('<script src="vendor/katex/katex.min.js"></script>')
                renderer = html.index('<script src="js/formula-render.js"></script>')
                self.assertLess(katex, renderer)
                first_app_script = min(html.index(s) for s in ('src="js/core.js', 'src="js/article.js') if s in html)
                self.assertLess(renderer, first_app_script, "renderer is loaded before the page scripts")

    def test_article_sanitizer_keeps_the_formula_source(self):
        self.assertIn("if (tagName === 'div' || tagName === 'span') allowedAttrs.push('data-latex');", read("js/article.js"))

    def test_saved_html_goes_through_the_source_converter(self):
        for path, count in (("js/drafts.js", 1), ("js/publication.js", 2), ("js/converter.js", 3), ("js/question-editor.js", 2)):
            with self.subTest(path=path):
                self.assertEqual(read(path).count("window.SCFormula.sourceHtml("), count)


ARTICLE_JS = """() => {
  const root = document.getElementById('articleContentWrap');
  const blocks = [...root.querySelectorAll('.editor-block-formula')];
  const inline = [...root.querySelectorAll('.editor-inline-formula')];
  const box = blocks.length ? blocks[0].querySelector('.formula-rendered') : null;
  return {
    raw: (root.innerText.match(/\\$\\$|\\\\\\(/g) || []).length,
    rendered: [...blocks, ...inline].every(e => e.classList.contains('is-rendered') && e.querySelector('.katex')),
    count: blocks.length + inline.length,
    font: getComputedStyle(root.querySelector('.katex .mathnormal')).fontFamily,
    textFont: getComputedStyle(root.querySelector('p')).fontFamily,
    blockInside: box ? box.getBoundingClientRect().right <= document.documentElement.clientWidth + 0.5 : null,
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  };
}"""


@unittest.skipUnless(PLAYWRIGHT_AVAILABLE and os.environ.get("RUN_BROWSER_SMOKE") == "1",
                     "Browser smoke test enabled via RUN_BROWSER_SMOKE=1 and Playwright")
class TestIssue263Browser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "issue263.db")
        server.DEFAULT_DB_PATH = cls.db_path
        init_db(cls.db_path, seed=True).close()
        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR, seed=False)
        cls.base = "http://127.0.0.1:%d" % cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.pw = sync_playwright().start()
        cdp = os.environ.get("PLAYWRIGHT_CDP_URL")
        if cdp:
            cls.browser = cls.pw.chromium.connect_over_cdp(cdp)
        else:
            cls.browser = cls.pw.chromium.launch(
                headless=True, args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.httpd.shutdown()
        cls.httpd.server_close()
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def open(self, width, path):
        touch = width < 1024
        ctx = self.browser.new_context(viewport={"width": width, "height": 900}, is_mobile=touch, has_touch=touch)
        page = ctx.new_page()
        external, errors = [], []
        page.on("request", lambda r: external.append(r.url) if not r.url.startswith(self.base) and not r.url.startswith("data:") else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(self.base + path, wait_until="networkidle")
        page.wait_for_timeout(300)
        return ctx, page, external, errors

    def test_article_formulas_are_drawn_on_phone_and_desktop(self):
        for width in (320, 375, 1280):
            with self.subTest(width=width):
                ctx, page, external, errors = self.open(width, "/article.html?id=art-01")
                try:
                    page.evaluate("document.fonts.ready")
                    r = page.evaluate(ARTICLE_JS)
                finally:
                    ctx.close()
                self.assertEqual(r["raw"], 0, "no $$ or \\( left in the text")
                self.assertEqual(r["count"], 2, "art-01 has one block and one inline formula")
                self.assertTrue(r["rendered"])
                self.assertEqual(r["font"], "KaTeX_Math")
                self.assertIn("Onest", r["textFont"], "the rest of the page keeps Onest")
                self.assertTrue(r["blockInside"], "long formulas scroll inside their box")
                self.assertLessEqual(r["overflow"], 0)
                self.assertEqual(external, [])
                self.assertEqual(errors, [])

    def test_editor_draws_formulas_and_saves_the_latex_source(self):
        ctx, page, external, errors = self.open(1280, "/editor.html")
        try:
            page.locator("#article-title").fill("Формулы в редакторе")
            page.evaluate("window.EditorApp.Toolbar.openFormulaModal(null, 0, true, '')")
            page.locator("#formula-input").fill("\\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}")
            preview_ok = page.evaluate("() => !!document.querySelector('#formula-live-preview .katex')")
            page.locator("#formula-input").fill("\\frac{1}{")
            preview_bad = page.evaluate("""() => { const e = document.getElementById('formula-live-preview');
              return {error: e.classList.contains('formula-error'), katex: !!e.querySelector('.katex'), text: e.textContent}; }""")
            page.locator("#formula-input").fill("\\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}")
            page.evaluate("window.EditorApp.Toolbar.saveFormula()")
            page.evaluate("""() => { const q = window.EditorApp.editor;
              q.insertEmbed(q.getLength() - 1, 'inlineFormula', {latex: 'E=mc^2'}, 'user');
              q.insertEmbed(q.getLength() - 1, 'inlineFormula', {latex: '\\\\frac{1}{'}, 'user'); }""")
            page.wait_for_timeout(300)
            r = page.evaluate("""() => {
              const root = window.EditorApp.editor.root;
              const published = window.EditorApp.Converter.sanitizeHTML(window.SCFormula.sourceHtml(root));
              return {
                block: root.querySelector('.editor-block-formula').className,
                inline: [...root.querySelectorAll('.editor-inline-formula')].map(e => e.className),
                font: getComputedStyle(root.querySelector('.katex .mathnormal')).fontFamily,
                publishedKatex: published.includes('katex'),
                publishedLatex: published.includes('data-latex="\\\\frac{-b \\\\pm \\\\sqrt{b^2-4ac}}{2a}"'),
                publishedText: published.includes('$$') && published.includes('\\\\(E=mc^2\\\\)'),
              };
            }""")
        finally:
            ctx.close()
        self.assertTrue(preview_ok)
        self.assertEqual((preview_bad["error"], preview_bad["katex"]), (True, False))
        self.assertIn("\\frac{1}{", preview_bad["text"], "a broken formula shows its source")
        self.assertIn("is-rendered", r["block"])
        self.assertIn("is-rendered", r["inline"][0])
        self.assertIn("formula-error", r["inline"][1])
        self.assertEqual(r["font"], "KaTeX_Math")
        self.assertFalse(r["publishedKatex"], "saved HTML has no KaTeX markup")
        self.assertTrue(r["publishedLatex"])
        self.assertTrue(r["publishedText"])
        self.assertEqual(external, [])
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
