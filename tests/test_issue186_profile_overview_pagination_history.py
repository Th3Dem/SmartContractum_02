#!/usr/bin/env python3
"""
tests/test_issue186_profile_overview_pagination_history.py

Automated test suite for Issue #186:
[P1][frontend][PROFILE] Исправить пустой обзор, гонки запросов, пагинацию и историю.

Verifies:
1. Safe pagination:
   - Offset is never incremented before fetch in loadActivity, loadPublications, loadQuestions, loadAnswers.
   - Offset is incremented strictly on successful response (offset += items.length).
   - Load more click handlers do not increment offset prematurely.
2. Race condition & Sequence token protection:
   - Request sequence counters (actReqSeq, pubReqSeq, questReqSeq, ansReqSeq) and AbortControllers.
   - Rapid filter/sort changes supersede pending requests without blocking UI.
   - Outdated in-flight responses are ignored.
3. Error states with retry:
   - Distinct error states for Activity, Publications, Questions, and Answers feeds.
   - Retry buttons present on error and wired to re-fetch with identical offset.
   - Load more errors preserve offset for subsequent retry.
4. History and tab navigation:
   - pushState on explicit tab clicks.
   - popstate handler (window.onpopstate and addEventListener) activates tab without duplicating history.
5. In-place stats update:
   - updateProfileStats updates stats, tab counts, and sidebar in-place.
   - Silent refresh does not wipe loaded tabs, reset scroll, or re-trigger feed loaders.
6. Top contributions fallback:
   - Derives top 2-3 items from publications (sorted by rating DESC, then date DESC) when topContributions is empty.
   - Displays #profileTopContributionsSection when items are derived.
7. Strict invariants:
   - Zero emojis across all files.
   - Zero em dashes across all files.
   - 100% offline-first.
"""

import os
import re
import subprocess
import unittest
import unicodedata

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")
HTML_PATH = os.path.join(FRONTEND_DIR, "profile.html")
PAGE_JS_PATH = os.path.join(FRONTEND_DIR, "js", "profile-page.js")
CSS_PATH = os.path.join(FRONTEND_DIR, "css", "profile.css")


class TestIssue186ProfileOverviewPaginationHistory(unittest.TestCase):
    """Automated test suite verifying Issue #186 implementation and invariants."""

    @classmethod
    def setUpClass(cls):
        with open(HTML_PATH, "r", encoding="utf-8") as f:
            cls.html = f.read()
        with open(PAGE_JS_PATH, "r", encoding="utf-8") as f:
            cls.page_js = f.read()
        with open(CSS_PATH, "r", encoding="utf-8") as f:
            cls.css = f.read()
        with open(__file__, "r", encoding="utf-8") as f:
            cls.test_py = f.read()

    # =========================================================================
    # 1. Safe Pagination Invariants
    # =========================================================================

    def test_safe_pagination_offset_updated_only_on_success(self):
        """Verify loadActivity, loadPublications, loadQuestions, loadAnswers update offset strictly on success."""
        # 1. loadActivity
        act_match = re.search(r"function loadActivity\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(act_match, "loadActivity function must exist")
        act_body = act_match.group(1)
        self.assertNotIn("activityOffset +=", act_body.split("fetch(")[0], "activityOffset must not be incremented before fetch")
        self.assertIn("activityOffset += newItems.length", act_body, "activityOffset must be incremented on successful fetch")

        # 2. loadPublications
        pub_match = re.search(r"function loadPublications\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(pub_match, "loadPublications function must exist")
        pub_body = pub_match.group(1)
        self.assertNotIn("pubOffset +=", pub_body.split("fetch(")[0], "pubOffset must not be incremented before fetch")
        self.assertIn("pubOffset += incoming.length", pub_body, "pubOffset must be incremented on successful fetch")

        # 3. loadQuestions
        quest_match = re.search(r"function loadQuestions\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(quest_match, "loadQuestions function must exist")
        quest_body = quest_match.group(1)
        self.assertNotIn("questOffset +=", quest_body.split("fetch(")[0], "questOffset must not be incremented before fetch")
        self.assertIn("questOffset += incoming.length", quest_body, "questOffset must be incremented on successful fetch")

        # 4. loadAnswers
        ans_match = re.search(r"function loadAnswers\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(ans_match, "loadAnswers function must exist")
        ans_body = ans_match.group(1)
        self.assertNotIn("ansOffset +=", ans_body.split("fetch(")[0], "ansOffset must not be incremented before fetch")
        self.assertIn("ansOffset += incoming.length", ans_body, "ansOffset must be incremented on successful fetch")

    def test_load_more_handlers_do_not_increment_offset_before_fetch(self):
        """Verify load more button click handlers removed premature offset += limit operations."""
        # Check btnProfileLoadMore
        self.assertNotIn(
            "activityOffset += activityLimit",
            self.page_js,
            "Premature activityOffset += activityLimit must be removed from click listener"
        )

        # Check btnProfileLoadMorePublications
        self.assertNotIn(
            "pubOffset += pubLimit",
            self.page_js,
            "Premature pubOffset += pubLimit must be removed from click listener"
        )

        # Check btnProfileLoadMoreQuestions
        self.assertNotIn(
            "questOffset += questLimit",
            self.page_js,
            "Premature questOffset += questLimit must be removed from click listener"
        )

        # Check btnProfileLoadMoreAnswers
        self.assertNotIn(
            "ansOffset += ansLimit",
            self.page_js,
            "Premature ansOffset += ansLimit must be removed from click listener"
        )

    # =========================================================================
    # 2. Race Condition & Sequence Token Protection
    # =========================================================================

    def test_sequence_counters_and_abort_controllers_defined(self):
        """Verify sequence tokens and abort controller variables exist for each feed."""
        tokens = [
            "actReqSeq",
            "pubReqSeq",
            "questReqSeq",
            "ansReqSeq",
            "actAbortCtrl",
            "pubAbortCtrl",
            "questAbortCtrl",
            "ansAbortCtrl"
        ]
        for token in tokens:
            self.assertRegex(
                self.page_js,
                rf"\b{token}\b",
                f"State variable {token} must be defined in profile-page.js"
            )

    def test_loaders_increment_sequence_and_ignore_outdated_responses(self):
        """Verify loaders increment sequence token before fetch and ignore superseded responses."""
        loaders = [
            ("loadActivity", "actReqSeq"),
            ("loadPublications", "pubReqSeq"),
            ("loadQuestions", "questReqSeq"),
            ("loadAnswers", "ansReqSeq")
        ]
        for fn_name, seq_name in loaders:
            pattern = rf"function {fn_name}\s*\([^\)]*\)\s*\{{([\s\S]*?)\n  \}}"
            match = re.search(pattern, self.page_js)
            self.assertIsNotNone(match, f"{fn_name} must be defined")
            body = match.group(1)

            # Pre-fetch sequence increment
            self.assertIn(f"++{seq_name}", body, f"{fn_name} must increment {seq_name} before request")

            # Superseded check in promise resolution
            self.assertRegex(
                body,
                rf"if\s*\([^)]*!==\s*{seq_name}\)\s*return;",
                f"{fn_name} must check and ignore superseded request responses"
            )

    def test_changing_filters_does_not_block_when_pending(self):
        """Verify that when append is false (filter/sort change), pending requests do not block new fetch."""
        loaders = [
            ("loadActivity", "isLoadingActivity"),
            ("loadPublications", "isLoadingPub"),
            ("loadQuestions", "isLoadingQuest"),
            ("loadAnswers", "isLoadingAns")
        ]
        for fn_name, flag_name in loaders:
            pattern = rf"function {fn_name}\s*\([^\)]*\)\s*\{{([\s\S]*?)\n  \}}"
            match = re.search(pattern, self.page_js)
            self.assertIsNotNone(match)
            body = match.group(1)

            # Block condition must check (append && isLoading...)
            self.assertRegex(
                body,
                rf"if\s*\(\s*append\s*&&\s*{flag_name}\s*\)\s*return;",
                f"{fn_name} must only block concurrent append requests, allowing filter changes to supersede"
            )

    # =========================================================================
    # 3. Distinct Error States and Retry Buttons
    # =========================================================================

    def test_distinct_error_states_and_retry_buttons_in_loaders(self):
        """Verify distinct error states with working retry buttons for all 4 feeds."""
        loaders_and_retry_ids = [
            ("loadActivity", "btnRetryActivity", "Ошибка загрузки ленты активности"),
            ("loadPublications", "btnRetryPublications", "Ошибка загрузки публикаций"),
            ("loadQuestions", "btnRetryQuestions", "Ошибка загрузки вопросов"),
            ("loadAnswers", "btnRetryAnswers", "Ошибка загрузки ответов")
        ]
        for fn_name, retry_id, err_text in loaders_and_retry_ids:
            pattern = rf"function {fn_name}\s*\([^\)]*\)\s*\{{([\s\S]*?)\n  \}}"
            match = re.search(pattern, self.page_js)
            self.assertIsNotNone(match)
            body = match.group(1)

            self.assertIn("profile-error-state", body, f"{fn_name} must render profile-error-state container")
            self.assertIn(retry_id, body, f"{fn_name} must render retry button #{retry_id}")
            self.assertIn(err_text, body, f"{fn_name} must render error message: {err_text}")
            self.assertIn(f"{fn_name}(userId, false)", body, f"Retry button must invoke {fn_name} on click")

    def test_error_state_css_classes_defined(self):
        """Verify CSS definitions for .profile-error-state, .profile-error-text, and .btn-profile-retry."""
        self.assertIn(".profile-error-state", self.css)
        self.assertIn(".profile-error-text", self.css)
        self.assertIn(".btn-profile-retry", self.css)
        self.assertIn(".btn-profile-retry:hover", self.css)

    # =========================================================================
    # 4. History and Tab Navigation
    # =========================================================================

    def test_tab_switching_uses_push_state(self):
        """Verify setActiveTab uses history.pushState when tab is changed by user."""
        set_tab_match = re.search(r"function setActiveTab\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(set_tab_match, "setActiveTab must exist")
        body = set_tab_match.group(1)

        self.assertIn("window.history.pushState", body, "setActiveTab must support window.history.pushState")
        self.assertIn("window.history.replaceState", body, "setActiveTab must preserve replaceState support")

    def test_popstate_handler_handles_navigation_without_duplication(self):
        """Verify popstate handler activates tab without pushing duplicate history entries."""
        self.assertIn("function handlePopState", self.page_js, "handlePopState must be defined")
        self.assertNotIn("window.onpopstate", self.page_js, "Redundant window.onpopstate must be removed")
        self.assertIn("window.addEventListener('popstate', handlePopState)", self.page_js, "popstate event listener must be registered")

        # Verify handlePopState invokes setActiveTab(tab, false)
        popstate_match = re.search(r"function handlePopState\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(popstate_match)
        pop_body = popstate_match.group(1)
        self.assertIn("setActiveTab(tab, false)", pop_body, "handlePopState must call setActiveTab with updateUrl=false")

    def test_tab_switching_with_different_params_invalidates_cache_and_triggers_fresh_load(self):
        """Verify switching between tabs with different query/filter parameters triggers fresh loads."""
        # 1. State variable tabLoadedState defined in profile-page.js
        self.assertIn("tabLoadedState", self.page_js, "tabLoadedState must be defined to track tab parameters")
        self.assertIn("areTabParamsEqual", self.page_js, "areTabParamsEqual helper must exist")
        self.assertIn("getCurrentTabParams", self.page_js, "getCurrentTabParams helper must exist")

        # 2. setActiveTab invalidates and reloads when parameters do not match
        set_tab_match = re.search(r"function setActiveTab\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(set_tab_match, "setActiveTab must exist")
        body = set_tab_match.group(1)
        self.assertIn("tabLoadedState.publications", body, "setActiveTab must check publications loaded parameters")
        self.assertIn("tabLoadedState.questions", body, "setActiveTab must check questions loaded parameters")
        self.assertIn("tabLoadedState.answers", body, "setActiveTab must check answers loaded parameters")
        self.assertIn("tabLoadedState.overview", body, "setActiveTab must check overview loaded parameters")

        # 3. handlePopState extracts all parameters and invalidates caches when changed
        popstate_match = re.search(r"function handlePopState\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(popstate_match, "handlePopState must exist")
        pop_body = popstate_match.group(1)
        self.assertIn("params.get('tab')", pop_body)
        self.assertIn("params.get('q')", pop_body)
        self.assertIn("params.get('sort')", pop_body)
        self.assertIn("params.get('topic')", pop_body)
        self.assertIn("params.get('status')", pop_body)
        self.assertIn("updateSearchInputUI", pop_body)
        self.assertIn("updatePubSortUI", pop_body)
        self.assertIn("updateQuestSortUI", pop_body)
        self.assertIn("updateQuestStatusUI", pop_body)
        self.assertIn("updateAnsFilterUI", pop_body)
        self.assertIn("updateTopicFilterUI", pop_body)

        # 4. Search query changes invalidate all tab caches
        self.assertIn("invalidateTabCaches", self.page_js, "invalidateTabCaches helper must exist")
        search_match = re.search(r"function setSearchQuery\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(search_match, "setSearchQuery function must exist")
        self.assertIn("invalidateTabCaches", search_match.group(1), "Changing search query must invalidate all tab caches")

        # 5. Dynamic Node.js contract test proving cache reuse vs fresh load
        node_script = """
const fs = require('fs');
const code = fs.readFileSync('""" + PAGE_JS_PATH + """', 'utf8');
const vm = require('vm');

let fetchCalls = [];
const mockFetch = (url, opts) => {
  fetchCalls.push(url);
  return Promise.resolve({
    ok: true,
    json: () => Promise.resolve({ success: true, items: [{ id: 'item_1' }], hasMore: false, activity: [{ id: 'act_1' }] })
  });
};

const domElements = {};
function getEl(id) {
  if (!domElements[id]) {
    domElements[id] = {
      id: id,
      classList: { toggle: () => {}, add: () => {}, remove: () => {} },
      setAttribute: () => {},
      removeAttribute: () => {},
      hasAttribute: () => false,
      getAttribute: () => '',
      style: {},
      innerHTML: '',
      textContent: '',
      addEventListener: () => {},
      querySelector: () => null
    };
  }
  return domElements[id];
}

const window = {
  console: console,
  URLSearchParams: URLSearchParams,
  URL: URL,
  location: { search: '?id=user_test', href: 'http://localhost/profile.html?id=user_test' },
  addEventListener: () => {},
  document: {
    documentElement: { setAttribute: () => {}, getAttribute: () => 'dark' },
    addEventListener: () => {},
    getElementById: getEl,
    querySelectorAll: () => []
  },
  localStorage: { getItem: () => null, setItem: () => {} },
  history: { pushState: () => {}, replaceState: () => {} },
  fetch: mockFetch
};
window.window = window;
vm.createContext(window);
vm.runInContext(code, window);

const api = window.SmartContractumProfilePage;
api.renderProfile({ id: 'user_test', publications: [], questions: [], answers: [] });

(async () => {
  await Promise.resolve();
  fetchCalls = [];

  // Step 1: Initial switch to publications
  api.setActiveTab('publications', false);
  await Promise.resolve();
  if (fetchCalls.length !== 1) {
    console.error('FAIL_STEP_1');
    process.exit(1);
  }

  // Step 2: Switch to questions
  api.setActiveTab('questions', false);
  await Promise.resolve();
  if (fetchCalls.length !== 2) {
    console.error('FAIL_STEP_2');
    process.exit(2);
  }

  // Step 3: Switch back to publications with unchanged parameters (cache hit, no fresh fetch)
  const countBeforeCached = fetchCalls.length;
  api.setActiveTab('publications', false);
  await Promise.resolve();
  if (fetchCalls.length !== countBeforeCached) {
    console.error('FAIL_STEP_3_CACHE_NOT_USED');
    process.exit(3);
  }

  // Step 4: Change sort via popstate to popular -> must trigger fresh load
  window.location.search = '?id=user_test&tab=publications&sort=popular';
  api.handlePopState({ state: { tab: 'publications', sort: 'popular' } });
  await Promise.resolve();
  if (fetchCalls.length !== countBeforeCached + 1) {
    console.error('FAIL_STEP_4_FRESH_LOAD_NOT_TRIGGERED');
    process.exit(4);
  }
  const lastUrl = fetchCalls[fetchCalls.length - 1];
  if (!lastUrl.includes('sort=popular')) {
    console.error('FAIL_STEP_4_URL_PARAM');
    process.exit(5);
  }

  // Step 5: Change search query -> must invalidate all tab caches and reload
  const countBeforeQuery = fetchCalls.length;
  api.setSearchQuery('audit', false);
  await Promise.resolve();
  if (fetchCalls.length !== countBeforeQuery + 1) {
    console.error('FAIL_STEP_5_QUERY_RELOAD');
    process.exit(6);
  }

  // Step 6: Switching to questions under new query must trigger fresh load with q=audit
  const countBeforeQuest = fetchCalls.length;
  api.setActiveTab('questions', false);
  await Promise.resolve();
  if (fetchCalls.length !== countBeforeQuest + 1) {
    console.error('FAIL_STEP_6_STALE_QUESTIONS_CACHE');
    process.exit(7);
  }
  const questUrl = fetchCalls[fetchCalls.length - 1];
  if (!questUrl.includes('q=audit')) {
    console.error('FAIL_STEP_6_QUERY_NOT_IN_URL');
    process.exit(8);
  }

  console.log('SUCCESS_CONTRACT_VERIFIED');
})();
"""
        proc = subprocess.run(
            ["node", "-e", node_script],
            capture_output=True,
            text=True
        )
        self.assertEqual(proc.returncode, 0, f"Node contract execution failed: {proc.stderr}")
        self.assertIn("SUCCESS_CONTRACT_VERIFIED", proc.stdout)

    # =========================================================================
    # 4.1 Search Query Handlers, Debounce, Keydown & Popstate Behavioral Tests
    # =========================================================================

    def test_search_competing_listeners_removed_and_unified_handlers_present(self):
        """Verify duplicate competing input listeners are removed and unified handlers are present."""
        # 1. Competing input listener calling setSearchQuery(..., false) must be removed
        self.assertNotIn(
            "setSearchQuery(e.target.value, false)",
            self.page_js,
            "Competing input listener calling setSearchQuery(..., false) must be removed"
        )

        # 2. searchDebounceTimer and triggerSearch must exist
        self.assertIn("searchDebounceTimer", self.page_js)
        self.assertIn("function triggerSearch", self.page_js)
        self.assertIn("triggerSearch: triggerSearch", self.page_js)
        self.assertIn("getSearchQuery:", self.page_js)

        # 3. Dedicated handlers for #profileSearchInput and #btnProfileSearchClear
        self.assertIn("document.getElementById('profileSearchInput')", self.page_js)
        self.assertIn("document.getElementById('btnProfileSearchClear')", self.page_js)
        self.assertIn("val.trim() ? 'flex' : 'none'", self.page_js)
        self.assertIn("e.key === 'Enter'", self.page_js)
        self.assertIn("e.key === 'Escape'", self.page_js)

        # 4. All tabs supported in setSearchQuery
        search_match = re.search(r"function setSearchQuery\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(search_match)
        body = search_match.group(1)
        self.assertIn("loadPublications(uid, false)", body)
        self.assertIn("loadQuestions(uid, false)", body)
        self.assertIn("loadAnswers(uid, false)", body)
        self.assertIn("loadComments(uid, false)", body)
        self.assertIn("loadActivity(uid, false)", body)

    def test_search_input_debounce_updates_url_and_history(self):
        """Verify search input debounces by 300ms, shows clear button, and updates history via pushState."""
        node_script = """
const fs = require('fs');
const code = fs.readFileSync('""" + PAGE_JS_PATH + """', 'utf8');
const vm = require('vm');

let fetchCalls = [];
const mockFetch = (url, opts) => {
  fetchCalls.push(url);
  return Promise.resolve({
    ok: true,
    json: () => Promise.resolve({ success: true, items: [{ id: 'item_1' }], hasMore: false, activity: [{ id: 'act_1' }] })
  });
};

const domElements = {};
function getEl(id) {
  if (!domElements[id]) {
    const listeners = {};
    domElements[id] = {
      id: id,
      value: '',
      classList: { toggle: () => {}, add: () => {}, remove: () => {} },
      setAttribute: () => {},
      removeAttribute: () => {},
      hasAttribute: () => false,
      getAttribute: () => '',
      style: {},
      innerHTML: '',
      textContent: '',
      addEventListener: (type, fn) => {
        if (!listeners[type]) listeners[type] = [];
        listeners[type].push(fn);
      },
      dispatchEvent: (event) => {
        const fns = listeners[event.type] || [];
        for (const fn of fns) {
          fn.call(domElements[id], event);
        }
      },
      querySelector: () => null,
      querySelectorAll: () => []
    };
  }
  return domElements[id];
}

const windowListeners = {};
const historyPushes = [];
const historyReplaces = [];

const window = {
  console: console,
  URLSearchParams: URLSearchParams,
  URL: URL,
  location: { search: '?id=user_test', href: 'http://localhost/profile.html?id=user_test' },
  addEventListener: (type, fn) => {
    if (!windowListeners[type]) windowListeners[type] = [];
    windowListeners[type].push(fn);
  },
  dispatchEvent: (event) => {
    const fns = windowListeners[event.type] || [];
    for (const fn of fns) {
      fn.call(window, event);
    }
  },
  document: {
    documentElement: { setAttribute: () => {}, getAttribute: () => 'dark' },
    addEventListener: () => {},
    getElementById: getEl,
    querySelectorAll: (sel) => {
      if (sel && sel.includes('profileSearchInput')) {
        return [getEl('profileSearchInput')];
      }
      return [];
    }
  },
  localStorage: { getItem: () => null, setItem: () => {} },
  history: {
    pushState: (state, title, url) => {
      historyPushes.push({ state, title, url });
      if (url) {
        window.location.href = url;
        const qIdx = url.indexOf('?');
        window.location.search = qIdx !== -1 ? url.substring(qIdx) : '';
      }
    },
    replaceState: (state, title, url) => {
      historyReplaces.push({ state, title, url });
      if (url) {
        window.location.href = url;
        const qIdx = url.indexOf('?');
        window.location.search = qIdx !== -1 ? url.substring(qIdx) : '';
      }
    }
  },
  fetch: mockFetch,
  setTimeout: setTimeout,
  clearTimeout: clearTimeout
};
window.window = window;
vm.createContext(window);
vm.runInContext(code, window);

const api = window.SmartContractumProfilePage;
api.renderProfile({ id: 'user_test', publications: [], questions: [], answers: [] });
api.initEventListeners();

(async () => {
  const inputEl = getEl('profileSearchInput');
  const clearBtn = getEl('btnProfileSearchClear');

  // Initial state check
  if (clearBtn.style.display === 'flex') {
    console.error('FAIL_INITIAL_CLEAR_BTN_VISIBLE');
    process.exit(1);
  }

  // Dispatch input event on #profileSearchInput
  inputEl.value = 'security';
  inputEl.dispatchEvent({ type: 'input' });

  // Clear button should immediately become visible
  if (clearBtn.style.display !== 'flex') {
    console.error('FAIL_CLEAR_BTN_NOT_FLEX');
    process.exit(2);
  }

  // Before 300ms, pushState must NOT have been called yet
  if (historyPushes.length !== 0) {
    console.error('FAIL_PREMATURE_PUSH_STATE');
    process.exit(3);
  }

  // Advance timer by waiting past 300ms debounce
  await new Promise(resolve => setTimeout(resolve, 350));

  // Verify pushState called with q=security
  if (historyPushes.length !== 1) {
    console.error('FAIL_PUSH_STATE_NOT_CALLED');
    process.exit(4);
  }
  const lastPush = historyPushes[historyPushes.length - 1];
  if (!lastPush.url || !lastPush.url.includes('q=security')) {
    console.error('FAIL_URL_MISSING_Q');
    process.exit(5);
  }
  if (!lastPush.state || lastPush.state.q !== 'security') {
    console.error('FAIL_STATE_MISSING_Q');
    process.exit(6);
  }
  if (api.getSearchQuery() !== 'security') {
    console.error('FAIL_ACTIVE_QUERY_MISMATCH');
    process.exit(7);
  }

  console.log('SUCCESS_SEARCH_DEBOUNCE');
})();
"""
        proc = subprocess.run(
            ["node", "-e", node_script],
            capture_output=True,
            text=True
        )
        self.assertEqual(proc.returncode, 0, f"Search debounce test failed: {proc.stderr}")
        self.assertIn("SUCCESS_SEARCH_DEBOUNCE", proc.stdout)

    def test_search_enter_and_escape_behavior(self):
        """Verify Enter immediately calls pushState and Escape clears query and removes from URL."""
        node_script = """
const fs = require('fs');
const code = fs.readFileSync('""" + PAGE_JS_PATH + """', 'utf8');
const vm = require('vm');

let fetchCalls = [];
const mockFetch = (url, opts) => {
  fetchCalls.push(url);
  return Promise.resolve({
    ok: true,
    json: () => Promise.resolve({ success: true, items: [{ id: 'item_1' }], hasMore: false, activity: [{ id: 'act_1' }] })
  });
};

const domElements = {};
function getEl(id) {
  if (!domElements[id]) {
    const listeners = {};
    domElements[id] = {
      id: id,
      value: '',
      classList: { toggle: () => {}, add: () => {}, remove: () => {} },
      setAttribute: () => {},
      removeAttribute: () => {},
      hasAttribute: () => false,
      getAttribute: () => '',
      style: {},
      innerHTML: '',
      textContent: '',
      addEventListener: (type, fn) => {
        if (!listeners[type]) listeners[type] = [];
        listeners[type].push(fn);
      },
      dispatchEvent: (event) => {
        const fns = listeners[event.type] || [];
        for (const fn of fns) {
          fn.call(domElements[id], event);
        }
      },
      querySelector: () => null,
      querySelectorAll: () => []
    };
  }
  return domElements[id];
}

const windowListeners = {};
const historyPushes = [];

const window = {
  console: console,
  URLSearchParams: URLSearchParams,
  URL: URL,
  location: { search: '?id=user_test', href: 'http://localhost/profile.html?id=user_test' },
  addEventListener: (type, fn) => {
    if (!windowListeners[type]) windowListeners[type] = [];
    windowListeners[type].push(fn);
  },
  dispatchEvent: (event) => {
    const fns = windowListeners[event.type] || [];
    for (const fn of fns) {
      fn.call(window, event);
    }
  },
  document: {
    documentElement: { setAttribute: () => {}, getAttribute: () => 'dark' },
    addEventListener: () => {},
    getElementById: getEl,
    querySelectorAll: (sel) => {
      if (sel && sel.includes('profileSearchInput')) {
        return [getEl('profileSearchInput')];
      }
      return [];
    }
  },
  localStorage: { getItem: () => null, setItem: () => {} },
  history: {
    pushState: (state, title, url) => {
      historyPushes.push({ state, title, url });
      if (url) {
        window.location.href = url;
        const qIdx = url.indexOf('?');
        window.location.search = qIdx !== -1 ? url.substring(qIdx) : '';
      }
    },
    replaceState: () => {}
  },
  fetch: mockFetch,
  setTimeout: setTimeout,
  clearTimeout: clearTimeout
};
window.window = window;
vm.createContext(window);
vm.runInContext(code, window);

const api = window.SmartContractumProfilePage;
api.renderProfile({ id: 'user_test', publications: [], questions: [], answers: [] });
api.initEventListeners();

(async () => {
  const inputEl = getEl('profileSearchInput');
  const clearBtn = getEl('btnProfileSearchClear');

  // Step 1: Type query and press Enter (immediate pushState without waiting 300ms)
  let prevented = false;
  inputEl.value = 'blockchain';
  inputEl.dispatchEvent({
    type: 'keydown',
    key: 'Enter',
    preventDefault: () => { prevented = true; }
  });

  if (!prevented) {
    console.error('FAIL_ENTER_NOT_PREVENTED');
    process.exit(1);
  }
  if (historyPushes.length !== 1) {
    console.error('FAIL_ENTER_IMMEDIATE_PUSH_COUNT');
    process.exit(2);
  }
  if (!historyPushes[0].url.includes('q=blockchain')) {
    console.error('FAIL_ENTER_URL_PARAM');
    process.exit(3);
  }
  if (api.getSearchQuery() !== 'blockchain') {
    console.error('FAIL_ENTER_ACTIVE_QUERY');
    process.exit(4);
  }

  // Step 2: Press Escape while value is present
  prevented = false;
  inputEl.dispatchEvent({
    type: 'keydown',
    key: 'Escape',
    preventDefault: () => { prevented = true; }
  });

  if (!prevented) {
    console.error('FAIL_ESCAPE_NOT_PREVENTED');
    process.exit(5);
  }
  if (inputEl.value !== '') {
    console.error('FAIL_ESCAPE_VALUE_NOT_CLEARED');
    process.exit(6);
  }
  if (clearBtn.style.display !== 'none') {
    console.error('FAIL_ESCAPE_CLEAR_BTN_NOT_HIDDEN');
    process.exit(7);
  }
  if (api.getSearchQuery() !== '') {
    console.error('FAIL_ESCAPE_ACTIVE_QUERY_NOT_CLEARED');
    process.exit(8);
  }
  const lastPushAfterEscape = historyPushes[historyPushes.length - 1];
  if (lastPushAfterEscape.url.includes('q=')) {
    console.error('FAIL_ESCAPE_URL_CONTAINS_Q');
    process.exit(9);
  }

  // Step 3: Clear button click handler test
  inputEl.value = 'smartcontract';
  inputEl.dispatchEvent({ type: 'input' });
  if (clearBtn.style.display !== 'flex') {
    console.error('FAIL_CLEAR_BTN_NOT_SHOWN');
    process.exit(10);
  }
  clearBtn.dispatchEvent({ type: 'click' });
  if (inputEl.value !== '') {
    console.error('FAIL_CLEAR_CLICK_INPUT_NOT_EMPTY');
    process.exit(11);
  }
  if (clearBtn.style.display !== 'none') {
    console.error('FAIL_CLEAR_CLICK_BTN_NOT_HIDDEN');
    process.exit(12);
  }
  if (api.getSearchQuery() !== '') {
    console.error('FAIL_CLEAR_CLICK_QUERY_NOT_EMPTY');
    process.exit(13);
  }
  const lastPushAfterClick = historyPushes[historyPushes.length - 1];
  if (lastPushAfterClick.url.includes('q=')) {
    console.error('FAIL_CLEAR_CLICK_URL_CONTAINS_Q');
    process.exit(14);
  }

  console.log('SUCCESS_ENTER_ESCAPE');
})();
"""
        proc = subprocess.run(
            ["node", "-e", node_script],
            capture_output=True,
            text=True
        )
        self.assertEqual(proc.returncode, 0, f"Search Enter/Escape test failed: {proc.stderr}")
        self.assertIn("SUCCESS_ENTER_ESCAPE", proc.stdout)

    def test_popstate_restores_search_query_and_ui(self):
        """Verify popstate restores search query in state, updates search input value and clear button, and reloads active tab."""
        node_script = """
const fs = require('fs');
const code = fs.readFileSync('""" + PAGE_JS_PATH + """', 'utf8');
const vm = require('vm');

let fetchCalls = [];
const mockFetch = (url, opts) => {
  fetchCalls.push(url);
  return Promise.resolve({
    ok: true,
    json: () => Promise.resolve({ success: true, items: [{ id: 'item_1' }], hasMore: false, activity: [{ id: 'act_1' }] })
  });
};

const domElements = {};
function getEl(id) {
  if (!domElements[id]) {
    const listeners = {};
    domElements[id] = {
      id: id,
      value: '',
      classList: { toggle: () => {}, add: () => {}, remove: () => {} },
      setAttribute: () => {},
      removeAttribute: () => {},
      hasAttribute: () => false,
      getAttribute: () => '',
      style: {},
      innerHTML: '',
      textContent: '',
      addEventListener: (type, fn) => {
        if (!listeners[type]) listeners[type] = [];
        listeners[type].push(fn);
      },
      dispatchEvent: (event) => {
        const fns = listeners[event.type] || [];
        for (const fn of fns) {
          fn.call(domElements[id], event);
        }
      },
      querySelector: () => null,
      querySelectorAll: () => []
    };
  }
  return domElements[id];
}

const windowListeners = {};
const window = {
  console: console,
  URLSearchParams: URLSearchParams,
  URL: URL,
  location: { search: '?id=user_test', href: 'http://localhost/profile.html?id=user_test' },
  addEventListener: (type, fn) => {
    if (!windowListeners[type]) windowListeners[type] = [];
    windowListeners[type].push(fn);
  },
  dispatchEvent: (event) => {
    const fns = windowListeners[event.type] || [];
    for (const fn of fns) {
      fn.call(window, event);
    }
  },
  document: {
    documentElement: { setAttribute: () => {}, getAttribute: () => 'dark' },
    addEventListener: () => {},
    getElementById: getEl,
    querySelectorAll: (sel) => {
      if (sel && sel.includes('profileSearchInput')) {
        return [getEl('profileSearchInput')];
      }
      return [];
    }
  },
  localStorage: { getItem: () => null, setItem: () => {} },
  history: { pushState: () => {}, replaceState: () => {} },
  fetch: mockFetch,
  setTimeout: setTimeout,
  clearTimeout: clearTimeout
};
window.window = window;
vm.createContext(window);
vm.runInContext(code, window);

const api = window.SmartContractumProfilePage;
api.renderProfile({ id: 'user_test', publications: [], questions: [], answers: [] });
api.initEventListeners();

(async () => {
  const inputEl = getEl('profileSearchInput');
  const clearBtn = getEl('btnProfileSearchClear');
  fetchCalls = [];

  // Fire popstate with state { tab: 'overview', q: 'audit' }
  window.dispatchEvent({ type: 'popstate', state: { tab: 'overview', q: 'audit' } });
  await Promise.resolve();

  // Verify search query updated
  if (api.getSearchQuery() !== 'audit') {
    console.error('FAIL_POPSTATE_QUERY_NOT_AUDIT: ' + api.getSearchQuery());
    process.exit(1);
  }

  // Verify input element value updated
  if (inputEl.value !== 'audit') {
    console.error('FAIL_POPSTATE_INPUT_NOT_AUDIT: ' + inputEl.value);
    process.exit(2);
  }

  // Verify clear button shown
  if (clearBtn.style.display !== 'flex') {
    console.error('FAIL_POPSTATE_CLEAR_BTN_NOT_FLEX');
    process.exit(3);
  }

  // Verify active tab data reload triggered with q=audit
  if (fetchCalls.length === 0) {
    console.error('FAIL_POPSTATE_NO_FETCH');
    process.exit(4);
  }
  const lastFetch = fetchCalls[fetchCalls.length - 1];
  if (!lastFetch.includes('q=audit')) {
    console.error('FAIL_POPSTATE_FETCH_MISSING_Q: ' + lastFetch);
    process.exit(5);
  }

  // Now fire popstate clearing query
  window.dispatchEvent({ type: 'popstate', state: { tab: 'overview', q: '' } });
  await Promise.resolve();

  if (api.getSearchQuery() !== '') {
    console.error('FAIL_POPSTATE_QUERY_NOT_CLEARED');
    process.exit(6);
  }
  if (inputEl.value !== '') {
    console.error('FAIL_POPSTATE_INPUT_NOT_CLEARED');
    process.exit(7);
  }
  if (clearBtn.style.display !== 'none') {
    console.error('FAIL_POPSTATE_CLEAR_BTN_NOT_NONE');
    process.exit(8);
  }

  console.log('SUCCESS_POPSTATE_RESTORES_QUERY');
})();
"""
        proc = subprocess.run(
            ["node", "-e", node_script],
            capture_output=True,
            text=True
        )
        self.assertEqual(proc.returncode, 0, f"Popstate search query restore test failed: {proc.stderr}")
        self.assertIn("SUCCESS_POPSTATE_RESTORES_QUERY", proc.stdout)

    # =========================================================================
    # 5. In-Place Stats Update
    # =========================================================================

    def test_update_profile_stats_function_defined_and_exported(self):
        """Verify updateProfileStats is defined, handles all stats, and is exported."""
        self.assertRegex(self.page_js, r"function updateProfileStats\s*\(", "updateProfileStats function must be defined")
        self.assertIn("updateProfileStats: updateProfileStats", self.page_js, "updateProfileStats must be exported")

        match = re.search(r"function updateProfileStats\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(match)
        body = match.group(1)

        # Check in-place updating of key elements
        self.assertIn("profileStatRating", body)
        self.assertIn("profileStatFollowers", body)
        self.assertIn("profileStatPublications", body)
        self.assertIn("profileStatQuestions", body)
        self.assertIn("profileStatAnswers", body)
        self.assertIn("profileStatSolutions", body)
        self.assertIn("tabCountPublications", body)
        self.assertIn("tabCountQuestions", body)
        self.assertIn("tabCountAnswers", body)

    def test_load_profile_silent_refresh_does_not_wipe_tabs(self):
        """Verify loadProfile with isSilentRefresh updates stats only without re-rendering or wiping tabs."""
        match = re.search(r"function loadProfile\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(match)
        body = match.group(1)

        self.assertIn("if (isSilentRefresh && currentProfile)", body)
        self.assertIn("updateProfileStats(", body)
        self.assertIn("return;", body, "Silent refresh must return immediately after updating stats")

    # =========================================================================
    # 6. Top Contributions Fallback
    # =========================================================================

    def test_top_contributions_fallback_logic(self):
        """Verify renderTopContributions derives top 2-3 items from publications when topContributions is empty."""
        match = re.search(r"function renderTopContributions\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(match, "renderTopContributions must exist")
        body = match.group(1)

        # Fallback inspection
        self.assertIn("fallbackPubs", body, "renderTopContributions must accept fallbackPubs")
        self.assertIn("candidates.sort", body, "Fallback items must be sorted")
        self.assertIn("candidates.slice(0, 3)", body, "Must pick top 2-3 items from fallback publications")
        self.assertIn("sec.style.display = 'block'", body)
        self.assertIn("sec.style.display = 'none'", body)

    def test_render_profile_supplies_fallback_publications_to_top_contributions(self):
        """Verify renderProfile passes fallback publications to renderTopContributions."""
        match = re.search(r"function renderProfile\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(match)
        body = match.group(1)

        self.assertRegex(
            body,
            r"renderTopContributions\(\s*p\.topContributions\s*\|\|\s*\[\]\s*,\s*p\.publications",
            "renderProfile must pass publications as fallback to renderTopContributions"
        )

    # =========================================================================
    # 7. Module Exports and Global API
    # =========================================================================

    def test_global_exports_include_issue_186_enhancements(self):
        """Verify window.SmartContractumProfilePage exports all required methods."""
        export_match = re.search(r"window\.SmartContractumProfilePage\s*=\s*\{([\s\S]*?)\n  \};", self.page_js)
        self.assertIsNotNone(export_match)
        exports = export_match.group(1)

        required = [
            "loadActivity",
            "loadPublications",
            "loadQuestions",
            "loadAnswers",
            "updateProfileStats",
            "handlePopState",
            "renderTopContributions",
            "getOffsets",
            "getSeqTokens",
            "getActiveTab"
        ]
        for r in required:
            self.assertIn(r, exports, f"Export {r} must be present in window.SmartContractumProfilePage")

    # =========================================================================
    # 8. Strict Invariants: Zero Emojis, Zero Em Dashes, Offline-First
    # =========================================================================

    def test_zero_emojis(self):
        """Verify zero emojis in all modified files."""
        for path, content in [
            ("profile.html", self.html),
            ("profile-page.js", self.page_js),
            ("profile.css", self.css),
            (__file__, self.test_py)
        ]:
            emojis = [c for c in content if "EMOJI" in unicodedata.name(c, "")]
            self.assertEqual(len(emojis), 0, f"Found emojis in {path}: {emojis}")

    def test_zero_em_dashes(self):
        """Verify zero em dashes in all modified files."""
        em_dash = chr(8212)
        for path, content in [
            ("profile.html", self.html),
            ("profile-page.js", self.page_js),
            ("profile.css", self.css),
            (__file__, self.test_py)
        ]:
            self.assertNotIn(em_dash, content, f"Found em dash in {path}")

    def test_offline_first_integrity(self):
        """Verify 100% offline-first architecture with no external CDNs or remote URLs."""
        for path, content in [
            ("profile.html", self.html),
            ("profile-page.js", self.page_js),
            ("profile.css", self.css)
        ]:
            # Disallow external CDNs
            for cdn in ["cdnjs", "unpkg", "jsdelivr", "googleapis.com", "gstatic.com"]:
                self.assertNotIn(cdn, content, f"External CDN {cdn} detected in {path}")


if __name__ == "__main__":
    unittest.main()
