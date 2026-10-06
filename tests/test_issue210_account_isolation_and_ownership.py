import unittest
import os
import json
import sqlite3
import threading
from http.server import HTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sys
sys.path.insert(0, REPO_ROOT)
from server import create_server

class TestIssue210AccountIsolation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_path = os.path.join(REPO_ROOT, "test_issue210.db")
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)
            
        cls.server = create_server(host="localhost", port=0, db_path=cls.db_path, seed=True, allow_demo_login=True)
        cls.port = cls.server.server_address[1]
        cls.server_thread = threading.Thread(target=cls.server.serve_forever)
        cls.server_thread.daemon = True
        cls.server_thread.start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=1.0)
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)

    def req(self, method, path, data=None, token=None):
        url = f"http://localhost:{self.port}{path}"
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
            headers["Cookie"] = f"session_id={token}"
        
        req = Request(url, method=method, headers=headers)
        if data is not None:
            req.add_header("Content-Type", "application/json")
            payload = json.dumps(data).encode("utf-8")
            req.data = payload
        
        try:
            with urlopen(req) as resp:
                body = resp.read().decode("utf-8")
                return resp.status, json.loads(body) if body else None
        except HTTPError as e:
            body = e.read().decode("utf-8")
            try:
                return e.code, json.loads(body)
            except:
                return e.code, body

    def test_isolation_and_ownership(self):
        # Register User A
        st, res = self.req("POST", "/api/auth/login", {"userId": "usera", "name": "User A"})
        self.assertIn(st, [200, 201])
        token_a = res["sessionToken"]
        user_a_id = res["user"]["id"]

        # Register User B
        st, res = self.req("POST", "/api/auth/login", {"userId": "userb", "name": "User B"})
        self.assertIn(st, [200, 201])
        token_b = res["sessionToken"]
        user_b_id = res["user"]["id"]

        # Guest gets 401 on private actions
        st, _ = self.req("GET", "/api/drafts")
        self.assertEqual(st, 401)
        st, _ = self.req("POST", "/api/subscriptions/toggle", {"targetType": "author", "targetId": "some_author"})
        self.assertEqual(st, 401)
        
        # New users have empty lists
        st, res = self.req("GET", "/api/subscriptions", token=token_a)
        self.assertIn(st, [200, 201])
        self.assertTrue(all(len(v) == 0 for v in res.get("subscriptions", {}).values()))
        
        st, res = self.req("GET", "/api/saved", token=token_a)
        self.assertIn(st, [200, 201])
        self.assertEqual(len(res.get("articles", [])), 0)

        # Independent subscriptions
        st, res = self.req("POST", "/api/subscriptions/toggle", {"targetType": "topic", "targetId": "python", "action": "subscribe"}, token=token_a)
        self.assertIn(st, [200, 201])
        self.assertTrue(res["subscribed"])

        st, res = self.req("GET", "/api/subscriptions", token=token_b)
        self.assertTrue(all(len(v) == 0 for v in res.get("subscriptions", {}).values()))

        # Idempotency
        st, res = self.req("POST", "/api/subscriptions/toggle", {"targetType": "topic", "targetId": "python", "action": "subscribe"}, token=token_a)
        self.assertTrue(res["subscribed"])
        st, res = self.req("GET", "/api/subscriptions", token=token_a)
        self.assertEqual(len(res["subscriptions"]["topics"]), 1)

        # Create article as A
        st, res = self.req("POST", "/api/drafts", {"title": "Article A", "content": "Hello", "tags": [], "materialType": "publication"}, token=token_a)
        article_a_id = res["draft"]["id"]
        
        # Approve manually by inserting direct to moderation_submissions
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO moderation_submissions (id, draft_id, author_id, status, title, publication_settings, article_html, snapshot_hash, created_at, updated_at) VALUES (?, ?, ?, 'approved', 'Title', '{}', '<p>test</p>', 'hash', '2026-10-06T00:00:00Z', '2026-10-06T00:00:00Z')", (article_a_id, article_a_id, user_a_id))
        conn.commit()
        conn.close()

        # A cannot vote for own
        st, res = self.req("POST", f"/api/articles/{article_a_id}/vote", {"value": 1}, token=token_a)
        self.assertEqual(st, 403)
        
        # A cannot report own
        st, res = self.req("POST", f"/api/articles/{article_a_id}/report", {"reason": "spam"}, token=token_a)
        self.assertEqual(st, 403)

        # Like idempotency for B
        st, res = self.req("POST", f"/api/articles/{article_a_id}/like", {"action": "like"}, token=token_b)
        self.assertIn(st, [200, 201])
        self.assertTrue(res["hasLiked"])
        st, res = self.req("POST", f"/api/articles/{article_a_id}/like", {"action": "like"}, token=token_b)
        self.assertTrue(res["hasLiked"])
        
        # Edit profile name for A
        st, res = self.req("POST", "/api/user/profile", {"name": "User A Mod"}, token=token_a)
        self.assertIn(st, [200, 201])
        
        # Verify A's profile
        st, res = self.req("GET", f"/api/users/{user_a_id}")
        self.assertEqual(res["user"]["name"], "User A Mod")
        
        # Create comment as A
        st, res = self.req("POST", f"/api/articles/{article_a_id}/comments", {"content": "comment by a", "commentType": "comment"}, token=token_a)
        self.assertIn(st, [200, 201])
        comment_a_id = res["comment"]["id"]
        
        # Verify comment author name is "User A Mod"
        st, res = self.req("GET", f"/api/articles/{article_a_id}/comments")
        self.assertEqual(res["comments"][0]["authorName"], "User A Mod")
        
        # User B cannot edit A's comment
        st, res = self.req("PUT", f"/api/comments/{comment_a_id}", {"content": "hacked"}, token=token_b)
        self.assertEqual(st, 403)

if __name__ == "__main__":
    unittest.main()
