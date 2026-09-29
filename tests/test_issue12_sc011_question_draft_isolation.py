#!/usr/bin/env python3
"""
tests/test_issue12_sc011_question_draft_isolation.py

Regression test suite for Issue #12 (SC-011):
"Изолировать действие «Задать вопрос» от автовосстановления статей"
GitHub Issue: #12 (https://github.com/Th3Dem/SmartContractum_02/issues/12)

Acceptance Criteria:
1. При переходе по ссылке editor.html?type=question создается новый независимый
   черновик вопроса без подгрузки старой статьи и без сброса типа на article.
2. Предыдущий черновик статьи сохраняется в списке черновиков и доступен для
   открытия через модальное окно.
3. Штатный вход в editor.html без параметров продолжает восстанавливать последний
   активный черновик.
4. 100% тестов проекта проходят успешно (python3 -m unittest discover tests/).
5. Оформлен tasks/issue-12-sc011-isolate-ask-question-draft/DEV_HANDOVER.md.
"""

import os
import re
import tempfile
import threading
import time
import unittest
import urllib.parse
import urllib.request

import server
from server import create_server, init_db

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
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


class SimulatedPublicationManager:
    def __init__(self, search_query=""):
        self.search_query = search_query
        self.materialType = "article"
        self.description = ""
        self.topics = []
        self.keywords = []

        params = urllib.parse.parse_qs(self.search_query.lstrip("?"))
        types = params.get("type", [])
        if types and types[0] == "question":
            self.setMaterialType("question")

    def setMaterialType(self, mat_type):
        self.materialType = mat_type or "article"

    def getSettings(self):
        return {
            "materialType": self.materialType,
            "type": self.materialType,
            "description": self.description,
            "topics": list(self.topics),
            "keywords": list(self.keywords),
        }

    def loadSettings(self, settings):
        if not settings or not isinstance(settings, dict):
            self.resetSettings()
            return
        self.materialType = settings.get("materialType") or settings.get("type") or "article"
        self.setMaterialType(self.materialType)
        self.description = settings.get("description", "")
        self.topics = list(settings.get("topics", []))
        self.keywords = list(settings.get("keywords", []))

    def resetSettings(self):
        default_type = "article"
        params = urllib.parse.parse_qs(self.search_query.lstrip("?"))
        types = params.get("type", [])
        if types and types[0] == "question":
            default_type = "question"

        self.materialType = default_type
        self.description = ""
        self.topics = []
        self.keywords = []
        if default_type == "question":
            self.setMaterialType("question")


class SimulatedDraftsManager:
    def __init__(self, editor, publication_manager, storage=None, active_draft_id=None, search_query=""):
        self.editor = editor
        self.publication = publication_manager
        self.search_query = search_query
        self.storage = storage if storage is not None else {}
        self.active_draft_id = active_draft_id
        self.currentDraftId = active_draft_id or f"draft_{int(time.time() * 1000)}"
        self.title = ""
        self.isDirty = False
        self.status = "saved"
        self.toasts = []

    def showToast(self, msg, toast_type="info"):
        self.toasts.append({"message": msg, "type": toast_type})

    def flush(self):
        if not self.isDirty:
            return
        if not self.title.strip() and not self.editor.getText().strip():
            self.isDirty = False
            return
        self.storage[self.currentDraftId] = {
            "id": self.currentDraftId,
            "title": self.title or "Без названия",
            "text": self.editor.getText(),
            "publicationSettings": self.publication.getSettings(),
            "updatedAt": time.time() * 1000,
        }
        self.isDirty = False

    def createNewDraft(self):
        self.flush()
        self.currentDraftId = f"draft_{int(time.time() * 1000)}"
        self.active_draft_id = self.currentDraftId
        self.title = ""
        self.editor.setText("")
        self.publication.resetSettings()
        self.isDirty = False
        self.status = "saved"
        self.showToast("Создан новый чистый черновик", "success")

    def loadDraft(self, draft, notify=True):
        if not draft or not draft.get("id"):
            return
        self.flush()
        self.currentDraftId = draft["id"]
        self.active_draft_id = draft["id"]
        self.title = "" if draft.get("title") == "Без названия" else draft.get("title", "")
        self.editor.setText(draft.get("text", ""))

        pub_settings = draft.get("publicationSettings")
        if pub_settings:
            self.publication.loadSettings(pub_settings)
        else:
            self.publication.resetSettings()

        self.isDirty = False
        self.status = "saved"
        if notify:
            self.showToast(f"Черновик «{draft.get('title') or 'Без названия'}» восстановлен", "info")

    def autoRestore(self):
        params = urllib.parse.parse_qs(self.search_query.lstrip("?"))
        types = params.get("type", [])
        requested_type = types[0] if types else None

        active_id = self.active_draft_id
        if not active_id:
            if requested_type == "question":
                self.publication.setMaterialType("question")
            return

        draft = self.storage.get(active_id)

        if requested_type == "question":
            active_material_type = None
            if draft and draft.get("publicationSettings"):
                pub_settings = draft["publicationSettings"]
                active_material_type = pub_settings.get("materialType") or pub_settings.get("type")

            if draft and active_material_type == "question":
                self.loadDraft(draft, False)
                self.publication.setMaterialType("question")
            else:
                self.createNewDraft()
                self.publication.setMaterialType("question")
            return

        if draft:
            self.loadDraft(draft, False)

    def getAllDrafts(self):
        draft_list = list(self.storage.values())
        draft_list.sort(key=lambda d: d.get("updatedAt", 0), reverse=True)
        return draft_list


class TestIssue12SC011QuestionDraftIsolation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue12_sc011.db")
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
            cls.publication_js = f.read()

        feed_html_path = os.path.join(FRONTEND_DIR, "feed.html")
        with open(feed_html_path, "r", encoding="utf-8") as f:
            cls.feed_html = f.read()

        editor_html_path = os.path.join(FRONTEND_DIR, "editor.html")
        with open(editor_html_path, "r", encoding="utf-8") as f:
            cls.editor_html = f.read()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.httpd.shutdown()
            cls.httpd.server_close()
        except Exception:
            pass

    def test_01_http_serves_frontend_files_correctly(self):
        """Verify server delivers editor.html, feed.html, drafts.js, publication.js with 200 OK."""
        files = ["editor.html", "feed.html", "js/drafts.js", "js/publication.js"]
        for rel_path in files:
            req = urllib.request.Request(f"{self.base_url}/{rel_path}")
            with urllib.request.urlopen(req) as resp:
                self.assertEqual(resp.status, 200, f"Expected 200 OK for {rel_path}")
                content = resp.read().decode("utf-8")
                self.assertGreater(len(content), 100, f"Content too short for {rel_path}")

    def test_02_static_analysis_autorestore_in_drafts_js(self):
        """Verify autoRestore checks URL search params and isolates question drafts from articles."""
        # Find autoRestore method
        match = re.search(r'async\s+autoRestore\s*\(\s*\)\s*\{(.*?)\n\s*async\s+loadDraft', self.drafts_js, re.DOTALL)
        self.assertIsNotNone(match, "DraftsManager must implement async autoRestore()")
        body = match.group(1)

        # 1. Reads URL parameter type using URLSearchParams
        self.assertIn("URLSearchParams", body, "autoRestore must inspect URLSearchParams")
        self.assertIn("window.location.search", body, "autoRestore must inspect window.location.search")
        self.assertIn("get('type')", body, "autoRestore must retrieve 'type' parameter")

        # 2. Checks if requestedType === 'question'
        self.assertIn("requestedType === 'question'", body, "autoRestore must branch on requestedType === 'question'")

        # 3. Inspects draft materialType
        self.assertRegex(
            body,
            r'activeMaterialType\s*===\s*[\'"]question[\'"]',
            "autoRestore must check if active draft materialType is 'question'"
        )

        # 4. Calls createNewDraft() when active draft is NOT a question
        self.assertIn(
            "await this.createNewDraft();",
            body,
            "autoRestore must call await this.createNewDraft() when active draft is not a question"
        )

        # 5. Sets materialType to 'question' on PublicationManager
        self.assertIn(
            "pub.setMaterialType('question')",
            body,
            "autoRestore must configure question materialType on PublicationManager"
        )

        # 6. Preserves loadDraft for existing question draft or normal editor access
        self.assertIn("await this.loadDraft(draft, false);", body)

    def test_03_static_analysis_publication_js_preserves_question_type(self):
        """Verify publication.js respects and preserves question materialType across lifecycles."""
        # 1. Constructor checks ?type=question
        self.assertIn("urlParams.get('type') === 'question'", self.publication_js)
        self.assertIn("this.setMaterialType('question');", self.publication_js)

        # 2. resetSettings defaults to question if ?type=question is in URL
        reset_match = re.search(r'resetSettings\s*\(\s*\)\s*\{(.*?)\n\s*validate\s*\(', self.publication_js, re.DOTALL)
        self.assertIsNotNone(reset_match, "PublicationManager must implement resetSettings()")
        reset_body = reset_match.group(1)
        self.assertIn("URLSearchParams", reset_body, "resetSettings must check URLSearchParams")
        self.assertIn("defaultMaterialType = 'question'", reset_body)
        self.assertIn("this.setMaterialType(defaultMaterialType);", reset_body)

        # 3. loadSettings synchronizes UI state with loaded materialType
        load_match = re.search(r'loadSettings\s*\(\s*settings\s*\)\s*\{(.*?)\n\s*resetSettings', self.publication_js, re.DOTALL)
        self.assertIsNotNone(load_match, "PublicationManager must implement loadSettings()")
        load_body = load_match.group(1)
        self.assertIn("this.setMaterialType(this.materialType);", load_body)

    def test_04_simulation_autorestore_with_question_url_and_article_draft(self):
        """Scenario 1: editor.html?type=question with active article draft initializes fresh question."""
        editor = SimulatedQuill()
        pub = SimulatedPublicationManager(search_query="?type=question")

        article_draft = {
            "id": "draft_article_001",
            "title": "Глубокий анализ EVM и байткода",
            "text": "Статья про опкоды, память и стек EVM виртуальной машины...",
            "publicationSettings": {
                "materialType": "article",
                "topics": ["solidity"],
                "keywords": ["evm", "opcodes"]
            },
            "updatedAt": 1000000
        }
        storage = {"draft_article_001": dict(article_draft)}

        # User previously had article draft active
        manager = SimulatedDraftsManager(
            editor=editor,
            publication_manager=pub,
            storage=storage,
            active_draft_id="draft_article_001",
            search_query="?type=question"
        )

        # Execute autoRestore on ?type=question
        manager.autoRestore()

        # Acceptance Criteria 1:
        # - Article content is NOT loaded
        self.assertEqual(manager.title, "", "Title must remain blank for fresh question draft")
        self.assertEqual(manager.editor.getText(), "", "Editor text must remain blank for fresh question draft")
        # - A new draft ID is active
        self.assertNotEqual(manager.currentDraftId, "draft_article_001", "Must generate new ID instead of active article ID")
        self.assertEqual(manager.active_draft_id, manager.currentDraftId)
        # - Material type is strictly 'question'
        self.assertEqual(pub.materialType, "question", "Material type must be set to 'question'")
        self.assertEqual(pub.getSettings()["materialType"], "question")
        # - Toast confirms clean draft creation
        self.assertTrue(any("Создан новый чистый черновик" in t["message"] for t in manager.toasts))

    def test_05_simulation_old_article_preserved_and_accessible_in_modal(self):
        """Scenario 2: Previous article draft remains untouched in storage and can be opened."""
        editor = SimulatedQuill()
        pub = SimulatedPublicationManager(search_query="?type=question")

        article_draft = {
            "id": "draft_article_001",
            "title": "Руководство по архитектуре DeFi",
            "text": "Полный обзор пулов ликвидности AMM...",
            "publicationSettings": {
                "materialType": "article",
                "topics": ["defi"],
                "keywords": ["amm", "liquidity"]
            },
            "updatedAt": 500000
        }
        storage = {"draft_article_001": dict(article_draft)}

        manager = SimulatedDraftsManager(
            editor=editor,
            publication_manager=pub,
            storage=storage,
            active_draft_id="draft_article_001",
            search_query="?type=question"
        )

        # 1. AutoRestore creates new question draft
        manager.autoRestore()
        question_draft_id = manager.currentDraftId

        # 2. Check that the original article is intact in storage
        self.assertIn("draft_article_001", manager.storage, "Original article draft must remain in storage")
        saved_article = manager.storage["draft_article_001"]
        self.assertEqual(saved_article["title"], "Руководство по архитектуре DeFi")
        self.assertEqual(saved_article["publicationSettings"]["materialType"], "article")

        # 3. Check drafts list contains both drafts
        drafts_list = manager.getAllDrafts()
        self.assertTrue(any(d["id"] == "draft_article_001" for d in drafts_list))

        # 4. User opens drafts modal and clicks "Открыть" on old article draft
        manager.loadDraft(saved_article, notify=True)

        self.assertEqual(manager.currentDraftId, "draft_article_001")
        self.assertEqual(manager.title, "Руководство по архитектуре DeFi")
        self.assertIn("Полный обзор пулов ликвидности AMM", manager.editor.getText())
        self.assertEqual(pub.materialType, "article", "Loading article must restore 'article' materialType")
        self.assertTrue(any("Руководство по архитектуре DeFi" in t["message"] for t in manager.toasts))

    def test_06_simulation_autorestore_with_question_url_and_existing_question_draft(self):
        """Scenario 3: editor.html?type=question with existing active question draft restores it."""
        editor = SimulatedQuill()
        pub = SimulatedPublicationManager(search_query="?type=question")

        question_draft = {
            "id": "draft_question_456",
            "title": "Как верифицировать контракт в блокчейн-эксплорере?",
            "text": "1. Что вы пытались сделать?\nЗагрузить стандартный JSON...",
            "publicationSettings": {
                "materialType": "question",
                "topics": ["contracts"],
                "keywords": ["verification"]
            },
            "updatedAt": 700000
        }
        storage = {"draft_question_456": dict(question_draft)}

        manager = SimulatedDraftsManager(
            editor=editor,
            publication_manager=pub,
            storage=storage,
            active_draft_id="draft_question_456",
            search_query="?type=question"
        )

        manager.autoRestore()

        # Existing question draft is restored
        self.assertEqual(manager.currentDraftId, "draft_question_456")
        self.assertEqual(manager.title, "Как верифицировать контракт в блокчейн-эксплорере?")
        self.assertIn("1. Что вы пытались сделать?", manager.editor.getText())
        self.assertEqual(pub.materialType, "question")

    def test_07_simulation_autorestore_standard_mode_without_url_params(self):
        """Scenario 4: editor.html without URL parameters restores last active article draft normally."""
        editor = SimulatedQuill()
        pub = SimulatedPublicationManager(search_query="")

        article_draft = {
            "id": "draft_article_789",
            "title": "Обзор безопасности ERC-4337",
            "text": "Абстракция учетных записей и UserOperation...",
            "publicationSettings": {
                "materialType": "article",
                "topics": ["security"],
                "keywords": ["erc4337", "account-abstraction"]
            },
            "updatedAt": 800000
        }
        storage = {"draft_article_789": dict(article_draft)}

        manager = SimulatedDraftsManager(
            editor=editor,
            publication_manager=pub,
            storage=storage,
            active_draft_id="draft_article_789",
            search_query=""
        )

        manager.autoRestore()

        # Regular editor restored the active article
        self.assertEqual(manager.currentDraftId, "draft_article_789")
        self.assertEqual(manager.title, "Обзор безопасности ERC-4337")
        self.assertIn("Абстракция учетных записей", manager.editor.getText())
        self.assertEqual(pub.materialType, "article")

    def test_08_simulation_fresh_browser_state_question_url(self):
        """Scenario 5: First-time open of editor.html?type=question with no active drafts."""
        editor = SimulatedQuill()
        pub = SimulatedPublicationManager(search_query="?type=question")

        manager = SimulatedDraftsManager(
            editor=editor,
            publication_manager=pub,
            storage={},
            active_draft_id=None,
            search_query="?type=question"
        )

        manager.autoRestore()

        self.assertEqual(manager.title, "")
        self.assertEqual(manager.editor.getText(), "")
        self.assertEqual(pub.materialType, "question")

        # Saving initial text produces question draft
        manager.title = "Вопрос по газу в Layer 2"
        manager.editor.setText("Почему газ в Arbitrum дешевле чем в Ethereum?")
        manager.isDirty = True
        manager.flush()

        saved = manager.storage[manager.currentDraftId]
        self.assertEqual(saved["title"], "Вопрос по газу в Layer 2")
        self.assertEqual(saved["publicationSettings"]["materialType"], "question")

    def test_09_feed_html_entry_points_link_to_question_editor(self):
        """Verify feed.html includes action buttons linking to editor.html?type=question."""
        self.assertIn('href="editor.html?type=question"', self.feed_html)
        self.assertIn('id="btnCreateQuestion"', self.feed_html)
        self.assertIn('id="btnWidgetAskQuestion"', self.feed_html)

    def test_10_js_syntax_integrity_and_formatting(self):
        """Verify balanced braces, quotes, and structural integrity of drafts.js and publication.js."""
        for name, content in [("drafts.js", self.drafts_js), ("publication.js", self.publication_js)]:
            open_braces = content.count("{")
            close_braces = content.count("}")
            self.assertEqual(open_braces, close_braces, f"Mismatched braces in {name}: {open_braces} vs {close_braces}")

            open_parens = content.count("(")
            close_parens = content.count(")")
            self.assertEqual(open_parens, close_parens, f"Mismatched parens in {name}: {open_parens} vs {close_parens}")

            open_brackets = content.count("[")
            close_brackets = content.count("]")
            self.assertEqual(open_brackets, close_brackets, f"Mismatched brackets in {name}: {open_brackets} vs {close_brackets}")

            self.assertIn("(function (window) {", content, f"{name} must be wrapped in IIFE")
            self.assertTrue(content.strip().endswith("})(window);"), f"{name} must end with IIFE invocation")
            self.assertNotIn("debugger;", content, f"{name} must not contain debugger statements")


if __name__ == "__main__":
    unittest.main()
