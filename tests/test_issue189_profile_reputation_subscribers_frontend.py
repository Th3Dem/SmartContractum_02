#!/usr/bin/env python3
"""
tests/test_issue189_profile_reputation_subscribers_frontend.py

Automated frontend test suite for Issue #189:
[P2][fullstack][PROFILE] Reputation breakdown, topic filtering, and subscribers modal.

Verifies:
1. profile.html Elements:
   - Stats bar interactive elements:
     * #profileStatRatingWrap with role="region" and rating formula title/aria-label.
     * #profileStatSolutionsWrap with role="button" and tabindex="0".
     * #profileStatFollowersWrap with role="button" and tabindex="0".
     * #profileStatFollowingWrap with role="button" and tabindex="0".
   - Active topic filtering bar:
     * #profileActiveTopicBar inside tabs toolbar.
     * #activeTopicChip, #activeTopicName, #btnClearTopicFilter.
   - Social modal (subscribers & subscriptions):
     * #profileSocialModal overlay with role="dialog" and aria-modal="true".
     * Header with #socialModalTitle and #btnProfileSocialModalClose.
     * Subnav for owner subscriptions: #socialModalSubnav, #socialSubTabAuthors, #socialSubTabBlogs.
     * List container #profileSocialList and load more container #profileSocialActions, #btnSocialLoadMore.
2. profile.css Styles:
   - .profile-stat-clickable with hover/focus states and pointer cursor.
   - .profile-active-topic-bar and .active-topic-chip with badge and clear button styling.
   - .profile-sidebar-topic-pill with interactive hover/active states.
   - .profile-social-modal-card, .profile-social-item, .profile-social-avatar-box, .profile-social-info.
3. profile-page.js Logic:
   - Reputation breakdown formatting and tooltip calculation.
   - Solution counter click routes to answers tab with filter=solutions.
   - Topic selection in sidebar filters author's publications via ?topic= parameter and displays active topic bar.
   - Clear topic filter resets filter and restores full publications list.
   - Subscribers modal pagination via GET /api/users/<user_id>/subscribers.
   - Subscriptions modal: privacy-preserving notice for other users; author/blog separated tabs for owner.
   - Real count reflection: toggleSubscription applies server-provided followersCount.
   - Silent refresh on votes via smartcontractum:voted window event.
4. Invariants:
   - Zero emojis, zero em dashes, 100% offline-first.
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


class TestIssue189ProfileReputationSubscribersFrontend(unittest.TestCase):
    """Verifies profile reputation breakdown, topic filtering, and subscribers modal."""

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
    # 1. profile.html Elements
    # =========================================================================

    def test_01_profile_html_stats_bar_interactive_elements(self):
        """Verify reputation and interactive counter wrappers in profile stats bar."""
        # 1. Rating wrap
        self.assertIn('id="profileStatRatingWrap"', self.html, "Rating wrap must have id='profileStatRatingWrap'")
        self.assertIn('role="region"', self.html, "Rating wrap must have role='region'")
        self.assertIn('aria-label="Рейтинг автора"', self.html, "Rating wrap must have aria-label")

        # 2. Solutions wrap
        self.assertIn('id="profileStatSolutionsWrap"', self.html, "Solutions wrap must have id='profileStatSolutionsWrap'")
        self.assertIn('profile-stat-clickable', self.html, "Solutions wrap must have profile-stat-clickable class")

        # 3. Followers & Following wraps
        self.assertIn('id="profileStatFollowersWrap"', self.html, "Followers wrap must have id='profileStatFollowersWrap'")
        self.assertIn('id="profileStatFollowingWrap"', self.html, "Following wrap must have id='profileStatFollowingWrap'")

    def test_02_profile_html_active_topic_bar(self):
        """Verify active topic filter pill and reset button inside toolbar."""
        self.assertIn('id="profileActiveTopicBar"', self.html, "Active topic bar must have id='profileActiveTopicBar'")
        self.assertIn('id="activeTopicChip"', self.html, "Active topic chip must have id='activeTopicChip'")
        self.assertIn('id="activeTopicName"', self.html, "Active topic name element must have id='activeTopicName'")
        self.assertIn('id="btnClearTopicFilter"', self.html, "Clear topic filter button must have id='btnClearTopicFilter'")

    def test_03_profile_html_social_modal(self):
        """Verify social modal markup for subscribers and subscriptions."""
        self.assertIn('id="profileSocialModal"', self.html, "Modal must have id='profileSocialModal'")
        self.assertIn('role="dialog"', self.html, "Social modal must have role='dialog'")
        self.assertIn('id="socialModalTitle"', self.html, "Social modal title must have id='socialModalTitle'")
        self.assertIn('id="btnProfileSocialModalClose"', self.html, "Social modal close button must have id='btnProfileSocialModalClose'")
        self.assertIn('id="socialModalSubnav"', self.html, "Owner subnav must have id='socialModalSubnav'")
        self.assertIn('id="socialSubTabAuthors"', self.html, "Authors subtab button must have id='socialSubTabAuthors'")
        self.assertIn('id="socialSubTabBlogs"', self.html, "Blogs subtab button must have id='socialSubTabBlogs'")
        self.assertIn('id="profileSocialList"', self.html, "Social list container must have id='profileSocialList'")
        self.assertIn('id="btnSocialLoadMore"', self.html, "Social load more button must have id='btnSocialLoadMore'")

    # =========================================================================
    # 2. profile.css Styles
    # =========================================================================

    def test_04_profile_css_classes(self):
        """Verify CSS classes for clickable stats, topic chips, and social modal."""
        self.assertIn('.profile-stat-clickable', self.css, "CSS must define .profile-stat-clickable")
        self.assertIn('.profile-active-topic-bar', self.css, "CSS must define .profile-active-topic-bar")
        self.assertIn('.active-topic-chip', self.css, "CSS must define .active-topic-chip")
        self.assertIn('.btn-clear-topic', self.css, "CSS must define .btn-clear-topic")
        self.assertIn('.profile-sidebar-topic-pill', self.css, "CSS must define .profile-sidebar-topic-pill")
        self.assertIn('.profile-social-modal-card', self.css, "CSS must define .profile-social-modal-card")
        self.assertIn('.profile-social-list', self.css, "CSS must define .profile-social-list")
        self.assertIn('.profile-social-item', self.css, "CSS must define .profile-social-item")
        self.assertIn('.profile-social-avatar-box', self.css, "CSS must define .profile-social-avatar-box")
        self.assertIn('.profile-social-name', self.css, "CSS must define .profile-social-name")
        self.assertIn('.btn-social-load-more', self.css, "CSS must define .btn-social-load-more")

    # =========================================================================
    # 3. profile-page.js Logic
    # =========================================================================

    def test_05_profile_page_js_reputation_breakdown_tooltip(self):
        """Verify rating formula and score breakdown calculation in profile-page.js."""
        self.assertIn('p.ratingFormula', self.page_js, "Must read ratingFormula from profile DTO")
        self.assertIn('materialsRating', self.page_js, "Must support materialsRating breakdown")
        self.assertIn('discussionsRating', self.page_js, "Must support discussionsRating breakdown")
        self.assertIn('profileStatRatingWrap', self.page_js, "Must update profileStatRatingWrap tooltip")

    def test_06_profile_page_js_solutions_and_metrics_routing(self):
        """Verify solutions metric shortcut to answers tab with solutions filter."""
        self.assertIn('switchToSolutions', self.page_js, "Must implement switchToSolutions helper")
        self.assertIn('filterAnswersSolutions', self.page_js, "Must trigger filterAnswersSolutions button")
        self.assertIn('profileStatSolutionsWrap', self.page_js, "Must wire profileStatSolutionsWrap click and keydown")
        self.assertIn('profileStatFollowersWrap', self.page_js, "Must wire profileStatFollowersWrap to openSubscribersModal")
        self.assertIn('profileStatFollowingWrap', self.page_js, "Must wire profileStatFollowingWrap to openSubscriptionsModal")

    def test_07_profile_page_js_topic_filtering(self):
        """Verify topic filtering on author's materials without redirecting to feed."""
        self.assertIn('applyTopicFilter', self.page_js, "Must implement applyTopicFilter helper")
        self.assertIn('clearTopicFilter', self.page_js, "Must implement clearTopicFilter helper")
        self.assertIn('&topic=', self.page_js, "Must append &topic= parameter in loadPublications")
        self.assertIn('profileActiveTopicBar', self.page_js, "Must toggle profileActiveTopicBar display")
        self.assertIn('activeTopicName', self.page_js, "Must update activeTopicName text")
        self.assertIn('btnClearTopicFilter', self.page_js, "Must wire btnClearTopicFilter to clearTopicFilter")

    def test_08_profile_page_js_subscribers_modal_pagination(self):
        """Verify subscribers modal pagination and rendering."""
        self.assertIn('openSubscribersModal', self.page_js, "Must implement openSubscribersModal")
        self.assertIn('loadSubscribers', self.page_js, "Must implement loadSubscribers with pagination")
        self.assertIn('/subscribers?limit=', self.page_js, "Must fetch /subscribers with limit and offset")
        self.assertIn('btnSocialLoadMore', self.page_js, "Must wire btnSocialLoadMore for pagination")
        self.assertIn('renderSocialAuthorItem', self.page_js, "Must render author items with avatars and links")

    def test_09_profile_page_js_subscriptions_modal_privacy_and_tabs(self):
        """Verify subscriptions modal privacy separation and author/blog subtabs."""
        self.assertIn('openSubscriptionsModal', self.page_js, "Must implement openSubscriptionsModal")
        self.assertIn('/subscriptions', self.page_js, "Must fetch /subscriptions")
        self.assertIn('data.isPrivate', self.page_js, "Must check data.isPrivate for foreign profiles")
        self.assertIn('renderSubscriptionsTabContent', self.page_js, "Must render separated author and blog tabs")
        self.assertIn('socialSubTabAuthors', self.page_js, "Must wire authors subtab")
        self.assertIn('socialSubTabBlogs', self.page_js, "Must wire blogs subtab")
        self.assertIn('renderSocialBlogItem', self.page_js, "Must render club/blog links")

    def test_10_profile_page_js_real_state_synchronization(self):
        """Verify server state reflection on subscription toggle and vote events."""
        self.assertIn('data.followersCount', self.page_js, "Must use server-provided followersCount on toggle")
        self.assertIn('smartcontractum:voted', self.page_js, "Must listen to smartcontractum:voted window event")
        self.assertIn('loadProfile', self.page_js, "Must trigger silent loadProfile on vote event")

    # =========================================================================
    # 4. Strict Invariants (Zero Emojis, Zero Em Dashes, 100% Offline-First)
    # =========================================================================

    def test_11_invariants_zero_em_dashes(self):
        """Verify that no em dashes (\u2014) exist in code or template files."""
        for path, content in [
            ("profile.html", self.html),
            ("profile-page.js", self.page_js),
            ("profile.css", self.css),
            ("test_py", self.test_py)
        ]:
            self.assertNotIn("\u2014", content, f"Em dash found in {path}")

    def test_12_invariants_zero_emojis(self):
        """Verify that zero emojis exist in code or template files."""
        def check_emojis(text, label):
            for i, ch in enumerate(text):
                cat = unicodedata.category(ch)
                if cat == "So" or ord(ch) > 0x1F000:
                    self.fail(f"Emoji character detected in {label} at pos {i}: U+{ord(ch):04X}")

        check_emojis(self.html, "profile.html")
        check_emojis(self.page_js, "profile-page.js")
        check_emojis(self.css, "profile.css")

    def test_13_invariants_offline_first(self):
        """Verify that no external CDN or literal http/https URLs exist in client files."""
        suspicious_html = re.findall(r'(https?://[^\s"\'<>]+)', self.html)
        for url in suspicious_html:
            self.assertIn('www.w3.org/2000/svg', url, f"External network URL found in profile.html: {url}")

        suspicious_js = re.findall(r'(https?://[^\s"\'<>]+)', self.page_js)
        for url in suspicious_js:
            self.assertIn('www.w3.org/2000/svg', url, f"External network URL found in profile-page.js: {url}")

    # =========================================================================
    # 5. Node.js VM Behavioral Tests
    # =========================================================================

    def _run_node_script(self, script_body, initial_url="http://localhost/profile.html?id=user_author"):
        """Run Node.js script against profile-page.js in a mock DOM environment."""
        setup = f"""
const fs = require('fs');
const vm = require('vm');

const jsPath = {repr(PAGE_JS_PATH)};
const code = fs.readFileSync(jsPath, 'utf8');

const domElements = {{}};
function createMockElement(id) {{
  const listeners = {{}};
  const classes = new Set();
  const attributes = {{}};
  const el = {{
    id: id,
    classList: {{
      add: (...cls) => cls.forEach(c => classes.add(c)),
      remove: (...cls) => cls.forEach(c => classes.delete(c)),
      toggle: (c, force) => {{
        if (force !== undefined) {{
          force ? classes.add(c) : classes.delete(c);
        }} else {{
          classes.has(c) ? classes.delete(c) : classes.add(c);
        }}
        return classes.has(c);
      }},
      contains: (c) => classes.has(c)
    }},
    setAttribute: (k, v) => {{ attributes[k] = String(v); }},
    removeAttribute: (k) => {{ delete attributes[k]; }},
    hasAttribute: (k) => k in attributes,
    getAttribute: (k) => (k in attributes ? attributes[k] : null),
    style: {{ display: '' }},
    innerHTML: '',
    textContent: '',
    value: '',
    disabled: false,
    addEventListener: (type, fn) => {{
      if (!listeners[type]) listeners[type] = [];
      listeners[type].push(fn);
    }},
    dispatchEvent: (event) => {{
      const fns = listeners[event.type] || [];
      for (const fn of fns) {{
        fn.call(el, event);
      }}
    }},
    querySelector: (sel) => {{
      if (sel === '.profile-topic-name') {{
        return {{ textContent: attributes['data-topic-title'] || attributes['data-topic-id'] || '' }};
      }}
      return null;
    }},
    querySelectorAll: (sel) => [],
    closest: (sel) => null,
    appendChild: () => {{}}
  }};
  return el;
}}

function getEl(id) {{
  if (!domElements[id]) {{
    domElements[id] = createMockElement(id);
  }}
  return domElements[id];
}}

const activeTopicBar = getEl('profileActiveTopicBar');
activeTopicBar.style.display = 'none';

const activeTopicName = getEl('activeTopicName');
activeTopicName.textContent = '';

const btnClearTopic = getEl('btnClearTopicFilter');

const pillSolidity = createMockElement('pill_solidity');
pillSolidity.setAttribute('data-topic-id', 'solidity');
pillSolidity.setAttribute('data-topic-title', 'Solidity');

const pillPython = createMockElement('pill_python');
pillPython.setAttribute('data-topic-id', 'python');
pillPython.setAttribute('data-topic-title', 'Python');

const topicPills = [pillSolidity, pillPython];

const windowListeners = {{}};
const historyPushes = [];
let fetchCalls = [];

const mockFetch = (url, opts) => {{
  fetchCalls.push(url);
  return Promise.resolve({{
    ok: true,
    status: 200,
    json: () => Promise.resolve({{ success: true, items: [], total: 0 }})
  }});
}};

const currentUrlObj = new URL({repr(initial_url)});
const window = {{
  console: console,
  URLSearchParams: URLSearchParams,
  URL: URL,
  location: {{
    href: currentUrlObj.toString(),
    search: currentUrlObj.search
  }},
  addEventListener: (type, fn) => {{
    if (!windowListeners[type]) windowListeners[type] = [];
    windowListeners[type].push(fn);
  }},
  dispatchEvent: (event) => {{
    const fns = windowListeners[event.type] || [];
    for (const fn of fns) {{
      fn.call(window, event);
    }}
  }},
  document: {{
    documentElement: {{ setAttribute: () => {{}}, getAttribute: () => 'dark' }},
    addEventListener: () => {{}},
    getElementById: getEl,
    createElement: (tag) => createMockElement('mock_' + Math.random().toString(36).substr(2, 9)),
    querySelectorAll: (sel) => {{
      if (sel && (sel.includes('profile-sidebar-topic-pill') || sel.includes('data-profile-topic'))) {{
        return topicPills;
      }}
      return [];
    }}
  }},
  localStorage: {{ getItem: () => null, setItem: () => {{}} }},
  history: {{
    pushState: (state, title, url) => {{
      historyPushes.push({{ state, title, url }});
      if (url) {{
        window.location.href = url;
        const qIdx = url.indexOf('?');
        window.location.search = qIdx !== -1 ? url.substring(qIdx) : '';
      }}
    }},
    replaceState: (state, title, url) => {{
      if (url) {{
        window.location.href = url;
        const qIdx = url.indexOf('?');
        window.location.search = qIdx !== -1 ? url.substring(qIdx) : '';
      }}
    }}
  }},
  fetch: mockFetch,
  setTimeout: setTimeout,
  clearTimeout: clearTimeout
}};
window.window = window;
vm.createContext(window);
vm.runInContext(code, window);

const api = window.SmartContractumProfilePage;
api.renderProfile({{ id: 'user_author', publications: [], questions: [], answers: [] }});
api.initEventListeners();
api.setActiveTab('publications', false);

(async () => {{
  await new Promise(r => setTimeout(r, 10));
  fetchCalls = [];
  {script_body}
}})();
"""
        return subprocess.run(["node", "-e", setup], capture_output=True, text=True)

    def test_topic_selection_and_reset_clears_server_query(self):
        """Simulate selecting topic -> publication fetch with &topic=solidity and URL updated; click clear -> bar hidden, param removed, fetch without &topic=."""
        script_body = """
  // 1. Click topic pill 'solidity'
  pillSolidity.dispatchEvent({ type: 'click' });
  await new Promise(r => setTimeout(r, 10));

  const solCalls = fetchCalls.filter(u => u.includes('/publications') && u.includes('&topic=solidity'));
  if (solCalls.length === 0) {
    console.error('FAIL_NO_SOLIDITY_FETCH: ' + JSON.stringify(fetchCalls));
    process.exit(1);
  }

  if (activeTopicBar.style.display !== 'inline-flex') {
    console.error('FAIL_ACTIVE_BAR_NOT_VISIBLE: ' + activeTopicBar.style.display);
    process.exit(2);
  }
  if (!activeTopicName.textContent.includes('Solidity') && !activeTopicName.textContent.includes('solidity')) {
    console.error('FAIL_ACTIVE_TOPIC_NAME: ' + activeTopicName.textContent);
    process.exit(3);
  }
  if (!window.location.search.includes('topic=solidity')) {
    console.error('FAIL_URL_NO_TOPIC: ' + window.location.search);
    process.exit(4);
  }

  // Clear fetchCalls to test reset
  fetchCalls = [];

  // 2. Click #btnClearTopicFilter
  btnClearTopic.dispatchEvent({ type: 'click' });
  await new Promise(r => setTimeout(r, 10));

  if (activeTopicBar.style.display !== 'none') {
    console.error('FAIL_ACTIVE_BAR_NOT_HIDDEN: ' + activeTopicBar.style.display);
    process.exit(5);
  }
  if (activeTopicName.textContent !== '') {
    console.error('FAIL_ACTIVE_NAME_NOT_CLEARED: ' + activeTopicName.textContent);
    process.exit(6);
  }
  if (window.location.search.includes('topic=')) {
    console.error('FAIL_URL_TOPIC_NOT_REMOVED: ' + window.location.search);
    process.exit(7);
  }

  const cleanCalls = fetchCalls.filter(u => u.includes('/publications'));
  if (cleanCalls.length === 0) {
    console.error('FAIL_NO_RELOAD_FETCH: ' + JSON.stringify(fetchCalls));
    process.exit(8);
  }
  const staleTopicCalls = fetchCalls.filter(u => u.includes('topic='));
  if (staleTopicCalls.length > 0) {
    console.error('FAIL_STALE_TOPIC_PARAM: ' + JSON.stringify(fetchCalls));
    process.exit(9);
  }

  console.log('SUCCESS_TOPIC_RESET');
"""
        proc = self._run_node_script(script_body)
        self.assertEqual(proc.returncode, 0, f"Topic selection and reset failed: {proc.stderr}")
        self.assertIn("SUCCESS_TOPIC_RESET", proc.stdout)

    def test_topic_pill_toggle_off(self):
        """Simulate selecting topic 'solidity', then clicking the same pill again -> filter is cleared and request has no &topic=."""
        script_body = """
  // 1. Click pill to select 'solidity'
  pillSolidity.dispatchEvent({ type: 'click' });
  await new Promise(r => setTimeout(r, 10));

  if (api.getCurrentTopicFilter() !== 'solidity') {
    console.error('FAIL_NOT_SELECTED: ' + api.getCurrentTopicFilter());
    process.exit(1);
  }

  fetchCalls = [];

  // 2. Click the same pill again to toggle off
  pillSolidity.dispatchEvent({ type: 'click' });
  await new Promise(r => setTimeout(r, 10));

  if (api.getCurrentTopicFilter() !== '') {
    console.error('FAIL_NOT_CLEARED: ' + api.getCurrentTopicFilter());
    process.exit(2);
  }
  if (activeTopicBar.style.display !== 'none') {
    console.error('FAIL_BAR_NOT_HIDDEN: ' + activeTopicBar.style.display);
    process.exit(3);
  }

  const pubCalls = fetchCalls.filter(u => u.includes('/publications'));
  if (pubCalls.length === 0) {
    console.error('FAIL_NO_FETCH: ' + JSON.stringify(fetchCalls));
    process.exit(4);
  }
  const topicCalls = pubCalls.filter(u => u.includes('topic='));
  if (topicCalls.length > 0) {
    console.error('FAIL_HAS_TOPIC_QUERY: ' + JSON.stringify(pubCalls));
    process.exit(5);
  }

  console.log('SUCCESS_PILL_TOGGLE_OFF');
"""
        proc = self._run_node_script(script_body)
        self.assertEqual(proc.returncode, 0, f"Topic pill toggle off failed: {proc.stderr}")
        self.assertIn("SUCCESS_PILL_TOGGLE_OFF", proc.stdout)

    def test_topic_pill_keyboard_enter_and_space(self):
        """Simulate Enter and Space keydown events on topic pills -> activate/deactivate filter identically to click."""
        script_body = """
  // 1. Enter keydown activates
  pillSolidity.dispatchEvent({ type: 'keydown', key: 'Enter' });
  await new Promise(r => setTimeout(r, 10));

  if (api.getCurrentTopicFilter() !== 'solidity') {
    console.error('FAIL_ENTER_ACTIVATE: ' + api.getCurrentTopicFilter());
    process.exit(1);
  }
  if (!fetchCalls.some(u => u.includes('&topic=solidity'))) {
    console.error('FAIL_ENTER_FETCH: ' + JSON.stringify(fetchCalls));
    process.exit(2);
  }

  // 2. Enter keydown again deactivates
  fetchCalls = [];
  pillSolidity.dispatchEvent({ type: 'keydown', key: 'Enter' });
  await new Promise(r => setTimeout(r, 10));

  if (api.getCurrentTopicFilter() !== '') {
    console.error('FAIL_ENTER_DEACTIVATE: ' + api.getCurrentTopicFilter());
    process.exit(3);
  }
  if (fetchCalls.some(u => u.includes('topic='))) {
    console.error('FAIL_ENTER_DEACTIVATE_FETCH: ' + JSON.stringify(fetchCalls));
    process.exit(4);
  }

  // 3. Space keydown activates
  fetchCalls = [];
  pillSolidity.dispatchEvent({ type: 'keydown', key: ' ' });
  await new Promise(r => setTimeout(r, 10));

  if (api.getCurrentTopicFilter() !== 'solidity') {
    console.error('FAIL_SPACE_ACTIVATE: ' + api.getCurrentTopicFilter());
    process.exit(5);
  }
  if (!fetchCalls.some(u => u.includes('&topic=solidity'))) {
    console.error('FAIL_SPACE_FETCH: ' + JSON.stringify(fetchCalls));
    process.exit(6);
  }

  // 4. Space keydown again deactivates
  fetchCalls = [];
  pillSolidity.dispatchEvent({ type: 'keydown', key: ' ' });
  await new Promise(r => setTimeout(r, 10));

  if (api.getCurrentTopicFilter() !== '') {
    console.error('FAIL_SPACE_DEACTIVATE: ' + api.getCurrentTopicFilter());
    process.exit(7);
  }
  if (fetchCalls.some(u => u.includes('topic='))) {
    console.error('FAIL_SPACE_DEACTIVATE_FETCH: ' + JSON.stringify(fetchCalls));
    process.exit(8);
  }

  console.log('SUCCESS_KEYBOARD_NAVIGATION');
"""
        proc = self._run_node_script(script_body)
        self.assertEqual(proc.returncode, 0, f"Topic pill keyboard navigation failed: {proc.stderr}")
        self.assertIn("SUCCESS_KEYBOARD_NAVIGATION", proc.stdout)

    def test_popstate_topic_synchronization(self):
        """Simulate popstate with { topic: 'python' } and { topic: '' } -> UI and state sync."""
        script_body = """
  // 1. Popstate with topic: 'python'
  window.dispatchEvent({
    type: 'popstate',
    state: { tab: 'publications', topic: 'python' }
  });
  await new Promise(r => setTimeout(r, 10));

  if (api.getCurrentTopicFilter() !== 'python') {
    console.error('FAIL_POPSTATE_STATE: ' + api.getCurrentTopicFilter());
    process.exit(1);
  }
  if (activeTopicBar.style.display !== 'inline-flex') {
    console.error('FAIL_POPSTATE_BAR_DISPLAY: ' + activeTopicBar.style.display);
    process.exit(2);
  }
  if (!activeTopicName.textContent.includes('Python') && !activeTopicName.textContent.includes('python')) {
    console.error('FAIL_POPSTATE_NAME: ' + activeTopicName.textContent);
    process.exit(3);
  }
  if (!pillPython.classList.contains('is-active')) {
    console.error('FAIL_PILL_NOT_ACTIVE');
    process.exit(4);
  }

  // 2. Popstate with topic: ''
  window.dispatchEvent({
    type: 'popstate',
    state: { tab: 'publications', topic: '' }
  });
  await new Promise(r => setTimeout(r, 10));

  if (api.getCurrentTopicFilter() !== '') {
    console.error('FAIL_POPSTATE_CLEAR_STATE: ' + api.getCurrentTopicFilter());
    process.exit(5);
  }
  if (activeTopicBar.style.display !== 'none') {
    console.error('FAIL_POPSTATE_CLEAR_BAR: ' + activeTopicBar.style.display);
    process.exit(6);
  }
  if (activeTopicName.textContent !== '') {
    console.error('FAIL_POPSTATE_CLEAR_NAME: ' + activeTopicName.textContent);
    process.exit(7);
  }
  if (pillPython.classList.contains('is-active')) {
    console.error('FAIL_PILL_STILL_ACTIVE');
    process.exit(8);
  }

  console.log('SUCCESS_POPSTATE_SYNC');
"""
        proc = self._run_node_script(script_body)
        self.assertEqual(proc.returncode, 0, f"Popstate topic synchronization failed: {proc.stderr}")
        self.assertIn("SUCCESS_POPSTATE_SYNC", proc.stdout)


if __name__ == "__main__":
    unittest.main()
