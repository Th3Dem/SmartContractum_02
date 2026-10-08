#!/usr/bin/env python3
"""
tests/test_issue258_drafts_auth_race.py

Issue #258: DraftsManager bound its auth:change listener only after IndexedDB
opened. A sign-in that resolved in between was missed, so the editor treated
the signed-in user as a guest: drafts were not synced to the account and
server drafts were not listed or restored.

The race is made deterministic: /api/auth/status answers after 300 ms and
IndexedDB opens after 1.5 s, so the sign-in lands inside the window.

Browser checks run with RUN_BROWSER_SMOKE=1 and Playwright; set
PLAYWRIGHT_CDP_URL to drive an already running Chromium.
"""

import os
import re
import sys
import time
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from playwright.sync_api import sync_playwright  # noqa: F401
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from tests import test_issue252_draft_settings_sync as t252
BROWSER_SMOKE = True  # collected by tests/run_browser_smoke.py

DRAFTS_JS = os.path.join(PROJECT_ROOT, "frontend", "public", "js", "drafts.js")

# Delays the IndexedDB success callbacks without changing their order
SLOW_INDEXEDDB = """(() => {
  const open = indexedDB.open.bind(indexedDB);
  indexedDB.open = function (...args) {
    const req = open(...args);
    const handlers = {};
    ['onsuccess', 'onerror', 'onupgradeneeded'].forEach(k => Object.defineProperty(req, k, {
      configurable: true, set(fn) { handlers[k] = fn; }, get() { return handlers[k]; }
    }));
    req.addEventListener('upgradeneeded', e => handlers.onupgradeneeded && handlers.onupgradeneeded.call(req, e));
    req.addEventListener('success', e => setTimeout(() => handlers.onsuccess && handlers.onsuccess.call(req, e), 1500));
    req.addEventListener('error', e => setTimeout(() => handlers.onerror && handlers.onerror.call(req, e), 1500));
    return req;
  };
})();"""


class TestIssue258Static(unittest.TestCase):
    def test_signed_in_user_is_adopted_after_init(self):
        with open(DRAFTS_JS, encoding="utf-8") as f:
            js = f.read()
        self.assertEqual(len(re.findall(r"this\.bindEvents\(\);\n\s+await this\.adoptSignedInUser\(\);", js)), 2,
                         "both init paths (IndexedDB and localStorage fallback) adopt the user")
        self.assertIn("async adoptSignedInUser()", js)


@unittest.skipUnless(PLAYWRIGHT_AVAILABLE and os.environ.get("RUN_BROWSER_SMOKE") == "1",
                     "Browser smoke test enabled via RUN_BROWSER_SMOKE=1 and Playwright")
class TestIssue258Browser(t252.TestIssue252Browser):
    """Reuses the server, users and helpers of the #252 browser tests."""

    def racy_context(self, token=None):
        ctx = self.context(token)
        ctx.add_init_script(SLOW_INDEXEDDB)

        def slow_status(route):
            time.sleep(0.3)
            route.continue_()
        ctx.route("**/api/auth/status", slow_status)
        return ctx

    def manager_user(self, page, editor):
        expr = "window.EditorApp.Drafts" if editor == "editor.html" else "window.QuestionEditor.state.draftsManager"
        page.wait_for_function("() => window.SCAuth && window.SCAuth.currentUser !== undefined", timeout=5000)
        page.wait_for_timeout(2500)  # IndexedDB opens after 1.5 s
        return page.evaluate("() => ({auth: window.SCAuth.currentUser ? window.SCAuth.currentUser.id : null, "
                             "manager: %s.userId})" % expr)

    def test_manager_knows_the_signed_in_user_in_both_editors(self):
        user_id, token = self.session("race_both")
        for editor in ("editor.html", "question-editor.html"):
            with self.subTest(editor=editor):
                ctx = self.racy_context(token)
                try:
                    page = ctx.new_page()
                    page.goto(self.base + "/" + editor, wait_until="networkidle")
                    self.assertEqual(self.manager_user(page, editor), {"auth": user_id, "manager": user_id})
                finally:
                    ctx.close()

    def test_draft_reaches_account_and_opens_in_a_clean_browser_despite_the_race(self):
        user_id, token = self.session("race_writer")
        ctx = self.racy_context(token)
        try:
            page = ctx.new_page()
            page.goto(self.base + "/editor.html", wait_until="networkidle")
            self.manager_user(page, "editor.html")
            page.locator("#article-title").fill("Черновик после гонки входа")
            self.wait_account_saved(page)
        finally:
            ctx.close()
        rows = self.server_drafts(user_id)
        self.assertEqual([r["title"] for r in rows], ["Черновик после гонки входа"])

        ctx = self.racy_context(token)
        try:
            page = ctx.new_page()
            page.goto(self.base + "/editor.html", wait_until="networkidle")
            self.manager_user(page, "editor.html")
            page.locator("#btn-drafts-modal").click()
            page.locator("#drafts-modal .draft-item .btn-load").first.click()
            page.wait_for_function("() => document.getElementById('article-title').value === 'Черновик после гонки входа'",
                                   timeout=5000)
        finally:
            ctx.close()

    def test_guest_stays_a_guest(self):
        ctx = self.racy_context()
        try:
            page = ctx.new_page()
            sent = []
            page.on("request", lambda r: sent.append(r.url) if "/api/drafts" in r.url and r.method != "GET" else None)
            page.goto(self.base + "/editor.html", wait_until="networkidle")
            self.assertEqual(self.manager_user(page, "editor.html"), {"auth": None, "manager": None})
            page.locator("#article-title").fill("Гость")
            page.wait_for_timeout(2500)
        finally:
            ctx.close()
        self.assertEqual(sent, [])


# Keep the helpers, drop the inherited #252 scenarios: they run in their own module
for _name in [n for n in vars(t252.TestIssue252Browser) if n.startswith("test_")]:
    setattr(TestIssue258Browser, _name, None)
del _name

if __name__ == "__main__":
    unittest.main()
