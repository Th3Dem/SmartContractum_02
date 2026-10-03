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
        """Verify HTML elements for Corporate Blogs section."""
        feed_html_path = os.path.join(FRONTEND_DIR, "feed.html")
        with open(feed_html_path, "r", encoding="utf-8") as f:
            html = f.read()

        self.assertIn('id="companiesView"', html)
        self.assertIn("Блоги компаний", html)
        self.assertIn("Публикации компаний, команд и технологических организаций сообщества", html)
        self.assertIn("Создать блог компании", html)
        self.assertIn('id="btnCompaniesTabCatalog"', html)
        self.assertIn('id="btnCompaniesTabArticles"', html)
        self.assertIn("Назад ко всем блогам", html)

    def test_04_js_url_routing_and_titles(self):
        """Verify feed.js maps tab=blogs to companies view and updates document title."""
        feed_js_path = os.path.join(FRONTEND_DIR, "js", "feed.js")
        with open(feed_js_path, "r", encoding="utf-8") as f:
            js = f.read()

        # Check tab=blogs mapping in parseURLParams
        self.assertIn("tabParam === 'blogs'", js)
        self.assertIn("state.tab = 'companies'", js)

        # Check title mapping
        self.assertIn("companies: 'Блоги", js)

        # Check cards empty state
        self.assertIn("Блоги компаний не найдены", js)


if __name__ == "__main__":
    unittest.main()
