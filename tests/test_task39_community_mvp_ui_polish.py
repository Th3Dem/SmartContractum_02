"""
tests/test_task39_community_mvp_ui_polish.py

Task 39: UI/UX Community MVP Polish & Two-User End-to-End QA Flow
100% Offline-First, Onest font, Zero emojis, strict regression validation.
"""

import unittest
import urllib.request
import urllib.parse
import json
import os
import re
import tempfile
import threading
import time
import shutil
import sqlite3

import server
from server import create_server, init_db
from tests.fixtures import seed_data
from tests.backend_source import BACKEND_FILES, backend_source_file


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestTask39CommunityMVP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_task39.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path)
        conn.close()

        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR)
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.1)

        # Cache file contents
        with open(os.path.join(FRONTEND_DIR, "feed.html"), "r", encoding="utf-8") as f:
            cls.feed_html = f.read()
        with open(os.path.join(FRONTEND_DIR, "css", "feed.css"), "r", encoding="utf-8") as f:
            cls.feed_css = f.read()
        with open(os.path.join(FRONTEND_DIR, "css", "theme.css"), "r", encoding="utf-8") as f:
            cls.theme_css = f.read()
        with open(os.path.join(FRONTEND_DIR, "js", "card.js"), "r", encoding="utf-8") as f:
            cls.card_js = f.read()
        with open(os.path.join(FRONTEND_DIR, "js", "feed.js"), "r", encoding="utf-8") as f:
            cls.feed_js = f.read()
        with open(os.path.join(FRONTEND_DIR, "js", "article.js"), "r", encoding="utf-8") as f:
            cls.article_js = f.read()
        with backend_source_file() as f:
            cls.server_py = f.read()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.httpd.shutdown()
            cls.httpd.server_close()
        except Exception:
            pass
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def _login(self, user_id, user_name):
        req = urllib.request.Request(
            f"{self.base_url}/api/auth/login",
            data=json.dumps({"userId": user_id, "name": user_name}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            cookie = resp.headers.get("Set-Cookie")
            return data, cookie

    def _get_json(self, path, cookie=None):
        headers = {}
        if cookie:
            headers["Cookie"] = cookie
        req = urllib.request.Request(f"{self.base_url}{path}", headers=headers)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data

    def _post_json(self, path, payload, cookie=None):
        headers = {"Content-Type": "application/json"}
        if cookie:
            headers["Cookie"] = cookie
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers
        )
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return resp.status, data
        except urllib.error.HTTPError as e:
            data = json.loads(e.read().decode("utf-8"))
            return e.code, data

    # -------------------------------------------------------------------------
    # 1. Subnav Layout and Sequential Grouping
    # -------------------------------------------------------------------------
    def test_subnav_left_aligned_and_no_space_between(self):
        """Verify .feed-subnav-container is flex-start left-aligned without space-between."""
        self.assertIn('.feed-subnav-container', self.feed_css)
        self.assertIn('justify-content: flex-start', self.feed_css)
        self.assertIn('margin-right: 8px', self.feed_css)

        # Check sequential order in HTML: Создать + -> Все публикации -> Вопросы -> Подписки -> Сохраненные
        pos_create = self.feed_html.find('id="btnCreateDropdown"')
        pos_all = self.feed_html.find('id="tabFeedAll"')
        pos_questions = self.feed_html.find('id="tabFeedQuestions"')
        pos_subs = self.feed_html.find('id="tabFeedSubscriptions"')
        pos_saved = self.feed_html.find('id="feedSavedTab"')

        self.assertTrue(pos_create < pos_all < pos_questions < pos_subs < pos_saved,
                        "Subnav items must be ordered sequentially from left to right")

        # Saved count badge preserved
        self.assertIn('id="feedSavedCount"', self.feed_html)

    def test_subnav_mobile_horizontal_scroll_no_overflow(self):
        """Verify mobile subnav container allows horizontal scrolling with nowrap flex."""
        self.assertIn('@media (max-width: 768px)', self.feed_css)
        self.assertIn('flex-direction: row', self.feed_css)
        self.assertIn('overflow-x: auto', self.feed_css)
        self.assertIn('flex-wrap: nowrap', self.feed_css)

    # -------------------------------------------------------------------------
    # 2. Welcome Banner Deduplication and Persistence
    # -------------------------------------------------------------------------
    def test_welcome_banner_exact_text_and_no_false_promises(self):
        """Verify welcome banner contains approved text and no unverified claims."""
        self.assertIn('Сообщество российских коммерческих смарт-контрактов', self.feed_html)
        self.assertIn('Задавайте вопросы, делитесь опытом разработки и применения смарт-контрактов, находите коллег.', self.feed_html)
        # Verify false promises are removed
        banner_match = re.search(r'id="feedWelcomeBanner"[^>]*>(.*?)</div>\s*<button', self.feed_html, re.DOTALL)
        self.assertIsNotNone(banner_match)
        banner_text = banner_match.group(1)
        self.assertNotIn('ответов экспертов', banner_text)
        self.assertNotIn('проверенных специалистов', banner_text)

    def test_welcome_banner_server_settings_persistence(self):
        """Verify authenticated user can persist welcome banner dismissal to /api/user/feed-settings."""
        _, cookie = self._login("user_qa_welcome", "Тестовый Пользователь")

        # GET initial settings - welcomeDismissed should be False
        status, data = self._get_json("/api/user/feed-settings", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertFalse(data.get("settings", {}).get("welcomeDismissed"))

        # POST toggle welcomeDismissed = True
        status, data = self._post_json("/api/user/feed-settings", {"welcomeDismissed": True}, cookie=cookie)
        self.assertEqual(status, 200)
        self.assertTrue(data.get("welcomeDismissed"))

        # GET settings again - welcomeDismissed should now be True
        status, data = self._get_json("/api/user/feed-settings", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertTrue(data.get("settings", {}).get("welcomeDismissed"))

    # -------------------------------------------------------------------------
    # 3. Right Block «Нужна помощь?»
    # -------------------------------------------------------------------------
    def test_right_block_cta_content_and_links(self):
        """Verify right block CTA has 'Нужна помощь?' heading, exact copy, and opens editor modes."""
        cta_match = re.search(r'id="widgetCommunityCta"[^>]*>(.*?)</div>\s*<!-- Widget:', self.feed_html, re.DOTALL)
        self.assertIsNotNone(cta_match)
        cta_content = cta_match.group(1)

        self.assertIn('Нужна помощь?', cta_content)
        self.assertIn('Опишите задачу — обсудим ее вместе.', cta_content)
        self.assertIn('editor.html?type=question', cta_content)
        self.assertIn('editor.html', cta_content)
        self.assertIn('Задать вопрос', cta_content)
        self.assertIn('Написать публикацию', cta_content)

    # -------------------------------------------------------------------------
    # 4. Question Badges and Action Routing
    # -------------------------------------------------------------------------
    def test_question_badge_rendered_and_no_faq(self):
        """Verify questions render explicit 'Вопрос' badge and suppress format badge (FAQ)."""
        self.assertIn('.meta-badge.question-badge', self.feed_css)
        self.assertIn('Вопрос', self.card_js)

        # Seed data questions art-24, art-29, art-30 must not have format 'faq'
        for art in seed_data.ARTICLES_DATA:
            mat_type = art.get("materialType")
            if mat_type == "question":
                self.assertNotEqual(art.get("format"), "faq", f"Question {art['id']} must not have format: faq")

        # Card.js routes 'Ответить' to #comment-form
        self.assertIn('#comment-form', self.card_js)
        self.assertIn('Ответить', self.card_js)

    def test_article_page_handles_comment_form_hash(self):
        """Verify article.js smoothly scrolls to comment form and prompts guest with auth modal."""
        self.assertIn('#comment-form', self.article_js)
        self.assertIn('commentGuestPrompt', self.article_js)
        self.assertIn('openAuthModal', self.article_js)

    # -------------------------------------------------------------------------
    # 5. Author Name Styling Reset
    # -------------------------------------------------------------------------
    def test_author_name_no_dark_borders_and_accessible_focus(self):
        """Verify .btn-author-profile has no border/background and retains :focus-visible."""
        self.assertIn('.btn-author-profile', self.feed_css)
        self.assertIn('border: none', self.feed_css)
        self.assertIn('background: transparent', self.feed_css)
        self.assertIn('.btn-author-profile:focus-visible', self.feed_css)
        self.assertIn('outline: 2px solid', self.feed_css)

        # Also in theme.css for universality
        self.assertIn('.btn-author-profile', self.theme_css)
        self.assertIn('.btn-author-profile:focus-visible', self.theme_css)

    # -------------------------------------------------------------------------
    # 6. Topics Widget Simplification
    # -------------------------------------------------------------------------
    def test_topics_widget_single_transition_and_count(self):
        """Verify topics widget has subtitle 'Количество публикаций' and single transition button with count."""
        self.assertIn('Количество публикаций', self.feed_html)
        self.assertIn('id="widgetTopicsTotalCount"', self.feed_html)
        self.assertIn('btnShowAllTopics', self.feed_html)
        self.assertIn('Все темы ·', self.feed_html)

        # Feed.js updates total count dynamically
        self.assertIn('widgetTopicsTotalCount', self.feed_js)

    # -------------------------------------------------------------------------
    # 7. Unanswered Questions Sidebar Widget
    # -------------------------------------------------------------------------
    def test_unanswered_questions_widget_structure_and_order(self):
        """Verify unanswered questions widget is placed after CTA and has link to all unanswered."""
        pos_cta = self.feed_html.find('id="widgetCommunityCta"')
        pos_unans = self.feed_html.find('id="widgetUnansweredQuestions"')
        pos_topics = self.feed_html.find('class="feed-widget-card widget-topics-card"')
        pos_about = self.feed_html.find('class="feed-widget-card widget-about-card"')

        self.assertTrue(pos_cta < pos_unans < pos_topics < pos_about,
                        "Sidebar widgets must be ordered: 1. Нужна помощь -> 2. Вопросы без ответа -> 3. Темы -> 4. О платформе")

        self.assertIn('id="linkAllUnanswered"', self.feed_html)
        self.assertIn('Все вопросы без ответа →', self.feed_html)

    # -------------------------------------------------------------------------
    # 8. End-to-End Two-User Full Scenario
    # -------------------------------------------------------------------------
    def test_two_user_full_question_answer_solution_scenario(self):
        """
        Full 2-user scenario:
        1. User A publishes a Question.
        2. Question appears in general feed and 'questions' tab as 1 record.
        3. User B views it and answers.
        4. User A receives in-app notification of new_answer.
        5. User A accepts User B's answer as solution.
        6. User B receives notification of solution_accepted.
        7. User B cannot accept solutions for User A (enforced 403 Forbidden).
        8. User A can unmark the solution.
        """
        user_a_id = "test_user_alice_39"
        user_b_id = "test_user_bob_39"

        _, cookie_a = self._login(user_a_id, "Алиса Инженер")
        _, cookie_b = self._login(user_b_id, "Боб Разработчик")

        # 1. User A publishes question
        question_payload = {
            "draftId": "draft_t39_alice",
            "authorId": user_a_id,
            "title": "Как реализовать атомарный своп между Fabric и Masterchain без оракулов?",
            "html": "<p>Интересует надежный шаблон HTLC для обмена токенами между реестрами без централизованного шлюза.</p>",
            "publicationSettings": {
                "author": "Алиса Инженер",
                "authorRole": "Blockchain Architect",
                "targetAudience": "smart-contracts-dev",
                "materialType": "question",
                "topics": ["pksc-architecture", "integrations-and-api"],
                "keywords": ["HTLC", "AtomicSwap", "Fabric", "Masterchain"],
                "format": "none",
                "complexity": "hard",
                "description": "Интересует надежный архитектурный шаблон HTLC для обмена токенами между распределенными реестрами без шлюза."
            }
        }
        status, submit_res = self._post_json("/api/moderation/submit", question_payload, cookie=cookie_a)
        self.assertEqual(status, 200)
        self.assertTrue(submit_res.get("success"))
        question_id = submit_res.get("submissionId")
        self.assertTrue(bool(question_id))

        # Approve question so it enters published stream
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute("UPDATE moderation_submissions SET status = 'approved' WHERE id = ?", (question_id,))

        # 2. Appears in general feed and in 'questions' tab as 1 record
        status, q_tab_data = self._get_json(f"/api/articles?materialType=question", cookie=cookie_b)
        self.assertEqual(status, 200)
        matched = [a for a in q_tab_data.get("articles", []) if a["id"] == question_id]
        self.assertEqual(len(matched), 1, "Question must appear as exactly 1 record in questions tab")
        self.assertEqual(matched[0]["answersCount"], 0)
        self.assertFalse(matched[0]["hasSolution"])

        # 3. User B answers the question
        ans_payload = {
            "content": "Для HTLC между Hyperledger Fabric и Masterchain используйте хэш-образ SHA-256 с таймлоком в блоках. Реализация доступна в открытом репозитории.",
            "commentType": "answer"
        }
        status, ans_res = self._post_json(f"/api/articles/{question_id}/comments", ans_payload, cookie=cookie_b)
        self.assertIn(status, (200, 201))
        self.assertTrue(ans_res.get("success"))
        answer_id = ans_res.get("comment", {}).get("id")
        self.assertTrue(bool(answer_id))

        # 4. User A receives in-app notification of new_answer
        status, notif_a = self._get_json("/api/notifications", cookie=cookie_a)
        self.assertEqual(status, 200)
        user_a_notifs = notif_a.get("notifications", [])
        ans_notifs = [n for n in user_a_notifs if (n.get("articleId") == question_id or n.get("article_id") == question_id) and n.get("type") == "new_answer"]
        self.assertTrue(len(ans_notifs) >= 1, "User A must receive a new_answer notification")
        self.assertEqual(ans_notifs[0].get("actorId") or ans_notifs[0].get("actor_id"), user_b_id)

        # 5. User B tries to accept own answer as solution on User A's question -> 403 Forbidden!
        status, err_res = self._post_json(f"/api/articles/{question_id}/comments/{answer_id}/solution", {}, cookie=cookie_b)
        self.assertEqual(status, 403, "User B must not be permitted to accept solution on User A's question")
        self.assertIn("автор вопроса", err_res.get("error", "").lower())

        # 6. User A accepts User B's answer as solution
        status, sol_res = self._post_json(f"/api/articles/{question_id}/comments/{answer_id}/solution", {}, cookie=cookie_a)
        self.assertEqual(status, 200)
        self.assertTrue(sol_res.get("isSolution"))

        # Verify question card status updated
        status, art_detail = self._get_json(f"/api/articles/{question_id}")
        self.assertEqual(status, 200)
        self.assertTrue(art_detail.get("article", {}).get("hasSolution"))

        # 7. User B receives notification of solution_accepted
        status, notif_b = self._get_json("/api/notifications", cookie=cookie_b)
        self.assertEqual(status, 200)
        user_b_notifs = notif_b.get("notifications", [])
        sol_notifs = [n for n in user_b_notifs if (n.get("articleId") == question_id or n.get("article_id") == question_id) and n.get("type") == "solution_accepted"]
        self.assertTrue(len(sol_notifs) >= 1, "User B must receive a solution_accepted notification")

        # 8. User A unmarks the solution
        status, unsol_res = self._post_json(f"/api/articles/{question_id}/comments/{answer_id}/solution", {}, cookie=cookie_a)
        self.assertEqual(status, 200)
        self.assertFalse(unsol_res.get("isSolution"))


if __name__ == '__main__':
    unittest.main()
