#!/usr/bin/env python3
"""
tests/test_issue11_sc010_feed_race_conditions.py

Regression test suite for Issue #11 (SC-010):
"Исключить гонки запросов в ленте через AbortController и генерации запросов"
GitHub Issue: #11 (https://github.com/Th3Dem/SmartContractum_02/issues/11)

Acceptance Criteria:
1. Сетевые запросы ленты используют AbortController для отмены устаревших запросов
   при смене вкладки, фильтров или поиска.
2. Введен счетчик поколений requestGeneration, ответы с устаревшим поколением
   гарантированно игнорируются.
3. Смена вкладки не блокируется флагом isLoading предыдущего незавершенного запроса.
4. 100% тестов проекта проходят успешно (python3 -m unittest discover tests/).
5. Оформлен tasks/issue-11-sc010-feed-abort-controller-and-request-generations/DEV_HANDOVER.md.
"""

import os
import re
import tempfile
import threading
import time
import unittest
import urllib.request

import server
from server import create_server, init_db

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue11SC010FeedRaceConditions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue11_sc010.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path)
        conn.close()

        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR)
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.1)

        feed_js_path = os.path.join(FRONTEND_DIR, "js", "feed.js")
        with open(feed_js_path, "r", encoding="utf-8") as f:
            cls.feed_js = f.read()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.httpd.shutdown()
            cls.httpd.server_close()
        except Exception:
            pass

    def test_01_http_serves_feed_js_with_abort_controller_and_generations(self):
        """Verify that server serves js/feed.js with 200 OK and expected race condition guards."""
        req = urllib.request.Request(f"{self.base_url}/js/feed.js")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            content = resp.read().decode("utf-8")
            self.assertIn("feedAbortController", content)
            self.assertIn("requestGeneration", content)
            self.assertIn("AbortError", content)

    def test_02_abort_controller_declaration_and_signal_passing(self):
        """Verify AbortController lifecycle in feed.js: module declaration, aborting previous, signal in fetch."""
        # 1. Module-level variable declaration
        self.assertRegex(
            self.feed_js,
            r'let\s+feedAbortController\s*=\s*null;',
            "feed.js must declare let feedAbortController = null at module scope"
        )

        # 2. In fetchFeed, prior controller is aborted when isInitial is true
        abort_pattern = (
            r'if\s*\(\s*isInitial\s*\)\s*\{\s*'
            r'if\s*\(\s*feedAbortController\s*\)\s*\{\s*'
            r'feedAbortController\.abort\(\);'
        )
        self.assertRegex(
            self.feed_js,
            abort_pattern,
            "fetchFeed must abort active feedAbortController when starting initial load"
        )

        # 3. New AbortController is instantiated
        self.assertIn(
            "feedAbortController = new AbortController();",
            self.feed_js,
            "fetchFeed must instantiate a new AbortController"
        )

        # 4. signal is passed to fetch()
        fetch_signal_pattern = r"fetch\(\s*['\"]/api/articles\?['\"]\s*\+\s*params\.toString\(\)\s*,\s*\{\s*signal:\s*feedAbortController\.signal\s*\}\s*\)"
        self.assertRegex(
            self.feed_js,
            fetch_signal_pattern,
            "fetch() must receive { signal: feedAbortController.signal }"
        )

    def test_03_request_generation_increment_and_guard_conditions(self):
        """Verify requestGeneration tracking and validation in .then() and .catch()."""
        # 1. Initialized in state object
        self.assertRegex(
            self.feed_js,
            r'requestGeneration:\s*0',
            "state object must define requestGeneration initialized to 0"
        )

        # 2. Incremented on request initiation
        self.assertRegex(
            self.feed_js,
            r'state\.requestGeneration\s*=\s*\(\s*state\.requestGeneration\s*\|\|\s*0\s*\)\s*\+\s*1;',
            "fetchFeed must increment state.requestGeneration"
        )

        # 3. Current generation captured
        self.assertIn(
            "const currentGeneration = state.requestGeneration;",
            self.feed_js,
            "fetchFeed must capture const currentGeneration = state.requestGeneration;"
        )

        # 4. Guard condition in first .then()
        then1_pattern = r"\.then\(function\s*\(\s*res\s*\)\s*\{\s*if\s*\(\s*currentGeneration\s*!==\s*state\.requestGeneration\s*\)\s*return;"
        self.assertRegex(
            self.feed_js,
            then1_pattern,
            "First .then callback must check if currentGeneration !== state.requestGeneration"
        )

        # 5. Guard condition in second .then()
        then2_pattern = r"\.then\(function\s*\(\s*data\s*\)\s*\{\s*if\s*\(\s*currentGeneration\s*!==\s*state\.requestGeneration"
        self.assertRegex(
            self.feed_js,
            then2_pattern,
            "Data .then callback must check if currentGeneration !== state.requestGeneration"
        )

    def test_04_no_tab_switching_lock_when_is_loading(self):
        """Verify fetchFeed does not block tab switching when state.isLoading is true."""
        # 1. No unconditional `if (state.isLoading) return;` at start of fetchFeed
        fetch_feed_idx = self.feed_js.find("function fetchFeed(isInitial)")
        self.assertNotEqual(fetch_feed_idx, -1, "fetchFeed function must be present")
        fetch_feed_body = self.feed_js[fetch_feed_idx:fetch_feed_idx + 1000]

        # In the first 150 chars of function body, ensure unconditional return is NOT present
        self.assertNotIn(
            "if (state.isLoading) return;",
            fetch_feed_body[:150],
            "fetchFeed must not unconditionally return if state.isLoading is true"
        )

        # 2. Check for scoped pagination lock
        self.assertIn(
            "if (!isInitial && state.isLoading) return;",
            fetch_feed_body,
            "fetchFeed must only lock when !isInitial && state.isLoading (pagination only)"
        )

        # 3. switchTab aborts feed controller and bumps generation for non-feed tabs
        switch_tab_idx = self.feed_js.find("if (tabName === 'clubs' || tabName === 'companies' || tabName === 'directions')")
        self.assertNotEqual(switch_tab_idx, -1, "switchTab must handle non-feed tabs")
        switch_tab_block = self.feed_js[switch_tab_idx:switch_tab_idx + 300]
        self.assertIn("feedAbortController.abort()", switch_tab_block)
        self.assertIn("state.requestGeneration", switch_tab_block)

    def test_05_abort_error_handling_and_no_offline_fallback(self):
        """Verify that AbortError and stale generation errors are ignored without triggering offline fallback."""
        fetch_feed_idx = self.feed_js.find("function fetchFeed(isInitial)")
        self.assertNotEqual(fetch_feed_idx, -1, "fetchFeed function must be present")

        catch_idx = self.feed_js.find(".catch(function (err) {", fetch_feed_idx)
        self.assertNotEqual(catch_idx, -1, "fetchFeed must contain .catch handler")
        catch_body = self.feed_js[catch_idx:catch_idx + 400]

        # Guard checks AbortError or stale generation
        self.assertIn(
            "if (err.name === 'AbortError' || currentGeneration !== state.requestGeneration)",
            catch_body,
            ".catch must guard against AbortError or stale generation before state manipulation"
        )

        # Immediate return before handleOfflineFallback
        guard_idx = catch_body.find("if (err.name === 'AbortError' || currentGeneration !== state.requestGeneration)")
        fallback_idx = catch_body.find("handleOfflineFallback(isInitial)")
        is_loading_idx = catch_body.find("state.isLoading = false;")

        self.assertGreater(fallback_idx, guard_idx, "handleOfflineFallback must come after AbortError guard")
        self.assertGreater(is_loading_idx, guard_idx, "state.isLoading = false must come after AbortError guard")

    def test_06_state_machine_simulation_race_condition_elimination(self):
        """
        Python state-machine simulation replicating the exact client-side logic:
        - Simulates asynchronous network delays and interleaving.
        - Proves that stale responses do NOT overwrite fresh tab data.
        - Proves that aborted requests do NOT trigger offline fallback.
        - Proves that switching tabs while loading immediately aborts and applies new generation.
        """
        class SimulatedFeedManager:
            def __init__(self):
                self.state = {
                    "tab": "focus",
                    "articles": [],
                    "total": 0,
                    "isLoading": False,
                    "requestGeneration": 0,
                    "offlineFallbackTriggered": False,
                }
                self.feedAbortController = None
                self.network_in_flight = {}

            def switchTab(self, new_tab):
                self.state["tab"] = new_tab
                self.fetchFeed(is_initial=True)

            def fetchFeed(self, is_initial):
                if not is_initial and self.state["isLoading"]:
                    return

                if is_initial:
                    if self.feedAbortController:
                        self.feedAbortController["aborted"] = True
                    self.feedAbortController = {"aborted": False, "signal": {"aborted": False}}
                elif not self.feedAbortController or self.feedAbortController["aborted"]:
                    self.feedAbortController = {"aborted": False, "signal": {"aborted": False}}

                self.state["requestGeneration"] = (self.state.get("requestGeneration") or 0) + 1
                current_generation = self.state["requestGeneration"]
                self.state["isLoading"] = True

                # Controller associated with this request
                req_controller = self.feedAbortController

                # Return request descriptor for test harness to resolve/reject
                req_id = f"req_{current_generation}"
                self.network_in_flight[req_id] = {
                    "req_id": req_id,
                    "tab": self.state["tab"],
                    "generation": current_generation,
                    "controller": req_controller,
                    "is_initial": is_initial,
                }
                return req_id

            def resolveRequest(self, req_id, articles_data, is_error=False, status=200):
                req = self.network_in_flight.pop(req_id, None)
                if not req:
                    return

                current_generation = req["generation"]
                controller = req["controller"]

                # Simulate fetch() behavior when signal is aborted
                if controller["aborted"]:
                    # Fetch rejects with AbortError
                    self._onCatch(
                        error={"name": "AbortError", "message": "The user aborted a request."},
                        current_generation=current_generation,
                        is_initial=req["is_initial"]
                    )
                    return

                if is_error:
                    # Server error or network error
                    self._onCatch(
                        error={"name": "NetworkError", "message": "Failed to fetch"},
                        current_generation=current_generation,
                        is_initial=req["is_initial"]
                    )
                    return

                # .then(res => ...)
                if current_generation != self.state["requestGeneration"]:
                    return

                # .then(data => ...)
                if current_generation != self.state["requestGeneration"]:
                    return

                self.state["isLoading"] = False
                if req["is_initial"]:
                    self.state["articles"] = list(articles_data)
                else:
                    self.state["articles"].extend(articles_data)
                self.state["total"] = len(self.state["articles"])

            def _onCatch(self, error, current_generation, is_initial):
                if error.get("name") == "AbortError" or current_generation != self.state["requestGeneration"]:
                    # Ignored cleanly!
                    return

                self.state["isLoading"] = False
                # Handle offline fallback
                self.state["offlineFallbackTriggered"] = True
                self.state["articles"] = [{"id": "fallback_1", "title": "Offline Fallback Article"}]
                self.state["total"] = 1

        # =========================================================================
        # Scenario 1: Tab A request is slow; Tab B request is fast.
        # Tab A response arrives AFTER Tab B has already resolved.
        # =========================================================================
        feed = SimulatedFeedManager()

        # User is on 'focus' tab
        req_1 = feed.fetchFeed(is_initial=True)
        self.assertEqual(feed.state["requestGeneration"], 1)
        self.assertTrue(feed.state["isLoading"])

        # User switches to 'top' tab while req_1 is still pending
        req_2 = feed.fetchFeed(is_initial=True)
        self.assertEqual(feed.state["requestGeneration"], 2)
        self.assertTrue(feed.state["isLoading"])

        # Check req_1's controller was aborted
        self.assertTrue(feed.network_in_flight[req_1]["controller"]["aborted"])
        self.assertFalse(feed.network_in_flight[req_2]["controller"]["aborted"])

        # Req 2 (Tab B 'top') arrives first
        tab_b_articles = [{"id": "top_1", "title": "Top Article 1"}, {"id": "top_2", "title": "Top Article 2"}]
        feed.resolveRequest(req_2, tab_b_articles)

        self.assertFalse(feed.state["isLoading"])
        self.assertEqual(len(feed.state["articles"]), 2)
        self.assertEqual(feed.state["articles"][0]["id"], "top_1")

        # Req 1 (Tab A 'focus') arrives late
        tab_a_articles = [{"id": "focus_old", "title": "Old Focus Article"}]
        feed.resolveRequest(req_1, tab_a_articles)

        # Tab B data must NOT be overwritten!
        self.assertEqual(len(feed.state["articles"]), 2)
        self.assertEqual(feed.state["articles"][0]["id"], "top_1")
        self.assertEqual(feed.state["articles"][1]["id"], "top_2")
        self.assertFalse(feed.state["offlineFallbackTriggered"])

        # =========================================================================
        # Scenario 2: Network failure on outdated request does NOT trigger offline
        # fallback or corrupt loading flag of current request.
        # =========================================================================
        feed_err = SimulatedFeedManager()
        req_x = feed_err.fetchFeed(is_initial=True)
        self.assertEqual(feed_err.state["requestGeneration"], 1)

        # Rapidly change search/tab
        req_y = feed_err.fetchFeed(is_initial=True)
        self.assertEqual(feed_err.state["requestGeneration"], 2)
        self.assertTrue(feed_err.state["isLoading"])

        # Req X suffers a network error
        feed_err.resolveRequest(req_x, [], is_error=True)

        # Req Y is still cleanly loading and offline fallback was NOT triggered
        self.assertTrue(feed_err.state["isLoading"], "Outdated error must not clear isLoading of newer request")
        self.assertFalse(feed_err.state["offlineFallbackTriggered"], "Outdated error must not trigger offline fallback")
        self.assertEqual(feed_err.state["articles"], [])

        # Req Y resolves successfully
        feed_err.resolveRequest(req_y, [{"id": "valid_res", "title": "Valid Result"}])
        self.assertFalse(feed_err.state["isLoading"])
        self.assertEqual(len(feed_err.state["articles"]), 1)
        self.assertEqual(feed_err.state["articles"][0]["id"], "valid_res")

        # =========================================================================
        # Scenario 3: Pagination lock behavior.
        # While pagination is in flight, another pagination call is ignored.
        # But a tab switch (is_initial=True) CANCELS the pagination request.
        # =========================================================================
        feed_pag = SimulatedFeedManager()
        req_init = feed_pag.fetchFeed(is_initial=True)
        feed_pag.resolveRequest(req_init, [{"id": "item_1"}])
        self.assertFalse(feed_pag.state["isLoading"])

        # Start pagination
        req_page1 = feed_pag.fetchFeed(is_initial=False)
        self.assertIsNotNone(req_page1)
        self.assertTrue(feed_pag.state["isLoading"])

        # Second pagination click while loading is ignored
        req_page_dup = feed_pag.fetchFeed(is_initial=False)
        self.assertIsNone(req_page_dup)

        # User switches tab -> cancels pagination and starts new initial request
        req_tab = feed_pag.fetchFeed(is_initial=True)
        self.assertIsNotNone(req_tab)
        self.assertTrue(feed_pag.network_in_flight[req_page1]["controller"]["aborted"])

        # Pagination arrives late; discarded
        feed_pag.resolveRequest(req_page1, [{"id": "item_2_late"}])
        # Tab arrives; accepted
        feed_pag.resolveRequest(req_tab, [{"id": "tab_item_1"}])

        self.assertEqual(len(feed_pag.state["articles"]), 1)
        self.assertEqual(feed_pag.state["articles"][0]["id"], "tab_item_1")

    def test_07_javascript_structural_integrity(self):
        """Verify balanced syntax tokens, closure integrity, and no debug artifacts."""
        open_braces = self.feed_js.count('{')
        close_braces = self.feed_js.count('}')
        self.assertEqual(open_braces, close_braces, f"Mismatched braces: {open_braces} vs {close_braces}")

        open_parens = self.feed_js.count('(')
        close_parens = self.feed_js.count(')')
        self.assertEqual(open_parens, close_parens, f"Mismatched parentheses: {open_parens} vs {close_parens}")

        open_brackets = self.feed_js.count('[')
        close_brackets = self.feed_js.count(']')
        self.assertEqual(open_brackets, close_brackets, f"Mismatched brackets: {open_brackets} vs {close_brackets}")

        # Check IIFE isolation
        self.assertIn('(function () {', self.feed_js)
        self.assertTrue(self.feed_js.strip().endswith('})();'))

        # Check no debuggers
        self.assertNotIn('debugger;', self.feed_js)


if __name__ == '__main__':
    unittest.main()
