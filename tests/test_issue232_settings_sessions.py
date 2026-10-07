"""
Account settings page (Issue #232): extended settings payload and the list of signed-in devices.
"""
import os
import shutil
import sqlite3
import tempfile
import threading
import unittest

from server import create_server, create_user, init_db, reset_login_rate_limiter
from tests.http_client import Client

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PASSWORD = "Settings-pass-12"


class TestSettingsAndSessions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "settings.db")
        init_db(cls.db_path, seed=False).close()
        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        for login in ("dora", "eric"):
            create_user(conn, login, f"{login}@example.com", PASSWORD, email_verified=True)
        conn.close()
        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path,
                                  media_dir=os.path.join(cls.temp_dir, "media"),
                                  directory=os.path.join(PROJECT_ROOT, "frontend", "public"),
                                  allow_demo_login=False, enforce_csrf=True)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=2)
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self):
        reset_login_rate_limiter()

    def client(self, login):
        return Client(self.base).login(login, PASSWORD)

    def test_settings_payload_has_account_details(self):
        dora = self.client("dora")
        dora.request("POST", "/api/user/profile", {"name": "Дора", "specialization": "Аудит"})
        status, body = dora.request("GET", "/api/user/settings")
        self.assertEqual(status, 200)
        settings = body["settings"]
        self.assertEqual((settings["login"], settings["name"], settings["specialization"]), ("dora", "Дора", "Аудит"))
        self.assertEqual(settings["role"], "user")
        self.assertTrue(settings["createdAt"])
        self.assertTrue(settings["emailVerified"])
        self.assertTrue(settings["emailVerifiedAt"])
        self.assertIn("cover", settings)
        self.assertNotIn("password_hash", str(body))
        self.assertEqual(Client(self.base).request("GET", "/api/user/settings")[0], 401)

    def test_sessions_list_marks_current_device_and_hides_tokens(self):
        laptop = self.client("eric")
        phone = self.client("eric")
        status, body = laptop.request("GET", "/api/auth/sessions")
        self.assertEqual(status, 200)
        sessions = body["sessions"]
        self.assertGreaterEqual(len(sessions), 2)
        self.assertEqual(sum(1 for s in sessions if s["current"]), 1)
        self.assertTrue(all("Python-urllib" in s["userAgent"] for s in sessions), "the browser of each sign-in is stored")
        tokens = {c.value for c in laptop.jar if c.name == "sc_session"} | {c.value for c in phone.jar if c.name == "sc_session"}
        listed = str(body)
        for token in tokens:
            self.assertNotIn(token, listed, "session tokens never leave the server")
        self.assertEqual(Client(self.base).request("GET", "/api/auth/sessions")[0], 401)

    def test_ending_another_device_signs_it_out(self):
        laptop = self.client("eric")
        phone = self.client("eric")
        _, body = phone.request("GET", "/api/auth/sessions")
        phone_id = next(s["id"] for s in body["sessions"] if s["current"])
        status, result = laptop.request("POST", "/api/auth/sessions/revoke", {"id": phone_id})
        self.assertEqual((status, result["current"]), (200, False))
        self.assertFalse(phone.request("GET", "/api/auth/status")[1]["authenticated"])
        self.assertTrue(laptop.request("GET", "/api/auth/status")[1]["authenticated"])
        self.assertEqual(laptop.request("POST", "/api/auth/sessions/revoke", {"id": phone_id})[0], 404, "already ended")

    def test_ending_the_current_session_signs_out_here(self):
        laptop = self.client("eric")
        _, body = laptop.request("GET", "/api/auth/sessions")
        own_id = next(s["id"] for s in body["sessions"] if s["current"])
        status, result = laptop.request("POST", "/api/auth/sessions/revoke", {"id": own_id})
        self.assertEqual((status, result["current"]), (200, True))
        self.assertFalse(laptop.request("GET", "/api/auth/status")[1]["authenticated"])

    def test_someone_elses_session_cannot_be_ended(self):
        dora = self.client("dora")
        eric = self.client("eric")
        _, body = eric.request("GET", "/api/auth/sessions")
        eric_id = next(s["id"] for s in body["sessions"] if s["current"])
        for payload in ({"id": eric_id}, {"id": ""}, {}):
            self.assertEqual(dora.request("POST", "/api/auth/sessions/revoke", payload)[0], 404, payload)
        self.assertTrue(eric.request("GET", "/api/auth/status")[1]["authenticated"])
        self.assertEqual(Client(self.base).request("POST", "/api/auth/sessions/revoke", {"id": eric_id})[0], 401)


if __name__ == "__main__":
    unittest.main()
