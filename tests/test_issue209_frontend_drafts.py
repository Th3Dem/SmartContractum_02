import os
import unittest
import re

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAFTS_JS_PATH = os.path.join(REPO_ROOT, 'frontend', 'public', 'js', 'drafts.js')
QUESTION_EDITOR_JS_PATH = os.path.join(REPO_ROOT, 'frontend', 'public', 'js', 'question-editor.js')

class TestIssue209FrontendDrafts(unittest.TestCase):
    def setUp(self):
        with open(DRAFTS_JS_PATH, 'r', encoding='utf-8') as f:
            self.drafts_js = f.read()
        with open(QUESTION_EDITOR_JS_PATH, 'r', encoding='utf-8') as f:
            self.question_editor_js = f.read()

    def test_no_emojis_and_em_dashes(self):
        emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]')
        self.assertFalse(emoji_pattern.search(self.drafts_js), "Found emojis in drafts.js")
        self.assertNotIn("\u2014", self.drafts_js, "Found em dash in drafts.js")

        self.assertFalse(emoji_pattern.search(self.question_editor_js), "Found emojis in question-editor.js")
        self.assertNotIn("\u2014", self.question_editor_js, "Found em dash in question-editor.js")

    def test_server_endpoints(self):
        self.assertIn('/api/drafts', self.drafts_js, "No calls to /api/drafts found")
        self.assertIn("fetch(`/api/drafts?material_type=${this.materialType}`", self.drafts_js)
        self.assertIn("fetch(`/api/drafts/${id}`", self.drafts_js)
        self.assertIn("'DELETE'", self.drafts_js)

    def test_status_messages(self):
        self.assertIn("Сохранено в аккаунте", self.drafts_js)
        self.assertIn("Сохранено на устройстве", self.drafts_js)
        self.assertIn("Конфликт синхронизации", self.drafts_js)

    def test_conflict_409(self):
        self.assertIn("409", self.drafts_js)

    def test_auth_change_reaction(self):
        self.assertIn("window.addEventListener('auth:change'", self.drafts_js)

    def test_user_id_isolation(self):
        self.assertIn("window.SCAuth.currentUser", self.drafts_js)
        self.assertIn("${this.userId}", self.drafts_js)

if __name__ == '__main__':
    unittest.main()
