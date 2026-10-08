#!/usr/bin/env python3
"""
tests/test_issue274_notification_center_browser.py

Issue #274 in the browser: a followed author's new publication appears in the shared notification center
with the unread badge, the item opens the material, the read state survives a reload, a material that is
no longer public shows a neutral item without a link, and switching accounts never shows the previous
user's list.

Runs with RUN_BROWSER_SMOKE=1 and Playwright; set PLAYWRIGHT_CDP_URL to drive an already running Chromium.
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
PASSWORD = "Center-pass-1"


@unittest.skipUnless(PLAYWRIGHT_AVAILABLE and os.environ.get("RUN_BROWSER_SMOKE") == "1",
                     "Browser smoke test enabled via RUN_BROWSER_SMOKE=1 and Playwright")
class TestNotificationCenterBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "center.db")
        server.DEFAULT_DB_PATH = cls.db_path
        init_db(cls.db_path, seed=False).close()
        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        cls.ids = {}
        for login, role, name in (("nc_mod", "moderator", "Модератор"), ("nc_author", "user", "Анна Автор"),
                                  ("nc_reader", "user", "Читатель"), ("nc_other", "user", "Другой")):
            uid = create_user(conn, login, login + "@example.com", PASSWORD, role=role, email_verified=True)["id"]
            with conn:
                conn.execute("INSERT OR REPLACE INTO user_profiles (user_id, name, created_at, updated_at) "
                             "VALUES (?, ?, '2026-01-01', '2026-01-01')", (uid, name))
            cls.ids[login] = uid
        conn.close()
        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR,
                                  seed=False, enforce_csrf=True)
        cls.base = "http://127.0.0.1:%d" % cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        reset_login_rate_limiter()
        cls.c = {login: Client(cls.base).login(login, PASSWORD) for login in cls.ids}

        author = cls.ids["nc_author"]
        assert cls.c["nc_reader"].request("PUT", "/api/authors/%s/notifications" % author, {"enabled": True})[0] == 200
        cls.sids = []
        for draft, title, kind in (("nc-pub", "Разбор газа <b>жирно</b>", "publication"),
                                   ("nc-hidden", "Скрытый заголовок 274", "publication"),
                                   ("nc-q", "Вопрос про EIP-712", "question")):
            status, body = cls.c["nc_author"].request("POST", "/api/moderation/submit",
                                                      submission_payload(draft, title=title, material_type=kind))
            assert status == 200, body
            sid = body["submissionId"]
            status, body = cls.c["nc_mod"].request("POST", "/api/admin/moderation/submissions/%s/decision" % sid,
                                                   {"decision": "approve"})
            assert status == 200, body
            cls.sids.append(sid)
        conn = sqlite3.connect(cls.db_path)
        with conn:
            conn.execute("UPDATE moderation_submissions SET status = 'rejected' WHERE id = ?", (cls.sids[1],))
            conn.execute("""INSERT INTO user_notifications (id, user_id, actor_id, actor_name, article_id, comment_id,
                            type, title, message, is_read, created_at)
                            VALUES ('notif_other_274', ?, 'x', 'X', ?, NULL, 'new_reply', 'Ответ для другого', 'm', 0,
                                    '2026-01-01T00:00:00+00:00')""", (cls.ids["nc_other"], cls.sids[0]))
        conn.close()

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

    def context_for(self, login, width=1280, height=900):
        ctx = self.browser.new_context(viewport={"width": width, "height": height})
        ctx.add_cookies([{"name": c.name, "value": c.value, "url": self.base} for c in self.c[login].jar])
        return ctx

    def open_popup(self, page):
        page.wait_for_function("() => window.SCNotifications && window.SCNotifications.notifications.length > 0",
                               timeout=10000)
        page.click("#headerNotificationsBtn")
        page.wait_for_selector("#headerNotifPopup[aria-expanded='true'] .notif-item", timeout=5000)

    def test_center_badge_link_read_state_and_neutral_item(self):
        ctx = self.context_for("nc_reader")
        try:
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(self.base + "/feed.html", wait_until="domcontentloaded")
            self.open_popup(page)
            self.assertEqual(page.locator("#headerNotifBadge").inner_text().strip(), "3")
            items = page.evaluate("""() => [...document.querySelectorAll('#notifListContainer .notif-item')].map(a => ({
                type: a.getAttribute('data-notif-type'), href: a.getAttribute('href'),
                unavailable: a.classList.contains('is-unavailable'),
                title: a.querySelector('.notif-item-title').textContent,
                msg: a.querySelector('.notif-item-msg').textContent,
                html: a.querySelector('.notif-item-msg').innerHTML}))""")
            by_href = {i["href"]: i for i in items}
            pub = by_href["article.html?id=%s" % self.sids[0]]
            self.assertEqual(pub["type"], "author_publication")
            self.assertEqual(pub["title"], "Новая публикация")
            self.assertIn("Анна Автор", pub["msg"])
            self.assertIn("<b>жирно</b>", pub["msg"], "title is shown as text")
            self.assertNotIn("<b>", pub["html"], "and never injected as markup")
            self.assertEqual(by_href["article.html?id=%s" % self.sids[2]]["title"], "Новый вопрос")
            hidden = next(i for i in items if i["unavailable"])
            self.assertEqual((hidden["href"], hidden["title"]), ("#", "Материал недоступен"))
            self.assertNotIn("Скрытый заголовок", page.locator("#notifListContainer").inner_text())

            # the neutral item stays on the page and is marked read
            page.locator("#notifListContainer .notif-item.is-unavailable").click()
            page.wait_for_function("() => document.getElementById('headerNotifBadge').textContent.trim() === '2'",
                                   timeout=5000)
            self.assertTrue(page.url.endswith("/feed.html"))

            # deep link opens the publication; the read state survives the navigation and a reload
            page.locator('#notifListContainer .notif-item[href="article.html?id=%s"]' % self.sids[0]).click()
            page.wait_for_url("**/article.html?id=%s" % self.sids[0], timeout=10000)
            page.reload(wait_until="domcontentloaded")
            page.wait_for_function("() => window.SCNotifications && window.SCNotifications.notifications.length === 3",
                                   timeout=10000)
            self.assertEqual(page.locator("#headerNotifBadge").inner_text().strip(), "1")
            self.assertEqual(errors, [])
        finally:
            ctx.close()

    def test_popup_stays_on_screen_at_every_width(self):
        """Scan, not fixed widths: the 376 to 450 px band used to push the popup off the left edge."""
        ctx = self.context_for("nc_reader")
        try:
            page = ctx.new_page()
            page.goto(self.base + "/feed.html", wait_until="domcontentloaded")
            self.open_popup(page)
            bad = []
            for width in list(range(320, 820, 10)) + [1024, 1280]:
                page.set_viewport_size({"width": width, "height": 800})
                r = page.evaluate("""() => { const b = document.getElementById('headerNotifPopup').getBoundingClientRect();
                    return {l: b.left, r: b.right, cw: document.documentElement.clientWidth,
                            hs: document.documentElement.scrollWidth > document.documentElement.clientWidth}; }""")
                if r["l"] < 0 or r["r"] > r["cw"] + 0.5 or r["hs"]:
                    bad.append((width, r))
            self.assertEqual(bad, [])
        finally:
            ctx.close()

    def test_account_switch_never_mixes_lists(self):
        ctx = self.context_for("nc_reader", width=375, height=740)
        try:
            page = ctx.new_page()
            # slow down the reader's list so it is still in flight when the account changes
            page.route("**/api/notifications", lambda route: (page.wait_for_timeout(800), route.continue_()))
            page.goto(self.base + "/feed.html", wait_until="domcontentloaded")
            page.wait_for_function("() => window.SCNotifications && window.SCNotifications.currentUser", timeout=10000)
            page.evaluate("""(other) => {
                document.cookie = 'sc_session=' + other.session + '; path=/';
                window.dispatchEvent(new CustomEvent('auth:change', {detail: {authenticated: true, user: {id: other.id}}}));
            }""", {"id": self.ids["nc_other"],
                   "session": next(c.value for c in self.c["nc_other"].jar if c.name == "sc_session")})
            page.wait_for_timeout(2500)
            state = page.evaluate("""() => ({n: window.SCNotifications.notifications.length,
                user: window.SCNotifications.currentUser.id,
                badge: getComputedStyle(document.getElementById('headerNotifBadge')).display,
                text: document.getElementById('notifListContainer').textContent})""")
            self.assertEqual(state["user"], self.ids["nc_other"])
            self.assertEqual(state["n"], 1, "the new account's own list loads at once, not on the next poll")
            self.assertIn("Ответ для другого", state["text"])
            self.assertNotIn("Анна Автор", state["text"], "the reader's late response is dropped")
            self.assertEqual(state["badge"], "block")
        finally:
            ctx.close()


if __name__ == "__main__":
    unittest.main()
