#!/usr/bin/env python3
"""
tests/test_issue284_starter_content.py

Issue #284: demo content is gone from the product code; tests run on the real starter content.
The five starter authors (tests/fixtures/starter_content.py) publish one publication and one
question each through the real API, and every rich block renders on the published pages.
"""

import os
import re
import shutil
import sqlite3
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
from server import create_server, init_db, reset_login_rate_limiter
from tests.fixtures import starter_content
from tests.http_client import Client

FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")
BROWSER_SMOKE = True  # collected by tests/run_browser_smoke.py


def read(path):
    with open(os.path.join(PROJECT_ROOT, path), encoding="utf-8") as f:
        return f.read()


class TestNoDemoContentInProductCode(unittest.TestCase):
    def test_product_code_has_no_demo_materials(self):
        for path in ("frontend/public/js/feed.js", "frontend/public/js/article.js"):
            js = read(path)
            self.assertNotIn("FALLBACK_ARTICLES", js, path)
            self.assertNotIn("isDemo: true", js, path)
            self.assertNotIn("Алексей Смирнов", js, path)
        for root in ("backend",):
            for dirpath, _, files in os.walk(os.path.join(PROJECT_ROOT, root)):
                for name in files:
                    if name.endswith(".py"):
                        src = read(os.path.relpath(os.path.join(dirpath, name), PROJECT_ROOT))
                        self.assertIsNone(re.search(r"\bimport seed_data\b|from backend\.seeds\b", src),
                                          "demo seed import in " + name)
        self.assertNotIn("--seed", read("server.py"))

    def test_starter_fixture_covers_every_rich_block(self):
        self.assertEqual(len(starter_content.AUTHORS), 5)
        html = "".join(a["publication"]["html"] for a in starter_content.AUTHORS)
        for marker in ('class="editor-figure', "<figcaption>", 'class="editor-block-formula" data-latex=',
                       'class="editor-inline-formula" data-latex=', "<blockquote>", "<table>",
                       '<pre class="ql-syntax"', 'class="editor-spoiler"', "<h2>", "<ol>", "<ul>"):
            self.assertIn(marker, html)
        self.assertEqual(len({a["login"] for a in starter_content.AUTHORS}), 5)
        self.assertTrue(all(a["email"].endswith("@example.com") for a in starter_content.AUTHORS))


@unittest.skipUnless(PLAYWRIGHT_AVAILABLE and os.environ.get("RUN_BROWSER_SMOKE") == "1",
                     "Browser smoke test enabled via RUN_BROWSER_SMOKE=1 and Playwright")
class TestStarterContentPublished(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "starter.db")
        server.DEFAULT_DB_PATH = cls.db_path
        init_db(cls.db_path, seed=False).close()
        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR, seed=False,
                                  enforce_csrf=True, media_dir=os.path.join(cls.temp_dir, "media"))
        cls.base = "http://127.0.0.1:%d" % cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        reset_login_rate_limiter()
        cls.authors = starter_content.publish_starter_content(cls.base, cls.db_path)
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

    def test_ten_materials_with_zero_rating_and_likes(self):
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute("SELECT publication_settings FROM moderation_submissions WHERE status = 'approved'").fetchall()
            kinds = sorted("question" if '"materialType": "question"' in r[0] else "publication" for r in rows)
            self.assertEqual(kinds, ["publication"] * 5 + ["question"] * 5)
            for table in ("article_likes", "article_votes", "article_comments"):
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0], 0, table)
        finally:
            conn.close()
        guest = Client(self.base)
        for a in self.authors:
            status, body = guest.request("GET", "/api/articles/" + a["publication"])
            self.assertEqual(status, 200)
            art = body["article"]
            self.assertEqual((art.get("likesCount", 0), art.get("score", 0)), (0, 0), a["login"])
            self.assertTrue(art.get("coverImage", "").startswith("/media/"), a["login"])

    def test_every_rich_block_renders(self):
        ctx = self.browser.new_context(viewport={"width": 1280, "height": 900})
        try:
            page = ctx.new_page()
            for a, src in zip(self.authors, starter_content.AUTHORS):
                html = src["publication"]["html"]
                expected = {
                    "figures": html.count('class="editor-figure'),
                    "formulas": html.count('class="editor-block-formula"') + html.count('class="editor-inline-formula"'),
                    "spoilers": html.count('class="editor-spoiler"'),
                    "tables": html.count("<table>"),
                    "code": html.count('<pre class="ql-syntax"'),
                    "quotes": html.count("<blockquote>"),
                }
                page.goto(self.base + "/article.html?id=" + a["publication"], wait_until="networkidle")
                page.wait_for_selector(".article-body-content h2", timeout=10000)
                if expected["formulas"]:
                    page.wait_for_function("(n) => document.querySelectorAll('.article-body-content .is-rendered').length >= n",
                                           arg=expected["formulas"], timeout=10000)
                got = page.evaluate("""() => { const r = document.querySelector('.article-body-content');
                    return {figures: r.querySelectorAll('.editor-figure figcaption').length,
                            formulas: r.querySelectorAll('.editor-block-formula.is-rendered, .editor-inline-formula.is-rendered').length,
                            spoilers: r.querySelectorAll('details.editor-spoiler > summary').length,
                            tables: r.querySelectorAll('table').length, code: r.querySelectorAll('pre').length,
                            quotes: r.querySelectorAll('blockquote').length,
                            errors: r.querySelectorAll('.formula-error').length, raw: r.textContent.includes('$$'),
                            images: [...r.querySelectorAll('img')].every(i => i.complete && i.naturalWidth > 0)}; }""")
                self.assertEqual(got, dict(expected, errors=0, raw=False, images=True), a["login"])
        finally:
            ctx.close()

    def test_author_signs_in_with_email_and_mobile_layout_holds(self):
        a = self.authors[2]
        ctx = self.browser.new_context(viewport={"width": 375, "height": 800})
        try:
            page = ctx.new_page()
            page.goto(self.base + "/article.html?id=" + self.authors[0]["publication"], wait_until="networkidle")
            page.wait_for_selector(".article-body-content table", timeout=10000)
            self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth"),
                            "no horizontal page scroll with a table, code and formulas at 375 px")
            page.evaluate("window.SCAuth.openModal('login')")
            page.fill("#login-identifier", a["email"])
            page.fill("#login-password", starter_content.TEST_PASSWORD)
            page.locator("#scAuthModal .sc-auth-submit").first.click()
            page.wait_for_function("() => window.SCAuth && window.SCAuth.currentUser", timeout=8000)
            self.assertEqual(page.evaluate("window.SCAuth.currentUser.id"), a["id"])
        finally:
            ctx.close()


if __name__ == "__main__":
    unittest.main()
