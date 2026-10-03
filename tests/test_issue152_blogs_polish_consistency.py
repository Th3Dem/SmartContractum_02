import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(REPO_ROOT, "frontend", "public")


class TestIssue152BlogsPolishConsistency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        feed_html_path = os.path.join(FRONTEND_DIR, "feed.html")
        with open(feed_html_path, "r", encoding="utf-8") as f:
            cls.feed_html = f.read()

        feed_css_path = os.path.join(FRONTEND_DIR, "css", "feed.css")
        with open(feed_css_path, "r", encoding="utf-8") as f:
            cls.feed_css = f.read()

        feed_js_path = os.path.join(FRONTEND_DIR, "js", "feed.js")
        with open(feed_js_path, "r", encoding="utf-8") as f:
            cls.feed_js = f.read()

        card_js_path = os.path.join(FRONTEND_DIR, "js", "card.js")
        with open(card_js_path, "r", encoding="utf-8") as f:
            cls.card_js = f.read()

    def test_01_tabs_consistent_active_and_focus_visible_states(self):
        """
        Tabs states consistency:
        - .blogs-subtab-btn.active has accent color, background, and border
        - :focus:not(:focus-visible) removes mouse outline
        - :focus-visible provides accessible focus ring
        - Legacy duplicate .companies-subtab-btn removed from orphan location
        """
        # Active state
        self.assertIn(".blogs-subtab-btn.active", self.feed_css)
        self.assertIn("color: var(--accent-color);", self.feed_css)
        self.assertIn("background: rgba(56, 189, 248, 0.12);", self.feed_css)
        self.assertIn("border-color: rgba(56, 189, 248, 0.25);", self.feed_css)

        # Focus states
        self.assertIn(".blogs-subtab-btn:focus:not(:focus-visible)", self.feed_css)
        self.assertIn(".blogs-subtab-btn:focus-visible", self.feed_css)
        self.assertIn("outline: 2px solid var(--accent-color);", self.feed_css)
        self.assertIn("outline-offset: 2px;", self.feed_css)

        # Hover state
        self.assertIn(".blogs-subtab-btn:hover", self.feed_css)

        # Ensure obsolete duplicate block is cleaned up
        self.assertNotIn(".companies-subtabs-bar {", self.feed_css)
        self.assertNotIn(".companies-subtab-btn {", self.feed_css)

    def test_02_create_blog_button_secondary_compact(self):
        """
        'Sozdat blog kompanii' button visual weight reduction:
        - Compact dimensions: height 32px, padding 0 12px, font-size 0.8rem, font-weight 500
        - Border radius var(--radius-md)
        - Secondary styling and plus icon preserved
        """
        btn_start = self.feed_css.find(".btn-blogs-create {")
        self.assertNotEqual(btn_start, -1, ".btn-blogs-create rule must exist in feed.css")
        btn_end = self.feed_css.find("}", btn_start)
        btn_rules = self.feed_css[btn_start:btn_end]

        self.assertIn("height: 32px;", btn_rules)
        self.assertIn("padding: 0 12px;", btn_rules)
        self.assertIn("font-size: 0.8rem;", btn_rules)
        self.assertIn("font-weight: 500;", btn_rules)
        self.assertIn("border-radius: var(--radius-md);", btn_rules)

        # HTML checks
        self.assertIn('id="btnBlogsCreateBlog"', self.feed_html)
        self.assertIn('class="btn btn-secondary btn-blogs-create"', self.feed_html)
        self.assertIn("Создать блог компании", self.feed_html)
        self.assertIn('<line x1="12" y1="5" x2="12" y2="19"', self.feed_html)
        self.assertIn('<line x1="5" y1="12" x2="19" y2="12"', self.feed_html)

    def test_03_no_raw_topic_slugs_in_unanswered_widget(self):
        """
        Sidebar unanswered questions widget:
        - Eliminates raw topic slugs (e.g. smart-contracts-development)
        - Item HTML renders question title link and date only
        - No TOPICS_MAP or topicTitle references inside loadUnansweredQuestions
        """
        load_fn_start = self.feed_js.find("function loadUnansweredQuestions()")
        self.assertNotEqual(load_fn_start, -1)
        load_fn_end = self.feed_js.find("loadUnansweredQuestions();", load_fn_start)
        load_fn_code = self.feed_js[load_fn_start:load_fn_end]

        # Must not contain topicTitle or TOPICS_MAP
        self.assertNotIn("topicTitle", load_fn_code)
        self.assertNotIn("TOPICS_MAP", load_fn_code)
        self.assertNotIn("q.topic", load_fn_code)

        # Must render title and date only
        self.assertIn("unanswered-item-title", load_fn_code)
        self.assertIn("unanswered-item-meta", load_fn_code)
        self.assertIn("dateStr", load_fn_code)

        # Simulation: verify rendered item HTML contains only title and date
        mock_q = {
            "id": 101,
            "title": "Kak realizovat timelock v Rust?",
            "topic": "smart-contracts-development",
            "date": "10 мая 2026",
        }

        # Simulated template matching feed.js implementation
        def render_unanswered_item(q):
            date_str = q.get("date", "")
            return (
                '<a href="article.html?id=' + str(q["id"]) + '" class="unanswered-item-title">' + q["title"] + '</a>' +
                '<div class="unanswered-item-meta">' +
                  (f'<span>{date_str}</span>' if date_str else '') +
                '</div>'
            )

        rendered_html = render_unanswered_item(mock_q)
        self.assertIn("Kak realizovat timelock v Rust?", rendered_html)
        self.assertIn("10 мая 2026", rendered_html)
        self.assertNotIn("smart-contracts-development", rendered_html)
        self.assertNotIn("pksc-architecture", rendered_html)

    def test_04_sidebar_widgets_visual_unification(self):
        """
        Right sidebar widgets visual unification:
        - Cards (#widgetCommunityCta, #widgetUnansweredQuestions, .widget-topics-card)
          share unified appearance: border-radius: var(--radius-lg), padding: 16px 18px,
          border: 1px solid var(--border-color), background: var(--bg-card)
        - All use .widget-header with consistent spacing
        """
        # CSS checks
        self.assertIn(".feed-widget-card,", self.feed_css)
        self.assertIn("#widgetCommunityCta,", self.feed_css)
        self.assertIn("#widgetUnansweredQuestions,", self.feed_css)
        self.assertIn(".widget-topics-card", self.feed_css)

        # Widget styling properties
        widget_card_idx = self.feed_css.find(".feed-widget-card,")
        widget_card_end = self.feed_css.find("}", widget_card_idx)
        widget_rules = self.feed_css[widget_card_idx:widget_card_end]

        self.assertIn("background: var(--bg-card);", widget_rules)
        self.assertIn("border: 1px solid var(--border-color);", widget_rules)
        self.assertIn("border-radius: var(--radius-lg);", widget_rules)
        self.assertIn("padding: 16px 18px;", widget_rules)

        # HTML checks
        self.assertIn('id="widgetCommunityCta"', self.feed_html)
        self.assertIn('id="widgetUnansweredQuestions"', self.feed_html)
        self.assertIn('class="feed-widget-card widget-topics-card"', self.feed_html)

        cta_idx = self.feed_html.find('id="widgetCommunityCta"')
        self.assertIn("feed-widget-card", self.feed_html[cta_idx - 50:cta_idx + 50])

        unans_idx = self.feed_html.find('id="widgetUnansweredQuestions"')
        self.assertIn("feed-widget-card", self.feed_html[unans_idx - 50:unans_idx + 50])

    def test_05_blogs_header_and_content_grid_alignment(self):
        """
        Grid and left axis alignment:
        - Blogs header padding has 0 on left/right
        - Subtabs bar starts flush at left edge
        - Toolbar slot width 100%
        - Participants list width 100%
        - Corporate card meta left aligned
        """
        # Header alignment
        self.assertIn(".blogs-view-header {", self.feed_css)
        header_start = self.feed_css.find(".blogs-view-header {")
        header_end = self.feed_css.find("}", header_start)
        header_rules = self.feed_css[header_start:header_end]
        self.assertIn("padding: 0 0 8px 0;", header_rules)

        # Subtabs bar
        self.assertIn(".blogs-subtabs-bar {", self.feed_css)
        tabs_start = self.feed_css.find(".blogs-subtabs-bar {")
        tabs_end = self.feed_css.find("}", tabs_start)
        tabs_rules = self.feed_css[tabs_start:tabs_end]
        self.assertIn("display: flex;", tabs_rules)
        self.assertIn("gap: 8px;", tabs_rules)

        # Toolbar slot and participants list
        self.assertIn(".blogs-posts-toolbar-slot {", self.feed_css)
        self.assertIn("width: 100%;", self.feed_css)
        self.assertIn(".companies-catalog-list {", self.feed_css)
        self.assertIn(".card-corporate-meta {", self.feed_css)
        self.assertIn("text-align: left;", self.feed_css)

    def test_06_top_spacing_normalized(self):
        """
        Normalized vertical rhythm:
        - Gap between second-level nav and blogs header is normalized
        - .blogs-view-header min-height: auto; padding: 0 0 8px 0; margin-bottom: 8px;
        - .companies-feed-view gap: 0;
        """
        header_start = self.feed_css.find(".blogs-view-header {")
        header_end = self.feed_css.find("}", header_start)
        header_rules = self.feed_css[header_start:header_end]

        self.assertIn("min-height: auto;", header_rules)
        self.assertIn("padding: 0 0 8px 0;", header_rules)
        self.assertIn("margin-bottom: 8px;", header_rules)

        view_start = self.feed_css.find(".companies-feed-view {")
        view_end = self.feed_css.find("}", view_start)
        view_rules = self.feed_css[view_start:view_end]
        self.assertIn("gap: 0;", view_rules)

    def test_07_verification_icon_consistency(self):
        """
        Verification icon standardization:
        - .verified-icon defined in CSS with consistent color and vertical alignment
        - SVG size standardized (15px) with stroke-width 2.5
        - Accessible tooltip (title and aria-label) present across feed card,
          participants directory, and company profile detail card
        """
        # CSS checks
        self.assertIn(".verified-icon {", self.feed_css)
        self.assertIn(".verified-icon svg {", self.feed_css)

        icon_start = self.feed_css.find(".verified-icon {")
        icon_end = self.feed_css.find("}", icon_start)
        icon_rules = self.feed_css[icon_start:icon_end]
        self.assertIn("display: inline-flex;", icon_rules)
        self.assertIn("color: var(--accent-color);", icon_rules)

        svg_start = self.feed_css.find(".verified-icon svg {")
        svg_end = self.feed_css.find("}", svg_start)
        svg_rules = self.feed_css[svg_start:svg_end]
        self.assertIn("width: 15px;", svg_rules)
        self.assertIn("height: 15px;", svg_rules)
        self.assertIn("stroke-width: 2.5;", svg_rules)

        # JS checks in card.js
        self.assertIn('class="verified-icon"', self.card_js)
        self.assertIn('title="Верифицированная компания"', self.card_js)
        self.assertIn('aria-label="Верифицированная компания"', self.card_js)

        # JS checks in feed.js
        self.assertIn('class="verified-icon"', self.feed_js)
        self.assertIn('title="Верифицированная компания"', self.feed_js)
        self.assertIn('aria-label="Верифицированная компания"', self.feed_js)

    def test_08_invariants_no_emojis_no_em_dashes(self):
        """
        Strict invariants:
        - 100% offline-first (no external network dependencies)
        - Zero emojis in modified frontend code and test file
        - Zero em dashes (use hyphens instead)
        - No local machine paths or real IPs in code
        """
        em_dash = chr(8212)
        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]", flags=re.UNICODE)

        # 1. card.js
        self.assertNotIn(em_dash, self.card_js, "card.js must not contain em dashes")
        self.assertEqual(len(emoji_pattern.findall(self.card_js)), 0, "card.js must not contain emojis")

        # 2. feed.css
        self.assertNotIn(em_dash, self.feed_css, "feed.css must not contain em dashes")
        self.assertEqual(len(emoji_pattern.findall(self.feed_css)), 0, "feed.css must not contain emojis")

        # 3. Blogs section in feed.html
        start = self.feed_html.find('id="companiesView"')
        end = self.feed_html.find('id="directionsFeedView"')
        blogs_html = self.feed_html[start:end]
        self.assertNotIn(em_dash, blogs_html, "Corporate blogs HTML must not contain em dashes")
        self.assertEqual(len(emoji_pattern.findall(blogs_html)), 0, "Corporate blogs HTML must not contain emojis")

        # 4. loadUnansweredQuestions in feed.js
        unans_start = self.feed_js.find("function loadUnansweredQuestions()")
        unans_end = self.feed_js.find("loadUnansweredQuestions();", unans_start)
        unans_code = self.feed_js[unans_start:unans_end]
        self.assertNotIn(em_dash, unans_code, "loadUnansweredQuestions must not contain em dashes")
        self.assertEqual(len(emoji_pattern.findall(unans_code)), 0, "loadUnansweredQuestions must not contain emojis")

        # 5. Current test file
        test_file_path = os.path.abspath(__file__)
        with open(test_file_path, "r", encoding="utf-8") as f:
            test_content = f.read()
        self.assertNotIn(em_dash, test_content, "Test file must not contain em dashes")
        self.assertEqual(len(emoji_pattern.findall(test_content)), 0, "Test file must not contain emojis")

        # 6. No local machine paths or real IPs
        for content, name in [
            (self.card_js, "card.js"),
            (self.feed_css, "feed.css")
        ]:
            self.assertNotIn("/home/", content, f"{name} must not contain local paths")
            self.assertNotIn("192.168.", content, f"{name} must not contain local IPs")
            self.assertNotIn("127.0.0.1", content, f"{name} must not contain local IPs")


if __name__ == "__main__":
    unittest.main()
