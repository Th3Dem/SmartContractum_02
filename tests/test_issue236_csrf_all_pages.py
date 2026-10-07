"""
Every page sends the CSRF token with requests that change data (Issue #236).

The interceptor used to live only in js/config.js, which several pages do not load, so saving on
settings.html failed with "CSRF verification failed" on a server with CSRF enforced.
"""
import glob
import json
import os
import re
import subprocess
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PUBLIC = os.path.join(PROJECT_ROOT, "frontend", "public")
AUTH_JS = os.path.join(PUBLIC, "js", "auth.js")
INTERCEPTOR_SCRIPTS = ("js/auth.js", "js/config.js")


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class TestCsrfOnEveryPage(unittest.TestCase):
    def test_every_page_loads_a_script_that_adds_the_token(self):
        for path in glob.glob(os.path.join(PUBLIC, "*.html")):
            name = os.path.basename(path)
            if name.startswith("_") or name == "mobile.html":  # mobile.html only frames other pages
                continue
            html = read(path)
            scripts = re.findall(r'<script[^>]+src="([^"]+)"', html)
            self.assertTrue(any(s in INTERCEPTOR_SCRIPTS for s in scripts),
                            f"{name} loads neither auth.js nor config.js, its POST requests would lack X-CSRF-Token")

    def run_interceptor(self, requests):
        """Runs auth.js's interceptor in Node with a fake page and returns the headers each request got."""
        script = """
const fs = require('fs');
const sent = [];
global.window = {
  location: { href: 'http://site.test/settings.html', origin: 'http://site.test' },
  fetch: (input, init) => { sent.push(Object.fromEntries(new Headers((init && init.headers) || {}).entries())); return Promise.resolve(); }
};
global.document = { cookie: 'theme=dark; sc_csrf=tok%2B123' };
const source = fs.readFileSync(process.argv[1], 'utf8');
// Only the interceptor block: everything before the auth dialog module
eval(source.slice(0, source.indexOf('(function() {\\n  if (window.SCAuth')));
for (const [url, init] of JSON.parse(process.argv[2])) window.fetch(url, init);
console.log(JSON.stringify(sent));
"""
        out = subprocess.run(["node", "-e", script, AUTH_JS, json.dumps(requests)],
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def test_interceptor_adds_the_cookie_value_to_changing_requests_only(self):
        sent = self.run_interceptor([
            ["/api/user/profile", {"method": "POST", "headers": {"Content-Type": "application/json"}}],
            ["/api/auth/sessions/revoke", {"method": "post"}],
            ["/api/user/settings", {"method": "GET"}],
            ["https://other.test/api", {"method": "POST"}],
            ["/api/x", {"method": "DELETE", "headers": {"X-CSRF-Token": "own"}}],
        ])
        self.assertEqual(sent[0].get("x-csrf-token"), "tok+123")
        self.assertEqual(sent[0].get("content-type"), "application/json", "existing headers are kept")
        self.assertEqual(sent[1].get("x-csrf-token"), "tok+123")
        self.assertNotIn("x-csrf-token", sent[2], "reads do not need the token")
        self.assertNotIn("x-csrf-token", sent[3], "the token never goes to another site")
        self.assertEqual(sent[4].get("x-csrf-token"), "own", "an explicit header wins")

    def test_installed_once_together_with_config_js(self):
        auth = read(AUTH_JS)
        config = read(os.path.join(PUBLIC, "js", "config.js"))
        self.assertIn("window.__sc_csrf_interceptor_installed", auth)
        self.assertIn("window.__sc_csrf_interceptor_installed", config)


if __name__ == "__main__":
    unittest.main()
