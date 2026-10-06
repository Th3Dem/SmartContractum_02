import unittest
import os
import re

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class TestNotificationsFrontend(unittest.TestCase):
    def setUp(self):
        self.css_path = os.path.join(REPO_ROOT, 'frontend', 'public', 'css', 'notifications.css')
        self.js_path = os.path.join(REPO_ROOT, 'frontend', 'public', 'js', 'notifications.js')
        self.html_files = [
            'index.html', 'feed.html', 'article.html', 'profile.html', 
            'settings.html', 'editor.html', 'question-editor.html'
        ]

    def test_files_exist(self):
        self.assertTrue(os.path.exists(self.css_path), "notifications.css should exist")
        self.assertTrue(os.path.exists(self.js_path), "notifications.js should exist")

    def test_html_integration(self):
        for html_file in self.html_files:
            path = os.path.join(REPO_ROOT, 'frontend', 'public', html_file)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

            self.assertIn('css/notifications.css', content, f"{html_file} missing CSS")
            self.assertIn('js/notifications.js', content, f"{html_file} missing JS")
            self.assertIn('header-notif-wrap', content, f"{html_file} missing header-notif-wrap")
            self.assertIn('headerNotificationsBtn', content, f"{html_file} missing headerNotificationsBtn")
            self.assertIn('headerNotifBadge', content, f"{html_file} missing headerNotifBadge")
            self.assertIn('headerNotifPopup', content, f"{html_file} missing headerNotifPopup")
            self.assertIn('notifMarkAllReadBtn', content, f"{html_file} missing notifMarkAllReadBtn")
            self.assertIn('notifListContainer', content, f"{html_file} missing notifListContainer")

    def test_js_logic(self):
        with open(self.js_path, 'r', encoding='utf-8') as f:
            content = f.read()

        self.assertIn('window.SCNotifications', content)
        self.assertIn('auth:change', content)
        self.assertIn('visibilitychange', content)
        self.assertIn('#comment-', content)
        self.assertIn('/api/notifications/read', content)

    def test_css_responsive(self):
        with open(self.css_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        self.assertIn('@media (max-width: 1440px)', content)
        self.assertIn('@media (max-width: 768px)', content)
        self.assertIn('@media (max-width: 375px)', content)
        self.assertIn('@media (max-width: 320px)', content)

    def test_invariants(self):
        def check_no_emojis(text):
            # A simple regex for many emojis, or just check string
            emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]', flags=re.UNICODE)
            self.assertFalse(emoji_pattern.search(text), "Found emoji")

        def check_no_em_dash(text):
            self.assertNotIn(chr(0x2014), text, "Found em dash")

        def check_no_cdn(text):
            self.assertNotIn('http://', text, "Found external URL")
            # except maybe w3.org in SVGs, but we don't have SVGs in CSS/JS
            if 'css' in text:
                self.assertNotIn('https://', text, "Found external URL")

        with open(self.css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()
            check_no_emojis(css_content)
            check_no_em_dash(css_content)
            check_no_cdn(css_content)

        with open(self.js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()
            check_no_emojis(js_content)
            check_no_em_dash(js_content)
            
if __name__ == '__main__':
    unittest.main()
