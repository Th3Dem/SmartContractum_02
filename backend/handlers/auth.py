"""Sign-in, sign-out, registration, email verification and credential recovery endpoints."""
import datetime
import hashlib
import hmac
import secrets
import sqlite3
import uuid

from backend.config import MAX_JSON_BODY_BYTES
from backend.mail import render_code_email, send_verification_email
from backend.security import (
    EMAIL_REGEX,
    LOGIN_RATE_LIMITER,
    LOGIN_REGEX,
    RECOVERY_RATE_LIMITER,
    REGISTRATION_RATE_LIMITER,
    RESET_ATTEMPT_LIMITER,
    generate_verification_code,
    get_capabilities_for_role,
    hash_password,
    hash_verification_code,
    mask_email,
    validate_email_format,
    verify_password,
    verify_verification_code,
)
from backend.users import authenticate_user


class AuthHandlers:
    def handle_auth_login(self):
        """POST /api/auth/login authenticates against users table, generates secure session token and CSRF token."""
        data = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
        if data is None:
            return

        client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
        login_or_email = (
            data.get("login")
            or data.get("username")
            or data.get("email")
            or data.get("login_or_email")
            or ""
        )
        if isinstance(login_or_email, str):
            login_or_email = login_or_email.strip()
        else:
            login_or_email = ""

        account_key = login_or_email.lower() if login_or_email else None

        # Rate limiting check
        is_limited, retry_after = LOGIN_RATE_LIMITER.is_rate_limited(client_ip, account_key)
        if is_limited:
            self.send_json_response(429, {
                "success": False,
                "error": "Слишком много неудачных попыток входа. Пожалуйста, подождите.",
                "retryAfter": retry_after
            }, extra_headers=[("Retry-After", str(retry_after))])
            return

        password = data.get("password")
        has_password = bool(password and isinstance(password, str))
        allow_demo = getattr(self.server, "allow_demo_login", False)

        if not has_password and not allow_demo:
            LOGIN_RATE_LIMITER.record_failure(client_ip, account_key)
            self.send_json_response(401, {
                "success": False,
                "error": "Неверный логин, email или пароль"
            })
            return

        if has_password:
            conn = self.get_db()
            try:
                user_record, err_msg = authenticate_user(conn, login_or_email, password)
            finally:
                conn.close()

            if not user_record:
                if err_msg == "PENDING_VERIFICATION":
                    self.send_json_response(403, {
                        "success": False,
                        "error": "Email не подтвержден. Пожалуйста, подтвердите ваш адрес электронной почты.",
                        "requiresEmailVerification": True
                    })
                    return
                LOGIN_RATE_LIMITER.record_failure(client_ip, account_key)
                self.send_json_response(401, {
                    "success": False,
                    "error": err_msg or "Неверный логин, email или пароль"
                })
                return

            LOGIN_RATE_LIMITER.record_success(client_ip, account_key)

            # Rotate session: revoke previous session if present
            old_token = self.get_session_token()
            if old_token:
                conn = self.get_db()
                try:
                    with conn:
                        conn.execute("UPDATE sessions SET is_revoked = 1 WHERE token = ?", (old_token,))
                finally:
                    conn.close()

            user_id = user_record["id"]
            user_role = user_record["role"]

            conn = self.get_db()
            profile_name = None
            profile_avatar = None
            try:
                cur = conn.cursor()
                cur.execute("SELECT name, avatar FROM user_profiles WHERE user_id = ?", (user_id,))
                p_row = cur.fetchone()
                if p_row:
                    profile_name = p_row["name"]
                    profile_avatar = p_row["avatar"]
            finally:
                conn.close()

            user_name = profile_name.strip() if (profile_name and profile_name.strip()) else user_record["login"]

            conn = self.get_db()
            try:
                with conn:
                    token, csrf_token = self.create_session(conn, user_id, user_name, user_role)
            finally:
                conn.close()

            user_dto = {
                "id": user_id,
                "name": user_name,
                "role": user_role,
                "avatar": profile_avatar,
                "capabilities": get_capabilities_for_role(user_role)
            }

            self.send_json_response(200, {
                "success": True,
                "authenticated": True,
                "user": user_dto,
                "csrfToken": csrf_token
            }, extra_headers=self.session_cookie_headers(token, csrf_token))
            return

        # Legacy demo login path (allowed only when allow_demo_login is explicitly True)
        user_id = (data.get("userId") or data.get("user_id") or data.get("authorId") or data.get("author_id") or "user_demo").strip()
        conn_check = self.get_db()
        try:
            cur_check = conn_check.cursor()
            cur_check.execute("SELECT status FROM users WHERE id = ? OR login_normalized = ? LIMIT 1", (user_id, user_id.lower()))
            u_check = cur_check.fetchone()
            if u_check and u_check["status"] == "pending":
                self.send_json_response(403, {
                    "success": False,
                    "error": "Email не подтвержден. Пожалуйста, подтвердите ваш адрес электронной почты.",
                    "requiresEmailVerification": True
                })
                return
        finally:
            conn_check.close()

        user_name = (data.get("name") or ("Демо Пользователь" if user_id == "user_demo" else user_id)).strip()
        role = data.get("role") or ("admin" if user_id in ("admin", "user_admin") else "moderator" if user_id in ("moderator", "user_moderator") else "user")
        user = {"id": user_id, "name": user_name, "role": role}

        token = secrets.token_hex(32)
        csrf_token = secrets.token_hex(32)
        now = datetime.datetime.now(datetime.timezone.utc)
        created_at = now.isoformat()
        expires_at = (now + datetime.timedelta(days=7)).isoformat()

        conn = None
        try:
            conn = self.get_db()
            with conn:
                conn.execute("""
                    INSERT INTO sessions (token, user_id, user_name, user_role, created_at, expires_at, is_revoked)
                    VALUES (?, ?, ?, ?, ?, ?, 0)
                """, (token, user_id, user_name, role, created_at, expires_at))
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

        secure_flag = "; Secure" if self.is_secure_request() else ""
        session_cookie = f"sc_session={token}; Path=/; HttpOnly; SameSite=Lax{secure_flag}"
        csrf_cookie = f"sc_csrf={csrf_token}; Path=/; SameSite=Lax{secure_flag}"

        self.send_json_response(200, {
            "success": True,
            "authenticated": True,
            "user": user,
            "sessionToken": token,
            "csrfToken": csrf_token
        }, extra_headers=[
            ("Set-Cookie", session_cookie),
            ("Set-Cookie", csrf_cookie)
        ])

    def handle_auth_logout(self):
        """POST /api/auth/logout revokes session in DB and clears sc_session and sc_csrf cookies."""
        raw_body = self.read_request_body(MAX_JSON_BODY_BYTES)
        if raw_body is None:
            return
        token = self.get_session_token()
        if token:
            conn = None
            try:
                conn = self.get_db()
                with conn:
                    conn.execute("UPDATE sessions SET is_revoked = 1 WHERE token = ?", (token,))
            finally:
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass

        self.send_json_response(200, {
            "success": True,
            "authenticated": False
        }, extra_headers=self.cleared_session_cookie_headers())

    def handle_auth_register(self):
        """POST /api/auth/register creates pending user and issues email verification challenge."""
        data = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
        if data is None:
            return

        client_ip = self.client_address[0] if self.client_address else "127.0.0.1"

        # Rate limiting by IP
        is_limited, retry_after = REGISTRATION_RATE_LIMITER.is_rate_limited(client_ip)
        if is_limited:
            self.send_json_response(429, {
                "success": False,
                "error": "Слишком много попыток регистрации. Пожалуйста, подождите.",
                "retryAfter": retry_after
            }, extra_headers=[("Retry-After", str(retry_after))])
            return

        raw_login = data.get("login") or ""
        raw_email = data.get("email") or ""
        raw_password = data.get("password") or ""
        raw_name = data.get("name") or ""

        if not isinstance(raw_login, str) or not raw_login.strip():
            self.send_json_response(400, {
                "success": False,
                "error": "Логин обязателен"
            })
            return
        login_clean = raw_login.strip()
        if not LOGIN_REGEX.match(login_clean):
            self.send_json_response(400, {
                "success": False,
                "error": "Логин должен содержать от 3 до 30 символов (буквы, цифры, дефис, подчеркивание)"
            })
            return
        login_norm = login_clean.lower()

        if not isinstance(raw_email, str) or not raw_email.strip():
            self.send_json_response(400, {
                "success": False,
                "error": "Email обязателен"
            })
            return
        email_clean = raw_email.strip()
        if not EMAIL_REGEX.match(email_clean) or len(email_clean) > 254:
            self.send_json_response(400, {
                "success": False,
                "error": "Некорректный email адрес"
            })
            return
        email_norm = email_clean.lower()

        # Rate limiting by email
        is_email_limited, email_retry_after = REGISTRATION_RATE_LIMITER.is_rate_limited(email_norm)
        if is_email_limited:
            self.send_json_response(429, {
                "success": False,
                "error": "Слишком много попыток регистрации с этого адреса. Пожалуйста, подождите.",
                "retryAfter": email_retry_after
            }, extra_headers=[("Retry-After", str(email_retry_after))])
            return

        if not isinstance(raw_password, str) or len(raw_password) < 8:
            self.send_json_response(400, {
                "success": False,
                "error": "Пароль должен содержать не менее 8 символов"
            })
            return

        name_clean = raw_name.strip() if (isinstance(raw_name, str) and raw_name.strip()) else login_clean

        conn = self.get_db()
        try:
            cur = conn.cursor()

            # Check existing email
            cur.execute("SELECT id, login, status FROM users WHERE email_normalized = ? LIMIT 1", (email_norm,))
            existing_email_user = cur.fetchone()

            # Check existing login
            cur.execute("SELECT id, status FROM users WHERE login_normalized = ? LIMIT 1", (login_norm,))
            existing_login_user = cur.fetchone()

            now_dt = datetime.datetime.now(datetime.timezone.utc)
            now_iso = now_dt.isoformat()

            def has_live_challenge(uid: str) -> bool:
                cur.execute("""
                    SELECT 1 FROM email_verifications
                    WHERE user_id = ? AND purpose = 'email_verification' AND status = 'pending' AND expires_at > ?
                    LIMIT 1
                """, (uid, now_iso))
                return cur.fetchone() is not None

            # A pending registration whose code has expired no longer reserves its login
            if (
                existing_login_user
                and existing_login_user["status"] == "pending"
                and not has_live_challenge(existing_login_user["id"])
                and not (existing_email_user and existing_email_user["id"] == existing_login_user["id"])
            ):
                with conn:
                    conn.execute("DELETE FROM user_profiles WHERE user_id = ?", (existing_login_user["id"],))
                    conn.execute("DELETE FROM users WHERE id = ? AND status = 'pending'", (existing_login_user["id"],))
                existing_login_user = None

            if existing_email_user:
                if existing_email_user["status"] == "pending" and has_live_challenge(existing_email_user["id"]):
                    # Never let a second registrant replace the credentials of a registration
                    # that is still waiting for its code: the email owner would activate them.
                    self.send_json_response(409, {
                        "success": False,
                        "error": "Регистрация с этим email уже ожидает подтверждения. Введите код из письма или повторите попытку через 10 минут."
                    })
                    return
                if existing_email_user["status"] == "active":
                    self.send_json_response(400, {
                        "success": False,
                        "error": "Email уже зарегистрирован"
                    })
                    return
                elif existing_email_user["status"] == "disabled":
                    self.send_json_response(400, {
                        "success": False,
                        "error": "Учетная запись заблокирована"
                    })
                    return

                # Existing pending user with same email
                if existing_login_user and existing_login_user["id"] != existing_email_user["id"]:
                    self.send_json_response(400, {
                        "success": False,
                        "error": "Логин уже занят"
                    })
                    return

                user_id = existing_email_user["id"]
                pw_hash = hash_password(raw_password)
                with conn:
                    conn.execute("""
                        UPDATE users
                        SET login = ?, login_normalized = ?, password_hash = ?, updated_at = ?
                        WHERE id = ?
                    """, (login_clean, login_norm, pw_hash, now_iso, user_id))
                    conn.execute("""
                        UPDATE user_profiles
                        SET name = ?, updated_at = ?
                        WHERE user_id = ?
                    """, (name_clean, now_iso, user_id))
            else:
                # New email: check if login is taken
                if existing_login_user:
                    self.send_json_response(400, {
                        "success": False,
                        "error": "Логин уже занят"
                    })
                    return

                user_id = f"usr_{secrets.token_hex(12)}"
                pw_hash = hash_password(raw_password)
                with conn:
                    conn.execute("""
                        INSERT INTO users (
                            id, login, login_normalized, email, email_normalized,
                            password_hash, status, role, email_verified_at, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, 'pending', 'user', NULL, ?, ?)
                    """, (user_id, login_clean, login_norm, email_clean, email_norm, pw_hash, now_iso, now_iso))
                    conn.execute("""
                        INSERT OR REPLACE INTO user_profiles (user_id, name, created_at, updated_at)
                        VALUES (?, ?, ?, ?)
                    """, (user_id, name_clean, now_iso, now_iso))

            # Only the browser holding this token can complete the registration with the emailed code
            registration_token = secrets.token_urlsafe(32)
            with conn:
                conn.execute(
                    "UPDATE users SET registration_token_hash = ? WHERE id = ?",
                    (hashlib.sha256(registration_token.encode("utf-8")).hexdigest(), user_id)
                )

            # Invalidate any existing pending challenges for this user/email
            with conn:
                conn.execute("""
                    UPDATE email_verifications
                    SET status = 'invalidated', updated_at = ?
                    WHERE (user_id = ? OR email = ?) AND purpose = 'email_verification' AND status = 'pending'
                """, (now_iso, user_id, email_clean))

            # Generate 6-digit challenge code
            code = f"{secrets.randbelow(1000000):06d}"
            code_hash = hash_verification_code(code)
            challenge_id = f"verif_{secrets.token_hex(16)}"
            expires_at = (now_dt + datetime.timedelta(seconds=600)).isoformat()
            resend_available_at = (now_dt + datetime.timedelta(seconds=60)).isoformat()

            with conn:
                conn.execute("""
                    INSERT INTO email_verifications (
                        id, user_id, email, purpose, code_hash,
                        attempts_left, expires_at, resend_available_at,
                        status, created_at, updated_at
                    ) VALUES (?, ?, ?, 'email_verification', ?, 5, ?, ?, 'pending', ?, ?)
                """, (challenge_id, user_id, email_clean, code_hash, expires_at, resend_available_at, now_iso, now_iso))

            # Send email
            sent, err_msg = send_verification_email(conn, email_clean, code, login_clean)
            if not sent:
                # An undelivered code must not block a retry of the same registration
                with conn:
                    conn.execute(
                        "UPDATE email_verifications SET status = 'invalidated', updated_at = ? WHERE id = ?",
                        (now_iso, challenge_id)
                    )
                self.send_json_response(500, {
                    "success": False,
                    "error": err_msg or "Не удалось отправить письмо с кодом подтверждения"
                })
                return

            REGISTRATION_RATE_LIMITER.record(client_ip)
            REGISTRATION_RATE_LIMITER.record(email_norm)

            secure_flag = "; Secure" if self.is_secure_request() else ""
            self.send_json_response(201, {
                "success": True,
                "message": "Код подтверждения отправлен на указанный email",
                "email": mask_email(email_clean),
                "registrationToken": registration_token
            }, extra_headers=[(
                "Set-Cookie",
                f"sc_reg={registration_token}; Path=/api/auth; Max-Age=86400; HttpOnly; SameSite=Strict{secure_flag}"
            )])
        finally:
            conn.close()

    def handle_auth_verify_email(self):
        """POST /api/auth/verify-email validates code, activates user account."""
        data = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
        if data is None:
            return

        ident = (
            data.get("email")
            or data.get("login")
            or data.get("identifier")
            or ""
        )
        if isinstance(ident, str):
            ident = ident.strip()
        else:
            ident = ""

        code = data.get("code")
        if isinstance(code, str):
            code = code.strip()
        else:
            code = ""

        if not ident:
            self.send_json_response(400, {
                "success": False,
                "error": "Укажите email или логин"
            })
            return

        if not code:
            self.send_json_response(400, {
                "success": False,
                "error": "Код подтверждения обязателен"
            })
            return

        if len(code) != 6 or not code.isdigit():
            self.send_json_response(400, {
                "success": False,
                "error": "Неверный формат кода подтверждения"
            })
            return

        ident_norm = ident.lower()
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        now_iso = now_dt.isoformat()

        conn = self.get_db()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, login, email, status, registration_token_hash FROM users
                WHERE email_normalized = ? OR login_normalized = ?
                LIMIT 1
            """, (ident_norm, ident_norm))
            user = cur.fetchone()

            if not user:
                self.send_json_response(400, {
                    "success": False,
                    "error": "Пользователь не найден"
                })
                return

            if user["status"] == "disabled":
                self.send_json_response(400, {
                    "success": False,
                    "error": "Учетная запись заблокирована"
                })
                return

            # The code proves control of the mailbox; the registration token proves this browser
            # submitted these credentials. Without both, the email owner could activate an account
            # whose password was chosen by someone else.
            reg_token = data.get("registrationToken") or self.get_cookie("sc_reg") or ""
            expected_hash = user["registration_token_hash"]
            if (
                not isinstance(reg_token, str)
                or not reg_token
                or not expected_hash
                or not hmac.compare_digest(hashlib.sha256(reg_token.encode("utf-8")).hexdigest(), expected_hash)
            ):
                self.send_json_response(400, {
                    "success": False,
                    "error": "Подтвердите email в том же браузере, где проходили регистрацию, или зарегистрируйтесь заново"
                })
                return

            user_id = user["id"]

            # Locate latest pending challenge
            cur.execute("""
                SELECT id, code_hash, attempts_left, expires_at, status
                FROM email_verifications
                WHERE user_id = ? AND purpose = 'email_verification' AND status = 'pending'
                ORDER BY created_at DESC
                LIMIT 1
            """, (user_id,))
            challenge = cur.fetchone()

            if not challenge:
                self.send_json_response(400, {
                    "success": False,
                    "error": "Код подтверждения не найден или устарел"
                })
                return

            challenge_id = challenge["id"]

            # Check expiration
            try:
                exp_dt = datetime.datetime.fromisoformat(challenge["expires_at"].replace("Z", "+00:00"))
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=datetime.timezone.utc)
            except Exception:
                exp_dt = now_dt

            if now_dt >= exp_dt:
                with conn:
                    conn.execute("""
                        UPDATE email_verifications
                        SET status = 'invalidated', updated_at = ?
                        WHERE id = ?
                    """, (now_iso, challenge_id))
                self.send_json_response(400, {
                    "success": False,
                    "error": "Срок действия кода истек"
                })
                return

            attempts_left = challenge["attempts_left"]
            if attempts_left <= 0:
                with conn:
                    conn.execute("""
                        UPDATE email_verifications
                        SET status = 'invalidated', updated_at = ?
                        WHERE id = ?
                    """, (now_iso, challenge_id))
                self.send_json_response(400, {
                    "success": False,
                    "error": "Превышено максимальное число попыток ввода кода"
                })
                return

            # Verify code hash
            is_valid = verify_verification_code(code, challenge["code_hash"])

            if not is_valid:
                new_attempts = attempts_left - 1
                new_status = "invalidated" if new_attempts <= 0 else "pending"
                with conn:
                    conn.execute("""
                        UPDATE email_verifications
                        SET attempts_left = ?, status = ?, updated_at = ?
                        WHERE id = ?
                    """, (new_attempts, new_status, now_iso, challenge_id))

                if new_attempts <= 0:
                    self.send_json_response(400, {
                        "success": False,
                        "error": "Превышено максимальное число попыток. Код заблокирован",
                        "attemptsLeft": 0
                    })
                else:
                    self.send_json_response(400, {
                        "success": False,
                        "error": f"Неверный код подтверждения. Осталось попыток: {new_attempts}",
                        "attemptsLeft": new_attempts
                    })
                return

            # Atomic consumption to prevent race condition
            with conn:
                cur.execute("""
                    UPDATE email_verifications
                    SET status = 'consumed', updated_at = ?
                    WHERE id = ? AND status = 'pending' AND attempts_left > 0
                """, (now_iso, challenge_id))
                if cur.rowcount == 0:
                    self.send_json_response(400, {
                        "success": False,
                        "error": "Код подтверждения уже был использован или устарел"
                    })
                    return

                # Invalidate any other pending challenges for this user
                conn.execute("""
                    UPDATE email_verifications
                    SET status = 'invalidated', updated_at = ?
                    WHERE user_id = ? AND purpose = 'email_verification' AND status = 'pending' AND id != ?
                """, (now_iso, user_id, challenge_id))

                # Activate user
                conn.execute("""
                    UPDATE users
                    SET status = 'active', email_verified_at = ?, updated_at = ?, registration_token_hash = NULL
                    WHERE id = ?
                """, (now_iso, now_iso, user_id))

            self.send_json_response(200, {
                "success": True,
                "message": "Email успешно подтвержден"
            }, extra_headers=[("Set-Cookie", "sc_reg=; Path=/api/auth; Max-Age=0; HttpOnly; SameSite=Strict")])
        finally:
            conn.close()

    def handle_auth_resend_code(self):
        """POST /api/auth/resend-code generates and sends a new code with cooldown and rate limits."""
        data = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
        if data is None:
            return

        ident = (
            data.get("email")
            or data.get("login")
            or data.get("identifier")
            or ""
        )
        if isinstance(ident, str):
            ident = ident.strip()
        else:
            ident = ""

        if not ident:
            self.send_json_response(400, {
                "success": False,
                "error": "Укажите email или логин"
            })
            return

        ident_norm = ident.lower()
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        now_iso = now_dt.isoformat()

        conn = self.get_db()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, login, email, status FROM users
                WHERE email_normalized = ? OR login_normalized = ?
                LIMIT 1
            """, (ident_norm, ident_norm))
            user = cur.fetchone()

            if not user:
                self.send_json_response(404, {
                    "success": False,
                    "error": "Пользователь не найден"
                })
                return

            if user["status"] == "active":
                self.send_json_response(400, {
                    "success": False,
                    "error": "Email уже подтвержден"
                })
                return

            if user["status"] == "disabled":
                self.send_json_response(400, {
                    "success": False,
                    "error": "Учетная запись заблокирована"
                })
                return

            user_id = user["id"]
            user_email = user["email"]
            user_login = user["login"]

            # Check latest challenge cooldown
            cur.execute("""
                SELECT resend_available_at FROM email_verifications
                WHERE user_id = ? AND purpose = 'email_verification'
                ORDER BY created_at DESC
                LIMIT 1
            """, (user_id,))
            last_ch = cur.fetchone()
            if last_ch and last_ch["resend_available_at"]:
                try:
                    resend_at = datetime.datetime.fromisoformat(last_ch["resend_available_at"].replace("Z", "+00:00"))
                    if resend_at.tzinfo is None:
                        resend_at = resend_at.replace(tzinfo=datetime.timezone.utc)
                    if now_dt < resend_at:
                        diff_sec = max(1, int((resend_at - now_dt).total_seconds()) + 1)
                        self.send_json_response(429, {
                            "success": False,
                            "error": f"Повторная отправка возможна через {diff_sec} сек.",
                            "retryAfter": diff_sec
                        }, extra_headers=[("Retry-After", str(diff_sec))])
                        return
                except Exception:
                    pass

            # Hourly rate limit (max 5 per hour per user/email)
            one_hour_ago = (now_dt - datetime.timedelta(hours=1)).isoformat()
            cur.execute("""
                SELECT COUNT(*) AS cnt FROM email_verifications
                WHERE (user_id = ? OR email = ?) AND created_at > ?
            """, (user_id, user_email, one_hour_ago))
            cnt = cur.fetchone()["cnt"]
            if cnt >= 5:
                self.send_json_response(429, {
                    "success": False,
                    "error": "Превышен лимит отправки кодов в час. Пожалуйста, подождите.",
                    "retryAfter": 3600
                }, extra_headers=[("Retry-After", "3600")])
                return

            # Invalidate previous pending challenge
            with conn:
                conn.execute("""
                    UPDATE email_verifications
                    SET status = 'invalidated', updated_at = ?
                    WHERE user_id = ? AND purpose = 'email_verification' AND status = 'pending'
                """, (now_iso, user_id))

            # Generate new code
            code = f"{secrets.randbelow(1000000):06d}"
            code_hash = hash_verification_code(code)
            challenge_id = f"verif_{secrets.token_hex(16)}"
            expires_at = (now_dt + datetime.timedelta(seconds=600)).isoformat()
            resend_available_at = (now_dt + datetime.timedelta(seconds=60)).isoformat()

            with conn:
                conn.execute("""
                    INSERT INTO email_verifications (
                        id, user_id, email, purpose, code_hash,
                        attempts_left, expires_at, resend_available_at,
                        status, created_at, updated_at
                    ) VALUES (?, ?, ?, 'email_verification', ?, 5, ?, ?, 'pending', ?, ?)
                """, (challenge_id, user_id, user_email, code_hash, expires_at, resend_available_at, now_iso, now_iso))

            sent, err_msg = send_verification_email(conn, user_email, code, user_login)
            if not sent:
                self.send_json_response(500, {
                    "success": False,
                    "error": err_msg or "Не удалось отправить письмо с кодом подтверждения"
                })
                return

            self.send_json_response(200, {
                "success": True,
                "message": "Новый код подтверждения отправлен",
                "email": mask_email(user_email)
            })
        finally:
            conn.close()

    def handle_auth_change_password(self):
        """POST /api/auth/change-password: verifies the current password, revokes every session and issues a new one for this device."""
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {"success": False, "error": "Необходима авторизация"})
            return

        data = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
        if data is None:
            return

        current_password = data.get("currentPassword", "")
        new_password = data.get("newPassword", "")
        if not isinstance(new_password, str) or len(new_password) < 8:
            self.send_json_response(400, {"success": False, "error": "Новый пароль должен содержать минимум 8 символов"})
            return

        conn = self.get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],))
            row = cur.fetchone()
            if not row or not verify_password(current_password, row["password_hash"]):
                self.send_json_response(400, {"success": False, "error": "Неверный текущий пароль"})
                return

            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            with conn:
                conn.execute("UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                             (hash_password(new_password), now_iso, user["id"]))
                conn.execute("UPDATE sessions SET is_revoked = 1 WHERE user_id = ?", (user["id"],))
                token, csrf_token = self.create_session(conn, user["id"], user["name"], user["role"])
        finally:
            conn.close()

        self.send_json_response(200, {
            "success": True,
            "message": "Пароль изменен. Остальные устройства отключены от аккаунта.",
            "csrfToken": csrf_token
        }, extra_headers=self.session_cookie_headers(token, csrf_token))

    def handle_auth_change_email(self):
        """POST /api/auth/change-email: re-checks the password and sends a code to the new address; the old address stays active until the code is confirmed."""
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {"success": False, "error": "Необходима авторизация"})
            return

        data = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
        if data is None:
            return

        password = data.get("password", "")
        new_email = data.get("newEmail", "")
        new_email = new_email.strip() if isinstance(new_email, str) else ""
        if not validate_email_format(new_email):
            self.send_json_response(400, {"success": False, "error": "Некорректный формат нового email"})
            return

        limit_key = f"email-change:{user['id']}"
        is_limited, retry_after = RECOVERY_RATE_LIMITER.is_rate_limited(limit_key)
        if is_limited:
            self.send_json_response(429, {
                "success": False,
                "error": "Слишком много запросов на смену email. Пожалуйста, подождите.",
                "retryAfter": retry_after
            }, extra_headers=[("Retry-After", str(retry_after))])
            return

        conn = self.get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT password_hash, email, email_normalized FROM users WHERE id = ?", (user["id"],))
            row = cur.fetchone()
            if not row or not verify_password(password, row["password_hash"]):
                self.send_json_response(400, {"success": False, "error": "Неверный пароль"})
                return
            if row["email_normalized"] == new_email.lower():
                self.send_json_response(400, {"success": False, "error": "Это ваш текущий email"})
                return
            cur.execute("SELECT 1 FROM users WHERE email_normalized = ?", (new_email.lower(),))
            if cur.fetchone():
                self.send_json_response(400, {"success": False, "error": "Указанный email уже используется"})
                return

            code = generate_verification_code()
            now = datetime.datetime.now(datetime.timezone.utc)
            now_iso = now.isoformat()
            challenge_id = str(uuid.uuid4())
            with conn:
                conn.execute("""
                    UPDATE email_verifications SET status = 'invalidated', updated_at = ?
                    WHERE user_id = ? AND purpose = 'email_change' AND status = 'pending'
                """, (now_iso, user["id"]))
                conn.execute("""
                    INSERT INTO email_verifications
                    (id, user_id, email, purpose, code_hash, expires_at, resend_available_at, created_at, updated_at)
                    VALUES (?, ?, ?, 'email_change', ?, ?, ?, ?, ?)
                """, (challenge_id, user["id"], new_email, hash_verification_code(code),
                      (now + datetime.timedelta(minutes=10)).isoformat(),
                      (now + datetime.timedelta(minutes=1)).isoformat(), now_iso, now_iso))
            RECOVERY_RATE_LIMITER.record(limit_key)

            body_text, html_body = render_code_email(
                "Подтвердите новый email",
                "Для вашего аккаунта SmartContractum запрошена смена email на этот адрес. Введите код в настройках аккаунта.",
                code,
                "Код действует 10 минут. Если вы ничего не меняли, просто проигнорируйте это письмо."
            )
            sent, err_msg = self.mailer().send_email(
                conn, new_email, "Подтверждение смены email SmartContractum", body_text,
                extra={"code": code}, html_body=html_body
            )
            if not sent:
                with conn:
                    conn.execute("UPDATE email_verifications SET status = 'invalidated', updated_at = ? WHERE id = ?",
                                 (now_iso, challenge_id))
                self.send_json_response(502, {
                    "success": False,
                    "error": "Не удалось отправить письмо на новый адрес. Текущий email не изменен."
                })
                return
            if row["email"]:
                self.mailer().send_email(
                    conn, row["email"], "Запрос на смену email SmartContractum",
                    "Для вашего аккаунта запрошена смена email. Если это были не вы, срочно смените пароль.\n"
                )
        finally:
            conn.close()

        self.send_json_response(200, {"success": True, "message": "Код подтверждения отправлен на новый email"})

    def handle_auth_verify_change_email(self):
        """POST /api/auth/verify-change-email: confirms the new address with the emailed code."""
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {"success": False, "error": "Необходима авторизация"})
            return

        data = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
        if data is None:
            return
        code = data.get("code", "")
        code = code.strip() if isinstance(code, str) else ""
        if not code:
            self.send_json_response(400, {"success": False, "error": "Код подтверждения обязателен"})
            return

        conn = self.get_db()
        try:
            cur = conn.cursor()
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            cur.execute("""
                SELECT id, email, code_hash, expires_at, attempts_left
                FROM email_verifications
                WHERE user_id = ? AND purpose = 'email_change' AND status = 'pending'
                ORDER BY created_at DESC LIMIT 1
            """, (user["id"],))
            challenge = cur.fetchone()
            if not challenge or challenge["expires_at"] < now_iso:
                self.send_json_response(400, {"success": False, "error": "Код недействителен или просрочен"})
                return

            if not verify_verification_code(code, challenge["code_hash"]):
                new_attempts = challenge["attempts_left"] - 1
                with conn:
                    conn.execute("""
                        UPDATE email_verifications SET attempts_left = ?, status = ?, updated_at = ? WHERE id = ?
                    """, (new_attempts, "invalidated" if new_attempts <= 0 else "pending", now_iso, challenge["id"]))
                self.send_json_response(400, {"success": False, "error": "Неверный код"})
                return

            new_email = challenge["email"]
            try:
                with conn:
                    consumed = conn.execute("""
                        UPDATE email_verifications SET status = 'consumed', updated_at = ?
                        WHERE id = ? AND status = 'pending'
                    """, (now_iso, challenge["id"])).rowcount
                    if consumed == 0:
                        raise sqlite3.IntegrityError("challenge already consumed")
                    conn.execute("""
                        UPDATE users
                        SET email = ?, email_normalized = ?, email_verified_at = ?, updated_at = ?
                        WHERE id = ?
                    """, (new_email, new_email.lower(), now_iso, now_iso, user["id"]))
            except sqlite3.IntegrityError:
                # The address was taken by another account after the code was sent, or the code raced
                self.send_json_response(400, {"success": False, "error": "Не удалось сменить email: адрес уже используется или код уже применен"})
                return
        finally:
            conn.close()

        self.send_json_response(200, {"success": True, "message": "Email успешно изменен"})

    def handle_auth_forgot_password(self):
        """POST /api/auth/forgot-password: always answers neutrally; sends a one-time code only to a verified address."""
        data = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
        if data is None:
            return

        identifier = data.get("identifier") or ""
        identifier = identifier.strip().lower() if isinstance(identifier, str) else ""
        if not identifier:
            self.send_json_response(400, {"success": False, "error": "Не указан email или логин"})
            return

        neutral = {"success": True, "message": "Если учетная запись существует, код для сброса пароля отправлен на привязанный email"}
        client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
        ip_key = f"forgot-ip:{client_ip}"
        is_limited, retry_after = RECOVERY_RATE_LIMITER.is_rate_limited(ip_key)
        if is_limited:
            self.send_json_response(429, {
                "success": False,
                "error": "Слишком много запросов на восстановление. Пожалуйста, подождите.",
                "retryAfter": retry_after
            }, extra_headers=[("Retry-After", str(retry_after))])
            return
        RECOVERY_RATE_LIMITER.record(ip_key)

        # The per-account limit is applied silently so the response never depends on whether the account exists
        account_key = f"forgot-account:{identifier}"
        account_limited, _ = RECOVERY_RATE_LIMITER.is_rate_limited(account_key)
        RECOVERY_RATE_LIMITER.record(account_key)
        if account_limited:
            self.send_json_response(200, neutral)
            return

        conn = self.get_db()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, email FROM users
                WHERE (login_normalized = ? OR email_normalized = ?)
                  AND status = 'active' AND email IS NOT NULL AND email_verified_at IS NOT NULL
            """, (identifier, identifier))
            row = cur.fetchone()
            if row:
                now = datetime.datetime.now(datetime.timezone.utc)
                now_iso = now.isoformat()
                cur.execute("""
                    SELECT 1 FROM email_verifications
                    WHERE user_id = ? AND purpose = 'password_reset' AND resend_available_at > ?
                    LIMIT 1
                """, (row["id"], now_iso))
                in_cooldown = cur.fetchone() is not None
                if not in_cooldown:
                    code = generate_verification_code()
                    with conn:
                        conn.execute("""
                            UPDATE email_verifications SET status = 'invalidated', updated_at = ?
                            WHERE user_id = ? AND purpose = 'password_reset' AND status = 'pending'
                        """, (now_iso, row["id"]))
                        conn.execute("""
                            INSERT INTO email_verifications
                            (id, user_id, email, purpose, code_hash, expires_at, resend_available_at, created_at, updated_at)
                            VALUES (?, ?, ?, 'password_reset', ?, ?, ?, ?, ?)
                        """, (str(uuid.uuid4()), row["id"], row["email"], hash_verification_code(code),
                              (now + datetime.timedelta(minutes=10)).isoformat(),
                              (now + datetime.timedelta(minutes=1)).isoformat(), now_iso, now_iso))
                    body_text, html_body = render_code_email(
                        "Восстановление пароля",
                        "Кто-то, возможно вы, запросил сброс пароля для аккаунта SmartContractum. Введите этот код в окне восстановления.",
                        code,
                        "Код действует 10 минут. Если вы не запрашивали сброс, проигнорируйте это письмо: пароль останется прежним."
                    )
                    self.mailer().send_email(
                        conn, row["email"], "Восстановление пароля SmartContractum", body_text,
                        extra={"code": code}, html_body=html_body
                    )
        finally:
            conn.close()

        self.send_json_response(200, neutral)

    def handle_auth_reset_password(self):
        """POST /api/auth/reset-password: consumes the one-time code, sets the new password and revokes every session."""
        data = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
        if data is None:
            return

        identifier = data.get("identifier") or ""
        identifier = identifier.strip().lower() if isinstance(identifier, str) else ""
        code = data.get("code", "")
        code = code.strip() if isinstance(code, str) else ""
        new_password = data.get("newPassword", "")
        if not isinstance(new_password, str) or len(new_password) < 8:
            self.send_json_response(400, {"success": False, "error": "Новый пароль должен содержать минимум 8 символов"})
            return

        client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
        ip_key = f"reset-ip:{client_ip}"
        is_limited, retry_after = RESET_ATTEMPT_LIMITER.is_rate_limited(ip_key)
        if is_limited:
            self.send_json_response(429, {
                "success": False,
                "error": "Слишком много попыток. Пожалуйста, подождите.",
                "retryAfter": retry_after
            }, extra_headers=[("Retry-After", str(retry_after))])
            return

        # One message for every failure, so the endpoint does not reveal which accounts exist
        invalid = {"success": False, "error": "Неверный или просроченный код"}
        conn = self.get_db()
        try:
            cur = conn.cursor()
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            cur.execute("""
                SELECT id FROM users
                WHERE (login_normalized = ? OR email_normalized = ?) AND status = 'active'
            """, (identifier, identifier))
            user_row = cur.fetchone()
            challenge = None
            if user_row:
                cur.execute("""
                    SELECT id, code_hash, expires_at, attempts_left
                    FROM email_verifications
                    WHERE user_id = ? AND purpose = 'password_reset' AND status = 'pending'
                    ORDER BY created_at DESC LIMIT 1
                """, (user_row["id"],))
                challenge = cur.fetchone()

            if not challenge or challenge["expires_at"] < now_iso or not code:
                RESET_ATTEMPT_LIMITER.record(ip_key)
                self.send_json_response(400, invalid)
                return

            if not verify_verification_code(code, challenge["code_hash"]):
                RESET_ATTEMPT_LIMITER.record(ip_key)
                new_attempts = challenge["attempts_left"] - 1
                with conn:
                    conn.execute("""
                        UPDATE email_verifications SET attempts_left = ?, status = ?, updated_at = ? WHERE id = ?
                    """, (new_attempts, "invalidated" if new_attempts <= 0 else "pending", now_iso, challenge["id"]))
                self.send_json_response(400, invalid)
                return

            user_id = user_row["id"]
            with conn:
                consumed = conn.execute("""
                    UPDATE email_verifications SET status = 'consumed', updated_at = ?
                    WHERE id = ? AND status = 'pending'
                """, (now_iso, challenge["id"])).rowcount
                if consumed == 1:
                    conn.execute("""
                        UPDATE email_verifications SET status = 'invalidated', updated_at = ?
                        WHERE user_id = ? AND purpose = 'password_reset' AND status = 'pending'
                    """, (now_iso, user_id))
                    conn.execute("UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                                 (hash_password(new_password), now_iso, user_id))
                    conn.execute("UPDATE sessions SET is_revoked = 1 WHERE user_id = ?", (user_id,))
            if consumed != 1:
                self.send_json_response(400, invalid)
                return
        finally:
            conn.close()

        self.send_json_response(200, {
            "success": True,
            "message": "Пароль успешно сброшен. Пожалуйста, выполните вход."
        }, extra_headers=self.cleared_session_cookie_headers())

    def handle_auth_logout_all(self):
        """POST /api/auth/logout-all: revokes every session of the current user, including this one."""
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {"success": False, "error": "Необходима авторизация"})
            return

        conn = self.get_db()
        try:
            with conn:
                conn.execute("UPDATE sessions SET is_revoked = 1 WHERE user_id = ?", (user["id"],))
        finally:
            conn.close()

        self.send_json_response(200, {"success": True, "authenticated": False},
                                extra_headers=self.cleared_session_cookie_headers())
