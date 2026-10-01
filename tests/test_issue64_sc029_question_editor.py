"""
Tests for Issue #64 (SC-029): Dedicated Simplified Question Editor (question-editor.html).

Verifications:
1. feed.html #btnCreateQuestion points to question-editor.html.
2. editor.html redirects type=question to question-editor.html.
3. question-editor.html contains title input, tags container, Quill editor container,
   security notice, submit button, header navigation, auth modal, and NO longread CMS elements.
4. question-editor.js contains minimal toolbar configuration, tags parsing logic,
   inline validation without alert(), autosave under smartcontractum_question_draft.
5. Backend compatibility: POST /api/upload/image and POST /api/moderation/submit
   with materialType: 'question' succeed with safe defaults.
"""

import base64
import json
import os
import re
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")

import server

# Minimal valid 1x1 PNG bytes for image upload tests
TINY_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00"
    b"\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class TestIssue64SC029QuestionEditor(unittest.TestCase):
    """Targeted contract and unit tests for Issue #64 (SC-029)."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(FRONTEND_DIR, "feed.html"), "r", encoding="utf-8") as f:
            cls.feed_html = f.read()
        with open(os.path.join(FRONTEND_DIR, "editor.html"), "r", encoding="utf-8") as f:
            cls.editor_html = f.read()
        with open(os.path.join(FRONTEND_DIR, "question-editor.html"), "r", encoding="utf-8") as f:
            cls.question_editor_html = f.read()
        with open(os.path.join(FRONTEND_DIR, "css", "question-editor.css"), "r", encoding="utf-8") as f:
            cls.question_editor_css = f.read()
        with open(os.path.join(FRONTEND_DIR, "js", "question-editor.js"), "r", encoding="utf-8") as f:
            cls.question_editor_js = f.read()

        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue64.db")
        cls.media_dir = os.path.join(cls.temp_dir, "media")
        os.makedirs(cls.media_dir, exist_ok=True)

        cls.server = server.create_server(
            host="127.0.0.1",
            port=0,
            db_path=cls.db_path,
            directory=FRONTEND_DIR,
            media_dir=cls.media_dir
        )
        cls.port = cls.server.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"

        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.05)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _post_json(self, path: str, payload: dict, cookie: str = None):
        data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data_bytes,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        if cookie:
            req.add_header("Cookie", cookie)
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return resp.status, data
        except urllib.error.HTTPError as e:
            try:
                data = json.loads(e.read().decode("utf-8"))
            except Exception:
                data = {"error": str(e)}
            return e.code, data

    def _post_binary(self, path: str, data: bytes, content_type: str = "image/png"):
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers={"Content-Type": content_type}
        )
        try:
            with urllib.request.urlopen(req) as resp:
                data_json = json.loads(resp.read().decode("utf-8"))
                return resp.status, data_json
        except urllib.error.HTTPError as e:
            try:
                data_json = json.loads(e.read().decode("utf-8"))
            except Exception:
                data_json = {"error": str(e)}
            return e.code, data_json

    def _login(self, user_id: str, name: str = None):
        status, data = self._post_json("/api/auth/login", {"userId": user_id, "name": name or user_id})
        return f"sc_session={data.get('sessionToken')}"

    # 1. Routing in feed.html
    def test_01_feed_html_btn_create_question_points_to_question_editor(self):
        """In feed.html, #btnCreateQuestion href points to question-editor.html."""
        btn_match = re.search(r'<a[^>]*id=["\']btnCreateQuestion["\'][^>]*>', self.feed_html)
        self.assertIsNotNone(btn_match, "#btnCreateQuestion not found in feed.html")
        btn_tag = btn_match.group(0)
        self.assertIn('href="question-editor.html"', btn_tag)

        # #btnCreatePublication continues to point to editor.html
        pub_btn_match = re.search(r'<a[^>]*id=["\']btnCreatePublication["\'][^>]*>', self.feed_html)
        self.assertIsNotNone(pub_btn_match, "#btnCreatePublication not found in feed.html")
        self.assertIn('href="editor.html"', pub_btn_match.group(0))

    # 2. Redirect in editor.html
    def test_02_editor_html_redirects_type_question_to_question_editor(self):
        """editor.html redirects immediately to question-editor.html if type=question."""
        self.assertIn("type=question", self.editor_html)
        self.assertIn("question-editor.html", self.editor_html)
        self.assertTrue(
            "window.location.replace('question-editor.html'" in self.editor_html
            or 'window.location.replace("question-editor.html"' in self.editor_html
            or "location.replace('question-editor.html'" in self.editor_html
        )

    # 3. Page Structure of question-editor.html
    def test_03_question_editor_html_structure_and_required_elements(self):
        """question-editor.html contains title, tags container, Quill editor, notice, and submit button."""
        # Page Title
        self.assertIn('<h1 class="question-title">Задать вопрос</h1>', self.question_editor_html)

        # Single-line title input
        self.assertIn('id="questionTitleInput"', self.question_editor_html)
        self.assertIn('class="question-input"', self.question_editor_html)
        self.assertIn('id="questionTitleError"', self.question_editor_html)

        # Tags wrapper and input
        self.assertIn('id="questionTagsWrapper"', self.question_editor_html)
        self.assertIn('id="questionTagsList"', self.question_editor_html)
        self.assertIn('id="questionTagInput"', self.question_editor_html)
        self.assertIn('id="questionTagsError"', self.question_editor_html)

        # Details section & compact Quill editor
        self.assertIn('id="questionEditor"', self.question_editor_html)
        self.assertIn('id="questionToolbar"', self.question_editor_html)
        self.assertIn('id="questionDetailsError"', self.question_editor_html)

        # Security notice banner
        self.assertIn("Не публикуйте приватные ключи, seed-фразы, пароли и боевые секреты смарт-контрактов.", self.question_editor_html)

        # Form error and autosave indicator
        self.assertIn('id="questionFormError"', self.question_editor_html)
        self.assertIn('id="questionAutosaveStatus"', self.question_editor_html)
        self.assertIn('Черновик сохранен', self.question_editor_html)

        # Submit action button
        self.assertIn('id="btnSubmitQuestion"', self.question_editor_html)
        self.assertIn('Опубликовать вопрос', self.question_editor_html)

        # Global header with logo, nav links, theme switch, auth button, and auth modal
        self.assertIn('id="appHeader"', self.question_editor_html)
        self.assertIn('brand-logo', self.question_editor_html)
        self.assertIn('navIndex', self.question_editor_html)
        self.assertIn('navFeed', self.question_editor_html)
        self.assertIn('id="btnCreateDropdown"', self.question_editor_html)
        self.assertIn('id="btnThemeToggle"', self.question_editor_html)
        self.assertIn('id="headerLoginBtn"', self.question_editor_html)
        self.assertIn('id="authModal"', self.question_editor_html)

        # Reuses shared styles and core scripts
        self.assertIn('css/theme.css', self.question_editor_html)
        self.assertIn('css/question-editor.css', self.question_editor_html)
        self.assertIn('vendor/quill/quill.snow.css', self.question_editor_html)
        self.assertIn('vendor/quill/quill.js', self.question_editor_html)
        self.assertIn('js/core.js', self.question_editor_html)
        self.assertIn('js/question-editor.js', self.question_editor_html)

    # 4. Exclusion of Longread CMS features
    def test_04_question_editor_html_excludes_longread_cms_elements(self):
        """question-editor.html strictly excludes publication modal, wizard, format selector, and cover upload."""
        # No publication modal
        self.assertNotIn('id="publication-modal"', self.question_editor_html)
        self.assertNotIn('class="pub-modal"', self.question_editor_html)
        self.assertNotIn('pub-section-num', self.question_editor_html)

        # No format dropdown
        self.assertNotIn('id="pub-format-select"', self.question_editor_html)
        self.assertNotIn('name="format"', self.question_editor_html)

        # No complexity dropdown
        self.assertNotIn('id="pub-complexity-select"', self.question_editor_html)

        # No cover image cropper or dropzone
        self.assertNotIn('id="cover-upload-area"', self.question_editor_html)
        self.assertNotIn('id="cropper-modal"', self.question_editor_html)

        # No table modal or formula modal
        self.assertNotIn('id="table-modal"', self.question_editor_html)
        self.assertNotIn('id="formula-modal"', self.question_editor_html)
        self.assertNotIn('id="video-modal"', self.question_editor_html)

    # 5. question-editor.js Minimal Toolbar Configuration
    def test_05_question_editor_js_minimal_toolbar(self):
        """question-editor.js toolbar contains only bold, italic, code, link, lists, blockquote, code-block, custom-spoiler, image."""
        self.assertIn("'bold'", self.question_editor_js)
        self.assertIn("'italic'", self.question_editor_js)
        self.assertIn("'code'", self.question_editor_js)
        self.assertIn("'link'", self.question_editor_js)
        self.assertIn("'bullet'", self.question_editor_js)
        self.assertIn("'ordered'", self.question_editor_js)
        self.assertIn("'blockquote'", self.question_editor_js)
        self.assertIn("'code-block'", self.question_editor_js)
        self.assertIn("'custom-spoiler'", self.question_editor_js)
        self.assertIn("'image'", self.question_editor_js)

        # Verify no header h1-h6 in question editor toolbar
        self.assertNotIn("{ 'header': 1 }", self.question_editor_js)
        self.assertNotIn("{ 'header': 2 }", self.question_editor_js)
        self.assertNotIn("{ 'header': [", self.question_editor_js)

    # 6. question-editor.js Tags and Validation Logic
    def test_06_question_editor_js_tags_and_validation(self):
        """question-editor.js implements comma/Enter tags, deduplication, backspace, and inline validation without alert()."""
        # Tags logic
        self.assertIn("addTag", self.question_editor_js)
        self.assertIn("removeTag", self.question_editor_js)
        self.assertIn("MAX_TAGS", self.question_editor_js)
        self.assertIn("Enter", self.question_editor_js)
        self.assertIn("Backspace", self.question_editor_js)

        # Validation logic
        self.assertIn("MIN_TITLE_LEN", self.question_editor_js)
        self.assertIn("MAX_TITLE_LEN", self.question_editor_js)
        self.assertIn("MIN_DETAILS_LEN", self.question_editor_js)
        self.assertIn("validateForm", self.question_editor_js)

        # Zero alert() in question-editor.js
        alert_calls = re.findall(r'\balert\s*\(', self.question_editor_js)
        self.assertEqual(len(alert_calls), 0, "question-editor.js must not call alert() for validation")

    # 7. Draft Autosave & Submission in question-editor.js
    def test_07_question_editor_js_autosave_and_submission(self):
        """question-editor.js autosaves to smartcontractum_question_draft and submits to /api/moderation/submit."""
        self.assertIn("smartcontractum_question_draft", self.question_editor_js)
        self.assertIn("saveDraft", self.question_editor_js)
        self.assertIn("restoreDraft", self.question_editor_js)
        self.assertIn("clearDraft", self.question_editor_js)
        self.assertIn("/api/moderation/submit", self.question_editor_js)
        self.assertIn("materialType", self.question_editor_js)
        self.assertIn("question", self.question_editor_js)

    # 8. Backend POST /api/upload/image integration
    def test_08_backend_upload_image_endpoints(self):
        """POST /api/upload/image accepts binary PNG bytes and JSON Data URI."""
        # 8a. Direct binary upload
        status_bin, data_bin = self._post_binary("/api/upload/image", TINY_PNG_BYTES, content_type="image/png")
        self.assertEqual(status_bin, 200)
        self.assertTrue(data_bin.get("success"))
        saved_url = data_bin.get("url")
        self.assertTrue(saved_url.startswith("/media/"))

        # 8b. JSON Data URI upload
        b64_png = base64.b64encode(TINY_PNG_BYTES).decode("ascii")
        data_uri = f"data:image/png;base64,{b64_png}"
        status_json, data_json = self._post_json("/api/upload/image", {"image": data_uri})
        self.assertEqual(status_json, 200)
        self.assertTrue(data_json.get("success"))
        self.assertTrue(data_json.get("url").startswith("/media/"))

    # 9. Backend POST /api/moderation/submit question with safe defaults
    def test_09_backend_question_submission_with_safe_defaults(self):
        """POST /api/moderation/submit with materialType: question succeeds with safe defaults."""
        cookie = self._login("author_issue64", "Алиса Вопросова")

        payload = {
            "title": "Как реализовать безопасный UUPS прокси контракт?",
            "html": "<p>Подробное описание вопроса о том, как реализовать безопасный UUPS прокси без уязвимостей.</p>",
            "materialType": "question",
            "publicationSettings": {
                "keywords": ["uups", "upgradeable", "security"],
                "targetAudience": "developers",
                "topics": ["smart-contracts-development"],
                "description": "Краткое описание вопроса по архитектуре UUPS прокси контрактов."
            },
            "idempotencyKey": "idemp_q_001"
        }

        status, data = self._post_json("/api/moderation/submit", payload, cookie=cookie)
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("status"), "pending_moderation")
        submission_id = data.get("submissionId")
        self.assertIsNotNone(submission_id)
        self.assertTrue(submission_id.startswith("sub_"))

        # Verify duplicate submission returns isDuplicate: True
        status_dup, data_dup = self._post_json("/api/moderation/submit", payload, cookie=cookie)
        self.assertEqual(status_dup, 200)
        self.assertTrue(data_dup.get("success"))
        self.assertTrue(data_dup.get("isDuplicate"))
        self.assertEqual(data_dup.get("submissionId"), submission_id)

    # 10. Backend unauthenticated submission returns 401
    def test_10_backend_question_submission_unauthenticated(self):
        """POST /api/moderation/submit without authentication returns 401 Unauthorized."""
        payload = {
            "title": "Вопрос от неавторизованного пользователя",
            "html": "<p>Текст вопроса, который должен быть отклонен сервером с 401.</p>",
            "materialType": "question"
        }
        status, data = self._post_json("/api/moderation/submit", payload)
        self.assertEqual(status, 401)
        self.assertFalse(data.get("success"))
        self.assertTrue(data.get("requireAuth"))

    # 11. Code standards: zero emojis and no em dashes
    def test_11_code_standards_zero_emojis_and_no_em_dashes(self):
        """Verified files must contain zero emojis and no em dashes."""
        files_to_check = [
            ("question-editor.html", self.question_editor_html),
            ("question-editor.css", self.question_editor_css),
            ("question-editor.js", self.question_editor_js)
        ]
        for name, content in files_to_check:
            # Check for em dash (U+2014) and en dash (U+2013)
            self.assertNotIn("\u2014", content, f"Em dash found in {name}")
            self.assertNotIn("\u2013", content, f"En dash found in {name}")

            # Check for high unicode / emojis
            for ch in content:
                self.assertLess(ord(ch), 0x1f000, f"Emoji character {ch} found in {name}")


if __name__ == "__main__":
    unittest.main()
