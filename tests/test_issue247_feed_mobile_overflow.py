#!/usr/bin/env python3
"""
tests/test_issue247_feed_mobile_overflow.py

Issue #247: on phones the feed must not scroll sideways. The card footer
actions fit the card (container queries on .card-footer), the feed tabs are
32 to 34 px high and scroll inside their own row, and the vote capsule in the
card stays compact on touch screens. The desktop card does not change.

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
from tests.auth_helpers import upload_auth_headers

FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")
PHONE_WIDTHS = [320, 360, 375, 414]


def read(rel_path):
    with open(os.path.join(FRONTEND_DIR, rel_path), encoding="utf-8") as f:
        return f.read()


class TestIssue247Static(unittest.TestCase):
    def test_footer_container_rules_follow_base_card_rules(self):
        css = read("css/feed.css")
        block = css.index("Issue #247: feed cards and tabs fit phone screens")
        for base in (".card-footer {\n  display: flex;", ".btn-card-action {\n  height: 36px;",
                     ".btn-card-share,\n.btn-card-report {", ".card-read-more,\n.btn-read-more {",
                     ".btn-card-answers {\n  display: inline-flex;"):
            self.assertLess(css.index(base), block, base)
        self.assertIn("container: card-footer / inline-size;", css[block:])
        self.assertIn("@container card-footer (max-width: 470px)", css[block:])

    def test_card_capsule_is_compact_on_touch(self):
        css = read("css/theme.css")
        touch = css.index("@media (pointer: coarse), (max-width: 768px) {")
        rule = re.search(r"\.card-footer-left \.vote-capsule \{([^}]*)\}", css[touch:])
        self.assertIsNotNone(rule)
        self.assertIn("aspect-ratio: auto;", rule.group(1))
        self.assertIn("width: auto;", rule.group(1))
        self.assertRegex(css[touch:], r"\.card-footer-left \.vote-btn \{\s*width: 32px;\s*height: 32px;")

    def test_icon_only_links_keep_accessible_names(self):
        js = read("js/card.js")
        self.assertIn("class=\"card-read-more btn-read-more\" title=\"' + readMoreText + '\" aria-label=\"' + readMoreText + '\"", js)
        self.assertIn("aria-label=\"' + (item.hasSolution ? 'Решение принято, ' : '') + aText + '\"", js)
        self.assertIn("<span class=\"card-answers-count\" aria-hidden=\"true\">", js)


FEED_JS = """() => {
  const vw = document.documentElement.clientWidth;
  const visible = e => { const cs = getComputedStyle(e); const b = e.getBoundingClientRect(); return cs.display !== 'none' && cs.visibility !== 'hidden' && b.width > 0 && b.height > 0; };
  const cards = [...document.querySelectorAll('.feed-card')].filter(visible);
  const out = [], missing = [], heights = [];
  for (const card of cards) {
    const cb = card.getBoundingClientRect();
    const footer = card.querySelector('.card-footer');
    heights.push(Math.round(footer.getBoundingClientRect().height));
    for (const e of footer.querySelectorAll('*')) {
      if (!visible(e)) continue;
      const b = e.getBoundingClientRect();
      if (b.right > cb.right + 0.5 || b.left < cb.left - 0.5) out.push(String(e.getAttribute('class')));
    }
    for (const sel of ['.btn-card-like', '.vote-btn-up', '.vote-btn-down', '.btn-card-bookmark', '.btn-card-share']) {
      const el = footer.querySelector(sel);
      if (!el || !visible(el)) missing.push(sel);
    }
    if (!footer.querySelector('.btn-card-comments, .btn-card-answers')) missing.push('comments');
  }
  const small = [...document.querySelectorAll('.card-footer button, .card-footer a')].filter(visible)
    .filter(e => e.getBoundingClientRect().height < 32 || e.getBoundingClientRect().width < 24)
    .map(e => String(e.getAttribute('class')));
  const tabs = [...document.querySelectorAll('#feedSubnavTabs .feed-subnav-tab')].filter(visible)
    .map(e => Math.round(e.getBoundingClientRect().height));
  return {cards: cards.length, overflow: document.documentElement.scrollWidth - vw, out, missing, heights, small, tabs};
}"""


@unittest.skipUnless(PLAYWRIGHT_AVAILABLE and os.environ.get("RUN_BROWSER_SMOKE") == "1",
                     "Browser smoke test enabled via RUN_BROWSER_SMOKE=1 and Playwright")
class TestIssue247Browser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "issue247.db")
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

    def open(self, width, signed_in=False):
        touch = width < 1024
        ctx = self.browser.new_context(viewport={"width": width, "height": 900}, is_mobile=touch, has_touch=touch)
        if signed_in:
            ctx.add_cookies([{"name": "sc_session", "value": self.token, "url": self.base}])
        page = ctx.new_page()
        page.goto(self.base + "/feed.html", wait_until="networkidle")
        page.wait_for_timeout(300)
        return ctx, page

    def check_phone(self, r, width):
        self.assertGreater(r["cards"], 0)
        self.assertLessEqual(r["overflow"], 0, "feed scrolls sideways")
        self.assertEqual(r["out"], [], "footer element leaves the card")
        self.assertEqual(r["missing"], [], "footer action is hidden")
        self.assertEqual(r["small"], [])
        for h in r["tabs"]:
            self.assertTrue(32 <= h <= 34, r["tabs"])
        if width >= 360:
            self.assertLessEqual(max(r["heights"]), 44, "footer fits one row")

    def test_publications_fit_phone_widths(self):
        for signed_in in (False, True):
            for width in PHONE_WIDTHS:
                with self.subTest(width=width, signed_in=signed_in):
                    ctx, page = self.open(width, signed_in)
                    try:
                        r = page.evaluate(FEED_JS)
                    finally:
                        ctx.close()
                    self.check_phone(r, width)

    def test_questions_fit_phone_widths(self):
        for width in PHONE_WIDTHS:
            with self.subTest(width=width):
                ctx, page = self.open(width)
                try:
                    page.locator("#tabFeedQuestions").click()
                    page.wait_for_timeout(800)
                    self.assertGreater(page.locator(".feed-card .btn-card-answers").count(), 0)
                    r = page.evaluate(FEED_JS)
                    label = page.locator(".feed-card .btn-card-answers").first.get_attribute("aria-label")
                finally:
                    ctx.close()
                self.check_phone(r, width)
                self.assertRegex(label, r"ответ")

    def test_tablet_capsule_fits_its_box(self):
        ctx, page = self.open(768)
        try:
            r = page.evaluate("""() => [...document.querySelectorAll('.card-footer-left .vote-capsule')].slice(0, 5).map(c => {
              const b = c.getBoundingClientRect();
              return [...c.querySelectorAll('.vote-btn')].every(v => { const x = v.getBoundingClientRect(); return x.left >= b.left - 0.5 && x.right <= b.right + 0.5; });
            })""")
        finally:
            ctx.close()
        self.assertTrue(r and all(r), r)

    def test_desktop_card_unchanged(self):
        ctx, page = self.open(1280)
        try:
            r = page.evaluate("""() => {
              const f = document.querySelector('.card-footer');
              const more = f.querySelector('.card-read-more');
              const cap = f.querySelector('.vote-capsule').getBoundingClientRect();
              return {label: more.querySelector('span').getBoundingClientRect().width, moreH: Math.round(more.getBoundingClientRect().height),
                      capW: Math.round(cap.width), answersLabel: document.querySelectorAll('.card-answers-label').length};
            }""")
        finally:
            ctx.close()
        self.assertGreater(r["label"], 20, "read more text is visible on desktop")
        self.assertEqual(r["moreH"], 36)
        self.assertEqual(r["capW"], 108)

    def test_read_more_link_is_reachable_by_name(self):
        ctx, page = self.open(414)
        try:
            link = page.locator(".feed-card .card-read-more").first
            self.assertTrue(link.is_visible())
            self.assertEqual(link.get_attribute("aria-label"), "Читать далее")
            box = link.bounding_box()
            self.assertEqual((round(box["width"]), round(box["height"])), (32, 32))
        finally:
            ctx.close()


if __name__ == "__main__":
    unittest.main()
