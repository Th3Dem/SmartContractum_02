"""User accounts: creation, authentication, legacy migration, administrator bootstrap."""
import datetime
import hashlib
import hmac
import os
import secrets
import sqlite3
from typing import Any, Dict, Optional, Tuple

from backend.security import EMAIL_REGEX, LOGIN_REGEX, hash_password, verify_password


def create_user(
    conn: sqlite3.Connection,
    login: str,
    email: Optional[str],
    password: str,
    role: str = "user",
    status: str = "active",
    email_verified: bool = False,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Creates a persistent user in the SQLite users table.
    Ensures normalized uniqueness for login and non-empty email.
    """
    if not login or not isinstance(login, str) or not login.strip():
        raise ValueError("Login must be a non-empty string")
    login_clean = login.strip()
    login_norm = login_clean.lower()

    if not password or not isinstance(password, str):
        raise ValueError("Password must be a non-empty string")

    if role not in ("user", "moderator", "admin"):
        raise ValueError(f"Invalid role: {role}. Must be 'user', 'moderator', or 'admin'")

    if status not in ("pending", "active", "disabled"):
        raise ValueError(f"Invalid status: {status}. Must be 'pending', 'active', or 'disabled'")

    email_clean = None
    email_norm = None
    if email and isinstance(email, str) and email.strip():
        email_clean = email.strip()
        email_norm = email_clean.lower()

    uid = user_id.strip() if (user_id and isinstance(user_id, str) and user_id.strip()) else f"usr_{secrets.token_hex(8)}"

    pw_hash = hash_password(password)
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    verified_at = now_iso if email_verified else None

    with conn:
        conn.execute("""
            INSERT INTO users (
                id, login, login_normalized, email, email_normalized,
                password_hash, status, role, email_verified_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (uid, login_clean, login_norm, email_clean, email_norm, pw_hash, status, role, verified_at, now_iso, now_iso))

        conn.execute("""
            INSERT OR IGNORE INTO user_profiles (user_id, name, created_at, updated_at)
            VALUES (?, ?, ?, ?)
        """, (uid, login_clean, now_iso, now_iso))

    return {
        "id": uid,
        "login": login_clean,
        "login_normalized": login_norm,
        "email": email_clean,
        "email_normalized": email_norm,
        "role": role,
        "status": status,
        "email_verified_at": verified_at,
        "created_at": now_iso,
        "updated_at": now_iso
    }


def authenticate_user(
    conn: sqlite3.Connection,
    login_or_email: str,
    password: str
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Authenticates user credentials against the users table.
    Returns (user_dict, None) on success, or (None, error_message) on failure.
    Uses constant-time comparison and uniform error messages to prevent enumeration/timing attacks.
    """
    generic_error = "Неверный логин, email или пароль"

    if not login_or_email or not password or not isinstance(login_or_email, str) or not isinstance(password, str):
        return None, generic_error

    ident_norm = login_or_email.strip().lower()
    if not ident_norm:
        return None, generic_error

    cur = conn.cursor()
    cur.execute("""
        SELECT id, login, login_normalized, email, email_normalized,
               password_hash, status, role, email_verified_at, created_at, updated_at
        FROM users
        WHERE login_normalized = ? OR email_normalized = ?
        LIMIT 1
    """, (ident_norm, ident_norm))
    row = cur.fetchone()

    if not row:
        dummy_salt = b"\\x00" * 16
        dummy_hash = hashlib.scrypt(b"dummy_timing_protection", salt=dummy_salt, n=16384, r=8, p=1)
        hmac.compare_digest(dummy_hash, dummy_hash)
        return None, generic_error

    if not verify_password(password, row["password_hash"]):
        return None, generic_error

    if row["status"] != "active":
        if row["status"] == "pending":
            return None, "PENDING_VERIFICATION"
        return None, "Учетная запись заблокирована или ожидает активации"

    user_dict = {
        "id": row["id"],
        "login": row["login"],
        "login_normalized": row["login_normalized"],
        "email": row["email"],
        "email_normalized": row["email_normalized"],
        "status": row["status"],
        "role": row["role"],
        "email_verified_at": row["email_verified_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }
    return user_dict, None


def migrate_legacy_profiles(conn: sqlite3.Connection) -> int:
    """
    Idempotently ensures all existing user_profiles have entries in users table with status='disabled'
    and unguessable password_hash, preserving user_id and preventing attackers from claiming legacy usernames.
    Revokes old demo sessions on migration.
    Returns the count of migrated accounts.
    """
    migrated_count = 0
    with conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT p.user_id, p.name, p.created_at, p.updated_at
            FROM user_profiles p
            LEFT JOIN users u ON p.user_id = u.id
            WHERE u.id IS NULL
        """)
        profiles_to_migrate = cur.fetchall()

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        for prof in profiles_to_migrate:
            u_id = prof["user_id"]
            login_base = str(u_id).strip()
            login_norm = login_base.lower()

            cur.execute("SELECT id FROM users WHERE login_normalized = ?", (login_norm,))
            if cur.fetchone():
                login_norm = f"{login_norm}_{secrets.token_hex(4)}"
                login_base = login_norm

            unguessable_pw = hash_password(secrets.token_urlsafe(48))
            prof_created = prof["created_at"] if "created_at" in prof.keys() and prof["created_at"] else now_iso
            prof_updated = prof["updated_at"] if "updated_at" in prof.keys() and prof["updated_at"] else now_iso

            assigned_role = "admin" if u_id in ("admin", "user_admin") else "moderator" if u_id in ("moderator", "user_moderator") else "user"

            cur.execute("""
                INSERT OR IGNORE INTO users (
                    id, login, login_normalized, email, email_normalized,
                    password_hash, status, role, email_verified_at, created_at, updated_at
                ) VALUES (?, ?, ?, NULL, NULL, ?, 'disabled', ?, NULL, ?, ?)
            """, (u_id, login_base, login_norm, unguessable_pw, assigned_role, prof_created, prof_updated))
            migrated_count += 1

        cur.execute("""
            UPDATE sessions
            SET is_revoked = 1
            WHERE user_id = 'user_demo';
        """)

    return migrated_count


# Password that older versions assigned to the auto-created admin; it is public in the repository history
LEGACY_DEFAULT_ADMIN_PASSWORD = "AdminSecure2026!"


def create_admin(conn: sqlite3.Connection, login: str, email: str, password: Optional[str] = None) -> Tuple[str, str]:
    """
    Creates (or promotes) the administrator account with a random password unless one is given.
    Intended for the trusted server command `server.py --create-admin`; never runs automatically.
    Returns (user_id, password). The password is shown once by the caller and is not stored in clear text.
    """
    login_clean = (login or "").strip()
    if not LOGIN_REGEX.match(login_clean):
        raise ValueError("Логин: 3-30 символов, латинские буквы, цифры, дефис и подчеркивание")
    email_clean = (email or "").strip()
    if not EMAIL_REGEX.match(email_clean):
        raise ValueError("Некорректный email")
    password = password or secrets.token_urlsafe(18)
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    pw_hash = hash_password(password)
    with conn:
        rows = conn.execute("SELECT id, login, login_normalized FROM users WHERE login_normalized = ? OR email_normalized = ?",
                            (login_clean.lower(), email_clean.lower())).fetchall()
        # The email may already belong to another account: promoting that one under a different
        # login would hand admin rights to an account the operator did not name.
        other = next((r for r in rows if r[2] != login_clean.lower()), None)
        if other:
            raise ValueError(f"Email уже принадлежит аккаунту '{other[1]}'. "
                             f"Укажите этот логин или другой email")
        row = rows[0] if rows else None
        if row:
            user_id = row[0]
            conn.execute("""
                UPDATE users SET role = 'admin', status = 'active', password_hash = ?,
                    email_verified_at = COALESCE(email_verified_at, ?), updated_at = ?
                WHERE id = ?
            """, (pw_hash, now_iso, now_iso, user_id))
            conn.execute("UPDATE sessions SET is_revoked = 1 WHERE user_id = ?", (user_id,))
        else:
            user_id = f"usr_{secrets.token_hex(12)}"
            conn.execute("""
                INSERT INTO users (
                    id, login, login_normalized, email, email_normalized,
                    password_hash, status, role, email_verified_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'active', 'admin', ?, ?, ?)
            """, (user_id, login_clean, login_clean.lower(), email_clean, email_clean.lower(),
                  pw_hash, now_iso, now_iso, now_iso))
        conn.execute("""
            INSERT OR IGNORE INTO user_profiles (user_id, name, specialization, created_at, updated_at)
            VALUES (?, 'Администратор', 'Администратор платформы', ?, ?)
        """, (user_id, now_iso, now_iso))
    return user_id, password


def disable_legacy_admin_password(conn: sqlite3.Connection) -> int:
    """
    Earlier versions created an 'admin' account with a password written in the public repository.
    Any account still using it gets an unusable password hash and loses its sessions.
    Returns the number of accounts secured.
    """
    secured = 0
    rows = conn.execute("""
        SELECT id, password_hash FROM users
        WHERE password_hash IS NOT NULL AND (role = 'admin' OR login_normalized = 'admin')
    """).fetchall()
    for row in rows:
        if verify_password(LEGACY_DEFAULT_ADMIN_PASSWORD, row[1]):
            with conn:
                conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", ("!disabled-legacy-default", row[0]))
                conn.execute("UPDATE sessions SET is_revoked = 1 WHERE user_id = ?", (row[0],))
            secured += 1
    return secured
