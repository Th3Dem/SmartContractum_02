#!/usr/bin/env python3
"""
tests/test_issue13_sc014_draft_revision_idempotency.py

Regression test suite for Issue #13 (SC-014):
"Привязать идемпотентность отправки публикации к ревизии черновика"
GitHub Issue: #13 (https://github.com/Th3Dem/SmartContractum_02/issues/13)

Acceptance Criteria:
1. idempotencyKey строго привязан к ID черновика и его неизмененной ревизии:
   'pub_' + draftId + '_rev_' + revision.
2. При повторной отправке без изменения черновика генерируется идентичный idempotencyKey.
3. При модификации черновика (сохранение правок) ревизия инкрементируется, и генерируется новый idempotencyKey.
4. Серверный API: повторный POST /api/moderation/submit с существующим idempotencyKey возвращает HTTP 200
   с isDuplicate: True и данными существующей заявки, без создания второй записи в moderation_submissions.
5. Серверный API: отправка с новым idempotencyKey успешно сохраняет новую заявку.
6. Конкурентная отправка с одинаковым idempotencyKey не приводит к IntegrityError или дубликатам.
7. Синтаксическая валидность JS и отсутствие регрессий во всех тестах проекта.
"""

import concurrent.futures
import json
import os
import re
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.error

import server
from server import create_server, init_db, get_db_connection

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class SimulatedDraftsManager:
    """
    Python mirror of DraftsManager revision and fingerprinting behavior
    for verification of the state-machine logic.
    """
    def __init__(self, initial_draft_id="draft_test_1"):
        self.currentDraftId = initial_draft_id
        self.currentRevision = 1
        self.lastSavedFingerprint = None
        self.currentDraft = None
        self.isDirty = False
        self.storage = {}

    def _computeFingerprint(self, title, delta, html, publicationSettings):
        filtered_settings = None
        if publicationSettings and isinstance(publicationSettings, dict):
            filtered_settings = {}
            for k in sorted(publicationSettings.keys()):
                if k != "status":
                    filtered_settings[k] = publicationSettings[k]
        return json.dumps({
            "title": (title or "").strip(),
            "delta": delta,
            "html": (html or "").strip(),
            "settings": filtered_settings
        }, sort_keys=True)

    def saveCurrent(self, title="Без названия", delta=None, html="", publicationSettings=None, isAuto=False, isManual=False):
        current_fingerprint = self._computeFingerprint(title, delta, html, publicationSettings)

        new_revision = self.currentRevision or 1
        if self.lastSavedFingerprint is None:
            new_revision = self.currentRevision if (self.currentRevision and self.currentRevision > 0) else 1
        elif self.lastSavedFingerprint != current_fingerprint or self.isDirty:
            new_revision = (self.currentRevision or 1) + 1

        draft = {
            "id": self.currentDraftId,
            "title": title or "Без названия",
            "revision": new_revision,
            "delta": delta,
            "html": html,
            "publicationSettings": publicationSettings,
            "updatedAt": int(time.time() * 1000)
        }

        self.storage[self.currentDraftId] = draft
        self.currentRevision = new_revision
        self.lastSavedFingerprint = current_fingerprint
        self.currentDraft = draft
        self.isDirty = False
        return draft

    def loadDraft(self, draft):
        self.currentDraftId = draft["id"]
        self.currentRevision = draft.get("revision", 1) or 1
        self.currentDraft = draft
        self.lastSavedFingerprint = self._computeFingerprint(
            draft.get("title", ""),
            draft.get("delta"),
            draft.get("html", ""),
            draft.get("publicationSettings")
        )
        self.isDirty = False

    def createNewDraft(self, new_id=None):
        self.currentDraftId = new_id or f"draft_{int(time.time() * 1000)}"
        self.currentRevision = 1
        self.lastSavedFingerprint = None
        self.currentDraft = None
        self.isDirty = False

    def getSubmissionIdempotencyKey(self):
        rev = self.currentRevision or (self.currentDraft and (self.currentDraft.get("revision") or self.currentDraft.get("updatedAt"))) or 1
        return f"pub_{self.currentDraftId}_rev_{rev}"


class TestIssue13SC014DraftRevisionIdempotency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue13_sc014.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path)
        conn.close()

        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR)
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.1)

        drafts_js_path = os.path.join(FRONTEND_DIR, "js", "drafts.js")
        with open(drafts_js_path, "r", encoding="utf-8") as f:
            cls.drafts_js = f.read()

        pub_js_path = os.path.join(FRONTEND_DIR, "js", "publication.js")
        with open(pub_js_path, "r", encoding="utf-8") as f:
            cls.pub_js = f.read()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.httpd.shutdown()
            cls.httpd.server_close()
        except Exception:
            pass

    def _post_json(self, path, payload, cookie=None):
        url = f"{self.base_url}{path}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        if cookie:
            req.add_header("Cookie", cookie)
        try:
            with urllib.request.urlopen(req) as resp:
                body = resp.read().decode("utf-8")
                return resp.status, json.loads(body)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            try:
                return e.code, json.loads(body)
            except Exception:
                return e.code, {"error": body}

    def _login(self, user_id: str, name: str = "Тестовый Автор", role: str = "user") -> str:
        url = f"{self.base_url}/api/auth/login"
        body = json.dumps({"userId": user_id, "name": name, "role": role}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST"
        )
        with urllib.request.urlopen(req) as resp:
            return resp.headers.get("Set-Cookie")

    def test_01_http_serves_js_files_with_200_ok(self):
        """Verify server serves js/drafts.js and js/publication.js with 200 OK."""
        for filename in ["js/drafts.js", "js/publication.js"]:
            req = urllib.request.Request(f"{self.base_url}/{filename}")
            with urllib.request.urlopen(req) as resp:
                self.assertEqual(resp.status, 200)
                content = resp.read().decode("utf-8")
                self.assertTrue(len(content) > 1000)

    def test_02_idempotency_key_stability_without_draft_modification(self):
        """
        Verify that repeated calls to getSubmissionIdempotencyKey() return the exact
        same key when the draft has not been modified.
        """
        dm = SimulatedDraftsManager(initial_draft_id="draft_alpha_1")
        # Initial state before first save
        key1 = dm.getSubmissionIdempotencyKey()
        self.assertEqual(key1, "pub_draft_alpha_1_rev_1")

        # Calling again returns same key
        key2 = dm.getSubmissionIdempotencyKey()
        self.assertEqual(key1, key2)

        # First save with initial content
        dm.saveCurrent(
            title="Заголовок первой статьи",
            html="<p>Текст статьи</p>",
            publicationSettings={"audience": "all", "topics": ["development"]}
        )
        self.assertEqual(dm.currentRevision, 1)
        key_after_save1 = dm.getSubmissionIdempotencyKey()
        self.assertEqual(key_after_save1, "pub_draft_alpha_1_rev_1")

        # Repeated calls without changes
        key3 = dm.getSubmissionIdempotencyKey()
        self.assertEqual(key3, "pub_draft_alpha_1_rev_1")

        # Saving unchanged draft (e.g. status transition to in_moderation) does NOT bump revision
        dm.saveCurrent(
            title="Заголовок первой статьи",
            html="<p>Текст статьи</p>",
            publicationSettings={"audience": "all", "topics": ["development"], "status": "in_moderation"}
        )
        self.assertEqual(dm.currentRevision, 1, "Saving unchanged content with only status updated must not bump revision")
        self.assertEqual(dm.getSubmissionIdempotencyKey(), "pub_draft_alpha_1_rev_1")

    def test_03_draft_modification_increments_revision_and_updates_key(self):
        """
        Verify that modifying draft content (title, html, or publication settings)
        increments the revision and produces a new deterministic idempotency key.
        """
        dm = SimulatedDraftsManager(initial_draft_id="draft_beta_2")
        dm.saveCurrent(
            title="Исходный заголовок",
            html="<p>Исходный контент</p>",
            publicationSettings={"audience": "all", "topics": ["design"]}
        )
        self.assertEqual(dm.currentRevision, 1)
        self.assertEqual(dm.getSubmissionIdempotencyKey(), "pub_draft_beta_2_rev_1")

        # Modification 1: user edits title
        dm.saveCurrent(
            title="Обновленный заголовок",
            html="<p>Исходный контент</p>",
            publicationSettings={"audience": "all", "topics": ["design"]}
        )
        self.assertEqual(dm.currentRevision, 2, "Title edit must bump revision to 2")
        self.assertEqual(dm.getSubmissionIdempotencyKey(), "pub_draft_beta_2_rev_2")

        # Stable on repeat
        self.assertEqual(dm.getSubmissionIdempotencyKey(), "pub_draft_beta_2_rev_2")

        # Modification 2: user edits body HTML
        dm.saveCurrent(
            title="Обновленный заголовок",
            html="<p>Добавлен новый абзац текста с деталями</p>",
            publicationSettings={"audience": "all", "topics": ["design"]}
        )
        self.assertEqual(dm.currentRevision, 3, "HTML body edit must bump revision to 3")
        self.assertEqual(dm.getSubmissionIdempotencyKey(), "pub_draft_beta_2_rev_3")

        # Modification 3: user updates tags / hubs in publicationSettings
        dm.saveCurrent(
            title="Обновленный заголовок",
            html="<p>Добавлен новый абзац текста с деталями</p>",
            publicationSettings={"audience": "all", "topics": ["design", "management"], "tags": ["ux"]}
        )
        self.assertEqual(dm.currentRevision, 4, "Publication settings edit must bump revision to 4")
        self.assertEqual(dm.getSubmissionIdempotencyKey(), "pub_draft_beta_2_rev_4")

    def test_04_server_api_idempotency_returns_duplicate_without_extra_row(self):
        """
        Server API check: repeated POST /api/moderation/submit with identical idempotencyKey
        returns HTTP 200 with isDuplicate: True and existing submission data.
        The row count in moderation_submissions must remain 1.
        """
        cookie = self._login("author_idempotent_user", "Идемпотентный Автор")
        draft_id = "draft_idem_001"
        idempotency_key = "pub_draft_idem_001_rev_1"

        payload = {
            "draftId": draft_id,
            "title": "Тестовая статья для проверки серверной идемпотентности",
            "html": "<p>Полный текст тестовой статьи для проверки очереди модерации без дублирования.</p>",
            "publicationSettings": {
                "targetAudience": "qa",
                "topics": ["qa"],
                "keywords": ["idempotency", "test"],
                "description": "Проверка защиты от повторных кликов и дубликатов в очереди модерации Antigravity Writer.",
                "format": "case",
                "complexity": "easy"
            },
            "idempotencyKey": idempotency_key
        }

        # First submission
        status1, data1 = self._post_json("/api/moderation/submit", payload, cookie=cookie)
        self.assertEqual(status1, 200)
        self.assertTrue(data1.get("success"))
        self.assertFalse(data1.get("isDuplicate", False))
        submission_id_1 = data1.get("submissionId")
        self.assertTrue(submission_id_1)

        # Check DB row count = 1
        conn = get_db_connection(self.db_path)
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) AS cnt FROM moderation_submissions WHERE draft_id = ?", (draft_id,))
            self.assertEqual(cur.fetchone()["cnt"], 1)
        conn.close()

        # Second submission with the exact same idempotencyKey (retry scenario)
        status2, data2 = self._post_json("/api/moderation/submit", payload, cookie=cookie)
        self.assertEqual(status2, 200)
        self.assertTrue(data2.get("success"))
        self.assertTrue(data2.get("isDuplicate"), "Second submission must return isDuplicate: True")
        self.assertEqual(data2.get("submissionId"), submission_id_1, "Must return existing submissionId")

        # Check DB row count is STILL 1
        conn = get_db_connection(self.db_path)
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) AS cnt FROM moderation_submissions WHERE draft_id = ?", (draft_id,))
            self.assertEqual(cur.fetchone()["cnt"], 1, "Database row count must not increase on duplicate submission")
        conn.close()

    def test_05_server_api_new_revision_submission_creates_new_record(self):
        """
        Server API check: sending a submission with a new idempotencyKey (e.g. new revision)
        creates a new submission record in moderation_submissions.
        """
        cookie = self._login("author_revision_user", "Автор Ревизий")
        draft_id = "draft_rev_002"

        payload_rev1 = {
            "draftId": draft_id,
            "title": "Первая ревизия статьи",
            "html": "<p>Контент первой ревизии статьи.</p>",
            "publicationSettings": {
                "targetAudience": "qa",
                "topics": ["qa"],
                "keywords": ["revision", "first"],
                "description": "Описание статьи первой ревизии для модерации в Antigravity.",
                "format": "case",
                "complexity": "easy"
            },
            "idempotencyKey": "pub_draft_rev_002_rev_1"
        }

        # Submit revision 1
        status1, data1 = self._post_json("/api/moderation/submit", payload_rev1, cookie=cookie)
        self.assertEqual(status1, 200)
        self.assertFalse(data1.get("isDuplicate", False))
        sub_id_1 = data1.get("submissionId")

        # Submit revision 2 with modified content and new revision key
        payload_rev2 = dict(payload_rev1)
        payload_rev2["title"] = "Вторая ревизия статьи с дополнениями"
        payload_rev2["html"] = "<p>Контент первой ревизии статьи, расширенный дополнительными сведениями.</p>"
        payload_rev2["idempotencyKey"] = "pub_draft_rev_002_rev_2"

        status2, data2 = self._post_json("/api/moderation/submit", payload_rev2, cookie=cookie)
        self.assertEqual(status2, 200)
        self.assertFalse(data2.get("isDuplicate", False))
        sub_id_2 = data2.get("submissionId")
        self.assertNotEqual(sub_id_1, sub_id_2, "New revision must produce a distinct submissionId")

        # Verify DB has 2 records for this draft_id
        conn = get_db_connection(self.db_path)
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT id, idempotency_key, title FROM moderation_submissions WHERE draft_id = ? ORDER BY created_at ASC", (draft_id,))
            rows = cur.fetchall()
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["idempotency_key"], "pub_draft_rev_002_rev_1")
            self.assertEqual(rows[1]["idempotency_key"], "pub_draft_rev_002_rev_2")
        conn.close()

    def test_06_server_concurrency_race_condition_handled_safely(self):
        """
        Verify that concurrent POST requests with the same idempotencyKey do not
        cause 500 errors, crash, or create duplicate entries.
        """
        cookie = self._login("author_concurrent_user", "Конкурентный Автор")
        draft_id = "draft_concurrent_003"
        idempotency_key = "pub_draft_concurrent_003_rev_1"

        payload = {
            "draftId": draft_id,
            "title": "Статья для проверки конкурентных запросов",
            "html": "<p>Параллельная отправка публикации с одинаковым ключом идемпотентности.</p>",
            "publicationSettings": {
                "targetAudience": "qa",
                "topics": ["qa"],
                "keywords": ["concurrency", "test"],
                "description": "Описание статьи для проверки параллельной отправки и гонок в Antigravity.",
                "format": "case",
                "complexity": "easy"
            },
            "idempotencyKey": idempotency_key
        }

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(self._post_json, "/api/moderation/submit", payload, cookie)
                for _ in range(5)
            ]
            for f in concurrent.futures.as_completed(futures):
                results.append(f.result())

        for status, data in results:
            self.assertEqual(status, 200, f"All requests must succeed with 200 OK: {data}")
            self.assertTrue(data.get("success"))

        # Exactly 1 request should have isDuplicate=False, remaining 4 should have isDuplicate=True
        duplicates = [data.get("isDuplicate", False) for _, data in results]
        self.assertEqual(duplicates.count(False), 1, "Exactly one request must be the original creation")
        self.assertEqual(duplicates.count(True), 4, "All duplicate requests must return isDuplicate: True")

        # Total rows in DB must be exactly 1
        conn = get_db_connection(self.db_path)
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) AS cnt FROM moderation_submissions WHERE draft_id = ?", (draft_id,))
            self.assertEqual(cur.fetchone()["cnt"], 1)
        conn.close()

    def test_07_static_analysis_drafts_js_and_publication_js(self):
        """
        Verify structural implementation in frontend/public/js/drafts.js and publication.js:
        - getSubmissionIdempotencyKey() exists and formats 'pub_' + draftId + '_rev_'
        - revision field is stored in draft object
        - this.currentRevision is initialized and incremented upon modification
        - publication.js uses getSubmissionIdempotencyKey() and handles isDuplicate
        """
        # drafts.js checks
        self.assertIn("getSubmissionIdempotencyKey()", self.drafts_js)
        self.assertRegex(
            self.drafts_js,
            r"getSubmissionIdempotencyKey\s*\(\s*\)\s*\{[^}]+'pub_'\s*\+\s*this\.currentDraftId\s*\+\s*'_rev_'",
            "getSubmissionIdempotencyKey must construct deterministic key from currentDraftId and revision"
        )
        self.assertIn("revision: newRevision", self.drafts_js, "draft object must contain revision field")
        self.assertIn("this.currentRevision = 1;", self.drafts_js, "this.currentRevision must be initialized to 1")
        self.assertIn("_computeFingerprint", self.drafts_js, "_computeFingerprint method must exist")

        # publication.js checks
        self.assertIn("getSubmissionIdempotencyKey", self.pub_js, "publication.js must reference getSubmissionIdempotencyKey")
        self.assertRegex(
            self.pub_js,
            r"draftsManager\.getSubmissionIdempotencyKey\s*\(\s*\)",
            "publication.js must call draftsManager.getSubmissionIdempotencyKey()"
        )
        self.assertIn("isDuplicate", self.pub_js, "publication.js must check isDuplicate")
        self.assertIn(
            "Статья уже находится на модерации",
            self.pub_js,
            "publication.js must notify user when article is already in moderation"
        )

    def test_08_js_structural_syntax_integrity(self):
        """Verify balanced braces, parentheses, brackets, and IIFE structure in JS files."""
        for filename, content in [("drafts.js", self.drafts_js), ("publication.js", self.pub_js)]:
            open_braces = content.count("{")
            close_braces = content.count("}")
            self.assertEqual(open_braces, close_braces, f"Mismatched braces in {filename}: {open_braces} vs {close_braces}")

            open_parens = content.count("(")
            close_parens = content.count(")")
            self.assertEqual(open_parens, close_parens, f"Mismatched parentheses in {filename}: {open_parens} vs {close_parens}")

            open_brackets = content.count("[")
            close_brackets = content.count("]")
            self.assertEqual(open_brackets, close_brackets, f"Mismatched brackets in {filename}: {open_brackets} vs {close_brackets}")

            self.assertIn("(function (window) {", content, f"{filename} must be wrapped in IIFE")
            self.assertTrue(content.strip().endswith("})(window);"), f"{filename} must end with IIFE closure")
            self.assertNotIn("debugger;", content, f"{filename} must not contain debugger statements")


if __name__ == "__main__":
    unittest.main()
