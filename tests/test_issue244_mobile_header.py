#!/usr/bin/env python3
"""
tests/test_issue244_mobile_header.py

Issue #244: the shared header and the editor document bar must fit phone
screens (320 to 414 px) without leaving the viewport.

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

PAGES = [
    "index.html", "feed.html", "article.html", "editor.html", "question-editor.html",
    "profile.html", "company.html", "settings.html", "my-materials.html", "admin.html",
]
PHONE_WIDTHS = [320, 360, 390, 414]


def read(rel_path):
    with open(os.path.join(FRONTEND_DIR, rel_path), encoding="utf-8") as f:
        return f.read()


def media_block(css, marker):
    """Return the @media block that contains marker (or follows it), with its offset."""
    pos = css.index(marker)

    def block_at(start):
        depth = 0
        for i in range(css.index("{", start), len(css)):
            if css[i] == "{":
                depth += 1
            elif css[i] == "}":
                depth -= 1
                if depth == 0:
                    return css[start:i + 1]
        raise AssertionError("unbalanced @media block")

    start = css.rfind("@media", 0, pos)
    if start == -1 or start + len(block_at(start)) < pos:
        start = css.index("@media", pos)
    return start, block_at(start)


class TestIssue244Static(unittest.TestCase):
    def test_create_button_has_icon_label_and_accessible_name(self):
        html = read("question-editor.html")
        button = re.search(r'<button[^>]*id="btnCreateDropdown"[^>]*>(.*?)</button>', html, re.S)
        self.assertIsNotNone(button)
        self.assertIn('aria-label="Создать материал"', button.group(0))
        self.assertIn('class="header-create-icon"', button.group(1))
        self.assertIn('aria-hidden="true"', button.group(1))
        self.assertIn('<span class="header-create-label">Создать +</span>', button.group(1))

    def test_question_editor_phone_rules(self):
        css = read("css/question-editor.css")
        _, block = media_block(css, "Issue #244: the header create button")
        self.assertIn("@media (max-width: 480px)", block)
        for rule in (".header-create-icon", ".header-create-label", ".header-create-btn", "#save-status-text"):
            self.assertIn(rule, block)
        self.assertRegex(block, r"\.header-create-btn \{\s*width: 34px;\s*height: 34px;")
        self.assertIn("clip: rect(0, 0, 0, 0);", block)

    def test_editor_phone_rules_follow_base_button_rule(self):
        css = read("css/editor.css")
        start, block = media_block(css, "Issue #244: one-line document bar on phones.")
        self.assertIn("@media (max-width: 480px)", block)
        self.assertGreater(start, css.index(".btn-next-to-pub,\n.btn-next-settings,"),
                           "the phone block must come after the base rule to win the cascade")
        self.assertIn(".btn-drafts span:not(#drafts-badge)", block)
        self.assertIn("#save-status-text", block)
        self.assertIn("height: 34px;", block)

    def test_header_control_heights_follow_base_rules(self):
        css = read("css/theme.css")
        start, block = media_block(css, "Issue #244: phone header controls")
        self.assertGreater(start, css.index("\n.header-notif-btn {"))
        self.assertGreater(start, css.index("\n.header-login-action-btn {"))
        self.assertRegex(block, r"\.header-notif-btn \{\s*width: 34px;\s*height: 34px;")
        self.assertRegex(block, r"\.header-login-action-btn \{[^}]*height: 34px;")


HEADER_JS = """() => {
  const vw = document.documentElement.clientWidth;
  const skip = e => e.closest('.header-notif-popup, .feed-create-menu');
  const visible = e => { const cs = getComputedStyle(e); return cs.display !== 'none' && cs.visibility !== 'hidden' && e.getBoundingClientRect().width > 1; };
  const out = [];
  for (const root of document.querySelectorAll('.app-header, .editor-document-bar')) {
    for (const e of [root, ...root.querySelectorAll('*')]) {
      if (skip(e) || !visible(e)) continue;
      const b = e.getBoundingClientRect();
      if (b.right > vw + 0.5 || b.left < -0.5) out.push((e.id || e.className) + ' ' + Math.round(b.left) + '..' + Math.round(b.right));
    }
  }
  const container = document.querySelector('.app-header .header-container');
  const items = [...container.querySelectorAll('*')].filter(e => !skip(e) && visible(e));
  const left = Math.min(...items.map(e => e.getBoundingClientRect().left));
  const right = Math.max(...items.map(e => e.getBoundingClientRect().right));
  const buttons = [...document.querySelectorAll('.app-header button:not(.btn-theme-toggle), .app-header a.header-login-action-btn, .editor-document-bar button')]
    .filter(b => !skip(b) && visible(b))
    .map(b => ({id: b.id || b.className, h: Math.round(b.getBoundingClientRect().height), clipped: b.scrollWidth > b.clientWidth + 1}));
  const bar = document.querySelector('.editor-document-bar');
  const wrapped = [...document.querySelectorAll('.editor-document-bar button span, .editor-document-bar .save-status')]
    .filter(e => visible(e) && e.getBoundingClientRect().height > 24).map(e => e.id || e.className);
  return {overflow: out, gap: [Math.round(left), Math.round(vw - right)], buttons,
          barHeight: bar ? Math.round(bar.getBoundingClientRect().height) : null, wrapped};
}"""


@unittest.skipUnless(PLAYWRIGHT_AVAILABLE and os.environ.get("RUN_BROWSER_SMOKE") == "1",
                     "Browser smoke test enabled via RUN_BROWSER_SMOKE=1 and Playwright")
class TestIssue244Browser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "issue244.db")
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

    def open(self, width, page_name, phone=True):
        ctx = self.browser.new_context(viewport={"width": width, "height": 800}, is_mobile=phone, has_touch=phone)
        page = ctx.new_page()
        page.goto("%s/%s" % (self.base, page_name), wait_until="networkidle")
        page.wait_for_timeout(150)
        return ctx, page

    def test_header_and_document_bar_fit_phone_widths(self):
        for width in PHONE_WIDTHS:
            for name in PAGES:
                with self.subTest(width=width, page=name):
                    ctx, page = self.open(width, name)
                    try:
                        r = page.evaluate(HEADER_JS)
                    finally:
                        ctx.close()
                    self.assertEqual(r["overflow"], [])
                    self.assertGreaterEqual(min(r["gap"]), 4, "header needs inner spacing on both sides")
                    for b in r["buttons"]:
                        self.assertTrue(32 <= b["h"] <= 34, b)
                        self.assertFalse(b["clipped"], b)
                    if r["barHeight"] is not None:
                        self.assertLessEqual(r["barHeight"], 52)
                        self.assertEqual(r["wrapped"], [])

    def test_create_menu_opens_inside_the_screen(self):
        for width in (320, 390):
            with self.subTest(width=width):
                ctx, page = self.open(width, "question-editor.html")
                try:
                    btn = page.locator("#btnCreateDropdown")
                    self.assertEqual(btn.get_attribute("aria-label"), "Создать материал")
                    box = btn.bounding_box()
                    self.assertEqual((round(box["width"]), round(box["height"])), (34, 34))
                    btn.tap()
                    self.assertEqual(btn.get_attribute("aria-expanded"), "true")
                    menu = page.locator("#feedCreateMenu").bounding_box()
                    self.assertGreaterEqual(menu["x"], 0)
                    self.assertLessEqual(menu["x"] + menu["width"], width)
                    with page.expect_navigation():
                        page.locator("#btnCreatePublication").tap()
                    self.assertTrue(page.url.endswith("/editor.html"))
                finally:
                    ctx.close()

    def test_save_status_text_stays_readable_for_screen_readers(self):
        for name in ("editor.html", "question-editor.html"):
            with self.subTest(page=name):
                ctx, page = self.open(390, name)
                try:
                    text = page.locator("#save-status-text")
                    self.assertTrue(text.text_content().strip())
                    self.assertNotEqual(text.evaluate("e => getComputedStyle(e).display"), "none")
                    self.assertLessEqual(text.bounding_box()["width"], 1)
                finally:
                    ctx.close()

    def test_desktop_keeps_text_labels(self):
        ctx, page = self.open(1280, "question-editor.html", phone=False)
        try:
            self.assertTrue(page.locator(".header-create-label").is_visible())
            self.assertFalse(page.locator(".header-create-icon").is_visible())
            self.assertGreater(page.locator("#save-status-text").bounding_box()["width"], 50)
        finally:
            ctx.close()
        ctx, page = self.open(1280, "editor.html", phone=False)
        try:
            self.assertTrue(page.locator(".btn-drafts span:not(#drafts-badge)").first.is_visible())
            self.assertGreater(page.locator("#save-status-text").bounding_box()["width"], 50)
        finally:
            ctx.close()


if __name__ == "__main__":
    unittest.main()
