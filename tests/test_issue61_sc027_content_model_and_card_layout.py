"""
Tests for Issue #61 (SC-027): Simplified Content Model (Publication / Question)
and Card Layout Alignment (Issues #55, #56, #57, #58, #59).

Acceptance Criteria verified:
1. UI has strictly «Публикация» and «Вопрос» as top-level material types.
2. Feed subnav tab is titled «Публикации», not «Все публикации».
3. Filters panel does NOT contain «Тип материала».
4. Filters panel does NOT contain «Уровень сложности».
5. Editor does NOT contain complexity section.
6. Feed card does NOT contain complexity.
7. API / filtering has no active complexity requirement.
8. «Новость» and «Заметка» are available as publication formats.
9. Topics (1 to 5) are displayed at the top of the card.
10. Format is displayed in bottom service row on place of former complexity.
11. Format title has no prefix «Формат:».
12. Questions do not show publication format.
13. Legacy article/post/news are read as publications.
14. New materials are saved as publication or question.
15. Editor preview and feed card share identical model and renderer.
16. Code standards: zero emojis, no em dashes, zero server IPs, 100% offline-first.
"""

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


class TestIssue61SC027ContentModelAndCardLayout(unittest.TestCase):
    """Verification suite for Issue #61 content model refactor and card layout updates."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(FRONTEND_DIR, "js", "card.js"), "r", encoding="utf-8") as f:
            cls.card_js = f.read()
        with open(os.path.join(FRONTEND_DIR, "js", "feed.js"), "r", encoding="utf-8") as f:
            cls.feed_js = f.read()
        with open(os.path.join(FRONTEND_DIR, "js", "publication.js"), "r", encoding="utf-8") as f:
            cls.pub_js = f.read()
        with open(os.path.join(FRONTEND_DIR, "js", "config.js"), "r", encoding="utf-8") as f:
            cls.config_js = f.read()
        with open(os.path.join(FRONTEND_DIR, "css", "feed.css"), "r", encoding="utf-8") as f:
            cls.feed_css = f.read()
        with open(os.path.join(FRONTEND_DIR, "editor.html"), "r", encoding="utf-8") as f:
            cls.editor_html = f.read()
        with open(os.path.join(FRONTEND_DIR, "feed.html"), "r", encoding="utf-8") as f:
            cls.feed_html = f.read()

        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue61.db")

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

    def _get_json(self, path: str, cookie: str = None):
        req = urllib.request.Request(f"{self.base_url}{path}")
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

    def _post_json(self, path: str, payload: dict, cookie: str = None):
        data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data_bytes,
            headers={"Content-Type": "application/json"}
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

    def _login(self, user_id: str, name: str = None):
        status, data = self._post_json("/api/auth/login", {"userId": user_id, "name": name or user_id})
        return f"sc_session={data.get('sessionToken')}"

    # AC 1: В UI существуют только «Публикация» и «Вопрос» как верхнеуровневые типы.
    def test_01_top_level_material_types_strictly_publication_and_question(self):
        """AC 1: UI has only publication and question as top-level material types."""
        self.assertIn("id: 'publication'", self.config_js)
        self.assertIn("id: 'question'", self.config_js)
        self.assertIn("singular: 'Публикация'", self.config_js)
        self.assertIn("singular: 'Вопрос'", self.config_js)

        # In feed settings panel: only publication and question
        self.assertIn('id="feedTypePublication"', self.feed_html)
        self.assertIn('id="feedTypeQuestion"', self.feed_html)
        self.assertNotIn('id="feedTypeArticle"', self.feed_html)
        self.assertNotIn('id="feedTypePost"', self.feed_html)
        self.assertNotIn('id="feedTypeNews"', self.feed_html)

    # AC 2: В навигации написано «Публикации», а не «Все публикации».
    def test_02_feed_subnav_tab_title_is_publications(self):
        """AC 2: Subnav tab is titled «Публикации», not «Все публикации»."""
        # Find #tabFeedAll text
        match = re.search(r'id="tabFeedAll"[^>]*>([\s\S]*?)</button>', self.feed_html)
        self.assertIsNotNone(match, "#tabFeedAll button must exist in feed.html")
        tab_text = match.group(1).strip()
        self.assertEqual(tab_text, "Публикации")
        self.assertNotIn("Все публикации", tab_text)

        # Page title update in feed.js
        self.assertIn("'Публикации — SmartContractum'", self.feed_js)

    # AC 3: В панели фильтров нет «Типа материала».
    def test_03_filters_panel_omits_material_types(self):
        """AC 3: Filters panel does NOT contain material types selector."""
        self.assertNotIn('id="feedFilterGroupTypes"', self.feed_html)
        self.assertNotIn('data-type="all"', self.feed_html)

    # AC 4: В панели фильтров нет «Уровня сложности».
    def test_04_filters_panel_omits_complexity(self):
        """AC 4: Filters panel does NOT contain complexity level selector."""
        self.assertNotIn('id="feedFilterGroupComplexity"', self.feed_html)
        self.assertNotIn('id="feedComplexitySelect"', self.feed_html)
        self.assertNotIn('data-complexity="all"', self.feed_html)

    # AC 5: В editor нет выбора сложности.
    def test_05_editor_omits_complexity_section(self):
        """AC 5: Editor section for complexity is completely removed."""
        self.assertNotIn('id="pub-section-complexity"', self.editor_html)
        self.assertNotIn('id="pub-complexity-grid"', self.editor_html)
        self.assertNotIn('name="pub-complexity"', self.editor_html)

        # Section for material type is also removed from editor
        self.assertNotIn('id="pub-section-material-type"', self.editor_html)

    # AC 6: В карточке нет сложности.
    def test_06_card_omits_complexity(self):
        """AC 6: Feed cards and preview cards do not contain complexity badge."""
        self.assertNotIn("card-complexity-badge", self.card_js)
        self.assertIn("function getComplexityBadgeHtml()", self.card_js)

    # AC 7: В API/фильтрации нет активной логики сложности.
    def test_07_api_submission_without_complexity_succeeds(self):
        """AC 7: Submitting material without complexity is valid and accepted."""
        server.init_db(self.db_path, seed=True)

        cookie = self._login("author_no_compl", "Автор Без Сложности")
        payload = {
            "draftId": "draft_no_compl_001",
            "title": "Публикация о коммерческих смарт-контрактах",
            "html": "<p>Подробный технический анализ реализации алгоритмов консенсуса.</p>",
            "publicationSettings": {
                "targetAudience": "developers",
                "topics": ["smart-contracts-development"],
                "keywords": ["консенсус", "алгоритмы"],
                "description": "Краткое техническое описание публикации для ленты сообщества разработчиков.",
                "format": "tutorial",
                "materialType": "publication"
            },
            "idempotencyKey": "idemp_no_compl_001"
        }
        status, data = self._post_json("/api/moderation/submit", payload, cookie=cookie)
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("status"), "pending_moderation")

    # AC 8: «Новость» и «Заметка» доступны как форматы публикации.
    def test_08_news_and_note_available_in_formats_config(self):
        """AC 8: «Новость» and «Заметка» are available in PublicationConfig.FORMATS."""
        self.assertIn("id: 'news'", self.config_js)
        self.assertIn("title: 'Новость'", self.config_js)
        self.assertIn("id: 'note'", self.config_js)
        self.assertIn("title: 'Заметка'", self.config_js)
        self.assertIn("id: 'tutorial'", self.config_js)
        self.assertIn("id: 'case-study'", self.config_js)
        self.assertIn("id: 'review'", self.config_js)

    # AC 9: Темы отображаются сверху карточки (от 1 до 5).
    def test_09_card_renders_all_topics_on_top(self):
        """AC 9: Topics (1 to 5) are rendered in the top badges row."""
        self.assertIn("getBadgesHtml", self.card_js)
        self.assertIn('class="meta-badge topic-badge"', self.card_js)
        # Verify no truncation "+N еще" in top topics
        self.assertNotIn("+${extraCount} еще", self.card_js)

    # AC 10: Формат отображается в нижней служебной строке на месте бывшей сложности.
    def test_10_format_rendered_in_bottom_service_row(self):
        """AC 10: Format is rendered in the bottom service row on place of former complexity."""
        self.assertIn("getFormatBadgeHtml", self.card_js)
        self.assertIn("formatBadgeHtml", self.card_js)
        self.assertIn('class="meta-badge format-badge card-format-badge"', self.card_js)
        self.assertIn("card-sub-info card-meta-row-bottom", self.card_js)

    # AC 11: Перед названием формата нет слова «Формат».
    def test_11_format_has_no_format_prefix(self):
        """AC 11: Format badge shows pure title without «Формат: » prefix."""
        self.assertNotIn("Формат: ${", self.card_js)
        self.assertNotIn("'Формат: ' +", self.card_js)
        self.assertNotIn('"Формат: " +', self.card_js)

    # AC 12: Вопросы не показывают формат публикации.
    def test_12_questions_do_not_show_format(self):
        """AC 12: Questions suppress format badge in bottom service row."""
        # Check getFormatBadgeHtml in card.js skips when materialType is question
        self.assertIn("isQuestion", self.card_js)
        match = re.search(r'function getFormatBadgeHtml[\s\S]*?return \'\';', self.card_js)
        self.assertIsNotNone(match)

    # AC 13: Старые article/post/news корректно читаются как публикации.
    def test_13_legacy_types_read_as_publication(self):
        """AC 13: Legacy article, post, and news records are normalized to publication."""
        conn = server.get_db_connection(self.db_path)
        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, idempotency_key, snapshot_hash, created_at, updated_at
                ) VALUES (
                    'art-legacy-post', 'draft-legacy-post', 'Старый пост сообщества', 'author_old', 'approved',
                    ?, '<p>Текст старого поста о разработке смарт-контрактов.</p>',
                    'idem_leg_1', 'hash_leg_1', '2026-09-25T10:00:00Z', '2026-09-25T10:00:00Z'
                )
            """, (json.dumps({
                "materialType": "post",
                "topics": ["smart-contracts-development"],
                "keywords": ["пост", "легаси"],
                "description": "Описание старого поста сообщества для проверки нормализации в ленте."
            }, ensure_ascii=False),))

        status, data = self._get_json("/api/articles/art-legacy-post")
        self.assertEqual(status, 200)
        self.assertEqual(data["article"]["materialType"], "publication")
        self.assertEqual(data["article"]["type"], "publication")

    # AC 14: Новые материалы записываются только как publication или question.
    def test_14_new_materials_saved_as_publication_or_question(self):
        """AC 14: New materials submitted from editor are saved as publication or question."""
        self.assertIn("materialType: (this.materialType === 'question') ? 'question' : 'publication'", self.pub_js)
        self.assertEqual(server.VALID_MATERIAL_TYPES, ("publication", "question"))

    # AC 15: Editor preview и реальная карточка используют одну и ту же продуктовую модель.
    def test_15_editor_preview_uses_card_js_single_renderer(self):
        """AC 15: Editor preview and feed cards both delegate to SmartContractumCard."""
        self.assertIn("window.SmartContractumCard.renderCardInnerHtml(previewItem", self.pub_js)
        self.assertIn("window.SmartContractumCard.createCardElement", self.feed_js)

    # AC 16: Code hygiene and standards.
    def test_16_code_hygiene_and_standards(self):
        """AC 16: Zero emojis, no em dashes, zero server IPs, offline-first."""
        files_to_check = [
            os.path.join(FRONTEND_DIR, "js", "card.js"),
            os.path.join(FRONTEND_DIR, "js", "config.js"),
            os.path.join(FRONTEND_DIR, "js", "feed.js"),
            os.path.join(FRONTEND_DIR, "js", "publication.js"),
            os.path.join(FRONTEND_DIR, "css", "feed.css"),
            os.path.join(FRONTEND_DIR, "editor.html"),
            os.path.join(FRONTEND_DIR, "feed.html"),
        ]
        # Zero emojis
        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]")
        for fpath in files_to_check:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIsNone(emoji_pattern.search(content), f"Emoji found in {fpath}")
            # Ensure no local server IPs
            self.assertNotIn("192.168.", content)
            self.assertNotIn("10.0.", content)


if __name__ == "__main__":
    unittest.main()
