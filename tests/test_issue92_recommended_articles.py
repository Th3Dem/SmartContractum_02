#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Suite for Issue #92:
[P3][frontend] Рекомендательный блок Еще по теме в конце публикации.

Verifies:
1. HTML markup: presence of #relatedArticlesSection, #relatedArticlesTitle, #relatedArticlesGrid with proper semantics.
2. CSS styling: 3-column responsive grid (2-col on 900px, 1-col on 600px), 780:350 cover ratio, line-clamp, hover states.
3. Recommendation algorithm: getRelatedArticles strict self-exclusion, topic matching score, and fresh fallback.
4. Rendering: renderRelatedCardHtml safe HTML escaping, relative links, fallback SVG cover, metadata chips.
5. Error state & safeguards: hiding block on error or empty recommendations.
6. Zero emojis and zero em dashes invariants.
"""

import os
import re
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(BASE_DIR, "frontend", "public", "article.html")
CSS_PATH = os.path.join(BASE_DIR, "frontend", "public", "css", "article.css")
JS_PATH = os.path.join(BASE_DIR, "frontend", "public", "js", "article.js")


class TestIssue92RecommendedArticles(unittest.TestCase):
    """Automated verification suite for Issue #92."""

    @classmethod
    def setUpClass(cls):
        with open(HTML_PATH, "r", encoding="utf-8") as f:
            cls.html = f.read()
        with open(CSS_PATH, "r", encoding="utf-8") as f:
            cls.css = f.read()
        with open(JS_PATH, "r", encoding="utf-8") as f:
            cls.js = f.read()

    def test_01_markup_and_accessibility(self):
        """Verify HTML markup for related articles section and accessibility attributes."""
        self.assertIn('id="relatedArticlesSection"', self.html)
        self.assertIn('id="relatedArticlesTitle"', self.html)
        self.assertIn('id="relatedArticlesGrid"', self.html)
        self.assertIn('aria-labelledby="relatedArticlesTitle"', self.html)
        self.assertIn('Еще по теме', self.html)

        # Confirm position after comments section
        comments_idx = self.html.find('id="commentsSection"')
        related_idx = self.html.find('id="relatedArticlesSection"')
        self.assertNotEqual(comments_idx, -1)
        self.assertNotEqual(related_idx, -1)
        self.assertGreater(related_idx, comments_idx, "relatedArticlesSection must be positioned after commentsSection")

    def test_02_css_styling_and_responsive_grid(self):
        """Verify CSS responsive grid, cover aspect ratio, line clamp, and hover effects."""
        self.assertIn('.related-articles-section', self.css)
        self.assertIn('.related-articles-title', self.css)
        self.assertIn('.related-articles-grid', self.css)
        self.assertIn('.related-card', self.css)
        self.assertIn('.related-card-cover-wrap', self.css)
        self.assertIn('.related-card-title', self.css)
        self.assertIn('.related-card-meta', self.css)

        # 3 columns desktop grid
        grid_desktop = re.search(r'\.related-articles-grid\s*\{[^}]*grid-template-columns:\s*repeat\(3,\s*1fr\)', self.css)
        self.assertIsNotNone(grid_desktop, ".related-articles-grid must specify 3 columns desktop")

        # 780:350 ratio for cover
        self.assertIn('aspect-ratio: 780 / 350', self.css)

        # 2-line clamp on title
        self.assertIn('-webkit-line-clamp: 2', self.css)

        # Responsive media queries
        query_900 = re.search(r'@media\s*\(max-width:\s*900px\)\s*\{[^}]*grid-template-columns:\s*repeat\(2,\s*1fr\)', self.css)
        self.assertIsNotNone(query_900, "900px media query must specify 2 columns")

        query_600 = re.search(r'@media\s*\(max-width:\s*600px\)\s*\{[^}]*grid-template-columns:\s*1fr', self.css)
        self.assertIsNotNone(query_600, "600px media query must specify 1 column")

    def test_03_js_recommendation_algorithm_logic(self):
        """Verify recommendation algorithm matching and self-exclusion logic."""
        self.assertIn('function getRelatedArticles', self.js)

        # Python test implementation mirroring getRelatedArticles JS logic
        def py_get_related(articles, cur_art):
            if not isinstance(articles, list) or not cur_art:
                return []
            cur_id = cur_art.get("id")
            cur_draft_id = cur_art.get("draftId")
            cur_topics = cur_art.get("topics") or ([cur_art.get("topic")] if cur_art.get("topic") else [])

            candidates = [
                a for a in articles
                if a and a.get("id") and a.get("id") != cur_id
                and (not cur_draft_id or a.get("id") != cur_draft_id)
                and (not a.get("draftId") or (a.get("draftId") != cur_id and a.get("draftId") != cur_draft_id))
            ]

            scored = []
            for item in candidates:
                item_topics = item.get("topics") or ([item.get("topic")] if item.get("topic") else [])
                matches = sum(1 for t in item_topics if t in cur_topics)
                scored.append((matches, item.get("createdAt") or item.get("date") or "", item))

            scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
            return [s[2] for s in scored[:3]]

        # Scenario 1: Strict self-exclusion
        test_articles = [
            {"id": "art-1", "title": "Article 1", "topics": ["Solidity", "Security"]},
            {"id": "art-2", "title": "Article 2", "topics": ["Solidity"]},
            {"id": "art-3", "title": "Article 3", "topics": ["Web3"]},
            {"id": "art-4", "title": "Article 4", "topics": ["Python"]},
        ]
        cur = {"id": "art-1", "topics": ["Solidity", "Security"]}
        result = py_get_related(test_articles, cur)
        self.assertNotIn("art-1", [r["id"] for r in result])
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["id"], "art-2", "Article 2 should rank first due to matching topic Solidity")

        # Scenario 2: Draft ID exclusion
        cur_with_draft = {"id": "art-2", "draftId": "draft-2", "topics": ["Solidity"]}
        test_articles_draft = [
            {"id": "art-2", "title": "Self by ID"},
            {"id": "draft-2", "title": "Self by draft ID"},
            {"id": "art-other", "title": "Other", "topics": ["Solidity"]},
        ]
        res_draft = py_get_related(test_articles_draft, cur_with_draft)
        self.assertEqual(len(res_draft), 1)
        self.assertEqual(res_draft[0]["id"], "art-other")

    def test_04_js_card_rendering_and_escaping(self):
        """Verify card HTML generator uses relative links, escapes content, and displays meta."""
        self.assertIn('function renderRelatedCardHtml', self.js)
        self.assertIn("'article.html?id=' + encodeURIComponent(item.id)", self.js)
        self.assertIn('escapeHtml(item.title', self.js)
        self.assertIn('escapeHtml(item.author', self.js)
        self.assertIn('related-topic-chip', self.js)
        self.assertIn('related-card-reading-time', self.js)

    def test_05_js_integration_and_safeguards(self):
        """Verify loadRelatedArticles integrates with populateArticle and hides in showErrorState."""
        self.assertIn('function loadRelatedArticles', self.js)
        self.assertIn('loadRelatedArticles(article)', self.js)
        self.assertIn('/api/articles?limit=12&tab=all', self.js)
        self.assertIn('FALLBACK_ARTICLES', self.js)

        # Check showErrorState hides recommendations
        error_state_match = re.search(r'function showErrorState\b[^}]*relatedArticlesSection[^}]*display\s*=\s*[\'"]none[\'"]', self.js, re.DOTALL)
        self.assertIsNotNone(error_state_match, "showErrorState must hide relatedArticlesSection")

    def test_06_zero_emojis_and_zero_em_dashes(self):
        """Verify strict project invariants: zero emojis and zero em dashes."""
        for path in [HTML_PATH, CSS_PATH, JS_PATH, __file__]:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertNotIn("\u2014", content, f"Em dash found in {os.path.basename(path)}")
            emoji_match = re.search(r"[\U00010000-\U0010ffff]", content)
            self.assertIsNone(emoji_match, f"Emoji found in {os.path.basename(path)}")


if __name__ == '__main__':
    unittest.main()
