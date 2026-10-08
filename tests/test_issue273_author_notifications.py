#!/usr/bin/env python3
"""
tests/test_issue273_author_notifications.py

Issue #273: a per-author notification bell, independent of the subscription.

  PUT /api/authors/<author_id>/notifications   {"enabled": true|false}
  GET /api/user/author-notifications           ?q=&limit=&offset=
  GET /api/users/<user_id>/summary             compact profile for the author mini card

HTTP and DB checks against a real server with CSRF on.
"""

import json
import os
import shutil
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import server
from server import create_server, create_user, init_db
from tests.http_client import Client

PASSWORD = "Bell-pass-1"


def add_user(db_path, login, name=None):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        user_id = create_user(conn, login, login + "@example.com", PASSWORD, email_verified=True)["id"]
        if name:
            with conn:
                conn.execute("INSERT OR REPLACE INTO user_profiles (user_id, name, created_at, updated_at) VALUES (?, ?, '2026-01-01', '2026-01-01')",
                             (user_id, name))
        return user_id
    finally:
        conn.close()


class TestIssue273AuthorNotifications(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "issue273.db")
        server.DEFAULT_DB_PATH = cls.db_path
        init_db(cls.db_path, seed=False).close()
        cls.reader_id = add_user(cls.db_path, "bell_reader", "Читатель")
        cls.other_id = add_user(cls.db_path, "bell_other", "Другой читатель")
        cls.author_id = add_user(cls.db_path, "bell_author", "Анна Автор")
        cls.author2_id = add_user(cls.db_path, "second_writer", "Борис Писатель")
        cls.author3_id = add_user(cls.db_path, "third_writer", "Вера Третья")
        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, seed=False, enforce_csrf=True)
        cls.base = "http://127.0.0.1:%d" % cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.reader = Client(cls.base).login("bell_reader", PASSWORD)
        cls.other = Client(cls.base).login("bell_other", PASSWORD)
        cls.author = Client(cls.base).login("bell_author", PASSWORD)
        cls.guest = Client(cls.base)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self):
        conn = sqlite3.connect(self.db_path)
        with conn:
            for table in ("user_author_notifications", "user_subscriptions", "user_feed_exceptions"):
                conn.execute("DELETE FROM %s" % table)
            conn.execute("UPDATE users SET status = 'active'")
        conn.close()

    # helpers
    def bell(self, client, author_id, enabled):
        return client.request("PUT", "/api/authors/%s/notifications" % author_id, {"enabled": enabled})

    def subscribe(self, client, author_id, action):
        return client.request("POST", "/api/subscriptions/toggle", {"targetType": "author", "targetId": author_id, "action": action})

    def exclude(self, client, author_id, action):
        return client.request("POST", "/api/exceptions/toggle", {"targetType": "author", "targetId": author_id, "action": action})

    def summary(self, client, author_id):
        status, body = client.request("GET", "/api/users/%s/summary" % author_id)
        self.assertEqual(status, 200, body)
        return body["summary"]

    def rows(self):
        conn = sqlite3.connect(self.db_path)
        try:
            return sorted(conn.execute("SELECT user_id, author_id FROM user_author_notifications").fetchall())
        finally:
            conn.close()

    # tests
    def test_bell_and_subscription_are_independent_in_all_four_combinations(self):
        a = self.author_id
        self.assertEqual(self.summary(self.reader, a)["authorNotificationsEnabled"], False, "off by default")
        status, body = self.bell(self.reader, a, True)
        self.assertEqual((status, body["enabled"], body["isSubscribed"]), (200, True, False), "on does not subscribe")
        self.subscribe(self.reader, a, "subscribe")
        s = self.summary(self.reader, a)
        self.assertEqual((s["isSubscribed"], s["authorNotificationsEnabled"]), (True, True))
        self.subscribe(self.reader, a, "unsubscribe")
        s = self.summary(self.reader, a)
        self.assertEqual((s["isSubscribed"], s["authorNotificationsEnabled"]), (False, True), "unsubscribe keeps the bell")
        self.subscribe(self.reader, a, "subscribe")
        self.bell(self.reader, a, False)
        s = self.summary(self.reader, a)
        self.assertEqual((s["isSubscribed"], s["authorNotificationsEnabled"]), (True, False), "off keeps the subscription")
        self.subscribe(self.reader, a, "unsubscribe")
        s = self.summary(self.reader, a)
        self.assertEqual((s["isSubscribed"], s["authorNotificationsEnabled"]), (False, False))

    def test_explicit_state_is_idempotent_and_personal(self):
        for _ in range(3):
            status, body = self.bell(self.reader, self.author_id, True)
            self.assertEqual((status, body["enabled"], body["count"]), (200, True, 1))
        self.assertEqual(self.rows(), [(self.reader_id, self.author_id)])
        self.assertFalse(self.summary(self.other, self.author_id)["authorNotificationsEnabled"], "B does not see A's bell")
        for _ in range(2):
            status, body = self.bell(self.reader, self.author_id, False)
            self.assertEqual((status, body["enabled"]), (200, False))
        self.assertEqual(self.rows(), [])

    def test_guest_spoofed_user_self_unknown_and_disabled_author(self):
        status, body = self.bell(self.guest, self.author_id, True)
        self.assertEqual(status, 401)
        self.assertTrue(body.get("requireAuth"))
        guest_summary = self.summary(self.guest, self.author_id)
        self.assertEqual((guest_summary["isSubscribed"], guest_summary["authorNotificationsEnabled"]), (False, False))

        status, _ = self.reader.request("PUT", "/api/authors/%s/notifications" % self.author_id,
                                        {"enabled": True, "userId": self.other_id, "user_id": self.other_id})
        self.assertEqual(status, 200)
        self.assertEqual(self.rows(), [(self.reader_id, self.author_id)], "user_id in the payload is ignored")

        status, body = self.bell(self.author, self.author_id, True)
        self.assertEqual((status, body["code"]), (400, "SELF_NOTIFICATIONS_FORBIDDEN"))
        own = self.summary(self.author, self.author_id)
        self.assertEqual((own["isOwnProfile"], own["authorNotificationsEnabled"], own["canNotify"]), (True, False, False))

        status, body = self.bell(self.reader, "nobody-here", True)
        self.assertEqual((status, body["code"]), (404, "AUTHOR_NOT_FOUND"))
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute("UPDATE users SET status = 'disabled' WHERE id = ?", (self.author2_id,))
        conn.close()
        status, body = self.bell(self.reader, self.author2_id, True)
        self.assertEqual((status, body["code"]), (404, "AUTHOR_NOT_FOUND"))
        for bad in ("true", 1, None):
            status, body = self.reader.request("PUT", "/api/authors/%s/notifications" % self.author_id, {"enabled": bad})
            self.assertEqual((status, body["code"]), (400, "INVALID_ENABLED"))

    def test_put_requires_csrf_token(self):
        session = [c.value for c in self.reader.jar if c.name == "sc_session"][0]
        req = urllib.request.Request(self.base + "/api/authors/%s/notifications" % self.author_id,
                                     data=json.dumps({"enabled": True}).encode(), method="PUT",
                                     headers={"Content-Type": "application/json", "Cookie": "sc_session=" + session})
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(ctx.exception.code, 403)
        self.assertEqual(self.rows(), [])

    def test_exclusion_turns_the_bell_off_on_every_path(self):
        a = self.author_id
        self.bell(self.reader, a, True)
        self.exclude(self.reader, a, "exclude")
        self.assertEqual(self.rows(), [], "single exclude")
        status, body = self.bell(self.reader, a, True)
        self.assertEqual((status, body["code"]), (409, "AUTHOR_EXCLUDED"))
        self.assertTrue(self.summary(self.reader, a)["isExcluded"])
        self.exclude(self.reader, a, "remove")
        self.assertFalse(self.summary(self.reader, a)["authorNotificationsEnabled"], "removing the exclusion does not turn it on")

        self.bell(self.reader, a, True)
        self.exclude(self.reader, a, "toggle")
        self.assertEqual(self.rows(), [], "toggle exclude")
        self.exclude(self.reader, a, "toggle")

        self.bell(self.reader, a, True)
        self.bell(self.reader, self.author3_id, True)
        status, _ = self.reader.request("POST", "/api/user/feed-settings", {
            "materialTypes": ["publication", "question"],
            "exceptions": {"authors": [{"id": a, "title": "Анна Автор"}]}})
        self.assertEqual(status, 200)
        self.assertEqual(self.rows(), [(self.reader_id, self.author3_id)], "batch exceptions clear only the excluded author")

    def test_subscription_paths_keep_the_bell(self):
        self.bell(self.reader, self.author_id, True)
        status, _ = self.reader.request("POST", "/api/user/feed-settings", {
            "materialTypes": ["publication", "question"],
            "subscriptions": {"authors": [{"id": self.author3_id, "title": "Вера Третья"}]}})
        self.assertEqual(status, 200)
        self.subscribe(self.reader, self.author_id, "toggle")
        self.subscribe(self.reader, self.author_id, "toggle")
        self.assertEqual(self.rows(), [(self.reader_id, self.author_id)])

    def test_private_list_with_search_pagination_and_unavailable_author(self):
        for author in (self.author_id, self.author2_id, self.author3_id):
            self.bell(self.reader, author, True)
        self.subscribe(self.reader, self.author2_id, "subscribe")
        status, body = self.reader.request("GET", "/api/user/author-notifications")
        self.assertEqual(status, 200)
        self.assertEqual((body["total"], body["count"]), (3, 3))
        by_id = {i["authorId"]: i for i in body["items"]}
        self.assertEqual(by_id[self.author2_id]["isSubscribed"], True)
        self.assertEqual(by_id[self.author_id]["isSubscribed"], False, "authors without a subscription are listed")
        self.assertEqual(by_id[self.author_id]["name"], "Анна Автор")

        status, body = self.reader.request("GET", "/api/user/author-notifications?q=" + urllib.request.quote("АННА"))
        self.assertEqual([i["authorId"] for i in body["items"]], [self.author_id], "case-insensitive Cyrillic search")
        status, body = self.reader.request("GET", "/api/user/author-notifications?q=second_writer")
        self.assertEqual([i["authorId"] for i in body["items"]], [self.author2_id], "search by login")
        status, body = self.reader.request("GET", "/api/user/author-notifications?limit=2&offset=0")
        self.assertEqual((len(body["items"]), body["hasMore"]), (2, True))
        status, body = self.reader.request("GET", "/api/user/author-notifications?limit=2&offset=2")
        self.assertEqual((len(body["items"]), body["hasMore"]), (1, False))

        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute("UPDATE users SET status = 'disabled' WHERE id = ?", (self.author3_id,))
            conn.execute("UPDATE user_profiles SET name = 'Вера Новая' WHERE user_id = ?", (self.author3_id,))
        conn.close()
        status, body = self.reader.request("GET", "/api/user/author-notifications")
        item = [i for i in body["items"] if i["authorId"] == self.author3_id][0]
        self.assertEqual((item["available"], item["name"]), (False, "Вера Новая"), "renamed and unavailable author stays listed")
        status, body = self.bell(self.reader, self.author3_id, False)
        self.assertEqual((status, body["count"]), (200, 2), "an unavailable author can be removed")

        self.assertEqual(self.other.request("GET", "/api/user/author-notifications")[1]["total"], 0, "B sees only B's list")
        self.assertEqual(self.guest.request("GET", "/api/user/author-notifications")[0], 401)

    def test_summary_matches_the_full_profile_and_has_no_lists(self):
        self.subscribe(self.reader, self.author_id, "subscribe")
        self.bell(self.reader, self.author_id, True)
        status, profile = self.reader.request("GET", "/api/users/%s" % self.author_id)
        self.assertEqual(status, 200)
        profile = profile["profile"]
        summary = self.summary(self.reader, self.author_id)
        for key in ("name", "avatar", "rating", "publicationsCount", "questionsCount", "commentsCount", "followersCount",
                    "isSubscribed", "authorNotificationsEnabled", "isOwnProfile"):
            self.assertEqual(summary[key], profile[key], key)
        self.assertNotIn("publications", summary)
        self.assertNotIn("topContributions", summary)
        self.assertEqual(self.guest.request("GET", "/api/users/nobody-here/summary")[0], 404)

    def test_migration_keeps_existing_subscriptions_without_bell(self):
        self.subscribe(self.reader, self.author_id, "subscribe")
        init_db(self.db_path, seed=False).close()
        self.assertEqual(self.rows(), [])
        self.assertFalse(self.summary(self.reader, self.author_id)["authorNotificationsEnabled"])


if __name__ == "__main__":
    unittest.main()
