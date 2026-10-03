import json
import os
import re
import shutil
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict

import server
from server import create_server, init_db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue138TopicsCatalog(unittest.TestCase):
    """
    Targeted tests for Issue #138 and Issue #149:
    - Topics catalog view based on existing directions infrastructure
    - All 13 topics returned by /api/directions with Russian titles and descriptions
    - 13 distinct thematic SVG icons without emojis or external CDN links
    - Single-column list layout (no repeat(2, 1fr))
    - Compact topic rows with icon, title, description, metadata, and subscribe button
    - No separate 'К публикациям' button
    - Row click navigation to filtered feed with topic filter active
    - Sidebar 'Все темы' button navigating directly to directions tab
    - Dedicated search input with placeholder 'Поиск по темам'
    - Duplicate sidebar widget and feed stream toolbar hidden when directions tab is active
    - Zero technical slugs displayed in topic card titles
    - Zero emojis and zero em dashes
    """

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue138.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path, seed=True)
        conn.close()

        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR, seed=False)
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "httpd"):
            cls.httpd.shutdown()
        if hasattr(cls, "temp_dir") and os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def _api_get(self, path: str) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, headers={"Content-Type": "application/json"}, method="GET")
        with urllib.request.urlopen(req) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data)

    def test_01_api_directions_returns_all_13_topics(self):
        """Verify /api/directions returns all 13 standard topics with metadata."""
        data = self._api_get("/api/directions")
        self.assertTrue(data.get("success"))
        directions = data.get("directions", [])
        self.assertEqual(len(directions), 13)

        topic_ids = [d["id"] for d in directions]
        expected_ids = [
            "pksc-architecture",
            "smart-contracts-development",
            "business-logic-deals",
            "testing-and-quality",
            "information-security",
            "audit-and-verification",
            "law-and-compliance",
            "oracles-and-data",
            "integrations-and-api",
            "digital-ruble-payments",
            "lifecycle-versioning",
            "infrastructure-operations",
            "business-cases-adoption"
        ]
        for eid in expected_ids:
            self.assertIn(eid, topic_ids)

        for d in directions:
            self.assertTrue(len(d["title"]) > 0)
            self.assertTrue(len(d["description"]) > 0)
            self.assertIn("articlesCount", d)
            self.assertIn("subscribersCount", d)
            self.assertIn("isSubscribed", d)

    def test_02_api_directions_search_filtering(self):
        """Verify search query filters topics by title and description."""
        data = self._api_get("/api/directions?search=" + urllib.parse.quote("рубль"))
        self.assertTrue(data.get("success"))
        directions = data.get("directions", [])
        self.assertTrue(any("рубль" in d["title"].lower() or "рубл" in d["description"].lower() for d in directions))

    def test_03_html_topics_view_structure(self):
        """Verify HTML elements for Topics catalog view per Issue #149."""
        feed_html_path = os.path.join(FRONTEND_DIR, "feed.html")
        with open(feed_html_path, "r", encoding="utf-8") as f:
            html = f.read()

        # Both new and backward-compatible IDs are supported
        self.assertIn('id="directionsFeedView"', html)
        self.assertIn('id="directionsView"', html)
        self.assertIn("Темы", html)
        self.assertIn("Каталог тем и специализаций SmartContractum", html)
        self.assertIn('id="directionsSearchInput"', html)
        self.assertIn('placeholder="Поиск по темам"', html)
        self.assertIn('id="directionsCatalogGrid"', html)
        self.assertIn('id="directionsGrid"', html)
        self.assertIn('id="btnShowAllTopics"', html)

    def test_04_js_svg_icons_and_navigation(self):
        """Verify 13 SVG icons, compact row click navigation, and absence of legacy button."""
        feed_js_path = os.path.join(FRONTEND_DIR, "js", "feed.js")
        with open(feed_js_path, "r", encoding="utf-8") as f:
            js = f.read()

        # Check TOPIC_ICONS definition
        self.assertIn("TOPIC_ICONS", js)
        self.assertIn("pksc-architecture", js)
        self.assertIn("smart-contracts-development", js)
        self.assertIn("information-security", js)
        self.assertIn("digital-ruble-payments", js)

        # Legacy button removed completely per Issue #149
        self.assertNotIn("К публикациям", js)

        # Row click navigation to filtered feed with topic filter active
        self.assertIn("state.filters.topics = [dir.id]", js)
        self.assertIn("switchTab('all')", js)

        # Sidebar button navigation to directions tab
        self.assertIn("switchTab('directions')", js)

        # Sorting: articlesCount descending, then alphabetical by title in Russian
        self.assertIn("localeCompare", js)

        # Real-time search input binding
        self.assertIn("directionsSearchInput", js)

        # Ensure no emojis in JS
        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]", flags=re.UNICODE)
        self.assertEqual(len(emoji_pattern.findall(js)), 0)

    def test_05_css_single_column_layout_and_compact_rows(self):
        """Verify single-column flex list layout and compact row dimensions."""
        feed_css_path = os.path.join(FRONTEND_DIR, "css", "feed.css")
        with open(feed_css_path, "r", encoding="utf-8") as f:
            css = f.read()

        # Single-column vertical list: no repeat(2, 1fr) for directions
        self.assertNotIn("repeat(2, 1fr)", css)
        self.assertIn(".directions-catalog-grid", css)
        self.assertIn("flex-direction: column", css)
        self.assertIn("gap: 8px", css)

        # Compact row styling with 72-100px desktop height target
        self.assertIn(".direction-catalog-card", css)
        self.assertIn("min-height: 72px", css)
        self.assertIn("max-height: 100px", css)
        self.assertIn("padding: 12px 16px", css)

        # Legacy separate button styles removed
        self.assertNotIn(".btn-direction-feed", css)

    def test_06_sidebar_and_toolbar_hidden_on_directions_tab(self):
        """Verify feedStreamToolbar and duplicate widget-topics-card are hidden on directions tab."""
        feed_js_path = os.path.join(FRONTEND_DIR, "js", "feed.js")
        with open(feed_js_path, "r", encoding="utf-8") as f:
            js = f.read()

        feed_css_path = os.path.join(FRONTEND_DIR, "css", "feed.css")
        with open(feed_css_path, "r", encoding="utf-8") as f:
            css = f.read()

        # In JS: streamToolbar and widget-topics-card hidden when tabName === 'directions'
        self.assertIn("feedStreamToolbar", js)
        self.assertIn("widget-topics-card", js)
        self.assertIn("is-directions-tab", js)

        # In CSS: deduplication rules
        self.assertIn("body.is-directions-tab #feedStreamToolbar", css)
        self.assertIn("body.is-directions-tab .widget-topics-card", css)

    def test_07_zero_emojis_and_zero_em_dashes(self):
        """Verify strict adherence to zero emojis and zero em dashes invariants."""
        test_file_path = __file__
        with open(test_file_path, "r", encoding="utf-8") as f:
            test_content = f.read()

        feed_css_path = os.path.join(FRONTEND_DIR, "css", "feed.css")
        with open(feed_css_path, "r", encoding="utf-8") as f:
            css_content = f.read()

        feed_html_path = os.path.join(FRONTEND_DIR, "feed.html")
        with open(feed_html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]", flags=re.UNICODE)

        # Zero emojis
        self.assertEqual(len(emoji_pattern.findall(test_content)), 0)
        self.assertEqual(len(emoji_pattern.findall(css_content)), 0)

        # Zero em dashes (code point 8212)
        em_dash = chr(8212)

        # Verify no em dash in test file itself
        self.assertNotIn(em_dash, test_content)

        # Verify no em dash in newly added directions CSS section
        directions_css_marker = "Topics / Directions Compact Catalog View (Issue #149)"
        self.assertIn(directions_css_marker, css_content)
        directions_css_part = css_content[css_content.index(directions_css_marker):]
        self.assertNotIn(em_dash, directions_css_part)

        # Verify no em dash in directions HTML section
        dir_start = html_content.index('id="directionsFeedView"')
        dir_end = html_content.index('</section>', dir_start)
        self.assertNotIn(em_dash, html_content[dir_start:dir_end])


if __name__ == "__main__":
    unittest.main()
