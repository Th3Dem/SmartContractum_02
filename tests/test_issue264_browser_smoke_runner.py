#!/usr/bin/env python3
"""
tests/test_issue264_browser_smoke_runner.py

Issue #264: CI finds browser smoke modules itself (tests/run_browser_smoke.py)
instead of a shared list of modules in .github/workflows/ci.yml.
"""

import os
import re
import shutil
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.run_browser_smoke import TESTS_DIR, discover_modules

CI_YML = os.path.join(PROJECT_ROOT, ".github", "workflows", "ci.yml")

# The modules the browser step ran before the runner existed
KNOWN_BROWSER_MODULES = {
    "test_issue22_sc023_browser_smoke", "test_issue192_profile_mobile_themes_regressions",
    "test_issue244_mobile_header", "test_issue246_article_mobile_actions", "test_issue247_feed_mobile_overflow",
    "test_issue248_index_hero_mobile", "test_issue252_draft_settings_sync", "test_issue254_theme_tokens",
    "test_issue258_drafts_auth_race",
}


class TestIssue264Runner(unittest.TestCase):
    def test_current_browser_modules_are_all_found(self):
        self.assertTrue(KNOWN_BROWSER_MODULES <= set(discover_modules()))

    def test_every_playwright_module_is_marked(self):
        """A module that drives a browser must declare the marker, or CI would silently skip it."""
        unmarked = []
        for name in sorted(os.listdir(TESTS_DIR)):
            if not (name.startswith("test_") and name.endswith(".py")):
                continue
            with open(os.path.join(TESTS_DIR, name), encoding="utf-8") as f:
                text = f.read()
            if re.search(r"^\s*from playwright\.sync_api import", text, re.M) and name[:-3] not in discover_modules():
                unmarked.append(name)
        self.assertEqual(unmarked, [])

    def test_new_module_is_found_and_unmarked_module_is_not(self):
        temp_dir = tempfile.mkdtemp()
        try:
            files = {
                "test_new_browser.py": "import unittest\nBROWSER_SMOKE = True\n",
                "test_with_comment.py": "BROWSER_SMOKE = True  # note\n",
                "test_plain.py": "import unittest\n",
                "test_false.py": "BROWSER_SMOKE = False\n",
                "test_in_text.py": "TEXT = 'BROWSER_SMOKE = True'\n",
                "helper_browser.py": "BROWSER_SMOKE = True\n",
            }
            for name, body in files.items():
                with open(os.path.join(temp_dir, name), "w", encoding="utf-8") as f:
                    f.write(body)
            self.assertEqual(discover_modules(temp_dir), ["test_new_browser", "test_with_comment"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_ci_runs_the_runner_without_a_module_list(self):
        with open(CI_YML, encoding="utf-8") as f:
            ci = f.read()
        step = ci[ci.index("- name: Run browser smoke tests"):]
        step = step[:step.find("\n      - name:", 1)] if "\n      - name:" in step[1:] else step
        self.assertIn("python3 -m tests.run_browser_smoke", step)
        self.assertIsNone(re.search(r"tests/test_[a-z0-9_]+\.py", step), "no hand-written module list")
        self.assertIn("RUN_BROWSER_SMOKE: '1'", step)


if __name__ == "__main__":
    unittest.main()
