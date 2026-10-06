import unittest
import urllib.request
import urllib.error
import json
import threading
import sqlite3
import os
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

import server

class TestIssue209Drafts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_path = os.path.join(REPO_ROOT, "data", "test_drafts.db")
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)
            
        cls.httpd = server.create_server(host="127.0.0.1", port=8105, db_path=cls.db_path, seed=False, enforce_csrf=False)
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever)
        cls.server_thread.daemon = True
        cls.server_thread.start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.server_thread.join()
        if os.path.exists(cls.db_path):
            try:
                os.remove(cls.db_path)
            except Exception:
                pass

    def setUp(self):
        self.base_url = "http://127.0.0.1:8105"
        
        # Setup users in DB manually to bypass rate limiters and auth setup
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        # userA
        cur.execute("INSERT OR IGNORE INTO users (id, login, login_normalized, password_hash, created_at, updated_at) VALUES ('user_a_id', 'userA', 'usera', 'hash', '2020-01-01', '2020-01-01')")
        cur.execute("INSERT OR REPLACE INTO sessions (token, user_id, user_name, created_at, expires_at) VALUES ('tokenA', 'user_a_id', 'userA', '2020-01-01', '2099-01-01')")
        
        # userB
        cur.execute("INSERT OR IGNORE INTO users (id, login, login_normalized, password_hash, created_at, updated_at) VALUES ('user_b_id', 'userB', 'userb', 'hash', '2020-01-01', '2020-01-01')")
        cur.execute("INSERT OR REPLACE INTO sessions (token, user_id, user_name, created_at, expires_at) VALUES ('tokenB', 'user_b_id', 'userB', '2020-01-01', '2099-01-01')")
        
        conn.commit()
        conn.close()
        
        self.users = {
            "userA": "sc_session=tokenA",
            "userB": "sc_session=tokenB"
        }

    def _request(self, method, path, user_key=None, data=None):
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, method=method)
        if user_key and self.users.get(user_key):
            req.add_header("Cookie", self.users[user_key])
        if data is not None:
            req.add_header("Content-Type", "application/json")
            req.data = json.dumps(data).encode("utf-8")
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    def test_01_create_draft(self):
        status, res = self._request("POST", "/api/drafts", "userA", {
            "materialType": "publication",
            "title": "Draft 1",
            "content": "Content 1"
        })
        self.assertIn(status, [200, 201])
        self.assertTrue(res["success"])
        self.assertIn("draft", res)
        self.assertEqual(res["draft"]["title"], "Draft 1")
        self.assertEqual(res["draft"]["revision"], 1)

        # Ensure 401 for guest
        status, res = self._request("POST", "/api/drafts", data={"materialType": "publication"})
        self.assertEqual(status, 401)

    def test_02_get_drafts_list(self):
        # Create drafts
        self._request("POST", "/api/drafts", "userA", {
            "materialType": "publication",
            "title": "Draft 1"
        })
        self._request("POST", "/api/drafts", "userA", {
            "materialType": "question",
            "title": "Draft 2"
        })

        status, res = self._request("GET", "/api/drafts", "userA")
        self.assertEqual(status, 200)
        self.assertTrue(res["success"])
        self.assertGreaterEqual(res["total"], 2)
        
        status, res = self._request("GET", "/api/drafts?material_type=question", "userA")
        self.assertEqual(status, 200)
        self.assertTrue(all(d["materialType"] == "question" for d in res["drafts"]))

    def test_03_idor_protection(self):
        status, res = self._request("POST", "/api/drafts", "userA", {
            "materialType": "publication",
            "title": "IDOR Draft"
        })
        draft_id = res["draft"]["id"]

        # User B tries to read
        status, res = self._request("GET", f"/api/drafts/{draft_id}", "userB")
        self.assertEqual(status, 403)

        # User B tries to update
        status, res = self._request("PUT", f"/api/drafts/{draft_id}", "userB", {
            "title": "Hacked",
            "revision": 1
        })
        self.assertEqual(status, 403)

        # User B tries to delete
        status, res = self._request("DELETE", f"/api/drafts/{draft_id}", "userB")
        self.assertEqual(status, 403)

    def test_04_optimistic_concurrency(self):
        status, res = self._request("POST", "/api/drafts", "userA", {
            "materialType": "publication",
            "title": "OCC Draft"
        })
        draft = res["draft"]
        draft_id = draft["id"]
        server_rev = draft["revision"]

        # Valid update
        status, res = self._request("PUT", f"/api/drafts/{draft_id}", "userA", {
            "title": "Update 1",
            "revision": server_rev
        })
        self.assertEqual(status, 200)
        new_rev = res["draft"]["revision"]
        self.assertEqual(new_rev, server_rev + 1)

        # Conflict update
        status, res = self._request("PUT", f"/api/drafts/{draft_id}", "userA", {
            "title": "Update 2",
            "revision": server_rev # Stale revision
        })
        self.assertEqual(status, 409)
        self.assertFalse(res["success"])
        self.assertEqual(res["error"], "CONFLICT")
        self.assertEqual(res["serverDraft"]["revision"], new_rev)

    def test_05_delete_draft(self):
        status, res = self._request("POST", "/api/drafts", "userA", {
            "materialType": "publication",
            "title": "To Delete"
        })
        draft_id = res["draft"]["id"]

        status, res = self._request("DELETE", f"/api/drafts/{draft_id}", "userA")
        self.assertEqual(status, 200)
        self.assertTrue(res["success"])

        status, res = self._request("GET", f"/api/drafts/{draft_id}", "userA")
        self.assertEqual(status, 404)

if __name__ == '__main__':
    unittest.main()
