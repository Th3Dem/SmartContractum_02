"""Request plumbing shared by every handler: DB access, JSON bodies, cookies, sessions, CSRF."""
import datetime
import hmac
import json
import os
import secrets
import sqlite3
import sys
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

from backend import config
from backend.config import FRONTEND_PUBLIC_DIR, MAX_JSON_BODY_BYTES
from backend.db import get_db_connection
from backend.mail import EMAIL_SERVICE
from backend.security import get_capabilities_for_role, is_same_origin


class BaseHandlers:
    def __init__(self, *args, directory=None, **kwargs):
        if directory is None:
            if len(args) >= 3 and hasattr(args[2], "directory"):
                directory = args[2].directory
            else:
                directory = FRONTEND_PUBLIC_DIR
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format, *args):
        """Optionally suppress verbose logging in quiet test environments."""
        if not os.environ.get("SERVER_QUIET"):
            sys.stderr.write(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {format % args}\n")

    def get_db(self) -> sqlite3.Connection:
        db_path = getattr(self.server, "db_path", config.DEFAULT_DB_PATH)
        return get_db_connection(db_path)

    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With, Idempotency-Key, X-User-Id")
        self.send_header("Access-Control-Allow-Credentials", "true")

    def send_json_response(self, status_code: int, data: dict, extra_headers: Optional[List[Tuple[str, str]]] = None):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        if extra_headers:
            for hk, hv in extra_headers:
                self.send_header(hk, hv)
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(payload)

    def read_request_body(self, max_bytes: int = MAX_JSON_BODY_BYTES) -> Optional[bytes]:
        """
        Safely reads the request body from self.rfile with size limits and streaming chunks.
        Validates Content-Length:
        - If missing or 0, returns b"" without error.
        - If invalid, negative, or > max_bytes, returns HTTP 413 Payload Too Large and None.
        - Streams from self.rfile in 64 KB chunks, continuously monitoring total bytes read.
        - If total bytes read exceeds max_bytes, interrupts and returns HTTP 413 Payload Too Large and None.
        """
        cl_header = self.headers.get("Content-Length")
        if cl_header is None:
            return b""

        cl_str = cl_header.strip()
        if not cl_str:
            return b""

        try:
            content_length = int(cl_str)
        except (ValueError, TypeError):
            self.close_connection = True
            self.send_json_response(413, {
                "success": False,
                "error": "Payload Too Large: некорректный заголовок Content-Length"
            }, extra_headers=[("Connection", "close")])
            return None

        if content_length < 0:
            self.close_connection = True
            self.send_json_response(413, {
                "success": False,
                "error": "Payload Too Large: некорректный заголовок Content-Length"
            }, extra_headers=[("Connection", "close")])
            return None

        if content_length == 0:
            return b""

        if content_length > max_bytes:
            self.close_connection = True
            self.send_json_response(413, {
                "success": False,
                "error": f"Payload Too Large: размер тела запроса ({content_length} байт) превышает допустимый лимит ({max_bytes} байт)"
            }, extra_headers=[("Connection", "close")])
            return None

        chunks = []
        total_read = 0
        remaining = content_length
        chunk_size = 64 * 1024

        while remaining > 0:
            to_read = min(remaining, chunk_size)
            chunk = self.rfile.read(to_read)
            if not chunk:
                break
            total_read += len(chunk)
            if total_read > max_bytes:
                self.close_connection = True
                self.send_json_response(413, {
                    "success": False,
                    "error": f"Payload Too Large: размер тела запроса превышает допустимый лимит ({max_bytes} байт)"
                }, extra_headers=[("Connection", "close")])
                return None
            chunks.append(chunk)
            remaining -= len(chunk)

        return b"".join(chunks)

    def read_json_body(
        self,
        max_bytes: int = MAX_JSON_BODY_BYTES,
        allow_empty: bool = False,
        default_empty: Optional[dict] = None
    ) -> Optional[dict]:
        raw_body = self.read_request_body(max_bytes)
        if raw_body is None:
            return None

        if not raw_body or not raw_body.strip():
            if allow_empty:
                return default_empty if default_empty is not None else {}
            self.send_json_response(400, {
                "success": False,
                "error": "Тело запроса не может быть пустым."
            })
            return None

        try:
            data = json.loads(raw_body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self.send_json_response(400, {
                "success": False,
                "error": f"Невалидный JSON: {str(e)}"
            })
            return None
        except Exception as e:
            self.send_json_response(400, {
                "success": False,
                "error": f"Ошибка декодирования запроса: {str(e)}"
            })
            return None

        if not isinstance(data, dict):
            self.send_json_response(400, {
                "success": False,
                "error": "Тело запроса должно быть JSON-объектом."
            })
            return None

        return data

    def is_secure_request(self) -> bool:
        """Determines if the request was made over HTTPS or behind an HTTPS reverse proxy."""
        if self.headers.get("X-Forwarded-Proto", "").strip().lower() == "https":
            return True
        if hasattr(self, "connection") and hasattr(self.connection, "getpeercert"):
            try:
                if self.connection.getpeercert() is not None:
                    return True
            except Exception:
                pass
        return False

    def get_cookie(self, cookie_name: str) -> Optional[str]:
        """Extracts a specific cookie value by name from the Cookie request header."""
        cookie_header = self.headers.get("Cookie", "")
        if not cookie_header:
            return None
        for part in cookie_header.split(";"):
            if "=" in part:
                k, v = part.split("=", 1)
                if k.strip() == cookie_name and v.strip():
                    return v.strip()
        return None

    def create_session(self, conn: sqlite3.Connection, user_id: str, user_name: str, user_role: str) -> Tuple[str, str]:
        """Inserts a new 7-day server session and returns (session_token, csrf_token). Caller commits."""
        token = secrets.token_hex(32)
        csrf_token = secrets.token_hex(32)
        now = datetime.datetime.now(datetime.timezone.utc)
        user_agent = (self.headers.get("User-Agent") or "")[:300] if getattr(self, "headers", None) else ""
        conn.execute("""
            INSERT INTO sessions (token, user_id, user_name, user_role, created_at, expires_at, is_revoked, user_agent)
            VALUES (?, ?, ?, ?, ?, ?, 0, ?)
        """, (token, user_id, user_name, user_role, now.isoformat(), (now + datetime.timedelta(days=7)).isoformat(), user_agent))
        return token, csrf_token

    def session_cookie_headers(self, token: str, csrf_token: str) -> List[Tuple[str, str]]:
        secure_flag = "; Secure" if self.is_secure_request() else ""
        return [
            ("Set-Cookie", f"sc_session={token}; Path=/; HttpOnly; SameSite=Lax{secure_flag}"),
            ("Set-Cookie", f"sc_csrf={csrf_token}; Path=/; SameSite=Lax{secure_flag}"),
        ]

    def cleared_session_cookie_headers(self) -> List[Tuple[str, str]]:
        secure_flag = "; Secure" if self.is_secure_request() else ""
        return [
            ("Set-Cookie", f"sc_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax{secure_flag}"),
            ("Set-Cookie", f"sc_csrf=; Path=/; Max-Age=0; SameSite=Lax{secure_flag}"),
        ]

    def get_session_token(self) -> Optional[str]:
        """
        Extracts session token from Cookie 'sc_session' or Authorization 'Bearer <token>'.
        """
        token = self.get_cookie("sc_session")
        if token:
            return token

        auth_header = self.headers.get("Authorization", "").strip()
        if auth_header:
            if auth_header.lower().startswith("bearer "):
                token = auth_header[7:].strip()
                if token:
                    return token

        return None

    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """
        Extracts authenticated user by validating session token from Cookie or Authorization header against sessions table.
        Rejects revoked or expired sessions and verifies user status against users table (rejects disabled users).
        Ignores X-User-Id and query parameters.
        """
        token = self.get_session_token()
        if not token:
            return None

        conn = None
        try:
            conn = self.get_db()
            cur = conn.cursor()
            try:
                cur.execute("""
                    SELECT s.user_id, s.user_name, s.user_role, s.expires_at, s.is_revoked,
                           p.name AS profile_name, p.avatar AS profile_avatar,
                           u.id AS db_user_id, u.role AS db_user_role, u.status AS user_status
                    FROM sessions s
                    LEFT JOIN users u ON s.user_id = u.id
                    LEFT JOIN user_profiles p ON s.user_id = p.user_id
                    WHERE s.token = ?
                """, (token,))
                row = cur.fetchone()
            except sqlite3.OperationalError:
                cur.execute("""
                    SELECT s.user_id, s.user_name, s.user_role, s.expires_at, s.is_revoked,
                           p.name AS profile_name, p.avatar AS profile_avatar
                    FROM sessions s
                    LEFT JOIN user_profiles p ON s.user_id = p.user_id
                    WHERE s.token = ?
                """, (token,))
                row = cur.fetchone()
        except Exception:
            return None
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

        if not row:
            return None

        if row["is_revoked"] != 0:
            return None

        now_dt = datetime.datetime.now(datetime.timezone.utc)
        try:
            exp_str = str(row["expires_at"]).replace("Z", "+00:00")
            exp_dt = datetime.datetime.fromisoformat(exp_str)
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=datetime.timezone.utc)
            if exp_dt <= now_dt:
                return None
        except Exception:
            return None

        # Verify user status against users table
        if "user_status" in row.keys() and row["db_user_id"] is not None:
            if row["user_status"] == "pending":
                return None
            if row["user_status"] != "active":
                if not getattr(self.server, "allow_demo_login", False):
                    return None
            effective_role = row["db_user_role"] or row["user_role"] or "user"
        else:
            if not getattr(self.server, "allow_demo_login", False):
                return None
            effective_role = row["user_role"] if "user_role" in row.keys() else "user"

        profile_name = row["profile_name"] if ("profile_name" in row.keys() and row["profile_name"]) else None
        effective_name = profile_name.strip() if (profile_name and str(profile_name).strip()) else row["user_name"]
        avatar_val = row["profile_avatar"] if ("profile_avatar" in row.keys() and row["profile_avatar"]) else None

        return {
            "id": row["user_id"],
            "name": effective_name,
            "role": effective_role,
            "avatar": avatar_val,
            "capabilities": get_capabilities_for_role(effective_role)
        }

    def is_moderator_or_admin(self, user: Optional[Dict[str, Any]]) -> bool:
        if not user:
            return False
        return user.get("role") in ("moderator", "admin")

    def verify_csrf_token(self) -> bool:
        """
        Validates CSRF protection for state-changing requests (POST, PUT, DELETE, PATCH).
        Rejects requests with mismatched Origin/Referer or invalid CSRF token when ambient cookie is used.
        """
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        host_header = self.headers.get("Host", "").strip()
        origin_header = self.headers.get("Origin", "").strip()
        referer_header = self.headers.get("Referer", "").strip()

        if host_header:
            if origin_header and not is_same_origin(origin_header, host_header):
                self.send_json_response(403, {
                    "success": False,
                    "error": "CSRF verification failed: Mismatched Origin"
                })
                return False
            elif not origin_header and referer_header and not is_same_origin(referer_header, host_header):
                self.send_json_response(403, {
                    "success": False,
                    "error": "CSRF verification failed: Mismatched Referer"
                })
                return False

        # /api/auth/login establishes the session and issues CSRF token;
        # Registration and verification are unauthenticated onboarding endpoints
        # requiring Origin/Referer check above, but no pre-existing CSRF token.
        if path in (
            "/api/auth/login",
            "/api/auth/register",
            "/api/auth/verify-email",
            "/api/auth/resend-code",
            "/api/auth/forgot-password",
            "/api/auth/reset-password"
        ):
            return True

        # Non-ambient authorization header bypasses CSRF token requirement
        auth_header = self.headers.get("Authorization", "").strip()
        if auth_header.lower().startswith("bearer "):
            return True

        # Explicit test bypass if allowed on server
        if getattr(self.server, "allow_csrf_bypass", False) and self.headers.get("X-Test-Bypass-CSRF") == "1":
            return True

        # Ambient cookie session validation
        session_cookie = self.get_cookie("sc_session")
        if session_cookie:
            csrf_cookie = self.get_cookie("sc_csrf")
            csrf_header = self.headers.get("X-CSRF-Token", "").strip()

            enforce = getattr(self.server, "enforce_csrf", False)
            if enforce:
                if not csrf_cookie or not csrf_header or not hmac.compare_digest(csrf_cookie, csrf_header):
                    self.send_json_response(403, {
                        "success": False,
                        "error": "CSRF verification failed: Invalid or missing CSRF token"
                    })
                    return False
            elif csrf_header:
                if not csrf_cookie or not hmac.compare_digest(csrf_cookie, csrf_header):
                    self.send_json_response(403, {
                        "success": False,
                        "error": "CSRF verification failed: Invalid or missing CSRF token"
                    })
                    return False

        return True

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()


    def mailer(self) -> "EmailService":
        return getattr(self.server, "email_service", None) or EMAIL_SERVICE
