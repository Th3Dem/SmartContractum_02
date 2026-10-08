#!/usr/bin/env python3
"""
tests/test_issue271_272_author_card.py

Issues #271 and #272 (epic #270): the author mini card.

#271 behaviour: a non-modal popover next to the author name or avatar; opens on
hover after 250 ms (a quick pass opens nothing and sends no request), stays open
while the pointer moves into it, closes 200 ms after leaving; click or tap pins
it, a second tap on the source or a tap outside closes it; keyboard focus shows
it, Enter pins it and moves to the actions, Escape closes it without reopening;
no overlay, no focus trap, no scroll lock; one card at a time and late responses
never replace a newer card; it stays inside the viewport and follows scrolling.

#272 design: compact head (avatar, name, rating), four metrics from the profile,
"Подписаться" / "Вы подписаны", secondary "Перейти в профиль"; loading, error
with retry, not found, guest and own profile states; long names, big numbers,
negative rating and a broken avatar do not break the card at 320 px.

Static checks always run. The browser checks run with RUN_BROWSER_SMOKE=1 and
Playwright; set PLAYWRIGHT_CDP_URL to drive an already running Chromium.
"""

import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time
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
ARTICLE = "/article.html?id=art-01"
AUTHOR = "author_smirnov"


def read(rel_path):
    with open(os.path.join(FRONTEND_DIR, rel_path), encoding="utf-8") as f:
        return f.read()


class TestAuthorCardStatic(unittest.TestCase):
    def test_old_modal_is_gone_from_pages_and_scripts(self):
        for page in ("feed.html", "article.html", "profile.html"):
            self.assertNotIn("userProfileModal", read(page), page)
        self.assertNotIn("openUserProfileModal(authorId)", read("js/feed.js"))
        self.assertNotIn("trapModalFocus", read("js/profile.js"))

    def test_delays_are_shared_constants(self):
        js = read("js/profile.js")
        self.assertIn("var AUTHOR_CARD_OPEN_DELAY = 250;", js)
        self.assertIn("var AUTHOR_CARD_CLOSE_DELAY = 200;", js)
        self.assertIn("card.setAttribute('role', 'dialog');", js)
        self.assertNotIn("role', 'tooltip'", js)
        self.assertNotIn("aria-modal', 'true'", js)


def card_state(page):
    return page.evaluate("""() => {
      const c = document.getElementById('authorCard');
      if (!c) return {exists: false, open: false};
      const r = c.getBoundingClientRect();
      const name = c.querySelector('#authorCardName');
      return {exists: true, open: !c.hidden, name: name ? name.textContent.trim() : null,
              left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width,
              vw: document.documentElement.clientWidth, vh: window.innerHeight,
              focusInside: c.contains(document.activeElement)};
    }""")


@unittest.skipUnless(PLAYWRIGHT_AVAILABLE and os.environ.get("RUN_BROWSER_SMOKE") == "1",
                     "Browser smoke test enabled via RUN_BROWSER_SMOKE=1 and Playwright")
class TestAuthorCardBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "author_card.db")
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

    def open(self, width=1280, height=900, signed_in=True, touch=False, theme=None, path=ARTICLE):
        ctx = self.browser.new_context(viewport={"width": width, "height": height}, is_mobile=touch, has_touch=touch)
        if theme:
            ctx.add_init_script("localStorage.setItem('sc_theme', '%s')" % theme)
        if signed_in:
            ctx.add_cookies([{"name": "sc_session", "value": self.token, "url": self.base}])
        page = ctx.new_page()
        page.requests = []
        page.on("request", lambda r: page.requests.append(r.url) if "/api/users/" in r.url else None)
        page.goto(self.base + path, wait_until="networkidle")
        page.wait_for_selector("#articleAuthorName[data-author-id]", timeout=5000)
        page.wait_for_timeout(200)
        page.requests.clear()
        return ctx, page

    def hover(self, page, selector):
        box = page.locator(selector).first.bounding_box()
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        return box

    # ---- #271 behaviour ----

    def test_hover_opens_after_delay_and_quick_pass_does_nothing(self):
        ctx, page = self.open()
        try:
            page.mouse.move(5, 5)
            box = self.hover(page, "#articleAuthorName")
            page.wait_for_timeout(80)
            page.mouse.move(5, 5)
            page.wait_for_timeout(500)
            self.assertFalse(card_state(page)["open"], "a quick pass does not open the card")
            self.assertEqual(page.requests, [], "a quick pass sends no request")

            self.hover(page, "#articleAuthorName")
            page.wait_for_timeout(120)
            self.assertFalse(card_state(page)["open"], "not before the open delay")
            page.wait_for_timeout(450)
            state = card_state(page)
            self.assertTrue(state["open"])
            self.assertEqual(state["name"], "Алексей Смирнов")
            self.assertFalse(state["focusInside"], "hover does not move the focus")
            self.assertEqual(page.evaluate("document.querySelector('#articleAuthorName').getAttribute('aria-expanded')"), "true")
            no_modal = page.evaluate("""() => ({overlay: !!document.querySelector('.feed-modal-overlay[style*=flex]'),
              scrollLocked: ['hidden', 'clip'].includes(getComputedStyle(document.body).overflowY) || ['hidden', 'clip'].includes(getComputedStyle(document.documentElement).overflowY),
              modal: document.getElementById('authorCard').getAttribute('aria-modal')})""")
            self.assertEqual(no_modal, {"overlay": False, "scrollLocked": False, "modal": None})
        finally:
            ctx.close()

    def test_pointer_can_move_into_the_card_and_actions_do_not_open_the_material(self):
        ctx, page = self.open()
        try:
            self.hover(page, "#articleAuthorName")
            page.wait_for_timeout(600)
            state = card_state(page)
            # cross the gap into the card
            page.mouse.move(state["left"] + 20, state["top"] - 3)
            page.wait_for_timeout(60)
            page.mouse.move(state["left"] + 40, state["top"] + 30)
            page.wait_for_timeout(400)
            self.assertTrue(card_state(page)["open"], "the card stays open while the pointer is in it")
            url = page.url
            sub = page.locator("#authorCard .author-card-subscribe")
            before = sub.get_attribute("aria-pressed")
            sub.click()
            page.wait_for_function("(b) => document.querySelector('#authorCard .author-card-subscribe').getAttribute('aria-pressed') !== b",
                                   arg=before, timeout=5000)
            self.assertEqual(page.url, url, "acting in the card does not navigate")
            self.assertTrue(card_state(page)["open"])
            page.locator("#authorCard .author-card-subscribe").click()  # restore
            page.wait_for_function("(b) => document.querySelector('#authorCard .author-card-subscribe').getAttribute('aria-pressed') === b",
                                   arg=before, timeout=5000)
            page.mouse.move(5, 5)
            page.wait_for_timeout(150)
            self.assertTrue(card_state(page)["open"], "pinned after acting in it")
            page.mouse.click(5, 300)
            page.wait_for_timeout(100)
            self.assertFalse(card_state(page)["open"], "a click outside closes a pinned card")
        finally:
            ctx.close()

    def test_leaving_without_entering_closes_after_delay(self):
        ctx, page = self.open()
        try:
            self.hover(page, "#articleAuthorName")
            page.wait_for_timeout(600)
            page.mouse.move(5, 600)
            page.wait_for_timeout(80)
            self.assertTrue(card_state(page)["open"], "not before the close delay")
            page.wait_for_timeout(300)
            self.assertFalse(card_state(page)["open"])
        finally:
            ctx.close()

    def test_late_response_for_a_does_not_replace_b(self):
        ctx, page = self.open()
        try:
            def slow(route):
                time.sleep(0.9)
                route.continue_()
            page.route("**/api/users/%s" % AUTHOR, slow)
            page.locator("#articleAuthorName").click()
            page.wait_for_timeout(100)
            other = page.locator('.btn-author-profile[data-author-id="author_volkova"]').first
            other.scroll_into_view_if_needed()
            other.click()
            page.wait_for_function("() => document.querySelector('#authorCardName') && document.querySelector('#authorCardName').textContent.trim() === 'Елена Волкова'",
                                   timeout=5000)
            page.wait_for_timeout(1200)
            self.assertEqual(card_state(page)["name"], "Елена Волкова", "the late answer for A does not replace B")
            self.assertEqual(page.locator("#authorCard").count(), 1, "one card at a time")
        finally:
            ctx.close()

    def test_touch_tap_opens_second_tap_and_outside_close(self):
        ctx, page = self.open(width=375, height=740, touch=True)
        try:
            page.locator("#articleAuthorName").tap()
            page.wait_for_function("() => document.querySelector('#authorCardName') && !document.getElementById('authorCard').hidden && !document.querySelector('#authorCard[aria-busy]')", timeout=5000)
            state = card_state(page)
            self.assertTrue(state["left"] >= 0 and state["right"] <= state["vw"], state)
            self.assertTrue(state["top"] >= 0 and state["bottom"] <= state["vh"], state)
            heights = page.evaluate("[...document.querySelectorAll('#authorCard .author-card-btn')].map(b => b.getBoundingClientRect().height)")
            self.assertTrue(heights and min(heights) >= 44, heights)
            page.locator("#articleAuthorName").tap()
            page.wait_for_timeout(150)
            self.assertFalse(card_state(page)["open"], "second tap on the source closes")
            page.locator("#articleAuthorName").tap()
            page.wait_for_timeout(300)
            self.assertTrue(card_state(page)["open"])
            page.touchscreen.tap(20, 700)
            page.wait_for_timeout(150)
            self.assertFalse(card_state(page)["open"], "tap outside closes")
        finally:
            ctx.close()

    def test_keyboard_focus_enter_tab_and_escape(self):
        ctx, page = self.open()
        try:
            page.evaluate("document.querySelector('#articleAuthorAvatar').focus(); document.querySelector('#articleAuthorAvatar').blur()")
            for _ in range(40):
                page.keyboard.press("Tab")
                if page.evaluate("document.activeElement && document.activeElement.id") == "articleAuthorName":
                    break
            self.assertEqual(page.evaluate("document.activeElement.id"), "articleAuthorName")
            page.wait_for_timeout(600)
            state = card_state(page)
            self.assertTrue(state["open"], "keyboard focus shows the card")
            self.assertFalse(state["focusInside"], "showing does not move the focus")
            page.keyboard.press("Enter")
            page.wait_for_timeout(200)
            self.assertTrue(card_state(page)["focusInside"], "Enter moves to the actions")
            page.keyboard.press("Tab")
            self.assertTrue(card_state(page)["focusInside"], "Tab moves through the actions")
            page.keyboard.press("Escape")
            page.wait_for_timeout(100)
            self.assertFalse(card_state(page)["open"])
            self.assertEqual(page.evaluate("document.activeElement.id"), "articleAuthorName", "focus returns to the source")
            page.wait_for_timeout(500)
            self.assertFalse(card_state(page)["open"], "restoring the focus does not reopen it")
        finally:
            ctx.close()

    def test_card_stays_in_viewport_follows_scroll_and_closes_without_source(self):
        ctx, page = self.open(width=1280, height=600)
        try:
            page.evaluate("""() => { const el = document.querySelector('#articleAuthorName');
              window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY - window.innerHeight + 40); }""")
            page.wait_for_timeout(200)
            page.locator("#articleAuthorName").click()
            page.wait_for_function("() => !document.querySelector('#authorCard[aria-busy]') && document.querySelector('#authorCard .author-card-stats')", timeout=5000)
            page.wait_for_timeout(100)
            state = card_state(page)
            self.assertTrue(state["top"] >= 0 and state["bottom"] <= state["vh"], state)
            self.assertEqual(page.evaluate("document.getElementById('authorCard').dataset.side"), "top", "flips above near the bottom edge")
            trigger_top = page.evaluate("document.querySelector('#articleAuthorName').getBoundingClientRect().top")
            page.mouse.wheel(0, -120)
            page.wait_for_timeout(250)
            moved = page.evaluate("document.querySelector('#articleAuthorName').getBoundingClientRect().top") - trigger_top
            new_state = card_state(page)
            self.assertAlmostEqual(new_state["top"] - state["top"], moved, delta=2, msg="the card follows the source")
            page.evaluate("document.querySelector('#articleAuthorName').remove()")
            page.wait_for_timeout(200)
            self.assertFalse(card_state(page)["open"], "the card closes when its source leaves the DOM")
        finally:
            ctx.close()

    # ---- #272 design and states ----

    def test_metrics_match_the_profile(self):
        ctx, page = self.open()
        try:
            page.locator("#articleAuthorName").click()
            page.wait_for_function("() => !document.querySelector('#authorCard[aria-busy]') && document.querySelector('#authorCard .author-card-stat dd')", timeout=5000)
            stats = page.evaluate("""() => Object.fromEntries([...document.querySelectorAll('#authorCard .author-card-stat')]
              .map(s => [s.querySelector('dt').textContent, s.querySelector('dd').textContent]))""")
            rating = page.locator("#authorCard .author-card-rating span").inner_text()
            profile = page.evaluate("fetch('/api/users/%s').then(r => r.json()).then(d => d.profile)" % AUTHOR)
            title = page.evaluate("document.title")
        finally:
            ctx.close()
        self.assertEqual(stats, {"Подписчики": str(profile["followersCount"]), "Публикации": str(profile["publicationsCount"]),
                                 "Вопросы": str(profile["questionsCount"]), "Комментарии": str(profile["commentsCount"])})
        expected = profile["rating"]
        self.assertEqual(rating, ("+%d" % expected) if expected > 0 else ("−%d" % -expected if expected < 0 else "0"))
        self.assertTrue(title)

    def test_long_name_big_numbers_negative_rating_broken_avatar_at_320(self):
        fake = {"success": True, "profile": {
            "id": AUTHOR, "name": "Очень Длинное Имя Автора Константинопольский-Многоточиев Второй",
            "avatar": "/missing-avatar.png", "bio": "Короткое описание. " * 20, "rating": -5,
            "followersCount": 1234567, "publicationsCount": 0, "questionsCount": None, "commentsCount": 98765,
            "isSubscribed": False, "isOwnProfile": False}}
        ctx, page = self.open(width=320, height=700)
        try:
            page.route("**/api/users/%s" % AUTHOR, lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(fake)))
            page.locator("#articleAuthorName").click()
            page.wait_for_function("() => !document.querySelector('#authorCard[aria-busy]') && document.querySelector('#authorCard .author-card-stat dd')", timeout=5000)
            page.wait_for_timeout(300)
            r = page.evaluate("""() => {
              const c = document.getElementById('authorCard'); const cr = c.getBoundingClientRect();
              const out = [...c.querySelectorAll('*')].filter(e => { const b = e.getBoundingClientRect();
                return b.width > 0 && (b.right > cr.right + 0.5 || b.left < cr.left - 0.5); }).map(e => e.className);
              const stats = Object.fromEntries([...c.querySelectorAll('.author-card-stat')].map(s => [s.querySelector('dt').textContent,
                {v: s.querySelector('dd').textContent, t: s.getAttribute('title')}]));
              return {out, right: cr.right, vw: document.documentElement.clientWidth, stats,
                      rating: c.querySelector('.author-card-rating').textContent, negative: c.querySelector('.author-card-rating').classList.contains('is-negative'),
                      initials: getComputedStyle(c.querySelector('.author-card-initials')).display, img: !!c.querySelector('.author-card-avatar-img'),
                      bioLines: Math.round(c.querySelector('.author-card-bio').getBoundingClientRect().height / parseFloat(getComputedStyle(c.querySelector('.author-card-bio')).lineHeight))};
            }""")
            page.screenshot(path=os.path.join(self.temp_dir, "edge.png"))
        finally:
            ctx.close()
        self.assertEqual(r["out"], [], "nothing leaves the card")
        self.assertLessEqual(r["right"], r["vw"] - 12 + 0.5)
        self.assertEqual(r["rating"], "−5")
        self.assertTrue(r["negative"])
        self.assertNotEqual(r["stats"]["Подписчики"]["v"], "1234567", "big numbers are shortened")
        self.assertIn("1234567", r["stats"]["Подписчики"]["t"], "the exact value stays in the title")
        self.assertEqual(r["stats"]["Публикации"]["v"], "0", "zero is a valid value")
        self.assertEqual(r["stats"]["Вопросы"]["v"], "н/д", "unknown is not shown as zero")
        self.assertFalse(r["img"], "a broken avatar falls back to initials")
        self.assertLessEqual(r["bioLines"], 2)

    def test_error_retry_and_not_found(self):
        ctx, page = self.open()
        try:
            calls = {"n": 0}

            def flaky(route):
                calls["n"] += 1
                if calls["n"] == 1:
                    route.fulfill(status=500, body="{}")
                else:
                    route.continue_()
            page.route("**/api/users/%s" % AUTHOR, flaky)
            page.locator("#articleAuthorName").click()
            page.wait_for_selector("#authorCard .author-card-retry", timeout=5000)
            self.assertIn("Не удалось загрузить профиль", page.locator("#authorCard").inner_text())
            page.locator("#authorCard .author-card-retry").click()
            page.wait_for_function("() => document.querySelector('#authorCardName').textContent.trim() === 'Алексей Смирнов'", timeout=5000)
            page.unroute("**/api/users/%s" % AUTHOR)
            page.evaluate("""() => { const b = document.createElement('button'); b.className = 'btn-author-profile'; b.id = 'ghost';
              b.setAttribute('data-author-id', 'nobody-here'); b.textContent = 'ghost'; document.body.prepend(b); }""")
            page.locator("#ghost").click()
            page.wait_for_function("() => document.querySelector('#authorCardName').textContent.includes('не найден')", timeout=5000)
        finally:
            ctx.close()

    def test_guest_is_asked_to_sign_in_and_own_profile_has_no_subscribe(self):
        ctx, page = self.open(signed_in=False)
        try:
            page.locator("#articleAuthorName").click()
            page.wait_for_selector("#authorCard .author-card-subscribe", timeout=5000)
            page.locator("#authorCard .author-card-subscribe").click()
            page.wait_for_timeout(300)
            self.assertFalse(card_state(page)["open"])
            signin = page.evaluate("""() => { const m = document.getElementById('scAuthModal');
              return !!m && !m.hidden; }""")
            self.assertTrue(signin, "the shared sign-in opens")
        finally:
            ctx.close()

        conn_ctx, page = self.open()
        try:
            me = page.evaluate("window.SCAuth.currentUser.id")
            page.evaluate("""(id) => { const b = document.createElement('button'); b.className = 'btn-author-profile'; b.id = 'me';
              b.setAttribute('data-author-id', id); b.textContent = 'me'; document.body.prepend(b); }""", me)
            page.locator("#me").click()
            page.wait_for_selector("#authorCard .author-card-profile", timeout=5000)
            self.assertEqual(page.locator("#authorCard .author-card-subscribe").count(), 0)
            self.assertEqual(page.locator("#authorCard .author-card-bell").count(), 0)
            self.assertIn("Это ваш профиль", page.locator("#authorCard").inner_text())
        finally:
            conn_ctx.close()

    def test_both_themes_and_subscribed_state_are_distinct(self):
        colors = {}
        for theme in ("dark", "light"):
            ctx, page = self.open(theme=theme)
            try:
                page.locator("#articleAuthorName").click()
                page.wait_for_selector("#authorCard .author-card-subscribe", timeout=5000)
                sub = page.locator("#authorCard .author-card-subscribe")
                off = sub.evaluate("b => [getComputedStyle(b).backgroundColor, b.textContent, b.getAttribute('aria-pressed')]")
                sub.click()
                page.wait_for_function("() => document.querySelector('#authorCard .author-card-subscribe').getAttribute('aria-pressed') === 'true'", timeout=5000)
                on = page.locator("#authorCard .author-card-subscribe").evaluate("b => [getComputedStyle(b).backgroundColor, b.textContent, b.getAttribute('aria-pressed')]")
                page.locator("#authorCard .author-card-subscribe").click()
                page.wait_for_function("() => document.querySelector('#authorCard .author-card-subscribe').getAttribute('aria-pressed') === 'false'", timeout=5000)
                card_bg = page.evaluate("getComputedStyle(document.getElementById('authorCard')).backgroundColor")
                colors[theme] = card_bg
            finally:
                ctx.close()
            self.assertEqual(off[1:], ["Подписаться", "false"])
            self.assertEqual(on[1:], ["Вы подписаны", "true"])
            self.assertNotEqual(off[0], on[0], "subscribed looks different (%s)" % theme)
        self.assertNotEqual(colors["dark"], colors["light"])

    def test_comment_authors_open_the_card(self):
        ctx, page = self.open()
        try:
            btn = page.locator('.btn-author-profile[data-author-id="author_volkova"]').first
            btn.scroll_into_view_if_needed()
            box = btn.bounding_box()
            page.mouse.move(box["x"] + 5, box["y"] + 5)
            page.wait_for_timeout(700)
            self.assertEqual(card_state(page)["name"], "Елена Волкова")
        finally:
            ctx.close()


if __name__ == "__main__":
    unittest.main()
