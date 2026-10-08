#!/usr/bin/env python3
"""
tests/test_issue261_company_header_mobile.py

Issue #261: on phones the company profile showed "Подписаться" and the link
button next to the name, so the name was squeezed into a narrow column and
broken in the middle of words (74 px and 10 lines at 320 px for a guest).
Up to 640 px the actions now go under the name; the desktop look is kept.

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
from tests.auth_helpers import upload_auth_headers

FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")
BROWSER_SMOKE = True  # collected by tests/run_browser_smoke.py
COMPANY = "/company.html?id=smarttech-innovations"
PHONE_WIDTHS = [320, 360, 375, 414]


class TestIssue261Static(unittest.TestCase):
    def test_phone_block_stacks_actions_and_keeps_words_whole(self):
        with open(os.path.join(FRONTEND_DIR, "css", "company.css"), encoding="utf-8") as f:
            css = f.read()
        block = css[css.index("@media (max-width: 640px) {"):]
        self.assertRegex(block, r"\.co-hero-row \{\s*flex-direction: column;")
        self.assertRegex(block, r"\.co-name \{\s*overflow-wrap: break-word;")


HEADER_JS = """() => {
  const card = document.querySelector('.co-hero').getBoundingClientRect();
  const name = document.querySelector('.co-name').getBoundingClientRect();
  const span = document.getElementById('companyName');
  const text = span.firstChild;
  const broken = [];
  let pos = 0;
  for (const word of span.textContent.split(' ')) {
    const range = document.createRange();
    range.setStart(text, pos); range.setEnd(text, pos + word.length);
    if (new Set([...range.getClientRects()].map(r => Math.round(r.top))).size > 1) broken.push(word);
    pos += word.length + 1;
  }
  const identity = document.querySelector('.co-identity').getBoundingClientRect();
  const actions = document.getElementById('companyActions');
  const buttons = [...actions.querySelectorAll('button, a')].map(e => {
    const b = e.getBoundingClientRect();
    return {h: Math.round(b.height), inside: b.left >= card.left - 0.5 && b.right <= card.right + 0.5};
  });
  return {ratio: name.width / card.width, broken, buttons,
          below: actions.getBoundingClientRect().top >= identity.bottom - 1,
          overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth};
}"""


@unittest.skipUnless(PLAYWRIGHT_AVAILABLE and os.environ.get("RUN_BROWSER_SMOKE") == "1",
                     "Browser smoke test enabled via RUN_BROWSER_SMOKE=1 and Playwright")
class TestIssue261Browser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "issue261.db")
        server.DEFAULT_DB_PATH = cls.db_path
        init_db(cls.db_path, seed=True).close()
        cls.token = upload_auth_headers(cls.db_path)["Authorization"].split(" ", 1)[1]
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

    def measure(self, width, signed_in):
        touch = width < 1024
        ctx = self.browser.new_context(viewport={"width": width, "height": 900}, is_mobile=touch, has_touch=touch)
        if signed_in:
            ctx.add_cookies([{"name": "sc_session", "value": self.token, "url": self.base}])
        try:
            page = ctx.new_page()
            page.goto(self.base + COMPANY, wait_until="networkidle")
            page.wait_for_function("() => document.getElementById('companyName').textContent.trim() !== ''", timeout=5000)
            page.wait_for_timeout(200)
            return page.evaluate(HEADER_JS)
        finally:
            ctx.close()

    def test_name_keeps_the_card_width_on_phones(self):
        for signed_in in (False, True):
            for width in PHONE_WIDTHS:
                with self.subTest(width=width, signed_in=signed_in):
                    r = self.measure(width, signed_in)
                    self.assertGreaterEqual(r["ratio"], 0.85, r)
                    self.assertEqual(r["broken"], [], "words of the name are not split")
                    self.assertTrue(r["below"], "actions are under the name")
                    self.assertTrue(r["buttons"], "subscribe and link buttons are shown")
                    for b in r["buttons"]:
                        self.assertTrue(32 <= b["h"] <= 34 and b["inside"], b)
                    self.assertLessEqual(r["overflow"], 0)

    def test_desktop_keeps_actions_next_to_the_name(self):
        r = self.measure(1280, signed_in=False)
        self.assertFalse(r["below"], "actions stay on the right on desktop")
        self.assertEqual(r["broken"], [])


if __name__ == "__main__":
    unittest.main()
