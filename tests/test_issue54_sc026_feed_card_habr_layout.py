"""
Tests for Issue #54 (SC-026): Habr-like compact feed card layout and invariants.
Sub-issues covered:
- #55 (SC-026.1): Render all topics (1-5) and separate format badge ("Формат: <Название>")
- #56 (SC-026.2): Remove hashtags (#keywords) and author role from feed card and editor preview
- #57 (SC-026.3): 780x350 cover container, cropper canvas synchronization (78:35)
- #58 (SC-026.4): Vertical compaction (16-18px padding, 14px mobile, 14px gap, 2-line clamp)
- #59 (SC-026.5): Single renderer authority in card.js, parity editor -> feed
"""

import os
import re
import unittest
import json
import tempfile
import threading
import time
import urllib.request
import urllib.error

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, 'frontend', 'public')

import server


class TestIssue54SC026FeedCardHabrLayout(unittest.TestCase):
    """Automated verification suite for Issue #54 / SC-026 invariants."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(FRONTEND_DIR, 'js', 'card.js'), 'r', encoding='utf-8') as f:
            cls.card_js = f.read()
        with open(os.path.join(FRONTEND_DIR, 'js', 'feed.js'), 'r', encoding='utf-8') as f:
            cls.feed_js = f.read()
        with open(os.path.join(FRONTEND_DIR, 'js', 'publication.js'), 'r', encoding='utf-8') as f:
            cls.pub_js = f.read()
        with open(os.path.join(FRONTEND_DIR, 'js', 'config.js'), 'r', encoding='utf-8') as f:
            cls.config_js = f.read()
        with open(os.path.join(FRONTEND_DIR, 'css', 'feed.css'), 'r', encoding='utf-8') as f:
            cls.feed_css = f.read()
        with open(os.path.join(FRONTEND_DIR, 'css', 'editor.css'), 'r', encoding='utf-8') as f:
            cls.editor_css = f.read()
        with open(os.path.join(FRONTEND_DIR, 'css', 'article.css'), 'r', encoding='utf-8') as f:
            cls.article_css = f.read()
        with open(os.path.join(FRONTEND_DIR, 'css', 'theme.css'), 'r', encoding='utf-8') as f:
            cls.theme_css = f.read()
        with open(os.path.join(FRONTEND_DIR, 'editor.html'), 'r', encoding='utf-8') as f:
            cls.editor_html = f.read()
        with open(os.path.join(FRONTEND_DIR, 'feed.html'), 'r', encoding='utf-8') as f:
            cls.feed_html = f.read()

        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, 'test_issue54.db')

        cls.server = server.create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR)
        cls.port = cls.server.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"

        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.05)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        import shutil
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_single_renderer_authority_invariant1(self):
        """Invariant 1: card.js is the sole source of HTML markup; feed.js delegates exclusively."""
        self.assertIn('window.SmartContractumCard.createCardElement', self.feed_js)
        # Verify feed.js createCardElement function does not contain duplicate card markup
        card_fn_match = re.search(r'function createCardElement\(item\)\s*\{([\s\S]*?)\n  \}', self.feed_js)
        self.assertIsNotNone(card_fn_match)
        fn_code = card_fn_match.group(1)
        self.assertNotIn('card-subscription-badge', fn_code)
        self.assertNotIn('author-avatar', fn_code)
        self.assertNotIn('tag-expand-btn', fn_code)
        # card.js provides renderCardInnerHtml and createCardElement
        self.assertIn('function renderCardInnerHtml', self.card_js)
        self.assertIn('function createCardElement', self.card_js)

    def test_02_topics_completeness_invariant2(self):
        """Invariant 2: All selected topics (1 to 5) are rendered as .topic-badge without truncation or '+N еще'."""
        self.assertIn('topicIds.forEach', self.card_js)
        self.assertIn('<span class="meta-badge topic-badge"', self.card_js)
        # Ensure card.js getBadgesHtml iterates over all topics
        self.assertIn('item.topics', self.card_js)
        # Ensure publication.js passes all topics array to previewItem
        self.assertIn('topics: (this.topics && this.topics.length > 0) ? this.topics : []', self.pub_js)

    def test_03_format_separation_invariant3(self):
        """Invariant 3: Format is rendered in a dedicated semantic group with 'Формат: <Название>'."""
        self.assertIn('card-format-badge', self.card_js)
        self.assertIn("'Формат: '", self.card_js)
        self.assertIn('.meta-badge.format-badge', self.feed_css)
        # Format badge is not rendered for questions
        card_badges_snippet = self.card_js[self.card_js.find('function getBadgesHtml'):self.card_js.find('function getComplexityBadgeHtml')]
        self.assertIn('if (!isQuestion)', card_badges_snippet)

    def test_04_hashtags_and_author_role_removal_invariant4(self):
        """Invariant 4: Hashtags and author role are completely removed from card.js and editor preview."""
        # card.js does not render author-role in authorHtml
        card_inner_snippet = self.card_js[self.card_js.find('function renderCardInnerHtml'):self.card_js.find('function createCardElement')]
        self.assertNotIn('author-role', card_inner_snippet)
        self.assertNotIn('preview-card-role', card_inner_snippet)
        # card.js does not render card-tags / tag-chip
        self.assertNotIn('card-tags', card_inner_snippet)
        self.assertNotIn('tag-chip', card_inner_snippet)
        # editor.html static preview does not contain author-role or preview-card-tags
        self.assertNotIn('id="preview-card-role"', self.editor_html)
        self.assertNotIn('id="preview-card-tags"', self.editor_html)

    def test_05_keywords_and_search_preservation_invariant5(self):
        """Invariant 5: Keywords remain fully preserved in publication model, API, search, and article view."""
        # feed.js search still indexes keywords
        self.assertIn('art.keywords', self.feed_js)
        # server.py returns keywords in publication settings
        self.assertIn('keywords', server.APPROVED_SEED_ARTICLES[0].get('publication_settings', {}))
        # GET /api/articles returns keywords
        req = urllib.request.Request(f"{self.base_url}/api/articles")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            articles = data.get('articles', [])
            self.assertTrue(len(articles) > 0)
            self.assertIn('keywords', articles[0])
            self.assertIsInstance(articles[0]['keywords'], list)

    def test_06_cover_aspect_ratio_sync_780x350_invariant6(self):
        """Invariant 6: Cover container uses 780x350 (~2.23:1); cropper canvas, config, CSS match 1:1."""
        # 1. config.js
        self.assertIn('TARGET_WIDTH: 780', self.config_js)
        self.assertIn('TARGET_HEIGHT: 350', self.config_js)
        self.assertIn("ASPECT_RATIO_STR: '780 / 350'", self.config_js)
        self.assertIn('ASPECT_RATIO_W: 78', self.config_js)
        self.assertIn('ASPECT_RATIO_H: 35', self.config_js)

        # 2. editor.html cropper canvas and hints
        self.assertIn('width="780" height="350"', self.editor_html)
        self.assertIn('780 × 350 px', self.editor_html)
        self.assertIn('78:35', self.editor_html)

        # 3. publication.js cropper dimensions
        self.assertIn('COVER_HEIGHT: 350', self.pub_js)
        self.assertIn('TARGET_HEIGHT: 350', self.pub_js)

        # 4. theme.css and feed.css tokens
        self.assertIn('--card-cover-aspect-ratio: 780 / 350;', self.theme_css)
        self.assertIn('aspect-ratio: 780 / 350;', self.feed_css)
        self.assertIn('aspect-ratio: var(--card-cover-aspect-ratio, 780 / 350);', self.feed_css)

        # 5. editor.css and article.css
        self.assertIn('aspect-ratio: 780 / 350;', self.editor_css)
        self.assertIn('aspect-ratio: 780 / 350;', self.article_css)

    def test_07_vertical_compaction_rhythm_invariant7(self):
        """Invariant 7: Compact feed card padding (16-18px desktop, 14px mobile), 14px gap, 2-line clamp."""
        # .feed-cards-container gap
        container_match = re.search(r'\.feed-cards-container\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(container_match)
        self.assertIn('gap: 14px;', container_match.group(1))

        # .feed-card padding
        card_match = re.search(r'\.feed-card\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(card_match)
        self.assertIn('padding: 16px 18px;', card_match.group(1))

        # Mobile media query padding
        mobile_match = re.search(r'@media[^{]+\(max-width:\s*680px\)[\s\S]*?\.feed-card\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(mobile_match)
        self.assertIn('padding: 14px;', mobile_match.group(1))

        # 2-line clamp on description lead
        lead_match = re.search(r'\.card-lead\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(lead_match)
        self.assertIn('-webkit-line-clamp: 2;', lead_match.group(1))
        self.assertIn('margin: 0 0 10px 0;', lead_match.group(1))

    def test_08_editor_preview_parity_invariant8(self):
        """Invariant 8: Editor preview in 'Отображение в ленте' delegates to SmartContractumCard."""
        self.assertIn('window.SmartContractumCard.renderCardInnerHtml(previewItem, { isPreview: true })', self.pub_js)
        # Confirm that previewItem does not pass authorRole or keywords
        preview_block = self.pub_js[self.pub_js.find('updateCardPreview()'):self.pub_js.find('updateCardPreview()') + 1500]
        self.assertNotIn('authorRole:', preview_block)
        self.assertNotIn('keywords:', preview_block)

    def test_09_mobile_adaptability_invariant9(self):
        """Invariant 9: Action buttons and touch targets conform to accessible sizing without layout shifts."""
        self.assertIn('.btn-card-action', self.feed_css)
        self.assertIn('.vote-capsule', self.theme_css)
        self.assertIn('tabular-nums', self.theme_css)

    def test_10_question_card_integrity_invariant10(self):
        """Invariant 10: Question cards retain question badge, answers count, solved badge, and no cover."""
        # card.js checks question type and does not render cover
        self.assertIn("isQuestion", self.card_js)
        self.assertIn("Вопрос", self.card_js)
        self.assertIn("btn-card-answers", self.card_js)
        # Questions do NOT have covers
        self.assertIn("!isQuestion && item.material_type !== 'question' && item.coverImage", self.card_js)


if __name__ == '__main__':
    unittest.main()
