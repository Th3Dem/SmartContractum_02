#!/usr/bin/env python3
"""
tests/test_issue280_rich_blocks.py

Issue #280: image captions, spoilers and formulas survive moderation. The server sanitizer
(/api/moderation/submit) and the article page allowlist keep figure/figcaption, details/summary
and data-latex, and still remove dangerous markup inside them.
"""

import base64
import os
import re
import shutil
import sqlite3
import struct
import sys
import tempfile
import threading
import unittest
import zlib

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

import server
from backend.content import sanitize_article_html
from server import create_server, create_user, init_db, reset_login_rate_limiter
from tests.http_client import Client, submission_payload

FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")
BROWSER_SMOKE = True  # collected by tests/run_browser_smoke.py
PASSWORD = "Rich-blocks-1"

RICH_HTML = (
    '<p>Вступление с формулой <span class="editor-inline-formula" data-latex="E = mc^2">\\(E = mc^2\\)</span> в тексте.</p>'
    '<figure class="editor-figure align-center"><img src="{src}" alt="Схема расчетов">'
    '<figcaption>Рис. 1. Схема атомарного расчета</figcaption></figure>'
    '<div class="editor-block-formula" data-latex="\\sum_{{i=1}}^{{n}} x_i = X">'
    '<div class="formula-rendered">$$\\sum_{{i=1}}^{{n}} x_i = X$$</div></div>'
    '<details class="editor-spoiler" open><summary class="editor-spoiler-title">Подробности реализации</summary>'
    '<div class="editor-spoiler-body"><p>Скрытый текст спойлера</p></div></details>'
)


def tiny_png(width=24, height=16):
    """A valid PNG without third-party libraries."""
    raw = b"".join(b"\x00" + bytes((40, 120, 220)) * width for _ in range(height))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class TestRichBlocksSanitizer(unittest.TestCase):
    def test_editor_blocks_survive(self):
        out = sanitize_article_html(RICH_HTML.format(src="/media/a.png"))
        self.assertIn('<figure class="editor-figure align-center"><img src="/media/a.png" alt="Схема расчетов">', out)
        self.assertIn("<figcaption>Рис. 1. Схема атомарного расчета</figcaption></figure>", out)
        self.assertIn('<details class="editor-spoiler" open="">', out)
        self.assertIn('<summary class="editor-spoiler-title">Подробности реализации</summary>', out)
        self.assertIn('data-latex="E = mc^2"', out)
        self.assertIn('data-latex="\\sum_{i=1}^{n} x_i = X"', out)

    def test_dangerous_markup_inside_new_blocks_is_removed(self):
        out = sanitize_article_html(
            '<figure onclick="steal()"><img src="javascript:alert(1)" onerror="x()"><figcaption>Подпись<script>alert(1)</script>'
            '</figcaption></figure><details open="evil" ontoggle="x()"><summary onclick="x()">S</summary></details>'
            '<span class="editor-inline-formula" data-latex="&quot;&gt;&lt;img src=x onerror=alert(1)&gt;">f</span>'
            '<p data-latex="x" style="color:red">p</p><a href="#" data-latex="x">a</a>')
        markup = re.sub(r'data-latex="[^"]*"', 'data-latex=""', out)
        for bad in ("onclick", "onerror", "ontoggle", "javascript:", "<script", "alert(1)", 'open="evil"', "style="):
            self.assertNotIn(bad, markup)
        self.assertIn('data-latex="&quot;&gt;&lt;img src=x onerror=alert(1)&gt;"', out, "LaTeX stays escaped text")
        self.assertNotIn("<img src=x", out)
        self.assertIn("<p>p</p>", out, "data-latex only on div and span")
        self.assertIn('<a href="#">a</a>', out)

    def test_latex_length_is_bounded(self):
        self.assertNotIn("data-latex", sanitize_article_html('<div data-latex="%s">x</div>' % ("a" * 4001)))
        self.assertIn("data-latex", sanitize_article_html('<div data-latex="%s">x</div>' % ("a" * 4000)))

    def test_article_page_allowlist(self):
        with open(os.path.join(FRONTEND_DIR, "js", "article.js"), encoding="utf-8") as f:
            js = f.read()
        self.assertIn("'figure', 'figcaption', 'details', 'summary'", js)
        self.assertIn("if (tagName === 'details') allowedAttrs.push('open');", js)
        with open(os.path.join(FRONTEND_DIR, "css", "article.css"), encoding="utf-8") as f:
            self.assertIn(".article-body-content .editor-figure figcaption", f.read())


@unittest.skipUnless(PLAYWRIGHT_AVAILABLE and os.environ.get("RUN_BROWSER_SMOKE") == "1",
                     "Browser smoke test enabled via RUN_BROWSER_SMOKE=1 and Playwright")
class TestRichBlocksPublishedPage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "rich.db")
        server.DEFAULT_DB_PATH = cls.db_path
        init_db(cls.db_path, seed=False).close()
        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        for login, role in (("rb_author", "user"), ("rb_mod", "moderator")):
            create_user(conn, login, login + "@example.com", PASSWORD, role=role, email_verified=True)
        conn.close()
        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR,
                                  seed=False, enforce_csrf=True, media_dir=os.path.join(cls.temp_dir, "media"))
        cls.base = "http://127.0.0.1:%d" % cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        reset_login_rate_limiter()
        author = Client(cls.base).login("rb_author", PASSWORD)
        mod = Client(cls.base).login("rb_mod", PASSWORD)
        status, up = author.request("POST", "/api/media/upload",
                                    {"image": "data:image/png;base64," + base64.b64encode(tiny_png()).decode()})
        assert status == 200, up
        payload = submission_payload("rich-280", title="Материал с формулами и спойлером")
        payload["html"] = RICH_HTML.format(src=up["url"])
        status, body = author.request("POST", "/api/moderation/submit", payload)
        assert status == 200, body
        cls.sid = body["submissionId"]
        status, body = mod.request("POST", "/api/admin/moderation/submissions/%s/decision" % cls.sid, {"decision": "approve"})
        assert status == 200, body
        cls.pw = sync_playwright().start()
        cdp = os.environ.get("PLAYWRIGHT_CDP_URL")
        cls.browser = cls.pw.chromium.connect_over_cdp(cdp) if cdp else cls.pw.chromium.launch(
            headless=True, args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.httpd.shutdown()
        cls.httpd.server_close()
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_published_page_renders_caption_spoiler_and_formulas(self):
        for width in (375, 1280):
            ctx = self.browser.new_context(viewport={"width": width, "height": 900})
            try:
                page = ctx.new_page()
                page.goto(self.base + "/article.html?id=" + self.sid, wait_until="networkidle")
                page.wait_for_selector(".article-body-content .editor-figure figcaption", timeout=10000)
                page.wait_for_function("() => document.querySelectorAll('.article-body-content .katex').length >= 2", timeout=10000)
                r = page.evaluate("""() => {
                    const root = document.querySelector('.article-body-content');
                    const fig = root.querySelector('.editor-figure'); const img = fig.querySelector('img');
                    const cap = fig.querySelector('figcaption');
                    const det = root.querySelector('details.editor-spoiler');
                    det.querySelector('summary').click();
                    return {capBelow: cap.getBoundingClientRect().top >= img.getBoundingClientRect().bottom - 1,
                            capText: cap.textContent, imgLoaded: img.naturalWidth > 0,
                            spoilerToggles: det.open === false,
                            blockRendered: root.querySelector('.editor-block-formula').classList.contains('is-rendered'),
                            inlineRendered: root.querySelector('.editor-inline-formula').classList.contains('is-rendered'),
                            rawLeft: root.textContent.includes('$$'),
                            hs: document.documentElement.scrollWidth > document.documentElement.clientWidth};
                }""")
                self.assertEqual(r, {"capBelow": True, "capText": "Рис. 1. Схема атомарного расчета", "imgLoaded": True,
                                     "spoilerToggles": True, "blockRendered": True, "inlineRendered": True,
                                     "rawLeft": False, "hs": False}, width)
            finally:
                ctx.close()


if __name__ == "__main__":
    unittest.main()
