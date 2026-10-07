"""
After a profile change the author is shown as they are now everywhere (Issue #238):
feed, article page, comments, saved items, the authors list of the feed filters.
"""
import json
import os
import shutil
import sqlite3
import struct
import tempfile
import threading
import unittest
import urllib.request
import zlib

from server import (
    create_admin,
    create_server,
    create_user,
    init_db,
    reset_login_rate_limiter,
    reset_media_upload_limiters,
)
from tests.http_client import Client, submission_payload

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PASSWORD = "Identity-pass-1"


def png(size, shade):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    row = b"\x00" + bytes([shade, 60, 140]) * size
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(row * size)) + chunk(b"IEND", b""))


class TestLiveAuthorIdentity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "identity.db")
        init_db(cls.db_path, seed=False).close()
        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        create_admin(conn, "chief", "chief@example.com", password=PASSWORD)
        cls.author_id = create_user(conn, "vera", "vera@example.com", PASSWORD, email_verified=True)["id"]
        create_user(conn, "reader", "reader@example.com", PASSWORD, email_verified=True)
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
        reset_media_upload_limiters()

    def upload(self, client, data):
        csrf = next(c.value for c in client.jar if c.name == "sc_csrf")
        req = urllib.request.Request(self.base + "/api/media/upload", data=data, method="POST",
                                     headers={"Content-Type": "image/png", "X-CSRF-Token": csrf})
        with client.opener.open(req, timeout=10) as resp:
            return json.loads(resp.read())["url"]

    def test_rename_and_new_photo_show_everywhere(self):
        author = Client(self.base).login("vera", PASSWORD)
        reader = Client(self.base).login("reader", PASSWORD)
        admin = Client(self.base).login("chief", PASSWORD)
        author.request("POST", "/api/user/profile", {"name": "Вера Старая", "specialization": "Аналитик"})

        _, submitted = author.request("POST", "/api/moderation/submit", submission_payload("id-draft", title="Проверка имени автора"))
        article_id = submitted["submissionId"]
        status, _ = admin.request("POST", f"/api/admin/moderation/submissions/{article_id}/decision", {"decision": "approve"})
        self.assertEqual(status, 200)
        status, created = author.request("POST", f"/api/articles/{article_id}/comments",
                                         {"commentType": "comment", "content": "Комментарий автора к своему материалу"})
        self.assertEqual(status, 201, created)
        _, comments = Client(self.base).request("GET", f"/api/articles/{article_id}/comments")
        comment_id = next(c["id"] for c in comments["comments"] if c["userId"] == self.author_id)
        reader.request("POST", f"/api/comments/{comment_id}/save", {})
        reader.request("POST", f"/api/articles/{article_id}/save", {})

        # The profile changes: new name, specialization and photo
        avatar = self.upload(author, png(200, 77))
        self.assertEqual(author.request("POST", "/api/user/profile",
                                        {"name": "Вера Новая", "specialization": "Аудитор"})[0], 200)
        self.assertEqual(author.request("POST", "/api/user/profile-media", {"kind": "avatar", "url": avatar})[0], 200)

        guest = Client(self.base)
        _, feed = guest.request("GET", "/api/articles?limit=50")
        card = next(i for i in feed["items"] if i["id"] == article_id)
        self.assertEqual((card["author"], card["authorInitials"], card["authorRole"], card["authorAvatar"]),
                         ("Вера Новая", "ВН", "Аудитор", avatar))

        _, article = guest.request("GET", f"/api/articles/{article_id}")
        article = article.get("article", article)
        self.assertEqual((article["author"], article["authorAvatar"]), ("Вера Новая", avatar))

        _, comments = guest.request("GET", f"/api/articles/{article_id}/comments")
        own = next(c for c in comments["comments"] if c["id"] == comment_id)
        self.assertEqual((own["authorName"], own["authorAvatar"]), ("Вера Новая", avatar), "older comments follow the profile")

        _, saved_comments = reader.request("GET", "/api/comments/saved")
        self.assertEqual(saved_comments["items"][0]["authorName"], "Вера Новая")
        _, saved = reader.request("GET", "/api/saved?type=all")
        saved_article = next(i for i in saved["items"] if i["id"] == article_id)
        self.assertEqual((saved_article["author"], saved_article["authorAvatar"]), ("Вера Новая", avatar))

        _, profile = guest.request("GET", f"/api/users/{self.author_id}")
        self.assertEqual(profile["profile"]["name"], "Вера Новая")

        # Removing the photo removes it from the comments as well
        author.request("POST", "/api/user/profile-media", {"kind": "avatar", "remove": True})
        _, comments = guest.request("GET", f"/api/articles/{article_id}/comments")
        self.assertIsNone(next(c for c in comments["comments"] if c["id"] == comment_id)["authorAvatar"])


if __name__ == "__main__":
    unittest.main()
