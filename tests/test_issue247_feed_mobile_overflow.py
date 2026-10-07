#!/usr/bin/env python3
"""
tests/test_issue247_feed_mobile_overflow.py

Issue #247: on phones the feed must not scroll sideways.

- Card footer actions stay inside the card; every action keeps a 32x32 px tap
  area (both vote arrows, share, report, read more); actions wrap to another
  row when one row does not fit.
- "Read more" stays available on every width (icon with an accessible name
  or its own row) and opens the card's material.
- Feed tabs are 32 to 34 px high, every tab is reachable by scrolling the tab
  row and really switches the section.
- The same card fits the profile and the editor preview (shared
  css/card-footer.css with container queries).
- The vote capsule in the card stays compact on touch screens; the desktop
  card does not change.

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
MIN_TARGET = 32


def read(rel_path):
    with open(os.path.join(FRONTEND_DIR, rel_path), encoding="utf-8") as f:
        return f.read()


class TestIssue247Static(unittest.TestCase):
    def test_shared_footer_styles_load_after_page_styles(self):
        for page in ("feed.html", "profile.html", "editor.html"):
            with self.subTest(page=page):
                head = read(page).split("</head>", 1)[0]
                links = re.findall(r'<link rel="stylesheet" href="([^"]+)">', head)
                self.assertIn("css/card-footer.css", links)
                self.assertEqual(links[-1], "css/card-footer.css", "must win over page card rules")

    def test_footer_rules_use_container_queries_and_keep_32px_targets(self):
        css = read("css/card-footer.css")
        self.assertIn("container: card-footer / inline-size;", css)
        self.assertIn("@container card-footer (max-width: 470px)", css)
        for size in re.findall(r"(?:width|height): (\d+)px;", css):
            if size != "1":
                self.assertGreaterEqual(int(size), MIN_TARGET, css)
        self.assertNotIn(".card-footer-right {\n    display: none;", css, "read more must not be removed")

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


# Measures every visible card footer under `root`.
FOOTER_JS = """(root) => {
  const vw = document.documentElement.clientWidth;
  const visible = e => { const cs = getComputedStyle(e); const b = e.getBoundingClientRect(); return cs.display !== 'none' && cs.visibility !== 'hidden' && b.width > 0 && b.height > 0; };
  const name = e => String(e.getAttribute('class') || e.tagName).split(' ').slice(0, 2).join('.');
  const cards = [...document.querySelectorAll(root)].filter(visible);
  const out = [], missing = [], small = [], overlap = [], readMore = [];
  for (const card of cards) {
    const cb = card.getBoundingClientRect();
    const footer = card.querySelector('.card-footer');
    const actions = [...footer.querySelectorAll('button, a')].filter(visible);
    for (const e of actions) {
      const b = e.getBoundingClientRect();
      if (b.right > cb.right + 0.5 || b.left < cb.left - 0.5) out.push(name(e));
      if (b.width < %(min)d - 0.5 || b.height < %(min)d - 0.5) small.push(name(e) + ' ' + Math.round(b.width) + 'x' + Math.round(b.height));
    }
    const items = [...footer.querySelectorAll('.card-footer-left > *, .card-footer-right > *')].filter(visible);
    for (let i = 0; i < items.length; i++) for (let j = i + 1; j < items.length; j++) {
      const a = items[i].getBoundingClientRect(), b = items[j].getBoundingClientRect();
      if (a.left < b.right - 0.5 && b.left < a.right - 0.5 && a.top < b.bottom - 0.5 && b.top < a.bottom - 0.5) overlap.push(name(items[i]) + '/' + name(items[j]));
    }
    for (const sel of ['.btn-card-like', '.vote-btn-up', '.vote-btn-down', '.btn-card-bookmark', '.btn-card-share']) {
      const el = footer.querySelector(sel);
      if (!el || !visible(el)) missing.push(sel);
    }
    if (!footer.querySelector('.btn-card-comments, .btn-card-answers')) missing.push('comments');
    const more = footer.querySelector('.card-read-more');
    const title = card.querySelector('.card-title a');
    readMore.push({visible: !!more && visible(more), name: more ? (more.getAttribute('aria-label') || '') : '',
                   href: more ? more.getAttribute('href') : null, titleHref: title ? title.getAttribute('href') : null});
  }
  const tabs = [...document.querySelectorAll('#feedSubnavTabs .feed-subnav-tab')].filter(visible)
    .map(e => Math.round(e.getBoundingClientRect().height));
  return {cards: cards.length, overflow: document.documentElement.scrollWidth - vw, out, missing, small, overlap, readMore, tabs};
}""" % {"min": MIN_TARGET}


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

    def context(self, width, signed_in=False, height=900):
        touch = width < 1024
        ctx = self.browser.new_context(viewport={"width": width, "height": height}, is_mobile=touch, has_touch=touch)
        if signed_in:
            ctx.add_cookies([{"name": "sc_session", "value": self.token, "url": self.base}])
        return ctx

    def open(self, width, path="/feed.html", signed_in=False):
        ctx = self.context(width, signed_in)
        page = ctx.new_page()
        page.goto(self.base + path, wait_until="networkidle")
        page.wait_for_timeout(300)
        return ctx, page

    def check_footers(self, r, feed=True):
        self.assertGreater(r["cards"], 0)
        self.assertLessEqual(r["overflow"], 0, "page scrolls sideways")
        self.assertEqual(r["out"], [], "footer action leaves the card")
        self.assertEqual(r["small"], [], "tap area under 32x32 px")
        self.assertEqual(r["overlap"], [], "footer items overlap")
        self.assertEqual(r["missing"], [], "footer action is hidden")
        for more in r["readMore"]:
            self.assertTrue(more["visible"], "read more is hidden")
            self.assertTrue(more["name"], "read more has no accessible name")
            if feed:
                self.assertTrue(more["href"].startswith(more["titleHref"]), more)
        for h in r["tabs"]:
            self.assertTrue(32 <= h <= 34, r["tabs"])

    def test_publications_fit_phone_widths(self):
        for signed_in in (False, True):
            for width in PHONE_WIDTHS:
                with self.subTest(width=width, signed_in=signed_in):
                    ctx, page = self.open(width, signed_in=signed_in)
                    try:
                        r = page.evaluate(FOOTER_JS, ".feed-card")
                        reports = page.locator(".feed-card .btn-card-report").count()
                    finally:
                        ctx.close()
                    self.check_footers(r)
                    self.assertGreater(reports, 0, "report is offered on other authors' cards")

    def test_questions_fit_phone_widths(self):
        for signed_in in (False, True):
            for width in PHONE_WIDTHS:
                with self.subTest(width=width, signed_in=signed_in):
                    ctx, page = self.open(width, signed_in=signed_in)
                    try:
                        page.locator("#tabFeedQuestions").tap()
                        page.wait_for_timeout(800)
                        self.assertGreater(page.locator(".feed-card .btn-card-answers").count(), 0)
                        r = page.evaluate(FOOTER_JS, ".feed-card")
                        label = page.locator(".feed-card .btn-card-answers").first.get_attribute("aria-label")
                    finally:
                        ctx.close()
                    self.check_footers(r)
                    self.assertRegex(label, r"ответ")

    def test_narrowest_read_more_opens_the_material(self):
        ctx, page = self.open(320)
        try:
            card = page.locator(".feed-card").first
            title_href = card.locator(".card-title a").get_attribute("href")
            more = card.locator(".card-read-more")
            self.assertTrue(more.is_visible())
            self.assertEqual(more.get_attribute("aria-label"), "Читать далее")
            more.tap()
            page.wait_for_url("**/" + title_href, timeout=5000)
        finally:
            ctx.close()

    def test_every_tab_is_reachable_and_switches_the_section(self):
        for width in (320, 375):
            for signed_in in (False, True):
                with self.subTest(width=width, signed_in=signed_in):
                    ctx, page = self.open(width, signed_in=signed_in)
                    try:
                        ids = page.evaluate("""() => [...document.querySelectorAll('#feedSubnavTabs .feed-subnav-tab, #feedSavedTab')]
                          .filter(e => getComputedStyle(e).display !== 'none' && e.getBoundingClientRect().width > 0).map(e => e.id)""")
                        expected = {"tabFeedAll", "tabFeedQuestions", "tabFeedDirections", "tabFeedCompanies"}
                        if signed_in:
                            expected |= {"tabFeedSubscriptions", "feedSavedTab"}
                        self.assertTrue(expected <= set(ids), ids)
                        for tab_id in ids:
                            tab = page.locator("#" + tab_id)
                            tab.scroll_into_view_if_needed()
                            box = tab.bounding_box()
                            self.assertGreaterEqual(box["x"], -0.5, tab_id)
                            self.assertLessEqual(box["x"] + box["width"], width + 0.5, tab_id)
                            tab.tap()
                            page.wait_for_timeout(700)
                            active = page.evaluate("""() => [...document.querySelectorAll('#feedSubnavTabs .feed-subnav-tab, #feedSavedTab')]
                              .filter(t => t.getAttribute('aria-selected') === 'true').map(t => t.id)""")
                            self.assertEqual(active, [tab_id])
                            tab_param = page.evaluate("new URLSearchParams(location.search).get('tab')")
                            self.assertEqual(tab_param, page.locator("#" + tab_id).get_attribute("data-tab")
                                             .replace("companies", "blogs"))
                    finally:
                        ctx.close()

    def test_profile_cards_fit_phone_widths(self):
        for width in PHONE_WIDTHS:
            with self.subTest(width=width):
                ctx, page = self.open(width, "/profile.html?id=author_smirnov&tab=publications")
                try:
                    page.wait_for_selector(".feed-card .card-footer", timeout=5000)
                    r = page.evaluate(FOOTER_JS, ".feed-card")
                finally:
                    ctx.close()
                self.check_footers(r, feed=False)

    def test_editor_preview_card_fits_phone_widths(self):
        for width in (320, 375, 414):
            with self.subTest(width=width):
                ctx = self.context(width, signed_in=True)
                try:
                    page = ctx.new_page()
                    page.goto(self.base + "/editor.html", wait_until="networkidle")
                    page.locator("#article-title").fill("Карточка в превью на телефоне")
                    page.locator("#editor .ql-editor").click()
                    page.keyboard.type("Текст для проверки превью карточки. " * 4)
                    page.wait_for_timeout(300)
                    # The phone document bar is fixed in #244; here only the preview card is checked
                    page.evaluate("document.getElementById('btn-next-to-settings').click()")
                    page.wait_for_selector("#pub-card-preview .card-footer", state="visible", timeout=5000)
                    r = page.evaluate(FOOTER_JS, "#pub-card-preview")
                finally:
                    ctx.close()
                self.assertEqual(r["cards"], 1)
                self.assertLessEqual(r["overflow"], 0)
                self.assertEqual(r["out"], [])
                self.assertEqual(r["small"], [])
                self.assertEqual(r["overlap"], [])

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
              const tops = [...f.querySelectorAll('.card-footer-left > *, .card-footer-right > *')].map(e => Math.round(e.getBoundingClientRect().top));
              return {label: more.querySelector('span').getBoundingClientRect().width, moreH: Math.round(more.getBoundingClientRect().height),
                      capW: Math.round(cap.width), rows: new Set(tops).size};
            }""")
        finally:
            ctx.close()
        self.assertGreater(r["label"], 20, "read more text is visible on desktop")
        self.assertEqual(r["moreH"], 36)
        self.assertEqual(r["capW"], 108)
        self.assertEqual(r["rows"], 1)


if __name__ == "__main__":
    unittest.main()
