#!/usr/bin/env python3
"""
tests/test_issue282_feed_avatar.py

Issue #282: the initials avatar on feed cards is also an author card trigger (#271); the shared
.btn-author-profile button reset must not strip its gradient, size and white initials.
"""

import os
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
from backend.db import update_submission_status
from server import create_server, create_user, init_db, reset_login_rate_limiter
from tests.http_client import Client, submission_payload

FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")
BROWSER_SMOKE = True  # collected by tests/run_browser_smoke.py


class TestFeedAvatarStatic(unittest.TestCase):
    def test_trigger_avatar_rule_follows_the_button_reset(self):
        with open(os.path.join(FRONTEND_DIR, "css", "feed.css"), encoding="utf-8") as f:
            css = f.read()
        reset = css.index(".btn-author-profile {")
        restore = css.index(".author-avatar.btn-author-profile {")
        self.assertGreater(restore, reset, "the avatar rule must come after the button reset")
        block = css[restore:css.index("}", restore)]
        self.assertIn("background: linear-gradient", block)
        self.assertIn("display: flex", block)


@unittest.skipUnless(PLAYWRIGHT_AVAILABLE and os.environ.get("RUN_BROWSER_SMOKE") == "1",
                     "Browser smoke test enabled via RUN_BROWSER_SMOKE=1 and Playwright")
class TestFeedAvatarBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "avatar.db")
        server.DEFAULT_DB_PATH = cls.db_path
        init_db(cls.db_path, seed=False).close()
        import sqlite3
        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        create_user(conn, "avatar_author", "avatar_author@example.com", "Avatar-pass-1", email_verified=True)
        conn.close()
        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR,
                                  seed=False, enforce_csrf=True)
        cls.base = "http://127.0.0.1:%d" % cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        reset_login_rate_limiter()
        author = Client(cls.base).login("avatar_author", "Avatar-pass-1")
        status, body = author.request("POST", "/api/moderation/submit", submission_payload("avatar-282"))
        assert status == 200, body
        assert update_submission_status(body["submissionId"], "approved", db_path=cls.db_path)
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

    def test_initials_avatar_keeps_its_look_and_opens_the_card(self):
        for theme in ("dark", "light"):
            ctx = self.browser.new_context(viewport={"width": 1280, "height": 900})
            ctx.add_init_script("localStorage.setItem('sc_theme', '%s')" % theme)
            try:
                page = ctx.new_page()
                page.goto(self.base + "/feed.html", wait_until="networkidle")
                page.wait_for_function("""() => [...document.querySelectorAll('.author-avatar.btn-author-profile')]
                    .some(a => !a.querySelector('img'))""", timeout=10000)
                handle = page.evaluate_handle("""() => [...document.querySelectorAll('.author-avatar.btn-author-profile')]
                    .find(a => !a.querySelector('img'))""")
                handle.as_element().scroll_into_view_if_needed()
                handle.as_element().hover()
                page.wait_for_timeout(100)
                s = page.evaluate("""(a) => { const c = getComputedStyle(a); const r = a.getBoundingClientRect();
                    return {bg: c.backgroundImage, color: c.color, display: c.display, deco: c.textDecorationLine,
                            w: Math.round(r.width), h: Math.round(r.height)}; }""", handle)
                self.assertIn("gradient", s["bg"], theme)
                self.assertEqual(s["color"], "rgb(255, 255, 255)", theme)
                self.assertEqual((s["display"], s["w"], s["h"]), ("flex", 34, 34), theme)
                self.assertEqual(s["deco"], "none", theme)
                handle.as_element().click()
                page.wait_for_function("() => { const c = document.getElementById('authorCard'); return c && !c.hidden; }",
                                       timeout=5000)
            finally:
                ctx.close()


if __name__ == "__main__":
    unittest.main()
