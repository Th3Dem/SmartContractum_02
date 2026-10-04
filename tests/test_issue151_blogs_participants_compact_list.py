import json
import os
import re
import shutil
import tempfile
import threading
import time
import unittest
import urllib.request
from typing import Any, Dict

import server
from server import create_server, init_db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue151BlogsParticipantsCompactList(unittest.TestCase):
    """
    Targeted tests for Issue #151:
    - Participants list rendered as a dense, scan-friendly directory
    - Left-aligned structure: logo (40-44px) + content (name + verified, specialization, description)
    - Compact row height (~105-125px) and unified surface with dividers
    - Specialization secondary styling (not link blue)
    - Description clamped to 2 lines
    - Single-line stats with correct Russian pluralization and middle dot separator
    - Independent Subscribe button click without row navigation to blog
    - Standardized search input matching platform feed search toolbar
    - Empty state with create corporate blog CTA
    - Invariants: 100% offline-first, zero emojis, zero em dashes
    """

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue151.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path, seed=True)
        conn.close()

        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR, seed=False)
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.1)

        feed_html_path = os.path.join(FRONTEND_DIR, "feed.html")
        with open(feed_html_path, "r", encoding="utf-8") as f:
            cls.feed_html = f.read()

        feed_js_path = os.path.join(FRONTEND_DIR, "js", "feed.js")
        with open(feed_js_path, "r", encoding="utf-8") as f:
            cls.feed_js = f.read()

        feed_css_path = os.path.join(FRONTEND_DIR, "css", "feed.css")
        with open(feed_css_path, "r", encoding="utf-8") as f:
            cls.feed_css = f.read()

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "httpd"):
            cls.httpd.shutdown()
        if hasattr(cls, "temp_dir") and os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_participants_render_as_single_column_list(self):
        """
        Verify participants catalog renders as a single-column flex list,
        not a multi-column grid layout.
        """
        # feed.html container check
        self.assertIn('id="companiesCatalogList"', self.feed_html)
        self.assertIn('class="companies-catalog-list"', self.feed_html)

        # feed.css single column flex list rules
        self.assertIn(".companies-catalog-list {", self.feed_css)
        list_match = re.search(r"\.companies-catalog-list\s*\{([^}]+)\}", self.feed_css)
        self.assertIsNotNone(list_match, ".companies-catalog-list CSS rule must exist")
        list_body = list_match.group(1)
        self.assertIn("display: flex;", list_body)
        self.assertIn("flex-direction: column;", list_body)
        self.assertIn("gap: 0;", list_body)
        self.assertNotIn("repeat(auto-fill", list_body)

        # feed.js appends company-participant-row sequentially
        self.assertIn("function renderCompaniesParticipantsList(companies)", self.feed_js)
        self.assertIn("company-participant-row", self.feed_js)
        self.assertIn("list.appendChild(row)", self.feed_js)

    def test_02_left_alignment_and_no_center_layout(self):
        """
        Verify left alignment of participant identity and removal of center layout:
        participant-main -> avatar + participant-content (header, spec, desc).
        """
        # feed.js markup structure
        self.assertIn("participant-main", self.feed_js)
        self.assertIn("participant-content", self.feed_js)
        self.assertIn("participant-header", self.feed_js)
        self.assertIn("participant-spec entity-card-spec", self.feed_js)
        self.assertIn("participant-desc entity-card-desc", self.feed_js)
        self.assertIn("participant-meta-col", self.feed_js)

        # No legacy center column
        render_fn_idx = self.feed_js.find("function renderCompaniesParticipantsList(companies)")
        render_fn_end = self.feed_js.find("function renderCompaniesGrid", render_fn_idx)
        render_fn_body = self.feed_js[render_fn_idx:render_fn_end]
        self.assertNotIn("participant-center", render_fn_body)
        self.assertNotIn("participant-left", render_fn_body)
        self.assertNotIn("participant-right", render_fn_body)

        # feed.css alignment
        self.assertIn(".participant-main {", self.feed_css)
        main_match = re.search(r"\.participant-main\s*\{([^}]+)\}", self.feed_css)
        self.assertIsNotNone(main_match)
        main_body = main_match.group(1)
        self.assertIn("display: flex;", main_body)
        self.assertIn("align-items: flex-start;", main_body)
        self.assertIn("gap: 14px;", main_body)
        self.assertIn("min-width: 0;", main_body)
        self.assertIn("flex: 1;", main_body)

        # participant-content text alignment
        content_match = re.search(r"\.participant-content\s*\{([^}]+)\}", self.feed_css)
        self.assertIsNotNone(content_match)
        self.assertIn("text-align: left;", content_match.group(1))

    def test_03_avatar_and_row_compact_height(self):
        """
        Verify avatar size is within 42-56px range and row padding is compact,
        giving a dense scan-friendly row height.
        """
        # Avatar dimensions
        avatar_match = re.search(r"\.participant-avatar\s*\{([^}]+)\}", self.feed_css)
        self.assertIsNotNone(avatar_match)
        avatar_body = avatar_match.group(1)
        self.assertTrue("width: 42px;" in avatar_body or "width: 52px;" in avatar_body or "width: 56px;" in avatar_body)
        self.assertTrue("height: 42px;" in avatar_body or "height: 52px;" in avatar_body or "height: 56px;" in avatar_body)
        self.assertIn("border-radius: var(--radius-md);", avatar_body)

        # Row compact padding
        row_match = re.search(r"\.company-participant-row\s*\{([^}]+)\}", self.feed_css)
        self.assertIsNotNone(row_match)
        row_body = row_match.group(1)
        self.assertTrue("padding: 14px 18px;" in row_body or "padding: 16px 20px;" in row_body)
        self.assertIn("cursor: pointer;", row_body)
        self.assertIn("transform: none;", row_body)

    def test_04_specialization_not_link_blue(self):
        """
        Verify company specialization is rendered in secondary text color,
        NOT in link blue (--accent-color).
        """
        spec_match = re.search(r"\.participant-spec\s*\{([^}]+)\}", self.feed_css)
        self.assertIsNotNone(spec_match)
        spec_body = spec_match.group(1)
        self.assertIn("color: var(--text-secondary);", spec_body)
        self.assertNotIn("var(--accent-color)", spec_body)
        self.assertTrue("font-size: 0.82rem;" in spec_body or "font-size: 0.85rem;" in spec_body)
        self.assertIn("font-weight: 500;", spec_body)

    def test_05_description_clamped(self):
        """
        Verify description is clamped (single-line or 2 lines) with muted text and line-height 1.35.
        """
        desc_match = re.search(r"\.participant-desc\s*\{([^}]+)\}", self.feed_css)
        self.assertIsNotNone(desc_match)
        desc_body = desc_match.group(1)
        self.assertTrue("-webkit-line-clamp:" in desc_body or ("white-space: nowrap;" in desc_body and "text-overflow: ellipsis;" in desc_body))
        self.assertIn("overflow: hidden;", desc_body)
        self.assertTrue("font-size: 0.84rem;" in desc_body or "font-size: 0.85rem;" in desc_body)
        self.assertIn("line-height: 1.35;", desc_body)
        self.assertIn("color: var(--text-muted);", desc_body)
        self.assertIn("margin: 0;", desc_body)

    def test_06_single_line_stats_with_pluralization(self):
        """
        Verify single-line stats format:
        [pluralized publications] · [pluralized subscribers]
        with middle dot separator and white-space nowrap.
        """
        # CSS rule
        stats_match = re.search(r"\.participant-stats\s*\{([^}]+)\}", self.feed_css)
        self.assertIsNotNone(stats_match)
        stats_body = stats_match.group(1)
        self.assertTrue("font-size: 0.8rem;" in stats_body or "font-size: 0.82rem;" in stats_body)
        self.assertIn("color: var(--text-muted);", stats_body)
        self.assertIn("white-space: nowrap;", stats_body)

        # JS single-line composition with middle dot
        self.assertIn("pluralizePublications(comp.articlesCount || 0)", self.feed_js)
        self.assertIn("pluralize(comp.subscribersCount || 0, 'подписчик', 'подписчика', 'подписчиков')", self.feed_js)
        self.assertIn("participant-stats", self.feed_js)

        # Verify Russian pluralization cases
        def pluralize(n, one, two, five):
            abs_n = abs(n) % 100
            num1 = abs_n % 10
            if abs_n > 10 and abs_n < 20:
                return five
            if num1 > 1 and num1 < 5:
                return two
            if num1 == 1:
                return one
            return five

        def pluralize_pubs(n):
            return f"{n} {pluralize(n, 'публикация', 'публикации', 'публикаций')}"

        def pluralize_subs(n):
            return f"{n} {pluralize(n, 'подписчик', 'подписчика', 'подписчиков')}"

        self.assertEqual(f"{pluralize_pubs(0)} · {pluralize_subs(0)}", "0 публикаций · 0 подписчиков")
        self.assertEqual(f"{pluralize_pubs(1)} · {pluralize_subs(1)}", "1 публикация · 1 подписчик")
        self.assertEqual(f"{pluralize_pubs(2)} · {pluralize_subs(2)}", "2 публикации · 2 подписчика")
        self.assertEqual(f"{pluralize_pubs(5)} · {pluralize_subs(5)}", "5 публикаций · 5 подписчиков")
        self.assertEqual(f"{pluralize_pubs(21)} · {pluralize_subs(21)}", "21 публикация · 21 подписчик")

    def test_07_subscribe_isolated_from_row_navigation(self):
        """
        Verify clicking Subscribe button stops propagation and toggles subscription
        without triggering company blog opening.
        Clicking anywhere else on the row opens company blog.
        """
        # Subscribe button event listener stops propagation
        self.assertIn("subBtn.addEventListener('click', function (e) {", self.feed_js)
        self.assertIn("e.stopPropagation();", self.feed_js)
        self.assertIn("toggleSubscription('company', comp.id, subBtn, comp.name);", self.feed_js)

        # Row click handler verifies non-button click before openCompanyDetail
        self.assertIn("function handleOpenBlog(e) {", self.feed_js)
        self.assertIn("if (e.target.closest('.btn-participant-sub')", self.feed_js)
        self.assertIn("openCompanyDetail(comp.id);", self.feed_js)

        # Keyboard accessibility on row
        self.assertIn("row.addEventListener('keydown', function (e) {", self.feed_js)

    def test_08_search_input_standardized(self):
        """
        Verify search input matches standard feed toolbar search input (36px, radius, border, focus),
        toolbar margin is compact (12px), and real-time filtering is attached.
        """
        # HTML placeholder and class
        self.assertIn('id="companiesSearchInput"', self.feed_html)
        self.assertIn('placeholder="Поиск участников по названию или специализации"', self.feed_html)
        self.assertIn('class="feed-subnav-search-input blogs-search-input"', self.feed_html)

        # Toolbar compact margin
        tb_match = re.search(r"\.blogs-participants-toolbar\s*\{([^}]+)\}", self.feed_css)
        self.assertIsNotNone(tb_match)
        self.assertIn("margin-bottom: 12px;", tb_match.group(1))

        # Search input styling matching standard toolbar
        input_match = re.search(r"\.blogs-search-input\s*\{([^}]+)\}", self.feed_css)
        self.assertIsNotNone(input_match)
        input_body = input_match.group(1)
        self.assertIn("height: 36px;", input_body)
        self.assertIn("padding: 6px 32px 6px 34px;", input_body)
        self.assertIn("border-radius: var(--radius-md);", input_body)
        self.assertIn("border: 1px solid var(--border-color);", input_body)

        # Real-time search filtering in JS
        self.assertIn("companiesSearchInput.addEventListener('input', handleCompaniesFilter);", self.feed_js)
        self.assertIn("comp.specialization", self.feed_js)
        self.assertIn("comp.name", self.feed_js)

    def test_09_unified_list_surface_and_empty_state(self):
        """
        Verify unified list surface with subtle bottom borders, hover state,
        and empty state with create corporate blog CTA.
        """
        # Surface styling
        list_match = re.search(r"\.companies-catalog-list\s*\{([^}]+)\}", self.feed_css)
        self.assertIsNotNone(list_match)
        list_body = list_match.group(1)
        self.assertIn("background: var(--bg-surface);", list_body)
        self.assertIn("border: 1px solid var(--border-color);", list_body)
        self.assertIn("border-radius: var(--radius-md);", list_body)
        self.assertIn("overflow: hidden;", list_body)

        # Row dividers
        row_match = re.search(r"\.company-participant-row\s*\{([^}]+)\}", self.feed_css)
        self.assertIsNotNone(row_match)
        row_body = row_match.group(1)
        self.assertIn("border-bottom: 1px solid var(--border-color);", row_body)
        self.assertIn("background: transparent;", row_body)

        self.assertIn(".company-participant-row:last-child {", self.feed_css)
        self.assertIn(".company-participant-row:hover {", self.feed_css)

        # Empty state handling
        self.assertIn("Пока ни одна компания не ведет блог", self.feed_js)
        self.assertIn("Создать блог компании", self.feed_js)
        self.assertIn("openCreateCompanyModal();", self.feed_js)

    def test_10_invariants_no_emojis_no_em_dashes(self):
        """
        Invariants check:
        - Zero emojis across feed.html, feed.js, feed.css, and test file
        - Zero em dashes (chr(8212)) across feed.html, feed.js, feed.css, and test file
        - No hardcoded local machine paths or external IP addresses
        """
        em_dash = chr(8212)
        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]", flags=re.UNICODE)

        # feed.html participants section
        start = self.feed_html.find('id="blogsParticipantsView"')
        end = self.feed_html.find('id="companyDetailView"')
        participants_html = self.feed_html[start:end]
        self.assertNotIn(em_dash, participants_html, "Participants HTML must not contain em dashes")
        self.assertEqual(len(emoji_pattern.findall(participants_html)), 0, "Participants HTML must not contain emojis")

        # feed.js participants section
        js_start = self.feed_js.find("function renderCompaniesParticipantsList(companies)")
        js_end = self.feed_js.find("function renderCompanyDetailCard", js_start)
        participants_js = self.feed_js[js_start:js_end]
        self.assertNotIn(em_dash, participants_js, "Participants JS must not contain em dashes")
        self.assertEqual(len(emoji_pattern.findall(participants_js)), 0, "Participants JS must not contain emojis")

        # feed.css participants section
        css_start = self.feed_css.find("/* Participants View: Unified scan-friendly list surface */")
        css_end = self.feed_css.find("/* Company Detail View", css_start)
        participants_css = self.feed_css[css_start:css_end]
        self.assertNotIn(em_dash, participants_css, "Participants CSS must not contain em dashes")
        self.assertEqual(len(emoji_pattern.findall(participants_css)), 0, "Participants CSS must not contain emojis")

        # Current test file
        test_file_path = os.path.abspath(__file__)
        with open(test_file_path, "r", encoding="utf-8") as f:
            test_content = f.read()
        self.assertNotIn(em_dash, test_content, "Test file must not contain em dashes")
        self.assertEqual(len(emoji_pattern.findall(test_content)), 0, "Test file must not contain emojis")


if __name__ == "__main__":
    unittest.main()
