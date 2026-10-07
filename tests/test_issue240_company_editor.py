"""
Company profile: same look as the person profile and editing in settings (Issue #240).

The editor in settings.html#company=<id> uses the existing company API; these tests check that
the API answers what the editor relies on and that the page markup matches the contract.
"""
import datetime
import os
import re
import shutil
import sqlite3
import tempfile
import threading
import unittest

from server import create_server, create_user, init_db, reset_login_rate_limiter
from tests.http_client import Client

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PUBLIC = os.path.join(PROJECT_ROOT, "frontend", "public")
PASSWORD = "Company-edit-1"


def read(*parts):
    with open(os.path.join(PUBLIC, *parts), "r", encoding="utf-8") as f:
        return f.read()


class TestCompanyEditorMarkup(unittest.TestCase):
    def test_company_page_has_no_dialog_and_links_to_settings(self):
        html, js = read("company.html"), read("js", "company.js")
        for marker in ("editDialog", "editForm", "co-dialog"):
            self.assertNotIn(marker, html)
        for fn in ("openEdit", "submitEdit", "closeEdit"):
            self.assertNotIn(fn, js)
        self.assertIn('href="settings.html#company=${encodeURIComponent(c.id)}"', js)
        self.assertIn('class="co-stats" id="companyStats"', html)
        hero = html[html.index('<section class="co-card co-hero">'):html.index('<div class="co-layout">')]
        self.assertIn('id="companyStats"', hero, "statistics live inside the hero card like on the profile")

    def test_settings_has_the_company_editor(self):
        html, js = read("settings.html"), read("js", "settings.js")
        section = html[html.index('id="tabContentCompany"'):html.index('id="tabContentAppearance"')]
        for element in ('id="companyForm"', 'id="coName"', 'id="coSpecialization"', 'id="coDescription"',
                        'id="coAbout"', 'id="coWebsite"', 'id="coDirections"', 'id="coSaveBar"',
                        'id="btnSaveCompany"', 'id="btnCoLogoEdit"', 'id="btnCoCoverEdit"', 'id="coProgress"'):
            self.assertIn(element, section)
        for limit, field in (("120", "coName"), ("120", "coSpecialization"), ("300", "coDescription"),
                             ("8000", "coAbout"), ("300", "coWebsite")):
            self.assertRegex(section, rf'id="{field}"[^>]*maxlength="{limit}"', f"{field} matches the server limit")
        self.assertIn("company=", js)
        self.assertIn("'PUT', '/api/companies/'", js)
        self.assertIn("/media`", js)
        self.assertIn("data.fieldErrors", js)
        self.assertIn('href="#company=${encodeURIComponent(c.id)}"', js, "owners open the editor from the list")

    def test_no_em_dashes_or_emojis(self):
        for name in (("company.html",), ("settings.html",), ("js", "company.js"), ("js", "settings.js"),
                     ("css", "company.css"), ("css", "settings.css")):
            text = read(*name)
            self.assertNotIn(chr(0x2014), text, name)
            self.assertFalse(re.search("[\U0001F300-\U0001FAFF]", text), name)


class TestCompanyEditorApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["SERVER_QUIET"] = "1"
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "company.db")
        init_db(cls.db_path, seed=False).close()
        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        owner = create_user(conn, "owner", "owner@example.com", PASSWORD, email_verified=True)["id"]
        create_user(conn, "stranger", "stranger@example.com", PASSWORD, email_verified=True)
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        conn.execute("""
            INSERT INTO companies (id, name, description, specialization, website, logo, directions, owner_id, is_verified, created_at, updated_at)
            VALUES ('lab', 'Лаборатория', 'Коротко', 'Аудит', '', NULL, '[]', ?, 0, ?, ?)
        """, (owner, now, now))
        conn.commit()
        conn.close()
        cls.httpd = create_server(host="127.0.0.1", port=0, db_path=cls.db_path,
                                  media_dir=os.path.join(cls.temp_dir, "media"),
                                  directory=PUBLIC, allow_demo_login=False, enforce_csrf=True)
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

    def test_editor_round_trip(self):
        owner = Client(self.base).login("owner", PASSWORD)
        _, profile = owner.request("GET", "/api/companies/lab/profile")
        self.assertTrue(profile["company"]["canEdit"], "the editor opens only when canEdit is true")
        payload = {"name": "Лаборатория Газа", "specialization": "Аудит и газ", "description": "Коротко о нас",
                   "about": "Первый абзац\n\nВторой абзац", "website": "lab.example",
                   "directions": ["pksc-architecture", "audit-and-verification"]}
        status, body = owner.request("PUT", "/api/companies/lab", payload)
        self.assertEqual(status, 200, body)
        _, profile = Client(self.base).request("GET", "/api/companies/lab/profile")
        company = profile["company"]
        self.assertEqual((company["name"], company["specialization"], company["website"]),
                         ("Лаборатория Газа", "Аудит и газ", "https://lab.example"))
        self.assertEqual(company["directions"], ["pksc-architecture", "audit-and-verification"])

    def test_field_errors_are_reported_per_field(self):
        owner = Client(self.base).login("owner", PASSWORD)
        status, body = owner.request("PUT", "/api/companies/lab", {"name": "", "specialization": "x" * 121})
        self.assertEqual(status, 400)
        self.assertEqual(set(body["fieldErrors"]), {"name", "specialization"})

    def test_only_the_owner_edits(self):
        stranger = Client(self.base).login("stranger", PASSWORD)
        _, profile = stranger.request("GET", "/api/companies/lab/profile")
        self.assertFalse(profile["company"]["canEdit"])
        self.assertEqual(stranger.request("PUT", "/api/companies/lab", {"name": "Чужое"})[0], 403)


if __name__ == "__main__":
    unittest.main()
