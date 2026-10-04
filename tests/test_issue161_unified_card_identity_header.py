import os
import re
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue161UnifiedCardIdentityHeader(unittest.TestCase):
    """
    Targeted test suite for Issue #161:
    [P1][frontend] Feed Cards: unified identity-header for authors, companies, and questions.
    """

    @classmethod
    def setUpClass(cls):
        card_js_path = os.path.join(FRONTEND_DIR, "js", "card.js")
        with open(card_js_path, "r", encoding="utf-8") as f:
            cls.card_js = f.read()

        feed_css_path = os.path.join(FRONTEND_DIR, "css", "feed.css")
        with open(feed_css_path, "r", encoding="utf-8") as f:
            cls.feed_css = f.read()

        editor_css_path = os.path.join(FRONTEND_DIR, "css", "editor.css")
        with open(editor_css_path, "r", encoding="utf-8") as f:
            cls.editor_css = f.read()

    def test_01_regular_author_card_has_identity_header_and_divider(self):
        """
        Verify regular author publication cards have an identity header and divider:
        - .card-meta container exists with .author-info, .author-avatar, and .author-details
        - .card-meta CSS defines the bottom divider line and spacing
        """
        # card.js markup structure
        self.assertIn('<div class="card-meta">', self.card_js)
        self.assertIn('<div class="author-info">', self.card_js)
        self.assertIn('class="author-avatar"', self.card_js)
        self.assertIn('<div class="author-details">', self.card_js)

        # feed.css divider styling
        card_meta_start = self.feed_css.find(".card-meta {")
        self.assertNotEqual(card_meta_start, -1, ".card-meta rule must exist in feed.css")
        card_meta_end = self.feed_css.find("}", card_meta_start)
        rules = self.feed_css[card_meta_start:card_meta_end]

        self.assertIn("border-bottom: 1px solid var(--border-color);", rules)
        self.assertIn("padding-bottom: 10px;", rules)
        self.assertIn("margin-bottom: 12px;", rules)
        self.assertIn("width: 100%;", rules)
        self.assertIn("text-align: left;", rules)

    def test_02_corporate_publication_card_has_identity_header_and_divider(self):
        """
        Verify corporate publication cards have an identity header and divider:
        - .card-meta.card-corporate-meta container with .card-corporate-header
        - .company-card-info with logo/avatar, name, and verified badge
        - .card-corporate-meta shares the identical divider line and spacing
        """
        # card.js corporate markup
        self.assertIn('<div class="card-meta card-corporate-meta">', self.card_js)
        self.assertIn('<div class="card-corporate-header">', self.card_js)
        self.assertIn('class="company-card-info"', self.card_js)
        self.assertIn("compAvatarHtml", self.card_js)
        self.assertIn('class="company-card-name"', self.card_js)
        self.assertIn('class="card-corporate-badge card-corporate-marker">Блог компании</span>', self.card_js)

        # feed.css divider styling
        corp_meta_start = self.feed_css.find(".card-corporate-meta {")
        self.assertNotEqual(corp_meta_start, -1, ".card-corporate-meta rule must exist in feed.css")
        corp_meta_end = self.feed_css.find("}", corp_meta_start)
        corp_rules = self.feed_css[corp_meta_start:corp_meta_end]

        self.assertIn("border-bottom: 1px solid var(--border-color);", corp_rules)
        self.assertIn("padding-bottom: 10px;", corp_rules)
        self.assertIn("margin-bottom: 12px;", corp_rules)
        self.assertIn("width: 100%;", corp_rules)
        self.assertIn("text-align: left;", corp_rules)

    def test_03_question_card_has_identity_header_and_divider(self):
        """
        Verify question cards share the same identity header and divider:
        - Question cards render through the .card-meta header block
        - Distinct question badge and title appear cleanly below the divider line
        """
        # Question cards reuse standard author header unless company-based
        self.assertIn("const isQuestion = (item.materialType === 'question' || item.type === 'question');", self.card_js)
        self.assertIn("question-badge", self.card_js)
        self.assertIn("question-card-title", self.card_js)

        # The header divider comes before title and badges in inner layout
        idx_author_header = self.card_js.find("authorHtml +")
        idx_title = self.card_js.find("titleHtml +")
        idx_badges = self.card_js.find("badgesContainerHtml +")
        self.assertTrue(
            idx_author_header < idx_title < idx_badges,
            "Identity header with divider must precede title and badges row"
        )

    def test_04_divider_style_is_identical_across_all_card_types(self):
        """
        Verify that divider declarations in .card-meta and .card-corporate-meta are 100% identical.
        """
        card_meta_start = self.feed_css.find(".card-meta {")
        card_meta_end = self.feed_css.find("}", card_meta_start)
        card_meta_block = self.feed_css[card_meta_start:card_meta_end]

        corp_meta_start = self.feed_css.find(".card-corporate-meta {")
        corp_meta_end = self.feed_css.find("}", corp_meta_start)
        corp_meta_block = self.feed_css[corp_meta_start:corp_meta_end]

        for prop in [
            "border-bottom: 1px solid var(--border-color);",
            "padding-bottom: 10px;",
            "margin-bottom: 12px;",
            "width: 100%;",
            "text-align: left;"
        ]:
            self.assertIn(prop, card_meta_block, f"Property '{prop}' missing in .card-meta")
            self.assertIn(prop, corp_meta_block, f"Property '{prop}' missing in .card-corporate-meta")

    def test_05_feed_avatars_use_square_geometry_with_radius_md(self):
        """
        Verify avatar geometry unification:
        - .author-avatar uses border-radius: var(--radius-md) (not 50%)
        - .company-card-logo uses border-radius: var(--radius-md) (not 50%)
        - Avatar image tags use border-radius: var(--radius-md)
        """
        # .author-avatar in feed.css
        author_av_start = self.feed_css.find(".author-avatar {")
        self.assertNotEqual(author_av_start, -1)
        author_av_end = self.feed_css.find("}", author_av_start)
        author_av_rules = self.feed_css[author_av_start:author_av_end]

        self.assertIn("border-radius: var(--radius-md);", author_av_rules)
        self.assertNotIn("border-radius: 50%;", author_av_rules)

        # .company-card-logo in feed.css
        comp_av_start = self.feed_css.find(".company-card-logo {")
        self.assertNotEqual(comp_av_start, -1)
        comp_av_end = self.feed_css.find("}", comp_av_start)
        comp_av_rules = self.feed_css[comp_av_start:comp_av_end]

        self.assertIn("border-radius: var(--radius-md);", comp_av_rules)
        self.assertNotIn("border-radius: 50%;", comp_av_rules)

        # Image rules for both author and company avatars
        self.assertIn(".author-avatar img", self.feed_css)
        self.assertIn(".company-card-logo-img", self.feed_css)
        self.assertIn("object-fit: cover;", self.feed_css)

    def test_06_avatar_size_is_34px(self):
        """
        Verify both author and company avatar dimensions are 34px by 34px:
        - .author-avatar: width 34px, height 34px
        - .company-card-logo: width 34px, height 34px
        """
        author_av_start = self.feed_css.find(".author-avatar {")
        author_av_end = self.feed_css.find("}", author_av_start)
        author_av_rules = self.feed_css[author_av_start:author_av_end]

        self.assertIn("width: 34px;", author_av_rules)
        self.assertIn("height: 34px;", author_av_rules)

        comp_av_start = self.feed_css.find(".company-card-logo {")
        comp_av_end = self.feed_css.find("}", comp_av_start)
        comp_av_rules = self.feed_css[comp_av_start:comp_av_end]

        self.assertIn("width: 34px;", comp_av_rules)
        self.assertIn("height: 34px;", comp_av_rules)

    def test_07_corporate_publication_card_does_not_display_human_author(self):
        """
        Verify corporate publication cards do not show a human author:
        - secondaryAuthorHtml is controlled by options.showSecondaryAuthor
        - By default, secondaryAuthorHtml evaluates to empty string
        - Only company branding and the 'Блог компании' marker appear
        """
        corp_block_start = self.card_js.find("if (hasCompany && !isCompanyDetail) {")
        self.assertNotEqual(corp_block_start, -1)
        corp_block_end = self.card_js.find("} else {", corp_block_start)
        corp_block = self.card_js[corp_block_start:corp_block_end]

        self.assertIn("const showSecondaryAuthor = Boolean(options.showSecondaryAuthor);", corp_block)
        self.assertIn("secondaryAuthorHtml", corp_block)
        self.assertIn(": '';", corp_block)
        self.assertIn("Блог компании", corp_block)

    def test_08_corporate_publication_card_does_not_display_subscribe_button_by_default(self):
        """
        Verify corporate publication cards do not display Subscribe button by default:
        - options.showCompanySubscribe controls subBtnHtml
        - By default, subBtnHtml is empty string
        - When options.showCompanySubscribe is true, renders button
        """
        corp_block_start = self.card_js.find("if (hasCompany && !isCompanyDetail) {")
        corp_block_end = self.card_js.find("} else {", corp_block_start)
        corp_block = self.card_js[corp_block_start:corp_block_end]

        self.assertIn("const showCompanySubscribe = Boolean(options.showCompanySubscribe);", corp_block)
        self.assertIn("const subBtnHtml = showCompanySubscribe", corp_block)
        self.assertIn("btn-card-company-sub", corp_block)
        self.assertIn(": '';", corp_block)

    def test_09_company_name_and_logo_navigates_to_company_blog(self):
        """
        Verify company name and logo are interactive and navigate to company blog:
        - .company-card-info has data-company-id, role='button', tabindex='0'
        - Click and keyboard event listeners call options.onCompanyClick or openCompanyDetail
        """
        self.assertIn('class="company-card-info"', self.card_js)
        self.assertIn('role="button"', self.card_js)
        self.assertIn('tabindex="0"', self.card_js)
        self.assertIn("options.onCompanyClick(cid)", self.card_js)
        self.assertIn("window.openCompanyDetail(cid)", self.card_js)

    def test_10_author_name_navigates_to_author_profile(self):
        """
        Verify author name remains interactive and navigates to author profile:
        - Rendered with .btn-author-profile, data-author-id, data-user-id, data-user-name
        - CSS includes pointer cursor, hover effects, and focus-visible states
        """
        self.assertIn('class="author-name btn-author-profile"', self.card_js)
        self.assertIn('data-author-id="\' + escapeHtml(authorId) + \'"', self.card_js)

        # Profile button styling in feed.css
        self.assertIn(".btn-author-profile", self.feed_css)
        self.assertIn(".btn-author-profile:hover", self.feed_css)
        self.assertIn(".btn-author-profile:focus-visible", self.feed_css)

    def test_11_content_block_after_divider_remains_unchanged(self):
        """
        Verify content block hierarchy after divider remains completely intact:
        - authorHtml (header + divider) -> titleHtml -> badgesContainerHtml ->
          coverHtml -> leadHtml -> snippetHtml -> subInfoHtml -> footerHtml
        """
        expected_order = [
            "authorHtml +",
            "titleHtml +",
            "badgesContainerHtml +",
            "coverHtml +",
            "leadHtml +",
            "snippetHtml +",
            "subInfoHtml +",
            "footerHtml;"
        ]
        last_idx = -1
        for item in expected_order:
            idx = self.card_js.find(item)
            self.assertNotEqual(idx, -1, f"Expected item {item} not found in card.js return statement")
            self.assertGreater(idx, last_idx, f"Item {item} violated expected layout sequence")
            last_idx = idx

    def test_12_invariants_no_emojis_no_em_dashes_offline_first(self):
        """
        Verify project invariants:
        - Zero emojis across all modified files and this test
        - Zero em dashes (unicode 8212) across all modified files and this test
        - No local machine paths (/home/, /tmp/) in production code
        - No hardcoded server IP addresses
        - Offline-first compliance (no external CDN references)
        """
        em_dash = chr(8212)
        emoji_pattern = re.compile(
            r"[\U00010000-\U0010ffff]|[\u2600-\u27ff]|[\u2300-\u23ff]|[\u2b50-\u2b55]|[\u203c-\u2049]"
        )
        ip_pattern = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
        external_url_pattern = re.compile(r"https?://(?!localhost|127\.0\.0\.1|www\.w3\.org|smartcontractum\.ru)[^\s\'\"<>]+")

        files_to_check = [
            ("card.js", self.card_js),
            ("feed.css", self.feed_css),
            ("editor.css", self.editor_css),
        ]

        with open(__file__, "r", encoding="utf-8") as f:
            test_content = f.read()
        files_to_check.append(("test_issue161_unified_card_identity_header.py", test_content))

        for filename, content in files_to_check:
            self.assertNotIn(em_dash, content, f"{filename} contains em dashes")
            self.assertEqual(len(emoji_pattern.findall(content)), 0, f"{filename} contains emojis")

        # In production frontend files, verify no machine paths or server IPs or remote CDN
        for filename, content in [("card.js", self.card_js), ("feed.css", self.feed_css), ("editor.css", self.editor_css)]:
            self.assertNotIn("/home/", content, f"{filename} contains local home path")
            self.assertNotIn("/tmp/", content, f"{filename} contains tmp path")
            self.assertEqual(len(ip_pattern.findall(content)), 0, f"{filename} contains IP address")
            self.assertEqual(len(external_url_pattern.findall(content)), 0, f"{filename} contains external CDN URL")


if __name__ == "__main__":
    unittest.main()
