#!/usr/bin/env python3
"""
tests/test_issue85_unify_save_terminology.py

Automated test suite for Issue #85:
1. Unified Save Terminology in frontend/public/article.html and frontend/public/js/article.js:
   - Inactive state:
     * Button text / title: 'Сохранить'
     * aria-label: 'Сохранить публикацию'
   - Active state (saved):
     * Button text / title: 'Сохранено'
     * aria-label: 'Удалить из сохраненного'
   - Toast notifications:
     * Added: 'Публикация сохранена'
     * Removed: 'Публикация удалена из сохраненного'
   - In localStorage:
     * Key remains strictly 'sc_bookmarks' for 100% backward compatibility.
     * Keep CSS class .is-bookmarked alongside .is-saved.
2. Unified Save Terminology in frontend/public/js/card.js:
   - Feed cards display 'Сохранить' / 'Сохранено' and fire matching toasts.
   - Fallback methods and helper functions for button states and storage.
3. Invariants:
   - Zero emojis.
   - Zero em dashes.
   - 100% offline-first.
"""

import os
import re
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def read_file(relative_path: str) -> str:
    full_path = os.path.join(PROJECT_ROOT, relative_path)
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()


class TestIssue85UnifySaveTerminology(unittest.TestCase):
    """Test suite for unified save terminology across article and feed cards."""

    @classmethod
    def setUpClass(cls):
        cls.article_html = read_file("frontend/public/article.html")
        cls.article_css = read_file("frontend/public/css/article.css")
        cls.article_js = read_file("frontend/public/js/article.js")
        cls.card_js = read_file("frontend/public/js/card.js")
        cls.feed_css = read_file("frontend/public/css/feed.css")

    def test_01_article_html_bookmark_elements_attributes(self):
        """Verify bookmark buttons in article.html have title 'Сохранить' and aria-label 'Сохранить публикацию'."""
        # 1. Desktop Rail Bookmark button
        rail_bm = re.search(r'<button[^>]*id="railBtnBookmark"[^>]*>', self.article_html)
        self.assertIsNotNone(rail_bm, "#railBtnBookmark must exist in article.html")
        self.assertIn('title="Сохранить"', rail_bm.group(0))
        self.assertIn('aria-label="Сохранить публикацию"', rail_bm.group(0))

        # 2. Top Action Bookmark button
        top_bm = re.search(r'<button[^>]*id="btnArticleBookmark"[^>]*>(.*?)</button>', self.article_html, re.DOTALL)
        self.assertIsNotNone(top_bm, "#btnArticleBookmark must exist in article.html")
        self.assertIn('title="Сохранить"', top_bm.group(0))
        self.assertIn('aria-label="Сохранить публикацию"', top_bm.group(0))
        self.assertIn('<span class="bookmark-text">Сохранить</span>', top_bm.group(0))

        # 3. Bottom Action Bookmark button
        bot_bm = re.search(r'<button[^>]*id="btnArticleBookmarkBottom"[^>]*>(.*?)</button>', self.article_html, re.DOTALL)
        self.assertIsNotNone(bot_bm, "#btnArticleBookmarkBottom must exist in article.html")
        self.assertIn('title="Сохранить"', bot_bm.group(0))
        self.assertIn('aria-label="Сохранить публикацию"', bot_bm.group(0))
        self.assertIn('Сохранить', bot_bm.group(0))

        # 4. Mobile Action Bar Bookmark button
        mob_bm = re.search(r'<button[^>]*id="mobileBtnBookmark"[^>]*>', self.article_html)
        self.assertIsNotNone(mob_bm, "#mobileBtnBookmark must exist in article.html")
        self.assertIn('title="Сохранить"', mob_bm.group(0))
        self.assertIn('aria-label="Сохранить публикацию"', mob_bm.group(0))

        # 5. Ensure legacy 'В закладки' is removed from all 4 buttons in article.html
        self.assertNotIn('В закладки', rail_bm.group(0))
        self.assertNotIn('В закладки', top_bm.group(0))
        self.assertNotIn('В закладки', bot_bm.group(0))
        self.assertNotIn('В закладки', mob_bm.group(0))

    def test_02_article_js_sync_bookmark_buttons_inactive_state(self):
        """Verify syncBookmarkButtons in article.js sets title/label to 'Сохранить' and aria-label to 'Сохранить публикацию'."""
        self.assertIn("function syncBookmarkButtons(id)", self.article_js)
        # Slicing syncBookmarkButtons implementation
        fn_start = self.article_js.find("function syncBookmarkButtons(id)")
        fn_end = self.article_js.find("function showToast(message)", fn_start)
        fn_body = self.article_js[fn_start:fn_end]

        # Verify inactive state assignments
        self.assertIn("bookmarked ? 'Сохранено' : 'Сохранить'", fn_body)
        self.assertIn("bookmarked ? 'Удалить из сохраненного' : 'Сохранить публикацию'", fn_body)
        self.assertNotIn("В закладках", fn_body)
        self.assertNotIn("В закладки", fn_body)

    def test_03_article_js_sync_bookmark_buttons_classes(self):
        """Verify syncBookmarkButtons toggles both .is-bookmarked and .is-saved alongside aria-pressed."""
        fn_start = self.article_js.find("function syncBookmarkButtons(id)")
        fn_end = self.article_js.find("function showToast(message)", fn_start)
        fn_body = self.article_js[fn_start:fn_end]

        self.assertIn("btn.classList.toggle('is-bookmarked', bookmarked);", fn_body)
        self.assertIn("btn.classList.toggle('is-saved', bookmarked);", fn_body)
        self.assertIn("btn.setAttribute('aria-pressed', bookmarked ? 'true' : 'false');", fn_body)

    def test_04_article_js_toggle_bookmark_toasts(self):
        """Verify toggleBookmark in article.js uses 'Публикация сохранена' and 'Публикация удалена из сохраненного'."""
        fn_start = self.article_js.find("function toggleBookmark(id)")
        fn_end = self.article_js.find("function syncBookmarkButtons(id)", fn_start)
        fn_body = self.article_js[fn_start:fn_end]

        self.assertIn("showToast('Публикация сохранена');", fn_body)
        self.assertIn("showToast('Публикация удалена из сохраненного');", fn_body)
        self.assertNotIn("Статья сохранена в закладки", fn_body)
        self.assertNotIn("Статья удалена из закладок", fn_body)

    def test_05_localstorage_sc_bookmarks_compatibility(self):
        """Verify storage key strictly remains sc_bookmarks for 100% backward compatibility."""
        self.assertIn("localStorage.getItem('sc_bookmarks')", self.article_js)
        self.assertIn("localStorage.setItem('sc_bookmarks'", self.article_js)
        self.assertIn("getBookmarks", self.article_js)
        self.assertIn("isBookmarked", self.article_js)

        # In card.js
        self.assertIn("localStorage.getItem('sc_bookmarks')", self.card_js)
        self.assertIn("localStorage.setItem('sc_bookmarks'", self.card_js)

    def test_06_card_js_render_card_inner_html_save_terminology(self):
        """Verify renderCardInnerHtml in card.js uses 'Сохранить'/'Сохранено' and appropriate aria-labels."""
        fn_start = self.card_js.find("function renderCardInnerHtml(")
        fn_end = self.card_js.find("function createCardElement(", fn_start)
        fn_body = self.card_js[fn_start:fn_end]

        self.assertIn("const bookmarkTooltip = isBookmarked ? 'Сохранено' : 'Сохранить';", fn_body)
        self.assertIn("const bookmarkAriaLabel = isBookmarked ? 'Удалить из сохраненного' : 'Сохранить публикацию';", fn_body)
        self.assertIn("is-bookmarked is-saved", fn_body)
        self.assertIn('title="\' + bookmarkTooltip + \'"', fn_body)
        self.assertIn('aria-label="\' + bookmarkAriaLabel + \'"', fn_body)

    def test_07_card_js_helpers_and_toasts(self):
        """Verify card.js provides updateBookmarkButtonState, toggleCardBookmark, and correct toasts."""
        self.assertIn("function updateBookmarkButtonState(btn, isBookmarked)", self.card_js)
        self.assertIn("function toggleCardBookmark(id, btn)", self.card_js)
        self.assertIn("showCardToast('Публикация сохранена');", self.card_js)
        self.assertIn("showCardToast('Публикация удалена из сохраненного');", self.card_js)

        # SmartContractumCard exports
        self.assertIn("updateBookmarkButtonState: updateBookmarkButtonState", self.card_js)
        self.assertIn("toggleCardBookmark: toggleCardBookmark", self.card_js)
        self.assertIn("isCardBookmarked: isCardBookmarked", self.card_js)

    def test_08_css_classes_support_is_bookmarked_and_is_saved(self):
        """Verify CSS selectors in article.css and feed.css support .is-saved alongside .is-bookmarked."""
        # article.css
        self.assertIn(".btn-action-bookmark.is-bookmarked", self.article_css)
        self.assertIn(".btn-action-bookmark.is-saved", self.article_css)
        self.assertIn(".btn-rail-bookmark.is-bookmarked", self.article_css)
        self.assertIn(".btn-rail-bookmark.is-saved", self.article_css)
        self.assertIn(".btn-mobile-bookmark.is-bookmarked", self.article_css)
        self.assertIn(".btn-mobile-bookmark.is-saved", self.article_css)

        # feed.css
        self.assertIn(".btn-card-bookmark.is-bookmarked", self.feed_css)
        self.assertIn(".btn-card-bookmark.is-saved", self.feed_css)

    def test_09_card_js_create_card_element_fallback_and_event(self):
        """Verify createCardElement falls back to isCardBookmarked and wires toggleCardBookmark."""
        self.assertIn("isCardBookmarked(item.id)", self.card_js)
        self.assertIn("toggleCardBookmark(item.id, bookmarkBtn)", self.card_js)

    def test_10_zero_emojis_no_em_dashes_offline_first(self):
        """Verify zero emojis, zero em dashes, and offline-first compliance across all modified files."""
        files_to_check = [
            ("frontend/public/article.html", self.article_html),
            ("frontend/public/css/article.css", self.article_css),
            ("frontend/public/js/article.js", self.article_js),
            ("frontend/public/js/card.js", self.card_js),
            ("frontend/public/css/feed.css", self.feed_css),
            ("tests/test_issue85_unify_save_terminology.py", read_file("tests/test_issue85_unify_save_terminology.py")),
        ]

        emdash = "\u2014"
        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]|[\u2600-\u27bf]")
        cdn_pattern = re.compile(r"https?://(?:cdn|unpkg|cdnjs|jsdelivr)")

        for filename, content in files_to_check:
            self.assertNotIn(
                emdash,
                content,
                f"Literal em dash found in {filename}. Replace with hyphens or colons."
            )
            emojis = emoji_pattern.findall(content)
            self.assertEqual(
                len(emojis),
                0,
                f"Emojis found in {filename}: {emojis}"
            )
            # Only HTML/CSS/JS files need strict offline check
            if not filename.startswith("tests/"):
                cdn_matches = cdn_pattern.findall(content)
                self.assertEqual(
                    len(cdn_matches),
                    0,
                    f"External CDN url found in {filename}: {cdn_matches}"
                )


if __name__ == "__main__":
    unittest.main()
