"""Password hashing, one-time codes, rate limiters and same-origin checks."""
import hashlib
import hmac
import os
import re
import secrets
import threading
import time
import urllib.parse
from typing import Dict, List, Optional, Tuple


def hash_password(password: str) -> str:
    """
    Hashes a password using hashlib.scrypt with random 16-byte salt, n=16384, r=8, p=1.
    Format: scrypt$16384$8$1$<salt_hex>$<hash_hex>
    Preserves Unicode passphrases without arbitrary truncation, trimming, or lowercasing.
    """
    if not isinstance(password, str):
        raise TypeError("Password must be a string")
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=16384,
        r=8,
        p=1,
        maxmem=0,
        dklen=64
    )
    return f"scrypt$16384$8$1${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """
    Verifies a password against a stored scrypt hash using constant-time comparison (hmac.compare_digest).
    """
    if not isinstance(password, str) or not isinstance(stored_hash, str):
        return False
    try:
        parts = stored_hash.split("$")
        if len(parts) != 6 or parts[0] != "scrypt":
            return False
        n = int(parts[1])
        r = int(parts[2])
        p = int(parts[3])
        salt = bytes.fromhex(parts[4])
        expected_hash = bytes.fromhex(parts[5])
        derived = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            maxmem=0,
            dklen=len(expected_hash)
        )
        return hmac.compare_digest(derived, expected_hash)
    except Exception:
        return False


def get_capabilities_for_role(role: str) -> List[str]:
    """Returns safe capabilities list for the given user role."""
    base_caps = ["read", "comment", "vote", "save"]
    if role == "moderator":
        return base_caps + ["moderate"]
    elif role == "admin":
        return base_caps + ["moderate", "admin", "manage_users"]
    return base_caps


def is_same_origin(origin_or_referer: str, host_header: str) -> bool:
    """
    Checks if an Origin or Referer header matches the Host header.
    Handles schemes, standard ports, and localhost/127.0.0.1 equivalence in dev/test.
    """
    try:
        parsed = urllib.parse.urlparse(origin_or_referer)
        origin_netloc = parsed.netloc.lower().strip()
        host = host_header.lower().strip()
        if not origin_netloc or not host:
            return False
        if origin_netloc == host:
            return True

        origin_hostname = parsed.hostname.lower() if parsed.hostname else ""
        host_parts = host.split(":")
        host_hostname = host_parts[0]
        host_port = int(host_parts[1]) if len(host_parts) > 1 and host_parts[1].isdigit() else (443 if parsed.scheme == "https" else 80)
        origin_port = parsed.port or (443 if parsed.scheme == "https" else 80)

        if {origin_hostname, host_hostname} in ({"localhost", "127.0.0.1"}, set()):
            return origin_port == host_port
        if origin_hostname == host_hostname and origin_port == host_port:
            return True
        return False
    except Exception:
        return False


class LoginRateLimiter:
    """
    Thread-safe in-memory rate limiter tracking failed login attempts
    by client IP and by target account identifier.
    """
    def __init__(self, max_attempts: int = 5, window_seconds: int = 60, lockout_seconds: int = 60):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        self.attempts: Dict[str, List[float]] = {}
        self.lockouts: Dict[str, float] = {}
        self._lock = threading.Lock()

    def _clean(self, now: float, key: str) -> None:
        if key in self.attempts:
            self.attempts[key] = [t for t in self.attempts[key] if now - t < self.window_seconds]
            if not self.attempts[key]:
                del self.attempts[key]
        if key in self.lockouts and now >= self.lockouts[key]:
            del self.lockouts[key]

    def is_rate_limited(self, ip: str, account: Optional[str] = None) -> Tuple[bool, int]:
        now = time.time()
        with self._lock:
            keys = [f"ip:{ip}"]
            if account:
                keys.append(f"acc:{account}")

            for key in keys:
                self._clean(now, key)
                if key in self.lockouts:
                    rem = int(self.lockouts[key] - now) + 1
                    if rem > 0:
                        return True, rem

                attempts = self.attempts.get(key, [])
                if len(attempts) >= self.max_attempts:
                    lockout_until = now + self.lockout_seconds
                    self.lockouts[key] = lockout_until
                    return True, self.lockout_seconds
            return False, 0

    def record_failure(self, ip: str, account: Optional[str] = None) -> None:
        now = time.time()
        with self._lock:
            keys = [f"ip:{ip}"]
            if account:
                keys.append(f"acc:{account}")

            for key in keys:
                self._clean(now, key)
                if key not in self.attempts:
                    self.attempts[key] = []
                self.attempts[key].append(now)
                if len(self.attempts[key]) >= self.max_attempts:
                    self.lockouts[key] = now + self.lockout_seconds

    def record_success(self, ip: str, account: Optional[str] = None) -> None:
        now = time.time()
        with self._lock:
            if account:
                key = f"acc:{account}"
                self.attempts.pop(key, None)
                self.lockouts.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self.attempts.clear()
            self.lockouts.clear()


LOGIN_RATE_LIMITER = LoginRateLimiter()


def reset_login_rate_limiter() -> None:
    """Helper to reset the login rate limiter state in tests."""
    LOGIN_RATE_LIMITER.reset()


EMAIL_VERIFICATION_SECRET = os.environ.get(
    "EMAIL_VERIFICATION_SECRET",
    "sc_email_verification_secret_pepper_2026_antigravity"
)
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
LOGIN_REGEX = re.compile(r"^[a-zA-Z0-9_-]{3,30}$")


def mask_email(email: str) -> str:
    """Masks email address for safe responses without exposing full address."""
    if not email or "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "***"
    else:
        masked_local = local[0] + "***" + local[-1]
    return f"{masked_local}@{domain}"


def hash_verification_code(code: str) -> str:
    """Hashes 6-digit verification code with server pepper using HMAC-SHA256."""
    secret_bytes = EMAIL_VERIFICATION_SECRET.encode("utf-8")
    code_bytes = code.strip().encode("utf-8")
    return hmac.new(secret_bytes, code_bytes, hashlib.sha256).hexdigest()


def verify_verification_code(code: str, stored_hash: str) -> bool:
    """Constant-time verification of code against stored HMAC-SHA256 hash."""
    if not code or not stored_hash:
        return False
    computed = hash_verification_code(code)
    return hmac.compare_digest(stored_hash, computed)


class RegistrationRateLimiter:
    """Tracks registration attempts per IP/key in rolling 1-hour window."""

    def __init__(self, max_per_hour: int = 5):
        self.max_per_hour = max_per_hour
        self._lock = threading.Lock()
        self._history: Dict[str, List[float]] = {}

    def is_rate_limited(self, key: str) -> Tuple[bool, int]:
        with self._lock:
            now = time.time()
            cutoff = now - 3600.0
            timestamps = [t for t in self._history.get(key, []) if t > cutoff]
            self._history[key] = timestamps
            if len(timestamps) >= self.max_per_hour:
                oldest = timestamps[0]
                retry_after = max(1, int(3600.0 - (now - oldest)))
                return True, retry_after
            return False, 0

    def record(self, key: str) -> None:
        with self._lock:
            now = time.time()
            cutoff = now - 3600.0
            timestamps = [t for t in self._history.get(key, []) if t > cutoff]
            timestamps.append(now)
            self._history[key] = timestamps

    def reset(self) -> None:
        with self._lock:
            self._history.clear()


REGISTRATION_RATE_LIMITER = RegistrationRateLimiter(max_per_hour=5)


def reset_registration_rate_limiter() -> None:
    REGISTRATION_RATE_LIMITER.reset()


# Password recovery and email change requests: per client IP and per target account/address
RECOVERY_RATE_LIMITER = RegistrationRateLimiter(max_per_hour=5)
# Failed password reset attempts per client IP, across all accounts
RESET_ATTEMPT_LIMITER = RegistrationRateLimiter(max_per_hour=20)


def reset_recovery_rate_limiter() -> None:
    RECOVERY_RATE_LIMITER.reset()
    RESET_ATTEMPT_LIMITER.reset()


def generate_verification_code() -> str:
    """Returns a cryptographically random 6-digit one-time code."""
    return f"{secrets.randbelow(1000000):06d}"


def validate_email_format(email: str) -> bool:
    return isinstance(email, str) and len(email) <= 254 and bool(EMAIL_REGEX.match(email))


# Media uploads: per signed-in user and per client IP, counted on successful saves
MEDIA_UPLOAD_USER_LIMITER = RegistrationRateLimiter(max_per_hour=60)
MEDIA_UPLOAD_IP_LIMITER = RegistrationRateLimiter(max_per_hour=120)


def reset_media_upload_limiters() -> None:
    MEDIA_UPLOAD_USER_LIMITER.reset()
    MEDIA_UPLOAD_IP_LIMITER.reset()
