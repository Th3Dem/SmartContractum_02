"""Paths, limits and allowed values; loading of the local .env file."""
import os
from typing import List


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
DEFAULT_DB_PATH = os.path.join(DATA_DIR, "moderation.db")
MEDIA_DIR = os.path.join(DATA_DIR, "media")
os.makedirs(MEDIA_DIR, exist_ok=True)

# Allowed configuration values
VALID_COMPLEXITIES = {"none", "easy", "medium", "hard"}
VALID_STATUSES = {"draft", "pending_moderation", "approved", "rejected"}
VALID_MATERIAL_TYPES = ("publication", "question")
LEGACY_MATERIAL_TYPES = {"article": "publication", "post": "publication", "news": "publication"}

# Request body size limits (Issue #8 / SC-005)
MAX_JSON_BODY_BYTES = 5 * 1024 * 1024    # 5 МБ для стандартных JSON-запросов
MAX_MEDIA_BODY_BYTES = 15 * 1024 * 1024  # 15 МБ для загрузки медиа/обложек
