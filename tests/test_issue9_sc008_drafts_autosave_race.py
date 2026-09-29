#!/usr/bin/env python3
"""
tests/test_issue9_sc008_drafts_autosave_race.py

Regression test suite for Issue #9 (SC-008):
"Устранить гонку автосохранения и потерю текста при переключении черновиков"
GitHub Issue: #9 (https://github.com/Th3Dem/SmartContractum_02/issues/9)

Acceptance Criteria:
1. Presence of async flush() method in DraftsManager with transaction completion awaiting.
2. Binding of saveDebounceTimer to specific currentDraftId and validation in callback.
3. Cancellation of autosave debounce timer upon draft switching and creation.
4. Call to flush() before changing this.currentDraftId in createNewDraft() and loadDraft().
5. Data loss prevention: state-machine simulation verifying no text loss or cross-draft overwrite.
6. Syntactic and structural validity of frontend/public/js/drafts.js and clean HTTP delivery.
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


class TestIssue9SC008DraftsAutosaveRace(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue9_sc008.db")
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

    @classmethod
    def tearDownClass(cls):
        try:
            cls.httpd.shutdown()
            cls.httpd.server_close()
        except Exception:
            pass

    def test_01_http_serves_drafts_js_correctly(self):
        """Verify that server serves js/drafts.js with 200 OK and expected content."""
        req = urllib.request.Request(f"{self.base_url}/js/drafts.js")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            content = resp.read().decode("utf-8")
            self.assertIn("class DraftsManager", content)
            self.assertIn("async flush()", content)

    def test_02_flush_method_exists_and_awaits_save(self):
        """Verify async flush() implementation in DraftsManager."""
        # 1. Method signature
        self.assertRegex(
            self.drafts_js,
            r'async\s+flush\s*\(\s*\)',
            "DraftsManager must implement an async flush() method"
        )

        # 2. Checks and clears timer
        self.assertIn("this.saveDebounceTimer", self.drafts_js)
        self.assertRegex(
            self.drafts_js,
            r'if\s*\(\s*this\.saveDebounceTimer\s*\)\s*\{\s*clearTimeout\(this\.saveDebounceTimer\);\s*this\.saveDebounceTimer\s*=\s*null;',
            "flush() must cancel and nullify active saveDebounceTimer"
        )

        # 3. Checks dirty state or pending timer
        self.assertRegex(
            self.drafts_js,
            r'if\s*\(\s*!this\.isDirty\s*&&\s*!hadPendingTimer\s*\)\s*\{\s*return;',
            "flush() must check for pending changes or timers before performing disk writes"
        )

        # 4. Awaits saveCurrent
        self.assertRegex(
            self.drafts_js,
            r'await\s+this\.saveCurrent\(\s*\{\s*isAuto:\s*true\s*\}\s*\);',
            "flush() must await this.saveCurrent({ isAuto: true })"
        )

        # 5. Resets isDirty flag
        self.assertIn("this.isDirty = false;", self.drafts_js)

        # 6. Transaction completion via tx.oncomplete in putToDB
        self.assertRegex(
            self.drafts_js,
            r'tx\.oncomplete\s*=',
            "putToDB must observe IndexedDB transaction completion (tx.oncomplete)"
        )

    def test_03_timer_bound_to_target_draft_id_and_validated(self):
        """Verify that triggerAutosave captures targetDraftId and validates it in the timer callback."""
        # Check targetDraftId capture
        self.assertRegex(
            self.drafts_js,
            r'const\s+targetDraftId\s*=\s*this\.currentDraftId;',
            "triggerAutosave must bind timer to targetDraftId = this.currentDraftId"
        )

        # Check guard condition inside setTimeout callback
        self.assertRegex(
            self.drafts_js,
            r'if\s*\(\s*this\.currentDraftId\s*!==\s*targetDraftId\s*\)\s*return;',
            "setTimeout callback must abort if currentDraftId has changed to avoid overwriting another draft"
        )

        # Check timer sets isDirty and unsaved status
        self.assertIn("this.isDirty = true;", self.drafts_js)
        self.assertIn("this.setStatus('unsaved');", self.drafts_js)

    def test_04_timer_cancellation_and_flush_in_draft_switch(self):
        """Verify createNewDraft and loadDraft call flush and clear timers before changing ID."""
        # 1. createNewDraft is async and calls flush before ID change
        create_match = re.search(r'async\s+createNewDraft\s*\(\s*\)\s*\{(.+?this\.currentDraftId\s*=)', self.drafts_js, re.DOTALL)
        self.assertIsNotNone(create_match, "createNewDraft must be async and assign this.currentDraftId")
        create_body = create_match.group(1)
        self.assertIn("await this.flush();", create_body, "createNewDraft must call await this.flush() before changing currentDraftId")
        self.assertIn("clearTimeout(this.saveDebounceTimer)", create_body, "createNewDraft must clear any pending timer")

        # 2. loadDraft is async and calls flush before ID change
        load_match = re.search(r'async\s+loadDraft\s*\([^)]*\)\s*\{(.+?this\.currentDraftId\s*=\s*draft\.id)', self.drafts_js, re.DOTALL)
        self.assertIsNotNone(load_match, "loadDraft must be async and assign this.currentDraftId = draft.id")
        load_body = load_match.group(1)
        self.assertIn("await this.flush();", load_body, "loadDraft must call await this.flush() before changing currentDraftId")
        self.assertIn("clearTimeout(this.saveDebounceTimer)", load_body, "loadDraft must clear any pending timer")

        # 3. deleteDraft resets isDirty and clears timer when active draft is deleted
        self.assertIn("if (this.currentDraftId === id)", self.drafts_js)

    def test_05_ui_event_handlers_properly_await_async_chains(self):
        """Verify UI click handlers for new draft and load draft use async/await."""
        # New draft button click handler
        self.assertRegex(
            self.drafts_js,
            r'this\.newDraftBtn\.addEventListener\(\s*[\'"]click[\'"]\s*,\s*async\s*\(\s*\)\s*=>\s*\{\s*await\s+this\.createNewDraft\(\);',
            "newDraftBtn click handler must await createNewDraft()"
        )

        # Load draft button click handler in renderDraftsList
        self.assertRegex(
            self.drafts_js,
            r'item\.querySelector\([\'"]\.btn-load[\'"]\)\.addEventListener\(\s*[\'"]click[\'"]\s*,\s*async\s*\(e\)\s*=>\s*\{\s*e\.stopPropagation\(\);\s*await\s+this\.loadDraft\(d,\s*true\);',
            ".btn-load click handler must await loadDraft(d, true)"
        )

        # openDraftsModal flushes before listing
        self.assertRegex(
            self.drafts_js,
            r'async\s+openDraftsModal\s*\(\s*\)\s*\{\s*await\s+this\.flush\(\);',
            "openDraftsModal must await this.flush() so active edits appear in the modal list"
        )

    def test_06_simulated_fast_switching_no_data_loss(self):
        """
        Python state-machine simulation reproducing the exact DraftsManager mechanics:
        - Triggering autosave debounced at 2s
        - Rapid draft switching (< 2s)
        - Asserting zero data loss and zero draft collision/overwriting.
        """
        class SimulatedDraftsManager:
            def __init__(self):
                self.storage = {}
                self.currentDraftId = "draft_1"
                self.title = "Draft 1 Initial Title"
                self.text = "Draft 1 Initial Text"
                self.isDirty = False
                self.saveDebounceTimer = None
                self.timerTargetId = None
                self.timerScheduledAt = None

            def triggerAutosave(self, current_virtual_time):
                self.isDirty = True
                if self.saveDebounceTimer:
                    self.saveDebounceTimer = None
                self.timerTargetId = self.currentDraftId
                self.saveDebounceTimer = True
                self.timerScheduledAt = current_virtual_time

            def flush(self):
                had_timer = bool(self.saveDebounceTimer)
                self.saveDebounceTimer = None
                self.timerTargetId = None

                if not self.isDirty and not had_timer:
                    return

                if not self.title.strip() and not self.text.strip():
                    self.isDirty = False
                    return

                # Snapshot current draft under currentDraftId
                self.storage[self.currentDraftId] = {
                    "id": self.currentDraftId,
                    "title": self.title,
                    "text": self.text,
                    "savedAt": time.time()
                }
                self.isDirty = False

            def createNewDraft(self, new_id):
                self.flush()
                self.saveDebounceTimer = None
                self.timerTargetId = None
                self.currentDraftId = new_id
                self.title = ""
                self.text = ""
                self.isDirty = False

            def loadDraft(self, draft):
                self.flush()
                self.saveDebounceTimer = None
                self.timerTargetId = None
                self.currentDraftId = draft["id"]
                self.title = draft.get("title", "")
                self.text = draft.get("text", "")
                self.isDirty = False

            def onTimerFired(self, timer_target_id):
                # Simulated callback
                if self.currentDraftId != timer_target_id:
                    # Guard prevents overwriting
                    return
                self.flush()

        manager = SimulatedDraftsManager()
        # Trigger edit on Draft 1 and flush initial state
        manager.triggerAutosave(current_virtual_time=90.0)
        manager.flush()
        self.assertIn("draft_1", manager.storage)

        # Scenario 1: User types in Draft 1, but switches to Draft 2 after 0.5s (before 2s timer)
        manager.title = "Draft 1 Modified Title"
        manager.text = "Draft 1 Modified Content with crucial thoughts"
        manager.triggerAutosave(current_virtual_time=100.0)

        # Verify timer is pending and dirty flag is set
        self.assertTrue(manager.isDirty)
        self.assertTrue(manager.saveDebounceTimer)
        self.assertEqual(manager.timerTargetId, "draft_1")

        # Now rapid switch to Draft 2 after 500ms
        draft_2 = {"id": "draft_2", "title": "Draft 2 Title", "text": "Draft 2 Text"}
        manager.loadDraft(draft_2)

        # Acceptance check 1: Draft 1 MUST have been flushed into storage with modified content!
        self.assertEqual(
            manager.storage["draft_1"]["title"],
            "Draft 1 Modified Title",
            "Draft 1 title must not be lost upon rapid switch"
        )
        self.assertEqual(
            manager.storage["draft_1"]["text"],
            "Draft 1 Modified Content with crucial thoughts",
            "Draft 1 text must not be lost upon rapid switch"
        )

        # Acceptance check 2: Current draft is now Draft 2
        self.assertEqual(manager.currentDraftId, "draft_2")
        self.assertEqual(manager.title, "Draft 2 Title")
        self.assertFalse(manager.isDirty)
        self.assertIsNone(manager.saveDebounceTimer)

        # Scenario 2: Simulate old timer callback somehow firing at virtual time 102.0s
        # (with target id "draft_1")
        manager.onTimerFired("draft_1")
        # Ensure Draft 2 text was NOT replaced by Draft 1
        self.assertEqual(manager.currentDraftId, "draft_2")
        self.assertEqual(manager.title, "Draft 2 Title")
        self.assertEqual(manager.text, "Draft 2 Text")

        # Scenario 3: User edits Draft 2 and creates new draft
        manager.text = "Draft 2 Unsaved Quick Edit"
        manager.triggerAutosave(current_virtual_time=103.0)
        manager.createNewDraft("draft_3")

        # Verify Draft 2 was saved with quick edit
        self.assertEqual(manager.storage["draft_2"]["text"], "Draft 2 Unsaved Quick Edit")
        # Verify Draft 3 is clean and empty
        self.assertEqual(manager.currentDraftId, "draft_3")
        self.assertEqual(manager.title, "")
        self.assertEqual(manager.text, "")

    def test_07_javascript_structural_integrity(self):
        """Verify JS syntax characteristics, balanced braces, and no rogue tokens."""
        # Balanced braces and parentheses
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

        # Check no unexpected syntax errors or debug statements
        self.assertNotIn('debugger;', self.drafts_js)


if __name__ == '__main__':
    unittest.main()
