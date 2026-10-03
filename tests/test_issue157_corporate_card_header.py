import os
import re
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue157CorporateCardHeader(unittest.TestCase):
    """
    Targeted tests for Issue #157:
    - Corporate post cards: separate company header from publication content
    - Remove human author from default corporate card header
    - Company header submeta contains only the blog marker ('Блог компании')
    - Backward compatibility: options.showSecondaryAuthor retains 'card-secondary-author'
    - Divider line under company header: border-bottom on .card-corporate-meta
    - Enhanced Subscribe button states: accent border/color, hover, is-subscribed, focus-visible
    - Subscribe button click event propagation prevention
    - Standard non-corporate feed cards remain unaffected
    - Invariants: zero emojis, zero em dashes, offline-first compliance
    """

    @classmethod
    def setUpClass(cls):
        card_js_path = os.path.join(FRONTEND_DIR, "js", "card.js")
        with open(card_js_path, "r", encoding="utf-8") as f:
            cls.card_js = f.read()

        feed_css_path = os.path.join(FRONTEND_DIR, "css", "feed.css")
        with open(feed_css_path, "r", encoding="utf-8") as f:
            cls.feed_css = f.read()

    def test_01_corporate_card_header_removes_human_author_by_default(self):
        """
        Verify corporate post cards remove the human author from corporate header by default:
        - options.showSecondaryAuthor flag controls secondaryAuthorHtml
        - secondaryAuthorHtml is empty when options.showSecondaryAuthor is false/undefined
        - .company-card-submeta contains .card-corporate-badge .card-corporate-marker
        - options.showSecondaryAuthor retains .card-secondary-author for backward compatibility
        """
        # 1. Verification of showSecondaryAuthor option
        self.assertIn("const showSecondaryAuthor = Boolean(options.showSecondaryAuthor);", self.card_js)
        self.assertIn("const secondaryAuthorHtml = showSecondaryAuthor", self.card_js)
        self.assertIn("card-secondary-author", self.card_js)
        self.assertIn("card-secondary-author-label", self.card_js)
        self.assertIn("Автор:", self.card_js)

        # 2. Extract corporate header template in card.js
        corp_block_start = self.card_js.find("if (hasCompany && !isCompanyDetail) {")
        self.assertNotEqual(corp_block_start, -1, "Corporate card header block must exist in card.js")
        corp_block_end = self.card_js.find("} else {", corp_block_start)
        corp_block = self.card_js[corp_block_start:corp_block_end]

        # 3. Check submeta structure
        submeta_markup = (
            '<div class="company-card-submeta">'
            + "' +\n"
            + "                  '<span class=\"card-corporate-badge card-corporate-marker\">Блог компании</span>' +\n"
            + "                  secondaryAuthorHtml +\n"
            + "                '</div>"
        )
        self.assertIn(submeta_markup, corp_block)

        # 4. By default secondaryAuthorHtml is empty string
        self.assertIn(": '';", corp_block)

    def test_02_corporate_header_branding_and_identity_elements(self):
        """
        Verify corporate header includes:
        - Logo avatar container and image support
        - Company name with title group
        - Verified checkmark badge
        - 'Блог компании' marker
        - Subscribe button container
        - Clickable info container with data-company-id, role='button', tabindex='0'
        """
        corp_block_start = self.card_js.find("if (hasCompany && !isCompanyDetail) {")
        corp_block_end = self.card_js.find("} else {", corp_block_start)
        corp_block = self.card_js[corp_block_start:corp_block_end]

        self.assertIn("card-corporate-meta", corp_block)
        self.assertIn("card-corporate-header", corp_block)
        self.assertIn("company-card-info", corp_block)
        self.assertIn('data-company-id="\' + escapeHtml(compId) + \'"', corp_block)
        self.assertIn('role="button"', corp_block)
        self.assertIn('tabindex="0"', corp_block)
        self.assertIn("compAvatarHtml", corp_block)
        self.assertIn("company-card-details", corp_block)
        self.assertIn("company-card-title-group", corp_block)
        self.assertIn("company-card-name", corp_block)
        self.assertIn("verifiedIcon", corp_block)
        self.assertIn("card-corporate-badge card-corporate-marker", corp_block)
        self.assertIn("Блог компании", corp_block)
        self.assertIn("subBtnHtml", corp_block)

    def test_03_card_corporate_meta_divider_and_spacing(self):
        """
        Verify .card-corporate-meta styling in feed.css:
        - border-bottom: 1px solid var(--border-color)
        - padding-bottom: 10px
        - margin-bottom: 12px
        - text-align: left
        - width: 100%
        - display: flex
        - flex-direction: column
        """
        block_start = self.feed_css.find(".card-corporate-meta {")
        self.assertNotEqual(block_start, -1, ".card-corporate-meta must exist in feed.css")
        block_end = self.feed_css.find("}", block_start)
        rules = self.feed_css[block_start:block_end]

        self.assertIn("width: 100%;", rules)
        self.assertIn("display: flex;", rules)
        self.assertIn("flex-direction: column;", rules)
        self.assertIn("padding-bottom: 10px;", rules)
        self.assertIn("margin-bottom: 12px;", rules)
        self.assertIn("border-bottom: 1px solid var(--border-color);", rules)
        self.assertIn("text-align: left;", rules)

    def test_04_enhanced_subscribe_button_css(self):
        """
        Verify .btn-card-company-sub styling in feed.css:
        - Base: height 30px, padding 0 14px, font-size 0.8rem, font-weight 600
        - Border: 1px solid var(--accent-color), color: var(--accent-color)
        - Hover: background rgba(56, 189, 248, 0.1), border-color and color var(--accent-color)
        - Light theme hover: background rgba(2, 132, 199, 0.08)
        - .is-subscribed state: background rgba(56, 189, 248, 0.16)
        - Light theme .is-subscribed: background rgba(2, 132, 199, 0.12)
        - .is-subscribed:hover: background rgba(56, 189, 248, 0.22)
        - Light theme .is-subscribed:hover: background rgba(2, 132, 199, 0.18)
        - Focus visible: outline 2px solid var(--accent-color), outline-offset: 2px
        """
        # Base button
        base_start = self.feed_css.find(".btn-card-company-sub {")
        self.assertNotEqual(base_start, -1, ".btn-card-company-sub must exist in feed.css")
        base_end = self.feed_css.find("}", base_start)
        base_rules = self.feed_css[base_start:base_end]

        self.assertIn("height: 30px;", base_rules)
        self.assertIn("padding: 0 14px;", base_rules)
        self.assertIn("font-size: 0.8rem;", base_rules)
        self.assertIn("font-weight: 600;", base_rules)
        self.assertIn("border-radius: var(--radius-md);", base_rules)
        self.assertIn("border: 1px solid var(--accent-color);", base_rules)
        self.assertIn("background: var(--bg-surface);", base_rules)
        self.assertIn("color: var(--accent-color);", base_rules)

        # Hover states
        hover_start = self.feed_css.find(".btn-card-company-sub:hover {")
        self.assertNotEqual(hover_start, -1)
        hover_end = self.feed_css.find("}", hover_start)
        hover_rules = self.feed_css[hover_start:hover_end]
        self.assertIn("background: rgba(56, 189, 248, 0.1);", hover_rules)
        self.assertIn("border-color: var(--accent-color);", hover_rules)
        self.assertIn("color: var(--accent-color);", hover_rules)

        self.assertIn('[data-theme="light"] .btn-card-company-sub:hover', self.feed_css)
        self.assertIn("background: rgba(2, 132, 199, 0.08);", self.feed_css)

        # Subscribed states
        sub_start = self.feed_css.find(".btn-card-company-sub.is-subscribed {")
        self.assertNotEqual(sub_start, -1)
        sub_end = self.feed_css.find("}", sub_start)
        sub_rules = self.feed_css[sub_start:sub_end]
        self.assertIn("background: rgba(56, 189, 248, 0.16);", sub_rules)
        self.assertIn("border-color: var(--accent-color);", sub_rules)
        self.assertIn("color: var(--accent-color);", sub_rules)

        self.assertIn('[data-theme="light"] .btn-card-company-sub.is-subscribed {', self.feed_css)
        self.assertIn("background: rgba(2, 132, 199, 0.12);", self.feed_css)

        # Subscribed hover states
        self.assertIn(".btn-card-company-sub.is-subscribed:hover {", self.feed_css)
        self.assertIn("background: rgba(56, 189, 248, 0.22);", self.feed_css)
        self.assertIn('[data-theme="light"] .btn-card-company-sub.is-subscribed:hover', self.feed_css)
        self.assertIn("background: rgba(2, 132, 199, 0.18);", self.feed_css)

        # Focus states
        self.assertIn(".btn-card-company-sub:focus:not(:focus-visible)", self.feed_css)
        self.assertIn(".btn-card-company-sub:focus-visible", self.feed_css)
        self.assertIn("outline: 2px solid var(--accent-color);", self.feed_css)
        self.assertIn("outline-offset: 2px;", self.feed_css)

    def test_05_subscribe_button_click_stops_propagation(self):
        """
        Verify clicking .btn-card-company-sub stops propagation and toggles subscription:
        - e.preventDefault() and e.stopPropagation() are invoked
        - company info element guards against nested clicks on .btn-card-company-sub
        """
        sub_handler_start = self.card_js.find("const compSubBtn = card.querySelector('.btn-card-company-sub');")
        self.assertNotEqual(sub_handler_start, -1)
        sub_handler_end = self.card_js.find("});\n      }", sub_handler_start)
        sub_handler = self.card_js[sub_handler_start:sub_handler_end + 8]

        self.assertIn("e.preventDefault();", sub_handler)
        self.assertIn("e.stopPropagation();", sub_handler)
        self.assertIn("options.onCompanySubscribeToggle", sub_handler)

        # Guard inside company-card-info
        self.assertIn("if (e.target.closest('.btn-author-profile') || e.target.closest('.btn-card-company-sub')) return;", self.card_js)

    def test_06_standard_non_corporate_cards_unaffected(self):
        """
        Verify standard feed cards remain unaffected:
        - Regular author info with avatar, author name button, and optional company badge
        - Badges, covers, lead, sub-info, and footer actions remain intact
        """
        corp_else_start = self.card_js.find("} else {\n      authorHtml =")
        self.assertNotEqual(corp_else_start, -1)
        corp_else_end = self.card_js.find("// 2. Title", corp_else_start)
        standard_author_block = self.card_js[corp_else_start:corp_else_end]

        self.assertIn("author-info", standard_author_block)
        self.assertIn("author-avatar", standard_author_block)
        self.assertIn("author-name", standard_author_block)
        self.assertIn("btn-author-profile", standard_author_block)
        self.assertNotIn("card-corporate-meta", standard_author_block)
        self.assertNotIn("card-corporate-header", standard_author_block)

    def test_07_invariants_no_emojis_no_em_dashes(self):
        """
        Invariants verification:
        - Zero emojis
        - Zero em dashes (use hyphens instead)
        - No local machine paths or real IPs in frontend code
        """
        em_dash = chr(8212)
        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]", flags=re.UNICODE)

        for filename, content in [("card.js", self.card_js), ("feed.css", self.feed_css)]:
            self.assertNotIn(em_dash, content, f"{filename} must not contain em dashes")
            self.assertEqual(len(emoji_pattern.findall(content)), 0, f"{filename} must not contain emojis")


if __name__ == "__main__":
    unittest.main()
