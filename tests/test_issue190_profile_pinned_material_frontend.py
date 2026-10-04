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

    def test_08_profile_page_js_exports(self):
        """Verify pinned material functions are exported on window.SmartContractumProfilePage."""
        exports = ['renderPinnedMaterial', 'pinMaterial', 'unpinMaterial', 'updateCardPinButtons']
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


if __name__ == "__main__":
    unittest.main()
