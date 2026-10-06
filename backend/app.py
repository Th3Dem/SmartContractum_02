"""HTTP handler assembly and server factory."""
import http.server
import os
import sys
from typing import Optional

from backend import config
from backend.config import FRONTEND_PUBLIC_DIR
from backend.db import init_db
from backend.mail import EMAIL_SERVICE
from backend.handlers.base import BaseHandlers
from backend.handlers.routing import RoutingHandlers
from backend.handlers.auth import AuthHandlers
from backend.handlers.account import AccountHandlers
from backend.handlers.profiles import ProfilesHandlers
from backend.handlers.profile_activity import ProfileActivityHandlers
from backend.handlers.articles import ArticlesHandlers
from backend.handlers.comments import CommentsHandlers
from backend.handlers.engagement import EngagementHandlers
from backend.handlers.subscriptions import SubscriptionsHandlers
from backend.handlers.communities import CommunitiesHandlers
from backend.handlers.moderation import ModerationHandlers
from backend.handlers.notifications import NotificationsHandlers
from backend.handlers.drafts import DraftsHandlers
from backend.handlers.media import MediaHandlers


class ModerationRequestHandler(
    BaseHandlers,
    RoutingHandlers,
    AuthHandlers,
    AccountHandlers,
    ProfilesHandlers,
    ProfileActivityHandlers,
    ArticlesHandlers,
    CommentsHandlers,
    EngagementHandlers,
    SubscriptionsHandlers,
    CommunitiesHandlers,
    ModerationHandlers,
    NotificationsHandlers,
    DraftsHandlers,
    MediaHandlers,
    http.server.SimpleHTTPRequestHandler,
):
    """
    HTTP Request Handler serving both the static frontend and the Moderation REST API.
    """
    directory = FRONTEND_PUBLIC_DIR


def create_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    db_path: Optional[str] = None,
    directory: Optional[str] = None,
    media_dir: Optional[str] = None,
    seed: Optional[bool] = None,
    allow_demo_login: Optional[bool] = None,
    enforce_csrf: Optional[bool] = None,
    allow_csrf_bypass: bool = False
) -> http.server.ThreadingHTTPServer:
    """
    Creates and returns a ThreadingHTTPServer instance with initialized database and media storage.
    """
    init_db(db_path, seed=seed)
    server_address = (host, port)
    httpd = http.server.ThreadingHTTPServer(server_address, ModerationRequestHandler)
    httpd.db_path = db_path or os.environ.get("MODERATION_DB_PATH", config.DEFAULT_DB_PATH)
    httpd.directory = directory or FRONTEND_PUBLIC_DIR
    httpd.media_dir = media_dir or os.environ.get("MEDIA_DIR", config.MEDIA_DIR)
    os.makedirs(httpd.media_dir, exist_ok=True)

    if allow_demo_login is None:
        if os.environ.get("ALLOW_DEMO_LOGIN") == "1":
            allow_demo_login = True
        elif os.environ.get("ALLOW_DEMO_LOGIN") == "0":
            allow_demo_login = False
        elif "unittest" in sys.modules:
            allow_demo_login = True
        else:
            allow_demo_login = False

    if enforce_csrf is None:
        if os.environ.get("ENFORCE_CSRF") == "1":
            enforce_csrf = True
        elif os.environ.get("ENFORCE_CSRF") == "0":
            enforce_csrf = False
        elif "unittest" in sys.modules:
            enforce_csrf = False
        else:
            enforce_csrf = True

    httpd.allow_demo_login = bool(allow_demo_login)
    httpd.enforce_csrf = bool(enforce_csrf)
    httpd.allow_csrf_bypass = bool(allow_csrf_bypass)
    return httpd


def run_server(host: str = "0.0.0.0", port: int = 8000, db_path: Optional[str] = None, seed: bool = False):
    """
    Starts the server loop listening on host:port.
    """
    httpd = create_server(host=host, port=port, db_path=db_path, seed=seed, allow_demo_login=False, enforce_csrf=True)
    print(f"Antigravity Moderation Server running at http://{host}:{port}/")
    print(f"Serving static files from {httpd.directory}")
    print(f"SQLite database at {httpd.db_path}")
    print(EMAIL_SERVICE.describe())
    if "EMAIL_VERIFICATION_SECRET" not in os.environ:
        print("WARNING: EMAIL_VERIFICATION_SECRET is not set; the public default is used. Set it in .env before production.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()
