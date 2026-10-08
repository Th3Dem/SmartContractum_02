#!/usr/bin/env python3
"""
tests/test_issue260_drafts_list_escaping.py

Issue #260: the drafts list ("Черновики" in both editors) must show the title,
snippet and tags of a draft as text. Before, they were inserted into
innerHTML as is, so a title like <img onerror> ran when the list opened.

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

FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")
BROWSER_SMOKE = True  # collected by tests/run_browser_smoke.py

EVIL_TITLE = '<img src=x onerror="window.__xss_title=1">Заголовок'
EVIL_SNIPPET = '<script>window.__xss_snippet=1</script><b>жирный</b> отрывок'
EVIL_TAG = '<img src=x onerror="window.__xss_tag=1">тег'


class TestIssue260Static(unittest.TestCase):
    def test_list_markup_escapes_every_draft_field(self):
        with open(os.path.join(FRONTEND_DIR, "js", "drafts.js"), encoding="utf-8") as f:
            js = f.read()
        block = js[js.index("item.innerHTML = `"):]
        block = block[:block.index("`;")]
        for value in re.findall(r"\$\{([^}]*)\}", block):
            self.assertTrue(value.startswith("escapeHtml(") or value in ("snippetHtml", "tagsHtml"), value)
        self.assertIn("${escapeHtml(snippetText)}", js)
        self.assertIn("${escapeHtml(t)}", js)


@unittest.skipUnless(PLAYWRIGHT_AVAILABLE and os.environ.get("RUN_BROWSER_SMOKE") == "1",
                     "Browser smoke test enabled via RUN_BROWSER_SMOKE=1 and Playwright")
class TestIssue260Browser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "issue260.db")
        server.DEFAULT_DB_PATH = cls.db_path
        init_db(cls.db_path, seed=False).close()
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

    def open_list_with_drafts(self, editor, manager):
        ctx = self.browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        page.goto(self.base + "/" + editor, wait_until="networkidle")
        page.wait_for_function("() => { const m = %s; return m && m.db; }" % manager, timeout=8000)
        material = "question" if editor == "question-editor.html" else "publication"
        prefix = "draft_q_" if material == "question" else "draft_"
        page.evaluate("""([manager, material, prefix, evil, normal]) => {
          const dm = eval(manager);
          const base = {materialType: material, schema: 'antigravity-editor-v2', revision: 1, userId: null,
                        wordCount: 3, readingTime: 1, delta: {ops: [{insert: 'text\\n'}]}, html: '<p>text</p>'};
          return Promise.all([
            dm.putToDB(Object.assign({}, base, {id: prefix + 'evil', title: evil.title, snippet: evil.snippet,
                                                tags: [evil.tag], updatedAt: Date.now()})),
            dm.putToDB(Object.assign({}, base, {id: prefix + 'normal', title: normal, snippet: 'Обычный отрывок',
                                                tags: ['solidity'], updatedAt: Date.now() - 1000})),
          ]);
        }""", [manager, material, prefix, {"title": EVIL_TITLE, "snippet": EVIL_SNIPPET, "tag": EVIL_TAG},
               "Обычный черновик"])
        page.locator("#btn-drafts-modal").click()
        page.wait_for_selector("#drafts-modal .draft-item", timeout=5000)
        page.wait_for_timeout(300)
        return ctx, page

    def test_malicious_fields_are_shown_as_text_in_both_editors(self):
        for editor, manager in (("editor.html", "window.EditorApp && window.EditorApp.Drafts"),
                                ("question-editor.html", "window.QuestionEditor && window.QuestionEditor.state.draftsManager")):
            with self.subTest(editor=editor):
                ctx, page = self.open_list_with_drafts(editor, manager)
                try:
                    r = page.evaluate("""() => {
                      const list = document.getElementById('drafts-list');
                      return {xss: [window.__xss_title, window.__xss_snippet, window.__xss_tag],
                              injected: list.querySelectorAll('img, script, b').length,
                              text: list.innerText};
                    }""")
                    items = page.locator("#drafts-modal .draft-item").count()
                finally:
                    ctx.close()
                self.assertEqual(r["xss"], [None, None, None], "no handler or script ran")
                self.assertEqual(r["injected"], 0, "no elements from draft data in the list")
                self.assertIn(EVIL_TITLE, r["text"])
                self.assertIn("<b>жирный</b> отрывок", r["text"])
                self.assertIn(EVIL_TAG, r["text"])
                self.assertEqual(items, 2)

    def test_normal_draft_still_opens_and_shows_its_details(self):
        ctx, page = self.open_list_with_drafts("editor.html", "window.EditorApp && window.EditorApp.Drafts")
        try:
            item = page.locator("#drafts-modal .draft-item", has_text="Обычный черновик")
            text = item.inner_text()
            self.assertIn("Обычный отрывок", text)
            self.assertIn("solidity", text)
            self.assertIn("3 сл.", text)
            item.locator(".btn-load").click()
            page.wait_for_function("() => document.getElementById('article-title').value === 'Обычный черновик'", timeout=5000)
        finally:
            ctx.close()


if __name__ == "__main__":
    unittest.main()
