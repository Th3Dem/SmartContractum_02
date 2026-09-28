#!/usr/bin/env python3
"""
tests/test_task38_community_mvp_navigation_questions_and_scenarios.py

Comprehensive test suite for Task 38:
Community MVP Navigation, Questions, and Scenarios:
1. Header Level 1 (#appHeader): No saved tab, unified notifications bell with badge across all 4 HTML files.
2. Subnav Level 2 (#feedSubnavBar): Create dropdown (question & publication), All, Questions, Subscriptions, Saved.
3. Obsolete Tabs Cleanup: No Focus, Top, New, Clubs, Companies, Directions visible in subnav tabs.
4. Stream Toolbar (#feedStreamToolbar): Search in current feed, sorting (newest, popular, discussed), question status pills, filters button.
5. Questions & Answers API:
   - Filtering by tab=questions
   - Status filtering (all, unanswered, solved)
   - Answer search with snippet generation (matchedAnswerSnippet)
   - Community sorting (newest, popular/rating, discussed)
6. Solution Toggle Authorization:
   - Only question author can mark solution (403 for non-author)
   - Marking solution sets is_solution=1 and dispatches notification to answer author
7. Community Widgets & Endpoints:
   - Unanswered questions widget API (/api/questions/unanswered)
   - User profile endpoints (/api/users/<id>/profile, /api/users/me/profile)
   - Notifications API (/api/notifications, /api/notifications/read)
8. Card Differentiation & Editor Scenarios:
   - Questions have no cover container, display solved badge, answers badge
   - Question editor mode (?type=question), prompts, security warning
9. Design Standards:
   - 100% offline-first, strict Onest font, zero emojis
"""

import json
import os
import re
import shutil
import tempfile
import threading
import time
import unittest
import urllib.parse
import urllib.request

import server
from server import (
    create_server,
    init_db,
)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestTask38Base(unittest.TestCase):
    """Base test class for Task 38 with isolated database and dynamic HTTP server."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_task38.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path)
        conn.close()

        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR)
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.1)

        with open(os.path.join(FRONTEND_DIR, "index.html"), "r", encoding="utf-8") as f:
            cls.index_html = f.read()
        with open(os.path.join(FRONTEND_DIR, "feed.html"), "r", encoding="utf-8") as f:
            cls.feed_html = f.read()
        with open(os.path.join(FRONTEND_DIR, "editor.html"), "r", encoding="utf-8") as f:
            cls.editor_html = f.read()
        with open(os.path.join(FRONTEND_DIR, "article.html"), "r", encoding="utf-8") as f:
            cls.article_html = f.read()
        with open(os.path.join(FRONTEND_DIR, "css", "feed.css"), "r", encoding="utf-8") as f:
            cls.feed_css = f.read()
        with open(os.path.join(FRONTEND_DIR, "css", "theme.css"), "r", encoding="utf-8") as f:
            cls.theme_css = f.read()
        with open(os.path.join(FRONTEND_DIR, "js", "feed.js"), "r", encoding="utf-8") as f:
            cls.feed_js = f.read()
        with open(os.path.join(FRONTEND_DIR, "js", "card.js"), "r", encoding="utf-8") as f:
            cls.card_js = f.read()
        with open(os.path.join(FRONTEND_DIR, "js", "publication.js"), "r", encoding="utf-8") as f:
            cls.publication_js = f.read()
        with open(os.path.join(FRONTEND_DIR, "js", "article.js"), "r", encoding="utf-8") as f:
            cls.article_js = f.read()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def _get_json(self, path: str, cookie: str = None):
        safe_path = urllib.parse.quote(path, safe="/:?=&%")
        req = urllib.request.Request(f"{self.base_url}{safe_path}", method="GET")
        if cookie:
            req.add_header("Cookie", cookie)
        try:
            with urllib.request.urlopen(req) as resp:
                body = resp.read().decode("utf-8")
                return resp.status, json.loads(body), resp.headers.get("Set-Cookie")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            try:
                data = json.loads(body)
            except Exception:
                data = {"raw": body}
            return e.code, data, None

    def _post_json(self, path: str, payload: dict, cookie: str = None):
        safe_path = urllib.parse.quote(path, safe="/:?=&%")
        data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(f"{self.base_url}{safe_path}", data=data_bytes, method="POST")
        req.add_header("Content-Type", "application/json")
        if cookie:
            req.add_header("Cookie", cookie)
        try:
            with urllib.request.urlopen(req) as resp:
                body = resp.read().decode("utf-8")
                return resp.status, json.loads(body), resp.headers.get("Set-Cookie")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            try:
                data = json.loads(body)
            except Exception:
                data = {"raw": body}
            return e.code, data, None


class TestTask38HeaderAndSubnav(TestTask38Base):
    """Section 3: Header Level 1 and Subnav Level 2 tests."""

    def test_01_saved_button_removed_from_header_level_1(self):
        """Header Level 1 must not contain #feedSavedTab in any of the 4 pages."""
        for html_content, page_name in [
            (self.feed_html, "feed.html"),
            (self.editor_html, "editor.html"),
            (self.index_html, "index.html"),
            (self.article_html, "article.html"),
        ]:
            header_match = re.search(r'<header[^>]*id=["\']appHeader["\'][^>]*>(.*?)</header>', html_content, re.DOTALL)
            self.assertIsNotNone(header_match, f"appHeader not found in {page_name}")
            header_html = header_match.group(1)
            self.assertNotIn('id="feedSavedTab"', header_html, f"#feedSavedTab found in header of {page_name}")

    def test_02_notifications_bell_in_header_level_1(self):
        """Header Level 1 must contain #headerNotificationsBtn and #headerNotifBadge across all 4 pages."""
        for html_content, page_name in [
            (self.feed_html, "feed.html"),
            (self.editor_html, "editor.html"),
            (self.index_html, "index.html"),
            (self.article_html, "article.html"),
        ]:
            header_match = re.search(r'<header[^>]*id=["\']appHeader["\'][^>]*>(.*?)</header>', html_content, re.DOTALL)
            self.assertIsNotNone(header_match, f"appHeader not found in {page_name}")
            header_html = header_match.group(1)
            self.assertIn('id="headerNotificationsBtn"', header_html, f"#headerNotificationsBtn missing in {page_name}")
            self.assertIn('id="headerNotifBadge"', header_html, f"#headerNotifBadge missing in {page_name}")
            self.assertIn('id="headerNotifPopup"', header_html, f"#headerNotifPopup missing in {page_name}")

    def test_03_subnav_level_2_elements_and_order(self):
        """Subnav Level 2 strictly ordered: Создать + -> Все публикации -> Вопросы -> Подписки -> Сохраненные."""
        subnav_match = re.search(r'<nav[^>]*id=["\']feedSubnavBar["\'][^>]*>(.*?)</nav>', self.feed_html, re.DOTALL)
        self.assertIsNotNone(subnav_match, "#feedSubnavBar missing in feed.html")
        subnav_html = subnav_match.group(1)

        # Elements exist
        self.assertIn('id="btnCreateDropdown"', subnav_html)
        self.assertIn('id="tabFeedAll"', subnav_html)
        self.assertIn('id="tabFeedQuestions"', subnav_html)
        self.assertIn('id="tabFeedSubscriptions"', subnav_html)
        self.assertIn('id="feedSavedTab"', subnav_html)
        self.assertIn('id="feedSavedCount"', subnav_html)

        # Verify dropdown menu options
        self.assertIn('id="btnCreateQuestion"', subnav_html)
        self.assertIn('editor.html?type=question', subnav_html)
        self.assertIn('id="btnCreatePublication"', subnav_html)
        self.assertIn('Задать вопрос', subnav_html)
        self.assertIn('Написать публикацию', subnav_html)

        # Verify strict order
        idx_create = subnav_html.find('id="btnCreateDropdown"')
        idx_all = subnav_html.find('id="tabFeedAll"')
        idx_questions = subnav_html.find('id="tabFeedQuestions"')
        idx_subs = subnav_html.find('id="tabFeedSubscriptions"')
        idx_saved = subnav_html.find('id="feedSavedTab"')

        self.assertLess(idx_create, idx_all)
        self.assertLess(idx_all, idx_questions)
        self.assertLess(idx_questions, idx_subs)
        self.assertLess(idx_subs, idx_saved)

    def test_04_obsolete_tabs_removed_from_visible_subnav(self):
        """Focus, Top, New, Clubs, Companies, Directions must not be visible tabs in #feedSubnavTabs."""
        subnav_tabs_match = re.search(r'<div[^>]*id=["\']feedSubnavTabs["\'][^>]*>(.*?)</div>', self.feed_html, re.DOTALL)
        self.assertIsNotNone(subnav_tabs_match, "#feedSubnavTabs missing")
        tabs_html = subnav_tabs_match.group(1)

        self.assertNotIn('tabFeedFocus', tabs_html)
        self.assertNotIn('tabFeedTop', tabs_html)
        self.assertNotIn('tabFeedNew', tabs_html)
        self.assertNotIn('tabFeedClubs', tabs_html)
        self.assertNotIn('tabFeedCompanies', tabs_html)
        self.assertNotIn('tabFeedDirections', tabs_html)


class TestTask38StreamToolbarAndControls(TestTask38Base):
    """Section 4 & 5: Stream Toolbar and feed-local search, sort, filters."""

    def test_01_stream_toolbar_structure(self):
        """#feedStreamToolbar contains search input, sort select, question status pills, and filters button."""
        toolbar_match = re.search(r'<div[^>]*id=["\']feedStreamToolbar["\'][^>]*>(.*?)</div>\s*<!-- Active Filter Chips Bar -->', self.feed_html, re.DOTALL)
        self.assertIsNotNone(toolbar_match, "#feedStreamToolbar missing in feed.html")
        toolbar_html = toolbar_match.group(1)

        self.assertIn('id="feedSearchInput"', toolbar_html)
        self.assertIn('placeholder="Поиск публикаций"', toolbar_html)
        self.assertIn('id="feedSortSelect"', toolbar_html)
        self.assertIn('value="newest"', toolbar_html)
        self.assertIn('value="popular"', toolbar_html)
        self.assertIn('value="discussed"', toolbar_html)
        self.assertIn('id="feedQuestionsStatusPills"', toolbar_html)
        self.assertIn('data-status="all"', toolbar_html)
        self.assertIn('data-status="unanswered"', toolbar_html)
        self.assertIn('data-status="solved"', toolbar_html)
        self.assertIn('id="btnFeedFiltersToggle"', toolbar_html)

    def test_02_feed_filters_panel_reused_and_has_all_filter_fields(self):
        """Filters panel is preserved and retains material types, topics, complexity, audience, format."""
        self.assertIn('id="feedFiltersPanel"', self.feed_html)
        self.assertIn('id="feedFilterTopics"', self.feed_html)
        self.assertIn('id="feedComplexitySelect"', self.feed_html)
        self.assertIn('id="feedFormatSelect"', self.feed_html)
        self.assertIn('id="feedAudienceSelect"', self.feed_html)
        self.assertIn('id="feedDateFilterSelect"', self.feed_html)
        self.assertIn('id="btnApplyFilters"', self.feed_html)


class TestTask38QuestionsAndAnswersAPI(TestTask38Base):
    """Section 6 & 7: Questions API, status filters, search with snippets, solution toggle."""

    def test_01_tab_questions_returns_only_questions(self):
        """GET /api/articles?tab=questions returns only items with material_type='question'."""
        status, data, _ = self._get_json("/api/articles?tab=questions")
        self.assertEqual(status, 200)
        items = data.get("items", [])
        self.assertGreater(len(items), 0)
        for item in items:
            self.assertEqual(item.get("material_type"), "question")

    def test_02_question_status_unanswered_and_solved(self):
        """GET /api/articles?tab=questions with questionStatus filter."""
        # Unanswered: answersCount == 0
        status, data_unans, _ = self._get_json("/api/articles?tab=questions&questionStatus=unanswered")
        self.assertEqual(status, 200)
        for item in data_unans.get("items", []):
            self.assertEqual(item.get("answersCount", 0), 0)

        # Solved: hasSolution == True
        status, data_solved, _ = self._get_json("/api/articles?tab=questions&questionStatus=solved")
        self.assertEqual(status, 200)
        for item in data_solved.get("items", []):
            self.assertTrue(item.get("hasSolution"))

    def test_03_answers_search_returns_matched_snippet(self):
        """Searching query that matches an answer body returns the parent question with matchedAnswerSnippet."""
        # In seed_data, art-30 has comment comm-seed-10 with text about SafeMath/ReentrancyGuard
        status, data, _ = self._get_json("/api/articles?tab=questions&q=SafeMath")
        self.assertEqual(status, 200)
        items = data.get("items", [])
        self.assertGreater(len(items), 0)
        found_art30 = next((it for it in items if it.get("id") == "art-30"), None)
        self.assertIsNotNone(found_art30)
        self.assertIn("matchedAnswerSnippet", found_art30)
        self.assertIn("SafeMath", found_art30["matchedAnswerSnippet"])

    def test_04_solution_toggle_authorization(self):
        """Only the question author can accept/unmark a solution (403 for other users)."""
        # Question art-24 author is 'author_petrov'
        # comm-seed-08 is an answer to art-24
        # 1. Non-author attempt (with author_ivanov cookie) -> 403 Forbidden
        fake_cookie = "auth_token=test_author_ivanov_token"
        # Log in author_ivanov first
        status_login, _, cookie_ivanov = self._post_json("/api/auth/login", {"author_id": "author_ivanov"})
        self.assertEqual(status_login, 200)

        status_toggle_fail, data_fail, _ = self._post_json(
            "/api/articles/art-24/comments/comm-seed-08/solution",
            {},
            cookie=cookie_ivanov
        )
        self.assertEqual(status_toggle_fail, 403)
        self.assertIn("Только автор вопроса", data_fail.get("error", ""))

        # 2. Author attempt (author_petrov) -> 200 OK
        status_login, _, cookie_petrov = self._post_json("/api/auth/login", {"author_id": "author_petrov"})
        self.assertEqual(status_login, 200)

        status_toggle_ok, data_ok, _ = self._post_json(
            "/api/articles/art-24/comments/comm-seed-08/solution",
            {},
            cookie=cookie_petrov
        )
        self.assertEqual(status_toggle_ok, 200)
        self.assertTrue(data_ok.get("is_solution"))

        # Verify article comments reflect solution
        status_comments, comm_data, _ = self._get_json("/api/articles/art-24/comments")
        self.assertEqual(status_comments, 200)
        self.assertTrue(comm_data.get("hasSolution"))
        self.assertEqual(comm_data.get("solutionCommentId"), "comm-seed-08")

        # 3. Author unmark -> 200 OK
        status_unmark, data_unmark, _ = self._post_json(
            "/api/articles/art-24/comments/comm-seed-08/solution",
            {},
            cookie=cookie_petrov
        )
        self.assertEqual(status_unmark, 200)
        self.assertFalse(data_unmark.get("is_solution"))


class TestTask38WidgetsAndUserProfiles(TestTask38Base):
    """Section 8 & 9: Sidebar widgets, user profiles, and notifications."""

    def test_01_unanswered_questions_widget_api(self):
        """GET /api/questions/unanswered returns questions with answersCount == 0."""
        status, data, _ = self._get_json("/api/questions/unanswered?limit=3")
        self.assertEqual(status, 200)
        items = data.get("items", [])
        self.assertLessEqual(len(items), 3)
        for q in items:
            self.assertEqual(q.get("material_type"), "question")
            self.assertEqual(q.get("answersCount", 0), 0)

    def test_02_user_profile_api(self):
        """GET /api/users/<id>/profile returns profile details and activity counters."""
        status, profile, _ = self._get_json("/api/users/author_volkov/profile")
        self.assertEqual(status, 200)
        self.assertEqual(profile.get("id"), "author_volkov")
        self.assertIn("specialization", profile)
        self.assertIn("company", profile)
        self.assertIn("bio", profile)
        stats = profile.get("stats", {})
        self.assertIn("publicationsCount", stats)
        self.assertIn("answersCount", stats)
        self.assertIn("solutionsCount", stats)

    def test_03_notifications_api(self):
        """GET /api/notifications and POST /api/notifications/read."""
        # Log in author_morozova
        status_login, _, cookie_morozova = self._post_json("/api/auth/login", {"author_id": "author_morozova"})
        self.assertEqual(status_login, 200)

        # Fetch notifications
        status_notifs, data, _ = self._get_json("/api/notifications", cookie=cookie_morozova)
        self.assertEqual(status_notifs, 200)
        self.assertIn("notifications", data)
        self.assertIn("unreadCount", data)

        # Mark all read
        status_read, read_data, _ = self._post_json("/api/notifications/read", {"all": True}, cookie=cookie_morozova)
        self.assertEqual(status_read, 200)
        self.assertEqual(read_data.get("unreadCount"), 0)


class TestTask38CardAndEditorScenarios(TestTask38Base):
    """Section 10: Question card rendering and Question editor prompt integration."""

    def test_01_question_card_renders_no_cover_and_has_solved_badge(self):
        """In card.js, questions skip cover container and render answers count & solved badge."""
        self.assertIn('item.material_type !== \'question\'', self.card_js)
        self.assertIn('solved-badge', self.card_js)
        self.assertIn('btn-card-answers', self.card_js)
        self.assertIn('card-matched-snippet', self.card_js)
        self.assertIn('btn-author-profile', self.card_js)

    def test_02_question_editor_guidance_and_security_warning(self):
        """In publication.js and editor.html, questions display guidance prompts and secret warning."""
        self.assertIn('type === \'question\'', self.publication_js)
        self.assertIn('questionGuidancePrompts', self.publication_js)
        self.assertIn('questionSecurityWarning', self.publication_js)
        self.assertIn('приватные ключи', self.publication_js)


class TestTask38QualityStandards(TestTask38Base):
    """Offline-first, font compliance, and zero emojis."""

    def test_01_offline_first_strict(self):
        """No external web assets (CDN links) allowed in frontend files."""
        external_pattern = re.compile(r'https?://(?!localhost|127\.0\.0\.1|www\.w3\.org|smartcontractum\.ru)[^\s\'"<>]+')
        for content, name in [
            (self.feed_html, "feed.html"),
            (self.editor_html, "editor.html"),
            (self.article_html, "article.html"),
            (self.index_html, "index.html"),
            (self.feed_css, "feed.css"),
            (self.feed_js, "feed.js"),
            (self.card_js, "card.js"),
            (self.publication_js, "publication.js"),
            (self.article_js, "article.js"),
        ]:
            matches = external_pattern.findall(content)
            self.assertEqual(matches, [], f"External CDN reference found in {name}: {matches}")

    def test_02_zero_emojis(self):
        """Zero emojis in modified JS and CSS files."""
        emoji_pattern = re.compile(r'[\U00010000-\U0010ffff\u2600-\u27bf\u2300-\u23ff\u2b50-\u2b55]')
        for content, name in [
            (self.feed_js, "feed.js"),
            (self.card_js, "card.js"),
            (self.publication_js, "publication.js"),
            (self.article_js, "article.js"),
            (self.feed_css, "feed.css"),
        ]:
            matches = emoji_pattern.findall(content)
            self.assertEqual(matches, [], f"Emoji found in {name}: {matches}")


if __name__ == "__main__":
    unittest.main()
