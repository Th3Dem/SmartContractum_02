"""
Avatar and cover for people, logo and cover for companies (Issue #213).
"""
import datetime
import os
import shutil
import sqlite3
import struct
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zlib

from server import create_server, create_user, init_db, reset_login_rate_limiter, reset_media_upload_limiters
from tests.http_client import Client

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PASSWORD = "Media-pass-12"


def png(width, height, shade=0):
    """A valid opaque PNG of the given size; shade changes the bytes so files differ."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    row = b"\x00" + bytes([shade % 256, 120, 200]) * width
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(row * height)) + chunk(b"IEND", b""))


class TestProfileMedia(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "media.db")
        cls.media_dir = os.path.join(cls.temp_dir, "media")
        os.makedirs(cls.media_dir)
        init_db(cls.db_path, seed=False).close()
        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        ids = {login: create_user(conn, login, f"{login}@example.com", PASSWORD, email_verified=True)["id"]
               for login in ("alice", "bob", "carol")}
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        conn.execute("""
            INSERT INTO companies (id, name, description, specialization, website, logo, directions, owner_id, is_verified, created_at, updated_at)
            VALUES ('acme', 'Акме', 'Описание', 'Аудит', '', NULL, '[]', ?, 0, ?, ?)
        """, (ids["alice"], now, now))
        conn.execute("INSERT INTO company_members (company_id, user_id, role, created_at) VALUES ('acme', ?, 'member', ?)", (ids["bob"], now))
        conn.commit()
        conn.close()
        cls.ids = ids
        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path, media_dir=cls.media_dir,
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

    def client(self, login=None):
        c = Client(self.base)
        return c.login(login, PASSWORD) if login else c

    def upload(self, client, data):
        req = urllib.request.Request(self.base + "/api/media/upload", data=data, method="POST",
                                     headers={"Content-Type": "image/png"})
        for c in client.jar:
            if c.name == "sc_csrf":
                req.add_header("X-CSRF-Token", c.value)
        with client.opener.open(req, timeout=10) as resp:
            import json
            return json.loads(resp.read())["url"]

    def test_person_sets_and_removes_avatar_and_cover_independently(self):
        alice = self.client("alice")
        avatar = self.upload(alice, png(200, 200, 1))
        cover = self.upload(alice, png(900, 300, 2))
        self.assertEqual(alice.request("POST", "/api/user/profile-media", {"kind": "avatar", "url": avatar})[0], 200)
        status, body = alice.request("POST", "/api/user/profile-media",
                                     {"kind": "cover", "url": cover, "focal": {"x": 0.5, "y": 0.4}})
        self.assertEqual(status, 200, body)
        self.assertEqual(body["coverFocal"], {"x": 0.5, "y": 0.4})

        _, profile = self.client().request("GET", f"/api/users/{self.ids['alice']}")
        self.assertEqual((profile["profile"]["avatar"], profile["profile"]["cover"]), (avatar, cover))

        _, after = alice.request("POST", "/api/user/profile-media", {"kind": "cover", "remove": True})
        self.assertEqual((after["avatar"], after["cover"]), (avatar, None), "removing the cover keeps the avatar")
        _, status_body = alice.request("GET", "/api/auth/status")
        self.assertEqual(status_body["user"]["avatar"], avatar, "the header gets the current avatar")

    def test_someone_elses_upload_cannot_be_assigned(self):
        alice_file = self.upload(self.client("alice"), png(300, 300, 3))
        bob = self.client("bob")
        status, _ = bob.request("POST", "/api/user/profile-media", {"kind": "avatar", "url": alice_file})
        self.assertEqual(status, 403)
        status, _ = bob.request("POST", "/api/user/profile", {"avatar": alice_file})
        self.assertEqual(status, 403, "the older profile endpoint enforces the same rule")

    def test_same_bytes_uploaded_by_two_people_work_for_both(self):
        data = png(300, 300, 4)
        alice_url = self.upload(self.client("alice"), data)
        carol = self.client("carol")
        carol_url = self.upload(carol, data)
        self.assertEqual(alice_url, carol_url)
        self.assertEqual(carol.request("POST", "/api/user/profile-media", {"kind": "avatar", "url": carol_url})[0], 200)

    def test_invalid_images_and_paths_are_rejected(self):
        alice = self.client("alice")
        small = self.upload(alice, png(300, 100, 5))
        for payload in (
            {"kind": "cover", "url": small},
            {"kind": "cover", "url": "https://example.com/x.png"},
            {"kind": "avatar", "url": "/media/../server.py"},
            {"kind": "avatar", "url": "/media/missing.png"},
            {"kind": "avatar", "url": "/media/icon.svg"},
            {"kind": "banner", "url": small},
            {"kind": "cover", "url": small, "focal": {"x": 2, "y": 0}},
        ):
            status, _ = alice.request("POST", "/api/user/profile-media", payload)
            self.assertEqual(status, 400, payload)
        self.assertEqual(self.client().request("POST", "/api/user/profile-media", {"kind": "avatar", "url": small})[0], 401)

    def test_company_images_are_managed_by_the_owner_only(self):
        alice = self.client("alice")
        logo = self.upload(alice, png(256, 256, 6))
        cover = self.upload(alice, png(1200, 400, 7))
        self.assertEqual(alice.request("POST", "/api/companies/acme/media", {"kind": "logo", "url": logo})[0], 200)
        status, body = alice.request("POST", "/api/companies/acme/media", {"kind": "cover", "url": cover})
        self.assertEqual((status, body["logo"], body["cover"]), (200, logo, cover))
        _, profile = self.client().request("GET", "/api/companies/acme/profile")
        self.assertEqual((profile["company"]["logo"], profile["company"]["cover"]), (logo, cover))

        bob = self.client("bob")
        bob_logo = self.upload(bob, png(256, 256, 8))
        self.assertEqual(bob.request("POST", "/api/companies/acme/media", {"kind": "logo", "url": bob_logo})[0], 403, "members do not edit")
        self.assertEqual(self.client().request("POST", "/api/companies/acme/media", {"kind": "logo", "remove": True})[0], 401)
        self.assertEqual(alice.request("POST", "/api/companies/ghost/media", {"kind": "logo", "remove": True})[0], 404)

        _, after = alice.request("POST", "/api/companies/acme/media", {"kind": "logo", "remove": True})
        self.assertEqual((after["logo"], after["cover"]), (None, cover))


if __name__ == "__main__":
    unittest.main()
