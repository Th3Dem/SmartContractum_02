"""
Source files of the backend for tests that inspect code as text.

The server was split from a single server.py into server.py plus the backend/ package;
text checks (SQL inspection, forbidden characters) cover all of these files.
"""
import glob
import io
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

BACKEND_FILES = [os.path.join(PROJECT_ROOT, "server.py")] + sorted(
    glob.glob(os.path.join(PROJECT_ROOT, "backend", "**", "*.py"), recursive=True)
)


def read_backend_source() -> str:
    parts = []
    for path in BACKEND_FILES:
        with open(path, "r", encoding="utf-8") as f:
            parts.append(f.read())
    return "\n".join(parts)


def backend_source_file() -> io.StringIO:
    """File-like object with the whole backend source, usable in `with ... as f`."""
    return io.StringIO(read_backend_source())
