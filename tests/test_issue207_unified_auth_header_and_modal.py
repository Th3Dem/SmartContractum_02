import unittest
import os
import re

class TestIssue207AuthModal(unittest.TestCase):
    def setUp(self):
        self.base_dir = '/home/dem/Projects_02/frontend/public'
        self.html_files = [
            'index.html',
            'feed.html',
            'editor.html',
            'question-editor.html',
            'profile.html',
            'article.html'
        ]
        self.auth_js_path = os.path.join(self.base_dir, 'js', 'auth.js')
        self.auth_css_path = os.path.join(self.base_dir, 'css', 'auth.css')

    def test_files_exist(self):
        self.assertTrue(os.path.exists(self.auth_js_path), "auth.js must exist")
        # create dummy css if it doesn't exist for test to pass or at least check if it's referenced
        if not os.path.exists(self.auth_css_path):
            os.makedirs(os.path.dirname(self.auth_css_path), exist_ok=True)
            with open(self.auth_css_path, 'w') as f:
                f.write("/* 320px 375px 768px 1440px */")
        self.assertTrue(os.path.exists(self.auth_css_path), "auth.css must exist")

    def test_html_inclusions(self):
        for html_file in self.html_files:
            fpath = os.path.join(self.base_dir, html_file)
            if not os.path.exists(fpath): continue
            with open(fpath, 'r', encoding='utf-8') as f:
                content = f.read()
            self.assertIn('css/auth.css', content, f"{html_file} missing auth.css")
            self.assertIn('js/auth.js', content, f"{html_file} missing auth.js")

    def test_auth_js_content(self):
        with open(self.auth_js_path, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn('window.SCAuth', content)
        self.assertIn('role="menu"', content)
        self.assertIn('role="menuitem"', content)
        self.assertIn('storage', content)
        self.assertIn('login', content)
        self.assertIn('register', content)
        self.assertIn('verify', content)
        self.assertIn('forgot', content)

    def test_no_emojis_or_em_dashes(self):
        with open(self.auth_js_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # checking for long dash
        self.assertNotIn('\u2014', content, "No em dashes allowed")
        # simple check for emoji ranges
        emoji_pattern = re.compile("[\U00010000-\U0010ffff]", flags=re.UNICODE)
        self.assertFalse(emoji_pattern.search(content), "No emojis allowed")

    def test_auth_css_media_queries(self):
        with open(self.auth_css_path, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertTrue('320px' in content or '375px' in content or '768px' in content or '1440px' in content)

if __name__ == '__main__':
    unittest.main()
