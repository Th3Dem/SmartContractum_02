#!/usr/bin/env python3
"""
tests/test_issue274_author_notification_delivery.py

Issue #274: in-app notifications about the first public version of materials of authors a reader follows
with the bell (#273). HTTP and DB checks of the event matrix, idempotency, transactions, read-time
publicity checks and the notification center contract, against a real server with CSRF on.
"""

import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest import mock

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import server
from server import create_server, create_user, init_db, reset_login_rate_limiter
from backend import db as backend_db
from backend.author_delivery import deliver_author_material, material_key
from tests.http_client import Client, submission_payload

PASSWORD = "Deliver-pass-1"
AUTHOR_TYPES = ("author_publication", "author_question")


def connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


class TestIssue274AuthorNotificationDelivery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "issue274.db")
        server.DEFAULT_DB_PATH = cls.db_path
        init_db(cls.db_path, seed=False).close()
        conn = connect(cls.db_path)
        cls.ids = {}
        for login, role, name in (("dl_mod", "moderator", "Модератор"), ("dl_mod2", "moderator", "Модератор 2"),
                                  ("dl_author", "user", "Анна Автор"), ("dl_reader", "user", "Читатель"),
                                  ("dl_plain", "user", "Просто подписчик"), ("dl_late", "user", "Поздний читатель"),
                                  ("dl_off", "user", "Выключивший")):
            uid = create_user(conn, login, login + "@example.com", PASSWORD, role=role, email_verified=True)["id"]
            with conn:
                conn.execute("INSERT OR REPLACE INTO user_profiles (user_id, name, created_at, updated_at) "
                             "VALUES (?, ?, '2026-01-01', '2026-01-01')", (uid, name))
            cls.ids[login] = uid
        conn.close()
        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, seed=False, enforce_csrf=True)
        cls.base = "http://127.0.0.1:%d" % cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        reset_login_rate_limiter()
        cls.c = {login: Client(cls.base).login(login, PASSWORD) for login in cls.ids}

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=2)
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self):
        conn = connect(self.db_path)
        with conn:
            for table in ("user_author_notifications", "user_subscriptions", "user_feed_exceptions",
                          "user_notifications"):
                conn.execute("DELETE FROM %s" % table)
            conn.execute("UPDATE users SET status = 'active'")
        conn.close()
        self.author_id = self.ids["dl_author"]

    # helpers
    def bell(self, login, enabled, author_id=None):
        status, body = self.c[login].request("PUT", "/api/authors/%s/notifications" % (author_id or self.author_id),
                                             {"enabled": enabled})
        self.assertEqual(status, 200, body)

    def submit(self, draft_id, title="Разбор оптимизации газа в Solidity", material_type="publication"):
        status, body = self.c["dl_author"].request("POST", "/api/moderation/submit",
                                                   submission_payload(draft_id, title=title, material_type=material_type))
        self.assertEqual(status, 200, body)
        return body["submissionId"]

    def decide(self, submission_id, decision, moderator="dl_mod", **kw):
        return self.c[moderator].request("POST", "/api/admin/moderation/submissions/%s/decision" % submission_id,
                                         dict(decision=decision, **kw))

    def approve(self, submission_id):
        status, body = self.decide(submission_id, "approve")
        self.assertEqual(status, 200, body)

    def author_rows(self, user_login=None):
        conn = connect(self.db_path)
        try:
            sql = "SELECT * FROM user_notifications WHERE type IN ('author_publication', 'author_question')"
            args = ()
            if user_login:
                sql += " AND user_id = ?"
                args = (self.ids[user_login],)
            return [dict(r) for r in conn.execute(sql + " ORDER BY created_at", args)]
        finally:
            conn.close()

    def notifications(self, login):
        status, body = self.c[login].request("GET", "/api/notifications")
        self.assertEqual(status, 200, body)
        return body

    def set_status(self, submission_id, status):
        conn = connect(self.db_path)
        with conn:
            conn.execute("UPDATE moderation_submissions SET status = ? WHERE id = ?", (status, submission_id))
        conn.close()

    # event matrix
    def test_01_approved_publication_and_question_reach_bell_recipients_only(self):
        self.bell("dl_reader", True)
        status, _ = self.c["dl_plain"].request("POST", "/api/subscriptions/toggle",
                                               {"targetType": "author", "targetId": self.author_id, "action": "subscribe"})
        self.assertEqual(status, 200)

        pub = self.submit("d274-pub", title="Паттерны газа <script>x</script>")
        self.assertEqual(self.author_rows(), [], "submitting creates no event")
        self.approve(pub)
        q = self.submit("d274-q", title="Как проверить подпись EIP-712?", material_type="question")
        self.approve(q)

        rows = self.author_rows("dl_reader")
        self.assertEqual([(r["type"], r["article_id"]) for r in rows],
                         [("author_publication", pub), ("author_question", q)])
        self.assertEqual(rows[0]["material_id"], material_key(self.author_id, "d274-pub"))
        self.assertEqual(self.author_rows("dl_plain"), [], "a subscription without the bell is no reason to deliver")
        self.assertEqual(self.author_rows("dl_author"), [], "the author gets no event about themselves")
        self.assertEqual(len(self.author_rows()), 2)

        body = self.notifications("dl_reader")
        items = {n["articleId"]: n for n in body["notifications"]}
        self.assertEqual(body["unreadCount"], 2)
        p = items[pub]
        self.assertEqual(p["type"], "author_publication")
        self.assertEqual(p["materialType"], "publication")
        self.assertEqual(p["title"], "Новая публикация")
        self.assertEqual(p["authorName"], "Анна Автор")
        self.assertEqual(p["materialTitle"], "Паттерны газа <script>x</script>", "raw text; the client escapes it")
        self.assertIn("Анна Автор", p["message"])
        self.assertTrue(p["available"])
        self.assertFalse(p["isRead"])
        self.assertTrue(p["createdAt"])
        self.assertEqual(items[q]["materialType"], "question")
        self.assertEqual(items[q]["title"], "Новый вопрос")

    def test_02_draft_revision_reject_create_no_event_and_resubmission_gives_one(self):
        self.bell("dl_reader", True)
        sid = self.submit("d274-rev")
        self.assertEqual(self.decide(sid, "revise", comment="Добавьте примеры кода и источники.")[0], 200)
        rej = self.submit("d274-rej")
        self.assertEqual(self.decide(rej, "reject", reasonCode="spam")[0], 200)
        self.assertEqual(self.author_rows(), [])

        again = self.submit("d274-rev")
        self.approve(again)
        rows = self.author_rows("dl_reader")
        self.assertEqual([r["article_id"] for r in rows], [again], "first public version after revision: one event")

    def test_03_repeat_reapprove_and_hide_restore_do_not_duplicate(self):
        self.bell("dl_reader", True)
        sid = self.submit("d274-repeat")
        self.approve(sid)
        self.assertEqual(self.decide(sid, "approve")[0], 409, "a decision is taken once")
        self.assertEqual(self.decide(sid, "approve", moderator="dl_mod2")[0], 409)
        self.assertTrue(backend_db.update_submission_status(sid, "approved", db_path=self.db_path))
        # hidden and restored again (status leaves 'approved' and returns)
        self.assertTrue(backend_db.update_submission_status(sid, "rejected", db_path=self.db_path))
        self.bell("dl_late", True)
        self.assertTrue(backend_db.update_submission_status(sid, "approved", db_path=self.db_path))
        conn = connect(self.db_path)
        try:
            with conn:
                self.assertEqual(deliver_author_material(conn, sid, "2026-10-08T00:00:00+00:00"), 0)
        finally:
            conn.close()
        self.assertEqual(len(self.author_rows("dl_reader")), 1)
        self.assertEqual(self.author_rows("dl_late"), [], "a restored material is not news")

    def test_04_bell_on_after_publication_gets_no_history_and_off_stops_future(self):
        old = self.submit("d274-old")
        self.approve(old)
        self.bell("dl_late", True)
        self.bell("dl_off", True)
        self.assertEqual(self.author_rows(), [], "turning the bell on does not send old materials")

        first = self.submit("d274-first")
        self.approve(first)
        self.assertEqual(len(self.author_rows("dl_off")), 1)
        self.bell("dl_off", False)
        second = self.submit("d274-second")
        self.approve(second)
        self.assertEqual([r["article_id"] for r in self.author_rows("dl_off")], [first],
                         "off stops future events and keeps existing ones")
        self.assertEqual([r["article_id"] for r in self.author_rows("dl_late")], [first, second])

    def test_05_disabled_and_excluding_recipients_and_company_identity_get_nothing(self):
        self.bell("dl_reader", True)
        self.bell("dl_late", True)
        conn = connect(self.db_path)
        with conn:
            conn.execute("UPDATE users SET status = 'disabled' WHERE id = ?", (self.ids["dl_late"],))
            # an exclusion written behind the API (the API itself turns the bell off, #273)
            conn.execute("INSERT INTO user_feed_exceptions (user_id, target_type, target_id, target_title, created_at) "
                         "VALUES (?, 'author', ?, 'x', '2026-01-01')", (self.ids["dl_reader"], self.author_id))
        conn.close()
        sid = self.submit("d274-excluded")
        self.approve(sid)
        self.assertEqual(self.author_rows(), [])

        conn = connect(self.db_path)
        with conn:
            conn.execute("DELETE FROM user_feed_exceptions")
            settings = json.dumps({"materialType": "publication", "companyId": "comp_any"})
            conn.execute("""INSERT INTO moderation_submissions (id, draft_id, title, author_id, status, publication_settings,
                            article_html, snapshot_hash, created_at, updated_at)
                            VALUES ('sub_company_274', 'd274-company', 'Блог компании', ?, 'approved', ?, '<p>x</p>', 'h',
                                    '2026-01-01', '2026-01-01')""", (self.author_id, settings))
            self.assertEqual(deliver_author_material(conn, "sub_company_274", "2026-10-08T00:00:00+00:00"), 0)
        conn.close()
        self.assertEqual(self.author_rows(), [], "materials under a company identity are not delivered")

    # reliability
    def test_06_failed_delivery_rolls_back_the_decision_and_a_retry_delivers_once(self):
        self.bell("dl_reader", True)
        sid = self.submit("d274-rollback")
        with mock.patch("backend.moderation.deliver_author_material", side_effect=sqlite3.OperationalError("boom")):
            status, _ = self.decide(sid, "approve")
        self.assertEqual(status, 503)
        conn = connect(self.db_path)
        try:
            row = conn.execute("SELECT status FROM moderation_submissions WHERE id = ?", (sid,)).fetchone()
            self.assertEqual(row["status"], "pending_moderation", "no partially accepted first publication")
            self.assertIsNone(conn.execute("SELECT 1 FROM author_material_publications WHERE submission_id = ?",
                                           (sid,)).fetchone())
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM moderation_decisions WHERE submission_id = ?",
                                          (sid,)).fetchone()[0], 0)
        finally:
            conn.close()
        self.approve(sid)
        self.assertEqual(len(self.author_rows("dl_reader")), 1)

    def test_07_concurrent_approvals_deliver_once(self):
        self.bell("dl_reader", True)
        sid = self.submit("d274-race")
        results = []
        barrier = threading.Barrier(2)

        def run(moderator):
            barrier.wait()
            results.append(self.decide(sid, "approve", moderator=moderator)[0])

        threads = [threading.Thread(target=run, args=(m,)) for m in ("dl_mod", "dl_mod2")]
        for t in threads:
            t.start()
        for t in threads:
            t.join(10)
        self.assertEqual(sorted(results), [200, 409])
        self.assertEqual(len(self.author_rows("dl_reader")), 1)

        conn = connect(self.db_path)
        try:
            row = dict(conn.execute("SELECT * FROM user_notifications WHERE user_id = ? AND type = 'author_publication'",
                                    (self.ids["dl_reader"],)).fetchone())
            row["id"] = "notif_dup_274"
            cols = ", ".join(row)
            with self.assertRaises(sqlite3.IntegrityError, msg="(user_id, type, material_id) is unique in the DB"):
                with conn:
                    conn.execute("INSERT INTO user_notifications (%s) VALUES (%s)" % (cols, ", ".join("?" * len(row))),
                                 tuple(row.values()))
        finally:
            conn.close()

    def test_07b_bell_off_committed_while_approval_waits_wins(self):
        """SQLite serialises writers: the order of commits decides; an off that commits first is honoured."""
        self.bell("dl_off", True)
        sid = self.submit("d274-order")
        lock = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
        lock.execute("BEGIN IMMEDIATE")
        result = {}
        t = threading.Thread(target=lambda: result.setdefault("status", self.decide(sid, "approve")[0]))
        t.start()
        t.join(0.5)
        self.assertTrue(t.is_alive(), "the approval waits for the writer lock")
        lock.execute("DELETE FROM user_author_notifications WHERE user_id = ?", (self.ids["dl_off"],))
        lock.execute("COMMIT")
        lock.close()
        t.join(10)
        self.assertEqual(result.get("status"), 200)
        self.assertEqual(self.author_rows("dl_off"), [], "off committed before the publication: no event")

    # read side
    def test_08_unpublished_material_shows_neutral_state_and_read_flags_persist(self):
        self.bell("dl_reader", True)
        secret = "Секретный заголовок 274"
        sid = self.submit("d274-hidden", title=secret)
        self.approve(sid)
        visible = self.submit("d274-visible", title="Открытый материал 274")
        self.approve(visible)
        self.set_status(sid, "rejected")

        body = self.notifications("dl_reader")
        self.assertEqual(body["unreadCount"], 2, "an unavailable unread row is still counted and shown")
        hidden = next(n for n in body["notifications"] if n["type"] in AUTHOR_TYPES and not n["available"])
        self.assertIsNone(hidden["articleId"])
        self.assertIsNone(hidden["materialTitle"])
        self.assertEqual(hidden["title"], "Материал недоступен")
        self.assertNotIn(secret, json.dumps(body, ensure_ascii=False), "no non-public title anywhere in the response")

        other = self.c["dl_plain"]
        self.assertEqual(other.request("POST", "/api/notifications/read", {"notificationId": hidden["id"]})[0], 403,
                         "a notification of another user cannot be changed")
        status, res = self.c["dl_reader"].request("POST", "/api/notifications/read", {"notificationId": hidden["id"]})
        self.assertEqual((status, res["unreadCount"]), (200, 1))
        body = self.notifications("dl_reader")
        self.assertTrue(next(n for n in body["notifications"] if n["id"] == hidden["id"])["isRead"], "read persists")
        self.assertEqual(self.c["dl_reader"].request("POST", "/api/notifications/read", {})[1]["unreadCount"], 0)
        self.assertEqual(self.notifications("dl_reader")["unreadCount"], 0)

        # back to public: title and link come back
        self.set_status(sid, "approved")
        item = next(n for n in self.notifications("dl_reader")["notifications"] if n["id"] == hidden["id"])
        self.assertEqual((item["available"], item["articleId"], item["materialTitle"]), (True, sid, secret))

    def test_09_current_author_name_is_shown(self):
        self.bell("dl_reader", True)
        sid = self.submit("d274-rename")
        self.approve(sid)
        conn = connect(self.db_path)
        with conn:
            conn.execute("UPDATE user_profiles SET name = 'Анна Новая' WHERE user_id = ?", (self.author_id,))
        conn.close()
        try:
            item = next(n for n in self.notifications("dl_reader")["notifications"] if n["articleId"] == sid)
            self.assertEqual(item["authorName"], "Анна Новая")
            self.assertIn("Анна Новая", item["message"])
        finally:
            conn = connect(self.db_path)
            with conn:
                conn.execute("UPDATE user_profiles SET name = 'Анна Автор' WHERE user_id = ?", (self.author_id,))
            conn.close()

    def test_10_only_publication_paths_deliver(self):
        """Comments, answers and replies keep their own events (#211); only the approval paths deliver."""
        callers = []
        for root, _, files in os.walk(os.path.join(PROJECT_ROOT, "backend")):
            for name in files:
                if name.endswith(".py") and name != "author_delivery.py":
                    with open(os.path.join(root, name), encoding="utf-8") as f:
                        if re.search(r"deliver_author_material\(", f.read()):
                            callers.append(name)
        self.assertEqual(sorted(callers), ["db.py", "moderation.py"])


class TestIssue274Migration(unittest.TestCase):
    def test_legacy_schema_is_extended_and_existing_materials_are_not_news(self):
        temp_dir = tempfile.mkdtemp()
        try:
            path = os.path.join(temp_dir, "legacy.db")
            conn = sqlite3.connect(path)
            with conn:
                conn.execute("""CREATE TABLE user_notifications (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, actor_id TEXT NOT NULL, actor_name TEXT NOT NULL,
                    article_id TEXT NOT NULL, comment_id TEXT,
                    type TEXT NOT NULL CHECK(type IN ('new_answer', 'new_reply', 'solution_accepted', 'moderation_approved', 'moderation_revision', 'moderation_rejected')),
                    title TEXT NOT NULL, message TEXT NOT NULL, is_read INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL)""")
                conn.execute("INSERT INTO user_notifications VALUES ('n1', 'u1', 'a', 'A', 'art', NULL, 'new_reply', 't', 'm', 0, '2026-01-01')")
            conn.close()
            init_db(path, seed=False).close()
            conn = connect(path)
            try:
                with conn:
                    conn.execute("""INSERT INTO moderation_submissions (id, draft_id, title, author_id, status,
                                    publication_settings, article_html, snapshot_hash, created_at, updated_at)
                                    VALUES ('sub_legacy', 'legacy-draft', 'Старый материал', 'auth', 'approved', '{}',
                                            '<p>x</p>', 'h', '2026-01-01', '2026-01-01')""")
                conn.close()
                init_db(path, seed=False).close()
                conn = connect(path)
                sql = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'user_notifications'").fetchone()[0]
                self.assertIn("'author_publication', 'author_question'", sql)
                self.assertEqual(conn.execute("SELECT type FROM user_notifications WHERE id = 'n1'").fetchone()[0],
                                 "new_reply", "existing rows kept")
                self.assertIn("material_id", [r[1] for r in conn.execute("PRAGMA table_info(user_notifications)")])
                self.assertIsNotNone(conn.execute("SELECT 1 FROM author_material_publications WHERE material_id = 'auth/legacy-draft'").fetchone(),
                                     "materials already public are backfilled as published")
                with conn:
                    self.assertEqual(deliver_author_material(conn, "sub_legacy", "2026-10-08T00:00:00+00:00"), 0)
            finally:
                conn.close()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
