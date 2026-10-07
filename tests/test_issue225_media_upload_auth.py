"""
Media upload requires a signed-in user and is rate limited (Issue #225).
"""
import base64
import json
import os
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

import server
from tests.auth_helpers import upload_auth_headers
from server import create_server, init_db, reset_media_upload_limiters

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)
SVG_ENDING_WITH_NEWLINE = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40">'
    b'<rect width="40" height="40" fill="#2563eb"/></svg>\n'
)


class TestMediaUploadAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "media.db")
        cls.media_dir = os.path.join(cls.temp_dir, "media")
        os.makedirs(cls.media_dir)
        init_db(cls.db_path, seed=False).close()
        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path,
                                  directory=os.path.join(PROJECT_ROOT, "frontend", "public"))
        cls.httpd.media_dir = cls.media_dir
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
        reset_media_upload_limiters()

    def upload(self, body, content_type="image/png", auth=True):
        headers = {"Content-Type": content_type}
        if auth:
            headers.update(upload_auth_headers(self.db_path))
        req = urllib.request.Request(self.base + "/api/media/upload", data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, dict(resp.headers), json.loads(resp.read())
        except urllib.error.HTTPError as e:
            payload = json.loads(e.read() or b"{}")
            e.close()
            return e.code, dict(e.headers), payload

    def test_guest_upload_is_rejected_and_not_stored(self):
        status, _, body = self.upload(TINY_PNG, auth=False)
        self.assertEqual(status, 401)
        self.assertTrue(body.get("requireAuth"))
        self.assertEqual(os.listdir(self.media_dir), [])

    def test_signed_in_upload_is_stored(self):
        status, _, body = self.upload(TINY_PNG)
        self.assertEqual(status, 200, body)
        self.assertTrue(body["url"].startswith("/media/"))

    def test_uploads_are_rate_limited(self):
        for _ in range(server.MEDIA_UPLOAD_USER_LIMITER.max_per_hour):
            self.assertEqual(self.upload(TINY_PNG)[0], 200)
        status, headers, body = self.upload(TINY_PNG)
        self.assertEqual(status, 429)
        self.assertTrue(int(headers.get("Retry-After", "0")) > 0)

    def test_multipart_upload_keeps_file_bytes_intact(self):
        boundary = "----scboundary"
        body = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"a.svg\"\r\n"
            f"Content-Type: image/svg+xml\r\n\r\n"
        ).encode() + SVG_ENDING_WITH_NEWLINE + f"\r\n--{boundary}--\r\n".encode()
        status, _, data = self.upload(body, content_type=f"multipart/form-data; boundary={boundary}")
        self.assertEqual(status, 200, data)
        with urllib.request.urlopen(self.base + data["url"]) as resp:
            self.assertEqual(resp.read(), SVG_ENDING_WITH_NEWLINE)


    def test_media_dir_environment_variable_is_honoured(self):
        custom = os.path.join(self.temp_dir, "env_media")
        os.environ["MEDIA_DIR"] = custom
        try:
            httpd = create_server(host="127.0.0.1", port=0, db_path=self.db_path,
                                  directory=os.path.join(PROJECT_ROOT, "frontend", "public"))
            httpd.server_close()
        finally:
            del os.environ["MEDIA_DIR"]
        self.assertEqual(httpd.media_dir, custom)


if __name__ == "__main__":
    unittest.main()
