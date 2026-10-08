#!/usr/bin/env python3
"""
tests/test_issue246_article_mobile_actions.py

Issue #246: below 1200 px the article page hides the side action rail, so the
bottom action bar (#mobileActionBar) must be shown there with all actions.
From 1200 px only the side rail is shown.

Static checks always run. The browser checks run with RUN_BROWSER_SMOKE=1 and
Playwright; set PLAYWRIGHT_CDP_URL to drive an already running Chromium
instead of launching one.
"""

import datetime
import json
import os
import re
import secrets
import sqlite3
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.request

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
from tests.auth_helpers import upload_auth_headers

FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")
BROWSER_SMOKE = True  # collected by tests/run_browser_smoke.py
BAR_WIDTHS = [320, 375, 414, 768, 1024]
ARTICLE = "article.html?id=art-01"


def read(rel_path):
    with open(os.path.join(FRONTEND_DIR, rel_path), encoding="utf-8") as f:
        return f.read()


class TestIssue246Static(unittest.TestCase):
    def test_bar_is_hidden_by_default_before_the_media_block_that_shows_it(self):
        css = read("css/article.css")
        hidden = re.search(r"\.mobile-action-bar,\s*#mobileActionBar \{\s*display: none;\s*\}", css)
        self.assertIsNotNone(hidden)
        self.assertEqual(len(re.findall(r"\.mobile-action-bar,\s*#mobileActionBar \{\s*display: none;", css)), 1,
                         "a second display: none rule later in the file would win the cascade again")
        shown = css.index("  .mobile-action-bar,\n  #mobileActionBar {\n    display: flex;")
        self.assertGreater(shown, css.index("@media (max-width: 1199px) {"))
        self.assertLess(hidden.start(), shown)

    def test_toast_lift_follows_base_toast_rule(self):
        css = read("css/article.css")
        base = css.index(".article-toast {\n  position: fixed;")
        lift = css.index("@media (max-width: 1199px) {\n  .article-toast {\n    bottom: 72px;")
        self.assertGreater(lift, base)


BAR_JS = """() => {
  const bar = document.getElementById('mobileActionBar');
  const rail = document.getElementById('articleActionRail');
  const r = bar.getBoundingClientRect();
  const visible = e => { const cs = getComputedStyle(e); const b = e.getBoundingClientRect(); return cs.display !== 'none' && cs.visibility !== 'hidden' && b.width > 0 && b.height > 0; };
  const actions = ['mobileBtnLike', 'mobileBtnBookmark', 'mobileBtnComments', 'mobileBtnShare', 'mobileBtnReport']
    .map(id => document.getElementById(id))
    .map(e => ({id: e.id, visible: visible(e), h: Math.round(e.getBoundingClientRect().height),
                inside: e.getBoundingClientRect().left >= 0 && e.getBoundingClientRect().right <= innerWidth,
                label: e.getAttribute('aria-label')}));
  const votes = [...document.querySelectorAll('#mobileArticleVote button')].filter(visible).length;
  return {barVisible: visible(bar), position: getComputedStyle(bar).position, top: Math.round(r.top), bottom: Math.round(r.bottom),
          railVisible: !!rail && visible(rail), actions, votes, innerHeight,
          overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth};
}"""


@unittest.skipUnless(PLAYWRIGHT_AVAILABLE and os.environ.get("RUN_BROWSER_SMOKE") == "1",
                     "Browser smoke test enabled via RUN_BROWSER_SMOKE=1 and Playwright")
class TestIssue246Browser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "issue246.db")
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

    def open(self, width, signed_in=False, height=800):
        touch = width < 1200
        ctx = self.browser.new_context(viewport={"width": width, "height": height}, is_mobile=touch, has_touch=touch)
        if signed_in:
            ctx.add_cookies([{"name": "sc_session", "value": self.token, "url": self.base}])
        page = ctx.new_page()
        page.goto("%s/%s" % (self.base, ARTICLE), wait_until="networkidle")
        page.wait_for_timeout(200)
        return ctx, page

    def test_bar_shows_all_actions_below_1200(self):
        for width in BAR_WIDTHS:
            with self.subTest(width=width):
                ctx, page = self.open(width)
                try:
                    r = page.evaluate(BAR_JS)
                finally:
                    ctx.close()
                self.assertTrue(r["barVisible"])
                self.assertEqual(r["position"], "fixed")
                self.assertEqual(r["bottom"], r["innerHeight"], "bar is pinned to the bottom of the screen")
                self.assertFalse(r["railVisible"])
                self.assertEqual(r["votes"], 2, "vote up and vote down are in the bar")
                for a in r["actions"]:
                    self.assertTrue(a["visible"] and a["inside"], a)
                    self.assertGreaterEqual(a["h"], 32, a)
                    self.assertTrue(a["label"], a)
                self.assertLessEqual(r["overflow"], 0)

    def test_desktop_shows_rail_only(self):
        ctx, page = self.open(1280)
        try:
            r = page.evaluate(BAR_JS)
        finally:
            ctx.close()
        self.assertFalse(r["barVisible"])
        self.assertTrue(r["railVisible"])

    def test_bar_does_not_cover_end_of_page(self):
        for width in (375, 768):
            with self.subTest(width=width):
                ctx, page = self.open(width)
                try:
                    page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
                    page.wait_for_timeout(200)
                    r = page.evaluate("""() => {
                      const main = document.getElementById('articleMainSlot');
                      const last = [...main.querySelectorAll('*')].filter(e => {
                        const cs = getComputedStyle(e); const b = e.getBoundingClientRect();
                        return cs.display !== 'none' && cs.visibility !== 'hidden' && b.height > 0 && e.children.length === 0;
                      }).map(e => e.getBoundingClientRect().bottom);
                      return {contentBottom: Math.max(...last), barTop: document.getElementById('mobileActionBar').getBoundingClientRect().top};
                    }""")
                finally:
                    ctx.close()
                self.assertLessEqual(r["contentBottom"], r["barTop"])

    def test_guest_like_opens_sign_in(self):
        ctx, page = self.open(375)
        try:
            page.locator("#mobileBtnLike").tap()
            page.wait_for_timeout(200)
            self.assertTrue(page.locator("#authModal").is_visible())
        finally:
            ctx.close()

    def test_comments_button_scrolls_to_comments(self):
        ctx, page = self.open(768)
        try:
            page.locator("#mobileBtnComments").tap()
            page.wait_for_timeout(1200)
            top = page.evaluate("document.getElementById('commentsSection').getBoundingClientRect().top")
            self.assertLess(abs(top), 120)
        finally:
            ctx.close()

    def test_signed_in_like_and_bookmark_are_saved(self):
        ctx, page = self.open(375, signed_in=True)
        try:
            likes = int(page.locator("#mobileLikeCount").inner_text())
            page.locator("#mobileBtnLike").tap()
            page.locator("#mobileBtnBookmark").tap()
            page.wait_for_timeout(800)
            page.reload(wait_until="networkidle")
            page.wait_for_timeout(300)
            self.assertEqual(int(page.locator("#mobileLikeCount").inner_text()), likes + 1)
            self.assertIn("is-liked", page.locator("#mobileBtnLike").get_attribute("class"))
            bookmark = page.locator("#mobileBtnBookmark").get_attribute("class")
            self.assertTrue("is-bookmarked" in bookmark or "is-saved" in bookmark, bookmark)
        finally:
            ctx.close()


    # Review of PR #249: every action from the bottom bar, on isolated data. Each scenario
    # gets its own user and its own article, so no state leaks between tests.

    def new_session(self, login):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            user_id = create_user(conn, login, login + "@example.com", "Reader-pass-1", email_verified=True)["id"]
            token = secrets.token_hex(32)
            now = datetime.datetime.now(datetime.timezone.utc)
            with conn:
                conn.execute("""INSERT INTO sessions (token, user_id, user_name, user_role, created_at, expires_at, is_revoked)
                                VALUES (?, ?, ?, 'user', ?, ?, 0)""",
                             (token, user_id, login, now.isoformat(), (now + datetime.timedelta(days=1)).isoformat()))
        finally:
            conn.close()
        return token

    def api_article(self, article_id, token):
        req = urllib.request.Request("%s/api/articles/%s" % (self.base, article_id),
                                     headers={"Authorization": "Bearer " + token})
        with urllib.request.urlopen(req, timeout=10) as res:
            return json.loads(res.read().decode("utf-8"))["article"]

    def open_as(self, width, token, article_id, height=800):
        touch = width < 1200
        ctx = self.browser.new_context(viewport={"width": width, "height": height}, is_mobile=touch, has_touch=touch)
        ctx.add_cookies([{"name": "sc_session", "value": token, "url": self.base}])
        page = ctx.new_page()
        page.goto("%s/article.html?id=%s" % (self.base, article_id), wait_until="networkidle")
        page.wait_for_timeout(300)
        return ctx, page

    def bar_vote(self, page, prefix="#mobileArticleVote"):
        return page.evaluate("""(p) => {
          const root = document.querySelector(p);
          return {up: root.querySelector('.vote-btn-up').getAttribute('aria-pressed'),
                  down: root.querySelector('.vote-btn-down').getAttribute('aria-pressed'),
                  score: parseInt(root.querySelector('.vote-score').textContent.replace(/[^0-9-]/g, ''), 10)};
        }""", prefix)

    def test_vote_up_and_down_from_bar_persist(self):
        for width, article_id in ((375, "art-02"), (768, "art-03")):
            with self.subTest(width=width):
                token = self.new_session("voter_%d" % width)
                before = self.api_article(article_id, token)
                self.assertEqual(before["myVote"], 0)
                ctx, page = self.open_as(width, token, article_id)
                try:
                    page.locator("#mobileArticleVote .vote-btn-up").tap()
                    page.wait_for_timeout(600)
                    self.assertEqual(self.bar_vote(page), {"up": "true", "down": "false", "score": before["score"] + 1})
                    page.reload(wait_until="networkidle")
                    page.wait_for_timeout(300)
                    self.assertEqual(self.bar_vote(page), {"up": "true", "down": "false", "score": before["score"] + 1})
                    api = self.api_article(article_id, token)
                    self.assertEqual((api["myVote"], api["score"]), (1, before["score"] + 1))

                    page.locator("#mobileArticleVote .vote-btn-down").tap()
                    page.wait_for_timeout(600)
                    page.reload(wait_until="networkidle")
                    page.wait_for_timeout(300)
                    self.assertEqual(self.bar_vote(page), {"up": "false", "down": "true", "score": before["score"] - 1})
                    api = self.api_article(article_id, token)
                    self.assertEqual((api["myVote"], api["score"]), (-1, before["score"] - 1))
                finally:
                    ctx.close()

    def test_state_stays_in_sync_when_viewport_changes(self):
        article_id = "art-04"
        token = self.new_session("resizer")
        before = self.api_article(article_id, token)
        ctx, page = self.open_as(375, token, article_id)
        try:
            page.locator("#mobileBtnLike").tap()
            page.locator("#mobileArticleVote .vote-btn-up").tap()
            page.locator("#mobileBtnBookmark").tap()
            page.wait_for_timeout(800)
            after = self.api_article(article_id, token)
            self.assertEqual(after["likesCount"], before["likesCount"] + 1)
            self.assertEqual(after["score"], before["score"] + 1)
            self.assertEqual(after["savesCount"], before["savesCount"] + 1)

            for width, like, like_count, bookmark, bookmark_count, vote in (
                    (1280, "#railBtnLike", "#railLikeCount", "#railBtnBookmark", "#railBookmarkCount", "#railArticleVote"),
                    (375, "#mobileBtnLike", "#mobileLikeCount", "#mobileBtnBookmark", "#mobileBookmarkCount", "#mobileArticleVote")):
                page.set_viewport_size({"width": width, "height": 800})
                page.wait_for_timeout(300)
                self.assertTrue(page.locator(like).is_visible(), width)
                self.assertIn("is-liked", page.locator(like).get_attribute("class"))
                self.assertEqual(int(page.locator(like_count).inner_text()), after["likesCount"])
                self.assertRegex(page.locator(bookmark).get_attribute("class"), r"is-(bookmarked|saved)")
                self.assertEqual(int(page.locator(bookmark_count).inner_text()), after["savesCount"])
                self.assertEqual(self.bar_vote(page, vote), {"up": "true", "down": "false", "score": after["score"]})

            final = self.api_article(article_id, token)
            self.assertEqual((final["likesCount"], final["score"], final["savesCount"]),
                             (after["likesCount"], after["score"], after["savesCount"]), "resizing changed counters")
        finally:
            ctx.close()

    def test_share_menu_opens_inside_the_screen_and_closes(self):
        for width in (320, 375, 768):
            with self.subTest(width=width):
                ctx, page = self.open(width)
                try:
                    share = page.locator("#mobileBtnShare")
                    share.tap()
                    menu = page.locator("#articleSharePopover")
                    self.assertTrue(menu.is_visible())
                    self.assertEqual(menu.get_attribute("role"), "menu")
                    self.assertEqual(share.get_attribute("aria-expanded"), "true")
                    box = menu.bounding_box()
                    self.assertGreaterEqual(box["x"], 0)
                    self.assertGreaterEqual(box["y"], 0)
                    self.assertLessEqual(box["x"] + box["width"], width)
                    self.assertLessEqual(box["y"] + box["height"], 800 - 56, "menu stays above the bar")
                    items = page.locator("#articleSharePopover [role=menuitem]")
                    self.assertGreaterEqual(items.count(), 2)
                    for i in range(items.count()):
                        self.assertTrue(items.nth(i).inner_text().strip())
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(200)
                    self.assertFalse(menu.is_visible())
                    self.assertEqual(share.get_attribute("aria-expanded"), "false")
                    share.tap()
                    self.assertTrue(menu.is_visible())
                    page.mouse.click(width // 2, 150)
                    page.wait_for_timeout(200)
                    self.assertFalse(menu.is_visible(), "tap outside closes the menu")
                finally:
                    ctx.close()

    def test_report_from_bar_signed_in_and_guest(self):
        article_id = "art-05"
        token = self.new_session("reporter")
        self.assertFalse(self.api_article(article_id, token)["hasReported"])
        ctx, page = self.open_as(375, token, article_id)
        try:
            page.locator("#mobileBtnReport").tap()
            dialog = page.locator("#articleReportModal")
            self.assertTrue(dialog.is_visible())
            self.assertEqual(dialog.get_attribute("role"), "dialog")
            dialog.locator("button[type=submit]").tap()
            page.wait_for_timeout(800)
            self.assertTrue(self.api_article(article_id, token)["hasReported"])
            page.reload(wait_until="networkidle")
            page.wait_for_timeout(300)
            self.assertIn("is-reported", page.locator("#mobileBtnReport").get_attribute("class"))
        finally:
            ctx.close()

        ctx, page = self.open(768)
        try:
            page.locator("#mobileBtnReport").tap()
            page.wait_for_timeout(200)
            self.assertTrue(page.locator("#authModal").is_visible(), "guest is asked to sign in")
            self.assertFalse(page.locator("#articleReportModal").is_visible())
        finally:
            ctx.close()

    def test_comment_form_and_end_of_page_reachable_in_both_themes(self):
        token = self.new_session("commenter")
        for theme in ("dark", "light"):
            for width in (375, 768):
                with self.subTest(theme=theme, width=width):
                    ctx = self.browser.new_context(viewport={"width": width, "height": 800}, is_mobile=True, has_touch=True)
                    ctx.add_init_script("localStorage.setItem('sc_theme', '%s')" % theme)
                    ctx.add_cookies([{"name": "sc_session", "value": token, "url": self.base}])
                    page = ctx.new_page()
                    try:
                        page.goto("%s/%s" % (self.base, ARTICLE), wait_until="networkidle")
                        page.wait_for_timeout(300)
                        self.assertEqual(page.evaluate("document.documentElement.getAttribute('data-theme')"), theme)
                        page.locator("#commentComposerTrigger").tap()
                        page.wait_for_timeout(300)
                        page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
                        page.wait_for_timeout(300)
                        r = page.evaluate("""() => {
                          const bar = document.getElementById('mobileActionBar').getBoundingClientRect();
                          const form = document.getElementById('commentForm').getBoundingClientRect();
                          const main = document.getElementById('articleMainSlot');
                          const leaves = [...main.querySelectorAll('*')].filter(e => {
                            const cs = getComputedStyle(e); const b = e.getBoundingClientRect();
                            return cs.display !== 'none' && cs.visibility !== 'hidden' && b.height > 0 && e.children.length === 0;
                          }).map(e => e.getBoundingClientRect().bottom);
                          return {barTop: bar.top, barBg: getComputedStyle(document.getElementById('mobileActionBar')).backgroundColor,
                                  contentBottom: Math.max(...leaves), formBottom: form.bottom, formHeight: form.height};
                        }""")
                        page.locator("#commentTextInput").scroll_into_view_if_needed()
                        input_box = page.locator("#commentTextInput").bounding_box()
                        bar_top = page.evaluate("document.getElementById('mobileActionBar').getBoundingClientRect().top")
                    finally:
                        ctx.close()
                    self.assertLessEqual(r["contentBottom"], r["barTop"])
                    self.assertGreater(r["formHeight"], 0)
                    self.assertLessEqual(input_box["y"] + input_box["height"], bar_top, "comment input is not under the bar")
                    self.assertNotIn(r["barBg"], ("rgba(0, 0, 0, 0)", "transparent"), "bar has a solid background")


if __name__ == "__main__":
    unittest.main()
