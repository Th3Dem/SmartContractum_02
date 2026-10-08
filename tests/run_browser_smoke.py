#!/usr/bin/env python3
"""
tests/run_browser_smoke.py

Runs every browser smoke test module, so CI does not keep a hand-written list
of modules in .github/workflows/ci.yml (Issue #264).

A module takes part when it declares, at module level:

    BROWSER_SMOKE = True

Usage from the repository root:

    RUN_BROWSER_SMOKE=1 python3 -m tests.run_browser_smoke          # all browser modules
    python3 -m tests.run_browser_smoke --list                        # only print the modules

RUN_BROWSER_SMOKE is set to 1 when it is missing, because the browser classes
are skipped without it. PLAYWRIGHT_CDP_URL works as in the modules themselves.
"""

import argparse
import os
import re
import sys
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
MARKER = re.compile(r"^BROWSER_SMOKE\s*=\s*True\s*(#.*)?$", re.M)


def discover_modules(tests_dir=TESTS_DIR):
    """Module names (without .py) of test files that declare BROWSER_SMOKE = True."""
    found = []
    for name in sorted(os.listdir(tests_dir)):
        if not (name.startswith("test_") and name.endswith(".py")):
            continue
        with open(os.path.join(tests_dir, name), encoding="utf-8") as f:
            if MARKER.search(f.read()):
                found.append(name[:-3])
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run all browser smoke test modules.")
    parser.add_argument("--list", action="store_true", help="print the modules and exit")
    parser.add_argument("-q", "--quiet", action="store_true", help="less output")
    args = parser.parse_args(argv)

    modules = discover_modules()
    if args.list:
        print("\n".join(modules))
        return 0
    if not modules:
        print("No browser smoke modules found (BROWSER_SMOKE = True).", file=sys.stderr)
        return 1

    os.environ.setdefault("RUN_BROWSER_SMOKE", "1")
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
    print("Browser smoke modules (%d): %s" % (len(modules), ", ".join(modules)), flush=True)
    suite = unittest.defaultTestLoader.loadTestsFromNames(["tests." + m for m in modules])
    result = unittest.TextTestRunner(verbosity=1 if args.quiet else 2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
