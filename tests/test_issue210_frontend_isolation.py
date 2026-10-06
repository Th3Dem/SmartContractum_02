import unittest
import os
import re

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class TestIssue210FrontendIsolation(unittest.TestCase):

    def read_file(self, filename):
        filepath = os.path.join(REPO_ROOT, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()

    def test_user_scoped_keys(self):
        card = self.read_file('frontend/public/js/card.js')
        article = self.read_file('frontend/public/js/article.js')
        feed = self.read_file('frontend/public/js/feed.js')
        profile = self.read_file('frontend/public/js/profile-page.js')

        self.assertIn("sc_bookmarks_' + user.id", card)
        self.assertIn("sc_bookmarks_guest", card)

        self.assertIn("sc_comment_bookmarks_' + user.id", article)
        self.assertIn("sc_comment_bookmarks_guest", article)

        self.assertIn("sc_comment_subscriptions_' + user.id", article)
        self.assertIn("sc_comment_subscriptions_guest", article)

        self.assertIn("sc_bookmarks_guest", feed)

        self.assertIn("sc_comment_bookmarks_' + user.id", profile)

    def test_auth_change_listeners(self):
        article = self.read_file('frontend/public/js/article.js')
        feed = self.read_file('frontend/public/js/feed.js')
        profile = self.read_file('frontend/public/js/profile-page.js')

        self.assertIn("addEventListener('auth:change'", article)
        self.assertIn("_reportedArticleIds.clear()", article)

        self.assertIn("addEventListener('auth:change'", feed)
        self.assertIn("_reportedArticleIds.clear()", feed)

        self.assertIn("addEventListener('auth:change'", profile)
        self.assertIn("_reportedArticleIds.clear()", profile)

    def test_double_click_protection(self):
        card = self.read_file('frontend/public/js/card.js')
        article = self.read_file('frontend/public/js/article.js')

        self.assertIn("dataset.pending === 'true'", card)
        self.assertIn("dataset.pending = 'true'", card)
        self.assertIn("dataset.pending = 'false'", card)

        self.assertIn("dataset.pending === 'true'", article)
        self.assertIn("dataset.pending = 'true'", article)
        self.assertIn("dataset.pending = 'false'", article)

    def test_rollback_on_error(self):
        card = self.read_file('frontend/public/js/card.js')
        # Rollback check
        self.assertIn("countEl.textContent = prevCount", card)
        self.assertIn("updateBookmarkButtonState(btn, wasBookmarked)", card)

    def test_no_emojis_or_em_dashes(self):
        files = [
            'frontend/public/js/card.js',
            'frontend/public/js/article.js',
            'frontend/public/js/feed.js',
            'frontend/public/js/profile-page.js'
        ]
        em_dash = '\u2014'
        emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]', flags=re.UNICODE)

        for filename in files:
            content = self.read_file(filename)
            self.assertNotIn(em_dash, content, f"Em dash found in {filename}")
            self.assertFalse(emoji_pattern.search(content), f"Emoji found in {filename}")

if __name__ == '__main__':
    unittest.main()
