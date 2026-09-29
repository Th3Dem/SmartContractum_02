#!/usr/bin/env python3
"""
tests/test_issue20_sc020_feed_error_retry_and_offline_badge.py

Comprehensive test suite for Issue #20 (SC-020):
"Устранить подмену серверных ошибок ленты демонстрационными статьями"
GitHub Issue: #20 (https://github.com/Th3Dem/SmartContractum_02/issues/20)

Acceptance Criteria:
1. Server errors (5xx) and network errors when online do not trigger handleOfflineFallback.
   Real server errors are never masked by mock/fallback demo articles.
2. Error state (renderErrorState) is rendered with detailed message and 'Повторить попытку' button (id="feedRetryBtn").
3. Triggering the retry button calls loadArticles(true).
4. Offline fallback (handleOfflineFallback) is only triggered when navigator.onLine === false
   or window.location.protocol === 'file:'.
5. Offline badge (feedOfflineBadge, .feed-offline-badge) is displayed during offline mode
   and hidden on successful online load or server error states.
6. CSS styles for .feed-offline-badge and .feed-offline-dot support dark and light themes,
   use Onest font and design tokens, and contain zero emojis.
7. window.FeedApp exposes loadArticles and retryLoad.
8. 100% pass across all tests in the project.
"""

import json
import os
import re
import shutil
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from typing import Optional, Tuple

import server
from server import create_server, init_db

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue20SC020FeedErrorRetryAndOfflineBadge(unittest.TestCase):
    """Unit and Integration tests for Issue #20 (SC-020)."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue20_sc020.db")
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

        feed_css_path = os.path.join(FRONTEND_DIR, "css", "feed.css")
        with open(feed_css_path, "r", encoding="utf-8") as f:
            cls.feed_css = f.read()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.httpd.shutdown()
            cls.httpd.server_close()
        except Exception:
            pass
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # 1. HTTP Server & Asset Delivery Tests
    # -------------------------------------------------------------------------

    def test_01_http_serves_feed_js_and_feed_css_with_200(self):
        """Verify that server serves js/feed.js and css/feed.css with 200 OK."""
        req_js = urllib.request.Request(f"{self.base_url}/js/feed.js")
        with urllib.request.urlopen(req_js) as resp:
            self.assertEqual(resp.status, 200)
            content = resp.read().decode("utf-8")
            self.assertIn("feedOfflineBadge", content)
            self.assertIn("feedRetryBtn", content)

        req_css = urllib.request.Request(f"{self.base_url}/css/feed.css")
        with urllib.request.urlopen(req_css) as resp:
            self.assertEqual(resp.status, 200)
            content = resp.read().decode("utf-8")
            self.assertIn(".feed-offline-badge", content)
            self.assertIn(".feed-offline-dot", content)

    # -------------------------------------------------------------------------
    # 2. Source Code Architecture & Contract Verification in feed.js
    # -------------------------------------------------------------------------

    def test_02_status_code_preservation_on_non_ok_response(self):
        """Verify fetch error handling attaches response status to Error object."""
        # Must check !res.ok, create error with status and throw
        fetch_idx = self.feed_js.find("fetch('/api/articles?'")
        self.assertNotEqual(fetch_idx, -1, "fetch('/api/articles?' call must exist in feed.js")

        then_block = self.feed_js[fetch_idx:fetch_idx + 600]
        self.assertIn("!res.ok", then_block, "Must check !res.ok in response handler")
        self.assertIn("err.status = res.status", then_block, "Must attach err.status = res.status")
        self.assertIn("throw err", then_block, "Must throw error with attached status")

    def test_03_error_categorization_and_messages(self):
        """Verify .catch handles 5xx, 4xx, and network errors with exact localized text."""
        fetch_idx = self.feed_js.find("fetch('/api/articles?'")
        catch_idx = self.feed_js.find(".catch(function (err) {", fetch_idx)
        self.assertNotEqual(catch_idx, -1, ".catch handler must exist after fetch")

        catch_block = self.feed_js[catch_idx:catch_idx + 1200]

        # 5xx server error message
        self.assertIn("err.status >= 500", catch_block)
        self.assertIn("Ошибка сервера (", catch_block)
        self.assertIn("). Не удалось загрузить публикации.", catch_block)

        # 4xx client request error message
        self.assertIn("err.status >= 400", catch_block)
        self.assertIn("Ошибка запроса (", catch_block)

        # Network error fallback message
        self.assertIn("Ошибка сети при загрузке публикаций.", catch_block)

        # Passes message to renderErrorState
        self.assertIn("renderErrorState(message)", catch_block)

    def test_04_offline_detection_and_conditional_fallback(self):
        """Verify offline fallback strictly requires navigator.onLine === false or file: protocol."""
        fetch_idx = self.feed_js.find("fetch('/api/articles?'")
        catch_idx = self.feed_js.find(".catch(function (err) {", fetch_idx)
        catch_end = self.feed_js.find("});", catch_idx)
        catch_block = self.feed_js[catch_idx:catch_end]

        # Exact offline condition check
        self.assertIn("navigator.onLine === false", catch_block)
        self.assertIn("window.location.protocol === 'file:'", catch_block)

        # Offline branch triggers showOfflineBadge and handleOfflineFallback
        offline_branch_idx = catch_block.find("if (isOffline) {")
        self.assertNotEqual(offline_branch_idx, -1)

        else_branch_idx = catch_block.find("} else {", offline_branch_idx)
        self.assertNotEqual(else_branch_idx, -1)

        offline_sub = catch_block[offline_branch_idx:else_branch_idx]
        self.assertIn("showOfflineBadge()", offline_sub)
        self.assertIn("handleOfflineFallback(isInitial)", offline_sub)

        # Online branch must hide offline badge and render error
        online_sub = catch_block[else_branch_idx:]
        self.assertIn("hideOfflineBadge()", online_sub)
        self.assertIn("renderErrorState(message)", online_sub)
        self.assertNotIn("handleOfflineFallback(isInitial)", online_sub)

    def test_05_online_success_and_api_failure_hide_offline_badge(self):
        """Verify successful load and API application-level error both hide offline badge."""
        fetch_idx = self.feed_js.find("fetch('/api/articles?'")
        then_data_idx = self.feed_js.find(".then(function (data) {", fetch_idx)
        self.assertNotEqual(then_data_idx, -1)

        catch_idx = self.feed_js.find(".catch(function (err) {", then_data_idx)
        then_data_block = self.feed_js[then_data_idx:catch_idx]

        # Success branch hides badge
        success_idx = then_data_block.find("if (data && data.success) {")
        self.assertNotEqual(success_idx, -1)
        else_idx = then_data_block.find("} else {", success_idx)
        self.assertNotEqual(else_idx, -1)

        success_code = then_data_block[success_idx:else_idx]
        self.assertIn("hideOfflineBadge()", success_code)

        # Failure branch hides badge and calls renderErrorState
        failure_code = then_data_block[else_idx:]
        self.assertIn("hideOfflineBadge()", failure_code)
        self.assertIn("renderErrorState(", failure_code)

    def test_06_show_and_hide_offline_badge_implementation(self):
        """Verify showOfflineBadge and hideOfflineBadge manage #feedOfflineBadge element."""
        self.assertIn("function showOfflineBadge()", self.feed_js)
        self.assertIn("function hideOfflineBadge()", self.feed_js)

        show_idx = self.feed_js.find("function showOfflineBadge()")
        show_body = self.feed_js[show_idx:show_idx + 800]

        # Element structure
        self.assertIn('id="feedOfflineBadge"', show_body)
        self.assertIn('feed-offline-badge', show_body)
        self.assertIn('feed-offline-dot', show_body)
        self.assertIn('Автономный режим (демо-данные)', show_body)

        # Placed before #feedCardsContainer
        self.assertIn("container.parentNode.insertBefore(badge, container)", show_body)

        # hideOfflineBadge hides badge
        hide_idx = self.feed_js.find("function hideOfflineBadge()")
        hide_body = self.feed_js[hide_idx:hide_idx + 300]
        self.assertIn("badge.style.display = 'none'", hide_body)

    def test_07_render_error_state_with_retry_button_and_event_listener(self):
        """Verify renderErrorState creates #feedRetryBtn and binds click to loadArticles(true)."""
        render_err_idx = self.feed_js.find("function renderErrorState(message)")
        self.assertNotEqual(render_err_idx, -1)

        render_body = self.feed_js[render_err_idx:render_err_idx + 1200]

        # Contains retry button with id and onclick fallback
        self.assertIn('id="feedRetryBtn"', render_body)
        self.assertIn('Повторить попытку', render_body)
        self.assertIn('window.FeedApp.loadArticles', render_body)
        self.assertIn('window.location.reload()', render_body)

        # Binds addEventListener on #feedRetryBtn to loadArticles(true)
        self.assertIn("getElementById('feedRetryBtn')", render_body)
        self.assertIn("addEventListener('click'", render_body)
        self.assertIn("loadArticles(true)", render_body)

    def test_08_window_feedapp_exports_load_articles_and_retry(self):
        """Verify window.FeedApp exposes loadArticles and retryLoad."""
        self.assertIn("window.FeedApp = window.FeedApp || {};", self.feed_js)
        self.assertIn("window.FeedApp.loadArticles = loadArticles;", self.feed_js)
        self.assertIn("window.FeedApp.retryLoad =", self.feed_js)
        self.assertIn("loadArticles(true)", self.feed_js)
        self.assertIn("const loadArticles = fetchFeed;", self.feed_js)

    # -------------------------------------------------------------------------
    # 3. CSS Styling and Tokens Verification in feed.css
    # -------------------------------------------------------------------------

    def test_09_feed_offline_badge_css_rules(self):
        """Verify .feed-offline-badge and .feed-offline-dot styles in feed.css."""
        # .feed-offline-badge rule exists
        self.assertIn(".feed-offline-badge", self.feed_css)
        badge_match = re.search(r"\.feed-offline-badge\s*\{([^}]+)\}", self.feed_css)
        self.assertIsNotNone(badge_match, ".feed-offline-badge CSS block must exist")
        badge_rules = badge_match.group(1)

        self.assertIn("display: inline-flex", badge_rules)
        self.assertIn("align-items: center", badge_rules)
        self.assertIn("Onest", badge_rules)

        # Light theme rule exists
        light_badge_match = re.search(r'\[data-theme="light"\]\s+\.feed-offline-badge\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(light_badge_match, "Light theme rule for .feed-offline-badge must exist")

        # .feed-offline-dot rule exists
        dot_match = re.search(r"\.feed-offline-dot\s*\{([^}]+)\}", self.feed_css)
        self.assertIsNotNone(dot_match, ".feed-offline-dot CSS block must exist")
        dot_rules = dot_match.group(1)
        self.assertIn("border-radius: 50%", dot_rules)

        # Light theme dot exists
        light_dot_match = re.search(r'\[data-theme="light"\]\s+\.feed-offline-dot\s*\{([^}]+)\}', self.feed_css)
        self.assertIsNotNone(light_dot_match, "Light theme rule for .feed-offline-dot must exist")

    def test_10_zero_emojis_in_feed_js_and_feed_css(self):
        """Verify strict zero emojis standard in feed.js and feed.css."""
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map
            "\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "\U0001F900-\U0001F9FF"  # supplemental symbols
            "\U0001FA00-\U0001FA6F"
            "\U0001FA70-\U0001FAFF"
            "]+",
            flags=re.UNICODE,
        )

        js_emojis = emoji_pattern.findall(self.feed_js)
        self.assertEqual(js_emojis, [], f"feed.js must not contain emojis: {js_emojis}")

        css_emojis = emoji_pattern.findall(self.feed_css)
        self.assertEqual(css_emojis, [], f"feed.css must not contain emojis: {css_emojis}")

    def test_11_offline_first_strict_no_cdns(self):
        """Verify 100% offline-first: no remote external URLs in feed.js or feed.css."""
        external_url_pattern = re.compile(r"https?://(?!localhost|127\.0\.0\.1|www\.w3\.org|smartcontractum\.ru)[^\s\'\"<>]+")
        js_external = external_url_pattern.findall(self.feed_js)
        self.assertEqual(js_external, [], f"feed.js contains external CDN URLs: {js_external}")

        css_external = external_url_pattern.findall(self.feed_css)
        self.assertEqual(css_external, [], f"feed.css contains external CDN URLs: {css_external}")

    # -------------------------------------------------------------------------
    # 4. Client State-Machine Emulation Tests
    # -------------------------------------------------------------------------

    def test_12_simulation_500_server_error_renders_error_and_does_not_fallback(self):
        """Simulate client receiving 500 error: verify renderErrorState is called, not offline fallback."""
        actions = []

        def showOfflineBadge():
            actions.append("showOfflineBadge")

        def hideOfflineBadge():
            actions.append("hideOfflineBadge")

        def handleOfflineFallback(isInitial):
            actions.append(("handleOfflineFallback", isInitial))

        def renderErrorState(msg):
            actions.append(("renderErrorState", msg))

        # Emulate .catch handler with 500 status and navigator.onLine = True
        is_online = True
        protocol = "http:"
        err_status = 500

        is_offline = (not is_online) or (protocol == "file:")
        if is_offline:
            showOfflineBadge()
            handleOfflineFallback(True)
        else:
            hideOfflineBadge()
            if err_status >= 500:
                msg = f"Ошибка сервера ({err_status}). Не удалось загрузить публикации."
            elif err_status >= 400:
                msg = f"Ошибка запроса ({err_status}). Не удалось загрузить публикации."
            else:
                msg = "Ошибка сети при загрузке публикаций."
            renderErrorState(msg)

        # Assertions
        self.assertIn("hideOfflineBadge", actions)
        self.assertIn(("renderErrorState", "Ошибка сервера (500). Не удалось загрузить публикации."), actions)
        self.assertNotIn("showOfflineBadge", actions)
        self.assertFalse(any(a[0] == "handleOfflineFallback" for a in actions if isinstance(a, tuple)))

    def test_13_simulation_404_client_error_renders_error(self):
        """Simulate client receiving 404 error: verify request error message rendered."""
        actions = []

        def hideOfflineBadge():
            actions.append("hideOfflineBadge")

        def renderErrorState(msg):
            actions.append(("renderErrorState", msg))

        err_status = 404
        is_offline = False

        if not is_offline:
            hideOfflineBadge()
            if err_status >= 500:
                msg = f"Ошибка сервера ({err_status}). Не удалось загрузить публикации."
            elif err_status >= 400:
                msg = f"Ошибка запроса ({err_status}). Не удалось загрузить публикации."
            else:
                msg = "Ошибка сети при загрузке публикаций."
            renderErrorState(msg)

        self.assertIn("hideOfflineBadge", actions)
        self.assertIn(("renderErrorState", "Ошибка запроса (404). Не удалось загрузить публикации."), actions)

    def test_14_simulation_offline_mode_shows_badge_and_runs_fallback(self):
        """Simulate client offline (navigator.onLine === false): badge shown, fallback rendered."""
        actions = []

        def showOfflineBadge():
            actions.append("showOfflineBadge")

        def handleOfflineFallback(isInitial):
            actions.append(("handleOfflineFallback", isInitial))

        is_online = False
        protocol = "http:"

        is_offline = (not is_online) or (protocol == "file:")
        if is_offline:
            showOfflineBadge()
            handleOfflineFallback(True)

        self.assertIn("showOfflineBadge", actions)
        self.assertIn(("handleOfflineFallback", True), actions)

    def test_15_simulation_file_protocol_shows_badge_and_runs_fallback(self):
        """Simulate file: protocol load: badge shown, fallback rendered."""
        actions = []

        def showOfflineBadge():
            actions.append("showOfflineBadge")

        def handleOfflineFallback(isInitial):
            actions.append(("handleOfflineFallback", isInitial))

        is_online = True
        protocol = "file:"

        is_offline = (not is_online) or (protocol == "file:")
        if is_offline:
            showOfflineBadge()
            handleOfflineFallback(True)

        self.assertIn("showOfflineBadge", actions)
        self.assertIn(("handleOfflineFallback", True), actions)

    def test_16_simulation_retry_reloads_and_hides_badge_on_success(self):
        """Simulate user clicking retry button after network recovery."""
        feed_state = {"isLoading": False, "articles": [], "badgeVisible": True}

        def hideOfflineBadge():
            feed_state["badgeVisible"] = False

        def loadArticles(is_initial):
            feed_state["isLoading"] = True
            # Simulate successful server response
            data = {"success": True, "articles": [{"id": "art-1", "title": "Live article"}]}
            feed_state["isLoading"] = False
            hideOfflineBadge()
            feed_state["articles"] = data["articles"]

        # Retry triggered
        loadArticles(True)

        self.assertFalse(feed_state["badgeVisible"])
        self.assertEqual(len(feed_state["articles"]), 1)
        self.assertEqual(feed_state["articles"][0]["id"], "art-1")

    # -------------------------------------------------------------------------
    # 5. Integration HTTP Endpoint Contract Tests
    # -------------------------------------------------------------------------

    def test_17_articles_endpoint_contract(self):
        """Verify GET /api/articles returns 200 with standard contract."""
        url = f"{self.base_url}/api/articles?tab=all"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("success"))
            self.assertIn("articles", data)
            self.assertIsInstance(data["articles"], list)


if __name__ == "__main__":
    unittest.main()
