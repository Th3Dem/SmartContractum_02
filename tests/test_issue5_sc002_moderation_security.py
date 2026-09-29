#!/usr/bin/env python3
"""
tests/test_issue5_sc002_moderation_security.py

Regression & Security test suite for Issue #5 (SC-002):
«Закрыть доступ к очереди модерации и исключить подмену авторства».

Acceptance Criteria / Test Cases:
- Тест 1: GET /api/moderation/list возвращает 401 для неавторизованного гостя.
- Тест 2: GET /api/moderation/list возвращает 403 для обычного пользователя (role="user").
- Тест 3: GET /api/moderation/list возвращает 200 для модератора (role="moderator") и администратора (role="admin").
- Тест 4: POST /api/moderation/submit возвращает 401 для неавторизованного гостя.
- Тест 5: POST /api/moderation/submit от авторизованной Алисы с payload authorId: 'bob' сохраняет заявку строго с author_id == 'alice'.
- Тест 6: GET /api/moderation/status возвращает 401 для гостя.
- Тест 7: GET /api/moderation/status возвращает 200 для автора заявки.
- Тест 8: GET /api/moderation/status возвращает 403 для стороннего обычного пользователя.
- Тест 9: GET /api/moderation/status возвращает 200 для модератора/администратора для любого черновика.
"""

import datetime
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

import server
from server import create_server, init_db

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")


class TestIssue5SC002ModerationSecurity(unittest.TestCase):
    """Test suite for Issue #5 (SC-002) Moderation Access Control and Identity Spoofing Protection."""

    @classmethod
    def setUpClass(cls):
        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_issue5_sc002.db")
        server.DEFAULT_DB_PATH = cls.db_path

        conn = init_db(cls.db_path)
        conn.close()

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
        cls.server_thread.join(timeout=2)
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def _login(self, user_id: str, name: str = "Test User", role: str = "user"):
        payload = {"userId": user_id, "name": name, "role": role}
        status, data, cookie = self._post_json("/api/auth/login", payload)
        self.assertEqual(status, 200)
        self.assertTrue(data.get("authenticated"))
        self.assertEqual(data.get("user", {}).get("role"), role)
        return data, cookie

    def _get_json(self, path: str, cookie: str = None, headers: dict = None):
        h = {}
        if headers:
            h.update(headers)
        if cookie:
            h["Cookie"] = cookie
        req = urllib.request.Request(f"{self.base_url}{path}", headers=h)
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return resp.status, data, resp.headers.get("Set-Cookie")
        except urllib.error.HTTPError as e:
            try:
                data = json.loads(e.read().decode("utf-8"))
            except Exception:
                data = {"error": str(e)}
            e.close()
            return e.code, data, e.headers.get("Set-Cookie")

    def _post_json(self, path: str, payload: dict, cookie: str = None, headers: dict = None):
        h = {"Content-Type": "application/json"}
        if headers:
            h.update(headers)
        if cookie:
            h["Cookie"] = cookie
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers=h,
            method="POST"
        )
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return resp.status, data, resp.headers.get("Set-Cookie")
        except urllib.error.HTTPError as e:
            try:
                data = json.loads(e.read().decode("utf-8"))
            except Exception:
                data = {"error": str(e)}
            e.close()
            return e.code, data, e.headers.get("Set-Cookie")

    def _sample_payload(self, draft_id: str, idempotency_key: str, title: str = "Тестовая статья для проверки безопасности"):
        return {
            "draftId": draft_id,
            "title": title,
            "html": "<p>Содержимое статьи для проверки ограничений доступа к модерации и защите авторства.</p>",
            "delta": {"ops": [{"insert": "Содержимое статьи..."}]},
            "publicationSettings": {
                "author": "Тестовый автор",
                "authorRole": "Разработчик",
                "targetAudience": "developers",
                "topics": ["pksc-architecture"],
                "keywords": ["security", "moderation"],
                "format": "article",
                "complexity": "medium",
                "description": "Описание тестовой статьи длиной более пятидесяти символов для проверки валидации."
            },
            "idempotencyKey": idempotency_key
        }

    def test_01_moderation_list_guest_returns_401(self):
        """Тест 1: GET /api/moderation/list возвращает 401 для неавторизованного гостя."""
        status, data, _ = self._get_json("/api/moderation/list")
        self.assertEqual(status, 401)
        self.assertFalse(data.get("success"))
        self.assertTrue(data.get("requireAuth"))
        self.assertIn("авторизация", data.get("error", "").lower())

    def test_02_moderation_list_regular_user_returns_403(self):
        """Тест 2: GET /api/moderation/list возвращает 403 для обычного пользователя (role="user")."""
        _, cookie_user = self._login("user_regular_01", "Обычный Пользователь", role="user")
        status, data, _ = self._get_json("/api/moderation/list", cookie=cookie_user)
        self.assertEqual(status, 403)
        self.assertFalse(data.get("success"))
        self.assertIn("Доступ запрещен", data.get("error", ""))

    def test_03_moderation_list_moderator_and_admin_returns_200(self):
        """Тест 3: GET /api/moderation/list возвращает 200 для модератора (role="moderator") и админа."""
        # 1. Moderator
        _, cookie_mod = self._login("user_moderator_01", "Модератор", role="moderator")
        status, data, _ = self._get_json("/api/moderation/list", cookie=cookie_mod)
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        self.assertIsInstance(data.get("submissions"), list)

        # 2. Admin
        _, cookie_adm = self._login("user_admin_01", "Администратор", role="admin")
        status_adm, data_adm, _ = self._get_json("/api/moderation/list", cookie=cookie_adm)
        self.assertEqual(status_adm, 200)
        self.assertTrue(data_adm.get("success"))
        self.assertIsInstance(data_adm.get("submissions"), list)

    def test_04_moderation_submit_guest_returns_401(self):
        """Тест 4: POST /api/moderation/submit возвращает 401 для неавторизованного гостя."""
        payload = self._sample_payload("draft_guest_submit", "idemp_guest_01")
        status, data, _ = self._post_json("/api/moderation/submit", payload)
        self.assertEqual(status, 401)
        self.assertFalse(data.get("success"))
        self.assertTrue(data.get("requireAuth"))
        self.assertIn("авторизация", data.get("error", "").lower())

    def test_05_moderation_submit_prevents_author_spoofing(self):
        """Тест 5: POST /api/moderation/submit от авторизованной Алисы с payload authorId: 'bob' сохраняет заявку строго с author_id == 'alice'."""
        _, cookie_alice = self._login("alice", "Алиса Смит", role="user")
        payload = self._sample_payload("draft_alice_submit", "idemp_alice_spoof_bob")
        # Attempt to spoof authorId in payload
        payload["authorId"] = "bob"
        payload["author_id"] = "bob"

        status, data, _ = self._post_json("/api/moderation/submit", payload, cookie=cookie_alice)
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        sub_id = data.get("submissionId")
        self.assertIsNotNone(sub_id)

        # Verify database record: author_id must strictly be 'alice'
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM moderation_submissions WHERE id = ?", (sub_id,))
                row = cur.fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row["author_id"], "alice")
                self.assertNotEqual(row["author_id"], "bob")
        finally:
            conn.close()

    def test_06_moderation_status_guest_returns_401(self):
        """Тест 6: GET /api/moderation/status возвращает 401 для гостя."""
        status, data, _ = self._get_json("/api/moderation/status?draftId=draft_alice_submit")
        self.assertEqual(status, 401)
        self.assertFalse(data.get("success"))
        self.assertTrue(data.get("requireAuth"))

    def test_07_moderation_status_author_returns_200(self):
        """Тест 7: GET /api/moderation/status возвращает 200 для автора заявки."""
        _, cookie_charlie = self._login("charlie", "Чарли Браун", role="user")
        payload = self._sample_payload("draft_charlie_01", "idemp_charlie_01")
        submit_status, submit_data, _ = self._post_json("/api/moderation/submit", payload, cookie=cookie_charlie)
        self.assertEqual(submit_status, 200)

        # Charlie checks his own draft status
        status, data, _ = self._get_json("/api/moderation/status?draftId=draft_charlie_01", cookie=cookie_charlie)
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("status"), "pending_moderation")
        self.assertEqual(data.get("submissionId"), submit_data.get("submissionId"))

    def test_08_moderation_status_other_regular_user_returns_403(self):
        """Тест 8: GET /api/moderation/status возвращает 403 для стороннего обычного пользователя."""
        # Charlie submitted draft_charlie_01 in test_07 (or create new)
        _, cookie_charlie = self._login("charlie_iso", "Чарли Изолированный", role="user")
        payload = self._sample_payload("draft_charlie_iso_01", "idemp_charlie_iso_01")
        self._post_json("/api/moderation/submit", payload, cookie=cookie_charlie)

        # Dave is another regular user
        _, cookie_dave = self._login("dave", "Дейв Смит", role="user")
        status, data, _ = self._get_json("/api/moderation/status?draftId=draft_charlie_iso_01", cookie=cookie_dave)
        self.assertEqual(status, 403)
        self.assertFalse(data.get("success"))
        self.assertIn("Доступ запрещен", data.get("error", ""))

    def test_09_moderation_status_moderator_and_admin_returns_200(self):
        """Тест 9: GET /api/moderation/status возвращает 200 для модератора/администратора для любого черновика."""
        # Charlie's draft
        _, cookie_charlie = self._login("charlie_mod_check", "Чарли Автор", role="user")
        payload = self._sample_payload("draft_charlie_for_mod", "idemp_charlie_for_mod")
        self._post_json("/api/moderation/submit", payload, cookie=cookie_charlie)

        # 1. Moderator can view status
        _, cookie_mod = self._login("eve_mod", "Ева Модератор", role="moderator")
        status_mod, data_mod, _ = self._get_json("/api/moderation/status?draftId=draft_charlie_for_mod", cookie=cookie_mod)
        self.assertEqual(status_mod, 200)
        self.assertTrue(data_mod.get("success"))
        self.assertEqual(data_mod.get("status"), "pending_moderation")

        # 2. Administrator can view status
        _, cookie_adm = self._login("frank_adm", "Франк Админ", role="admin")
        status_adm, data_adm, _ = self._get_json("/api/moderation/status?draftId=draft_charlie_for_mod", cookie=cookie_adm)
        self.assertEqual(status_adm, 200)
        self.assertTrue(data_adm.get("success"))
        self.assertEqual(data_adm.get("status"), "pending_moderation")


if __name__ == "__main__":
    unittest.main()
