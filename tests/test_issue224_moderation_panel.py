"""
HTTP tests for the moderation panel (Issue #224) against a real server instance.
"""
import http.cookiejar
import json
import os
import shutil
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from server import (
    EMAIL_SERVICE,
    create_admin,
    create_server,
    create_user,
    init_db,
    reset_login_rate_limiter,
)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PASSWORD = "Moderation-pass-1"


class Client:
    def __init__(self, base_url):
        self.base_url = base_url
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def request(self, method, path, payload=None):
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        for c in self.jar:
            if c.name == "sc_csrf":
                req.add_header("X-CSRF-Token", c.value)
        try:
            with self.opener.open(req, timeout=10) as resp:
                raw = resp.read()
                return resp.status, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            raw = e.read()
            e.close()
            return e.code, json.loads(raw) if raw else {}

    def login(self, login, password=PASSWORD):
        status, _ = self.request("POST", "/api/auth/login", {"login": login, "password": password})
        assert status == 200, (login, status)
        return self


def submission_payload(draft_id, title="Разбор оптимизации газа в Solidity", material_type="publication"):
    return {
        "draftId": draft_id,
        "title": title,
        "html": "<p>Подробный разбор приемов оптимизации, примеры кода и измерения расхода газа до и после.</p>",
        "delta": {"ops": [{"insert": "Подробный разбор\n"}]},
        "publicationSettings": {
            "materialType": material_type,
            "targetAudience": "architects-integrators",
            "topics": ["pksc-architecture"],
            "keywords": ["solidity"],
            "description": "Практический разбор оптимизации смарт-контрактов с примерами и замерами расхода газа.",
            "format": "tutorial",
            "complexity": "medium",
        },
    }


class TestModerationPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "moderation.db")
        init_db(cls.db_path, seed=False).close()
        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        create_admin(conn, "chief", "chief@example.com", password=PASSWORD)
        for login, role in (("mod_anna", "moderator"), ("mod_boris", "moderator"),
                            ("author_one", "user"), ("author_two", "user"), ("reader", "user")):
            create_user(conn, login, f"{login}@example.com", PASSWORD, role=role, email_verified=True)
        conn.close()
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
        EMAIL_SERVICE.clear_sent_emails()

    def client(self, login=None):
        c = Client(self.base)
        return c.login(login) if login else c

    def submit(self, author, draft_id, **kw):
        status, body = author.request("POST", "/api/moderation/submit", submission_payload(draft_id, **kw))
        self.assertEqual(status, 200, body)
        return body["submissionId"]

    def decide(self, moderator, submission_id, decision, **kw):
        return moderator.request("POST", f"/api/admin/moderation/submissions/{submission_id}/decision",
                                 dict(decision=decision, **kw))

    def mails_to(self, address):
        return [m for m in EMAIL_SERVICE.get_sent_emails() if m["recipient"] == address]

    # access

    def test_guest_and_regular_user_have_no_access(self):
        author = self.client("author_one")
        sid = self.submit(author, "access-draft")
        guest = self.client()
        for path in ("/api/admin/moderation/queue", f"/api/admin/moderation/submissions/{sid}",
                     "/api/admin/moderation/log", "/api/admin/users"):
            self.assertEqual(guest.request("GET", path)[0], 401, path)
            self.assertEqual(author.request("GET", path)[0], 403, path)
        self.assertEqual(self.decide(author, sid, "approve")[0], 403)
        moderator = self.client("mod_anna")
        self.assertEqual(moderator.request("GET", "/api/admin/users")[0], 403, "moderators cannot manage users")

    # decisions

    def test_approve_publishes_and_notifies_author(self):
        author = self.client("author_one")
        sid = self.submit(author, "approve-draft", title="Материал для одобрения модератором")
        moderator = self.client("mod_anna")
        status, queue = moderator.request("GET", "/api/admin/moderation/queue")
        self.assertEqual(status, 200)
        self.assertIn(sid, [i["id"] for i in queue["items"]])

        status, body = self.decide(moderator, sid, "approve")
        self.assertEqual(status, 200, body)
        _, feed = self.client().request("GET", "/api/articles?limit=50")
        self.assertIn(sid, json.dumps(feed))

        _, notifications = author.request("GET", "/api/notifications")
        self.assertEqual(notifications["notifications"][0]["type"], "moderation_approved")
        self.assertEqual(len(self.mails_to("author_one@example.com")), 1)
        self.assertEqual(self.decide(moderator, sid, "reject", reasonCode="spam")[0], 409, "decided only once")

    def test_revise_requires_remarks_and_allows_resubmission(self):
        author = self.client("author_two")
        sid = self.submit(author, "revise-draft")
        moderator = self.client("mod_anna")
        self.assertEqual(self.decide(moderator, sid, "revise", comment="кратко")[0], 400)
        remarks = "Добавьте источники и примеры кода для каждого приема."
        self.assertEqual(self.decide(moderator, sid, "revise", comment=remarks)[0], 200)

        _, mine = author.request("GET", "/api/moderation/my")
        item = next(i for i in mine["items"] if i["id"] == sid)
        self.assertEqual(item["status"], "needs_revision")
        self.assertEqual(item["reviewComment"], remarks)
        status, snapshot = author.request("GET", f"/api/moderation/my/{sid}")
        self.assertEqual(status, 200)
        self.assertTrue(snapshot["submission"]["canRevise"])
        self.assertIn("Разбор", snapshot["submission"]["title"])
        self.assertIn("Нужна доработка", self.mails_to("author_two@example.com")[0]["body_text"])

        new_sid = self.submit(author, "revise-draft")
        _, mine = author.request("GET", "/api/moderation/my")
        latest = [i for i in mine["items"] if i["draftId"] == "revise-draft"]
        self.assertEqual([i["id"] for i in latest], [new_sid])
        self.assertEqual(latest[0]["status"], "pending_moderation")
        _, detail = moderator.request("GET", f"/api/admin/moderation/submissions/{new_sid}")
        self.assertEqual(detail["submission"]["versions"][0]["reviewComment"], remarks)

    def test_reject_requires_reason_and_blocks_resubmission(self):
        author = self.client("author_one")
        sid = self.submit(author, "reject-draft")
        moderator = self.client("mod_boris")
        self.assertEqual(self.decide(moderator, sid, "reject")[0], 400)
        self.assertEqual(self.decide(moderator, sid, "reject", reasonCode="other", comment="")[0], 400)
        self.assertEqual(self.decide(moderator, sid, "reject", reasonCode="off_topic")[0], 200)

        status, body = author.request("POST", "/api/moderation/submit", submission_payload("reject-draft"))
        self.assertEqual(status, 400)
        _, feed = self.client().request("GET", "/api/articles?limit=50")
        self.assertNotIn(sid, json.dumps(feed))
        self.assertIn("Не по теме", self.mails_to("author_one@example.com")[0]["body_text"])

    def test_claim_prevents_parallel_decisions(self):
        author = self.client("author_two")
        sid = self.submit(author, "claim-draft")
        anna, boris = self.client("mod_anna"), self.client("mod_boris")
        self.assertEqual(anna.request("POST", f"/api/admin/moderation/submissions/{sid}/claim", {})[0], 200)
        self.assertEqual(boris.request("POST", f"/api/admin/moderation/submissions/{sid}/claim", {})[0], 409)
        self.assertEqual(self.decide(boris, sid, "approve")[0], 409)
        _, detail = boris.request("GET", f"/api/admin/moderation/submissions/{sid}")
        self.assertEqual(detail["submission"]["claimedBy"]["name"], "mod_anna")
        self.assertEqual(anna.request("POST", f"/api/admin/moderation/submissions/{sid}/release", {})[0], 200)
        self.assertEqual(self.decide(boris, sid, "approve")[0], 200)

    def test_author_cannot_read_foreign_submission(self):
        sid = self.submit(self.client("author_one"), "private-draft")
        self.assertEqual(self.client("author_two").request("GET", f"/api/moderation/my/{sid}")[0], 404)

    def test_decision_log_records_every_decision(self):
        author = self.client("author_one")
        sid = self.submit(author, "log-draft")
        self.decide(self.client("mod_anna"), sid, "revise", comment="Уточните заголовок материала.")
        _, log = self.client("chief").request("GET", "/api/admin/moderation/log")
        entry = next(e for e in log["items"] if e["submissionId"] == sid)
        self.assertEqual(entry["decision"], "revise")
        self.assertEqual(entry["moderator"]["name"], "mod_anna")

    # users

    def test_admin_manages_roles_and_blocks_accounts(self):
        admin = self.client("chief")
        _, users = admin.request("GET", "/api/admin/users?q=reader")
        reader_id = users["items"][0]["id"]

        self.assertEqual(admin.request("POST", f"/api/admin/users/{reader_id}/role", {"role": "moderator"})[0], 200)
        promoted = self.client("reader")
        self.assertEqual(promoted.request("GET", "/api/admin/moderation/queue")[0], 200)
        self.assertEqual(admin.request("POST", f"/api/admin/users/{reader_id}/role", {"role": "admin"})[0], 400)
        self.assertEqual(admin.request("POST", f"/api/admin/users/{reader_id}/role", {"role": "user"})[0], 200)
        self.assertEqual(promoted.request("GET", "/api/admin/moderation/queue")[0], 403)

        self.assertEqual(admin.request("POST", f"/api/admin/users/{reader_id}/status", {"status": "disabled"})[0], 200)
        self.assertFalse(promoted.request("GET", "/api/auth/status")[1].get("authenticated"))
        self.assertEqual(admin.request("POST", f"/api/admin/users/{reader_id}/status", {"status": "active"})[0], 200)

        _, me = admin.request("GET", "/api/auth/status")
        self.assertEqual(admin.request("POST", f"/api/admin/users/{me['user']['id']}/status", {"status": "disabled"})[0], 409)

    # migration

    def test_old_database_is_migrated(self):
        path = os.path.join(self.temp_dir, "old.db")
        conn = sqlite3.connect(path)
        conn.execute("""
            CREATE TABLE moderation_submissions (
                id TEXT PRIMARY KEY, draft_id TEXT NOT NULL, title TEXT NOT NULL,
                author_id TEXT NOT NULL DEFAULT 'author_local',
                status TEXT NOT NULL DEFAULT 'pending_moderation' CHECK (status IN ('draft', 'pending_moderation', 'approved', 'rejected')),
                publication_settings TEXT NOT NULL, article_html TEXT NOT NULL, article_delta TEXT,
                idempotency_key TEXT UNIQUE, snapshot_hash TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )""")
        conn.execute("""INSERT INTO moderation_submissions VALUES
            ('sub_old', 'd1', 'Old', 'u1', 'pending_moderation', '{}', '<p>x</p>', NULL, NULL, 'h', '2026-01-01', '2026-01-01')""")
        conn.commit()
        conn.close()
        init_db(path, seed=False).close()
        init_db(path, seed=False).close()  # idempotent
        conn = sqlite3.connect(path)
        conn.execute("UPDATE moderation_submissions SET status = 'needs_revision', review_comment = 'ok' WHERE id = 'sub_old'")
        self.assertEqual(conn.execute("SELECT status FROM moderation_submissions").fetchone()[0], "needs_revision")
        conn.close()


class TestCreateAdmin(unittest.TestCase):
    """The server command names one account; it never promotes a different one found by email."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.conn = init_db(os.path.join(self.temp_dir, "admin.db"), seed=False)
        self.conn.row_factory = sqlite3.Row

    def tearDown(self):
        self.conn.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def role(self, login):
        return self.conn.execute("SELECT role FROM users WHERE login = ?", (login,)).fetchone()[0]

    def test_email_of_another_account_is_refused(self):
        create_user(self.conn, "owner_one", "owner@example.com", PASSWORD, email_verified=True)
        with self.assertRaises(ValueError) as ctx:
            create_admin(self.conn, "chief", "owner@example.com")
        self.assertIn("owner_one", str(ctx.exception), "the message names the account that has the email")
        self.assertEqual(self.role("owner_one"), "user")
        self.assertIsNone(self.conn.execute("SELECT 1 FROM users WHERE login = 'chief'").fetchone())

    def test_login_and_email_of_two_accounts_are_refused(self):
        create_user(self.conn, "chief", "chief@example.com", PASSWORD, email_verified=True)
        create_user(self.conn, "owner_one", "owner@example.com", PASSWORD, email_verified=True)
        with self.assertRaises(ValueError):
            create_admin(self.conn, "chief", "owner@example.com")
        self.assertEqual((self.role("chief"), self.role("owner_one")), ("user", "user"))

    def test_named_account_is_promoted(self):
        create_user(self.conn, "owner_one", "owner@example.com", PASSWORD, email_verified=True)
        user_id, _ = create_admin(self.conn, "Owner_One", "owner@example.com")
        self.assertEqual(self.role("owner_one"), "admin")
        _, _ = create_admin(self.conn, "fresh_admin", "fresh@example.com")
        self.assertEqual(self.role("fresh_admin"), "admin")
        self.assertTrue(user_id)


if __name__ == "__main__":
    unittest.main()
