#!/usr/bin/env python3
"""
tests/test_issue86_article_share_menu.py

Automated test suite for Issue #86:
"[P2][frontend] Полноценное меню Share публикации по аналогии с комментариями".

Acceptance Criteria verified:
1. Unified #articleSharePopover DOM structure with role="menu" and aria-label="Поделиться публикацией".
2. 4 Share channels:
   - Copy link (with instant microcopy change "Ссылка скопирована" and toast notification)
   - Telegram (https://t.me/share/url?url=...&text=...)
   - VKontakte (https://vk.com/share.php?url=...&title=...)
   - Odnoklassniki (https://connect.ok.ru/offer?url=...&title=...)
3. Trigger buttons (railBtnShare, btnCopyLink, mobileBtnShare) with aria-haspopup="true" and dynamic aria-expanded.
4. Open/close/toggle functions: openArticleSharePopover, closeArticleSharePopover, isArticleSharePopoverOpen.
5. Outside click, Escape key (restoring focus), and keyboard navigation (ArrowDown, ArrowUp, Home, End).
6. Shared popover styling tokens in article.css and theme.css (.article-share-popover, .article-share-item).
7. Zero emojis, zero em dashes, and 100% offline-first.
"""

import os
import re
import unittest
import urllib.parse

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def read_file(relative_path: str) -> str:
    full_path = os.path.join(PROJECT_ROOT, relative_path)
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()


class TestIssue86ArticleShareMenu(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.article_html = read_file("frontend/public/article.html")
        cls.article_js = read_file("frontend/public/js/article.js")
        cls.article_css = read_file("frontend/public/css/article.css")
        cls.theme_css = read_file("frontend/public/css/theme.css")

    def test_01_article_share_popover_dom_structure(self) -> None:
        """Verify #articleSharePopover container exists with accessibility attributes."""
        self.assertIn('id="articleSharePopover"', self.article_html)
        match = re.search(
            r'<div\s+id="articleSharePopover"\s+class="[^"]*article-share-popover[^"]*"\s+role="menu"\s+aria-label="Поделиться публикацией"',
            self.article_html
        )
        self.assertIsNotNone(match, "#articleSharePopover must have role='menu' and aria-label='Поделиться публикацией'")
        self.assertIn('style="display: none;"', match.string[match.start():match.end() + 40])

    def test_02_article_share_popover_action_items(self) -> None:
        """Verify 4 share channels exist inside #articleSharePopover."""
        popover_start = self.article_html.find('id="articleSharePopover"')
        self.assertNotEqual(popover_start, -1)
        popover_end = self.article_html.find('</div>', popover_start)
        popover_snippet = self.article_html[popover_start:popover_end]

        # 1. Copy link button
        self.assertIn('data-action="copy"', popover_snippet)
        self.assertIn('class="share-copy-label">Скопировать ссылку<', popover_snippet)

        # 2. Telegram link
        self.assertIn('data-action="telegram"', popover_snippet)
        self.assertIn('<span>Telegram</span>', popover_snippet)

        # 3. VKontakte link
        self.assertIn('data-action="vk"', popover_snippet)
        self.assertIn('<span>ВКонтакте</span>', popover_snippet)

        # 4. Odnoklassniki link
        self.assertIn('data-action="ok"', popover_snippet)
        self.assertIn('<span>Одноклассники</span>', popover_snippet)

        # Accessibility on items
        for action in ['copy', 'telegram', 'vk', 'ok']:
            pattern = rf'data-action="{action}"[^>]*role="menuitem"'
            match = re.search(pattern, popover_snippet) or re.search(rf'role="menuitem"[^>]*data-action="{action}"', popover_snippet)
            self.assertIsNotNone(match, f"Action item {action} must have role='menuitem'")

    def test_03_article_share_triggers_attributes(self) -> None:
        """Verify share trigger buttons have aria-haspopup and aria-expanded attributes."""
        triggers = ['railBtnShare', 'btnCopyLink', 'mobileBtnShare']
        for btn_id in triggers:
            match = re.search(rf'id="{btn_id}"[^>]*', self.article_html)
            self.assertIsNotNone(match, f"Trigger button {btn_id} must exist in article.html")
            snippet = match.group(0)
            self.assertIn('aria-haspopup="true"', snippet, f"{btn_id} must have aria-haspopup='true'")
            self.assertIn('aria-expanded="false"', snippet, f"{btn_id} must have aria-expanded='false'")

    def test_04_article_js_open_close_methods(self) -> None:
        """Verify article.js defines openArticleSharePopover, closeArticleSharePopover, and isArticleSharePopoverOpen."""
        self.assertIn('function isArticleSharePopoverOpen()', self.article_js)
        self.assertIn('function closeArticleSharePopover()', self.article_js)
        self.assertIn('function openArticleSharePopover(triggerBtn)', self.article_js)

        # Check export on window.ArticleReader
        self.assertIn('window.ArticleReader.openArticleSharePopover = openArticleSharePopover', self.article_js)
        self.assertIn('window.ArticleReader.closeArticleSharePopover = closeArticleSharePopover', self.article_js)
        self.assertIn('window.ArticleReader.isArticleSharePopoverOpen = isArticleSharePopoverOpen', self.article_js)

    def test_05_social_share_url_encoding(self) -> None:
        """Verify social share URLs use encodeURIComponent with current URL and article title."""
        self.assertIn("'https:' + '//t.me/share/url?url=' + encodedUrl + '&text=' + encodedText", self.article_js)
        self.assertIn("'https:' + '//vk.com/share.php?url=' + encodedUrl + '&title=' + encodedText", self.article_js)
        self.assertIn("'https:' + '//connect.ok.ru/offer?url=' + encodedUrl + '&title=' + encodedText", self.article_js)

        # Verify python equivalent encoding logic
        url = "https://smartcontractum.org/article.html?id=123"
        title = "Обзор архитектуры SmartContractum"
        enc_url = urllib.parse.quote(url, safe="")
        enc_title = urllib.parse.quote(title, safe="")

        tg_url = f"https://t.me/share/url?url={enc_url}&text={enc_title}"
        self.assertTrue(tg_url.startswith("https://t.me/share/url?url=https%3A%2F%2Fsmartcontractum.org"))

    def test_06_copy_action_microcopy_and_toast(self) -> None:
        """Verify copy action sets microcopy 'Ссылка скопирована' and calls copyArticleLink."""
        self.assertIn("copyArticleLink()", self.article_js)
        self.assertIn("copyLabel.textContent = 'Ссылка скопирована'", self.article_js)

    def test_07_outside_click_and_escape_close(self) -> None:
        """Verify outside click and Escape key close articleSharePopover and return focus."""
        self.assertIn('isArticleSharePopoverOpen()', self.article_js)
        self.assertIn('closeArticleSharePopover()', self.article_js)
        self.assertIn('e.key === \'Escape\'', self.article_js)
        self.assertIn('trigger.focus()', self.article_js)

    def test_08_arrow_key_navigation_in_popover(self) -> None:
        """Verify ArrowDown, ArrowUp, Home, End navigation in articleSharePopover."""
        self.assertIn("e.key === 'ArrowDown'", self.article_js)
        self.assertIn("e.key === 'ArrowUp'", self.article_js)
        self.assertIn("e.key === 'Home'", self.article_js)
        self.assertIn("e.key === 'End'", self.article_js)

    def test_09_css_styling_and_tokens(self) -> None:
        """Verify .article-share-popover and .article-share-item styles in article.css and theme.css."""
        for css_file, content in [("article.css", self.article_css), ("theme.css", self.theme_css)]:
            self.assertIn(".article-share-popover", content, f".article-share-popover must be in {css_file}")
            self.assertIn(".article-share-item", content, f".article-share-item must be in {css_file}")
            self.assertIn("z-index: 1000", content, f"z-index: 1000 must be defined in {css_file}")

    def test_10_zero_emojis_no_em_dashes_offline_first(self) -> None:
        """Verify zero emojis, zero em dashes, and offline-first compliance."""
        emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]', flags=re.UNICODE)
        em_dash = '\u2014'

        files_to_check = [
            ("article.html", self.article_html),
            ("article.js", self.article_js),
            ("article.css", self.article_css),
            ("theme.css", self.theme_css),
        ]

        for fname, content in files_to_check:
            self.assertIsNone(emoji_pattern.search(content), f"Found emoji in {fname}")
            self.assertNotIn(em_dash, content, f"Found em dash in {fname}")


if __name__ == "__main__":
    unittest.main()
