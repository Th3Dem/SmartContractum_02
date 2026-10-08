#!/usr/bin/env python3
"""
tests/test_issue262_admin_mobile.py

Issue #262: the moderation panel (admin.html) was wider than 320-360 px phones:
the page grew to the width of the tab row, so the users tab, the search and the
queue items left the screen. The tab row now scrolls inside itself, the filter
and the search stack, and the page cannot grow wider than the screen.

Static checks always run. The browser checks run with RUN_BROWSER_SMOKE=1 and
Playwright; set PLAYWRIGHT_CDP_URL to drive an already running Chromium.
"""

import datetime
import os
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
BROWSER_SMOKE = True  # collected by tests/run_browser_smoke.py
PHONE_WIDTHS = [320, 360, 375]


class TestIssue262Static(unittest.TestCase):
    def test_phone_rules_keep_the_page_inside_the_screen(self):
        with open(os.path.join(FRONTEND_DIR, "css", "moderation.css"), encoding="utf-8") as f:
            css = f.read()
        block = css[css.index("Issue #262"):]
        self.assertIn("@media (max-width: 480px)", block)
        self.assertRegex(block, r"\.mod-page,\s*\.mod-page > \*,\s*\.mod-topbar > \* \{\s*min-width: 0;")
        self.assertRegex(block, r"\.mod-tabs \{[^}]*overflow-x: auto;")
        self.assertRegex(block, r"\.mod-toolbar-right \{\s*flex-direction: column;")


@unittest.skipUnless(PLAYWRIGHT_AVAILABLE and os.environ.get("RUN_BROWSER_SMOKE") == "1",
                     "Browser smoke test enabled via RUN_BROWSER_SMOKE=1 and Playwright")
class TestIssue262Browser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "issue262.db")
        server.DEFAULT_DB_PATH = cls.db_path
        init_db(cls.db_path, seed=True).close()
        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        user_id = create_user(conn, "panel_admin", "panel_admin@example.com", "Panel-pass-1", email_verified=True)["id"]
        cls.token = secrets.token_hex(32)
        now = datetime.datetime.now(datetime.timezone.utc)
        with conn:
            conn.execute("UPDATE users SET role = 'admin' WHERE id = ?", (user_id,))
            conn.execute("""INSERT INTO sessions (token, user_id, user_name, user_role, created_at, expires_at, is_revoked)
                            VALUES (?, ?, 'panel_admin', 'admin', ?, ?, 0)""",
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

    def open(self, width):
        touch = width < 1024
        ctx = self.browser.new_context(viewport={"width": width, "height": 800}, is_mobile=touch, has_touch=touch)
        ctx.add_cookies([{"name": "sc_session", "value": self.token, "url": self.base}])
        page = ctx.new_page()
        page.goto(self.base + "/admin.html", wait_until="networkidle")
        page.wait_for_selector("#tabUsersBtn:not([hidden])", timeout=5000)
        page.wait_for_timeout(200)
        return ctx, page

    def test_panel_fits_phones_and_every_tab_switches(self):
        for width in PHONE_WIDTHS:
            with self.subTest(width=width):
                ctx, page = self.open(width)
                try:
                    overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
                    controls = page.evaluate("""() => ['typeFilter', 'queueSearch'].map(id => {
                      const b = document.getElementById(id).getBoundingClientRect();
                      return {left: b.left, right: b.right, h: Math.round(b.height)};
                    })""")
                    switched = []
                    for tab, section in (("log", "sectionLog"), ("users", "sectionUsers"), ("queue", "sectionQueue")):
                        button = page.locator('.mod-tab[data-tab="%s"]' % tab)
                        button.scroll_into_view_if_needed()
                        box = button.bounding_box()
                        inside = box["x"] >= -0.5 and box["x"] + box["width"] <= width + 0.5
                        button.tap()
                        page.wait_for_timeout(300)
                        switched.append((tab, inside, round(box["height"]), button.get_attribute("aria-selected"),
                                         page.locator("#" + section).is_visible()))
                        self.assertLessEqual(page.evaluate(
                            "document.documentElement.scrollWidth - document.documentElement.clientWidth"), 0, tab)
                finally:
                    ctx.close()
                self.assertLessEqual(overflow, 0, "admin page scrolls sideways")
                for c in controls:
                    self.assertTrue(c["left"] >= 0 and c["right"] <= width, c)
                    self.assertEqual(c["h"], 34)
                for tab, inside, height, selected, visible in switched:
                    self.assertTrue(inside, tab)
                    self.assertTrue(32 <= height <= 34, (tab, height))
                    self.assertEqual(selected, "true", tab)
                    self.assertTrue(visible, tab)

    def test_desktop_layout_unchanged(self):
        ctx, page = self.open(1280)
        try:
            r = page.evaluate("""() => {
              const f = document.getElementById('typeFilter').getBoundingClientRect();
              const s = document.getElementById('queueSearch').getBoundingClientRect();
              const tabs = [...document.querySelectorAll('.mod-tab')].map(t => Math.round(t.getBoundingClientRect().top));
              return {sameRow: Math.round(f.top) === Math.round(s.top), filterLeft: f.right <= s.left, tabsRow: new Set(tabs).size};
            }""")
        finally:
            ctx.close()
        self.assertTrue(r["sameRow"] and r["filterLeft"], r)
        self.assertEqual(r["tabsRow"], 1)


if __name__ == "__main__":
    unittest.main()
