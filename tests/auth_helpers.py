"""
Authentication helpers for tests that call endpoints requiring a signed-in user.
"""
import datetime
import secrets
import sqlite3

from server import create_user

_TOKENS = {}


def upload_auth_headers(db_path: str) -> dict:
    """
    Authorization header of an active, email-confirmed user with a server session in db_path.
    Media upload requires a signed-in user; a Bearer token needs no CSRF token.
    The user and session are created once per database.
    """
    token = _TOKENS.get(db_path)
    if token is None:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute("SELECT id FROM users WHERE login_normalized = 'media_uploader'").fetchone()
            if row:
                user_id = row["id"]
            else:
                user_id = create_user(conn, "media_uploader", "media_uploader@example.com",
                                      "Uploader-pass-1", email_verified=True)["id"]
            token = secrets.token_hex(32)
            now = datetime.datetime.now(datetime.timezone.utc)
            with conn:
                conn.execute("""
                    INSERT INTO sessions (token, user_id, user_name, user_role, created_at, expires_at, is_revoked)
                    VALUES (?, ?, 'media_uploader', 'user', ?, ?, 0)
                """, (token, user_id, now.isoformat(), (now + datetime.timedelta(days=1)).isoformat()))
        finally:
            conn.close()
        _TOKENS[db_path] = token
    return {"Authorization": f"Bearer {token}"}
