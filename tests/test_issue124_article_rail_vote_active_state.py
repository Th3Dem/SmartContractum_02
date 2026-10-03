"""
Tests for Issue #124: Article Rating localized active border and glow around selected arrow in Action Rail.

Verifies:
1. Upvote active state has a localized U-inverted (top, upper-left, upper-right) border with height limited to arrow area.
2. Downvote active state has a localized U-shape (bottom, lower-left, lower-right) border with height limited to arrow area.
3. Glow radial gradients are centered behind the respective arrows (top 13px / bottom calc(100% - 13px)), not behind the score.
4. Action Rail vote control remains a unified single component without splitting into separate button borders.
5. Ratings in Feed cards and Comments remain untouched and isolated in theme.css.
6. Zero emojis and zero em dashes across modified files.
"""

import os
import re
import unittest


class TestIssue124ArticleRailVoteActiveState(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.css_dir = os.path.join(cls.root_dir, "frontend", "public", "css")

        with open(os.path.join(cls.css_dir, "article.css"), "r", encoding="utf-8") as f:
            cls.article_css = f.read()

        with open(os.path.join(cls.css_dir, "theme.css"), "r", encoding="utf-8") as f:
            cls.theme_css = f.read()

    def test_rail_vote_wrapper_has_localized_upvote_border(self):
        """Verify Upvote active state is localized to the top and upper sides only."""
        # Upvote border rule exists
        self.assertIn('.rail-vote-wrapper .vote-capsule.has-voted-up::after', self.article_css)

        # Limited height (does not span full capsule)
        self.assertIn('height: 25px;', self.article_css)

        # Border localized: top, left, right, but bottom none
        self.assertIn('border-top: 1.5px solid var(--vote-up-color', self.article_css)
        self.assertIn('border-left: 1.5px solid var(--vote-up-color', self.article_css)
        self.assertIn('border-right: 1.5px solid var(--vote-up-color', self.article_css)
        self.assertIn('border-bottom: none !important;', self.article_css)

        # Upper radius preserved, lower radius 0
        self.assertIn('border-top-left-radius: var(--radius-sm', self.article_css)
        self.assertIn('border-top-right-radius: var(--radius-sm', self.article_css)
        self.assertIn('border-bottom-left-radius: 0;', self.article_css)
        self.assertIn('border-bottom-right-radius: 0;', self.article_css)

    def test_rail_vote_wrapper_has_localized_downvote_border(self):
        """Verify Downvote active state is localized to the bottom and lower sides only."""
        # Downvote border rule exists
        self.assertIn('.rail-vote-wrapper .vote-capsule.has-voted-down::after', self.article_css)

        # Border localized: bottom, left, right, but top none
        self.assertIn('border-bottom: 1.5px solid var(--vote-down-color', self.article_css)
        self.assertIn('border-left: 1.5px solid var(--vote-down-color', self.article_css)
        self.assertIn('border-right: 1.5px solid var(--vote-down-color', self.article_css)
        self.assertIn('border-top: none !important;', self.article_css)

        # Lower radius preserved, upper radius 0
        self.assertIn('border-bottom-left-radius: var(--radius-sm', self.article_css)
        self.assertIn('border-bottom-right-radius: var(--radius-sm', self.article_css)
        self.assertIn('border-top-left-radius: 0;', self.article_css)
        self.assertIn('border-top-right-radius: 0;', self.article_css)

    def test_rail_vote_glow_centered_behind_arrows_not_score(self):
        """Verify glow centers are directly behind Up/Down arrows and fade towards score."""
        # Upvote glow at top 13px (Up arrow position)
        self.assertIn('.rail-vote-wrapper .vote-capsule.has-voted-up::before', self.article_css)
        self.assertIn('radial-gradient(circle 24px at 50% 13px', self.article_css)

        # Downvote glow at bottom calc(100% - 13px) (Down arrow position)
        self.assertIn('.rail-vote-wrapper .vote-capsule.has-voted-down::before', self.article_css)
        self.assertIn('radial-gradient(circle 24px at 50% calc(100% - 13px)', self.article_css)

        # Dark theme overrides present
        self.assertIn('[data-theme="dark"] .rail-vote-wrapper .vote-capsule.has-voted-up::before', self.article_css)
        self.assertIn('[data-theme="dark"] .rail-vote-wrapper .vote-capsule.has-voted-down::before', self.article_css)

    def test_rail_vote_container_remains_unified_component(self):
        """Verify vote control is a single vertical container without splitting into separate buttons."""
        self.assertIn('.rail-vote-wrapper .vote-capsule {', self.article_css)
        self.assertIn('display: flex;', self.article_css)
        self.assertIn('flex-direction: column;', self.article_css)
        self.assertIn('border: 1px solid var(--border-color);', self.article_css)
        self.assertIn('border-radius: var(--radius-sm', self.article_css)

    def test_feed_and_comment_votes_unaffected(self):
        """Verify feed and comment rating styles in theme.css remain intact."""
        self.assertIn('.card-footer-left .vote-capsule', self.theme_css)
        self.assertIn('.comment-vote-row .vote-capsule', self.theme_css)
        self.assertIn('.vote-capsule.has-voted-up::before', self.theme_css)
        self.assertIn('.vote-capsule.has-voted-down::before', self.theme_css)

    def test_cleanliness_zero_emojis_and_em_dashes(self):
        """Verify zero emojis and zero em dashes in article.css and this test file."""
        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]", flags=re.UNICODE)
        self.assertFalse("\u2014" in self.article_css, "Em dash found in article.css")
        self.assertEqual(len(emoji_pattern.findall(self.article_css)), 0, "Emoji found in article.css")

        with open(__file__, "r", encoding="utf-8") as f:
            test_content = f.read()
        self.assertFalse("\u2014" in test_content, "Em dash found in test file")
        self.assertEqual(len(emoji_pattern.findall(test_content)), 0, "Emoji found in test file")


if __name__ == "__main__":
    unittest.main()
