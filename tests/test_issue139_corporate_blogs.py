import json
import os
import shutil
import sqlite3
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


class TestIssue139CorporateBlogs(unittest.TestCase):
    """
    Targeted tests for Issue #139:
    - Corporate blogs catalog reusing existing companies infrastructure
    - GET /api/companies and POST /api/companies
    - Subtabs for Blogs and Company Publications
    - HTML titles, create blog button, and modal texts
    - URL parameter tab=blogs / tab=companies mapping
    - Subscriptions and canPublish permissions
    """

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue139.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path, seed=True)
        conn.close()

        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR, seed=False)
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.1)

        cls.user = cls._create_or_login_user("user_blog_owner", "Blog Owner")

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "httpd"):
            cls.httpd.shutdown()
        if hasattr(cls, "temp_dir") and os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir, ignore_errors=True)

    @classmethod
    def _create_or_login_user(cls, user_id: str, name: str) -> Dict[str, Any]:
        payload = json.dumps({"userId": user_id, "name": name}).encode("utf-8")
        req = urllib.request.Request(
            f"{cls.base_url}/api/auth/login",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            cookie = resp.headers.get("Set-Cookie", "")
            return {"user": data.get("user"), "cookie": cookie, "id": user_id, "name": name}

    def _api_request(self, method: str, path: str, data: Any = None, cookie: str = "") -> Any:
        url = f"{self.base_url}{path}"
        body = json.dumps(data).encode("utf-8") if data is not None else None
        headers = {"Content-Type": "application/json"}
        if cookie:
            headers["Cookie"] = cookie
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}

    def test_01_api_companies_catalog(self):
        """Verify GET /api/companies returns list of companies with required blog fields."""
        status, data = self._api_request("GET", "/api/companies")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        companies = data.get("companies", [])
        self.assertTrue(len(companies) > 0)
        c0 = companies[0]
        self.assertIn("id", c0)
        self.assertIn("name", c0)
        self.assertIn("description", c0)
        self.assertIn("articlesCount", c0)
        self.assertIn("subscribersCount", c0)
        self.assertIn("isSubscribed", c0)

    def test_02_create_company_blog(self):
        """Verify POST /api/companies creates corporate blog with canPublish=True for owner."""
        payload = {
            "name": "Тестовая Корпорация 139",
            "description": "Разработка распределенных реестров и смарт-контрактов для финтеха",
            "specialization": "Инфраструктура DLT",
            "website": "https://test-corp-139.example.com"
        }
        status, data = self._api_request("POST", "/api/companies", data=payload, cookie=self.user["cookie"])
        self.assertIn(status, (200, 201))
        self.assertTrue(data.get("success"))
        comp = data.get("company", {})
        self.assertEqual(comp.get("name"), payload["name"])
        self.assertTrue(comp.get("canPublish"))
        self.assertEqual(comp.get("ownerId"), self.user["id"])

    def test_03_html_companies_view_blogs_branding(self):
        """Verify HTML elements for Corporate Blogs section (Issues #147 & #148)."""
        feed_html_path = os.path.join(FRONTEND_DIR, "feed.html")
        with open(feed_html_path, "r", encoding="utf-8") as f:
            html = f.read()

        self.assertIn('id="companiesView"', html)
        self.assertIn("Блоги компаний", html)
        self.assertIn("Публикации компаний, команд и технологических организаций SmartContractum.", html)
        self.assertIn("Создать блог компании", html)
        self.assertIn('id="btnCompaniesTabPosts"', html)
        self.assertIn('id="btnCompaniesTabParticipants"', html)
        self.assertIn("Назад к блогам", html)
        self.assertIn("Поиск участников по названию или специализации", html)

    def test_04_js_url_routing_and_titles(self):
        """Verify feed.js maps tab=blogs to companies view and updates document title."""
        feed_js_path = os.path.join(FRONTEND_DIR, "js", "feed.js")
        with open(feed_js_path, "r", encoding="utf-8") as f:
            js = f.read()

        # Check tab=blogs mapping in parseURLParams
        self.assertIn("tabParam === 'blogs'", js)
        self.assertIn("state.tab = 'companies'", js)

        # Check view=posts / view=participants subtab parsing
        self.assertIn("state.companiesSubtab = 'posts'", js)
        self.assertIn("state.companiesSubtab = 'participants'", js)

        # Check title mapping
        self.assertIn("companies: 'Блоги", js)

        # Check empty states
        self.assertIn("Блоги компаний не найдены", js)
        self.assertIn("Пока нет публикаций от технологических компаний.", js)

    def test_05_corporate_card_identity_and_delegation(self):
        """Verify card.js renders corporate posts with company as primary identity and secondary author."""
        card_js_path = os.path.join(FRONTEND_DIR, "js", "card.js")
        with open(card_js_path, "r", encoding="utf-8") as f:
            js = f.read()

        # Primary identity elements
        self.assertIn("card-corporate-meta", js)
        self.assertIn("card-corporate-header", js)
        self.assertIn("company-card-info", js)
        self.assertIn("company-card-logo", js)
        self.assertIn("card-corporate-badge", js)
        self.assertIn("Блог компании", js)
        self.assertIn("btn-card-company-sub", js)

        # Secondary author
        self.assertIn("card-secondary-author", js)
        self.assertIn("Автор:", js)

        # Interaction handlers
        self.assertIn("options.onCompanyClick", js)
        self.assertIn("options.onCompanySubscribeToggle", js)

    def test_06_company_detail_page_and_empty_state(self):
        """Company blogs open the standalone company profile (Issue #212) with header, subscribe, CTA and empty state."""
        with open(os.path.join(FRONTEND_DIR, "js", "feed.js"), "r", encoding="utf-8") as f:
            feed_js = f.read()
        with open(os.path.join(FRONTEND_DIR, "js", "company.js"), "r", encoding="utf-8") as f:
            company_js = f.read()

        self.assertIn("'company.html?id=' + encodeURIComponent(companyId)", feed_js)
        self.assertIn("btnSubscribe", company_js)
        self.assertIn("Написать публикацию", company_js)
        self.assertIn("Публикаций пока нет", company_js)
        self.assertIn("/api/articles?", company_js)

    def test_07_invariants_no_emojis_no_em_dashes(self):
        """Invariant: Zero emojis and zero em dashes in corporate blogs modified files."""
        import re
        em_dash = chr(8212)
        emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]", flags=re.UNICODE)

        # Check feed.html corporate blogs section
        feed_html_path = os.path.join(FRONTEND_DIR, "feed.html")
        with open(feed_html_path, "r", encoding="utf-8") as f:
            html = f.read()
        start = html.index('id="companiesView"')
        end = html.index('id="directionsFeedView"')
        blogs_slice = html[start:end]
        self.assertNotIn(em_dash, blogs_slice, "Corporate blogs HTML must not contain em dashes")
        self.assertEqual(len(emoji_pattern.findall(blogs_slice)), 0, "Corporate blogs HTML must not contain emojis")

        # Check card.js
        card_js_path = os.path.join(FRONTEND_DIR, "js", "card.js")
        with open(card_js_path, "r", encoding="utf-8") as f:
            card_js = f.read()
        self.assertNotIn(em_dash, card_js, "card.js must not contain em dashes")
        self.assertEqual(len(emoji_pattern.findall(card_js)), 0, "card.js must not contain emojis")

        # Check feed.css
        feed_css_path = os.path.join(FRONTEND_DIR, "css", "feed.css")
        with open(feed_css_path, "r", encoding="utf-8") as f:
            css = f.read()
        self.assertNotIn(em_dash, css, "feed.css must not contain em dashes")
        self.assertEqual(len(emoji_pattern.findall(css)), 0, "feed.css must not contain emojis")


if __name__ == "__main__":
    unittest.main()
