#!/usr/bin/env python3
"""
tests/test_issue275_author_bell_ui.py

Issue #275 (epic #270): the author bell in the mini card and in the full profile header, the private
"Авторы с уведомлениями" list in the owner's subscriptions, and the end-to-end path of the epic:
reader A turns the bell on for author B, B publishes, A gets the event and opens it; A turns the bell
off and the next material gives no event.

Static checks always run. The browser checks run with RUN_BROWSER_SMOKE=1 and Playwright; set
PLAYWRIGHT_CDP_URL to drive an already running Chromium.
"""

import os
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
from server import create_server, create_user, init_db, reset_login_rate_limiter
from tests.http_client import Client, submission_payload

FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")
BROWSER_SMOKE = True  # collected by tests/run_browser_smoke.py
PASSWORD = "Bell-ui-pass-1"
ARTICLE = "/article.html?id=art-01"
SEED_AUTHOR = "author_smirnov"
LABEL_OFF = "Уведомлять о новых публикациях и вопросах"
LABEL_ON = "Отключить уведомления автора"
HINT = "Подписка добавляет автора в вашу ленту. Колокольчик включает уведомления."


def read(rel_path):
    with open(os.path.join(FRONTEND_DIR, rel_path), encoding="utf-8") as f:
        return f.read()


class TestAuthorBellStatic(unittest.TestCase):
    def test_same_labels_and_hint_in_card_and_profile(self):
        profile_js = read("js/profile.js")
        for text in (LABEL_OFF, LABEL_ON, HINT, "Уведомления автора остаются включены",
                     "Автор скрыт из вашей ленты. Сначала уберите его из исключений."):
            self.assertIn(text, profile_js)
        self.assertIn("var AUTHOR_BELL_ENABLED = true;", profile_js)
        self.assertIn("'/summary'", profile_js, "the card uses the compact summary (#273)")
        html = read("profile.html")
        self.assertIn('id="btnProfileBell"', html)
        self.assertIn(HINT, html)
        self.assertIn('id="ownerNavAuthorBells"', html)
        self.assertIn('id="socialSubTabBells"', html)
        page_js = read("js/profile-page.js")
        self.assertIn("window.SCAuthorBell.set(", page_js, "one client for every view")
        self.assertNotIn("fetch('/api/authors/", page_js)

    def test_manage_link_and_hide_warning(self):
        self.assertIn("Управлять авторами", read("js/notifications.js"))
        self.assertIn("&subscriptions=bells", read("js/notifications.js"))
        self.assertIn("confirmExclusion(", read("js/feed.js"))
        self.assertIn("Скрыть и отключить уведомления", read("js/profile.js"))


def cookies_of(client, base):
    return [{"name": c.name, "value": c.value, "url": base} for c in client.jar]


@unittest.skipUnless(PLAYWRIGHT_AVAILABLE and os.environ.get("RUN_BROWSER_SMOKE") == "1",
                     "Browser smoke test enabled via RUN_BROWSER_SMOKE=1 and Playwright")
class TestAuthorBellBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "bell_ui.db")
        server.DEFAULT_DB_PATH = cls.db_path
        init_db(cls.db_path, seed=True).close()
        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        cls.ids = {}
        for login, role, name in (("bu_reader", "user", "Анна Читатель"), ("bu_other", "user", "Борис Другой"),
                                  ("bu_writer", "user", "Вера Писатель"), ("bu_mod", "moderator", "Модератор")):
            uid = create_user(conn, login, login + "@example.com", PASSWORD, role=role, email_verified=True)["id"]
            with conn:
                conn.execute("INSERT OR REPLACE INTO user_profiles (user_id, name, created_at, updated_at) "
                             "VALUES (?, ?, '2026-01-01', '2026-01-01')", (uid, name))
            cls.ids[login] = uid
        # extra authors for paging and search; one of them is blocked later
        cls.extra = []
        for i in range(23):
            login = "bu_extra_%02d" % i
            uid = create_user(conn, login, login + "@example.com", PASSWORD, email_verified=True)["id"]
            with conn:
                conn.execute("INSERT OR REPLACE INTO user_profiles (user_id, name, created_at, updated_at) "
                             "VALUES (?, ?, '2026-01-01', '2026-01-01')", (uid, "Дополнительный автор %02d" % i))
            cls.extra.append(uid)
        with conn:
            conn.execute("UPDATE users SET status = 'active' WHERE id = ?", (SEED_AUTHOR,))
        conn.close()
        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR,
                                  seed=False, enforce_csrf=True)
        cls.base = "http://127.0.0.1:%d" % cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        reset_login_rate_limiter()
        cls.c = {login: Client(cls.base).login(login, PASSWORD) for login in cls.ids}
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

    def setUp(self):
        conn = sqlite3.connect(self.db_path)
        with conn:
            for table in ("user_author_notifications", "user_subscriptions", "user_feed_exceptions"):
                conn.execute("DELETE FROM %s" % table)
            conn.execute("DELETE FROM user_notifications WHERE type IN ('author_publication', 'author_question')")
            conn.execute("UPDATE users SET status = 'active' WHERE id IN (%s)" % ",".join("?" * len(self.extra)), self.extra)
        conn.close()
        reset_login_rate_limiter()

    # helpers
    def db(self, sql, args=()):
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                return conn.execute(sql, args).fetchall()
        finally:
            conn.close()

    def bell_on(self, reader, author):
        return bool(self.db("SELECT 1 FROM user_author_notifications WHERE user_id = ? AND author_id = ?",
                            (self.ids[reader], author)))

    def subscribed(self, reader, author):
        return bool(self.db("SELECT 1 FROM user_subscriptions WHERE user_id = ? AND target_type = 'author' AND target_id = ?",
                            (self.ids[reader], author)))

    def context(self, login=None, width=1280, height=900, theme=None):
        ctx = self.browser.new_context(viewport={"width": width, "height": height})
        if theme:
            ctx.add_init_script("localStorage.setItem('sc_theme', '%s')" % theme)
        if login:
            ctx.add_cookies(cookies_of(self.c[login], self.base))
        return ctx

    def open_card(self, page):
        page.goto(self.base + ARTICLE, wait_until="networkidle")
        page.wait_for_selector("#articleAuthorName[data-author-id]", timeout=10000)
        page.locator("#articleAuthorName").click()
        page.wait_for_function("() => !document.querySelector('#authorCard[aria-busy]') && document.querySelector('#authorCard .author-card-actions')",
                               timeout=8000)

    def card_bell(self, page):
        return page.evaluate("""() => { const b = document.querySelector('#authorCard .author-card-bell');
            return b ? {pressed: b.getAttribute('aria-pressed'), label: b.getAttribute('aria-label'), disabled: b.disabled} : null; }""")

    def card_status(self, page):
        return page.evaluate("() => (document.querySelector('#authorCard .author-card-status') || {}).textContent || ''")

    def publish(self, title, draft):
        status, body = self.c["bu_writer"].request("POST", "/api/moderation/submit", submission_payload(draft, title=title))
        self.assertEqual(status, 200, body)
        sid = body["submissionId"]
        status, body = self.c["bu_mod"].request("POST", "/api/admin/moderation/submissions/%s/decision" % sid,
                                                {"decision": "approve"})
        self.assertEqual(status, 200, body)
        return sid

    # card
    def test_card_bell_four_combinations_with_subscription(self):
        ctx = self.context("bu_reader")
        try:
            page = ctx.new_page()
            self.open_card(page)
            self.assertEqual(self.card_bell(page), {"pressed": "false", "label": LABEL_OFF, "disabled": False})
            self.assertIn(HINT, page.locator("#authorCard").inner_text())

            # 1. bell on without subscription: no automatic subscription
            page.locator("#authorCard .author-card-bell").click()
            page.wait_for_function("() => document.querySelector('#authorCard .author-card-bell').getAttribute('aria-pressed') === 'true'", timeout=5000)
            self.assertTrue(self.bell_on("bu_reader", SEED_AUTHOR))
            self.assertFalse(self.subscribed("bu_reader", SEED_AUTHOR))
            self.assertEqual(self.card_bell(page)["label"], LABEL_ON)

            # 2. subscribe with the bell on
            page.locator("#authorCard .author-card-subscribe").click()
            page.wait_for_function("() => document.querySelector('#authorCard .author-card-subscribe').classList.contains('is-subscribed')", timeout=5000)
            self.assertTrue(self.subscribed("bu_reader", SEED_AUTHOR))

            # 3. unsubscribe keeps the bell and says so
            page.locator("#authorCard .author-card-subscribe").click()
            page.wait_for_function("() => !document.querySelector('#authorCard .author-card-subscribe').classList.contains('is-subscribed')", timeout=5000)
            self.assertIn("Уведомления автора остаются включены", self.card_status(page))
            self.assertTrue(self.bell_on("bu_reader", SEED_AUTHOR))
            self.assertEqual(self.card_bell(page)["pressed"], "true")

            # 4. subscribed, bell off
            page.locator("#authorCard .author-card-subscribe").click()
            page.wait_for_function("() => document.querySelector('#authorCard .author-card-subscribe').classList.contains('is-subscribed')", timeout=5000)
            page.locator("#authorCard .author-card-bell").click()
            page.wait_for_function("() => document.querySelector('#authorCard .author-card-bell').getAttribute('aria-pressed') === 'false'", timeout=5000)
            self.assertFalse(self.bell_on("bu_reader", SEED_AUTHOR))
            self.assertTrue(self.subscribed("bu_reader", SEED_AUTHOR))

            # reopening and reloading show the server state
            page.reload(wait_until="networkidle")
            page.locator("#articleAuthorName").click()
            page.wait_for_function("() => document.querySelector('#authorCard .author-card-bell')", timeout=8000)
            self.assertEqual(self.card_bell(page)["pressed"], "false")
        finally:
            ctx.close()

    def test_card_pending_blocks_second_write_and_error_keeps_true_state(self):
        ctx = self.context("bu_reader")
        try:
            page = ctx.new_page()
            puts = []
            state = {"fail": True}

            def handler(route):
                if route.request.method == "PUT":
                    puts.append(1)
                    if state["fail"]:
                        page.wait_for_timeout(400)
                        route.fulfill(status=500, content_type="application/json", body='{"success": false}')
                        return
                route.continue_()
            page.route("**/api/authors/*/notifications", handler)
            self.open_card(page)
            page.evaluate("() => { const b = document.querySelector('#authorCard .author-card-bell'); b.click(); b.click(); }")
            page.wait_for_function("() => (document.querySelector('#authorCard .author-card-status') || {}).textContent", timeout=5000)
            self.assertEqual(len(puts), 1, "a pending request blocks a second write")
            self.assertEqual(self.card_bell(page)["pressed"], "false", "an error never leaves a false on")
            self.assertFalse(self.card_bell(page)["disabled"], "the action can be repeated")
            self.assertIn("Не удалось", self.card_status(page))
            self.assertFalse(self.bell_on("bu_reader", SEED_AUTHOR))

            state["fail"] = False
            page.locator("#authorCard .author-card-bell").click()
            page.wait_for_function("() => document.querySelector('#authorCard .author-card-bell').getAttribute('aria-pressed') === 'true'", timeout=5000)
            self.assertTrue(self.bell_on("bu_reader", SEED_AUTHOR))
        finally:
            ctx.close()

    def test_excluded_author_is_explained_and_exclusion_unchanged(self):
        self.db("INSERT INTO user_feed_exceptions (user_id, target_type, target_id, target_title, created_at) "
                "VALUES (?, 'author', ?, 'x', '2026-01-01')", (self.ids["bu_reader"], SEED_AUTHOR))
        ctx = self.context("bu_reader")
        try:
            page = ctx.new_page()
            self.open_card(page)
            page.locator("#authorCard .author-card-bell").click()
            page.wait_for_function("() => (document.querySelector('#authorCard .author-card-status') || {}).textContent", timeout=5000)
            self.assertIn("Сначала уберите его из исключений", self.card_status(page))
            self.assertEqual(self.card_bell(page)["pressed"], "false")
            self.assertFalse(self.bell_on("bu_reader", SEED_AUTHOR))
            self.assertTrue(self.db("SELECT 1 FROM user_feed_exceptions WHERE user_id = ?", (self.ids["bu_reader"],)),
                            "the exclusion is not changed automatically")
        finally:
            ctx.close()

    def test_guest_signs_in_and_confirms_without_silent_action(self):
        ctx = self.context()
        try:
            page = ctx.new_page()
            self.open_card(page)
            page.locator("#authorCard .author-card-bell").click()
            page.wait_for_function("() => { const m = document.getElementById('scAuthModal'); return m && !m.hidden; }", timeout=5000)
            self.assertFalse(self.bell_on("bu_reader", SEED_AUTHOR), "no fake change for a guest")
            page.fill("#login-identifier", "bu_reader")
            page.fill("#login-password", PASSWORD)
            page.locator("#scAuthModal .sc-auth-submit").first.click()
            page.wait_for_function("() => document.activeElement && document.activeElement.classList.contains('author-card-bell')", timeout=8000)
            self.assertIn("Вы вошли", self.card_status(page))
            self.assertFalse(self.bell_on("bu_reader", SEED_AUTHOR), "the action is not done silently after sign-in")
            page.keyboard.press("Enter")
            page.wait_for_function("() => document.querySelector('#authorCard .author-card-bell').getAttribute('aria-pressed') === 'true'", timeout=5000)
            self.assertTrue(self.bell_on("bu_reader", SEED_AUTHOR))
        finally:
            ctx.close()

    # full profile and sync
    def test_profile_header_bell_and_sync_with_card_in_another_tab(self):
        ctx = self.context("bu_reader")
        try:
            profile = ctx.new_page()
            profile.goto(self.base + "/profile.html?id=" + SEED_AUTHOR, wait_until="networkidle")
            profile.wait_for_selector("#btnProfileBell:not([hidden])", timeout=8000)
            self.assertEqual(profile.locator("#btnProfileBell").get_attribute("aria-label"), LABEL_OFF)
            self.assertFalse(profile.locator("#profileBellHint").is_hidden())
            self.assertEqual(profile.locator("#profileBellHint").inner_text().strip(), HINT)

            article = ctx.new_page()
            self.open_card(article)
            article.locator("#authorCard .author-card-bell").click()
            article.wait_for_function("() => document.querySelector('#authorCard .author-card-bell').getAttribute('aria-pressed') === 'true'", timeout=5000)
            # the other tab follows without a reload
            profile.wait_for_function("() => document.getElementById('btnProfileBell').getAttribute('aria-pressed') === 'true'", timeout=5000)

            # and back from the profile header to the open card
            profile.locator("#btnProfileBell").click()
            profile.wait_for_function("() => document.getElementById('btnProfileBell').getAttribute('aria-pressed') === 'false'", timeout=5000)
            article.wait_for_function("() => document.querySelector('#authorCard .author-card-bell').getAttribute('aria-pressed') === 'false'", timeout=5000)
            self.assertFalse(self.bell_on("bu_reader", SEED_AUTHOR))

            # subscription from the header updates the card button and the follower count
            profile.locator("#btnProfileSubscribe").click()
            profile.wait_for_function("() => document.getElementById('btnProfileSubscribe').classList.contains('is-subscribed')", timeout=5000)
            article.wait_for_function("() => document.querySelector('#authorCard .author-card-subscribe').classList.contains('is-subscribed')", timeout=5000)
        finally:
            ctx.close()

    def test_own_and_foreign_profile(self):
        ctx = self.context("bu_reader")
        try:
            page = ctx.new_page()
            page.goto(self.base + "/profile.html?id=" + self.ids["bu_reader"], wait_until="networkidle")
            page.wait_for_selector("#profileOwnerNavWidget", state="visible", timeout=8000)
            self.assertTrue(page.locator("#btnProfileBell").is_hidden(), "own profile has no bell")
            self.assertTrue(page.locator("#btnProfileSubscribe").is_hidden())
            self.assertTrue(page.locator("#ownerNavAuthorBells").is_visible())

            page.goto(self.base + "/profile.html?id=" + self.ids["bu_other"], wait_until="networkidle")
            page.wait_for_selector("#btnProfileSubscribe", state="visible", timeout=8000)
            self.assertTrue(page.locator("#profileOwnerNavWidget").is_hidden())
            page.locator("#profileStatFollowingWrap").click()
            page.wait_for_function("() => document.getElementById('profileSocialList').textContent.includes('скрыт')", timeout=8000)
            self.assertTrue(page.locator("#socialSubTabBells").is_hidden(), "the private list is not shown on a foreign profile")
            self.assertTrue(page.locator("#socialBellsTools").is_hidden())
        finally:
            ctx.close()

    def test_bells_list_search_paging_turn_off_error_and_empty(self):
        reader = self.ids["bu_reader"]
        for uid in self.extra:
            self.db("INSERT INTO user_author_notifications (user_id, author_id, created_at) VALUES (?, ?, '2026-01-01')", (reader, uid))
        self.db("UPDATE users SET status = 'disabled' WHERE id = ?", (self.extra[0],))
        self.db("INSERT INTO user_subscriptions (user_id, target_type, target_id, target_title, created_at) "
                "VALUES (?, 'author', ?, 'x', '2026-01-01')", (reader, self.extra[1]))
        ctx = self.context("bu_reader", width=375, height=760)
        try:
            page = ctx.new_page()
            page.goto(self.base + "/profile.html?id=" + reader, wait_until="networkidle")
            page.wait_for_function("() => document.getElementById('ownerNavAuthorBellsCount').textContent === '23'", timeout=8000)
            page.locator("#ownerNavAuthorBells").click()
            page.wait_for_selector(".social-bell-row", timeout=8000)
            self.assertTrue(page.locator("#socialSubTabBells").evaluate("e => e.classList.contains('is-active')"))
            self.assertEqual(page.locator(".social-bell-row").count(), 20, "server paging")
            texts = page.locator("#profileSocialList").inner_text()
            self.assertIn("Без подписки, только уведомления", texts, "authors without a subscription are listed")
            page.locator("#btnSocialLoadMore").click()
            page.wait_for_function("() => document.querySelectorAll('.social-bell-row').length === 23", timeout=5000)
            self.assertIn("Автор недоступен", page.locator("#profileSocialList").inner_text())
            no_scroll = page.evaluate("() => document.documentElement.scrollWidth <= document.documentElement.clientWidth")
            self.assertTrue(no_scroll)

            # search by name
            page.fill("#socialBellsSearch", "автор 07")
            page.wait_for_function("() => document.querySelectorAll('.social-bell-row').length === 1", timeout=5000)

            # an error restores the row and the count
            page.route("**/api/authors/*/notifications", lambda r: r.fulfill(status=500, body="{}"))
            page.locator(".social-bell-off").click()
            page.wait_for_function("() => document.querySelectorAll('.social-bell-row').length === 1 && !document.querySelector('.social-bell-off').disabled", timeout=5000)
            self.assertEqual(page.locator("#socialSubBellsCount").inner_text(), "23")
            page.unroute("**/api/authors/*/notifications")

            # turning off removes the row, updates the count and keeps subscriptions
            page.locator(".social-bell-off").click()
            page.wait_for_function("() => document.getElementById('socialSubBellsCount').textContent === '22'", timeout=5000)
            self.assertEqual(page.locator(".social-bell-row").count(), 0)
            self.assertIn("Никого не нашли", page.locator("#profileSocialList").inner_text())
            self.assertEqual(page.locator("#ownerNavAuthorBellsCount").inner_text(), "22")

            # the unavailable author can be removed
            page.fill("#socialBellsSearch", "автор 00")
            page.wait_for_function("() => document.querySelectorAll('.social-bell-row').length === 1", timeout=5000)
            page.locator(".social-bell-off").click()
            page.wait_for_function("() => document.getElementById('socialSubBellsCount').textContent === '21'", timeout=5000)
            self.assertTrue(self.subscribed("bu_reader", self.extra[1]), "turning bells off never unsubscribes")

            # empty state explains how to turn it on
            self.db("DELETE FROM user_author_notifications WHERE user_id = ?", (reader,))
            page.fill("#socialBellsSearch", "")
            page.wait_for_selector(".social-bells-empty", timeout=5000)
            self.assertIn("колокольчик в карточке автора", page.locator(".social-bells-empty").inner_text())
        finally:
            ctx.close()

    def test_hide_author_warns_when_the_bell_is_on(self):
        self.db("INSERT INTO user_author_notifications (user_id, author_id, created_at) VALUES (?, ?, '2026-01-01')",
                (self.ids["bu_reader"], SEED_AUTHOR))
        ctx = self.context("bu_reader")
        try:
            page = ctx.new_page()
            page.goto(self.base + "/feed.html", wait_until="networkidle")
            result = page.evaluate("""async (author) => {
                const btn = document.createElement('button'); btn.textContent = 'Скрыть'; document.body.appendChild(btn);
                const first = await window.SCAuthorBell.confirmExclusion(author, btn);
                const text = btn.textContent;
                const second = await window.SCAuthorBell.confirmExclusion(author, btn);
                const plain = await window.SCAuthorBell.confirmExclusion('author_without_bell', btn);
                return {first, text, second, plain};
            }""", SEED_AUTHOR)
            self.assertEqual(result, {"first": False, "text": "Скрыть и отключить уведомления", "second": True, "plain": True})
        finally:
            ctx.close()

    def test_manage_link_opens_the_list(self):
        ctx = self.context("bu_reader")
        try:
            page = ctx.new_page()
            page.goto(self.base + "/feed.html", wait_until="networkidle")
            page.click("#headerNotificationsBtn")
            link = page.locator("#notifManageAuthorsLink")
            link.wait_for(state="visible", timeout=5000)
            link.click()
            page.wait_for_url("**/profile.html?id=%s&subscriptions=bells" % self.ids["bu_reader"], timeout=8000)
            page.wait_for_selector("#socialSubTabBells.is-active", timeout=8000)
        finally:
            ctx.close()

    def test_account_switch_clears_personal_state(self):
        ctx = self.context("bu_reader")
        try:
            page = ctx.new_page()
            self.db("INSERT INTO user_author_notifications (user_id, author_id, created_at) VALUES (?, ?, '2026-01-01')",
                    (self.ids["bu_reader"], SEED_AUTHOR))
            page.goto(self.base + "/profile.html?id=" + SEED_AUTHOR, wait_until="networkidle")
            page.wait_for_function("() => document.getElementById('btnProfileBell').getAttribute('aria-pressed') === 'true'", timeout=8000)
            other = next(c.value for c in self.c["bu_other"].jar if c.name == "sc_session")
            page.evaluate("""(args) => { document.cookie = 'sc_session=' + args.s + '; path=/';
                window.dispatchEvent(new CustomEvent('auth:change', {detail: {authenticated: true, user: {id: args.id}}})); }""",
                          {"s": other, "id": self.ids["bu_other"]})
            page.wait_for_function("() => document.getElementById('btnProfileBell').getAttribute('aria-pressed') === 'false'", timeout=8000)
        finally:
            ctx.close()

    # themes, mobile, keyboard
    def test_themes_mobile_and_keyboard(self):
        for theme in ("light", "dark"):
            for width in (320, 414, 1280):
                ctx = self.context("bu_reader", width=width, height=800, theme=theme)
                try:
                    page = ctx.new_page()
                    page.goto(self.base + "/profile.html?id=" + SEED_AUTHOR, wait_until="networkidle")
                    page.wait_for_selector("#btnProfileBell:not([hidden])", timeout=8000)
                    r = page.evaluate("""() => { const b = document.getElementById('btnProfileBell').getBoundingClientRect();
                        const s = getComputedStyle(document.getElementById('btnProfileBell'));
                        return {right: b.right, cw: document.documentElement.clientWidth, h: b.height, color: s.color, bg: s.backgroundColor,
                                hs: document.documentElement.scrollWidth > document.documentElement.clientWidth}; }""")
                    self.assertLessEqual(r["right"], r["cw"], (theme, width))
                    self.assertFalse(r["hs"], (theme, width))
                    self.assertGreaterEqual(r["h"], 34)
                    self.assertNotEqual(r["color"], r["bg"])
                finally:
                    ctx.close()
        ctx = self.context("bu_reader")
        try:
            page = ctx.new_page()
            page.goto(self.base + "/profile.html?id=" + SEED_AUTHOR, wait_until="networkidle")
            page.wait_for_selector("#btnProfileBell:not([hidden])", timeout=8000)
            page.focus("#btnProfileSubscribe")
            page.keyboard.press("Tab")
            self.assertEqual(page.evaluate("document.activeElement.id"), "btnProfileBell")
            page.keyboard.press("Space")
            page.wait_for_function("() => document.getElementById('btnProfileBell').getAttribute('aria-pressed') === 'true'", timeout=5000)
            self.assertTrue(self.bell_on("bu_reader", SEED_AUTHOR))
        finally:
            ctx.close()

    # epic #270 end to end
    def test_end_to_end_bell_publication_event_and_off(self):
        writer = self.ids["bu_writer"]
        ctx = self.context("bu_reader")
        try:
            page = ctx.new_page()
            page.goto(self.base + "/profile.html?id=" + writer, wait_until="networkidle")
            page.wait_for_selector("#btnProfileBell:not([hidden])", timeout=8000)
            page.locator("#btnProfileBell").click()
            page.wait_for_function("() => document.getElementById('btnProfileBell').getAttribute('aria-pressed') === 'true'", timeout=5000)

            sid = self.publish("Сквозная проверка эпика 270", "e2e-270-first")

            page.goto(self.base + "/feed.html", wait_until="networkidle")
            page.wait_for_function("() => window.SCNotifications && SCNotifications.notifications.some(n => n.articleId === '%s')" % sid,
                                   timeout=10000)
            page.click("#headerNotificationsBtn")
            item = page.locator('#notifListContainer .notif-item[href="article.html?id=%s"]' % sid)
            item.wait_for(state="visible", timeout=5000)
            self.assertIn("Новая публикация", item.inner_text())
            self.assertIn("Вера Писатель", item.inner_text())
            item.click()
            page.wait_for_url("**/article.html?id=%s" % sid, timeout=8000)

            # off from the mini card on the material itself
            page.wait_for_selector("#articleAuthorName[data-author-id]", timeout=8000)
            page.locator("#articleAuthorName").click()
            page.wait_for_function("() => document.querySelector('#authorCard .author-card-bell') && document.querySelector('#authorCard .author-card-bell').getAttribute('aria-pressed') === 'true'", timeout=8000)
            page.locator("#authorCard .author-card-bell").click()
            page.wait_for_function("() => document.querySelector('#authorCard .author-card-bell').getAttribute('aria-pressed') === 'false'", timeout=5000)

            second = self.publish("Второй материал после отключения", "e2e-270-second")
            rows = self.db("SELECT article_id FROM user_notifications WHERE user_id = ? AND type = 'author_publication'",
                           (self.ids["bu_reader"],))
            self.assertEqual([r[0] for r in rows], [sid], "no event after the bell is off: %s" % second)
        finally:
            ctx.close()


if __name__ == "__main__":
    unittest.main()
