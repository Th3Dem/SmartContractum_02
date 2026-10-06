import os
import unittest
import re

class TestIssue208FrontendSettings(unittest.TestCase):
    def setUp(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.frontend_public = os.path.join(self.base_dir, 'frontend', 'public')

    def test_files_exist(self):
        self.assertTrue(os.path.exists(os.path.join(self.frontend_public, 'settings.html')))
        self.assertTrue(os.path.exists(os.path.join(self.frontend_public, 'css', 'settings.css')))
        self.assertTrue(os.path.exists(os.path.join(self.frontend_public, 'js', 'settings.js')))

    def test_html_includes(self):
        with open(os.path.join(self.frontend_public, 'settings.html'), 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn('css/auth.css', content)
        self.assertIn('css/settings.css', content)
        self.assertIn('js/auth.js', content)
        self.assertIn('js/settings.js', content)

    def test_html_structure(self):
        with open(os.path.join(self.frontend_public, 'settings.html'), 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn('tabBtnProfile', content)
        self.assertIn('tabBtnSecurity', content)
        self.assertIn('name="firstName"', content)
        self.assertIn('btnSaveProfile', content)
        self.assertIn('btnRequestChangeEmail', content)

    def test_auth_js_link(self):
        with open(os.path.join(self.frontend_public, 'js', 'auth.js'), 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn('settings.html', content)

    def test_no_emojis_and_em_dashes(self):
        files = [
            os.path.join(self.frontend_public, 'settings.html'),
            os.path.join(self.frontend_public, 'css', 'settings.css'),
            os.path.join(self.frontend_public, 'js', 'settings.js'),
            os.path.join(self.frontend_public, 'js', 'auth.js')
        ]
        
        emoji_pattern = re.compile(
            "["
            "\U0001f600-\U0001f64f"  # emoticons
            "\U0001f300-\U0001f5ff"  # symbols & pictographs
            "\U0001f680-\U0001f6ff"  # transport & map symbols
            "\U0001f1e0-\U0001f1ff"  # flags (iOS)
            "]+", flags=re.UNICODE)

        for file in files:
            if os.path.exists(file):
                with open(file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.assertNotIn('\u2014', content, f"Em dash found in {file}")
                    # Remove false positive matching with regex or simply rely on not having any
                    # to be safe, I just check unicode emojis
                    self.assertFalse(emoji_pattern.search(content), f"Emoji found in {file}")

if __name__ == '__main__':
    unittest.main()
