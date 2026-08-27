"""Local filesystem storage backend.

Files are written to ``/app/backend/uploads/<path>`` and served through
``/api/files/<path>`` by ``server.py``.  Signatures kept compatible with the
previous Emergent-object-store implementation so nothing else in the codebase
needs to change.
"""

from __future__ import annotations

import logging
import mimetypes
import os
import uuid
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)

# Root directory for uploads
STORAGE_ROOT = Path(os.environ.get("STORAGE_ROOT", "/app/backend/uploads")).resolve()

# Public URL prefix
PUBLIC_BASE = os.environ.get("FRONTEND_URL", "").rstrip("/")

# Allowed image content-types for uploads
ALLOWED_IMAGE_MIMES = {
    "image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp",
    "image/svg+xml", "image/x-icon", "image/vnd.microsoft.icon", "image/bmp",
}

MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", 10 * 1024 * 1024))  # 10 MB


def init_storage() -> str:
    """Ensure the uploads root exists.  Returns the absolute path."""
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    logger.info(f"Local storage ready at {STORAGE_ROOT}")
    return str(STORAGE_ROOT)


def _safe_target(path: str) -> Path:
    """Resolve ``path`` under ``STORAGE_ROOT`` and guard against traversal."""
    if not path:
        raise ValueError("Empty storage path")
    target = (STORAGE_ROOT / path).resolve()
    if STORAGE_ROOT not in target.parents and target != STORAGE_ROOT:
        raise ValueError("Path escapes storage root")
    return target


def put_object(path: str, data: bytes, content_type: str) -> dict:
    """Persist ``data`` at ``path`` beneath STORAGE_ROOT."""
    if data is None:
        raise ValueError("No data provided")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(f"File exceeds max size of {MAX_UPLOAD_BYTES} bytes")

    target = _safe_target(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "wb") as fh:
        fh.write(data)
    logger.info(f"Stored object {path} ({len(data)} bytes, {content_type})")
    return {"path": path, "size": len(data), "content_type": content_type}


def get_object(path: str) -> Tuple[bytes, str]:
    """Read an object; return (bytes, content-type)."""
    target = _safe_target(path)
    if not target.exists() or not target.is_file():
        raise FileNotFoundError(path)
    ctype, _ = mimetypes.guess_type(str(target))
    if not ctype:
        ctype = "application/octet-stream"
    with open(target, "rb") as fh:
        return fh.read(), ctype


def generate_upload_path(scope: str, filename: str) -> str:
    """Build a unique storage path scoped to a namespace (user, entity, etc)."""
    scope = (scope or "misc").strip().strip("/") or "misc"
    ext = "bin"
    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()[:8] or "bin"
    return f"officeflow/{scope}/{uuid.uuid4().hex}.{ext}"


def to_public_url(path: str) -> str:
    """Turn a stored object path into a browser-fetchable URL.

    Always returns a RELATIVE URL of the form ``/api/files/<key>``. Handles
    three input shapes safely:

    * bare storage key (``officeflow/dispatch/x.png``) → ``/api/files/...``
    * already-prefixed relative path (``/api/files/...``) → returned as-is
    * legacy absolute URL (``https://old-host/api/files/...``) →
      rewritten to the relative form so it survives host changes.
    """
    if not path:
        return path
    if path.startswith("/api/files/"):
        return path
    if path.startswith("http://") or path.startswith("https://"):
        marker = "/api/files/"
        if marker in path:
            return "/api/files/" + path.split(marker, 1)[1]
        return path
    return f"/api/files/{path.lstrip('/')}"
