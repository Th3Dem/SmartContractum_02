#!/usr/bin/env python3
"""
tests/test_issue190_profile_pinned_material_frontend.py

Automated frontend test suite for Issue #190:
[P2][fullstack][PROFILE] Single pinned material in user profile with authorship validation.

Verifies:
1. profile.html Elements:
   - Pinned material section: #profilePinnedSection
   - Pinned header and label: #profilePinnedHeader, .profile-pinned-label
   - Unpin action button: #btnProfileUnpin
   - Pinned card container: #profilePinnedCard
   - Ordering: #profilePinnedSection is placed inside #profileTabOverview above #profileTopContributionsSection
2. profile.css Rules:
   - .profile-pinned-section container styles
   - .profile-pinned-badge and .profile-pinned-label typography
   - .btn-profile-unpin button styles and hover states
   - .profile-pinned-card card layout and typography
   - .profile-pinned-unavailable-card warning layout for retracted materials
   - .btn-card-pin and .btn-card-pin.is-pinned card action buttons
3. profile-page.js Logic:
   - renderPinnedMaterial handles both active cards and unavailable owner state
   - pinMaterial sends POST /api/user/pinned with targetType and targetId
   - unpinMaterial sends DELETE /api/user/pinned
   - updateCardPinButtons updates card buttons state
   - renderTopContributions excludes pinned material ID to prevent duplicate display
   - renderPublicationsTab and renderAnswersTab provide pin/unpin buttons for profile owner
   - window.SmartContractumProfilePage exports renderPinnedMaterial, pinMaterial, unpinMaterial, updateCardPinButtons
4. Strict Invariants:
   - Zero emojis, zero em dashes (\\u2014), 100% offline-first.
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


class TestIssue190ProfilePinnedMaterialFrontend(unittest.TestCase):
    """Verifies profile pinned material HTML markup, CSS styling, and JS behavior."""

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
    # 1. profile.html Markup & Placement
    # =========================================================================

    def test_01_profile_html_pinned_section_structure(self):
        """Verify #profilePinnedSection, #profilePinnedCard, and #btnProfileUnpin exist."""
        self.assertIn('id="profilePinnedSection"', self.html, "HTML must contain #profilePinnedSection")
        self.assertIn('profile-pinned-section', self.html, "HTML must contain class 'profile-pinned-section'")
        self.assertIn('id="profilePinnedCard"', self.html, "HTML must contain #profilePinnedCard")
        self.assertIn('id="btnProfileUnpin"', self.html, "HTML must contain #btnProfileUnpin")
        self.assertIn('btn-profile-unpin', self.html, "HTML must contain class 'btn-profile-unpin'")

    def test_02_profile_html_pinned_section_placement(self):
        """Verify #profilePinnedSection is placed inside #profileTabOverview above #profileTopContributionsSection."""
        pinned_idx = self.html.find('id="profilePinnedSection"')
        top_idx = self.html.find('id="profileTopContributionsSection"')
        overview_idx = self.html.find('id="profileTabOverview"')

        self.assertNotEqual(pinned_idx, -1, "#profilePinnedSection must exist")
        self.assertNotEqual(top_idx, -1, "#profileTopContributionsSection must exist")
        self.assertNotEqual(overview_idx, -1, "#profileTabOverview must exist")

        self.assertTrue(overview_idx < pinned_idx < top_idx,
                        "#profilePinnedSection must be inside overview tab and before top contributions")

    # =========================================================================
    # 2. profile.css Styles
    # =========================================================================

    def test_03_profile_css_pinned_classes(self):
        """Verify CSS classes for pinned section, card, badges, unpin button, and pin action buttons."""
        classes = [
            '.profile-pinned-section',
            '.profile-pinned-badge',
            '.btn-profile-unpin',
            '.profile-pinned-card',
            '.profile-pinned-unavailable-card',
            '.btn-card-pin',
            '.btn-card-pin.is-pinned'
        ]
        for cls_name in classes:
            self.assertIn(cls_name, self.css, f"CSS must define rule for '{cls_name}'")

    # =========================================================================
    # 3. profile-page.js Logic & Exports
    # =========================================================================

    def test_04_profile_page_js_render_pinned_material(self):
        """Verify renderPinnedMaterial handles active pinned card and unavailable states."""
        self.assertIn('function renderPinnedMaterial', self.page_js, "Must define renderPinnedMaterial function")
        self.assertIn('profilePinnedSection', self.page_js, "Must reference profilePinnedSection element")
        self.assertIn('profilePinnedCard', self.page_js, "Must reference profilePinnedCard element")
        self.assertIn('isUnavailable', self.page_js, "Must handle isUnavailable state for profile owner")
        self.assertIn('profile-pinned-unavailable-card', self.page_js, "Must use unavailable card styling when retracted")

    def test_05_profile_page_js_api_actions(self):
        """Verify pinMaterial and unpinMaterial call /api/user/pinned with correct methods."""
        self.assertIn('function pinMaterial', self.page_js, "Must define pinMaterial function")
        self.assertIn('function unpinMaterial', self.page_js, "Must define unpinMaterial function")
        self.assertIn("'/api/user/pinned'", self.page_js, "Must call /api/user/pinned")
        self.assertIn("method: 'POST'", self.page_js, "Must perform POST on /api/user/pinned for pin")
        self.assertIn("method: 'DELETE'", self.page_js, "Must perform DELETE on /api/user/pinned for unpin")

    def test_06_profile_page_js_duplicate_prevention(self):
        """Verify renderTopContributions filters out the pinned item to avoid duplicate cards."""
        self.assertIn('function renderTopContributions', self.page_js, "Must define renderTopContributions function")
        # Check that pinnedMaterial filter logic exists inside renderTopContributions
        self.assertIn('items.filter(function (it) { return it.id !== pinId; });', self.page_js,
                      "renderTopContributions must filter out pinned material ID")

    def test_07_profile_page_js_card_pin_actions(self):
        """Verify publication cards and answers cards render pin/unpin buttons for profile owner."""
        self.assertIn('btn-card-pin', self.page_js, "Must create btn-card-pin elements")
        self.assertIn("pinMaterial('publication'", self.page_js, "Must call pinMaterial('publication', ...) on pub cards")
        self.assertIn("pinMaterial('solution'", self.page_js, "Must call pinMaterial('solution', ...) on solution cards")
        self.assertIn('updateCardPinButtons', self.page_js, "Must define updateCardPinButtons function")
        self.assertIn('isMaterialPinned', self.page_js, "Must define isMaterialPinned helper")

    def test_08_profile_page_js_exports(self):
        """Verify pinned material functions are exported on window.SmartContractumProfilePage."""
        exports = ['renderPinnedMaterial', 'pinMaterial', 'unpinMaterial', 'updateCardPinButtons', 'isMaterialPinned']
        for exp in exports:
            self.assertIn(f'{exp}: {exp}', self.page_js,
                          f"window.SmartContractumProfilePage must export '{exp}'")

    # =========================================================================
    # 4. Strict Invariants (Zero Emojis, Zero Em Dashes, 100% Offline-First)
    # =========================================================================

    def test_09_invariants_zero_em_dashes(self):
        """Verify that no em dashes (\\u2014) exist in code or template files."""
        for path, content in [
            ("profile.html", self.html),
            ("profile-page.js", self.page_js),
            ("profile.css", self.css),
            ("test_py", self.test_py)
        ]:
            self.assertNotIn("\u2014", content, f"Em dash found in {path}")

    def test_10_invariants_zero_emojis(self):
        """Verify that zero emojis exist in code or template files."""
        def check_emojis(text, label):
            for i, ch in enumerate(text):
                cat = unicodedata.category(ch)
                if cat == "So" or ord(ch) > 0x1F000:
                    self.fail(f"Emoji character detected in {label} at pos {i}: U+{ord(ch):04X}")

        check_emojis(self.html, "profile.html")
        check_emojis(self.page_js, "profile-page.js")
        check_emojis(self.css, "profile.css")

    def test_11_invariants_offline_first(self):
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

    def _run_node_vm_test(self, test_body):
        """Execute a test script inside a Node.js VM context simulating profile-page.js environment."""
        setup = f"""
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

const jsPath = {repr(PAGE_JS_PATH)};
const code = fs.readFileSync(jsPath, 'utf8');

function createMockEl(tag, id) {{
  const listeners = {{}};
  const classes = new Set();
  const attrs = {{}};
  const el = {{
    tagName: (tag || 'div').toUpperCase(),
    id: id || '',
    style: {{ display: '' }},
    children: [],
    classList: {{
      add: (...c) => c.forEach(x => classes.add(x)),
      remove: (...c) => c.forEach(x => classes.delete(x)),
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
    setAttribute: (k, v) => {{ attrs[k] = String(v); }},
    getAttribute: (k) => (k in attrs ? attrs[k] : null),
    removeAttribute: (k) => {{ delete attrs[k]; }},
    hasAttribute: (k) => k in attrs,
    addEventListener: (evt, fn) => {{
      if (!listeners[evt]) listeners[evt] = [];
      listeners[evt].push(fn);
    }},
    dispatchEvent: (e) => {{
      const fns = listeners[e.type] || [];
      for (const fn of fns) fn.call(el, e);
    }},
    appendChild: (child) => {{
      el.children.push(child);
      child.parentElement = el;
      el.lastElementChild = child;
      return child;
    }},
    querySelector: (sel) => {{
      for (const ch of el.children) {{
        if (sel.startsWith('.') && ch.classList.contains(sel.slice(1))) return ch;
        if (ch.querySelector) {{
          const res = ch.querySelector(sel);
          if (res) return res;
        }}
      }}
      return null;
    }},
    querySelectorAll: (sel) => {{
      const res = [];
      for (const ch of el.children) {{
        if (sel.startsWith('.') && ch.classList.contains(sel.slice(1))) res.push(ch);
        if (ch.querySelectorAll) res.push(...ch.querySelectorAll(sel));
      }}
      return res;
    }},
    innerHTML: '',
    textContent: '',
    title: '',
    type: 'button'
  }};
  Object.defineProperty(el, 'className', {{
    get: () => Array.from(classes).join(' '),
    set: (val) => {{
      classes.clear();
      String(val || '').split(/\\s+/).filter(Boolean).forEach(c => classes.add(c));
    }}
  }});
  return el;
}}

const elements = {{}};
function getEl(id) {{
  if (!elements[id]) elements[id] = createMockEl('div', id);
  return elements[id];
}}

const allCreated = [];
const fetchCalls = [];
let fetchHandler = null;

const win = {{
  console: console,
  location: {{ search: '?id=user_author', href: 'http://localhost/profile.html?id=user_author' }},
  document: {{
    documentElement: {{ setAttribute: () => {{}}, getAttribute: () => 'dark' }},
    body: createMockEl('body', 'body'),
    getElementById: getEl,
    createElement: (tag) => {{
      const el = createMockEl(tag);
      allCreated.push(el);
      return el;
    }},
    querySelectorAll: (sel) => {{
      if (sel === '.btn-card-pin') {{
        return allCreated.filter(e => e.classList.contains('btn-card-pin'));
      }}
      return [];
    }},
    querySelector: () => null,
    addEventListener: () => {{}}
  }},
  localStorage: {{ getItem: () => null, setItem: () => {{}} }},
  history: {{ pushState: () => {{}}, replaceState: () => {{}} }},
  fetch: (url, opts) => {{
    const callRecord = {{ url, opts, body: opts && opts.body ? JSON.parse(opts.body) : null }};
    fetchCalls.push(callRecord);
    if (fetchHandler) return fetchHandler(url, opts, callRecord);
    return Promise.resolve({{ ok: true, json: () => Promise.resolve({{ success: true, items: [] }}) }});
  }},
  setTimeout: (fn, ms) => setTimeout(fn, ms),
  clearTimeout: (t) => clearTimeout(t)
}};
win.window = win;

vm.createContext(win);
vm.runInContext(code, win);

(async () => {{
  try {{
    {test_body}
  }} catch (err) {{
    console.error(err);
    process.exit(1);
  }}
}})();
"""
        proc = subprocess.run(["node", "-e", setup], capture_output=True, text=True)
        if proc.returncode != 0:
            self.fail(f"Node VM test failed (exit {proc.returncode}):\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}")

    def test_pin_unpin_repin_sequence_without_reload(self):
        """Card A pinned -> click A sends unpin -> button A updates to 'Закрепить' -> click A sends pin A -> button A updates to 'Закреплено'."""
        body = """
  const api = win.SmartContractumProfilePage;
  api.setAuthState({ id: 'user_author', name: 'Author Alice' });
  api.renderProfile({
    id: 'user_author',
    isOwnProfile: true,
    pinnedMaterial: { id: 'pub_1', targetType: 'publication', title: 'Article 1' }
  });
  api.renderPublicationsTab([{ id: 'pub_1', title: 'Article 1' }], false, false);

  const pinBtns = win.document.querySelectorAll('.btn-card-pin');
  assert.strictEqual(pinBtns.length, 1, 'One pin button should be rendered for pub_1');
  const btnA = pinBtns[0];

  assert.strictEqual(btnA.getAttribute('data-target-id'), 'pub_1');
  assert.strictEqual(btnA.getAttribute('data-target-type'), 'publication');
  assert.strictEqual(btnA.getAttribute('data-is-pinned'), 'true');
  assert.strictEqual(btnA.classList.contains('is-pinned'), true);
  assert.strictEqual(btnA.textContent, 'Закреплено');
  assert.strictEqual(btnA.title, 'Материал закреплен в профиле');
  assert.strictEqual(api.isMaterialPinned('pub_1'), true);

  fetchHandler = (url, opts) => {
    if (url === '/api/user/pinned' && opts.method === 'DELETE') {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) });
    }
    if (url === '/api/user/pinned' && opts.method === 'POST') {
      const body = opts.body ? JSON.parse(opts.body) : {};
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          pinnedMaterial: { id: body.targetId, targetType: body.targetType }
        })
      });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, items: [] }) });
  };

  // Click A: sends unpin
  btnA.dispatchEvent({ type: 'click', stopPropagation: () => {} });
  await new Promise(r => setTimeout(r, 20));

  const unpinCalls = fetchCalls.filter(c => c.url === '/api/user/pinned' && c.opts.method === 'DELETE');
  assert.strictEqual(unpinCalls.length, 1, 'Should send DELETE /api/user/pinned');
  assert.strictEqual(btnA.getAttribute('data-is-pinned'), 'false');
  assert.strictEqual(btnA.classList.contains('is-pinned'), false);
  assert.strictEqual(btnA.textContent, 'Закрепить');
  assert.strictEqual(btnA.title, 'Закрепить в профиле');
  assert.strictEqual(api.isMaterialPinned('pub_1'), false);

  // Click A again: sends pin A
  btnA.dispatchEvent({ type: 'click', stopPropagation: () => {} });
  await new Promise(r => setTimeout(r, 20));

  const pinCalls = fetchCalls.filter(c => c.url === '/api/user/pinned' && c.opts.method === 'POST');
  assert.strictEqual(pinCalls.length, 1, 'Should send POST /api/user/pinned');
  assert.strictEqual(pinCalls[0].body.targetId, 'pub_1');
  assert.strictEqual(pinCalls[0].body.targetType, 'publication');
  assert.strictEqual(btnA.getAttribute('data-is-pinned'), 'true');
  assert.strictEqual(btnA.classList.contains('is-pinned'), true);
  assert.strictEqual(btnA.textContent, 'Закреплено');
  assert.strictEqual(btnA.title, 'Материал закреплен в профиле');
  assert.strictEqual(api.isMaterialPinned('pub_1'), true);
"""
        self._run_node_vm_test(body)

    def test_pin_replacement_a_to_b_then_a(self):
        """A pinned -> click B pins B -> button B 'Закреплено', button A 'Закрепить' -> click A pins A (does NOT unpin B)."""
        body = """
  const api = win.SmartContractumProfilePage;
  api.setAuthState({ id: 'user_author', name: 'Author Alice' });
  api.renderProfile({
    id: 'user_author',
    isOwnProfile: true,
    pinnedMaterial: { id: 'pub_A', targetType: 'publication', title: 'Article A' }
  });
  api.renderPublicationsTab([
    { id: 'pub_A', title: 'Article A' },
    { id: 'pub_B', title: 'Article B' }
  ], false, false);

  const pinBtns = win.document.querySelectorAll('.btn-card-pin');
  assert.strictEqual(pinBtns.length, 2, 'Two pin buttons should be rendered');
  const btnA = pinBtns[0];
  const btnB = pinBtns[1];

  assert.strictEqual(btnA.textContent, 'Закреплено');
  assert.strictEqual(btnA.classList.contains('is-pinned'), true);
  assert.strictEqual(btnB.textContent, 'Закрепить');
  assert.strictEqual(btnB.classList.contains('is-pinned'), false);
  assert.strictEqual(api.isMaterialPinned('pub_A'), true);
  assert.strictEqual(api.isMaterialPinned('pub_B'), false);

  fetchHandler = (url, opts) => {
    if (url === '/api/user/pinned' && opts.method === 'POST') {
      const body = opts.body ? JSON.parse(opts.body) : {};
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          pinnedMaterial: { id: body.targetId, targetType: body.targetType }
        })
      });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, items: [] }) });
  };

  // Click B: pins B (replaces A without explicit DELETE)
  btnB.dispatchEvent({ type: 'click', stopPropagation: () => {} });
  await new Promise(r => setTimeout(r, 20));

  const deleteCalls = () => fetchCalls.filter(c => c.url === '/api/user/pinned' && c.opts.method === 'DELETE');
  const postCalls = () => fetchCalls.filter(c => c.url === '/api/user/pinned' && c.opts.method === 'POST');

  assert.strictEqual(deleteCalls().length, 0, 'Should NOT send DELETE request when replacing pin');
  assert.strictEqual(postCalls().length, 1, 'Should send single POST /api/user/pinned for B');
  assert.strictEqual(postCalls()[0].body.targetId, 'pub_B');

  assert.strictEqual(btnB.textContent, 'Закреплено');
  assert.strictEqual(btnB.classList.contains('is-pinned'), true);
  assert.strictEqual(btnB.getAttribute('data-is-pinned'), 'true');
  assert.strictEqual(btnA.textContent, 'Закрепить');
  assert.strictEqual(btnA.classList.contains('is-pinned'), false);
  assert.strictEqual(btnA.getAttribute('data-is-pinned'), 'false');
  assert.strictEqual(api.isMaterialPinned('pub_B'), true);
  assert.strictEqual(api.isMaterialPinned('pub_A'), false);

  // Click A: pins A (does NOT unpin B)
  btnA.dispatchEvent({ type: 'click', stopPropagation: () => {} });
  await new Promise(r => setTimeout(r, 20));

  assert.strictEqual(deleteCalls().length, 0, 'Still should NOT send DELETE request');
  assert.strictEqual(postCalls().length, 2, 'Should send second POST for A');
  assert.strictEqual(postCalls()[1].body.targetId, 'pub_A');

  assert.strictEqual(btnA.textContent, 'Закреплено');
  assert.strictEqual(btnA.classList.contains('is-pinned'), true);
  assert.strictEqual(btnA.getAttribute('data-is-pinned'), 'true');
  assert.strictEqual(btnB.textContent, 'Закрепить');
  assert.strictEqual(btnB.classList.contains('is-pinned'), false);
  assert.strictEqual(btnB.getAttribute('data-is-pinned'), 'false');
  assert.strictEqual(api.isMaterialPinned('pub_A'), true);
  assert.strictEqual(api.isMaterialPinned('pub_B'), false);
"""
        self._run_node_vm_test(body)

    def test_solution_pin_unpin_sequence(self):
        """Verifies the same dynamic behavior for solution cards."""
        body = """
  const api = win.SmartContractumProfilePage;
  api.setAuthState({ id: 'user_author', name: 'Author Alice' });
  api.renderProfile({
    id: 'user_author',
    isOwnProfile: true,
    pinnedMaterial: { id: 'sol_1', targetType: 'solution', isSolution: true }
  });
  api.renderAnswersTab([
    { id: 'sol_1', isSolution: true, title: 'Solution 1' },
    { id: 'sol_2', isSolution: true, title: 'Solution 2' }
  ], false, false);

  const pinBtns = win.document.querySelectorAll('.btn-card-pin');
  assert.strictEqual(pinBtns.length, 2, 'Two pin buttons should be rendered for solution answers');
  const btnS1 = pinBtns[0];
  const btnS2 = pinBtns[1];

  assert.strictEqual(btnS1.getAttribute('data-target-type'), 'solution');
  assert.strictEqual(btnS2.getAttribute('data-target-type'), 'solution');
  assert.strictEqual(btnS1.textContent, 'Закреплено');
  assert.strictEqual(btnS1.title, 'Решение закреплено в профиле');
  assert.strictEqual(btnS1.classList.contains('is-pinned'), true);
  assert.strictEqual(btnS2.textContent, 'Закрепить');
  assert.strictEqual(btnS2.title, 'Закрепить решение в профиле');
  assert.strictEqual(btnS2.classList.contains('is-pinned'), false);
  assert.strictEqual(api.isMaterialPinned('sol_1'), true);
  assert.strictEqual(api.isMaterialPinned('sol_2'), false);

  fetchHandler = (url, opts) => {
    if (url === '/api/user/pinned' && opts.method === 'DELETE') {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) });
    }
    if (url === '/api/user/pinned' && opts.method === 'POST') {
      const body = opts.body ? JSON.parse(opts.body) : {};
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          pinnedMaterial: { id: body.targetId, targetType: body.targetType, isSolution: true }
        })
      });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, items: [] }) });
  };

  // Step 1: Click S1 to unpin
  btnS1.dispatchEvent({ type: 'click', stopPropagation: () => {} });
  await new Promise(r => setTimeout(r, 20));

  const deleteCalls = fetchCalls.filter(c => c.url === '/api/user/pinned' && c.opts.method === 'DELETE');
  assert.strictEqual(deleteCalls.length, 1, 'Should call DELETE for solution unpin');
  assert.strictEqual(btnS1.textContent, 'Закрепить');
  assert.strictEqual(btnS1.title, 'Закрепить решение в профиле');
  assert.strictEqual(btnS1.classList.contains('is-pinned'), false);
  assert.strictEqual(btnS1.getAttribute('data-is-pinned'), 'false');
  assert.strictEqual(api.isMaterialPinned('sol_1'), false);

  // Step 2: Click S2 to pin solution 2
  btnS2.dispatchEvent({ type: 'click', stopPropagation: () => {} });
  await new Promise(r => setTimeout(r, 20));

  const postCalls = fetchCalls.filter(c => c.url === '/api/user/pinned' && c.opts.method === 'POST');
  assert.strictEqual(postCalls.length, 1, 'Should call POST with targetType: solution');
  assert.strictEqual(postCalls[0].body.targetId, 'sol_2');
  assert.strictEqual(postCalls[0].body.targetType, 'solution');

  assert.strictEqual(btnS2.textContent, 'Закреплено');
  assert.strictEqual(btnS2.title, 'Решение закреплено в профиле');
  assert.strictEqual(btnS2.classList.contains('is-pinned'), true);
  assert.strictEqual(btnS2.getAttribute('data-is-pinned'), 'true');
  assert.strictEqual(btnS1.textContent, 'Закрепить');
  assert.strictEqual(btnS1.title, 'Закрепить решение в профиле');
  assert.strictEqual(btnS1.classList.contains('is-pinned'), false);
  assert.strictEqual(api.isMaterialPinned('sol_2'), true);
  assert.strictEqual(api.isMaterialPinned('sol_1'), false);
"""
        self._run_node_vm_test(body)

    def test_double_click_protection_and_error_handling(self):
        """Rapid clicks while request is in flight are ignored; network failure preserves previous state."""
        body = """
  const api = win.SmartContractumProfilePage;
  api.setAuthState({ id: 'user_author', name: 'Author Alice' });
  api.renderProfile({ id: 'user_author', isOwnProfile: true, pinnedMaterial: null });
  api.renderPublicationsTab([{ id: 'pub_1', title: 'Article 1' }], false, false);

  const btnA = win.document.querySelectorAll('.btn-card-pin')[0];
  assert.strictEqual(btnA.textContent, 'Закрепить');

  let pendingResolvers = [];
  fetchHandler = (url, opts) => {
    if (url === '/api/user/pinned') {
      return new Promise((resolve, reject) => {
        pendingResolvers.push({ resolve, reject, url, opts });
      });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, items: [] }) });
  };

  // 1. Rapid clicks while request is in flight
  btnA.dispatchEvent({ type: 'click', stopPropagation: () => {} });
  btnA.dispatchEvent({ type: 'click', stopPropagation: () => {} });
  btnA.dispatchEvent({ type: 'click', stopPropagation: () => {} });

  const inFlightCalls = fetchCalls.filter(c => c.url === '/api/user/pinned');
  assert.strictEqual(inFlightCalls.length, 1, 'Only first click initiates request; rapid double-clicks ignored');
  assert.strictEqual(pendingResolvers.length, 1);

  // Resolve first request successfully
  pendingResolvers.shift().resolve({
    ok: true,
    json: () => Promise.resolve({
      success: true,
      pinnedMaterial: { id: 'pub_1', targetType: 'publication' }
    })
  });
  await new Promise(r => setTimeout(r, 20));

  assert.strictEqual(btnA.textContent, 'Закреплено');
  assert.strictEqual(btnA.classList.contains('is-pinned'), true);
  assert.strictEqual(api.isMaterialPinned('pub_1'), true);

  // 2. Network failure preserves previous state
  btnA.dispatchEvent({ type: 'click', stopPropagation: () => {} });
  assert.strictEqual(fetchCalls.filter(c => c.url === '/api/user/pinned').length, 2, 'Unpin click initiates request');
  assert.strictEqual(pendingResolvers.length, 1);

  // Simulate network rejection
  pendingResolvers.shift().reject(new Error('Network disconnected'));
  await new Promise(r => setTimeout(r, 20));

  assert.strictEqual(btnA.textContent, 'Закреплено', 'State must remain Закреплено after network error');
  assert.strictEqual(btnA.classList.contains('is-pinned'), true, 'is-pinned class preserved after error');
  assert.strictEqual(api.isMaterialPinned('pub_1'), true, 'Pinned status in profile preserved after error');

  // Verify in-flight guard was reset so subsequent actions are permitted
  btnA.dispatchEvent({ type: 'click', stopPropagation: () => {} });
  assert.strictEqual(fetchCalls.filter(c => c.url === '/api/user/pinned').length, 3, 'Retry unpin click sends new request');
  assert.strictEqual(pendingResolvers.length, 1);

  pendingResolvers.shift().resolve({
    ok: true,
    json: () => Promise.resolve({ success: true })
  });
  await new Promise(r => setTimeout(r, 20));

  assert.strictEqual(btnA.textContent, 'Закрепить');
  assert.strictEqual(btnA.classList.contains('is-pinned'), false);
  assert.strictEqual(api.isMaterialPinned('pub_1'), false);
"""
        self._run_node_vm_test(body)


if __name__ == "__main__":
    unittest.main()

