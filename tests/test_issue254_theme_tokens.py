#!/usr/bin/env python3
"""
tests/test_issue254_theme_tokens.py

Issue #254: styles must not depend on CSS variables that are never declared.
An undefined var() without a fallback makes the declaration invalid, so the
element became transparent: the article rail and TOC in the light theme, and
the notifications popup in the dark theme (notifications.css overrode the
theme.css background with var(--bg-primary)).

Static checks always run. The browser checks run with RUN_BROWSER_SMOKE=1 and
Playwright; set PLAYWRIGHT_CDP_URL to drive an already running Chromium
instead of launching one.
"""

import datetime
import glob
import os
import re
import secrets
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
from server import create_server, create_user, init_db

FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")
# Variables set from JavaScript at runtime (style.setProperty) are declared there
RUNTIME_VARS = {"--phone-w", "--phone-h", "--phone-radius", "--phone-bezel-w", "--feed-header-total-height"}
TRANSPARENT = ("rgba(0, 0, 0, 0)", "transparent")


def sources():
    files = glob.glob(os.path.join(FRONTEND_DIR, "css", "*.css")) + glob.glob(os.path.join(FRONTEND_DIR, "*.html"))
    return {f: open(f, encoding="utf-8").read() for f in files}


class TestIssue254Static(unittest.TestCase):
    def test_every_var_without_fallback_is_declared(self):
        texts = sources()
        declared = set()
        for text in texts.values():
            declared |= set(re.findall(r"(--[\w-]+)\s*:", text))
        missing = []
        for path, text in texts.items():
            for name, fallback in re.findall(r"var\(\s*(--[\w-]+)\s*(,)?", text):
                if not fallback and name not in declared and name not in RUNTIME_VARS:
                    missing.append("%s in %s" % (name, os.path.relpath(path, FRONTEND_DIR)))
        self.assertEqual(sorted(set(missing)), [])

    def test_surface_1_is_declared_for_both_themes(self):
        css = open(os.path.join(FRONTEND_DIR, "css", "theme.css"), encoding="utf-8").read()
        self.assertIn("--surface-1: #ffffff;", css)
        self.assertIn("--surface-1: #1e293b;", css, "dark keeps the value its rules already used")


@unittest.skipUnless(PLAYWRIGHT_AVAILABLE and os.environ.get("RUN_BROWSER_SMOKE") == "1",
                     "Browser smoke test enabled via RUN_BROWSER_SMOKE=1 and Playwright")
class TestIssue254Browser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "issue254.db")
        server.DEFAULT_DB_PATH = cls.db_path
        init_db(cls.db_path, seed=True).close()
        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        user_id = create_user(conn, "theme_reader", "theme_reader@example.com", "Theme-pass-1", email_verified=True)["id"]
        cls.token = secrets.token_hex(32)
        now = datetime.datetime.now(datetime.timezone.utc)
        with conn:
            conn.execute("""INSERT INTO sessions (token, user_id, user_name, user_role, created_at, expires_at, is_revoked)
                            VALUES (?, ?, 'theme_reader', 'user', ?, ?, 0)""",
                         (cls.token, user_id, now.isoformat(), (now + datetime.timedelta(days=1)).isoformat()))
        conn.close()
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

    def open(self, theme, path, signed_in=False):
        ctx = self.browser.new_context(viewport={"width": 1440, "height": 900})
        ctx.add_init_script("localStorage.setItem('sc_theme', '%s')" % theme)
        if signed_in:
            ctx.add_cookies([{"name": "sc_session", "value": self.token, "url": self.base}])
        page = ctx.new_page()
        page.goto(self.base + path, wait_until="networkidle")
        page.wait_for_timeout(200)
        self.assertEqual(page.evaluate("document.documentElement.getAttribute('data-theme')"), theme)
        return ctx, page

    def background(self, page, selector):
        return page.evaluate("(s) => getComputedStyle(document.querySelector(s)).backgroundColor", selector)

    def test_article_rail_and_toc_have_a_background_in_both_themes(self):
        for theme in ("light", "dark"):
            with self.subTest(theme=theme):
                ctx, page = self.open(theme, "/article.html?id=art-01")
                try:
                    for selector in (".article-action-rail", ".article-sidebar-toc", ".article-toc-accordion"):
                        bg = self.background(page, selector)
                        self.assertNotIn(bg, TRANSPARENT, "%s %s" % (selector, theme))
                        if theme == "dark":
                            self.assertEqual(bg, "rgb(30, 41, 59)", "dark look unchanged")
                finally:
                    ctx.close()

    def test_notifications_popup_is_opaque_in_both_themes(self):
        for theme in ("light", "dark"):
            with self.subTest(theme=theme):
                ctx, page = self.open(theme, "/feed.html", signed_in=True)
                try:
                    page.locator("#headerNotificationsBtn").click()
                    page.wait_for_selector(".header-notif-popup", state="visible", timeout=5000)
                    self.assertNotIn(self.background(page, ".header-notif-popup"), TRANSPARENT)
                finally:
                    ctx.close()


if __name__ == "__main__":
    unittest.main()
