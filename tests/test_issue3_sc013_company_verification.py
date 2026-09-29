#!/usr/bin/env python3
"""
tests/test_issue3_sc013_company_verification.py

Regression test suite for Issue #3 (SC-013):
"Отключить автоматическую верификацию компаний при саморегистрации".

Acceptance Criteria:
1. POST /api/companies returns "isVerified": False in response payload.
2. Direct SQLite inspection confirms `is_verified` column is 0 in companies table,
   and schema default is 0 (INTEGER DEFAULT 0).
3. GET /api/companies and GET /api/companies/<new_id> return "isVerified": False.
4. Seed companies maintain their designated verification statuses:
   - "smarttech-innovations" -> isVerified: True (DB: 1)
   - "cryptosolutions-lab" -> isVerified: True (DB: 1)
   - "fintech-ledgers" -> isVerified: True (DB: 1)
   - "blockchain-audit-lab" -> isVerified: True (DB: 1)
   - "cyberinfra-tech" -> isVerified: False (DB: 0)
5. Frontend markup contract in feed.js:
   Badge `verified-icon` is rendered only when `comp.isVerified === true`
   and is absent when `comp.isVerified` is false.
"""

import json
import os
import re
import shutil
import sqlite3
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

import server
from server import create_server, init_db

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue3SC013CompanyVerification(unittest.TestCase):
    """Test suite for Issue #3 (SC-013) company verification logic."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue3_sc013.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path)
        conn.close()

        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR)
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.1)

        with open(os.path.join(FRONTEND_DIR, "js", "feed.js"), "r", encoding="utf-8") as f:
            cls.feed_js = f.read()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.httpd.shutdown()
            cls.httpd.server_close()
        except Exception:
            pass
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def _login(self, user_id: str = "user_demo", user_name: str = "Демо Пользователь"):
        req = urllib.request.Request(
            f"{self.base_url}/api/auth/login",
            data=json.dumps({"userId": user_id, "name": user_name}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            cookie = resp.headers.get("Set-Cookie")
            return data, cookie

    def _get_json(self, path: str, cookie: str = None):
        headers = {}
        if cookie:
            headers["Cookie"] = cookie
        req = urllib.request.Request(f"{self.base_url}{path}", headers=headers)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data

    def _post_json(self, path: str, payload: dict, cookie: str = None):
        headers = {"Content-Type": "application/json"}
        if cookie:
            headers["Cookie"] = cookie
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers
        )
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return resp.status, data
        except urllib.error.HTTPError as e:
            data = json.loads(e.read().decode("utf-8"))
            return e.code, data

    def test_post_company_returns_is_verified_false(self):
        """Тест 1: POST /api/companies возвращает 'isVerified': False."""
        _, cookie = self._login()
        payload = {
            "name": "Новая Тестовая Компания ДЛТ",
            "description": "Разработка распределенных реестров и смарт-контрактов нового поколения.",
            "specialization": "Смарт-контракты и консенсусы",
            "website": "new-test-company.example.com",
            "directions": ["pksc-architecture", "smart-contracts-development"]
        }
        status, data = self._post_json("/api/companies", payload, cookie=cookie)
        self.assertEqual(status, 201)
        self.assertTrue(data.get("success"))
        comp = data.get("company", {})
        self.assertIn("isVerified", comp)
        self.assertIs(comp["isVerified"], False, "Registered company must have isVerified: False in response")
        self.assertEqual(comp["name"], payload["name"])

    def test_database_direct_check_is_verified_zero_and_schema_default(self):
        """Тест 2: Прямая проверка БД (SELECT is_verified FROM companies WHERE id = ?) подтверждает 0."""
        _, cookie = self._login()
        payload = {
            "name": "Автономный Тест Базы Данных",
            "description": "Проверка записи 0 в колонку is_verified SQLite.",
            "specialization": "Аудит баз данных",
            "website": "db-test.example.com"
        }
        status, data = self._post_json("/api/companies", payload, cookie=cookie)
        self.assertEqual(status, 201)
        comp_id = data["company"]["id"]

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT id, name, is_verified FROM companies WHERE id = ?", (comp_id,))
            row = cur.fetchone()
            self.assertIsNotNone(row, "Created company should exist in SQLite database")
            self.assertEqual(row["is_verified"], 0, "SQLite column is_verified must be 0 for newly created company")

            # Check schema DDL default value
            cur.execute("PRAGMA table_info(companies);")
            cols = cur.fetchall()
            is_verified_col = next((c for c in cols if c["name"] == "is_verified"), None)
            self.assertIsNotNone(is_verified_col, "Column is_verified must exist in companies table")
            self.assertIn(str(is_verified_col["dflt_value"]).strip(), ("0", "0.0", "DEFAULT 0"),
                          "Default value for is_verified must be 0")

            # Verify that omitting is_verified during direct SQL INSERT applies default 0
            cur.execute("""
                INSERT INTO companies (id, name, description, specialization, website, logo, directions, owner_id, created_at, updated_at)
                VALUES ('direct-default-test', 'Дефолтная Компания', 'Проверка DEFAULT 0', 'Тестирование', '', '', '[]', 'user_demo', '2026-09-29T12:00:00Z', '2026-09-29T12:00:00Z')
            """)
            cur.execute("SELECT is_verified FROM companies WHERE id = 'direct-default-test'")
            default_row = cur.fetchone()
            self.assertEqual(default_row["is_verified"], 0, "Default value upon insertion without column must be 0")

    def test_get_companies_and_detail_return_is_verified_false(self):
        """Тест 3: GET /api/companies и GET /api/companies/<new_id> возвращают 'isVerified': False."""
        _, cookie = self._login()
        payload = {
            "name": "Компания Для Проверки GET",
            "description": "Проверка эндпоинтов списка и карточки компании.",
            "specialization": "API валидация",
            "website": "get-test.example.com"
        }
        status, data = self._post_json("/api/companies", payload, cookie=cookie)
        self.assertEqual(status, 201)
        created_id = data["company"]["id"]

        # 1. Detail endpoint GET /api/companies/<id>
        detail_status, detail_data = self._get_json(f"/api/companies/{created_id}")
        self.assertEqual(detail_status, 200)
        self.assertTrue(detail_data.get("success"))
        comp_detail = detail_data.get("company", {})
        self.assertIn("isVerified", comp_detail)
        self.assertIs(comp_detail["isVerified"], False, "GET /api/companies/<id> must return isVerified: False")

        # 2. List endpoint GET /api/companies
        list_status, list_data = self._get_json("/api/companies")
        self.assertEqual(list_status, 200)
        self.assertTrue(list_data.get("success"))
        companies = list_data.get("companies", [])
        matched = [c for c in companies if c["id"] == created_id]
        self.assertEqual(len(matched), 1, "Created company must be found in GET /api/companies list")
        self.assertIs(matched[0]["isVerified"], False, "GET /api/companies item must have isVerified: False")

    def test_seed_companies_verification_statuses(self):
        """Тест 4: Проверка сид-компаний: верифицированная smarttech-innovations возвращает True, неверифицированная cyberinfra-tech возвращает False."""
        # 1. Check via API GET /api/companies/<id>
        # smarttech-innovations (verified: True)
        status, data = self._get_json("/api/companies/smarttech-innovations")
        self.assertEqual(status, 200)
        self.assertIs(data["company"]["isVerified"], True, "smarttech-innovations must be verified (isVerified: True)")

        # fintech-ledgers (verified: True)
        status, data = self._get_json("/api/companies/fintech-ledgers")
        self.assertEqual(status, 200)
        self.assertIs(data["company"]["isVerified"], True, "fintech-ledgers must be verified (isVerified: True)")

        # cyberinfra-tech (unverified: False)
        status, data = self._get_json("/api/companies/cyberinfra-tech")
        self.assertEqual(status, 200)
        self.assertIs(data["company"]["isVerified"], False, "cyberinfra-tech must be unverified (isVerified: False)")

        # 2. Check directly in DB
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        with conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, is_verified FROM companies
                WHERE id IN ('smarttech-innovations', 'cryptosolutions-lab', 'cyberinfra-tech', 'fintech-ledgers', 'blockchain-audit-lab')
            """)
            rows = {r["id"]: r["is_verified"] for r in cur.fetchall()}

            self.assertEqual(rows.get("smarttech-innovations"), 1)
            self.assertEqual(rows.get("cryptosolutions-lab"), 1)
            self.assertEqual(rows.get("cyberinfra-tech"), 0)
            self.assertEqual(rows.get("fintech-ledgers"), 1)
            self.assertEqual(rows.get("blockchain-audit-lab"), 1)

    def test_frontend_markup_verified_icon_only_when_verified(self):
        """Тест 5: Проверка соответствия разметки frontend: бейдж 'verified-icon' отображается только при comp.isVerified === true."""
        # 1. Check card list rendering logic in feed.js
        card_verified_match = re.search(
            r"const\s+verifiedIcon\s*=\s*comp\.isVerified\s*\?\s*['\"](<span class=[\'\"]verified-icon[\'\"].*?</span>)['\"]\s*:\s*['\"]['\"];",
            self.feed_js,
            re.DOTALL
        )
        self.assertIsNotNone(card_verified_match, "feed.js must conditionally build verifiedIcon based on comp.isVerified")
        badge_html = card_verified_match.group(1)
        self.assertIn("verified-icon", badge_html)
        self.assertIn("Верифицированная компания", badge_html)

        # 2. Check detail view rendering logic in feed.js
        detail_matches = re.findall(
            r"const\s+verifiedIcon\s*=\s*comp\.isVerified\s*\?\s*(['\"].*?verified-icon.*?['\"])\s*:\s*['\"]['\"];",
            self.feed_js,
            re.DOTALL
        )
        self.assertGreaterEqual(len(detail_matches), 1, "feed.js must conditionally assign verifiedIcon in detail view")

        # 3. Simulate client-side card generation with verified vs unverified companies
        def simulate_feed_card_markup(comp):
            verified_icon = (
                '<span class="verified-icon" title="Верифицированная компания">'
                '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">'
                '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline>'
                '</svg></span>'
            ) if comp.get("isVerified") else ''
            return f'<div class="entity-card-title">{comp.get("name", "")} {verified_icon}</div>'

        unverified_comp = {"id": "new-test-corp", "name": "Тестовая Корпорация", "isVerified": False}
        unverified_markup = simulate_feed_card_markup(unverified_comp)
        self.assertNotIn("verified-icon", unverified_markup, "Unverified company markup must NOT contain verified-icon")
        self.assertNotIn("Верифицированная компания", unverified_markup)

        verified_comp = {"id": "smarttech-innovations", "name": "ООО «СмартТех Инновации»", "isVerified": True}
        verified_markup = simulate_feed_card_markup(verified_comp)
        self.assertIn("verified-icon", verified_markup, "Verified company markup MUST contain verified-icon")
        self.assertIn("Верифицированная компания", verified_markup)


if __name__ == "__main__":
    unittest.main()
