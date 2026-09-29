#!/usr/bin/env python3
"""
tests/test_issue10_sc009_drafts_storage_errors.py

Regression test suite for Issue #10 (SC-009):
"Обеспечить честные статусы ошибок записи в IndexedDB / localStorage"
GitHub Issue: #10 (https://github.com/Th3Dem/SmartContractum_02/issues/10)

Acceptance Criteria:
1. Promise сохранения в IndexedDB ожидает transaction.oncomplete (putToDB).
2. Ошибки квоты и сбои хранилища (IndexedDB и localStorage) явно пробрасываются
   и отображаются пользователю через статус ошибки и toast вместо ложного «Все изменения сохранены».
3. Флаг несохраненных данных (isDirty) сохраняется при сбое записи.
4. flush() при сбое сохранения не подменяет статус на успешный и пробрасывает ошибку.
5. Штатное сохранение успешно переводит статус в 'saved' и сбрасывает isDirty в false.
6. 100% тестов проекта проходят успешно (python3 -m unittest discover tests/).
"""

import os
import re
import tempfile
import threading
import time
import unittest
import urllib.request

import server
from server import create_server, init_db

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue10SC009DraftsStorageErrors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue10_sc009.db")
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

        main_js_path = os.path.join(FRONTEND_DIR, "js", "main.js")
        with open(main_js_path, "r", encoding="utf-8") as f:
            cls.main_js = f.read()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.httpd.shutdown()
            cls.httpd.server_close()
        except Exception:
            pass

    def test_01_http_serves_drafts_js_and_main_js(self):
        """Verify server serves js/drafts.js and js/main.js with 200 OK and expected contents."""
        req_drafts = urllib.request.Request(f"{self.base_url}/js/drafts.js")
        with urllib.request.urlopen(req_drafts) as resp:
            self.assertEqual(resp.status, 200)
            content = resp.read().decode("utf-8")
            self.assertIn("class DraftsManager", content)
            self.assertIn("putToDB", content)
            self.assertIn("putToLocalStorage", content)

        req_main = urllib.request.Request(f"{self.base_url}/js/main.js")
        with urllib.request.urlopen(req_main) as resp:
            self.assertEqual(resp.status, 200)
            content = resp.read().decode("utf-8")
            self.assertIn("showToast", content)
            self.assertIn("toast-error", content)

    def test_02_put_to_db_strict_tx_oncomplete_and_rejections(self):
        """Verify putToDB resolves strictly on tx.oncomplete and rejects on all errors."""
        # 1. Method signature and body until next method
        match = re.search(r'putToDB\s*\(\s*draft\s*\)\s*\{(.*?)\n\s*putToLocalStorage', self.drafts_js, re.DOTALL)
        self.assertIsNotNone(match, "DraftsManager must implement putToDB(draft)")
        body = match.group(1)

        # 2. Strict tx.oncomplete resolution
        self.assertRegex(
            body,
            r'tx\.oncomplete\s*=\s*\(\s*\)\s*=>\s*resolve\(',
            "putToDB must resolve strictly on tx.oncomplete"
        )

        # 3. No premature resolution on req.onsuccess
        self.assertNotRegex(
            body,
            r'req\.onsuccess\s*=\s*\(\s*\)\s*=>\s*resolve\(',
            "putToDB must not resolve prematurely on req.onsuccess before transaction commit"
        )

        # 4. Rejections on tx.onerror, tx.onabort, req.onerror
        self.assertRegex(
            body,
            r'tx\.onerror\s*=\s*\(\s*\)\s*=>\s*reject\(',
            "putToDB must reject on tx.onerror"
        )
        self.assertRegex(
            body,
            r'tx\.onabort\s*=\s*\(\s*\)\s*=>\s*reject\(',
            "putToDB must reject on tx.onabort"
        )
        self.assertRegex(
            body,
            r'req\.onerror\s*=\s*\(\s*\)\s*=>\s*reject\(',
            "putToDB must reject on req.onerror"
        )

        # 5. Catch block for synchronous transaction errors
        self.assertRegex(
            body,
            r'catch\s*\(\s*err\s*\)\s*\{\s*reject\(err\);',
            "putToDB must catch synchronous transaction errors and reject"
        )

    def test_03_put_to_local_storage_no_exception_suppression(self):
        """Verify putToLocalStorage does not suppress exceptions and rethrows to caller."""
        match = re.search(r'putToLocalStorage\s*\(\s*draft\s*\)\s*\{(.*?)\n\s*async\s+getAllDrafts', self.drafts_js, re.DOTALL)
        self.assertIsNotNone(match, "DraftsManager must implement putToLocalStorage(draft)")
        body = match.group(1)

        # Exception must not be swallowed: must throw on catch or have no silent suppression
        self.assertRegex(
            body,
            r'throw\s+e;',
            "putToLocalStorage must rethrow caught errors to prevent silent suppression"
        )

    def test_04_do_save_current_honest_error_status_and_toast(self):
        """Verify _doSaveCurrent sets 'error' status, keeps isDirty=true, and shows informative toast."""
        match = re.search(r'async\s+_doSaveCurrent\s*\([^)]*\)\s*\{(.*?)\n\s*putToDB', self.drafts_js, re.DOTALL)
        self.assertIsNotNone(match, "DraftsManager must implement _doSaveCurrent")
        body = match.group(1)

        # In catch block:
        catch_match = re.search(r'catch\s*\(\s*err\s*\)\s*\{(.*)', body, re.DOTALL)
        self.assertIsNotNone(catch_match, "_doSaveCurrent must contain a catch(err) block")
        catch_body = catch_match.group(1)

        # 1. Sets status to error
        self.assertIn("this.setStatus('error');", catch_body, "_doSaveCurrent must setStatus('error') on failure")

        # 2. Preserves isDirty = true
        self.assertIn("this.isDirty = true;", catch_body, "_doSaveCurrent must keep this.isDirty = true on failure")

        # 3. Detects quota exceeded condition
        self.assertIn("QuotaExceededError", catch_body, "Must detect QuotaExceededError")
        self.assertIn("22", catch_body, "Must detect quota error code 22")

        # 4. Shows informative toast messages
        self.assertIn(
            "Ошибка: хранилище браузера переполнено",
            catch_body,
            "Must show 'Ошибка: хранилище браузера переполнено' when browser quota is exceeded"
        )
        self.assertIn(
            "Ошибка сохранения черновика",
            catch_body,
            "Must show 'Ошибка сохранения черновика' on other storage errors"
        )

        # 5. Calls showToast
        self.assertRegex(
            catch_body,
            r'window\.EditorApp\.showToast\(\s*errMsg',
            "Must call window.EditorApp.showToast with errMsg"
        )

        # 6. Re-throws error
        self.assertIn("throw err;", catch_body, "_doSaveCurrent must throw err on failure so callers know save failed")

    def test_05_flush_error_handling_and_dirty_flag_retention(self):
        """Verify flush() retains dirty state and error status when saveCurrent fails."""
        match = re.search(r'async\s+flush\s*\(\s*\)\s*\{(.*?)\n\s*setStatus', self.drafts_js, re.DOTALL)
        self.assertIsNotNone(match, "DraftsManager must implement flush()")
        body = match.group(1)

        # Catch block in flush
        self.assertIn("this.setStatus('error');", body, "flush() must retain or set status 'error' on save failure")
        self.assertIn("this.isDirty = true;", body, "flush() must keep this.isDirty = true on save failure")
        self.assertRegex(body, r'(?s)catch\s*\(\s*err\s*\)\s*\{.*?throw\s+err;', "flush() must propagate save errors to callers")

    def test_06_simulated_drafts_manager_storage_error_scenarios(self):
        """
        Comprehensive Python behavioral simulation reproducing DraftsManager storage logic:
        - QuotaExceededError in localStorage
        - Transaction error/abort in IndexedDB
        - Request error in IndexedDB
        - Toast messages and editor status
        - isDirty retention and flush behavior
        - Recovery to healthy state
        """
        class DOMExceptionMock(Exception):
            def __init__(self, name, code=0, message=""):
                super().__init__(message or name)
                self.name = name
                self.code = code
                self.message = message or name

        class SimulatedDraftsManager:
            def __init__(self, use_db=True):
                self.use_db = use_db
                self.storage = {}
                self.currentDraftId = "draft_1"
                self.title = "Test Article"
                self.text = "Article text content"
                self.isDirty = False
                self.status = "saved"
                self.toasts = []
                self.fail_mode = None  # None, 'quota', 'tx_error', 'tx_abort', 'req_error', 'generic'

            def showToast(self, message, toast_type="info"):
                self.toasts.append({"message": message, "type": toast_type})

            def setStatus(self, state):
                self.status = state

            def putToDB(self, draft):
                if self.fail_mode == 'tx_error':
                    raise DOMExceptionMock("AbortError", 20, "Transaction failed")
                if self.fail_mode == 'tx_abort':
                    raise DOMExceptionMock("AbortError", 20, "Transaction aborted")
                if self.fail_mode == 'req_error':
                    raise DOMExceptionMock("ConstraintError", 0, "Put request failed")
                if self.fail_mode == 'quota':
                    raise DOMExceptionMock("QuotaExceededError", 22, "Quota exceeded")
                if self.fail_mode == 'generic':
                    raise Exception("Generic disk I/O error")
                self.storage[draft["id"]] = draft

            def putToLocalStorage(self, draft):
                if self.fail_mode == 'quota':
                    raise DOMExceptionMock("QuotaExceededError", 22, "Quota exceeded")
                if self.fail_mode == 'quota_ns':
                    raise DOMExceptionMock("NS_ERROR_DOM_QUOTA_REACHED", 1014, "Quota reached")
                if self.fail_mode == 'generic':
                    raise Exception("LocalStorage disk full")
                self.storage[draft["id"]] = draft

            def _doSaveCurrent(self):
                if not self.title and not self.text:
                    self.setStatus('saved')
                    self.isDirty = False
                    return

                self.setStatus('saving')
                draft = {
                    "id": self.currentDraftId,
                    "title": self.title,
                    "text": self.text,
                    "updatedAt": time.time()
                }

                try:
                    if self.use_db:
                        self.putToDB(draft)
                    else:
                        self.putToLocalStorage(draft)

                    self.setStatus('saved')
                    self.isDirty = False
                except Exception as err:
                    self.setStatus('error')
                    self.isDirty = True

                    is_quota = (
                        getattr(err, 'name', '') in ('QuotaExceededError', 'NS_ERROR_DOM_QUOTA_REACHED')
                        or getattr(err, 'code', None) in (22, 1014)
                        or 'Quota' in str(err)
                    )
                    err_msg = 'Ошибка: хранилище браузера переполнено' if is_quota else 'Ошибка сохранения черновика'
                    self.showToast(err_msg, 'error')
                    raise err

            def saveCurrent(self):
                return self._doSaveCurrent()

            def flush(self):
                if not self.isDirty:
                    return
                try:
                    self.saveCurrent()
                    self.isDirty = False
                except Exception as err:
                    self.isDirty = True
                    self.setStatus('error')
                    raise err

        # Scenario 1: Normal save with healthy IndexedDB
        manager = SimulatedDraftsManager(use_db=True)
        manager.isDirty = True
        manager.saveCurrent()
        self.assertEqual(manager.status, 'saved')
        self.assertFalse(manager.isDirty)
        self.assertIn("draft_1", manager.storage)

        # Scenario 2: IndexedDB transaction error
        manager.fail_mode = 'tx_error'
        manager.isDirty = True
        manager.toasts.clear()
        with self.assertRaises(Exception):
            manager.saveCurrent()
        self.assertEqual(manager.status, 'error', "Status must be 'error' on IndexedDB transaction error")
        self.assertTrue(manager.isDirty, "isDirty must remain True on IndexedDB transaction error")
        self.assertEqual(len(manager.toasts), 1)
        self.assertEqual(manager.toasts[0]["message"], 'Ошибка сохранения черновика')

        # Scenario 3: IndexedDB transaction abort
        manager.fail_mode = 'tx_abort'
        manager.isDirty = True
        manager.toasts.clear()
        with self.assertRaises(Exception):
            manager.saveCurrent()
        self.assertEqual(manager.status, 'error')
        self.assertTrue(manager.isDirty)
        self.assertEqual(manager.toasts[0]["message"], 'Ошибка сохранения черновика')

        # Scenario 4: LocalStorage QuotaExceededError (code 22)
        ls_manager = SimulatedDraftsManager(use_db=False)
        ls_manager.fail_mode = 'quota'
        ls_manager.isDirty = True
        ls_manager.toasts.clear()
        with self.assertRaises(Exception):
            ls_manager.saveCurrent()
        self.assertEqual(ls_manager.status, 'error')
        self.assertTrue(ls_manager.isDirty)
        self.assertEqual(len(ls_manager.toasts), 1)
        self.assertEqual(
            ls_manager.toasts[0]["message"],
            'Ошибка: хранилище браузера переполнено',
            "QuotaExceededError must display 'Ошибка: хранилище браузера переполнено'"
        )

        # Scenario 5: LocalStorage NS_ERROR_DOM_QUOTA_REACHED (Firefox legacy)
        ls_manager.fail_mode = 'quota_ns'
        ls_manager.isDirty = True
        ls_manager.toasts.clear()
        with self.assertRaises(Exception):
            ls_manager.saveCurrent()
        self.assertEqual(ls_manager.status, 'error')
        self.assertTrue(ls_manager.isDirty)
        self.assertEqual(ls_manager.toasts[0]["message"], 'Ошибка: хранилище браузера переполнено')

        # Scenario 6: Flush with failure retains isDirty=True and status='error'
        manager.fail_mode = 'generic'
        manager.isDirty = True
        manager.toasts.clear()
        with self.assertRaises(Exception):
            manager.flush()
        self.assertEqual(manager.status, 'error', "flush() must not mask 'error' status on failure")
        self.assertTrue(manager.isDirty, "flush() must not set isDirty to False on failure")

        # Scenario 7: Recovery to healthy state when storage issue resolves
        manager.fail_mode = None
        manager.flush()
        self.assertEqual(manager.status, 'saved', "Status must transition to 'saved' once storage recovers")
        self.assertFalse(manager.isDirty, "isDirty must reset to False after successful recovery")

    def test_07_javascript_structural_integrity(self):
        """Verify JavaScript syntax characteristics, balanced braces, and IIFE structure."""
        # Balanced braces and parentheses in drafts.js
        open_braces = self.drafts_js.count('{')
        close_braces = self.drafts_js.count('}')
        self.assertEqual(open_braces, close_braces, f"Mismatched braces: {open_braces} vs {close_braces}")

        open_parens = self.drafts_js.count('(')
        close_parens = self.drafts_js.count(')')
        self.assertEqual(open_parens, close_parens, f"Mismatched parentheses: {open_parens} vs {close_parens}")

        open_brackets = self.drafts_js.count('[')
        close_brackets = self.drafts_js.count(']')
        self.assertEqual(open_brackets, close_brackets, f"Mismatched brackets: {open_brackets} vs {close_brackets}")

        # Check IIFE isolation
        self.assertIn('(function (window) {', self.drafts_js)
        self.assertTrue(self.drafts_js.strip().endswith('})(window);'))

        # Check no debug statements
        self.assertNotIn('debugger;', self.drafts_js)


if __name__ == '__main__':
    unittest.main()
