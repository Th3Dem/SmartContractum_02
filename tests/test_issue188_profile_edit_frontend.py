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
    # 7. Strict Invariants
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
