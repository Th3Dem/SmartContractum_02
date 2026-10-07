"""
HTTP tests for the standalone company profile (Issue #212).
"""
import datetime
import os
import shutil
import sqlite3
import tempfile
import threading
import unittest

from server import create_server, create_user, init_db, reset_login_rate_limiter
from tests.http_client import Client, submission_payload

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PASSWORD = "Company-pass-1"


class TestCompanyProfile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "companies.db")
        init_db(cls.db_path, seed=False).close()
        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        ids = {}
        for login in ("owner", "member", "stranger", "fan"):
            ids[login] = create_user(conn, login, f"{login}@example.com", PASSWORD, email_verified=True)["id"]
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        for cid, name, owner in (("acme", "ООО «Акме»", ids["owner"]), ("other", "АО «Другая»", ids["stranger"])):
            conn.execute("""
                INSERT INTO companies (id, name, description, specialization, website, logo, directions, owner_id, is_verified, created_at, updated_at)
                VALUES (?, ?, 'Короткое описание', 'Аудит', 'acme.example', NULL, '[]', ?, 0, ?, ?)
            """, (cid, name, owner, now, now))
        conn.execute("INSERT INTO company_members (company_id, user_id, role, created_at) VALUES ('acme', ?, 'member', ?)",
                     (ids["member"], now))
        conn.commit()
        conn.close()
        cls.ids = ids
        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path,
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

    def client(self, login=None):
        c = Client(self.base)
        return c.login(login, PASSWORD) if login else c

    def test_profile_and_not_found(self):
        status, body = self.client().request("GET", "/api/companies/acme/profile")
        self.assertEqual(status, 200)
        c = body["company"]
        self.assertEqual(c["name"], "ООО «Акме»")
        self.assertFalse(c["canEdit"])
        self.assertEqual(c["stats"]["members"], 2, "the owner and one member")
        self.assertEqual(self.client().request("GET", "/api/companies/missing/profile")[0], 404)

    def test_only_owner_edits(self):
        update = {"about": "Мы проводим аудит смарт-контрактов.\n\nКоманда из 12 инженеров."}
        self.assertEqual(self.client().request("PUT", "/api/companies/acme", update)[0], 401)
        self.assertEqual(self.client("stranger").request("PUT", "/api/companies/acme", update)[0], 403)
        self.assertEqual(self.client("member").request("PUT", "/api/companies/acme", update)[0], 403,
                         "members publish but do not edit the profile")
        owner = self.client("owner")
        status, body = owner.request("PUT", "/api/companies/acme", update)
        self.assertEqual(status, 200, body)
        self.assertEqual(body["company"]["about"], update["about"])
        self.assertTrue(body["company"]["canEdit"])

    def test_profile_fields_are_validated(self):
        owner = self.client("owner")
        status, body = owner.request("PUT", "/api/companies/acme", {"website": "javascript:alert(1)"})
        self.assertEqual(status, 400)
        self.assertIn("website", body["fieldErrors"])
        self.assertEqual(owner.request("PUT", "/api/companies/acme", {"name": ""})[0], 400)
        self.assertEqual(owner.request("PUT", "/api/companies/acme", {"about": "x" * 8001})[0], 400)
        status, body = owner.request("PUT", "/api/companies/acme", {"website": "acme.example/blog"})
        self.assertEqual(body["company"]["website"], "https://acme.example/blog")

    def test_company_creation_rejects_script_links(self):
        status, _ = self.client("fan").request("POST", "/api/companies", {
            "name": "Новая", "description": "Описание", "specialization": "Аудит", "website": "javascript:alert(1)"})
        self.assertEqual(status, 400)

    def test_subscribers_list_follows_people_subscriptions(self):
        fan = self.client("fan")
        fan.request("POST", "/api/subscriptions/toggle", {"targetType": "company", "targetId": "acme", "title": "Акме", "action": "subscribe"})
        _, subs = self.client().request("GET", "/api/companies/acme/subscribers")
        self.assertIn(self.ids["fan"], [s["id"] for s in subs["items"]])
        _, profile = fan.request("GET", "/api/companies/acme/profile")
        self.assertTrue(profile["company"]["isSubscribed"])

    def test_company_subscriptions_are_separate_from_owner(self):
        owner = self.client("owner")
        path = "/api/companies/acme/subscriptions/toggle"
        self.assertEqual(self.client("member").request("POST", path, {"targetType": "topic", "targetId": "pksc-architecture"})[0], 403)
        self.assertEqual(owner.request("POST", path, {"targetType": "company", "targetId": "acme"})[0], 400, "not itself")
        self.assertEqual(owner.request("POST", path, {"targetType": "company", "targetId": "ghost"})[0], 404)
        status, body = owner.request("POST", path, {"targetType": "company", "targetId": "other", "action": "subscribe"})
        self.assertEqual((status, body["subscribed"]), (200, True))
        owner.request("POST", path, {"targetType": "company", "targetId": "other", "action": "subscribe"})

        _, following = self.client().request("GET", "/api/companies/acme/subscriptions")
        self.assertEqual([(i["targetType"], i["targetId"]) for i in following["items"]], [("company", "other")])
        _, personal = owner.request("GET", "/api/subscriptions")
        self.assertNotIn("other", str(personal), "the owner's personal subscriptions are untouched")

    def test_my_companies(self):
        _, mine = self.client("owner").request("GET", "/api/user/companies")
        self.assertEqual([(c["id"], c["role"], c["canEdit"]) for c in mine["items"]], [("acme", "owner", True)])
        _, member = self.client("member").request("GET", "/api/user/companies")
        self.assertEqual([(c["id"], c["canEdit"]) for c in member["items"]], [("acme", False)])
        self.assertEqual(self.client().request("GET", "/api/user/companies")[0], 401)

    def test_foreign_company_cannot_be_used_when_publishing(self):
        payload = submission_payload("spoof-draft")
        payload["publicationSettings"]["companyId"] = "acme"
        status, _ = self.client("stranger").request("POST", "/api/moderation/submit", payload)
        self.assertEqual(status, 403)
        status, _ = self.client("member").request("POST", "/api/moderation/submit", submission_payload("member-draft") | {
            "publicationSettings": dict(submission_payload("x")["publicationSettings"], companyId="acme")})
        self.assertEqual(status, 200)


if __name__ == "__main__":
    unittest.main()
