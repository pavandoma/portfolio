"""File storage under the private data directory. Paths are always resolved inside it."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from app.config import Settings


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _inside(base: Path, target: Path) -> Path:
    base = base.resolve()
    target = target.resolve()
    if base != target and base not in target.parents:
        raise PermissionError("Refusing to access a path outside the data directory.")
    return target


def store_upload(settings: Settings, doc_id: str, kind: str, content: bytes) -> Path:
    settings.ensure_dirs()
    ext = {"pdf": ".pdf", "docx": ".docx", "txt": ".txt"}.get(kind, ".bin")
    path = _inside(settings.uploads_dir, settings.uploads_dir / f"{doc_id}{ext}")
    path.write_bytes(content)
    path.chmod(0o600)
    return path


def output_dir(settings: Settings, version_id: str) -> Path:
    settings.ensure_dirs()
    d = _inside(settings.outputs_dir, settings.outputs_dir / version_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def store_output(settings: Settings, version_id: str, filename: str, content: bytes) -> Path:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", filename)[:150]
    path = _inside(settings.outputs_dir, output_dir(settings, version_id) / safe)
    path.write_bytes(content)
    path.chmod(0o600)
    return path


def resolve_stored(settings: Settings, stored_path: str) -> Path:
    return _inside(settings.data_dir, Path(stored_path))


def delete_stored(settings: Settings, stored_path: str | None) -> None:
    if not stored_path:
        return
    try:
        p = resolve_stored(settings, stored_path)
        if p.exists():
            p.unlink()
    except (PermissionError, OSError):
        pass
