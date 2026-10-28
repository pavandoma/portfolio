"""File storage under the private data directory. Paths are always resolved inside it.

With RIP_STORAGE=db (the default on Vercel) every file is also written to the ``stored_files`` table, in the
caller's transaction, and the data directory is only a cache: a server that does not have a file locally
fetches it from the database on first read.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import Settings


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _inside(base: Path, target: Path) -> Path:
    base = base.resolve()
    target = target.resolve()
    if base != target and base not in target.parents:
        raise PermissionError("Refusing to access a path outside the data directory.")
    return target


def _key(settings: Settings, path: Path) -> str:
    return path.resolve().relative_to(settings.data_dir.resolve()).as_posix()


def _write(settings: Settings, path: Path, content: bytes, session: Session | None) -> None:
    path.write_bytes(content)
    path.chmod(0o600)
    if settings.storage == "db":
        from app.models import StoredFile

        row = StoredFile(key=_key(settings, path), content=content, sha256=sha256_bytes(content),
                         size_bytes=len(content))
        if session is not None:
            session.merge(row)
        else:
            from app.db import session_scope

            with session_scope() as s:
                s.merge(row)


def store_upload(settings: Settings, doc_id: str, kind: str, content: bytes, session: Session | None = None) -> Path:
    settings.ensure_dirs()
    ext = {"pdf": ".pdf", "docx": ".docx", "txt": ".txt"}.get(kind, ".bin")
    path = _inside(settings.uploads_dir, settings.uploads_dir / f"{doc_id}{ext}")
    _write(settings, path, content, session)
    return path


def output_dir(settings: Settings, version_id: str) -> Path:
    settings.ensure_dirs()
    d = _inside(settings.outputs_dir, settings.outputs_dir / version_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def store_output(settings: Settings, version_id: str, filename: str, content: bytes,
                 session: Session | None = None) -> Path:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", filename)[:150]
    path = _inside(settings.outputs_dir, output_dir(settings, version_id) / safe)
    _write(settings, path, content, session)
    return path


def resolve_stored(settings: Settings, stored_path: str, session: Session | None = None) -> Path:
    """The local path of a stored file, fetched from the database first when this server has no copy."""
    path = _inside(settings.data_dir, Path(stored_path))
    if settings.storage == "db" and not path.exists():
        from app.models import StoredFile

        def fetch(s: Session) -> bytes | None:
            row = s.get(StoredFile, _key(settings, path))
            return row.content if row else None

        if session is not None:
            content = fetch(session)
        else:
            from app.db import session_scope

            with session_scope() as s:
                content = fetch(s)
        if content is None:
            raise FileNotFoundError("The stored file is missing.")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        path.chmod(0o600)
    return path


def delete_stored(settings: Settings, stored_path: str | None, session: Session | None = None) -> None:
    if not stored_path:
        return
    try:
        p = _inside(settings.data_dir, Path(stored_path))
        if p.exists():
            p.unlink()
        if settings.storage == "db" and session is not None:
            from app.models import StoredFile

            row = session.get(StoredFile, _key(settings, p))
            if row is not None:
                session.delete(row)
    except (PermissionError, OSError):
        pass
