#!/usr/bin/env python3
"""
tests/test_issue188_profile_edit_frontend.py

Issue #188 (edit profile, avatar, personal navigation) as it stands after Issue #234:
profile fields are edited on settings.html#profile, and the profile page keeps only
the in-place cover and avatar change through the shared crop dialog.

Verifies:
1. The profile page has no edit dialog of its own; "Edit profile" leads to settings.
2. The owner's personal navigation widget links to drafts, materials, saved items,
   subscriptions and settings.html, and is shown only on one's own profile.
3. The avatar and cover change in place through js/media-crop.js and /api/user/profile-media.
4. Invariants: zero emojis, zero em dashes, offline-first.
"""

import os
import re
import unittest
import unicodedata

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")
HTML_PATH = os.path.join(FRONTEND_DIR, "profile.html")
PAGE_JS_PATH = os.path.join(FRONTEND_DIR, "js", "profile-page.js")
MEDIA_JS_PATH = os.path.join(FRONTEND_DIR, "js", "profile-media.js")
CSS_PATH = os.path.join(FRONTEND_DIR, "css", "profile.css")


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class TestIssue188ProfileEditFrontend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = read(HTML_PATH)
        cls.page_js = read(PAGE_JS_PATH)
        cls.media_js = read(MEDIA_JS_PATH)
        cls.css = read(CSS_PATH)
        cls.test_py = read(__file__)

    def test_01_no_second_edit_form_on_the_profile(self):
        for marker in ("editProfileModal", "avatarCropModal", "editProfileName", "btnChooseAvatar"):
            self.assertNotIn(marker, self.html, f"{marker} belongs to the removed edit dialog")
            self.assertNotIn(marker, self.page_js, f"{marker} belongs to the removed edit dialog")
        for fn in ("openEditModal", "saveProfileEdit", "handleAvatarFileSelected", "applyAvatarCrop"):
            self.assertNotIn(fn, self.page_js)

    def test_02_edit_button_leads_to_settings(self):
        match = re.search(r'<a[^>]*id="btnProfileEdit"[^>]*>', self.html)
        self.assertIsNotNone(match, "Edit profile is a link")
        self.assertIn('href="settings.html#profile"', match.group(0))
        self.assertIn("display: none;", match.group(0), "hidden until the owner is known")
        self.assertIn("btnEdit.style.display = 'inline-flex'", self.page_js)

    def test_03_owner_navigation_widget(self):
        widget = re.search(r'<div[^>]*id="profileOwnerNavWidget"[^>]*>', self.html)
        self.assertIsNotNone(widget)
        self.assertIn("display: none;", widget.group(0))
        for href, label in (("editor.html", "Черновики"), ("my-materials.html", "Мои материалы"),
                            ("feed.html?tab=saved", "Сохраненное"), ("feed.html?tab=my", "Подписки"),
                            ("settings.html", "Настройки")):
            self.assertIn(f'href="{href}"', self.html)
            self.assertIn(label, self.html)
        self.assertNotIn("panel=settings", self.html, "the old settings panel is gone")

    def test_04_owner_navigation_visibility_logic(self):
        match = re.search(r"function renderSidebar\s*\([^\)]*\)\s*\{([\s\S]*?)\n  \}", self.page_js)
        self.assertIsNotNone(match)
        self.assertIn("profileOwnerNavWidget", match.group(1))
        self.assertIn("isOwn ? 'flex' : 'none'", match.group(1))

    def test_05_avatar_and_cover_change_in_place(self):
        self.assertIn('<script src="js/media-crop.js"></script>', self.html)
        self.assertIn('<script src="js/profile-media.js"></script>', self.html)
        self.assertIn("/api/user/profile-media", self.media_js)
        self.assertIn("data-avatar-edit", self.media_js)
        self.assertIn("kind: 'avatar'", self.media_js)
        self.assertIn("state.isOwn", self.media_js, "only the owner gets the buttons")
        self.assertIn(".profile-avatar-edit", self.css)

    def test_06_owner_empty_overview_suggests_next_steps(self):
        self.assertIn("profile-empty-owner", self.page_js)
        self.assertIn('href="editor.html">Написать публикацию', self.page_js)
        self.assertIn('href="settings.html#profile">Заполнить профиль', self.page_js)

    def test_07_strict_invariants(self):
        files = {"profile.html": self.html, "profile.css": self.css, "profile-page.js": self.page_js,
                 "profile-media.js": self.media_js, "test_file": self.test_py}
        for fname, content in files.items():
            self.assertNotIn(chr(0x2014), content, f"Em dash forbidden in {fname}")
            for ch in content:
                cp = ord(ch)
                if cp > 127 and (unicodedata.category(ch) in ("So", "Sk") or 0x1F000 <= cp <= 0x1FFFF):
                    self.fail(f"Emoji U+{cp:04X} forbidden in {fname}")
            if fname != "test_file":
                for ext in re.findall(r'https?://[^\s\'"<>]+', content):
                    if any(allowed in ext for allowed in ["t.me/", "vk.com/", "connect.ok.ru/", "schema.org"]):
                        continue
                    for cdn in ("cdn", "unpkg"):
                        self.assertNotIn(cdn, ext.lower(), f"External link forbidden in {fname}: {ext}")


if __name__ == "__main__":
    unittest.main()
