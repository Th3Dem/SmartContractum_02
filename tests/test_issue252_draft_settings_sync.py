#!/usr/bin/env python3
"""
tests/test_issue252_draft_settings_sync.py

Issue #252: drafts of signed-in users must reach the account. The editors send
publicationSettings as a JSON object; the API stores it as JSON text and
returns it as an object. Rich content (Quill delta and html) is stored too, so
a draft opens with its content and settings in a clean browser on the same
account. Unsupported types get a JSON 400 instead of a dropped connection.

The API checks always run. The browser checks run with RUN_BROWSER_SMOKE=1 and
Playwright; set PLAYWRIGHT_CDP_URL to drive an already running Chromium
instead of launching one.
"""

import datetime
import json
import os
import secrets
import shutil
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.error
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
from tests.http_client import Client

FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")
BROWSER_SMOKE = True  # collected by tests/run_browser_smoke.py
PASSWORD = "Drafts-pass-1"

PUBLICATION_SETTINGS = {
    "materialType": "publication",
    "type": "article",
    "keywords": ["solidity", "газ"],
    "topics": ["smart-contracts-development"],
    "nested": {"level": 2, "flags": [True, None, "x"]},
}
QUESTION_SETTINGS = {
    "materialType": "question",
    "type": "question",
    "keywords": ["uups", "proxy"],
    "targetAudience": "developers",
}
DELTA = {"ops": [{"insert": "Жирный", "attributes": {"bold": True}}, {"insert": " текст\n"}]}
HTML = "<p><strong>Жирный</strong> текст</p>"


def start_server(test_case, name):
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, name + ".db")
    server.DEFAULT_DB_PATH = db_path
    init_db(db_path, seed=False).close()
    httpd = create_server(host="127.0.0.1", port=0, db_path=db_path, directory=FRONTEND_DIR, seed=False)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    test_case.temp_dir, test_case.db_path, test_case.httpd = temp_dir, db_path, httpd
    test_case.base = "http://127.0.0.1:%d" % httpd.server_address[1]


def stop_server(test_case):
    test_case.httpd.shutdown()
    test_case.httpd.server_close()
    shutil.rmtree(test_case.temp_dir, ignore_errors=True)


def add_user(db_path, login):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return create_user(conn, login, login + "@example.com", PASSWORD, email_verified=True)["id"]
    finally:
        conn.close()


def db_row(db_path, draft_id):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM user_drafts WHERE id = ?", (draft_id,)).fetchone()
    finally:
        conn.close()


class TestIssue252DraftsApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        start_server(cls, "issue252_api")
        cls.owner_id = add_user(cls.db_path, "draft_owner")
        add_user(cls.db_path, "draft_stranger")
        cls.owner = Client(cls.base).login("draft_owner", PASSWORD)
        cls.stranger = Client(cls.base).login("draft_stranger", PASSWORD)

    @classmethod
    def tearDownClass(cls):
        stop_server(cls)

    def create(self, draft_id, material_type, settings, **extra):
        payload = {"id": draft_id, "materialType": material_type, "title": "Черновик " + draft_id,
                   "content": "Жирный текст", "publicationSettings": settings}
        payload.update(extra)
        return self.owner.request("POST", "/api/drafts", payload)

    def test_create_with_object_settings_for_both_types(self):
        for draft_id, material_type, settings in (("d-pub", "publication", PUBLICATION_SETTINGS),
                                                  ("d-q", "question", QUESTION_SETTINGS)):
            with self.subTest(material_type=material_type):
                status, body = self.create(draft_id, material_type, settings, delta=DELTA, html=HTML)
                self.assertEqual(status, 201, body)
                self.assertTrue(body["success"])
                self.assertEqual(body["draft"]["publicationSettings"], settings)
                self.assertEqual(body["draft"]["revision"], 1)
                row = db_row(self.db_path, draft_id)
                self.assertEqual(row["user_id"], self.owner_id)
                self.assertEqual(row["material_type"], material_type)
                self.assertEqual(json.loads(row["publication_settings"]), settings)
                self.assertEqual(json.loads(row["content_delta"]), DELTA)
                self.assertEqual(row["content_html"], HTML)

    def test_get_one_and_list_return_the_same_objects(self):
        self.create("d-get", "publication", PUBLICATION_SETTINGS, delta=DELTA, html=HTML)
        status, one = self.owner.request("GET", "/api/drafts/d-get")
        self.assertEqual(status, 200)
        self.assertEqual(one["draft"]["publicationSettings"], PUBLICATION_SETTINGS)
        self.assertEqual(one["draft"]["delta"], DELTA)
        self.assertEqual(one["draft"]["html"], HTML)
        status, listing = self.owner.request("GET", "/api/drafts?material_type=publication")
        self.assertEqual(status, 200)
        listed = [d for d in listing["drafts"] if d["id"] == "d-get"][0]
        self.assertEqual(listed, one["draft"])
        status, questions = self.owner.request("GET", "/api/drafts?material_type=question")
        self.assertNotIn("d-get", [d["id"] for d in questions["drafts"]], "types are not mixed")

    def test_put_updates_content_settings_and_revision_and_rejects_stale_revision(self):
        self.create("d-put", "question", QUESTION_SETTINGS, delta=DELTA, html=HTML)
        new_settings = dict(QUESTION_SETTINGS, keywords=["uups", "proxy", "storage"])
        new_delta = {"ops": [{"insert": "Новый текст\n"}]}
        status, body = self.owner.request("PUT", "/api/drafts/d-put", {
            "revision": 1, "title": "Обновлено", "content": "Новый текст",
            "publicationSettings": new_settings, "delta": new_delta, "html": "<p>Новый текст</p>"})
        self.assertEqual(status, 200, body)
        self.assertEqual(body["draft"]["revision"], 2)
        self.assertEqual(body["draft"]["publicationSettings"], new_settings)
        self.assertEqual(body["draft"]["delta"], new_delta)

        before = dict(db_row(self.db_path, "d-put"))
        status, body = self.owner.request("PUT", "/api/drafts/d-put", {
            "revision": 1, "title": "Старое", "publicationSettings": {"keywords": []}})
        self.assertEqual(status, 409)
        self.assertEqual(body["error"], "CONFLICT")
        self.assertEqual(body["serverDraft"]["publicationSettings"], new_settings)
        self.assertEqual(dict(db_row(self.db_path, "d-put")), before, "no partial write on conflict")

    def test_put_without_settings_keeps_stored_settings(self):
        self.create("d-keep", "publication", PUBLICATION_SETTINGS)
        status, body = self.owner.request("PUT", "/api/drafts/d-keep", {"revision": 1, "title": "Только заголовок"})
        self.assertEqual(status, 200, body)
        self.assertEqual(body["draft"]["publicationSettings"], PUBLICATION_SETTINGS)

    def test_null_empty_and_json_string_settings(self):
        for draft_id, settings, expected in (("d-null", None, None), ("d-empty", "", None),
                                             ("d-obj-empty", {}, {}),
                                             ("d-str", json.dumps(PUBLICATION_SETTINGS), PUBLICATION_SETTINGS)):
            with self.subTest(settings=settings):
                status, body = self.create(draft_id, "publication", settings)
                self.assertEqual(status, 201, body)
                self.assertEqual(body["draft"]["publicationSettings"], expected)

    def test_unsupported_types_get_a_json_error(self):
        cases = [
            {"publicationSettings": ["a", "b"]},
            {"publicationSettings": 5},
            {"publicationSettings": True},
            {"publicationSettings": "not json"},
            {"delta": "not json"},
            {"delta": [1, 2]},
            {"html": {"a": 1}},
            {"title": {"a": 1}},
            {"content": ["x"]},
            {"companyId": 7},
        ]
        for i, extra in enumerate(cases):
            with self.subTest(extra=extra):
                payload = {"id": "d-bad-%d" % i, "materialType": "publication", "title": "t", "content": "c"}
                payload.update(extra)
                status, body = self.owner.request("POST", "/api/drafts", payload)
                self.assertEqual(status, 400, body)
                self.assertFalse(body["success"])
                self.assertIsNone(db_row(self.db_path, "d-bad-%d" % i))
        self.create("d-bad-put", "publication", PUBLICATION_SETTINGS)
        for extra in ({"publicationSettings": [1]}, {"revision": "1"}, {"materialType": "poll"}):
            with self.subTest(put=extra):
                status, body = self.owner.request("PUT", "/api/drafts/d-bad-put", dict({"revision": 1}, **extra))
                self.assertEqual(status, 400, body)
        self.assertEqual(json.loads(db_row(self.db_path, "d-bad-put")["publication_settings"]), PUBLICATION_SETTINGS)

    def test_existing_records_are_read_without_errors(self):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        conn = sqlite3.connect(self.db_path)
        with conn:
            for draft_id, raw in (("legacy-json", json.dumps(QUESTION_SETTINGS)), ("legacy-text", "plain words"),
                                  ("legacy-null", None)):
                conn.execute("""INSERT INTO user_drafts (id, user_id, material_type, title, content, publication_settings,
                                revision, created_at, updated_at) VALUES (?, ?, 'question', 't', 'старый текст', ?, 3, ?, ?)""",
                             (draft_id, self.owner_id, raw, now, now))
        conn.close()
        expected = {"legacy-json": QUESTION_SETTINGS, "legacy-text": None, "legacy-null": None}
        for draft_id, settings in expected.items():
            with self.subTest(draft_id=draft_id):
                status, body = self.owner.request("GET", "/api/drafts/" + draft_id)
                self.assertEqual(status, 200)
                self.assertEqual(body["draft"]["publicationSettings"], settings)
                self.assertIsNone(body["draft"]["delta"])
                self.assertEqual(body["draft"]["content"], "старый текст")
        self.assertEqual(db_row(self.db_path, "legacy-text")["publication_settings"], "plain words",
                         "reading does not rewrite stored data")

    def test_other_user_and_anonymous_are_refused(self):
        self.create("d-private", "publication", PUBLICATION_SETTINGS)
        self.assertEqual(self.stranger.request("GET", "/api/drafts/d-private")[0], 403)
        self.assertEqual(self.stranger.request("PUT", "/api/drafts/d-private", {"revision": 1, "title": "x"})[0], 403)
        self.assertEqual(self.stranger.request("POST", "/api/drafts", {"id": "d-private", "materialType": "publication"})[0], 403)
        self.assertEqual(self.stranger.request("DELETE", "/api/drafts/d-private")[0], 403)
        status, listing = self.stranger.request("GET", "/api/drafts")
        self.assertNotIn("d-private", [d["id"] for d in listing["drafts"]])
        anonymous = Client(self.base)
        self.assertEqual(anonymous.request("GET", "/api/drafts")[0], 401)
        self.assertEqual(anonymous.request("GET", "/api/drafts/d-private")[0], 401)
        self.assertEqual(db_row(self.db_path, "d-private")["title"], "Черновик d-private")


class TestIssue256StaleSave(unittest.TestCase):
    """Issue #256: a stale save through POST (the editor's path while revision is 1)
    must not overwrite a newer server version."""

    @classmethod
    def setUpClass(cls):
        start_server(cls, "issue256_api")
        add_user(cls.db_path, "two_tabs")
        cls.tab_a = Client(cls.base).login("two_tabs", PASSWORD)
        cls.tab_b = Client(cls.base).login("two_tabs", PASSWORD)

    @classmethod
    def tearDownClass(cls):
        stop_server(cls)

    def payload(self, draft_id, material_type, label, revision):
        return {"id": draft_id, "materialType": material_type, "revision": revision,
                "title": "Title " + label, "content": "Text " + label, "html": "<p>%s</p>" % label,
                "delta": {"ops": [{"insert": label + "\n"}]},
                "publicationSettings": {"materialType": material_type, "keywords": [label]}}

    def test_stale_post_from_second_tab_gets_conflict_without_changes(self):
        for material_type in ("publication", "question"):
            with self.subTest(material_type=material_type):
                draft_id = "tabs-" + material_type
                status, _ = self.tab_a.request("POST", "/api/drafts", self.payload(draft_id, material_type, "Initial", 1))
                self.assertEqual(status, 201)
                status, body = self.tab_a.request("POST", "/api/drafts", self.payload(draft_id, material_type, "A", 1))
                self.assertEqual((status, body["draft"]["revision"]), (200, 2))
                before = dict(db_row(self.db_path, draft_id))

                status, body = self.tab_b.request("POST", "/api/drafts", self.payload(draft_id, material_type, "B", 1))
                self.assertEqual(status, 409, body)
                self.assertEqual(body["error"], "CONFLICT")
                self.assertEqual(body["serverDraft"]["content"], "Text A")
                self.assertEqual(body["serverDraft"]["revision"], 2)
                self.assertEqual(dict(db_row(self.db_path, draft_id)), before, "no change on conflict")
                _, got = self.tab_a.request("GET", "/api/drafts/" + draft_id)
                self.assertEqual((got["draft"]["title"], got["draft"]["html"], got["draft"]["revision"]),
                                 ("Title A", "<p>A</p>", 2))
                self.assertEqual(got["draft"]["publicationSettings"]["keywords"], ["A"])
                self.assertEqual(got["draft"]["delta"], {"ops": [{"insert": "A\n"}]})

    def test_post_to_existing_draft_without_revision_conflicts(self):
        self.tab_a.request("POST", "/api/drafts", self.payload("no-rev", "publication", "A", 1))
        before = dict(db_row(self.db_path, "no-rev"))
        payload = self.payload("no-rev", "publication", "B", None)
        del payload["revision"]
        status, _ = self.tab_b.request("POST", "/api/drafts", payload)
        self.assertEqual(status, 409)
        self.assertEqual(dict(db_row(self.db_path, "no-rev")), before)

    def test_fresh_saves_and_put_protection_keep_working(self):
        status, body = self.tab_a.request("POST", "/api/drafts", self.payload("fresh", "question", "1", 1))
        self.assertEqual((status, body["draft"]["revision"]), (201, 1))
        status, body = self.tab_a.request("POST", "/api/drafts", self.payload("fresh", "question", "2", 1))
        self.assertEqual((status, body["draft"]["revision"]), (200, 2))
        status, body = self.tab_a.request("PUT", "/api/drafts/fresh", self.payload("fresh", "question", "3", 2))
        self.assertEqual((status, body["draft"]["revision"]), (200, 3))
        status, _ = self.tab_b.request("PUT", "/api/drafts/fresh", self.payload("fresh", "question", "old", 2))
        self.assertEqual(status, 409)
        self.assertEqual(db_row(self.db_path, "fresh")["content"], "Text 3")

    def test_concurrent_saves_of_the_same_revision_let_one_win(self):
        self.tab_a.request("POST", "/api/drafts", self.payload("race", "publication", "start", 1))
        token = [c.value for c in self.tab_a.jar if c.name == "sc_session"][0]

        def save(label, revision, results, method="POST", path="/api/drafts"):
            data = json.dumps(self.payload("race", "publication", label, revision)).encode("utf-8")
            req = urllib.request.Request(self.base + path, data=data, method=method,
                                         headers={"Content-Type": "application/json", "Authorization": "Bearer " + token})
            try:
                with urllib.request.urlopen(req, timeout=10) as res:
                    results.append(res.status)
            except urllib.error.HTTPError as e:
                results.append(e.code)

        for round_no in range(8):
            revision = db_row(self.db_path, "race")["revision"]
            results = []
            method, path = ("POST", "/api/drafts") if round_no % 2 == 0 else ("PUT", "/api/drafts/race")
            threads = [threading.Thread(target=save, args=("r%d-%d" % (round_no, i), revision, results, method, path))
                       for i in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            with self.subTest(round=round_no, method=method):
                self.assertEqual(sorted(results), [200, 409, 409, 409])
                self.assertEqual(db_row(self.db_path, "race")["revision"], revision + 1)


class TestIssue252Migration(unittest.TestCase):
    def test_old_table_gets_new_columns_and_keeps_rows(self):
        temp_dir = tempfile.mkdtemp()
        try:
            db_path = os.path.join(temp_dir, "old.db")
            init_db(db_path, seed=False).close()
            conn = sqlite3.connect(db_path)
            with conn:
                conn.execute("DROP TABLE user_drafts")
                conn.execute("""CREATE TABLE user_drafts (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, material_type TEXT NOT NULL,
                                title TEXT, content TEXT, publication_settings TEXT, company_id TEXT,
                                revision INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
                conn.execute("""INSERT INTO user_drafts VALUES ('old-1', 'u', 'publication', 't', 'c', '{"keywords": ["a"]}',
                                NULL, 4, '2026-01-01', '2026-01-01')""")
            conn.close()
            init_db(db_path, seed=False).close()
            conn = sqlite3.connect(db_path)
            cols = [r[1] for r in conn.execute("PRAGMA table_info(user_drafts)")]
            row = conn.execute("SELECT id, publication_settings, revision FROM user_drafts").fetchone()
            conn.close()
            self.assertIn("content_delta", cols)
            self.assertIn("content_html", cols)
            self.assertEqual(row, ("old-1", '{"keywords": ["a"]}', 4))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


@unittest.skipUnless(PLAYWRIGHT_AVAILABLE and os.environ.get("RUN_BROWSER_SMOKE") == "1",
                     "Browser smoke test enabled via RUN_BROWSER_SMOKE=1 and Playwright")
class TestIssue252Browser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        start_server(cls, "issue252_browser")
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
        stop_server(cls)

    def session(self, login):
        user_id = add_user(self.db_path, login)
        token = secrets.token_hex(32)
        now = datetime.datetime.now(datetime.timezone.utc)
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute("""INSERT INTO sessions (token, user_id, user_name, user_role, created_at, expires_at, is_revoked)
                            VALUES (?, ?, ?, 'user', ?, ?, 0)""",
                         (token, user_id, login, now.isoformat(), (now + datetime.timedelta(days=1)).isoformat()))
        conn.close()
        return user_id, token

    def context(self, token=None):
        ctx = self.browser.new_context(viewport={"width": 1280, "height": 900})
        if token:
            ctx.add_cookies([{"name": "sc_session", "value": token, "url": self.base}])
        return ctx

    def server_drafts(self, user_id):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in conn.execute("SELECT * FROM user_drafts WHERE user_id = ?", (user_id,))]
        finally:
            conn.close()

    def wait_account_saved(self, page):
        page.wait_for_function(
            "() => document.getElementById('save-status-text').textContent === 'Сохранено в аккаунте'", timeout=10000)

    def test_publication_draft_reaches_account_and_opens_in_a_clean_browser(self):
        user_id, token = self.session("pub_writer")
        ctx = self.context(token)
        try:
            page = ctx.new_page()
            page.goto(self.base + "/editor.html", wait_until="networkidle")
            page.locator("#article-title").fill("Черновик на другом устройстве")
            page.locator("#editor .ql-editor").click()
            page.keyboard.press("Control+B")
            page.keyboard.type("Жирное начало")
            page.keyboard.press("Control+B")
            page.keyboard.type(" и обычный текст статьи.")
            self.wait_account_saved(page)
            sent = page.evaluate("window.EditorApp.Publication.getSettings()")
        finally:
            ctx.close()

        rows = self.server_drafts(user_id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["material_type"], "publication")
        self.assertEqual(json.loads(rows[0]["publication_settings"]), json.loads(json.dumps(sent)))
        self.assertIn("bold", rows[0]["content_delta"])

        ctx = self.context(token)  # clean browser storage, same account
        try:
            page = ctx.new_page()
            page.goto(self.base + "/editor.html", wait_until="networkidle")
            self.assertEqual(page.evaluate("localStorage.getItem('ag_active_draft_id')"), None)
            page.locator("#btn-drafts-modal").click()
            page.locator("#drafts-modal .draft-item .btn-load").first.click()
            page.wait_for_function("() => document.getElementById('article-title').value !== ''", timeout=5000)
            self.assertEqual(page.locator("#article-title").input_value(), "Черновик на другом устройстве")
            self.assertEqual(page.locator("#editor .ql-editor strong").first.inner_text(), "Жирное начало")
            self.assertIn("обычный текст статьи", page.locator("#editor .ql-editor").inner_text())
            restored = page.evaluate("window.EditorApp.Publication.getSettings()")
            self.assertEqual(restored, sent)
        finally:
            ctx.close()

    def test_question_draft_reaches_account_and_opens_in_a_clean_browser(self):
        user_id, token = self.session("question_writer")
        ctx = self.context(token)
        try:
            page = ctx.new_page()
            page.goto(self.base + "/question-editor.html", wait_until="networkidle")
            page.locator("#questionTitleInput").fill("Как безопасно обновить прокси UUPS?")
            tags = page.locator("#questionTagInput")
            for tag in ("uups", "proxy"):
                tags.fill(tag)
                tags.press("Enter")
            page.locator("#questionEditor .ql-editor").click()
            page.keyboard.type("Подробности вопроса для проверки сохранения в аккаунте.")
            self.wait_account_saved(page)
        finally:
            ctx.close()

        rows = self.server_drafts(user_id)
        self.assertEqual([r["material_type"] for r in rows], ["question"])
        self.assertEqual(json.loads(rows[0]["publication_settings"])["keywords"], ["uups", "proxy"])

        ctx = self.context(token)
        try:
            page = ctx.new_page()
            page.goto(self.base + "/question-editor.html", wait_until="networkidle")
            page.wait_for_function("() => document.getElementById('questionTitleInput').value !== ''", timeout=5000)
            self.assertEqual(page.locator("#questionTitleInput").input_value(), "Как безопасно обновить прокси UUPS?")
            self.assertIn("Подробности вопроса", page.locator("#questionEditor .ql-editor").inner_text())
            self.assertEqual(page.evaluate("window.QuestionEditor.getTagsArray()"), ["uups", "proxy"])
        finally:
            ctx.close()

    def test_failed_sync_is_not_shown_as_saved_to_account(self):
        user_id, token = self.session("offline_writer")
        ctx = self.context(token)
        try:
            page = ctx.new_page()
            page.goto(self.base + "/editor.html", wait_until="networkidle")
            page.route("**/api/drafts**", lambda route: route.fulfill(status=500, body="{}"))
            page.locator("#article-title").fill("Сервер недоступен")
            page.wait_for_function("""() => {
              const t = document.getElementById('save-status-text').textContent;
              return t !== 'Есть изменения' && t !== 'Сохранение...';
            }""", timeout=10000)
            status = page.locator("#save-status-text").inner_text()
            local = page.evaluate("window.EditorApp.Drafts.getAllDrafts().then(l => l.map(d => d.title))")
        finally:
            ctx.close()
        self.assertNotEqual(status, "Сохранено в аккаунте")
        self.assertIn("Сервер недоступен", local, "the draft is kept on the device")
        self.assertEqual(self.server_drafts(user_id), [])

        ctx = self.context(token)
        try:
            page = ctx.new_page()
            page.goto(self.base + "/editor.html", wait_until="networkidle")
            ctx.set_offline(True)
            page.locator("#article-title").fill("Без сети")
            page.wait_for_timeout(2500)
            local = page.evaluate("window.EditorApp.Drafts.getAllDrafts().then(l => l.map(d => d.title))")
            status = page.locator("#save-status-text").inner_text()
        finally:
            ctx.close()
        self.assertIn("Без сети", local)
        self.assertNotEqual(status, "Сохранено в аккаунте")

    def test_stale_tab_gets_conflict_and_keeps_its_text(self):
        """Issue #256: two independent browser contexts of one account edit the same draft."""
        user_id, token = self.session("two_tab_writer")
        tab_a, tab_b = self.context(token), self.context(token)
        try:
            page_a = tab_a.new_page()
            page_a.goto(self.base + "/editor.html", wait_until="networkidle")
            page_a.locator("#article-title").fill("Общий черновик")
            self.wait_account_saved(page_a)

            page_b = tab_b.new_page()
            page_b.on("dialog", lambda d: d.dismiss())  # "save as a copy?" -> no
            page_b.goto(self.base + "/editor.html", wait_until="networkidle")
            page_b.locator("#btn-drafts-modal").click()
            page_b.locator("#drafts-modal .draft-item .btn-load").first.click()
            page_b.wait_for_function("() => document.getElementById('article-title').value === 'Общий черновик'", timeout=5000)

            page_a.locator("#article-title").fill("Версия вкладки A")
            page_a.wait_for_function("() => document.getElementById('save-status-text').textContent === 'Сохранено в аккаунте'"
                                     " && document.getElementById('article-title').value === 'Версия вкладки A'", timeout=10000)
            page_a.wait_for_timeout(500)
            server_a = self.server_drafts(user_id)[0]
            self.assertEqual(server_a["title"], "Версия вкладки A")

            page_b.locator("#article-title").fill("Устаревшая версия вкладки B")
            page_b.wait_for_function("() => document.getElementById('save-status-text').textContent === 'Конфликт синхронизации'",
                                     timeout=10000)
            local_b = page_b.evaluate("""() => new Promise(resolve => {
              const dm = window.EditorApp.Drafts;
              const req = dm.db.transaction(['drafts'], 'readonly').objectStore('drafts').get(dm.currentDraftId);
              req.onsuccess = () => resolve(req.result ? req.result.title : null);
            })""")
            self.assertEqual(page_b.locator("#article-title").input_value(), "Устаревшая версия вкладки B")
        finally:
            tab_a.close()
            tab_b.close()
        self.assertEqual(local_b, "Устаревшая версия вкладки B", "tab B keeps its text on the device")
        rows = self.server_drafts(user_id)
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["title"], rows[0]["revision"]), ("Версия вкладки A", server_a["revision"]),
                         "the server keeps tab A's version")

    def test_guest_draft_stays_on_the_device(self):
        ctx = self.context()
        try:
            page = ctx.new_page()
            page.goto(self.base + "/editor.html", wait_until="networkidle")
            requests = []
            page.on("request", lambda r: requests.append(r.url) if "/api/drafts" in r.url and r.method != "GET" else None)
            page.locator("#article-title").fill("Гостевой черновик")
            page.wait_for_timeout(2500)
            local = page.evaluate("window.EditorApp.Drafts.getAllDrafts().then(l => l.map(d => d.title))")
        finally:
            ctx.close()
        self.assertIn("Гостевой черновик", local)
        self.assertEqual(requests, [], "guests do not send drafts to the server")


if __name__ == "__main__":
    unittest.main()
