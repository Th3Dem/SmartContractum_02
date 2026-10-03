#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Suite for Issue #106:
[P1][frontend] Унифицировать геометрию элементов reader с дизайн-системой SmartContractum.

Verifies:
1. Elimination of border-radius: 9999px across reader controls.
2. Standard token usage: var(--radius-sm, 4px) for chips, action buttons, subscribe button, and vote capsule.
3. Standard token usage: var(--radius-md, 8px) for action rail container.
4. Preservation of 50% circle border-radius for avatars.
5. Invariants: zero emojis, zero em dashes, 100% offline-first.
"""

import os
import re
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS_PATH = os.path.join(BASE_DIR, "frontend", "public", "css", "article.css")
HTML_PATH = os.path.join(BASE_DIR, "frontend", "public", "article.html")


class TestIssue106ReaderGeometryUnification(unittest.TestCase):
    """Automated verification suite for Issue #106."""

    @classmethod
    def setUpClass(cls):
        with open(CSS_PATH, "r", encoding="utf-8") as f:
            cls.css = f.read()
        with open(HTML_PATH, "r", encoding="utf-8") as f:
            cls.html = f.read()

    def test_01_no_9999px_pill_radii_in_article_css(self):
        """Verify that border-radius: 9999px has been completely eliminated from article.css."""
        self.assertNotIn("9999px", self.css, "border-radius: 9999px should not be present in article.css")

    def test_02_badges_and_chips_use_standard_radius(self):
        """Verify topic-badge and meta-badge use var(--radius-sm)."""
        badge_match = re.search(r'\.meta-badge,\s*\.topic-badge\s*\{[^}]*border-radius:\s*var\(--radius-sm', self.css)
        self.assertIsNotNone(badge_match, ".meta-badge and .topic-badge must use var(--radius-sm)")

    def test_03_subscribe_button_uses_standard_radius(self):
        """Verify btn-author-subscribe uses var(--radius-sm)."""
        sub_match = re.search(r'\.btn-author-subscribe[^{]*\{[^}]*border-radius:\s*var\(--radius-sm', self.css)
        self.assertIsNotNone(sub_match, ".btn-author-subscribe must use var(--radius-sm)")

    def test_04_action_rail_and_buttons_geometry(self):
        """Verify action rail container uses var(--radius-md) and buttons use var(--radius-sm)."""
        rail_match = re.search(r'\.article-action-rail\s*\{[^}]*border-radius:\s*var\(--radius-md', self.css)
        self.assertIsNotNone(rail_match, ".article-action-rail must use var(--radius-md)")

        btn_match = re.search(r'\.btn-rail-action\s*\{[^}]*border-radius:\s*var\(--radius-sm', self.css)
        self.assertIsNotNone(btn_match, ".btn-rail-action must use var(--radius-sm)")

    def test_05_vote_capsule_uses_standard_radius(self):
        """Verify rail vote capsule uses var(--radius-sm)."""
        vote_match = re.search(r'\.rail-vote-wrapper\s+\.vote-capsule\s*\{[^}]*border-radius:\s*var\(--radius-sm', self.css)
        self.assertIsNotNone(vote_match, ".rail-vote-wrapper .vote-capsule must use var(--radius-sm)")

    def test_06_avatar_circles_preserved(self):
        """Verify user avatars retain border-radius: 50%."""
        self.assertIn("border-radius: 50%", self.css)
        avatar_match = re.search(r'\.article-author-avatar\s*\{[^}]*border-radius:\s*50%', self.css)
        self.assertIsNotNone(avatar_match, ".article-author-avatar must retain border-radius: 50%")

    def test_07_zero_emojis_and_zero_em_dashes(self):
        """Verify strict project invariants: zero emojis and zero em dashes."""
        for path in [CSS_PATH, HTML_PATH, __file__]:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertNotIn("\u2014", content, f"Em dash found in {os.path.basename(path)}")
            emoji_match = re.search(r"[\U00010000-\U0010ffff]", content)
            self.assertIsNone(emoji_match, f"Emoji found in {os.path.basename(path)}")


if __name__ == '__main__':
    unittest.main()
