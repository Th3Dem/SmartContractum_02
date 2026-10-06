#!/usr/bin/env python3
"""
server.py - SmartContractum web server entry point.

The application lives in the backend/ package:
- backend/config.py, db.py, users.py, security.py, mail.py, content.py, submissions.py, seeds.py, storage.py
- backend/handlers/: HTTP handlers grouped by product area, assembled in backend/app.py

This module loads the local .env (only when run as a script), re-exports the public names
of the package for existing imports such as `from server import init_db`, and parses the
command line.

Usage:
    python3 server.py --port 8000 [--host 127.0.0.1] [--db path] [--seed]
    python3 server.py --send-test-email ADDRESS
"""

import argparse
import os
import sys
import types

from backend.config import load_env_file

# Secrets and mail settings live in a git-ignored .env next to this file. Only a real
# server start reads it, so importing the module (tests) never picks up production credentials.
# It must run before the backend modules below read their settings at import time.
if __name__ == "__main__":
    load_env_file(os.environ.get("SC_ENV_FILE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from backend import config
from backend.config import *  # noqa: F401,F403
from backend.content import *  # noqa: F401,F403
from backend.storage import *  # noqa: F401,F403
from backend.security import *  # noqa: F401,F403
from backend.mail import *  # noqa: F401,F403
from backend.users import *  # noqa: F401,F403
from backend.seeds import *  # noqa: F401,F403
from backend.db import *  # noqa: F401,F403
from backend.submissions import *  # noqa: F401,F403
from backend.app import *  # noqa: F401,F403

# Settings that callers reassign at runtime, e.g. `server.DEFAULT_DB_PATH = ...` in tests.
# The backend reads them from backend.config at call time, so assignments are forwarded there.
_FORWARDED_SETTINGS = ("DEFAULT_DB_PATH", "MEDIA_DIR")


class _ServerModule(types.ModuleType):
    def __setattr__(self, name, value):
        if name in _FORWARDED_SETTINGS:
            setattr(config, name, value)
        super().__setattr__(name, value)


sys.modules[__name__].__class__ = _ServerModule


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Antigravity Moderation Server")
    parser.add_argument("port_pos", nargs="?", type=int, default=None, help="Port to listen on (positional)")
    parser.add_argument("--port", type=int, default=None, help="Port to listen on (default 8000)")
    parser.add_argument("--host", type=str, default=os.environ.get("HOST", "0.0.0.0"), help="Host to bind to (default 0.0.0.0)")
    parser.add_argument("--db", type=str, default=None, help="Path to SQLite database")
    parser.add_argument("--seed", action="store_true", help="Seed database with demo data on startup")
    parser.add_argument("--send-test-email", metavar="ADDRESS", help="Send one test email with the current mail settings and exit")
    args = parser.parse_args()
    if args.send_test_email:
        print(EMAIL_SERVICE.describe())
        if not EMAIL_SERVICE.is_configured():
            sys.exit("SMTP is not configured: set SMTP_HOST, SMTP_USER and SMTP_PASSWORD in .env")
        text, html_body = render_code_email(
            "Тестовое письмо",
            "Если вы видите это письмо, отправка почты SmartContractum настроена правильно.",
            "123456",
            "Это проверочное письмо, код в нем ненастоящий."
        )
        try:
            EMAIL_SERVICE.deliver_smtp(args.send_test_email, "Проверка почты SmartContractum", text, html_body)
        except Exception as e:
            sys.exit(f"Delivery failed: {type(e).__name__}: {e}")
        print(f"Test email sent to {args.send_test_email}")
        sys.exit(0)
    port = args.port or args.port_pos or int(os.environ.get("PORT", 8000))
    run_server(host=args.host, port=port, db_path=args.db, seed=args.seed)
