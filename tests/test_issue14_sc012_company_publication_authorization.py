#!/usr/bin/env python3
"""
tests/test_issue14_sc012_company_publication_authorization.py

Comprehensive regression test suite for Issue #14 (SC-012):
"Проверка полномочий пользователя на публикацию от имени компании".

Acceptance Criteria:
1. Публикация без привязки к компании отправляется успешно (200 OK).
2. Публикация от имени компании ее владельцем завершается успешно (200 OK).
3. Публикация от имени компании зарегистрированным участником (company_members) завершается успешно (200 OK).
4. Попытка публикации от имени чужой компании пользователем без прав отклоняется с кодом 403 Forbidden
   и сообщением fieldErrors["companyId"]: "Вы не являетесь владельцем или участником этой компании.".
5. Попытка публикации с несуществующим companyId отклоняется с кодом 400 Bad Request.
6. Функция update_submission_status при попытке перевода в approved заявки с несанкционированной
   компанией отклоняет смену статуса (возвращает False).
7. Эндпоинт GET /api/companies возвращает атрибут canPublish и корректно фильтрует список при ?manageable=1 / ?mine=1.
8. Все базовые тесты проекта продолжают проходить со 100% успехом.
"""

import json
import os
import shutil
import sqlite3
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from typing import Optional, Tuple

import server
from server import (
    can_user_publish_for_company,
    create_server,
    init_db,
    update_submission_status,
)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue14SC012CompanyPublicationAuthorization(unittest.TestCase):
    """Test suite for Issue #14 (SC-012) company publication authorization."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue14_sc012.db")
        server.DEFAULT_DB_PATH = cls.db_path

        # Initialize DB with schema and seed data
        conn = init_db(cls.db_path)
        conn.close()

        # Start dynamic HTTP server
        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR)
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.httpd.shutdown()
            cls.httpd.server_close()
        except Exception:
            pass
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def _login(self, user_id: str, name: str = "Test User", role: str = "user") -> str:
        url = f"{self.base_url}/api/auth/login"
        body = json.dumps({"userId": user_id, "name": name, "role": role}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST"
        )
        with urllib.request.urlopen(req) as resp:
            return resp.headers.get("Set-Cookie")

    def _post_json(self, path: str, data: dict, cookie: Optional[str] = None) -> Tuple[int, dict]:
        url = f"{self.base_url}{path}"
        body = json.dumps(data).encode("utf-8")
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if cookie:
            headers["Cookie"] = cookie
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                res_body = resp.read().decode("utf-8")
                return resp.status, json.loads(res_body) if res_body else {}
        except urllib.error.HTTPError as e:
            res_body = e.read().decode("utf-8")
            return e.code, json.loads(res_body) if res_body else {}

    def _get_json(self, path: str, cookie: Optional[str] = None) -> Tuple[int, dict]:
        url = f"{self.base_url}{path}"
        headers = {}
        if cookie:
            headers["Cookie"] = cookie
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req) as resp:
                res_body = resp.read().decode("utf-8")
                return resp.status, json.loads(res_body) if res_body else {}
        except urllib.error.HTTPError as e:
            res_body = e.read().decode("utf-8")
            return e.code, json.loads(res_body) if res_body else {}

    def _get_valid_payload(self, draft_id: str, company_id: Optional[str] = None) -> dict:
        settings = {
            "targetAudience": "all",
            "topics": ["security", "backend"],
            "keywords": ["authorization", "company"],
            "description": "Подробное архитектурное описание механизмов разграничения прав доступа при публикации от имени компаний.",
            "format": "tutorial",
            "complexity": "medium"
        }
        if company_id is not None:
            settings["companyId"] = company_id

        return {
            "draftId": draft_id,
            "title": f"Тестовая статья для проверки прав компании {draft_id}",
            "html": "<p>Содержимое тестовой статьи с валидным текстом и проверкой полномочий автора.</p>",
            "publicationSettings": settings
        }

    # =========================================================================
    # 1. Pure Unit Tests for can_user_publish_for_company helper
    # =========================================================================

    def test_can_user_publish_for_company_unit_logic(self):
        """Unit test for can_user_publish_for_company helper rules."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            # Setup a dedicated test company and member
            now = "2026-09-29T12:00:00Z"
            conn.execute(
                "INSERT OR REPLACE INTO companies (id, name, description, specialization, owner_id, created_at, updated_at) "
                "VALUES ('test-comp-unit', 'Unit Test Co', 'Desc', 'Fintech', 'owner_unit_user', ?, ?)",
                (now, now)
            )
            conn.execute(
                "INSERT OR REPLACE INTO company_members (company_id, user_id, role, created_at) "
                "VALUES ('test-comp-unit', 'editor_unit_user', 'editor', ?)",
                (now,)
            )
            conn.execute(
                "INSERT OR REPLACE INTO company_members (company_id, user_id, role, created_at) "
                "VALUES ('test-comp-unit', 'guest_unit_user', 'guest', ?)",
                (now,)
            )
            conn.commit()

            # Rule 1: Admin can publish for any company
            self.assertTrue(can_user_publish_for_company(conn, "any_admin", "test-comp-unit", user_role="admin"))
            self.assertTrue(can_user_publish_for_company(conn, "any_admin", "some_other_co", user_role="admin"))

            # Rule 2: Empty or None company_id returns False
            self.assertFalse(can_user_publish_for_company(conn, "owner_unit_user", None, user_role="user"))
            self.assertFalse(can_user_publish_for_company(conn, "owner_unit_user", "", user_role="user"))

            # Rule 3: Non-existent company returns False for non-admin
            self.assertFalse(can_user_publish_for_company(conn, "owner_unit_user", "non_existent_comp_xyz", user_role="user"))

            # Rule 4: Empty user_id returns False
            self.assertFalse(can_user_publish_for_company(conn, None, "test-comp-unit", user_role="user"))
            self.assertFalse(can_user_publish_for_company(conn, "", "test-comp-unit", user_role="user"))

            # Rule 5: Owner returns True
            self.assertTrue(can_user_publish_for_company(conn, "owner_unit_user", "test-comp-unit", user_role="user"))

            # Rule 6: Members with allowed roles ('owner', 'admin', 'editor', 'author', 'member') return True
            for role in ("owner", "admin", "editor", "author", "member"):
                conn.execute(
                    "INSERT OR REPLACE INTO company_members (company_id, user_id, role, created_at) VALUES ('test-comp-unit', 'test_role_user', ?, ?)",
                    (role, now)
                )
                conn.commit()
                self.assertTrue(
                    can_user_publish_for_company(conn, "test_role_user", "test-comp-unit", user_role="user"),
                    f"Role '{role}' should be authorized to publish"
                )

            # Disallowed member roles (e.g. 'guest', 'viewer') return False
            self.assertFalse(can_user_publish_for_company(conn, "guest_unit_user", "test-comp-unit", user_role="user"))

            # Non-member returns False
            self.assertFalse(can_user_publish_for_company(conn, "stranger_user", "test-comp-unit", user_role="user"))
        finally:
            conn.close()

    # =========================================================================
    # 2. POST /api/companies adds creator to company_members
    # =========================================================================

    def test_post_company_registers_owner_in_company_members(self):
        """Creating a new company automatically inserts owner into company_members with role 'owner'."""
        cookie = self._login("comp_founder_1", "Основатель Компании", role="user")
        payload = {
            "name": f"Компания Основателя {int(time.time())}",
            "description": "Описание тестовой создаваемой компании для проверки членства.",
            "specialization": "Блокчейн решения",
            "website": "https://founder-test.io"
        }
        status, data = self._post_json("/api/companies", payload, cookie=cookie)
        self.assertEqual(status, 201)
        self.assertTrue(data["success"])
        self.assertIn("company", data)
        created_id = data["company"]["id"]
        self.assertTrue(data["company"]["canPublish"])

        # Check DB directly
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT role FROM company_members WHERE company_id = ? AND user_id = ?",
                (created_id, "comp_founder_1")
            )
            row = cur.fetchone()
            self.assertIsNotNone(row, "Owner must be registered in company_members")
            self.assertEqual(row["role"], "owner")
        finally:
            conn.close()

    # =========================================================================
    # 3. Submission tests: acceptance criteria 1, 2, 3, 4, 5
    # =========================================================================

    def test_ac1_submission_without_company_succeeds(self):
        """Acceptance Criteria 1: Публикация без привязки к компании отправляется успешно."""
        cookie = self._login("author_personal", "Личный Автор", role="user")
        payload = self._get_valid_payload("draft_ac1_personal", company_id=None)

        status, data = self._post_json("/api/moderation/submit", payload, cookie=cookie)
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])
        self.assertEqual(data["status"], "pending_moderation")
        self.assertIn("submissionId", data)

    def test_ac2_submission_by_company_owner_succeeds(self):
        """Acceptance Criteria 2: Публикация от имени компании ее владельцем завершается успешно."""
        # Create company
        cookie_owner = self._login("owner_ac2", "Владелец Компании", role="user")
        comp_payload = {
            "name": f"Тест Компании АС2 {int(time.time())}",
            "description": "Компания для проверки успешной публикации владельцем.",
            "specialization": "Fintech"
        }
        status_c, data_c = self._post_json("/api/companies", comp_payload, cookie=cookie_owner)
        self.assertEqual(status_c, 201)
        company_id = data_c["company"]["id"]

        # Submit article under company
        payload = self._get_valid_payload("draft_ac2_owner", company_id=company_id)
        status, data = self._post_json("/api/moderation/submit", payload, cookie=cookie_owner)
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])
        self.assertEqual(data["status"], "pending_moderation")

    def test_ac3_submission_by_company_member_succeeds(self):
        """Acceptance Criteria 3: Публикация от имени компании зарегистрированным участником (company_members) завершается успешно."""
        # 1. Create company by owner
        cookie_owner = self._login("owner_ac3", "Владелец АС3", role="user")
        comp_payload = {
            "name": f"Тест Компании АС3 {int(time.time())}",
            "description": "Компания для проверки публикации участником.",
            "specialization": "Инженерия"
        }
        status_c, data_c = self._post_json("/api/companies", comp_payload, cookie=cookie_owner)
        self.assertEqual(status_c, 201)
        company_id = data_c["company"]["id"]

        # 2. Add an editor/author to company_members in DB
        member_id = "editor_ac3"
        conn = sqlite3.connect(self.db_path)
        try:
            now_str = "2026-09-29T12:00:00Z"
            conn.execute(
                "INSERT INTO company_members (company_id, user_id, role, created_at) VALUES (?, ?, 'author', ?)",
                (company_id, member_id, now_str)
            )
            conn.commit()
        finally:
            conn.close()

        # 3. Submit article as the member
        cookie_member = self._login(member_id, "Автор Участник", role="user")
        payload = self._get_valid_payload("draft_ac3_member", company_id=company_id)
        status, data = self._post_json("/api/moderation/submit", payload, cookie=cookie_member)
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])
        self.assertEqual(data["status"], "pending_moderation")

    def test_ac4_submission_by_unauthorized_user_rejected_403(self):
        """Acceptance Criteria 4: Попытка публикации от имени чужой компании пользователем без прав отклоняется с кодом 403 Forbidden."""
        # 1. Company owned by owner_ac4
        cookie_owner = self._login("owner_ac4", "Владелец АС4", role="user")
        comp_payload = {
            "name": f"Компания АС4 Чужая {int(time.time())}",
            "description": "Чужая компания для проверки запрета публикации.",
            "specialization": "Security"
        }
        status_c, data_c = self._post_json("/api/companies", comp_payload, cookie=cookie_owner)
        self.assertEqual(status_c, 201)
        company_id = data_c["company"]["id"]

        # 2. Stranger tries to publish under company_id
        cookie_stranger = self._login("stranger_ac4", "Чужой Пользователь", role="user")
        payload = self._get_valid_payload("draft_ac4_forbidden", company_id=company_id)
        status, data = self._post_json("/api/moderation/submit", payload, cookie=cookie_stranger)

        self.assertEqual(status, 403)
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "Отказано в доступе: у вас нет прав на публикацию от имени выбранной компании.")
        self.assertIn("fieldErrors", data)
        self.assertEqual(data["fieldErrors"].get("companyId"), "Вы не являетесь владельцем или участником этой компании.")

    def test_ac5_submission_with_non_existent_company_rejected_400(self):
        """Acceptance Criteria 5: Попытка публикации с несуществующим companyId отклоняется с кодом 400 Bad Request."""
        cookie = self._login("author_ac5", "Автор АС5", role="user")
        payload = self._get_valid_payload("draft_ac5_non_existent", company_id="non-existent-company-404")

        status, data = self._post_json("/api/moderation/submit", payload, cookie=cookie)
        self.assertEqual(status, 400)
        self.assertFalse(data["success"])
        self.assertIn("fieldErrors", data)
        self.assertIn("companyId", data["fieldErrors"])

    def test_admin_can_publish_for_any_existing_company(self):
        """System administrator can publish on behalf of any existing company."""
        # 1. Company owned by owner_ac_admin
        cookie_owner = self._login("owner_for_admin", "Обычный Владелец", role="user")
        comp_payload = {
            "name": f"Компания Для Админа {int(time.time())}",
            "description": "Компания для проверки прав администратора.",
            "specialization": "DevOps"
        }
        status_c, data_c = self._post_json("/api/companies", comp_payload, cookie=cookie_owner)
        self.assertEqual(status_c, 201)
        company_id = data_c["company"]["id"]

        # 2. Admin submits article under company
        cookie_admin = self._login("admin_sys", "Системный Администратор", role="admin")
        payload = self._get_valid_payload("draft_admin_pub", company_id=company_id)
        status, data = self._post_json("/api/moderation/submit", payload, cookie=cookie_admin)
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])

    # =========================================================================
    # 4. update_submission_status: acceptance criteria 6
    # =========================================================================

    def test_ac6_update_submission_status_rejects_unauthorized_company_approval(self):
        """Acceptance Criteria 6: update_submission_status при попытке перевода в approved заявки с несанкционированной компанией отклоняет смену статуса."""
        conn = sqlite3.connect(self.db_path)
        try:
            now = "2026-09-29T13:00:00Z"
            # 1. Create company owned by someone else
            conn.execute(
                "INSERT OR REPLACE INTO companies (id, name, description, specialization, owner_id, created_at, updated_at) "
                "VALUES ('comp-mod-check', 'Mod Check Co', 'Desc', 'AI', 'real_owner_user', ?, ?)",
                (now, now)
            )

            # 2. Insert a submission authored by unauthorized_user with comp-mod-check
            sub_id = "sub_unauth_mod_test"
            settings_json = json.dumps({
                "targetAudience": "all",
                "topics": ["security"],
                "keywords": ["audit"],
                "description": "Статья несанкционированного автора для проверки блокировки модератором.",
                "companyId": "comp-mod-check"
            })
            conn.execute("""
                INSERT OR REPLACE INTO moderation_submissions (
                    id, draft_id, title, author_id, status, publication_settings,
                    article_html, snapshot_hash, created_at, updated_at
                ) VALUES (?, 'draft_unauth_mod', 'Title', 'unauthorized_user', 'pending_moderation', ?, '<p>Body text</p>', 'dummyhash', ?, ?)
            """, (sub_id, settings_json, now, now))
            conn.commit()
        finally:
            conn.close()

        # Attempt to approve the submission -> must be REJECTED (False)
        result = update_submission_status(sub_id, "approved", self.db_path)
        self.assertFalse(result, "Approving submission with unauthorized companyId must return False")

        # Verify status remained unchanged in DB
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            cur.execute("SELECT status FROM moderation_submissions WHERE id = ?", (sub_id,))
            row = cur.fetchone()
            self.assertEqual(row["status"], "pending_moderation")
        finally:
            conn.close()

        # Now authorize the user in company_members and verify approval succeeds
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "INSERT OR REPLACE INTO company_members (company_id, user_id, role, created_at) VALUES ('comp-mod-check', 'unauthorized_user', 'member', ?)",
                ("2026-09-29T13:05:00Z",)
            )
            conn.commit()
        finally:
            conn.close()

        result_authorized = update_submission_status(sub_id, "approved", self.db_path)
        self.assertTrue(result_authorized, "Approving submission once user is a valid member must return True")

    # =========================================================================
    # 5. GET /api/companies: acceptance criteria 7
    # =========================================================================

    def test_ac7_get_companies_returns_can_publish_and_filters_manageable(self):
        """Acceptance Criteria 7: GET /api/companies возвращает атрибут canPublish и корректно фильтрует список при ?manageable=1."""
        # 1. Create a company owned by user_author_filter
        cookie = self._login("user_author_filter", "Фильтр Автор", role="user")
        comp_name = f"Управляемая Компания {int(time.time())}"
        payload = {
            "name": comp_name,
            "description": "Описание управляемой компании для тестирования фильтра.",
            "specialization": "Security"
        }
        status_c, data_c = self._post_json("/api/companies", payload, cookie=cookie)
        self.assertEqual(status_c, 201)
        my_comp_id = data_c["company"]["id"]

        # 2. Call GET /api/companies (without filter)
        status, data = self._get_json("/api/companies", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])
        companies = data["companies"]
        self.assertGreater(len(companies), 1, "There should be seed companies plus newly created one")

        # Each company item must have canPublish: bool
        my_comp = None
        for comp in companies:
            self.assertIn("canPublish", comp, "Each company item must contain canPublish attribute")
            self.assertIsInstance(comp["canPublish"], bool)
            if comp["id"] == my_comp_id:
                my_comp = comp

        self.assertIsNotNone(my_comp)
        self.assertTrue(my_comp["canPublish"])

        # 3. Call GET /api/companies?manageable=1 with author's cookie
        status_m, data_m = self._get_json("/api/companies?manageable=1", cookie=cookie)
        self.assertEqual(status_m, 200)
        self.assertTrue(data_m["success"])
        manageable_comps = data_m["companies"]

        # All returned companies must have canPublish: True
        self.assertTrue(all(c["canPublish"] is True for c in manageable_comps))
        # My company must be in the list
        self.assertTrue(any(c["id"] == my_comp_id for c in manageable_comps))
        # Unauthorized companies must NOT be in the manageable list
        self.assertLess(len(manageable_comps), len(companies))

        # 4. Call GET /api/companies?mine=1 also works as synonym
        status_mine, data_mine = self._get_json("/api/companies?mine=1", cookie=cookie)
        self.assertEqual(status_mine, 200)
        self.assertEqual(len(data_mine["companies"]), len(manageable_comps))

        # 5. Call GET /api/companies?manageable=1 with a user having 0 companies
        cookie_nobody = self._login("nobody_user", "Пользователь Без Компаний", role="user")
        status_none, data_none = self._get_json("/api/companies?manageable=1", cookie=cookie_nobody)
        self.assertEqual(status_none, 200)
        self.assertEqual(data_none["companies"], [])

    # =========================================================================
    # 6. Frontend contract test: publication.js fetches /api/companies?manageable=1
    # =========================================================================

    def test_frontend_publication_js_contract(self):
        """Frontend publication.js initEntityOptions must query /api/companies?manageable=1."""
        pub_js_path = os.path.join(FRONTEND_DIR, "js", "publication.js")
        with open(pub_js_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn(
            "fetch('/api/companies?manageable=1')",
            content,
            "publication.js must fetch /api/companies?manageable=1 in initEntityOptions"
        )


if __name__ == "__main__":
    unittest.main()
