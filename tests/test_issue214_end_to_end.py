"""
End-to-end acceptance of the account, editor, company and moderation work (Issue #214).

One scenario walks through the features in the order a real user meets them, on a server
started with the production settings (no demo login, CSRF enforced).
"""
import json
import os
import re
import shutil
import sqlite3
import struct
import tempfile
import threading
import unittest
import urllib.request
import zlib

from server import (
    EMAIL_SERVICE,
    create_admin,
    create_server,
    init_db,
    reset_login_rate_limiter,
    reset_media_upload_limiters,
    reset_recovery_rate_limiter,
    reset_registration_rate_limiter,
)
from tests.http_client import Client, submission_payload

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PASSWORD = "E2e-strong-pass-1"


def png(width, height, shade):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    row = b"\x00" + bytes([shade, 90, 160]) * width
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(row * height)) + chunk(b"IEND", b""))


class TestEndToEndAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "e2e.db")
        init_db(cls.db_path, seed=False).close()
        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        create_admin(conn, "chief", "chief@example.com", password=PASSWORD)
        conn.close()
        # Production settings: no demo login, CSRF tokens enforced
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
        for reset in (reset_login_rate_limiter, reset_registration_rate_limiter,
                      reset_recovery_rate_limiter, reset_media_upload_limiters):
            reset()
        EMAIL_SERVICE.clear_sent_emails()

    # helpers

    def code_for(self, address):
        mails = [m for m in EMAIL_SERVICE.get_sent_emails() if m["recipient"] == address]
        self.assertTrue(mails, f"no email to {address}")
        return re.findall(r"\b\d{6}\b", mails[-1]["body_text"])[0]

    def register(self, login):
        client = Client(self.base)
        email = f"{login}@example.com"
        status, body = client.request("POST", "/api/auth/register", {"login": login, "email": email, "password": PASSWORD})
        self.assertEqual(status, 201, body)
        status, _ = client.request("POST", "/api/auth/verify-email",
                                   {"email": email, "code": self.code_for(email), "registrationToken": body["registrationToken"]})
        self.assertEqual(status, 200)
        return client.login(login, PASSWORD)

    def upload(self, client, data):
        csrf = next(c.value for c in client.jar if c.name == "sc_csrf")
        req = urllib.request.Request(self.base + "/api/media/upload", data=data, method="POST",
                                     headers={"Content-Type": "image/png", "X-CSRF-Token": csrf})
        with client.opener.open(req, timeout=10) as resp:
            return json.loads(resp.read())["url"]

    # the scenario

    def test_full_journey(self):
        # 1. Registration with an emailed code; the session belongs to the new account
        author = self.register("anna_author")
        _, me = author.request("GET", "/api/auth/status")
        self.assertTrue(me["authenticated"])
        author_id = me["user"]["id"]

        # 2. The author creates a company and owns its profile
        status, created = author.request("POST", "/api/companies", {
            "name": "ООО «Сквозной Тест»", "description": "Проверяем все вместе",
            "specialization": "Аудит", "website": "e2e.example"})
        self.assertEqual(status, 201, created)
        company_id = created["company"]["id"]
        _, company = author.request("GET", f"/api/companies/{company_id}/profile")
        self.assertTrue(company["company"]["canEdit"])

        # 3. A server draft written on one device opens on another
        draft = {"id": "e2e-draft", "materialType": "publication", "title": "Черновик", "content": "Текст"}
        self.assertIn(author.request("POST", "/api/drafts", draft)[0], (200, 201))
        second_device = Client(self.base).login("anna_author", PASSWORD)
        _, drafts = second_device.request("GET", "/api/drafts")
        self.assertIn("e2e-draft", json.dumps(drafts))

        # 4. The author submits a publication on behalf of the company
        payload = submission_payload("e2e-draft", title="Сквозная проверка публикации")
        payload["publicationSettings"]["companyId"] = company_id
        status, submitted = author.request("POST", "/api/moderation/submit", payload)
        self.assertEqual(status, 200, submitted)
        submission_id = submitted["submissionId"]
        _, feed = Client(self.base).request("GET", "/api/articles?limit=50")
        self.assertNotIn(submission_id, json.dumps(feed), "not visible before moderation")

        # 5. The administrator appoints a moderator, who approves the material
        moderator = self.register("max_moderator")
        admin = Client(self.base).login("chief", PASSWORD)
        _, users = admin.request("GET", "/api/admin/users?q=max_moderator")
        moderator_id = users["items"][0]["id"]
        self.assertEqual(admin.request("POST", f"/api/admin/users/{moderator_id}/role", {"role": "moderator"})[0], 200)
        _, queue = moderator.request("GET", "/api/admin/moderation/queue")
        self.assertIn(submission_id, [i["id"] for i in queue["items"]])
        status, _ = moderator.request("POST", f"/api/admin/moderation/submissions/{submission_id}/decision", {"decision": "approve"})
        self.assertEqual(status, 200)

        # 6. Published in the feed and on the company page; the author is notified on the site and by email
        _, feed = Client(self.base).request("GET", "/api/articles?limit=50")
        self.assertIn(submission_id, json.dumps(feed))
        _, company_feed = Client(self.base).request("GET", f"/api/articles?companyId={company_id}")
        self.assertIn(submission_id, json.dumps(company_feed))
        item = next(i for i in feed["items"] if i["id"] == submission_id)
        self.assertEqual(item["author"], "anna_author", "the author's profile name, not a placeholder")
        author.request("POST", "/api/user/profile", {"name": "Анна Авторова"})
        _, feed = Client(self.base).request("GET", "/api/articles?limit=50")
        self.assertEqual(next(i for i in feed["items"] if i["id"] == submission_id)["author"], "Анна Авторова",
                         "a rename shows on existing materials")
        _, article = Client(self.base).request("GET", f"/api/articles/{submission_id}")
        self.assertIn("Анна Авторова", json.dumps(article, ensure_ascii=False))
        _, notifications = author.request("GET", "/api/notifications")
        self.assertIn("moderation_approved", [n["type"] for n in notifications["notifications"]])
        self.assertTrue([m for m in EMAIL_SERVICE.get_sent_emails() if m["recipient"] == "anna_author@example.com"
                         and "опубликован" in m["subject"]])

        # 7. A reader comments and follows the company; the author is notified about the comment
        reader = self.register("rita_reader")
        status, _ = reader.request("POST", f"/api/articles/{submission_id}/comments",
                                   {"commentType": "comment", "content": "Отличный разбор, спасибо"})
        self.assertEqual(status, 201)
        _, notifications = author.request("GET", "/api/notifications")
        self.assertIn("new_reply", [n["type"] for n in notifications["notifications"]])
        self.assertGreaterEqual(notifications["unreadCount"], 2)
        reader.request("POST", "/api/subscriptions/toggle",
                       {"targetType": "company", "targetId": company_id, "title": "Тест", "action": "subscribe"})
        _, subscribers = Client(self.base).request("GET", f"/api/companies/{company_id}/subscribers")
        self.assertIn("rita_reader", json.dumps(subscribers))

        # 8. Avatar from one's own upload; someone else's upload is refused
        avatar = self.upload(author, png(200, 200, 33))
        self.assertEqual(author.request("POST", "/api/user/profile-media", {"kind": "avatar", "url": avatar})[0], 200)
        _, me = author.request("GET", "/api/auth/status")
        self.assertEqual(me["user"]["avatar"], avatar)
        self.assertEqual(reader.request("POST", "/api/user/profile-media", {"kind": "avatar", "url": avatar})[0], 403)

        # 9. Password recovery by email revokes every session of the account
        anonymous = Client(self.base)
        anonymous.request("POST", "/api/auth/forgot-password", {"identifier": "anna_author"})
        status, _ = anonymous.request("POST", "/api/auth/reset-password", {
            "identifier": "anna_author", "code": self.code_for("anna_author@example.com"), "newPassword": "E2e-new-pass-2"})
        self.assertEqual(status, 200)
        self.assertFalse(author.request("GET", "/api/auth/status")[1]["authenticated"])
        self.assertFalse(second_device.request("GET", "/api/auth/status")[1]["authenticated"])
        Client(self.base).login("anna_author", "E2e-new-pass-2")

        # 10. Production settings: the old demo login with a forged identity gives no session
        intruder = Client(self.base)
        status, _ = intruder.request("POST", "/api/auth/login", {"userId": author_id, "role": "admin"})
        self.assertIn(status, (400, 401))
        self.assertFalse(intruder.request("GET", "/api/auth/status")[1]["authenticated"])


if __name__ == "__main__":
    unittest.main()
