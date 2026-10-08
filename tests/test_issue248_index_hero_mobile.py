#!/usr/bin/env python3
"""
tests/test_issue248_index_hero_mobile.py

Issue #248: the home page (index.html) must not scroll sideways on phones.
The hero title scales with the screen, the hero buttons stack below 600px,
and the badge shows product text instead of internal notes. The desktop hero
does not change apart from the badge text.

Static checks always run. The browser checks run with RUN_BROWSER_SMOKE=1 and
Playwright; set PLAYWRIGHT_CDP_URL to drive an already running Chromium
instead of launching one.
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
PHONE_WIDTHS = [320, 360, 375, 414]


def read(rel_path):
    with open(os.path.join(FRONTEND_DIR, rel_path), encoding="utf-8") as f:
        return f.read()


class TestIssue248Static(unittest.TestCase):
    def setUp(self):
        self.html = read("index.html")

    def test_title_scales_with_the_screen(self):
        rule = re.search(r"\.hero-title \{([^}]*)\}", self.html)
        self.assertIsNotNone(rule)
        self.assertIn("font-size: clamp(1.75rem, 8.5vw, 3rem);", rule.group(1))

    def test_buttons_stack_on_phones(self):
        block = self.html[self.html.index("@media (max-width: 600px) {"):]
        self.assertRegex(block, r"\.hero-actions \{\s*flex-direction: column;")
        self.assertRegex(block, r"\.btn-hero \{[^}]*height: 34px;")

    def test_badge_has_product_text(self):
        badge = re.search(r'<div class="hero-badge">(.*?)</div>', self.html, re.S).group(1)
        self.assertNotIn("Quill", badge)
        self.assertNotIn("Offline-First", badge)
        self.assertNotIn("Референс", badge)
        self.assertIn("смарт-контрактов", badge)


HERO_JS = """() => {
  const vw = document.documentElement.clientWidth;
  const title = document.querySelector('.hero-title');
  const range = document.createRange();
  range.selectNodeContents(title);
  const lines = [...range.getClientRects()];
  const buttons = [...document.querySelectorAll('.btn-hero')].map(b => {
    const r = b.getBoundingClientRect();
    const cs = getComputedStyle(b);
    return {left: r.left, right: r.right, top: Math.round(r.top), h: Math.round(r.height),
            padding: cs.paddingTop + ' ' + cs.paddingLeft, font: cs.fontSize};
  });
  const out = [...document.querySelectorAll('main *')].filter(e => {
    const r = e.getBoundingClientRect();
    return r.width > 0 && (r.right > vw + 0.5 || r.left < -0.5);
  }).map(e => String(e.getAttribute('class')));
  return {vw, overflow: document.documentElement.scrollWidth - vw,
          titleLeft: Math.min(...lines.map(r => r.left)), titleRight: Math.max(...lines.map(r => r.right)),
          fontSize: parseFloat(getComputedStyle(title).fontSize), buttons, out};
}"""


@unittest.skipUnless(PLAYWRIGHT_AVAILABLE and os.environ.get("RUN_BROWSER_SMOKE") == "1",
                     "Browser smoke test enabled via RUN_BROWSER_SMOKE=1 and Playwright")
class TestIssue248Browser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "issue248.db")
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

    def measure(self, width):
        touch = width < 1024
        ctx = self.browser.new_context(viewport={"width": width, "height": 800}, is_mobile=touch, has_touch=touch)
        try:
            page = ctx.new_page()
            page.goto(self.base + "/index.html", wait_until="networkidle")
            page.wait_for_timeout(200)
            return page.evaluate(HERO_JS)
        finally:
            ctx.close()

    def test_hero_fits_phone_widths(self):
        for width in PHONE_WIDTHS:
            with self.subTest(width=width):
                r = self.measure(width)
                self.assertLessEqual(r["overflow"], 0, "home page scrolls sideways")
                self.assertEqual(r["out"], [])
                self.assertGreaterEqual(r["titleLeft"], 0)
                self.assertLessEqual(r["titleRight"], r["vw"], "title is cut")
                first, second = r["buttons"]
                self.assertGreater(second["top"], first["top"], "buttons are stacked")
                for b in r["buttons"]:
                    self.assertEqual(b["h"], 34, "one line of text, design height")
                    self.assertGreaterEqual(b["left"], 0)
                    self.assertLessEqual(b["right"], r["vw"])

    def test_desktop_hero_unchanged(self):
        r = self.measure(1280)
        self.assertEqual(r["fontSize"], 48)
        first, second = r["buttons"]
        self.assertEqual(first["top"], second["top"], "buttons stay in one row")
        # Pixel height depends on the platform font rendering; check the unchanged desktop styles instead
        self.assertEqual({b["padding"] for b in r["buttons"]}, {"14px 32px"})
        self.assertEqual({b["font"] for b in r["buttons"]}, {"17.6px"})


if __name__ == "__main__":
    unittest.main()
