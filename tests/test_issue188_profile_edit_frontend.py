#!/usr/bin/env python3
"""
tests/test_issue188_profile_edit_frontend.py

Automated frontend test suite for Issue #188:
[P1][fullstack][PROFILE] Edit profile: upload avatar and personal navigation widget.

Verifies:
1. profile.html Elements:
   - Edit modal avatar management section:
     * Avatar preview elements: id="editAvatarPreviewImg", id="editAvatarInitials".
     * Hidden file input: id="editAvatarFileInput", accept="image/png,image/jpeg,image/webp,image/svg+xml".
     * Buttons: id="btnChooseAvatar", id="btnRemoveAvatar".
     * Error box: id="editProfileError" (hidden by default, role="alert").
   - Profile sidebar personal navigation widget:
     * Widget container: id="profileOwnerNavWidget" inside .profile-sidebar (hidden by default).
     * Links to personal sections:
       - Черновики: href="editor.html"
       - Сохраненное: href="feed.html?tab=saved"
       - Подписки: href="feed.html?tab=my"
2. profile.css Styles:
   - .edit-avatar-section, .edit-avatar-preview, .edit-avatar-preview-img, .edit-avatar-initials
   - .btn-remove-avatar, .edit-profile-error
   - .profile-owner-nav-widget, .profile-owner-nav-list, .profile-owner-nav-link
3. profile-page.js Logic:
   - Avatar preview and selection handling (FileReader base64 and preview display).
   - Avatar removal handling (clears preview, sets isAvatarRemoved flag).
   - Input validation rules:
     * Name required (1..100 characters).
     * Specialization max 120 characters.
     * Company max 120 characters.
     * Bio max 1000 characters.
     * Website URL normalization (missing scheme auto-prepends https://).
     * Dangerous website scheme rejection (e.g. javascript:, data:).
     * Website max 300 characters.
   - Save profile payload assembly:
     * { name, specialization, company, bio, website, avatar: newAvatar, removeAvatar: isAvatarRemoved }
   - Save success handling:
     * Updates currentProfile.
     * Updates header user bar if own profile (name and avatar).
     * Re-renders profile UI via renderProfile.
     * Closes edit modal.
     * Shows toast: 'Профиль успешно обновлен'.
   - Owner navigation widget visibility:
     * Shown only when viewing own profile, hidden for other users.
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


class TestIssue188ProfileEditFrontend(unittest.TestCase):
    """Verifies profile edit modal avatar controls, personal nav widget, and validation logic."""

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

    @classmethod
    def _run_node_script(cls, script_body):
        """Execute a JavaScript snippet in a Node.js vm context simulating the profile page DOM."""
        setup = f"""
const fs = require('fs');
const vm = require('vm');

const code = fs.readFileSync('{PAGE_JS_PATH}', 'utf8');

const domElements = {{}};
function getEl(id) {{
  if (!domElements[id]) {{
    const listeners = {{}};
    domElements[id] = {{
      id: id,
      value: '',
      src: '',
      style: {{ display: 'none' }},
      disabled: false,
      classList: {{
        _classes: new Set(),
        add: function(c) {{ this._classes.add(c); }},
        remove: function(c) {{ this._classes.delete(c); }},
        contains: function(c) {{ return this._classes.has(c); }},
        toggle: function(c) {{}}
      }},
      setAttribute: function(k, v) {{ this[k] = v; }},
      removeAttribute: function(k) {{ delete this[k]; }},
      getAttribute: function(k) {{ return this[k] || ''; }},
      hasAttribute: function(k) {{ return k in this; }},
      focus: function() {{ win.document.activeElement = this; }},
      blur: function() {{ if (win.document.activeElement === this) win.document.activeElement = null; }},
      addEventListener: function(t, fn) {{
        if (!listeners[t]) listeners[t] = [];
        listeners[t].push(fn);
      }},
      dispatchEvent: function(e) {{
        const fns = listeners[e.type] || [];
        for (const fn of fns) fn.call(this, e);
      }},
      querySelector: function() {{ return null; }},
      querySelectorAll: function() {{ return []; }},
      getContext: function() {{
        return {{ clearRect: () => {{}}, fillRect: () => {{}}, drawImage: () => {{}} }};
      }},
      toDataURL: function() {{ return 'data:image/png;base64,mock'; }}
    }};
  }}
  return domElements[id];
}}

const docListeners = {{}};
let uploadResolvers = [];

const win = {{
  console: console,
  URLSearchParams: URLSearchParams,
  URL: URL,
  location: {{ search: '?id=user_test', href: 'http://localhost/profile.html?id=user_test' }},
  addEventListener: () => {{}},
  dispatchEvent: () => {{}},
  document: {{
    documentElement: {{ setAttribute: () => {{}}, getAttribute: () => 'dark' }},
    activeElement: null,
    getElementById: getEl,
    addEventListener: (t, fn) => {{
      if (!docListeners[t]) docListeners[t] = [];
      docListeners[t].push(fn);
    }},
    createElement: (tag) => getEl('dyn_' + Math.random().toString(36).substr(2, 6)),
    querySelectorAll: (sel) => []
  }},
  localStorage: {{ getItem: () => null, setItem: () => {{}} }},
  history: {{ pushState: () => {{}}, replaceState: () => {{}} }},
  fetch: (url, opts) => {{
    if (url === '/api/media/upload') {{
      return new Promise((resolve, reject) => {{
        uploadResolvers.push({{ resolve, body: opts && opts.body ? JSON.parse(opts.body) : null }});
      }});
    }}
    return Promise.resolve({{ ok: true, json: () => Promise.resolve({{ success: true, url: '/test.png' }}) }});
  }},
  setTimeout: (fn, ms) => setTimeout(fn, ms),
  clearTimeout: (id) => clearTimeout(id),
  FileReader: function() {{
    this.readAsDataURL = function(file) {{
      setTimeout(() => {{
        if (this.onload) this.onload({{ target: {{ result: file.dataUrl || 'data:image/png;base64,mock' }} }});
      }}, 0);
    }};
  }},
  Image: function() {{
    this.src = '';
    this.complete = true;
    this.onload = () => {{}};
  }}
}};
win.window = win;

// Setup modal elements
const cropModal = getEl('avatarCropModal');
const editModal = getEl('editProfileModal');

const btnCloseCrop = getEl('btnCloseAvatarCropModal');
const zoomInput = getEl('avatarCropZoom');
const btnCancelCrop = getEl('btnCancelAvatarCrop');
const btnApplyCrop = getEl('btnApplyAvatarCrop');
btnCloseCrop.style.display = 'inline-block';
zoomInput.style.display = 'inline-block';
btnCancelCrop.style.display = 'inline-block';
btnApplyCrop.style.display = 'inline-block';

const cropChildren = [btnCloseCrop, zoomInput, btnCancelCrop, btnApplyCrop];
cropModal._children = cropChildren;
cropModal.contains = (el) => cropChildren.includes(el);
cropModal.querySelectorAll = (sel) => cropChildren;

const inpName = getEl('editProfileName');
const btnCropAvatar = getEl('btnCropAvatar');
const btnSaveEdit = getEl('btnSaveProfile');
inpName.style.display = 'block';
btnCropAvatar.style.display = 'inline-block';
btnSaveEdit.style.display = 'inline-block';

const editChildren = [inpName, btnCropAvatar, btnSaveEdit];
editModal._children = editChildren;
editModal.contains = (el) => editChildren.includes(el);
editModal.querySelectorAll = (sel) => editChildren;

vm.createContext(win);
vm.runInContext(code, win);

const api = win.SmartContractumProfilePage;
api.initEventListeners();

function sendDocKey(key, shiftKey) {{
  let prevented = false;
  for (const fn of (docListeners['keydown'] || [])) {{
    fn({{
      key: key,
      shiftKey: Boolean(shiftKey),
      preventDefault: () => {{ prevented = true; }}
    }});
  }}
  return prevented;
}}

(async () => {{
  {script_body}
}})();
"""
        return subprocess.run(["node", "-e", setup], capture_output=True, text=True)

    # =========================================================================
    # 1. profile.html Elements
    # =========================================================================

    def test_01_profile_html_edit_modal_avatar_controls(self):
        """Verify avatar management controls and error box inside #editProfileModal."""
        # 1. Modal wrapper
        self.assertIn('id="editProfileModal"', self.html, "Modal must have id='editProfileModal'")

        # 2. Avatar preview elements
        self.assertIn('id="editAvatarPreviewImg"', self.html, "Avatar preview img must have id='editAvatarPreviewImg'")
        self.assertIn('id="editAvatarInitials"', self.html, "Avatar initials span must have id='editAvatarInitials'")

        # 3. Hidden file input with allowed image MIME types
        self.assertIn('id="editAvatarFileInput"', self.html, "Avatar file input must have id='editAvatarFileInput'")
        self.assertIn(
            'accept="image/png,image/jpeg,image/webp,image/svg+xml"',
            self.html,
            "Avatar file input must accept image/png,image/jpeg,image/webp,image/svg+xml"
        )
        self.assertIn('type="file"', self.html, "Avatar input must have type='file'")

        # 4. Buttons for avatar selection and removal
        self.assertIn('id="btnChooseAvatar"', self.html, "Button to choose avatar must have id='btnChooseAvatar'")
        self.assertIn('id="btnCropAvatar"', self.html, "Button to crop avatar must have id='btnCropAvatar'")
        self.assertIn('id="btnRemoveAvatar"', self.html, "Button to remove avatar must have id='btnRemoveAvatar'")

        # 5. Error box hidden by default
        self.assertIn('id="editProfileError"', self.html, "Error container must have id='editProfileError'")
        error_match = re.search(r'<div[^>]*id="editProfileError"[^>]*>', self.html)
        self.assertIsNotNone(error_match, "editProfileError element must exist in profile.html")
        self.assertIn('display: none;', error_match.group(0), "editProfileError must be hidden by default")

        # 6. Avatar crop modal and controls
        self.assertIn('id="avatarCropModal"', self.html, "Cropper modal must have id='avatarCropModal'")
        self.assertIn('id="avatarCropCanvas"', self.html, "Cropper canvas must have id='avatarCropCanvas'")
        self.assertIn('id="avatarCropZoom"', self.html, "Cropper zoom slider must have id='avatarCropZoom'")
        self.assertIn('id="btnApplyAvatarCrop"', self.html, "Button to apply crop must have id='btnApplyAvatarCrop'")

    def test_02_profile_html_owner_navigation_widget(self):
        """Verify owner personal navigation widget in profile.html sidebar."""
        # 1. Widget container inside sidebar
        self.assertIn('id="profileOwnerNavWidget"', self.html, "Owner nav widget must have id='profileOwnerNavWidget'")

        widget_match = re.search(r'<div[^>]*id="profileOwnerNavWidget"[^>]*>', self.html)
        self.assertIsNotNone(widget_match, "profileOwnerNavWidget element must exist in profile.html")
        self.assertIn('display: none;', widget_match.group(0), "profileOwnerNavWidget must be hidden by default")

        # 2. Links to drafts, saved, following, and settings
        self.assertIn('href="editor.html"', self.html, "Personal nav must contain link to editor.html (Черновики)")
        self.assertIn('href="feed.html?tab=saved"', self.html, "Personal nav must contain link to feed.html?tab=saved (Сохраненное)")
        self.assertIn('href="feed.html?tab=my"', self.html, "Personal nav must contain link to feed.html?tab=my (Подписки)")
        self.assertIn('href="feed.html?panel=settings"', self.html, "Personal nav must contain link to feed.html?panel=settings (Настройки)")

        # Verify link labels
        self.assertIn('Черновики', self.html, "Personal nav must display label 'Черновики'")
        self.assertIn('Сохраненное', self.html, "Personal nav must display label 'Сохраненное'")
        self.assertIn('Подписки', self.html, "Personal nav must display label 'Подписки'")
        self.assertIn('Настройки', self.html, "Personal nav must display label 'Настройки'")

    # =========================================================================
    # 2. profile.css Styles
    # =========================================================================

    def test_03_profile_css_avatar_and_nav_styles(self):
        """Verify CSS styling for avatar edit section, error feedback, and owner nav widget."""
        # Avatar edit controls
        self.assertIn(".edit-avatar-section", self.css, "CSS must style .edit-avatar-section")
        self.assertIn(".edit-avatar-preview", self.css, "CSS must style .edit-avatar-preview")
        self.assertIn(".edit-avatar-preview-img", self.css, "CSS must style .edit-avatar-preview-img")
        self.assertIn(".edit-avatar-initials", self.css, "CSS must style .edit-avatar-initials")
        self.assertIn(".edit-avatar-actions", self.css, "CSS must style .edit-avatar-actions")
        self.assertIn(".btn-remove-avatar", self.css, "CSS must style .btn-remove-avatar")

        # Error feedback
        self.assertIn(".edit-profile-error", self.css, "CSS must style .edit-profile-error")

        # Owner nav widget
        self.assertIn(".profile-owner-nav-widget", self.css, "CSS must style .profile-owner-nav-widget")
        self.assertIn(".profile-owner-nav-list", self.css, "CSS must style .profile-owner-nav-list")
        self.assertIn(".profile-owner-nav-link", self.css, "CSS must style .profile-owner-nav-link")

    # =========================================================================
    # 3. profile-page.js Avatar Management Logic
    # =========================================================================

    def test_04_profile_page_js_avatar_selection_and_preview(self):
        """Verify avatar selection, preview update, and upload handling in profile-page.js."""
        # Functions defined
        self.assertIn("function handleChooseAvatar", self.page_js, "handleChooseAvatar must be defined")
        self.assertIn("function handleAvatarFileSelected", self.page_js, "handleAvatarFileSelected must be defined")
        self.assertIn("function updateModalAvatarPreview", self.page_js, "updateModalAvatarPreview must be defined")

        # FileReader reads file as data URL
        self.assertIn("FileReader", self.page_js, "Must use FileReader for client-side avatar preview")
        self.assertIn("readAsDataURL", self.page_js, "Must read avatar file with readAsDataURL")

        # Pending data set
        self.assertIn("pendingAvatarData", self.page_js, "Must track pending avatar data")

        # Allowed image formats checked
        self.assertIn("image/png", self.page_js, "Must allow image/png")
        self.assertIn("image/jpeg", self.page_js, "Must allow image/jpeg")
        self.assertIn("image/webp", self.page_js, "Must allow image/webp")
        self.assertIn("image/svg+xml", self.page_js, "Must allow image/svg+xml")

        # Preview update logic
        self.assertIn("editAvatarPreviewImg", self.page_js, "Must update editAvatarPreviewImg element")
        self.assertIn("editAvatarInitials", self.page_js, "Must update editAvatarInitials fallback element")

    def test_05_profile_page_js_avatar_removal(self):
        """Verify avatar removal clears preview and sets removeAvatar flag."""
        self.assertIn("function handleRemoveAvatar", self.page_js, "handleRemoveAvatar must be defined")

        match = re.search(r"function handleRemoveAvatar\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(match, "handleRemoveAvatar function must be present in profile-page.js")
        body = match.group(1)

        self.assertIn("isAvatarRemoved = true", body, "handleRemoveAvatar must set isAvatarRemoved flag to true")
        self.assertIn("pendingAvatarData = null", body, "handleRemoveAvatar must clear pendingAvatarData")
        self.assertIn("updateModalAvatarPreview(null", body, "handleRemoveAvatar must reset modal avatar preview to initials")

    # =========================================================================
    # 4. profile-page.js Input Validation Rules
    # =========================================================================

    def test_06_profile_page_js_input_validation(self):
        """Verify input validation rules for name, specialization, company, bio, website."""
        match = re.search(r"function saveProfileEdit\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(match, "saveProfileEdit function must be present in profile-page.js")
        body = match.group(1)

        # 1. Name required 1..100 chars
        self.assertIn("trimmedName.length > 100", body, "Must check name length not exceeding 100")
        self.assertIn("!trimmedName", body, "Must reject empty name")
        self.assertIn("Имя обязательно для заполнения и должно содержать от 1 до 100 символов", body)

        # 2. Specialization max 120 chars
        self.assertIn("trimmedSpec.length > 120", body, "Must check specialization max 120 chars")
        self.assertIn("Специализация не должна превышать 120 символов", body)

        # 3. Company max 120 chars
        self.assertIn("trimmedComp.length > 120", body, "Must check company max 120 chars")
        self.assertIn("Название компании не должно превышать 120 символов", body)

        # 4. Bio max 1000 chars
        self.assertIn("trimmedBio.length > 1000", body, "Must check bio max 1000 chars")
        self.assertIn("О себе не должно превышать 1000 символов", body)

        # 5. Website URL normalization and scheme validation
        self.assertIn("proto = 'https:' + '//'", body, "Must auto-prepend https when scheme is omitted")
        self.assertIn("site = proto + site", body, "Must auto-prepend https when scheme is omitted")
        self.assertIn("scheme !== 'http' && scheme !== 'https'", body, "Must reject schemes other than http/https")
        self.assertIn("site.length > 300", body, "Must reject website exceeding 300 chars")
        self.assertIn("Адрес сайта должен использовать протокол http или https", body)

    # =========================================================================
    # 5. profile-page.js Save Payload & Success Handling
    # =========================================================================

    def test_07_profile_page_js_save_payload_and_ui_update(self):
        """Verify saveProfileEdit payload assembly, UI update, header sync, and toast feedback."""
        match = re.search(r"function saveProfileEdit\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(match, "saveProfileEdit function must be present in profile-page.js")
        body = match.group(1)

        # 1. Payload structure
        self.assertIn("avatar: newAvatar", body, "Payload must include avatar: newAvatar")
        self.assertIn("removeAvatar: isAvatarRemoved", body, "Payload must include removeAvatar: isAvatarRemoved")
        self.assertIn("name: trimmedName", body, "Payload must include name: trimmedName")
        self.assertIn("website: site", body, "Payload must include website: site")

        # 2. Endpoint URL and method
        self.assertIn("fetch('/api/user/profile'", body, "Must send POST request to /api/user/profile")
        self.assertIn("method: 'POST'", body, "Must use POST method for profile update")

        # 3. Success actions
        self.assertIn("renderProfile(currentProfile)", body, "Must re-render profile on save success")
        self.assertIn("closeEditModal()", body, "Must close edit modal on save success")
        self.assertIn("showToast('Профиль успешно обновлен')", body, "Must display success toast notification")

        # 4. Header user bar sync if own profile
        self.assertIn("updateHeaderUserBar()", body, "Must synchronize header user bar on save success")

    # =========================================================================
    # 6. Owner Personal Navigation Widget Visibility
    # =========================================================================

    def test_08_profile_owner_nav_widget_visibility_logic(self):
        """Verify profileOwnerNavWidget is shown only when viewing own profile."""
        match = re.search(r"function renderSidebar\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(match, "renderSidebar function must be present in profile-page.js")
        body = match.group(1)

        self.assertIn("profileOwnerNavWidget", body, "renderSidebar must control profileOwnerNavWidget")
        self.assertIn("isOwn ? 'flex' : 'none'", body, "profileOwnerNavWidget display must depend on isOwn")

    def test_09_exported_helpers_on_smartcontractum_profile_page(self):
        """Verify avatar and edit helpers are exported on window.SmartContractumProfilePage."""
        self.assertIn("handleChooseAvatar: handleChooseAvatar", self.page_js)
        self.assertIn("handleRemoveAvatar: handleRemoveAvatar", self.page_js)
        self.assertIn("handleAvatarFileSelected: handleAvatarFileSelected", self.page_js)
        self.assertIn("updateModalAvatarPreview: updateModalAvatarPreview", self.page_js)
        self.assertIn("showEditError: showEditError", self.page_js)
        self.assertIn("clearEditError: clearEditError", self.page_js)
        self.assertIn("getPendingAvatarData:", self.page_js)
        self.assertIn("getUploadedAvatarUrl:", self.page_js)
        self.assertIn("getIsAvatarRemoved:", self.page_js)
        self.assertIn("openAvatarCropModal: openAvatarCropModal", self.page_js)
        self.assertIn("closeAvatarCropModal: closeAvatarCropModal", self.page_js)
        self.assertIn("applyAvatarCrop: applyAvatarCrop", self.page_js)
        self.assertIn("getAvatarUploadSeq:", self.page_js)

    def test_11_avatar_cropping_and_settings_navigation(self):
        """Verify avatar cropping logic, race condition safety seq counter, and settings navigation."""
        # 1. Cropping logic and handlers in profile-page.js
        self.assertIn("function openAvatarCropModal", self.page_js)
        self.assertIn("function closeAvatarCropModal", self.page_js)
        self.assertIn("function drawAvatarCropCanvas", self.page_js)
        self.assertIn("function applyAvatarCrop", self.page_js)
        self.assertIn("avatarUploadSeq", self.page_js)

        # 2. Sequential counter guards against stale uploads
        self.assertIn("if (seq !== avatarUploadSeq || isAvatarRemoved) return;", self.page_js)

        # 3. Settings navigation in feed.js opens panel
        feed_js_path = os.path.join(FRONTEND_DIR, "js", "feed.js")
        with open(feed_js_path, "r", encoding="utf-8") as f:
            feed_js = f.read()
        self.assertIn("openFeedSettingsPanel()", feed_js)
        self.assertIn("panelParam === 'settings'", feed_js)

    # =========================================================================
    # 7. Avatar Crop Focus Trap and Escape Handling (Issue #188 Round 2)
    # =========================================================================

    def test_crop_modal_escape_closes_crop_only(self):
        """Verify opening crop modal and pressing Escape closes crop modal while edit modal stays open."""
        # 1. Static code verification: Escape listener checks avatarCropModal first
        escape_match = re.search(r"if\s*\(\s*e\.key\s*===\s*'Escape'\s*\)\s*\{([\s\S]*?)(?:if\s*\(\s*e\.key\s*===\s*'Tab'|\}\s*\);)", self.page_js)
        self.assertIsNotNone(escape_match, "Escape key handler must be present in profile-page.js")
        escape_body = escape_match.group(1)

        crop_idx = escape_body.find("avatarCropModal")
        edit_idx = escape_body.find("editProfileModal")
        self.assertNotEqual(crop_idx, -1, "avatarCropModal must be checked in Escape handler")
        self.assertNotEqual(edit_idx, -1, "editProfileModal must be checked in Escape handler")
        self.assertLess(crop_idx, edit_idx, "avatarCropModal must be checked before editProfileModal in Escape handler")

        self.assertIn("closeAvatarCropModal()", escape_body, "Must call closeAvatarCropModal() on Escape")
        self.assertIn("e.preventDefault()", escape_body, "Must prevent default when Escape dismisses crop modal")

        # 2. Functional Node.js vm verification
        script_body = """
  editModal.style.display = 'flex';
  api.openAvatarCropModal();
  if (cropModal.style.display !== 'flex') {
    console.error('FAIL_CROP_NOT_OPEN');
    process.exit(1);
  }

  const prevented = sendDocKey('Escape', false);
  if (!prevented) {
    console.error('FAIL_ESCAPE_NOT_PREVENTED');
    process.exit(2);
  }
  if (cropModal.style.display !== 'none') {
    console.error('FAIL_CROP_NOT_CLOSED');
    process.exit(3);
  }
  if (editModal.style.display !== 'flex') {
    console.error('FAIL_EDIT_WAS_CLOSED');
    process.exit(4);
  }
  console.log('SUCCESS_ESCAPE_CLOSES_CROP_ONLY');
"""
        proc = self._run_node_script(script_body)
        self.assertEqual(proc.returncode, 0, f"Escape crop test failed: {proc.stderr}")
        self.assertIn("SUCCESS_ESCAPE_CLOSES_CROP_ONLY", proc.stdout)

    def test_crop_modal_focus_restoration_to_trigger(self):
        """Verify closing crop modal returns focus to #btnCropAvatar (the initiator)."""
        # 1. Static code verification
        self.assertIn("let lastCropTriggerEl", self.page_js, "Must declare lastCropTriggerEl")
        open_crop_match = re.search(r"function openAvatarCropModal\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(open_crop_match, "openAvatarCropModal function must be defined")
        self.assertIn("lastCropTriggerEl", open_crop_match.group(1), "openAvatarCropModal must store lastCropTriggerEl")

        close_crop_match = re.search(r"function closeAvatarCropModal\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(close_crop_match, "closeAvatarCropModal function must be defined")
        close_body = close_crop_match.group(1)
        self.assertIn("lastCropTriggerEl", close_body, "closeAvatarCropModal must reference lastCropTriggerEl")
        self.assertIn(".focus()", close_body, "closeAvatarCropModal must restore focus")

        apply_crop_match = re.search(r"function applyAvatarCrop\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(apply_crop_match, "applyAvatarCrop function must be defined")
        self.assertIn("closeAvatarCropModal()", apply_crop_match.group(1), "applyAvatarCrop must call closeAvatarCropModal()")

        # 2. Functional Node.js vm verification
        script_body = """
  btnCropAvatar.focus();
  api.openAvatarCropModal();
  if (cropModal.style.display !== 'flex') {
    console.error('FAIL_CROP_NOT_OPEN');
    process.exit(1);
  }

  // Change focus to inside the crop modal
  zoomInput.focus();
  if (win.document.activeElement !== zoomInput) {
    console.error('FAIL_ZOOM_NOT_FOCUSED');
    process.exit(2);
  }

  // Close crop modal
  api.closeAvatarCropModal();
  if (cropModal.style.display !== 'none') {
    console.error('FAIL_CROP_NOT_CLOSED');
    process.exit(3);
  }
  if (win.document.activeElement !== btnCropAvatar) {
    console.error('FAIL_FOCUS_NOT_RESTORED: ' + (win.document.activeElement ? win.document.activeElement.id : 'null'));
    process.exit(4);
  }

  console.log('SUCCESS_FOCUS_RESTORATION');
"""
        proc = self._run_node_script(script_body)
        self.assertEqual(proc.returncode, 0, f"Focus restoration test failed: {proc.stderr}")
        self.assertIn("SUCCESS_FOCUS_RESTORATION", proc.stdout)

    def test_crop_modal_tab_focus_trap(self):
        """Verify Tab and Shift+Tab cycle focus strictly within #avatarCropModal elements without escaping to #editProfileModal."""
        # 1. Static code verification
        tab_match = re.search(r"if\s*\(\s*e\.key\s*===\s*'Tab'\s*\)\s*\{([\s\S]*?)\n    \}\);", self.page_js)
        self.assertIsNotNone(tab_match, "Tab key handler must be defined in profile-page.js")
        tab_body = tab_match.group(1)

        self.assertIn("avatarCropModal", tab_body, "Tab handler must prioritize avatarCropModal")
        self.assertIn("editProfileModal", tab_body, "Tab handler must handle editProfileModal")
        self.assertIn("e.shiftKey", tab_body, "Tab handler must handle Shift+Tab reverse navigation")
        self.assertIn("e.preventDefault()", tab_body, "Tab handler must prevent default on trap boundaries")

        # 2. Functional Node.js vm verification
        script_body = """
  editModal.style.display = 'flex';
  cropModal.style.display = 'flex';

  // 1. Focus on last element of crop modal (btnApplyCrop) -> Tab wraps to first (btnCloseCrop)
  btnApplyCrop.focus();
  let prev = sendDocKey('Tab', false);
  if (!prev || win.document.activeElement !== btnCloseCrop) {
    console.error('FAIL_TAB_WRAP: ' + (win.document.activeElement ? win.document.activeElement.id : 'null') + ' prev=' + prev);
    process.exit(1);
  }

  // 2. Focus on first element of crop modal (btnCloseCrop) -> Shift+Tab wraps to last (btnApplyCrop)
  btnCloseCrop.focus();
  prev = sendDocKey('Tab', true);
  if (!prev || win.document.activeElement !== btnApplyCrop) {
    console.error('FAIL_SHIFTTAB_WRAP: ' + (win.document.activeElement ? win.document.activeElement.id : 'null') + ' prev=' + prev);
    process.exit(2);
  }

  // 3. Focus on element in underlying edit modal (inpName) -> Tab jumps to crop modal first element
  inpName.focus();
  prev = sendDocKey('Tab', false);
  if (!prev || win.document.activeElement !== btnCloseCrop) {
    console.error('FAIL_OUTSIDE_TAB: ' + (win.document.activeElement ? win.document.activeElement.id : 'null'));
    process.exit(3);
  }

  // 4. Focus on element in underlying edit modal (inpName) -> Shift+Tab jumps to crop modal last element
  inpName.focus();
  prev = sendDocKey('Tab', true);
  if (!prev || win.document.activeElement !== btnApplyCrop) {
    console.error('FAIL_OUTSIDE_SHIFTTAB: ' + (win.document.activeElement ? win.document.activeElement.id : 'null'));
    process.exit(4);
  }

  console.log('SUCCESS_TAB_FOCUS_TRAP');
"""
        proc = self._run_node_script(script_body)
        self.assertEqual(proc.returncode, 0, f"Tab focus trap test failed: {proc.stderr}")
        self.assertIn("SUCCESS_TAB_FOCUS_TRAP", proc.stdout)

    def test_rapid_avatar_change_or_removal_discards_stale_upload(self):
        """Verify rapid selection or removal sets avatarUploadSeq and discards older upload responses."""
        # 1. Static code verification
        self.assertIn("avatarUploadSeq", self.page_js, "Must track avatarUploadSeq")
        self.assertIn("seq !== avatarUploadSeq || isAvatarRemoved", self.page_js, "Must check seq and isAvatarRemoved")

        # 2. Functional Node.js vm verification
        script_body = """
  const initialSeq = api.getAvatarUploadSeq();
  const file1 = { name: 'avatar1.png', type: 'image/png', dataUrl: 'data:image/png;base64,avatar1' };
  api.handleAvatarFileSelected({ target: { files: [file1] } });
  await new Promise(r => setTimeout(r, 10));

  const seq1 = api.getAvatarUploadSeq();
  if (seq1 <= initialSeq) {
    console.error('FAIL_SEQ_NOT_INCREMENTED_ON_SELECT');
    process.exit(1);
  }
  if (uploadResolvers.length !== 1) {
    console.error('FAIL_NO_UPLOAD_PROMISE');
    process.exit(2);
  }

  // Rapid removal before upload resolves
  api.handleRemoveAvatar();
  const seq2 = api.getAvatarUploadSeq();
  if (seq2 <= seq1) {
    console.error('FAIL_SEQ_NOT_INCREMENTED_ON_REMOVE');
    process.exit(3);
  }
  if (!api.getIsAvatarRemoved()) {
    console.error('FAIL_IS_AVATAR_REMOVED_NOT_TRUE');
    process.exit(4);
  }

  // Old upload resolves after removal
  uploadResolvers[0].resolve({
    ok: true,
    json: () => Promise.resolve({ success: true, url: '/media/avatar1_stale.png' })
  });
  await new Promise(r => setTimeout(r, 10));

  if (api.getUploadedAvatarUrl() !== null) {
    console.error('FAIL_STALE_UPLOAD_NOT_DISCARDED: ' + api.getUploadedAvatarUrl());
    process.exit(5);
  }

  console.log('SUCCESS_RAPID_AVATAR_STALE_DISCARD');
"""
        proc = self._run_node_script(script_body)
        self.assertEqual(proc.returncode, 0, f"Rapid avatar stale discard test failed: {proc.stderr}")
        self.assertIn("SUCCESS_RAPID_AVATAR_STALE_DISCARD", proc.stdout)

    # =========================================================================
    # 8. Strict Invariants
    # =========================================================================

    def test_10_strict_invariants(self):
        """Verify zero emojis, zero em dashes, and offline-first compliance across all modified files."""
        files = {
            "profile.html": self.html,
            "profile.css": self.css,
            "profile-page.js": self.page_js,
            "test_file": self.test_py,
        }

        for fname, content in files.items():
            # 1. Zero em dashes
            self.assertNotIn("\u2014", content, f"Em dash forbidden in {fname}")

            # 2. Zero emojis
            for ch in content:
                cp = ord(ch)
                if cp > 127:
                    cat = unicodedata.category(ch)
                    if cat in ("So", "Sk") or (0x1F000 <= cp <= 0x1FFFF):
                        self.fail(f"Emoji '{ch}' (U+{cp:04X}) forbidden in {fname}")

            # 3. 100% offline-first: no external CDN scripts, styles or fonts
            if fname in ("profile.html", "profile.css", "profile-page.js"):
                external_matches = re.findall(r'https?://[^\s\'"<>]+', content)
                for ext in external_matches:
                    # Allow internal/local documentation references, share links, or mock protocols
                    if any(allowed in ext for allowed in ["t.me/", "vk.com/", "connect.ok.ru/", "schema.org"]):
                        continue
                    # Ensure no CDN resource links are imported
                    self.assertNotIn(
                        "cdn", ext.lower(), f"External CDN link forbidden in {fname}: {ext}"
                    )
                    self.assertNotIn(
                        "unpkg", ext.lower(), f"External unpkg link forbidden in {fname}: {ext}"
                    )
                    self.assertNotIn(
                        "cdnjs", ext.lower(), f"External cdnjs link forbidden in {fname}: {ext}"
                    )


if __name__ == "__main__":
    unittest.main()
