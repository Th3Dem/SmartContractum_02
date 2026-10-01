#!/usr/bin/env python3
"""
tests/test_issue17_sc017_question_status_url_sync.py

Comprehensive regression test suite for Issue #17 (SC-017):
"Сохранять фильтр статуса вопросов (questionStatus) в URL и истории"
GitHub Issue: #17 (https://github.com/Th3Dem/SmartContractum_02/issues/17)

Acceptance Criteria:
1. syncURL() correctly serializes questionStatus into searchParams:
   - When tab === 'questions' and questionStatus is not 'all', questionStatus is included in URL.
   - When questionStatus is 'all' or absent, questionStatus is omitted from URL for clean URLs.
   - When tab is not 'questions', questionStatus is omitted from URL.
2. Filter pill state (#feedQuestionsStatusPills .feed-status-pill) is synchronized:
   - Initial page load with questionStatus URL param updates active pill.
   - Browser back / forward (popstate event) calls parseURLParams and updates pills UI.
   - Tab switching (switchTab to 'questions') triggers updateQuestionStatusPillsUI().
   - Clicking status pills updates state, toggles active class, calls syncURL(false), and fetches feed.
3. Backend /api/articles endpoint works properly with tab=questions & questionStatus:
   - questionStatus=all returns all questions.
   - questionStatus=unanswered returns questions with answersCount == 0.
   - questionStatus=solved returns questions with hasSolution == True.
4. Standards:
   - 100% Offline-First (no external CDNs).
   - Zero emojis in modified codebase and test files.
5. All 491+ base tests pass (100% PASS).
"""

import json
import os
import re
import shutil
import sqlite3
import tempfile
import threading
import time
import unittest
import urllib.parse
import urllib.request
from typing import Optional, Tuple

import server
from server import (
    create_server,
    init_db,
)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue17CodeContracts(unittest.TestCase):
    """Verify JavaScript code contracts and structural implementations in feed.js and feed.html."""

    @classmethod
    def setUpClass(cls):
        feed_js_path = os.path.join(FRONTEND_DIR, "js", "feed.js")
        with open(feed_js_path, "r", encoding="utf-8") as f:
            cls.feed_js = f.read()

        feed_html_path = os.path.join(FRONTEND_DIR, "feed.html")
        with open(feed_html_path, "r", encoding="utf-8") as f:
            cls.feed_html = f.read()

    def test_01_state_declares_question_status(self):
        """state object in feed.js must declare questionStatus default value."""
        self.assertRegex(
            self.feed_js,
            r'questionStatus:\s*[\'"]all[\'"]',
            "state object must declare questionStatus initialized to 'all'"
        )

    def test_02_sync_url_serializes_question_status(self):
        """syncURL() must serialize questionStatus into URL searchParams only for questions tab."""
        pattern = (
            r'if\s*\(\s*state\.tab\s*===\s*[\'"]questions[\'"]\s*&&\s*'
            r'state\.questionStatus\s*&&\s*'
            r'state\.questionStatus\s*!==\s*[\'"]all[\'"]\s*\)\s*\{\s*'
            r'params\.set\(\s*[\'"]questionStatus[\'"]\s*,\s*state\.questionStatus\s*\);\s*'
            r'\}'
        )
        self.assertRegex(
            self.feed_js,
            pattern,
            "syncURL() must conditionally serialize questionStatus when tab === 'questions' and status !== 'all'"
        )

    def test_03_update_question_status_pills_ui_function_defined(self):
        """updateQuestionStatusPillsUI() must be defined and manage .feed-status-pill .active classes."""
        self.assertIn("function updateQuestionStatusPillsUI()", self.feed_js)
        fn_match = re.search(
            r'function updateQuestionStatusPillsUI\(\)\s*\{([\s\S]*?)\n  \}',
            self.feed_js
        )
        self.assertIsNotNone(fn_match, "updateQuestionStatusPillsUI function body not found")
        body = fn_match.group(1)

        self.assertIn("feedQuestionsStatusPills", body, "Must look up #feedQuestionsStatusPills element")
        self.assertIn(".feed-status-pill", body, "Must select .feed-status-pill elements")
        self.assertIn("data-status", body, "Must check data-status attribute on pills")
        self.assertIn("classList.toggle", body, "Must toggle active class on pills")

    def test_04_parse_url_params_calls_update_question_status_pills_ui(self):
        """parseURLParams() must invoke updateQuestionStatusPillsUI()."""
        fn_match = re.search(
            r'function parseURLParams\(\)\s*\{([\s\S]*?)\n  \}',
            self.feed_js
        )
        self.assertIsNotNone(fn_match, "parseURLParams function body not found")
        body = fn_match.group(1)

        self.assertIn(
            "updateQuestionStatusPillsUI()",
            body,
            "parseURLParams must call updateQuestionStatusPillsUI() to synchronize UI on initial load and popstate"
        )
        self.assertIn(
            "state.questionStatus = params.get('questionStatus') || 'all'",
            body,
            "parseURLParams must parse questionStatus from URL search params"
        )

    def test_05_switch_tab_calls_update_question_status_pills_ui(self):
        """switchTab() must invoke updateQuestionStatusPillsUI() when transitioning to questions tab."""
        fn_match = re.search(
            r'function switchTab\(tabName\)\s*\{([\s\S]*?)\n  \}',
            self.feed_js
        )
        self.assertIsNotNone(fn_match, "switchTab function body not found")
        body = fn_match.group(1)

        q_block_pattern = (
            r'if\s*\(\s*tabName\s*===\s*[\'"]questions[\'"]\s*\)\s*\{[\s\S]*?'
            r'updateQuestionStatusPillsUI\(\);'
        )
        self.assertRegex(
            body,
            q_block_pattern,
            "switchTab must call updateQuestionStatusPillsUI() when tabName === 'questions'"
        )

    def test_06_status_pills_click_listener_wires_sync_and_ui(self):
        """Clicking on .feed-status-pill must update state, call updateQuestionStatusPillsUI, syncURL(false), and fetchFeed(true)."""
        listener_match = re.search(
            r'const\s+statusPillsWrap\s*=\s*document\.getElementById\([\'"]feedQuestionsStatusPills[\'"]\);([\s\S]*?)\n    \}',
            self.feed_js
        )
        self.assertIsNotNone(listener_match, "Questions status pills listener block not found")
        listener_block = listener_match.group(1)

        self.assertIn("updateQuestionStatusPillsUI()", listener_block)
        self.assertIn("syncURL(false)", listener_block)
        self.assertIn("fetchFeed(true)", listener_block)

    def test_07_popstate_listener_calls_parse_url_params(self):
        """window 'popstate' event handler must call parseURLParams()."""
        popstate_pattern = (
            r'window\.addEventListener\([\'"]popstate[\'"],\s*function\s*\(\)\s*\{[\s\S]*?'
            r'parseURLParams\(\);'
        )
        self.assertRegex(
            self.feed_js,
            popstate_pattern,
            "window popstate event listener must call parseURLParams()"
        )

    def test_08_feed_html_contains_questions_status_pills_markup(self):
        """feed.html must contain #feedQuestionsStatusPills with all, unanswered, and solved status pills."""
        pills_match = re.search(
            r'<div[^>]*id=["\']feedQuestionsStatusPills["\'][^>]*>(.*?)</div>',
            self.feed_html,
            re.DOTALL
        )
        self.assertIsNotNone(pills_match, "#feedQuestionsStatusPills container missing in feed.html")
        pills_html = pills_match.group(1)

        self.assertIn('data-status="all"', pills_html)
        self.assertIn('data-status="unanswered"', pills_html)
        self.assertIn('data-status="solved"', pills_html)
        self.assertIn('class="feed-status-pill active"', pills_html)

    def test_09_window_exports_include_pills_helper(self):
        """feed.js must expose __updateQuestionStatusPillsUI, __parseURLParams, and __syncURL on window."""
        self.assertIn("window.__updateQuestionStatusPillsUI = updateQuestionStatusPillsUI;", self.feed_js)
        self.assertIn("window.__parseURLParams = parseURLParams;", self.feed_js)
        self.assertIn("window.__syncURL = syncURL;", self.feed_js)


class TestIssue17URLSyncSimulation(unittest.TestCase):
    """
    Simulate the exact JavaScript logic of parseURLParams(), syncURL(),
    and updateQuestionStatusPillsUI() across full navigation cycles.
    """

    class MockPill:
        def __init__(self, status: str, active: bool = False):
            self.status = status
            self.classes = {"feed-status-pill"}
            if active:
                self.classes.add("active")

        def get_attribute(self, attr: str):
            if attr == "data-status":
                return self.status
            return None

        def toggle_class(self, cls: str, state: bool):
            if state:
                self.classes.add(cls)
            else:
                self.classes.discard(cls)

        @property
        def is_active(self):
            return "active" in self.classes

    class FeedEngineSimulation:
        """Mirror of the JavaScript state machine in feed.js."""

        def __init__(self):
            self.state = {
                "tab": "all",
                "questionStatus": "all",
                "topPeriod": "week",
                "search": "",
                "sort": "newest",
                "offset": 0,
                "filters": {
                    "types": [],
                    "topics": [],
                    "complexities": [],
                    "period": "all",
                    "dateFrom": "",
                    "dateTo": "",
                    "formats": [],
                    "format": "all",
                    "audiences": [],
                    "audience": "all",
                }
            }
            self.pills = [
                TestIssue17URLSyncSimulation.MockPill("all", active=True),
                TestIssue17URLSyncSimulation.MockPill("unanswered", active=False),
                TestIssue17URLSyncSimulation.MockPill("solved", active=False),
            ]
            self.history = []
            self.current_url = "/feed.html"

        def update_question_status_pills_ui(self):
            current = self.state.get("questionStatus") or "all"
            for pill in self.pills:
                s = pill.get_attribute("data-status") or "all"
                pill.toggle_class("active", s == current)

        def sync_url(self, replace: bool = False) -> str:
            params = urllib.parse.parse_qsl("")
            out_params = {}

            if self.state["tab"] and self.state["tab"] != "focus":
                out_params["tab"] = self.state["tab"]

            if (self.state["tab"] == "questions" and
                    self.state.get("questionStatus") and
                    self.state["questionStatus"] != "all"):
                out_params["questionStatus"] = self.state["questionStatus"]

            if self.state["tab"] == "top" and self.state.get("topPeriod") and self.state["topPeriod"] != "week":
                out_params["period"] = self.state["topPeriod"]

            if self.state.get("search"):
                out_params["search"] = self.state["search"]

            if self.state.get("sort") and self.state["sort"] != "newest":
                out_params["sort"] = self.state["sort"]

            query_str = urllib.parse.urlencode(out_params)
            new_url = "/feed.html" + ("?" + query_str if query_str else "")

            if replace:
                if self.history:
                    self.history[-1] = new_url
                else:
                    self.history.append(new_url)
            else:
                self.history.append(new_url)

            self.current_url = new_url
            return new_url

        def parse_url_params(self, query_string: str):
            qs = query_string.lstrip("?")
            params = dict(urllib.parse.parse_qsl(qs))

            tab_param = (params.get("tab") or "").lower()
            if tab_param == "questions":
                self.state["tab"] = "questions"
            elif tab_param in ("all", "focus", ""):
                self.state["tab"] = "all"
            else:
                self.state["tab"] = tab_param

            self.state["questionStatus"] = params.get("questionStatus") or "all"
            self.update_question_status_pills_ui()

        def click_status_pill(self, status: str):
            self.state["questionStatus"] = status
            self.update_question_status_pills_ui()
            self.state["offset"] = 0
            self.sync_url(replace=False)

        def switch_tab(self, tab_name: str):
            self.state["tab"] = tab_name
            self.state["offset"] = 0
            if tab_name == "questions":
                self.update_question_status_pills_ui()
            self.sync_url(replace=False)

        def popstate(self, url: str):
            parsed = urllib.parse.urlparse(url)
            self.current_url = url
            self.parse_url_params(parsed.query)

    def test_01_initial_page_load_with_question_status(self):
        """Initial load with ?tab=questions&questionStatus=unanswered sets state and active pill."""
        engine = self.FeedEngineSimulation()
        engine.parse_url_params("tab=questions&questionStatus=unanswered")

        self.assertEqual(engine.state["tab"], "questions")
        self.assertEqual(engine.state["questionStatus"], "unanswered")

        pills = {p.status: p.is_active for p in engine.pills}
        self.assertFalse(pills["all"])
        self.assertTrue(pills["unanswered"])
        self.assertFalse(pills["solved"])

    def test_02_sync_url_omits_all_status(self):
        """When questionStatus is 'all', syncURL generates clean ?tab=questions."""
        engine = self.FeedEngineSimulation()
        engine.switch_tab("questions")
        engine.click_status_pill("all")

        self.assertEqual(engine.current_url, "/feed.html?tab=questions")
        self.assertNotIn("questionStatus", engine.current_url)

    def test_03_sync_url_includes_unanswered_and_solved(self):
        """Clicking unanswered or solved updates URL with questionStatus param."""
        engine = self.FeedEngineSimulation()
        engine.switch_tab("questions")

        engine.click_status_pill("unanswered")
        self.assertEqual(engine.current_url, "/feed.html?tab=questions&questionStatus=unanswered")
        self.assertTrue(next(p for p in engine.pills if p.status == "unanswered").is_active)

        engine.click_status_pill("solved")
        self.assertEqual(engine.current_url, "/feed.html?tab=questions&questionStatus=solved")
        self.assertTrue(next(p for p in engine.pills if p.status == "solved").is_active)
        self.assertFalse(next(p for p in engine.pills if p.status == "unanswered").is_active)

    def test_04_sync_url_omits_question_status_on_other_tabs(self):
        """Switching away from questions tab excludes questionStatus from URL."""
        engine = self.FeedEngineSimulation()
        engine.switch_tab("questions")
        engine.click_status_pill("unanswered")
        self.assertIn("questionStatus=unanswered", engine.current_url)

        engine.switch_tab("all")
        self.assertEqual(engine.current_url, "/feed.html?tab=all")
        self.assertNotIn("questionStatus", engine.current_url)

        engine.switch_tab("subscriptions")
        self.assertEqual(engine.current_url, "/feed.html?tab=subscriptions")
        self.assertNotIn("questionStatus", engine.current_url)

    def test_05_browser_history_back_forward_popstate_synchronization(self):
        """Full navigation history sequence: popstate synchronizes pills and state correctly."""
        engine = self.FeedEngineSimulation()

        # 1. User arrives on questions feed (?tab=questions)
        engine.switch_tab("questions")
        url_all = engine.current_url
        self.assertEqual(url_all, "/feed.html?tab=questions")

        # 2. User clicks 'Без ответа'
        engine.click_status_pill("unanswered")
        url_unans = engine.current_url
        self.assertEqual(url_unans, "/feed.html?tab=questions&questionStatus=unanswered")

        # 3. User clicks 'Решенные'
        engine.click_status_pill("solved")
        url_solved = engine.current_url
        self.assertEqual(url_solved, "/feed.html?tab=questions&questionStatus=solved")

        # 4. User hits browser 'Back' -> returns to 'Без ответа'
        engine.popstate(url_unans)
        self.assertEqual(engine.state["questionStatus"], "unanswered")
        self.assertTrue(next(p for p in engine.pills if p.status == "unanswered").is_active)
        self.assertFalse(next(p for p in engine.pills if p.status == "solved").is_active)

        # 5. User hits browser 'Back' -> returns to 'Все'
        engine.popstate(url_all)
        self.assertEqual(engine.state["questionStatus"], "all")
        self.assertTrue(next(p for p in engine.pills if p.status == "all").is_active)
        self.assertFalse(next(p for p in engine.pills if p.status == "unanswered").is_active)

        # 6. User hits browser 'Forward' -> returns to 'Без ответа'
        engine.popstate(url_unans)
        self.assertEqual(engine.state["questionStatus"], "unanswered")
        self.assertTrue(next(p for p in engine.pills if p.status == "unanswered").is_active)

        # 7. User hits browser 'Forward' -> returns to 'Решенные'
        engine.popstate(url_solved)
        self.assertEqual(engine.state["questionStatus"], "solved")
        self.assertTrue(next(p for p in engine.pills if p.status == "solved").is_active)


class TestIssue17QuestionsAPI(unittest.TestCase):
    """Integration test suite for backend /api/articles with tab=questions & questionStatus."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue17_sc017.db")
        server.DEFAULT_DB_PATH = cls.db_path

        # Initialize base schema and seeds
        conn = init_db(cls.db_path)
        conn.close()

        # Start dynamic HTTP server
        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR)
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.httpd.shutdown()
            cls.httpd.server_close()
        except Exception:
            pass
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def _get_json(self, path: str, cookie: Optional[str] = None) -> Tuple[int, dict]:
        url = f"{self.base_url}{path}"
        headers = {}
        if cookie:
            headers["Cookie"] = cookie
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req) as resp:
                res_body = resp.read().decode("utf-8")
                return resp.status, json.loads(res_body) if res_body else {}
        except urllib.error.HTTPError as e:
            res_body = e.read().decode("utf-8")
            return e.code, json.loads(res_body) if res_body else {}

    def test_01_tab_questions_status_all_returns_only_questions(self):
        """GET /api/articles?tab=questions&questionStatus=all returns questions with all statuses."""
        status, data = self._get_json("/api/articles?tab=questions&questionStatus=all&limit=50")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))

        items = data.get("items") or data.get("articles") or []
        self.assertGreater(len(items), 0, "Seed data must contain question materials")

        for item in items:
            self.assertEqual(item.get("material_type"), "question")

    def test_02_tab_questions_status_unanswered_filters_zero_answers(self):
        """GET /api/articles?tab=questions&questionStatus=unanswered returns only questions with 0 answers."""
        status, data = self._get_json("/api/articles?tab=questions&questionStatus=unanswered&limit=50")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))

        items = data.get("items") or data.get("articles") or []
        self.assertGreater(len(items), 0, "Seed data must contain unanswered questions")

        for item in items:
            self.assertEqual(item.get("material_type"), "question")
            self.assertEqual(item.get("answersCount", 0), 0, f"Question {item.get('id')} must have 0 answers")

    def test_03_tab_questions_status_solved_filters_has_solution(self):
        """GET /api/articles?tab=questions&questionStatus=solved returns only questions with hasSolution=True."""
        status, data = self._get_json("/api/articles?tab=questions&questionStatus=solved&limit=50")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))

        items = data.get("items") or data.get("articles") or []
        self.assertGreater(len(items), 0, "Seed data must contain solved questions")

        for item in items:
            self.assertEqual(item.get("material_type"), "question")
            self.assertTrue(item.get("hasSolution"), f"Question {item.get('id')} must be solved")

    def test_04_tab_questions_pagination_with_status_filter(self):
        """Pagination (limit, offset) respects questionStatus filter boundaries."""
        status1, data1 = self._get_json("/api/articles?tab=questions&questionStatus=unanswered&limit=1&offset=0")
        self.assertEqual(status1, 200)
        items1 = data1.get("items") or data1.get("articles") or []
        self.assertEqual(len(items1), 1)

        total_unanswered = data1.get("total", 0)
        self.assertGreaterEqual(total_unanswered, 1)

        if total_unanswered > 1:
            status2, data2 = self._get_json("/api/articles?tab=questions&questionStatus=unanswered&limit=1&offset=1")
            self.assertEqual(status2, 200)
            items2 = data2.get("items") or data2.get("articles") or []
            self.assertEqual(len(items2), 1)
            self.assertNotEqual(items1[0]["id"], items2[0]["id"], "Offset must return distinct question")

    def test_05_tab_all_ignores_question_status_filter(self):
        """GET /api/articles?tab=all&questionStatus=unanswered returns regular articles as well as questions."""
        status, data = self._get_json("/api/articles?tab=all&questionStatus=unanswered&limit=50")
        self.assertEqual(status, 200)

        items = data.get("items") or data.get("articles") or []
        types = {item.get("material_type") for item in items}
        self.assertTrue("publication" in types or "article" in types, "Tab 'all' must return publications regardless of questionStatus param")


class TestIssue17StandardsAndQuality(unittest.TestCase):
    """Standards compliance: 100% offline-first, strict zero emojis, clean code."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(FRONTEND_DIR, "js", "feed.js"), "r", encoding="utf-8") as f:
            cls.feed_js = f.read()
        with open(__file__, "r", encoding="utf-8") as f:
            cls.test_file_code = f.read()

    def test_01_zero_emojis(self):
        """Ensure zero emojis in frontend/public/js/feed.js and test file."""
        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]")

        feed_emojis = emoji_pattern.findall(self.feed_js)
        self.assertEqual(len(feed_emojis), 0, f"Found emojis in feed.js: {feed_emojis}")

        test_emojis = emoji_pattern.findall(self.test_file_code)
        self.assertEqual(len(test_emojis), 0, f"Found emojis in test file: {test_emojis}")

    def test_02_offline_first_strict(self):
        """Ensure no external CDN or third-party web assets are referenced in feed.js."""
        external_patterns = [
            r"https?://cdnjs\.cloudflare\.com",
            r"https?://cdn\.jsdelivr\.net",
            r"https?://fonts\.googleapis\.com",
            r"https?://unpkg\.com",
        ]
        for pat in external_patterns:
            self.assertIsNone(
                re.search(pat, self.feed_js, re.IGNORECASE),
                f"External web asset reference detected matching {pat}"
            )


if __name__ == "__main__":
    unittest.main()
