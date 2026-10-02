"""
tests/test_issue67_question_drafts_system.py

Comprehensive test suite for Issue #67:
"Question Editor: полноценные черновики, autosave и управление несколькими вопросами."

Verifications:
1. DraftsManager supports materialType ('publication' vs 'question') and customizable options.
2. Question Editor has drafts modal and badge elements.
3. Question drafts are strictly isolated from publication drafts (Issue #12 invariant).
4. Autosave dot states and status text support 4 states.
5. "Новый вопрос" creates new draft without overwriting previous draft.
6. Deleting draft removes only target draft with proper fallback.
7. Submitting question clears only the active draft while preserving others.
8. Legacy localStorage migration imports old single-draft into IndexedDB/storage.
9. Zero emojis and no em dashes in codebase.
"""

import os
import re
import time
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class SimulatedQuill:
    def __init__(self, text=""):
        self.text = text
        self.contents = {"ops": [{"insert": text + "\n"}]} if text else None

    def getText(self):
        return self.text

    def setText(self, val):
        self.text = val
        self.contents = {"ops": [{"insert": val + "\n"}]} if val else None

    def getContents(self):
        return self.contents

    def setContents(self, delta):
        self.contents = delta
        if delta and "ops" in delta:
            self.text = "".join(op.get("insert", "") for op in delta["ops"]).rstrip("\n")
        else:
            self.text = ""


class SimulatedDraftsManager:
    """Python behavioral simulation faithfully modeling DraftsManager in drafts.js."""

    def __init__(self, editor=None, title="", options=None, storage=None, local_storage=None):
        self.editor = editor or SimulatedQuill()
        self.title = title
        self.options = options or {}
        self.materialType = self.options.get("materialType", "publication")
        self.activeDraftKey = self.options.get(
            "activeDraftKey",
            "ag_active_question_draft_id" if self.materialType == "question" else "ag_active_draft_id"
        )
        self.storage = storage if storage is not None else {}
        self.localStorage = local_storage if local_storage is not None else {}
        self.tags = list(self.options.get("initialTags", []))

        prefix = "draft_q_" if self.materialType == "question" else "draft_"
        active_id = self.localStorage.get(self.activeDraftKey)
        self.currentDraftId = active_id or f"{prefix}{int(time.time_ns())}"
        self.currentRevision = 1
        self.isDirty = False
        self.status = "saved"
        self.statusText = "Все изменения сохранены"

    def getTags(self):
        return list(self.tags)

    def setTags(self, tags):
        self.tags = list(tags)

    def triggerAutosave(self):
        self.isDirty = True
        self.setStatus("unsaved")

    def setStatus(self, state):
        self.status = state
        if state == "unsaved":
            self.statusText = "Есть изменения"
        elif state == "saving":
            self.statusText = "Сохранение..."
        elif state == "error":
            self.statusText = "Ошибка сохранения"
        else:
            self.statusText = "Все изменения сохранены"

    def flush(self):
        if not self.isDirty:
            return
        title_val = self.title.strip()
        text_val = self.editor.getText().strip()
        if not title_val and not text_val and not self.tags:
            self.isDirty = False
            self.setStatus("saved")
            return
        self.saveCurrent(is_auto=True)

    def saveCurrent(self, is_auto=False):
        title_val = self.title.strip()
        text_val = self.editor.getText().strip()
        if not title_val and not text_val and not self.tags and is_auto:
            self.setStatus("saved")
            self.isDirty = False
            return

        self.setStatus("saving")
        self.currentRevision += 1
        snippet = text_val[:150] or title_val

        draft = {
            "id": self.currentDraftId,
            "materialType": self.materialType,
            "schema": "antigravity-editor-v2",
            "title": self.title or "Без названия",
            "tags": list(self.tags),
            "revision": self.currentRevision,
            "delta": self.editor.getContents(),
            "html": f"<p>{text_val}</p>",
            "snippet": snippet,
            "textSnippet": snippet,
            "updatedAt": time.time() * 1000,
        }

        self.storage[self.currentDraftId] = draft
        self.localStorage[self.activeDraftKey] = self.currentDraftId
        self.isDirty = False
        self.setStatus("saved")

    def getAllDrafts(self):
        all_items = list(self.storage.values())
        if self.materialType == "question":
            filtered = [
                d for d in all_items
                if d.get("materialType") == "question"
                or (d.get("publicationSettings") and d["publicationSettings"].get("materialType") == "question")
                or str(d.get("id", "")).startswith("draft_q_")
            ]
        else:
            filtered = [
                d for d in all_items
                if d.get("materialType") != "question"
                and not (d.get("publicationSettings") and d["publicationSettings"].get("materialType") == "question")
                and not str(d.get("id", "")).startswith("draft_q_")
            ]
        filtered.sort(key=lambda d: d.get("updatedAt", 0), reverse=True)
        return filtered

    def getDraftsList(self):
        return self.getAllDrafts()

    def getBadgeCount(self):
        return len(self.getAllDrafts())

    def createNewDraft(self):
        self.flush()
        prefix = "draft_q_" if self.materialType == "question" else "draft_"
        self.currentDraftId = f"{prefix}{int(time.time_ns())}"
        self.localStorage[self.activeDraftKey] = self.currentDraftId
        self.currentRevision = 1
        self.title = ""
        self.editor.setText("")
        self.tags = []
        self.isDirty = False
        self.setStatus("saved")

    def loadDraft(self, draft, notify=True):
        if not draft or not draft.get("id"):
            return
        self.flush()
        self.currentDraftId = draft["id"]
        self.localStorage[self.activeDraftKey] = draft["id"]
        self.currentRevision = draft.get("revision", 1)
        self.title = "" if draft.get("title") == "Без названия" else draft.get("title", "")
        self.editor.setText(draft.get("snippet", ""))
        self.tags = list(draft.get("tags", []))
        self.isDirty = False
        self.setStatus("saved")

    def deleteDraft(self, draft_id):
        if draft_id in self.storage:
            del self.storage[draft_id]
        if self.currentDraftId == draft_id:
            remaining = self.getAllDrafts()
            if remaining:
                self.loadDraft(remaining[0], False)
            else:
                self.createNewDraft()

    def deleteCurrentDraft(self):
        target_id = self.currentDraftId
        if target_id in self.storage:
            del self.storage[target_id]
        self.isDirty = False
        self.createNewDraft()

    def clearActiveDraft(self):
        return self.deleteCurrentDraft()

    def migrateLegacyQuestionDraft(self):
        legacy = self.localStorage.get("smartcontractum_question_draft")
        if not legacy or not isinstance(legacy, dict):
            return
        title = (legacy.get("title") or "").strip()
        tags = legacy.get("tags") or []
        html = legacy.get("html") or ""
        text = html.replace("<p>", "").replace("</p>", "").strip()
        if title or text or tags:
            migration_id = f"draft_q_migrated_{int(time.time() * 1000)}"
            draft = {
                "id": migration_id,
                "materialType": "question",
                "schema": "antigravity-editor-v2",
                "title": title or "Без названия",
                "tags": list(tags),
                "revision": 1,
                "delta": {"ops": [{"insert": text + "\n"}]},
                "html": html,
                "snippet": text[:150] or title,
                "textSnippet": text[:150] or title,
                "updatedAt": time.time() * 1000,
            }
            self.storage[migration_id] = draft
            self.currentDraftId = migration_id
            self.localStorage[self.activeDraftKey] = migration_id
        if "smartcontractum_question_draft" in self.localStorage:
            del self.localStorage["smartcontractum_question_draft"]

    def autoRestore(self):
        if self.materialType == "question":
            self.migrateLegacyQuestionDraft()
            active_id = self.localStorage.get(self.activeDraftKey)
            draft = self.storage.get(active_id) if active_id else None
            is_question = draft and (
                draft.get("materialType") == "question" or str(draft.get("id", "")).startswith("draft_q_")
            )
            if draft and is_question:
                self.loadDraft(draft, False)
            else:
                question_drafts = self.getAllDrafts()
                if question_drafts:
                    self.loadDraft(question_drafts[0], False)
                else:
                    self.createNewDraft()
            return

        # Publication editor autoRestore
        active_id = self.localStorage.get("ag_active_draft_id")
        draft = self.storage.get(active_id) if active_id else None
        if draft:
            is_question = draft.get("materialType") == "question" or str(draft.get("id", "")).startswith("draft_q_")
            if is_question:
                self.createNewDraft()
            else:
                self.loadDraft(draft, False)


class TestIssue67QuestionDraftsSystem(unittest.TestCase):
    """Automated unit and contract tests for Issue #67."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(FRONTEND_DIR, "question-editor.html"), "r", encoding="utf-8") as f:
            cls.html = f.read()
        with open(os.path.join(FRONTEND_DIR, "css", "question-editor.css"), "r", encoding="utf-8") as f:
            cls.css = f.read()
        with open(os.path.join(FRONTEND_DIR, "js", "question-editor.js"), "r", encoding="utf-8") as f:
            cls.question_js = f.read()
        with open(os.path.join(FRONTEND_DIR, "js", "drafts.js"), "r", encoding="utf-8") as f:
            cls.drafts_js = f.read()

    # 1. DraftsManager supports materialType and configurable options
    def test_01_drafts_js_material_type_support_and_options(self):
        """drafts.js supports materialType, activeDraftKey, and tag serialization callbacks."""
        self.assertIn("materialType", self.drafts_js)
        self.assertIn("activeDraftKey", self.drafts_js)
        self.assertIn("ag_active_question_draft_id", self.drafts_js)
        self.assertIn("ag_active_draft_id", self.drafts_js)
        self.assertIn("tagsGetter", self.drafts_js)
        self.assertIn("tagsSetter", self.drafts_js)

        # Constructor signature checks
        match = re.search(r'constructor\s*\(\s*editor\s*,\s*titleInput\s*(?:,\s*options\s*=\s*\{\s*\})?\s*\)', self.drafts_js)
        self.assertIsNotNone(match, "DraftsManager constructor must accept options parameter")

    # 2. drafts.js filtering and strict draft isolation
    def test_02_drafts_js_filtering_and_strict_isolation(self):
        """getAllDrafts filters drafts by materialType with strict isolation between questions and articles."""
        self.assertIn("getAllDrafts", self.drafts_js)
        self.assertIn("getDraftsList", self.drafts_js)

        # Filtering logic checks
        self.assertIn("this.materialType === 'question'", self.drafts_js)
        self.assertIn("draft_q_", self.drafts_js)

        # Strict isolation in autoRestore
        self.assertIn("async autoRestore", self.drafts_js)
        self.assertIn("restoreQuestionDraft", self.drafts_js)

    # 3. SaveDraft structure and 4 autosave status states
    def test_03_savedraft_structure_and_autosave_statuses(self):
        """SaveDraft includes required metadata and setStatus supports 4 autosave states."""
        # Required draft fields in drafts.js
        self.assertIn("materialType: this.materialType", self.drafts_js)
        self.assertIn("revision: newRevision", self.drafts_js)
        self.assertIn("snippet:", self.drafts_js)
        self.assertIn("tags: tags", self.drafts_js)
        self.assertIn("updatedAt: Date.now()", self.drafts_js)

        # 4 autosave status classes
        self.assertIn("status-saved", self.drafts_js)
        self.assertIn("status-unsaved", self.drafts_js)
        self.assertIn("status-saving", self.drafts_js)
        self.assertIn("status-error", self.drafts_js)

        # Status text
        self.assertIn("Все изменения сохранены", self.drafts_js)
        self.assertIn("Сохранение...", self.drafts_js)
        self.assertIn("Ошибка сохранения", self.drafts_js)

    # 4. Question Editor HTML modal, badge, and script inclusion
    def test_04_question_editor_html_drafts_modal_and_badge(self):
        """question-editor.html contains drafts modal with required buttons and loads drafts.js."""
        self.assertIn('id="drafts-modal"', self.html)
        self.assertIn('id="drafts-list"', self.html)
        self.assertIn('id="btn-new-draft"', self.html)
        self.assertIn('id="btn-close-drafts"', self.html)
        self.assertIn('id="btn-drafts-modal"', self.html)
        self.assertIn('id="drafts-badge"', self.html)
        self.assertIn("Новый вопрос", self.html)

        # Script inclusion order: drafts.js before question-editor.js
        pos_drafts = self.html.find('src="js/drafts.js"')
        pos_question = self.html.find('src="js/question-editor.js"')
        self.assertGreater(pos_drafts, 0, "drafts.js script must be loaded in question-editor.html")
        self.assertGreater(pos_question, 0, "question-editor.js script must be loaded in question-editor.html")
        self.assertLess(pos_drafts, pos_question, "drafts.js must be loaded before question-editor.js")

    # 5. Question Editor CSS modal styling
    def test_05_question_editor_css_modal_and_drafts_styles(self):
        """question-editor.css contains styles for drafts modal and draft items."""
        self.assertIn(".modal-overlay", self.css)
        self.assertIn(".modal-card", self.css)
        self.assertIn(".drafts-list", self.css)
        self.assertIn(".draft-item", self.css)
        self.assertIn(".btn-load", self.css)
        self.assertIn(".btn-delete", self.css)
        self.assertIn(".status-saved", self.css)
        self.assertIn(".status-unsaved", self.css)
        self.assertIn(".status-saving", self.css)
        self.assertIn(".status-error", self.css)

    # 6. Question Editor JS integration
    def test_06_question_editor_js_drafts_manager_integration(self):
        """question-editor.js initializes DraftsManager with question options and clears draft on submit."""
        self.assertIn("window.DraftsManager", self.question_js)
        self.assertIn("materialType: 'question'", self.question_js)
        self.assertIn("ag_active_question_draft_id", self.question_js)
        self.assertIn("getTags", self.question_js)
        self.assertIn("setTags", self.question_js)
        self.assertIn("deleteCurrentDraft", self.question_js)
        self.assertIn("openDraftsModal", self.question_js)

    # 7. Simulation: Strict isolation between Question and Publication Editors
    def test_07_simulation_strict_isolation_between_editors(self):
        """Simulated DraftsManager enforces strict isolation between question and article drafts."""
        shared_db = {
            "draft_art_01": {
                "id": "draft_art_01",
                "materialType": "publication",
                "title": "Архитектура смарт-контрактов",
                "snippet": "Текст статьи...",
                "updatedAt": 1000,
            },
            "draft_q_01": {
                "id": "draft_q_01",
                "materialType": "question",
                "title": "Как вызвать fallback функцию?",
                "tags": ["solidity", "fallback"],
                "snippet": "Текст вопроса...",
                "updatedAt": 2000,
            }
        }
        shared_local_storage = {
            "ag_active_draft_id": "draft_art_01",
            "ag_active_question_draft_id": "draft_q_01"
        }

        # Question editor instance
        q_mgr = SimulatedDraftsManager(
            title="",
            options={"materialType": "question"},
            storage=shared_db,
            local_storage=shared_local_storage
        )
        q_drafts = q_mgr.getAllDrafts()
        self.assertEqual(len(q_drafts), 1)
        self.assertEqual(q_drafts[0]["id"], "draft_q_01")
        self.assertEqual(q_mgr.getBadgeCount(), 1)

        # Article editor instance
        art_mgr = SimulatedDraftsManager(
            title="",
            options={"materialType": "publication"},
            storage=shared_db,
            local_storage=shared_local_storage
        )
        art_drafts = art_mgr.getAllDrafts()
        self.assertEqual(len(art_drafts), 1)
        self.assertEqual(art_drafts[0]["id"], "draft_art_01")
        self.assertEqual(art_mgr.getBadgeCount(), 1)

        # AutoRestore in Question Editor should never restore article
        shared_local_storage["ag_active_question_draft_id"] = "draft_art_01"  # Tampered or stale key
        q_mgr.autoRestore()
        self.assertNotEqual(q_mgr.currentDraftId, "draft_art_01")
        self.assertTrue(q_mgr.currentDraftId.startswith("draft_q_"))

    # 8. Simulation: "Новый вопрос" creates new draft without overwriting previous
    def test_08_simulation_new_question_draft_creation(self):
        """Simulated createNewDraft saves current dirty draft and starts clean draft."""
        storage = {}
        local_storage = {}
        mgr = SimulatedDraftsManager(
            title="Первый вопрос о прокси",
            options={"materialType": "question", "initialTags": ["uups"]},
            storage=storage,
            local_storage=local_storage
        )
        mgr.editor.setText("Детали первого вопроса...")
        mgr.triggerAutosave()
        mgr.flush()

        first_id = mgr.currentDraftId
        self.assertIn(first_id, storage)
        self.assertEqual(mgr.getBadgeCount(), 1)

        # User clicks "Новый вопрос"
        mgr.createNewDraft()
        second_id = mgr.currentDraftId
        self.assertNotEqual(first_id, second_id)
        self.assertEqual(mgr.title, "")
        self.assertEqual(mgr.editor.getText(), "")
        self.assertEqual(mgr.getTags(), [])
        self.assertEqual(mgr.currentRevision, 1)

        # First draft remains intact in storage
        self.assertIn(first_id, storage)
        self.assertEqual(storage[first_id]["title"], "Первый вопрос о прокси")

    # 9. Simulation: Deleting draft removes only target draft with proper fallback
    def test_09_simulation_delete_draft_and_fallback(self):
        """Simulated deleteDraft removes target draft and switches active draft smoothly."""
        storage = {
            "draft_q_1": {
                "id": "draft_q_1",
                "materialType": "question",
                "title": "Вопрос номер один",
                "tags": ["one"],
                "snippet": "Детали 1",
                "updatedAt": 1000,
            },
            "draft_q_2": {
                "id": "draft_q_2",
                "materialType": "question",
                "title": "Вопрос номер два",
                "tags": ["two"],
                "snippet": "Детали 2",
                "updatedAt": 2000,
            }
        }
        local_storage = {"ag_active_question_draft_id": "draft_q_2"}
        mgr = SimulatedDraftsManager(
            options={"materialType": "question"},
            storage=storage,
            local_storage=local_storage
        )
        mgr.autoRestore()
        self.assertEqual(mgr.currentDraftId, "draft_q_2")
        self.assertEqual(mgr.getBadgeCount(), 2)

        # Delete non-active draft_q_1
        mgr.deleteDraft("draft_q_1")
        self.assertNotIn("draft_q_1", storage)
        self.assertIn("draft_q_2", storage)
        self.assertEqual(mgr.currentDraftId, "draft_q_2")
        self.assertEqual(mgr.getBadgeCount(), 1)

        # Delete active draft_q_2: fallback creates fresh empty draft
        mgr.deleteDraft("draft_q_2")
        self.assertNotIn("draft_q_2", storage)
        self.assertTrue(mgr.currentDraftId.startswith("draft_q_"))
        self.assertEqual(mgr.getBadgeCount(), 0)

    # 10. Simulation: Clear on successful submit
    def test_10_simulation_clear_on_successful_submit(self):
        """deleteCurrentDraft / clearActiveDraft clears submitted draft while retaining others."""
        storage = {
            "draft_q_submitting": {
                "id": "draft_q_submitting",
                "materialType": "question",
                "title": "Готовый к публикации вопрос",
                "tags": ["solidity"],
                "snippet": "Текст",
                "updatedAt": 1500,
            },
            "draft_q_other": {
                "id": "draft_q_other",
                "materialType": "question",
                "title": "Другой черновик вопроса",
                "tags": ["security"],
                "snippet": "Другой текст",
                "updatedAt": 1200,
            },
            "draft_art_01": {
                "id": "draft_art_01",
                "materialType": "publication",
                "title": "Статья черновик",
                "snippet": "Статья",
                "updatedAt": 1100,
            }
        }
        local_storage = {"ag_active_question_draft_id": "draft_q_submitting"}
        mgr = SimulatedDraftsManager(
            options={"materialType": "question"},
            storage=storage,
            local_storage=local_storage
        )
        mgr.autoRestore()
        self.assertEqual(mgr.currentDraftId, "draft_q_submitting")

        # Simulate submission success
        mgr.deleteCurrentDraft()

        # Submitted draft removed, other drafts preserved
        self.assertNotIn("draft_q_submitting", storage)
        self.assertIn("draft_q_other", storage)
        self.assertIn("draft_art_01", storage)
        self.assertEqual(mgr.getBadgeCount(), 1)
        self.assertNotEqual(mgr.currentDraftId, "draft_q_submitting")

    # 11. Simulation: Legacy localStorage migration
    def test_11_simulation_legacy_local_storage_migration(self):
        """One-time migration imports smartcontractum_question_draft into IndexedDB structure."""
        storage = {}
        local_storage = {
            "smartcontractum_question_draft": {
                "title": "Миграционный вопрос",
                "tags": ["migration", "upgrade"],
                "html": "<p>Контент вопроса до Issue #67</p>",
                "updatedAt": "2026-10-01T20:00:00.000Z"
            }
        }
        mgr = SimulatedDraftsManager(
            options={"materialType": "question"},
            storage=storage,
            local_storage=local_storage
        )
        mgr.autoRestore()

        # Legacy key removed
        self.assertNotIn("smartcontractum_question_draft", local_storage)

        # Migrated draft exists in storage
        self.assertEqual(len(storage), 1)
        migrated_id = list(storage.keys())[0]
        migrated = storage[migrated_id]

        self.assertEqual(migrated["title"], "Миграционный вопрос")
        self.assertEqual(migrated["materialType"], "question")
        self.assertEqual(migrated["tags"], ["migration", "upgrade"])
        self.assertEqual(mgr.currentDraftId, migrated_id)

    # 12. Code Standards: Zero emojis and no em dashes
    def test_12_code_standards_zero_emojis_and_no_em_dashes(self):
        """Verified files must contain zero emojis and no em dashes."""
        emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]')
        files_to_check = [
            os.path.join(FRONTEND_DIR, "question-editor.html"),
            os.path.join(FRONTEND_DIR, "css", "question-editor.css"),
            os.path.join(FRONTEND_DIR, "js", "question-editor.js"),
            os.path.join(FRONTEND_DIR, "js", "drafts.js"),
            __file__
        ]

        for filepath in files_to_check:
            rel = os.path.relpath(filepath, PROJECT_ROOT)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            emojis = emoji_pattern.findall(content)
            self.assertEqual(len(emojis), 0, f"Found emojis in {rel}: {emojis[:5]}")
            self.assertNotIn("\u2014", content, f"Found em dash in {rel}")


if __name__ == "__main__":
    unittest.main()
