import unittest
import os
import json
import sqlite3
import threading
import time
from urllib import request
from urllib.error import HTTPError
import tempfile
import shutil

import sys
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
import server
from server import create_server, init_db

FRONTEND_DIR = os.path.join(REPO_ROOT, "frontend", "public")

class TestAccountNotificationsBackend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_notifications.db")
        server.DEFAULT_DB_PATH = cls.db_path
        
        conn = init_db(cls.db_path, seed=False)
        cls._seed_test_data(conn)
        conn.close()

        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, directory=FRONTEND_DIR, seed=False)
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

    @classmethod
    def _seed_test_data(cls, conn):
        cur = conn.cursor()
        users = [
            ("user_author", "user_author_token", "Author User", "author"),
            ("user_commenter", "user_commenter_token", "Commenter User", "commenter"),
            ("user_company_owner", "user_company_owner_token", "Company Owner", "owner")
        ]
        for u in users:
            cur.execute("INSERT INTO users (id, login, login_normalized, name, password_hash, created_at, updated_at) VALUES (?, ?, ?, ?, 'hash', '2023-01-01T00:00:00Z', '2023-01-01T00:00:00Z')",
                        (u[0], u[3], u[3].lower(), u[2]))
            cur.execute("INSERT INTO sessions (token, user_id, user_name, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
                        (u[1], u[0], u[2], "2023-01-01T00:00:00Z", "2029-01-01T00:00:00Z"))
            cur.execute("INSERT INTO user_profiles (user_id, name, created_at, updated_at) VALUES (?, ?, '2023-01-01T00:00:00Z', '2023-01-01T00:00:00Z')", (u[0], u[2]))
        
        # Create company
        cur.execute("INSERT INTO companies (id, name, description, specialization, owner_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, '2023-01-01T00:00:00Z', '2023-01-01T00:00:00Z')",
                    ("comp_1", "Tech Corp", "Desc", "Spec", "user_company_owner"))
        
        # Create articles
        cur.execute("""
            INSERT INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, '', 'approved', ?, 'hash', '2023-01-01T00:00:00Z', '2023-01-01T00:00:00Z')
        """, ("art_1", "draft_art_1", "user_author", "Regular Article", json.dumps({"materialType": "article"})))
        
        cur.execute("""
            INSERT INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, '', 'approved', ?, 'hash', '2023-01-01T00:00:00Z', '2023-01-01T00:00:00Z')
        """, ("art_2", "draft_art_2", "user_author", "Corporate Article", json.dumps({"materialType": "article", "companyId": "comp_1"})))
        
        cur.execute("""
            INSERT INTO moderation_submissions (id, draft_id, author_id, title, article_html, status, publication_settings, snapshot_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, '', 'approved', ?, 'hash', '2023-01-01T00:00:00Z', '2023-01-01T00:00:00Z')
        """, ("q_1", "draft_q_1", "user_author", "A Question", json.dumps({"materialType": "question"})))
        
        conn.commit()

    def request(self, method, path, data=None, token=None):
        req = request.Request(f"{self.base_url}{path}", method=method)
        if data is not None:
            req.data = json.dumps(data).encode("utf-8")
            req.add_header("Content-Type", "application/json")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        
        try:
            with request.urlopen(req) as response:
                return response.status, json.loads(response.read().decode())
        except HTTPError as e:
            try:
                body = json.loads(e.read().decode())
            except:
                body = {}
            return e.code, body

    def test_01_root_comment_regular_article(self):
        # Commenter adds a root comment to art_1
        st, res = self.request("POST", "/api/comments", {
            "articleId": "art_1",
            "content": "Nice article",
            "commentType": "comment"
        }, token="user_commenter_token")
        self.assertEqual(st, 201)
        
        st, res = self.request("GET", "/api/notifications", token="user_author_token")
        self.assertEqual(st, 200)
        self.assertEqual(res["unreadCount"], 1)
        self.assertEqual(len(res["notifications"]), 1)
        notif = res["notifications"][0]
        self.assertEqual(notif["type"], "new_reply")
        self.assertEqual(notif["actorId"], "user_commenter")

    def test_02_root_comment_corporate_article(self):
        # Commenter adds a root comment to art_2
        # Author and Company Owner should get a notification
        st, res = self.request("POST", "/api/comments", {
            "articleId": "art_2",
            "content": "Nice corporate article",
            "commentType": "comment"
        }, token="user_commenter_token")
        self.assertEqual(st, 201)
        comm_id = res["comment"]["id"]
        
        st, res = self.request("GET", "/api/notifications", token="user_company_owner_token")
        self.assertEqual(st, 200)
        self.assertEqual(res["unreadCount"], 1)
        self.assertEqual(len(res["notifications"]), 1)
        notif = res["notifications"][0]
        self.assertEqual(notif["commentId"], comm_id)
        self.assertEqual(notif["type"], "new_reply")

    def test_03_no_self_notification(self):
        # Author comments on own article, should not get notification
        st, res = self.request("GET", "/api/notifications", token="user_author_token")
        initial_unread = res["unreadCount"]
        
        st, res = self.request("POST", "/api/comments", {
            "articleId": "art_1",
            "content": "My own comment",
            "commentType": "comment"
        }, token="user_author_token")
        self.assertEqual(st, 201)
        
        st, res = self.request("GET", "/api/notifications", token="user_author_token")
        self.assertEqual(res["unreadCount"], initial_unread)

    def test_04_reply_to_comment(self):
        # Author replies to commenter's comment
        # Commenter should get notification
        st, res = self.request("POST", "/api/comments", {
            "articleId": "art_1",
            "content": "First comment",
            "commentType": "comment"
        }, token="user_commenter_token")
        parent_id = res["comment"]["id"]
        
        st, res = self.request("GET", "/api/notifications", token="user_commenter_token")
        initial_unread = res["unreadCount"]
        
        st, res = self.request("POST", "/api/comments", {
            "articleId": "art_1",
            "content": "Reply",
            "commentType": "comment",
            "parentCommentId": parent_id
        }, token="user_author_token")
        self.assertEqual(st, 201)
        
        st, res = self.request("GET", "/api/notifications", token="user_commenter_token")
        self.assertEqual(res["unreadCount"], initial_unread + 1)
        notif = res["notifications"][0]
        self.assertEqual(notif["type"], "new_reply")
        self.assertEqual(notif["actorId"], "user_author")

    def test_05_answer_to_question(self):
        st, res = self.request("POST", "/api/comments", {
            "articleId": "q_1",
            "content": "My answer",
            "commentType": "answer"
        }, token="user_commenter_token")
        self.assertEqual(st, 201)
        ans_id = res["comment"]["id"]
        
        st, res = self.request("GET", "/api/notifications", token="user_author_token")
        notif = res["notifications"][0]
        self.assertEqual(notif["type"], "new_answer")
        self.assertEqual(notif["commentId"], ans_id)
        self.assertEqual(notif["actorId"], "user_commenter")

    def test_06_idempotency_no_dup_notifs(self):
        st, res = self.request("GET", "/api/notifications", token="user_author_token")
        initial_unread = res["unreadCount"]
        
        payload = {
            "articleId": "art_1",
            "content": "Idempotent comment",
            "commentType": "comment",
            "clientOperationId": "op123"
        }
        st, res = self.request("POST", "/api/comments", payload, token="user_commenter_token")
        self.assertEqual(st, 201)
        
        st, res = self.request("POST", "/api/comments", payload, token="user_commenter_token")
        self.assertEqual(st, 200)
        self.assertTrue(res.get("isDuplicate"))
        
        st, res = self.request("GET", "/api/notifications", token="user_author_token")
        self.assertEqual(res["unreadCount"], initial_unread + 1)

    def test_07_guest_notifications(self):
        st, res = self.request("GET", "/api/notifications")
        self.assertEqual(st, 200)
        self.assertEqual(res["notifications"], [])
        self.assertEqual(res["unreadCount"], 0)

    def test_08_read_all_notifications(self):
        st, res = self.request("POST", "/api/notifications/read", {}, token="user_author_token")
        self.assertEqual(st, 200)
        self.assertEqual(res["unreadCount"], 0)
        
        st, res = self.request("GET", "/api/notifications", token="user_author_token")
        self.assertEqual(res["unreadCount"], 0)
        # Check that items are marked read
        for n in res["notifications"]:
            self.assertTrue(n["isRead"])

    def test_09_idor_protection(self):
        # Company owner has 1 unread notification
        st, res = self.request("GET", "/api/notifications", token="user_company_owner_token")
        notif_id = res["notifications"][0]["id"]
        
        # Author tries to read company owner's notification
        st, res = self.request("POST", "/api/notifications/read", {"notificationId": notif_id}, token="user_author_token")
        self.assertEqual(st, 403)
        self.assertEqual(res["error"], "Отказано в доступе")
        
        # Unknown notification
        st, res = self.request("POST", "/api/notifications/read", {"notificationId": "notfound"}, token="user_author_token")
        self.assertEqual(st, 404)

if __name__ == '__main__':
    unittest.main()
