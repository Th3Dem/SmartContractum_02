#!/usr/bin/env python3
"""
tests/test_issue185_profile_card_actions_auth.py

Automated test suite for Issue #185:
[P1][frontend][PROFILE] Подключить действия карточек, авторизацию и общую шапку

Verifies:
1. Card callbacks presence and wiring in profile-page.js:
   - renderPublicationsTab and renderQuestionsTab pass full callbacks to SmartContractumCard.createCardElement.
   - Helper functions: toggleArticleLike, toggleArticleBookmark, openArticleShare, openArticleReport, isItemBookmarked, isItemReported.
   - Guest authentication handling (openAuthModal + showToast).
   - Optimistic UI updates and rollback handling.
2. Header user menu and auth modal elements in profile.html & profile-page.js:
   - #headerUserMenu, #headerMenuProfileLink, #headerLogoutBtn.
   - #authModal, #btnAuthLoginDemo, #btnAuthLoginSubmit, #authUserIdInput.
   - Outside click dismissal, logout without confirm prompt.
3. Avatar onerror fallback handler:
   - profileAvatarImg onerror fallback in markup and script.
4. Report modal and share popover markup:
   - #articleReportModal, #articleReportForm, reasons, details, submit/cancel.
   - #feedSharePopover, copy and social actions.
   - #btnProfileMore copies profile URL with toast.
5. Invariants:
   - Zero emojis across files.
   - Zero em dashes across files.
   - 100% offline-first.
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
CARD_JS_PATH = os.path.join(FRONTEND_DIR, "js", "card.js")


class TestIssue185ProfileCardActionsAuth(unittest.TestCase):
    """Automated test suite verifying Issue #185 acceptance criteria."""

    @classmethod
    def setUpClass(cls):
        with open(HTML_PATH, "r", encoding="utf-8") as f:
            cls.html = f.read()
        with open(PAGE_JS_PATH, "r", encoding="utf-8") as f:
            cls.page_js = f.read()
        with open(CSS_PATH, "r", encoding="utf-8") as f:
            cls.css = f.read()
        with open(CARD_JS_PATH, "r", encoding="utf-8") as f:
            cls.card_js = f.read()

    # =========================================================================
    # 1. Card Callbacks Presence and Wiring
    # =========================================================================

    def test_publications_tab_passes_full_card_callbacks(self):
        """Verify renderPublicationsTab supplies full action callbacks to SmartContractumCard."""
        pub_func_match = re.search(r"function renderPublicationsTab\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(pub_func_match, "renderPublicationsTab function must exist in profile-page.js")
        pub_body = pub_func_match.group(1)

        self.assertIn("onLikeToggle: toggleArticleLike", pub_body)
        self.assertIn("onBookmarkToggle: toggleArticleBookmark", pub_body)
        self.assertIn("onShareClick: openArticleShare", pub_body)
        self.assertIn("onReportClick: openArticleReport", pub_body)
        self.assertIn("isBookmarked: isItemBookmarked", pub_body)
        self.assertIn("isReported: isItemReported", pub_body)
        self.assertIn("onAuthorClick:", pub_body)
        self.assertIn("currentUserId:", pub_body)

    def test_questions_tab_passes_full_card_callbacks(self):
        """Verify renderQuestionsTab supplies full action callbacks to SmartContractumCard."""
        quest_func_match = re.search(r"function renderQuestionsTab\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(quest_func_match, "renderQuestionsTab function must exist in profile-page.js")
        quest_body = quest_func_match.group(1)

        self.assertIn("onLikeToggle: toggleArticleLike", quest_body)
        self.assertIn("onBookmarkToggle: toggleArticleBookmark", quest_body)
        self.assertIn("onShareClick: openArticleShare", quest_body)
        self.assertIn("onReportClick: openArticleReport", quest_body)
        self.assertIn("isBookmarked: isItemBookmarked", quest_body)
        self.assertIn("isReported: isItemReported", quest_body)
        self.assertIn("onAuthorClick:", quest_body)
        self.assertIn("currentUserId:", quest_body)

    def test_card_action_helper_functions_defined(self):
        """Verify presence of concise card action helpers in profile-page.js."""
        helpers = [
            "toggleArticleLike",
            "toggleArticleBookmark",
            "openArticleShare",
            "closeSharePopover",
            "openArticleReport",
            "closeArticleReportModal",
            "isItemBookmarked",
            "isItemReported",
            "markArticleReported"
        ]
        for fn_name in helpers:
            self.assertRegex(
                self.page_js,
                rf"function\s+{fn_name}\s*\(",
                f"Helper function {fn_name} must be defined in profile-page.js"
            )

    def test_guest_triggers_auth_modal_on_actions(self):
        """Verify unauthenticated user triggers openAuthModal() and toast on like, bookmark, report."""
        # 1. toggleArticleLike
        like_match = re.search(r"function toggleArticleLike\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(like_match)
        like_body = like_match.group(1)
        self.assertIn("if (!currentUser)", like_body)
        self.assertIn("openAuthModal()", like_body)
        self.assertIn("showToast(", like_body)

        # 2. toggleArticleBookmark
        bm_match = re.search(r"function toggleArticleBookmark\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(bm_match)
        bm_body = bm_match.group(1)
        self.assertIn("if (!currentUser)", bm_body)
        self.assertIn("openAuthModal()", bm_body)
        self.assertIn("showToast(", bm_body)

        # 3. openArticleReport
        rep_match = re.search(r"function openArticleReport\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(rep_match)
        rep_body = rep_match.group(1)
        self.assertIn("if (!currentUser)", rep_body)
        self.assertIn("openAuthModal()", rep_body)
        self.assertIn("showToast(", rep_body)

    def test_optimistic_ui_and_rollback_logic(self):
        """Verify optimistic UI updates with error rollback in like and bookmark handlers."""
        like_match = re.search(r"function toggleArticleLike\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(like_match)
        like_body = like_match.group(1)
        self.assertIn("btn.classList.toggle('is-liked'", like_body)
        self.assertIn("/api/articles/", like_body)
        self.assertIn("/like", like_body)
        # Rollback check
        self.assertIn("btn.classList.toggle('is-liked', currentLiked)", like_body)

        bm_match = re.search(r"function toggleArticleBookmark\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(bm_match)
        bm_body = bm_match.group(1)
        self.assertIn("btn.classList.toggle('is-bookmarked'", bm_body)
        self.assertIn("/save", bm_body)
        self.assertIn("/unsave", bm_body)
        # Rollback check
        self.assertIn("btn.classList.toggle('is-bookmarked', wasActive)", bm_body)

    def test_auth_401_triggers_rollback_no_false_positive_state(self):
        """Verify 401 response executes unconditional rollback for likes and bookmarks."""
        # 1. Like action catch block
        like_func_match = re.search(r"function toggleArticleLike\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(like_func_match, "toggleArticleLike must exist in profile-page.js")
        like_body = like_func_match.group(1)
        like_catch_match = re.search(r"\.catch\s*\(\s*function\s*\(\s*err\s*\)\s*\{([\s\S]*?)\n      \}\s*\)", like_body)
        self.assertIsNotNone(like_catch_match, "toggleArticleLike must have a .catch handler")
        like_catch = like_catch_match.group(1)

        self.assertNotIn("if (err.message !== 'AUTH_REQUIRED')", like_catch,
                         "Rollback must not be skipped when err.message === 'AUTH_REQUIRED'")
        self.assertIn("btn.classList.toggle('is-liked', currentLiked)", like_catch)
        self.assertIn("btn.setAttribute('aria-pressed', currentLiked ? 'true' : 'false')", like_catch)
        self.assertIn("countEl.textContent = currentCount", like_catch)
        self.assertIn("item.hasLiked = currentLiked", like_catch)
        self.assertIn("item.likesCount = currentCount", like_catch)
        self.assertIn("err.message === 'AUTH_REQUIRED'", like_catch)
        self.assertIn("showToast('Войдите, чтобы поставить отметку')", like_catch)

        # 2. Bookmark action catch block
        bm_func_match = re.search(r"function toggleArticleBookmark\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(bm_func_match, "toggleArticleBookmark must exist in profile-page.js")
        bm_body = bm_func_match.group(1)
        bm_catch_match = re.search(r"\.catch\s*\(\s*function\s*\(\s*err\s*\)\s*\{([\s\S]*?)\n      \}\s*\)", bm_body)
        self.assertIsNotNone(bm_catch_match, "toggleArticleBookmark must have a .catch handler")
        bm_catch = bm_catch_match.group(1)

        self.assertNotIn("if (err.message !== 'AUTH_REQUIRED')", bm_catch,
                         "Rollback must not be skipped when err.message === 'AUTH_REQUIRED'")
        self.assertIn("btn.classList.toggle('is-bookmarked', wasActive)", bm_catch)
        self.assertIn("btn.classList.toggle('is-saved', wasActive)", bm_catch)
        self.assertIn("svg.setAttribute('fill', wasActive ? 'currentColor' : 'none')", bm_catch)
        self.assertIn("countEl.textContent = prevCount", bm_catch)
        self.assertIn("item.hasSaved = wasActive", bm_catch)
        self.assertIn("item.isSaved = wasActive", bm_catch)
        self.assertIn("item.isBookmarked = wasActive", bm_catch)
        self.assertIn("item.savesCount = prevCount", bm_catch)
        self.assertIn("saveBookmarks(rbBms)", bm_catch)
        self.assertIn("err.message === 'AUTH_REQUIRED'", bm_catch)
        self.assertIn("showToast('Для сохранения публикации необходимо войти')", bm_catch)

    # =========================================================================
    # 2. Header User Menu, Notifications and Auth Modal in profile.html & JS
    # =========================================================================

    def test_header_user_menu_elements_present_in_html(self):
        """Verify #headerUserMenu, #headerMenuProfileLink, and #headerLogoutBtn in profile.html."""
        self.assertIn('id="headerUserMenu"', self.html)
        self.assertIn('class="header-user-menu"', self.html)
        self.assertIn('id="headerMenuProfileLink"', self.html)
        self.assertIn('id="headerLogoutBtn"', self.html)
        self.assertIn('class="header-user-menu-item', self.html)
        self.assertIn('role="menu"', self.html)

    def test_auth_modal_elements_present_in_html(self):
        """Verify unified authModal with demo login and custom username input in profile.html."""
        self.assertIn('id="authModal"', self.html)
        self.assertIn('id="btnCloseAuthModal"', self.html)
        self.assertIn('id="btnAuthLoginDemo"', self.html)
        self.assertIn('id="btnAuthLoginSubmit"', self.html)
        self.assertIn('id="authUserIdInput"', self.html)
        self.assertIn('id="authCustomForm"', self.html)

    def test_header_login_and_user_menu_logic_in_js(self):
        """Verify headerLoginBtn toggles menu when logged in and opens modal when guest."""
        self.assertIn("document.getElementById('headerLoginBtn')", self.page_js)
        self.assertIn("document.getElementById('headerUserMenu')", self.page_js)
        self.assertIn("document.getElementById('headerLogoutBtn')", self.page_js)

        # Outside click handling
        self.assertRegex(
            self.page_js,
            r"!menu\.contains\(e\.target\)\s*&&\s*!\(loginBtn\s*&&\s*loginBtn\.contains\(e\.target\)\)",
            "Outside click must dismiss header user menu"
        )

        # Logout calls endpoint without confirm prompt
        self.assertNotIn("confirm('Вы вошли как", self.page_js, "Old confirm logout popup must be eliminated")
        self.assertIn("fetch('/api/auth/logout', { method: 'POST' })", self.page_js)

    def test_custom_and_demo_login_in_js(self):
        """Verify authModal handles custom username submission and demo login."""
        self.assertIn("document.getElementById('btnAuthLoginDemo')", self.page_js)
        self.assertIn("document.getElementById('btnAuthLoginSubmit')", self.page_js)
        self.assertIn("document.getElementById('authUserIdInput')", self.page_js)
        self.assertIn("performLogin('user_demo', 'Демо Пользователь')", self.page_js)
        self.assertIn("fetch('/api/auth/login',", self.page_js)

    def test_header_notification_button_and_popup_wiring(self):
        """Verify header notification button, badge, popup markup and event listeners."""
        # 1. Markup verification in profile.html
        self.assertIn('id="headerNotificationsBtn"', self.html)
        self.assertIn('id="headerNotifBadge"', self.html)
        self.assertIn('id="headerNotifPopup"', self.html)
        self.assertIn('id="notifListContainer"', self.html)
        self.assertIn('id="notifMarkAllReadBtn"', self.html)
        self.assertIn('id="headerNotifWrap"', self.html)

        # 2. Logic verification in profile-page.js
        self.assertIn("function loadHeaderNotifications()", self.page_js)
        self.assertIn("fetch('/api/notifications')", self.page_js)
        self.assertIn("fetch('/api/notifications/read'", self.page_js)
        self.assertIn("document.getElementById('headerNotificationsBtn')", self.page_js)
        self.assertIn("document.getElementById('headerNotifPopup')", self.page_js)
        self.assertIn("document.getElementById('notifListContainer')", self.page_js)
        self.assertIn("document.getElementById('notifMarkAllReadBtn')", self.page_js)

        # Popup toggle on button click
        self.assertRegex(
            self.page_js,
            r"notifBtn\.addEventListener\('click'[\s\S]*?notifPopup\.style\.display\s*!==\s*'none'",
            "Clicking notification button must toggle popup visibility"
        )

        # Outside click dismissal
        self.assertRegex(
            self.page_js,
            r"!notifWrap\.contains\(e\.target\)",
            "Clicking outside notifWrap must dismiss notification popup"
        )

        # Escape key dismissal
        escape_match = re.search(r"document\.addEventListener\('keydown'[\s\S]*?e\.key === 'Escape'[\s\S]*?\}\);", self.page_js)
        self.assertIsNotNone(escape_match)
        self.assertIn("headerNotifPopup", escape_match.group(0))

        # Initial load when authenticated
        init_match = re.search(r"function init\(\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(init_match)
        self.assertIn("loadHeaderNotifications()", init_match.group(1))

        # Reset on logout
        logout_match = re.search(r"logoutBtn\.addEventListener\('click'[\s\S]*?fetch\('/api/auth/logout'[\s\S]*?\}\);", self.page_js)
        self.assertIsNotNone(logout_match)
        self.assertIn("headerNotifBadge", logout_match.group(0))
        self.assertIn("headerNotifPopup", logout_match.group(0))

    # =========================================================================
    # 3. Avatar onerror Fallback Handler
    # =========================================================================

    def test_avatar_onerror_fallback_in_html_and_js(self):
        """Verify avatar onerror displays initials fallback on broken image URL."""
        # 1. Markup inline onerror fallback
        avatar_img_match = re.search(r'<img[^>]*id="profileAvatarImg"[^>]*>', self.html)
        self.assertIsNotNone(avatar_img_match, "#profileAvatarImg must be present in profile.html")
        avatar_img_tag = avatar_img_match.group(0)
        self.assertIn("onerror=", avatar_img_tag, "profileAvatarImg must include onerror handler in markup")
        self.assertIn("profileAvatarInitials", avatar_img_tag)

        # 2. Script dynamic onerror fallback
        self.assertIn("avatarImg.onerror", self.page_js, "avatarImg.onerror handler must be attached in script")
        self.assertIn("avatarInitials.style.display = 'block'", self.page_js)

    # =========================================================================
    # 4. Report Modal and Share Popover Markup and JS Wiring
    # =========================================================================

    def test_article_report_modal_markup_and_js(self):
        """Verify #articleReportModal markup and form submission wiring."""
        self.assertIn('id="articleReportModal"', self.html)
        self.assertIn('id="articleReportForm"', self.html)
        self.assertIn('id="reportArticleId"', self.html)
        self.assertIn('name="articleReportReason"', self.html)
        self.assertIn('id="articleReportDetails"', self.html)
        self.assertIn('id="btnCloseArticleReportModal"', self.html)
        self.assertIn('id="btnCancelArticleReport"', self.html)
        self.assertIn('id="btnSubmitArticleReport"', self.html)

        # JS wiring
        self.assertIn("document.getElementById('articleReportModal')", self.page_js)
        self.assertIn("document.getElementById('articleReportForm')", self.page_js)
        self.assertIn("fetch('/api/articles/' + encodeURIComponent(articleId) + '/report'", self.page_js)
        self.assertIn("markArticleReported(articleId)", self.page_js)

    def test_share_popover_markup_and_js(self):
        """Verify #feedSharePopover markup, social links, copy button, and outside click dismissal."""
        self.assertIn('id="feedSharePopover"', self.html)
        self.assertIn('data-action="copy"', self.html)
        self.assertIn('data-action="telegram"', self.html)
        self.assertIn('data-action="vk"', self.html)
        self.assertIn('data-action="ok"', self.html)

        # JS wiring
        self.assertIn("document.getElementById('feedSharePopover')", self.page_js)
        self.assertIn("closeSharePopover()", self.page_js)
        self.assertIn("!popover.contains(e.target) && !e.target.closest('.btn-card-share')", self.page_js)

    def test_profile_more_button_copies_profile_url(self):
        """Verify #btnProfileMore copies profile URL with expected toast notification."""
        self.assertIn('id="btnProfileMore"', self.html)
        self.assertIn("btnMore.addEventListener('click', copyProfileLink)", self.page_js)
        self.assertIn("copyTextToClipboard(window.location.href, 'Ссылка на профиль скопирована')", self.page_js)

    # =========================================================================
    # 5. Export and Global Compatibility
    # =========================================================================

    def test_profile_page_exports_include_card_and_auth_methods(self):
        """Verify window.SmartContractumProfilePage exports all relevant methods."""
        export_match = re.search(r"window\.SmartContractumProfilePage\s*=\s*\{([\s\S]*?)\};", self.page_js)
        self.assertIsNotNone(export_match, "SmartContractumProfilePage must be exported on window")
        export_body = export_match.group(1)

        required_exports = [
            "renderPublicationsTab",
            "renderQuestionsTab",
            "toggleArticleLike",
            "toggleArticleBookmark",
            "openArticleShare",
            "closeSharePopover",
            "openArticleReport",
            "closeArticleReportModal",
            "isItemBookmarked",
            "isItemReported",
            "openAuthModal",
            "closeAuthModal",
            "setAuthState",
            "loadHeaderNotifications"
        ]
        for exp in required_exports:
            self.assertIn(exp, export_body, f"Method {exp} must be exported in SmartContractumProfilePage")

        self.assertIn("window.openAuthModal = openAuthModal;", self.page_js)

    # =========================================================================
    # 6. Strict Invariants
    # =========================================================================

    def test_zero_emojis(self):
        """Verify zero emojis in profile-page.js, profile.html, and profile.css."""
        for path, content in [
            ("profile.html", self.html),
            ("profile-page.js", self.page_js),
            ("profile.css", self.css)
        ]:
            emojis = [c for c in content if "EMOJI" in unicodedata.name(c, "")]
            self.assertEqual(len(emojis), 0, f"Found emojis in {path}: {emojis}")

    def test_zero_em_dashes(self):
        """Verify zero em dashes (\\u2014) in profile-page.js, profile.html, and profile.css."""
        for path, content in [
            ("profile.html", self.html),
            ("profile-page.js", self.page_js),
            ("profile.css", self.css)
        ]:
            self.assertNotIn("\u2014", content, f"Found em dash (\\u2014) in {path}")
            self.assertNotIn(chr(0x2014), content, f"Found em dash character in {path}")

    def test_offline_first_integrity(self):
        """Verify no external CDN or font resources in profile.html."""
        external_refs = re.findall(r'(?:href|src)=["\']https?://[^"\']+', self.html)
        # Social share intent links (t.me, vk.com, ok.ru) in popover are acceptable
        for ref in external_refs:
            self.assertFalse(
                any(cdn in ref for cdn in ["cdnjs", "unpkg", "jsdelivr", "fonts.googleapis", "fonts.gstatic"]),
                f"External CDN found in profile.html: {ref}"
            )


if __name__ == "__main__":
    unittest.main()
