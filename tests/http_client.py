"""
Small HTTP client with its own cookie jar for tests that drive a real server instance.
"""
import http.cookiejar
import json
import urllib.error
import urllib.request


class Client:
    """A browser stand-in: keeps cookies and sends the CSRF header like the frontend does."""

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

    def login(self, login, password):
        status, _ = self.request("POST", "/api/auth/login", {"login": login, "password": password})
        assert status == 200, (login, status)
        return self


def submission_payload(draft_id, title="Разбор оптимизации газа в Solidity", material_type="publication"):
    """A publication or question that passes server validation."""
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
