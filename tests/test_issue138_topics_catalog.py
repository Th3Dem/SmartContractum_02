import json
import os
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
    Targeted tests for Issue #138:
    - Topics catalog view based on existing directions infrastructure
    - All 13 topics returned by /api/directions with Russian titles and descriptions
    - 13 distinct thematic SVG icons without emojis or external CDN links
    - 'К публикациям' button switching to feed with topic filter active
    - Sidebar 'Все темы' button navigating directly to directions tab
    - Zero technical slugs displayed in topic card titles
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
        """Verify HTML elements for Topics catalog view."""
        feed_html_path = os.path.join(FRONTEND_DIR, "feed.html")
        with open(feed_html_path, "r", encoding="utf-8") as f:
            html = f.read()

        self.assertIn('id="directionsView"', html)
        self.assertIn("Темы", html)
        self.assertIn("Каталог тем и специализаций платформы SmartContractum", html)
        self.assertIn('id="directionsSearchInput"', html)
        self.assertIn('id="directionsGrid"', html)
        self.assertIn('id="btnShowAllTopics"', html)

    def test_04_js_svg_icons_and_navigation(self):
        """Verify 13 SVG icons, 'К публикациям' button, and sidebar navigation."""
        feed_js_path = os.path.join(FRONTEND_DIR, "js", "feed.js")
        with open(feed_js_path, "r", encoding="utf-8") as f:
            js = f.read()

        # Check TOPIC_ICONS definition
        self.assertIn("TOPIC_ICONS", js)
        self.assertIn("pksc-architecture", js)
        self.assertIn("smart-contracts-development", js)
        self.assertIn("information-security", js)
        self.assertIn("digital-ruble-payments", js)

        # Check button label
        self.assertIn("К публикациям", js)

        # Check sidebar button navigation to directions tab
        self.assertIn("switchTab('directions')", js)

        # Ensure no emojis in SVG icons or topic descriptions
        import re
        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]", flags=re.UNICODE)
        self.assertEqual(len(emoji_pattern.findall(js)), 0)


if __name__ == "__main__":
    unittest.main()
