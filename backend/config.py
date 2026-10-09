"""Paths, limits and allowed values; loading of the local .env file."""
import atexit
import os
import shutil
import sys
import tempfile
import types
from typing import List, Optional


def load_env_file(path: str) -> List[str]:
    """
    Loads KEY=VALUE lines from a local env file into os.environ without overriding
    variables that are already set. Returns the names that were loaded.
    Lines starting with # and blank lines are ignored; values may be quoted.
    """
    loaded = []
    if not os.path.isfile(path):
        return loaded
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            if key and key not in os.environ:
                os.environ[key] = value
                loaded.append(key)
    return loaded


# Base paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_PUBLIC_DIR = os.path.join(PROJECT_ROOT, "frontend", "public")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")


def is_under_test() -> bool:
    return "unittest" in sys.modules


_TEST_DATA_DIR = None


def get_test_data_dir() -> str:
    global _TEST_DATA_DIR
    if _TEST_DATA_DIR is None:
        _TEST_DATA_DIR = tempfile.mkdtemp(prefix="sc-test-data-")
        atexit.register(shutil.rmtree, _TEST_DATA_DIR, ignore_errors=True)
    return _TEST_DATA_DIR


def check_forbidden_test_path(path: Optional[str]) -> None:
    if not path or path == ":memory:":
        return
    if not is_under_test():
        return
    real_target = os.path.realpath(os.path.abspath(path))
    real_data = os.path.realpath(os.path.abspath(DATA_DIR))
    if real_target == real_data or real_target.startswith(real_data + os.sep):
        raise RuntimeError(f"Test runs must never touch repository data directory: {path}")


_CUSTOM_DB_PATH: Optional[str] = None
_CUSTOM_MEDIA_DIR: Optional[str] = None


class _ConfigModule(types.ModuleType):
    @property
    def DEFAULT_DB_PATH(self) -> str:
        if _CUSTOM_DB_PATH is not None:
            return _CUSTOM_DB_PATH
        if is_under_test():
            return os.path.join(get_test_data_dir(), "moderation.db")
        return os.path.join(DATA_DIR, "moderation.db")

    @DEFAULT_DB_PATH.setter
    def DEFAULT_DB_PATH(self, value: Optional[str]) -> None:
        global _CUSTOM_DB_PATH
        _CUSTOM_DB_PATH = value

    @property
    def MEDIA_DIR(self) -> str:
        if _CUSTOM_MEDIA_DIR is not None:
            return _CUSTOM_MEDIA_DIR
        if is_under_test():
            return os.path.join(get_test_data_dir(), "media")
        return os.path.join(DATA_DIR, "media")

    @MEDIA_DIR.setter
    def MEDIA_DIR(self, value: Optional[str]) -> None:
        global _CUSTOM_MEDIA_DIR
        _CUSTOM_MEDIA_DIR = value

    def __dir__(self):
        return list(super().__dir__()) + ["DEFAULT_DB_PATH", "MEDIA_DIR"]


# Allowed configuration values
VALID_COMPLEXITIES = {"none", "easy", "medium", "hard"}
VALID_STATUSES = {"draft", "pending_moderation", "approved", "rejected"}
VALID_MATERIAL_TYPES = ("publication", "question")
LEGACY_MATERIAL_TYPES = {"article": "publication", "post": "publication", "news": "publication"}

# Request body size limits (Issue #8 / SC-005)
MAX_JSON_BODY_BYTES = 5 * 1024 * 1024    # 5 МБ для стандартных JSON-запросов
MAX_MEDIA_BODY_BYTES = 15 * 1024 * 1024  # 15 МБ для загрузки медиа/обложек


def site_url() -> str:
    """Public base URL used in links inside emails, without a trailing slash."""
    return os.environ.get("SITE_URL", "http://localhost:8000").rstrip("/")


__all__ = [
    "load_env_file",
    "PROJECT_ROOT",
    "FRONTEND_PUBLIC_DIR",
    "DATA_DIR",
    "DEFAULT_DB_PATH",
    "MEDIA_DIR",
    "is_under_test",
    "get_test_data_dir",
    "check_forbidden_test_path",
    "VALID_COMPLEXITIES",
    "VALID_STATUSES",
    "VALID_MATERIAL_TYPES",
    "LEGACY_MATERIAL_TYPES",
    "MAX_JSON_BODY_BYTES",
    "MAX_MEDIA_BODY_BYTES",
    "site_url",
]

sys.modules[__name__].__class__ = _ConfigModule
