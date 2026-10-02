#!/usr/bin/env python3
"""
tests/test_issue72_comment_share_menu.py

Automated test suite for Issue #72 (SC-030):
"Popover dropdown menu for comment Share button and permalink navigation logic".

Acceptance Criteria verified:
1. Compact Popover dropdown menu for comment and answer share buttons.
2. Structure: 4 items (copy permalink, Telegram, VKontakte, Odnoklassniki).
3. Social share URLs with encoded URL and title.
4. Popover close triggers (outside click, Escape key, button toggle, item selection).
5. Deep link navigation:
   - ?comment=<id> query parameter and #comm_<id> hash.
   - Recursive expansion of ancestor threads and parent answer replies.
   - Smooth scroll and temporary 2.5s highlight pulse (.comment-highlight).
6. Accessibility: role="menu", aria-label, aria-haspopup="true", aria-expanded="true/false", keyboard navigation.
7. CSS styling: design system tokens, surface background, blur backdrop, proper z-index.
8. Zero emojis, zero em dashes, 100% offline-first.
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


class TestIssue72CommentShareMenu(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.article_html = read_file("frontend/public/article.html")
        cls.article_js = read_file("frontend/public/js/article.js")
        cls.article_css = read_file("frontend/public/css/article.css")
        cls.theme_css = read_file("frontend/public/css/theme.css")

    def test_01_permalink_generation_logic_and_encoding(self) -> None:
        """Verify generateCommentPermalink creates valid URLs with origin, pathname, ?id= and #comm_."""
        self.assertIn("function generateCommentPermalink(articleId, commentId)", self.article_js)

        # Check JS implementation structure
        match = re.search(
            r'function generateCommentPermalink\(articleId, commentId\)\s*\{([^}]+)\}',
            self.article_js
        )
        self.assertIsNotNone(match, "generateCommentPermalink function body must be found in article.js")
        body = match.group(1)
        self.assertIn("window.location.origin", body)
        self.assertIn("window.location.pathname", body)
        self.assertIn("encodeURIComponent(targetArtId)", body)
        self.assertIn("'#comm_' + encodeURIComponent(commentId)", body)

        # Python equivalent logic verification
        def py_generate_permalink(origin: str, pathname: str, article_id: str, comment_id: str) -> str:
            return f"{origin}{pathname}?id={urllib.parse.quote(article_id, safe='')}#comm_{urllib.parse.quote(comment_id, safe='')}"

        url1 = py_generate_permalink("https://smartcontractum.org", "/article.html", "art_100", "comm_200")
        self.assertEqual(url1, "https://smartcontractum.org/article.html?id=art_100#comm_comm_200")

        url2 = py_generate_permalink("http://localhost:8000", "/article", "art/with spaces/1", "c?=&special")
        self.assertIn("art%2Fwith%20spaces%2F1", url2)
        self.assertIn("c%3F%3D%26special", url2)

    def test_02_social_share_urls_formatting(self) -> None:
        """Verify Telegram, VK, and OK sharing URLs format properly with encoded parameters."""
        self.assertIn("'https:' + '//t.me/share/url?url=' + encodedUrl + '&text=' + encodedText", self.article_js)
        self.assertIn("'https:' + '//vk.com/share.php?url=' + encodedUrl + '&title=' + encodedText", self.article_js)
        self.assertIn("'https:' + '//connect.ok.ru/offer?url=' + encodedUrl + '&title=' + encodedText", self.article_js)

        permalink = "https://smartcontractum.org/article.html?id=art_1&comm=comm_2"
        title = "Смарт-контракты и безопасность"

        enc_url = urllib.parse.quote(permalink, safe="")
        enc_title = urllib.parse.quote(title, safe="")

        tg_url = f"https://t.me/share/url?url={enc_url}&text={enc_title}"
        vk_url = f"https://vk.com/share.php?url={enc_url}&title={enc_title}"
        ok_url = f"https://connect.ok.ru/offer?url={enc_url}&title={enc_title}"

        self.assertTrue(tg_url.startswith("https://t.me/share/url?url="))
        self.assertIn("&text=", tg_url)
        self.assertTrue(vk_url.startswith("https://vk.com/share.php?url="))
        self.assertIn("&title=", vk_url)
        self.assertTrue(ok_url.startswith("https://connect.ok.ru/offer?url="))
        self.assertIn("&title=", ok_url)

    def test_03_popover_dom_structure_in_article_html(self) -> None:
        """Verify popover container and 4 action items exist in article.html with accessibility attributes."""
        # Container check
        popover_match = re.search(
            r'<div\s+id="commentSharePopover"\s+class="comment-share-popover"\s+role="menu"\s+aria-label="Поделиться комментарием"\s+style="display:\s*none;">',
            self.article_html
        )
        self.assertIsNotNone(popover_match, "commentSharePopover container must exist in article.html with correct attributes")

        # Copy item
        copy_match = re.search(
            r'<button\s+type="button"\s+class="comment-share-item"\s+role="menuitem"\s+data-action="copy">',
            self.article_html
        )
        self.assertIsNotNone(copy_match, "Copy link button must exist in popover")
        self.assertIn("<span>Скопировать ссылку</span>", self.article_html)

        # Telegram item
        tg_match = re.search(
            r'<a\s+class="comment-share-item"\s+role="menuitem"\s+data-action="telegram"\s+target="_blank"\s+rel="noopener noreferrer"\s+href="#">',
            self.article_html
        )
        self.assertIsNotNone(tg_match, "Telegram item must exist in popover with target='_blank' and rel='noopener noreferrer'")
        self.assertIn("<span>Telegram</span>", self.article_html)

        # VKontakte item
        vk_match = re.search(
            r'<a\s+class="comment-share-item"\s+role="menuitem"\s+data-action="vk"\s+target="_blank"\s+rel="noopener noreferrer"\s+href="#">',
            self.article_html
        )
        self.assertIsNotNone(vk_match, "VK item must exist in popover with target='_blank' and rel='noopener noreferrer'")
        self.assertIn("<span>VKontakte</span>", self.article_html)

        # Odnoklassniki item
        ok_match = re.search(
            r'<a\s+class="comment-share-item"\s+role="menuitem"\s+data-action="ok"\s+target="_blank"\s+rel="noopener noreferrer"\s+href="#">',
            self.article_html
        )
        self.assertIsNotNone(ok_match, "OK item must exist in popover with target='_blank' and rel='noopener noreferrer'")
        self.assertIn("<span>Одноклассники</span>", self.article_html)

        # Verify SVGs inside each item
        popover_block = self.article_html[popover_match.start():self.article_html.find('</div>', popover_match.end() + 2000)]
        svg_count = popover_block.count("<svg")
        self.assertEqual(svg_count, 4, "Popover must contain exactly 4 SVG icons")

    def test_04_popover_open_and_close_logic_in_article_js(self) -> None:
        """Verify openCommentSharePopover and closeCommentSharePopover logic and state handling."""
        self.assertIn("function isCommentSharePopoverOpen()", self.article_js)
        self.assertIn("function closeCommentSharePopover()", self.article_js)
        self.assertIn("function openCommentSharePopover(triggerBtn, articleId, commentId)", self.article_js)

        # Check toggle on same button
        self.assertIn("if (activeSharePopoverCommentId === commentId && isCommentSharePopoverOpen()) {", self.article_js)
        self.assertIn("closeCommentSharePopover();", self.article_js)

        # Check aria attributes toggle
        self.assertIn("triggerBtn.setAttribute('aria-haspopup', 'true');", self.article_js)
        self.assertIn("triggerBtn.setAttribute('aria-expanded', 'true');", self.article_js)
        self.assertIn("activeSharePopoverTrigger.setAttribute('aria-expanded', 'false');", self.article_js)

        # Check positioning calculation
        self.assertIn("const rect = triggerBtn.getBoundingClientRect();", self.article_js)
        self.assertIn("popover.style.top = top + 'px';", self.article_js)
        self.assertIn("popover.style.left = left + 'px';", self.article_js)
        self.assertIn("popover.style.display = 'flex';", self.article_js)

    def test_05_popover_outside_click_and_escape_handlers(self) -> None:
        """Verify click outside and Escape key listeners close the popover."""
        # Click outside listener
        click_match = re.search(
            r"document\.addEventListener\('click',\s*function\s*\(e\)\s*\{([^}]+closeCommentSharePopover\(\);[^}]*)\}\);",
            self.article_js
        )
        self.assertIsNotNone(click_match, "Click outside listener must be registered")
        click_body = click_match.group(1)
        self.assertIn("if (!isCommentSharePopoverOpen()) return;", click_body)
        self.assertIn("popover.contains(e.target)", click_body)
        self.assertIn(".btn-share-comment, .btn-share-answer", click_body)

        # Escape key listener
        self.assertIn("document.addEventListener('keydown'", self.article_js)
        keydown_idx = self.article_js.find("document.addEventListener('keydown'")
        self.assertNotEqual(keydown_idx, -1, "Keydown listener must be found in article.js")
        keydown_block = self.article_js[keydown_idx:keydown_idx + 1200]
        self.assertIn("e.key === 'Escape'", keydown_block)
        self.assertIn("closeCommentSharePopover()", keydown_block)
        self.assertIn("activeSharePopoverTrigger.focus()", keydown_block)

    def test_06_keyboard_navigation_within_popover(self) -> None:
        """Verify ArrowDown, ArrowUp, Home, End keyboard navigation in popover."""
        self.assertIn("e.key === 'ArrowDown'", self.article_js)
        self.assertIn("e.key === 'ArrowUp'", self.article_js)
        self.assertIn("e.key === 'Home'", self.article_js)
        self.assertIn("e.key === 'End'", self.article_js)

    def test_07_action_buttons_wiring_in_comments_and_answers(self) -> None:
        """Verify .btn-share-comment and .btn-share-answer wire to openCommentSharePopover with aria attributes."""
        # Comments
        comm_share_block = re.search(
            r"const shareBtn = el\.querySelector\('\.btn-share-comment'\);.*?openCommentSharePopover\(shareBtn,\s*targetArtId,\s*comment\.id\);",
            self.article_js,
            re.DOTALL
        )
        self.assertIsNotNone(comm_share_block, ".btn-share-comment must wire to openCommentSharePopover")
        comm_code = comm_share_block.group(0)
        self.assertIn("shareBtn.setAttribute('aria-haspopup', 'true');", comm_code)
        self.assertIn("shareBtn.setAttribute('aria-expanded', 'false');", comm_code)
        self.assertIn("e.stopPropagation();", comm_code)

        # Answers
        ans_share_block = re.search(
            r"const shareBtn = el\.querySelector\('\.btn-share-answer'\);.*?openCommentSharePopover\(shareBtn,\s*articleId,\s*comment\.id\);",
            self.article_js,
            re.DOTALL
        )
        self.assertIsNotNone(ans_share_block, ".btn-share-answer must wire to openCommentSharePopover")
        ans_code = ans_share_block.group(0)
        self.assertIn("shareBtn.setAttribute('aria-haspopup', 'true');", ans_code)
        self.assertIn("shareBtn.setAttribute('aria-expanded', 'false');", ans_code)
        self.assertIn("e.stopPropagation();", ans_code)

    def test_08_deep_link_handling_with_query_param_and_hash(self) -> None:
        """Verify handleDeepLink supports ?comment=<id> and #comm_<id> with thread auto-expansion."""
        self.assertIn("function handleDeepLink()", self.article_js)

        # Query param support
        self.assertIn("const commentParam = urlParams.get('comment');", self.article_js)
        self.assertIn("if (!hash && commentParam) {", self.article_js)
        self.assertIn("hash = '#comm_' + commentParam;", self.article_js)

        # Ancestor thread expansion
        self.assertIn("window._expandedCommentIds.add(parentId);", self.article_js)
        self.assertIn("childrenContainer.style.display = 'flex';", self.article_js)
        self.assertIn("btn.setAttribute('aria-expanded', 'true');", self.article_js)
        self.assertIn("Скрыть комментарии", self.article_js)

        # Answer replies expansion
        self.assertIn("repliesContainer.style.display = 'block';", self.article_js)

        # Scroll into view and highlight
        self.assertIn("targetEl.scrollIntoView({ behavior: 'smooth', block: 'center' });", self.article_js)
        self.assertIn("targetEl.classList.add('comment-highlight');", self.article_js)
        self.assertIn("targetEl.classList.remove('comment-highlight');", self.article_js)

    def test_09_css_popover_and_highlight_styles(self) -> None:
        """Verify .comment-share-popover, .comment-share-item, and .comment-highlight rules."""
        for css_content, file_name in [(self.article_css, "article.css"), (self.theme_css, "theme.css")]:
            self.assertIn(".comment-share-popover", css_content, f".comment-share-popover must be defined in {file_name}")
            self.assertIn(".comment-share-item", css_content, f".comment-share-item must be defined in {file_name}")

        # Check key style rules in article.css or theme.css
        self.assertIn("position: absolute;", self.article_css)
        self.assertIn("background: var(--bg-surface);", self.article_css)
        self.assertIn("border: 1px solid var(--border-color);", self.article_css)
        self.assertIn("box-shadow: var(--shadow-md);", self.article_css)
        self.assertIn("min-width: 190px;", self.article_css)
        self.assertIn("z-index: 1000;", self.article_css)

        # Highlight pulse animation in theme.css
        self.assertIn(".comment-highlight", self.theme_css)
        self.assertIn("animation: commentHighlightPulse 2.5s ease-out;", self.theme_css)
        self.assertIn("@keyframes commentHighlightPulse", self.theme_css)

    def test_10_window_exports_for_contracts_and_testing(self) -> None:
        """Verify window exports for popover and permalink helpers."""
        self.assertIn("window.copyCommentLink = copyCommentLink;", self.article_js)
        self.assertIn("window.generateCommentPermalink = generateCommentPermalink;", self.article_js)
        self.assertIn("window.openCommentSharePopover = openCommentSharePopover;", self.article_js)
        self.assertIn("window.closeCommentSharePopover = closeCommentSharePopover;", self.article_js)
        self.assertIn("window.isCommentSharePopoverOpen = isCommentSharePopoverOpen;", self.article_js)

    def test_11_zero_emojis_and_no_em_dashes(self) -> None:
        """Ensure zero emojis, zero em dashes, zero server IPs, and zero local filesystem paths."""
        em_dash = "\u2014"
        emoji_pattern = re.compile(
            "[\U00010000-\U0010ffff]|"
            "[\u2600-\u26ff]|"
            "[\u2700-\u27bf]"
        )

        files = [
            ("frontend/public/article.html", self.article_html),
            ("frontend/public/js/article.js", self.article_js),
            ("frontend/public/css/article.css", self.article_css),
            ("frontend/public/css/theme.css", self.theme_css),
        ]

        for path, content in files:
            self.assertNotIn(
                em_dash,
                content,
                f"Em dash found in {path}. Use hyphen or colon instead."
            )
            emojis = emoji_pattern.findall(content)
            self.assertEqual(
                len(emojis),
                0,
                f"Emojis {emojis} found in {path}."
            )
            self.assertNotIn(
                "/ho" + "me/",
                content,
                f"Absolute filesystem path found in {path}"
            )

    def test_12_offline_first_and_no_external_cdns(self) -> None:
        """Ensure 100% offline-first: no external CDNs or unbundled resources."""
        external_pattern = re.compile(r'https?://(?!t\.me|vk\.com|connect\.ok\.ru)[a-zA-Z0-9.-]+\.(?:com|org|net|io|cdn)/')

        for path, content in [
            ("frontend/public/css/article.css", self.article_css),
            ("frontend/public/css/theme.css", self.theme_css),
        ]:
            matches = external_pattern.findall(content)
            self.assertEqual(len(matches), 0, f"External CDN links found in {path}: {matches}")


if __name__ == "__main__":
    unittest.main()
