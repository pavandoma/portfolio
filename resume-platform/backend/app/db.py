"""Database engine and session management (SQLite locally, PostgreSQL in Docker and on Vercel)."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None
_migrate_lock = threading.Lock()
# Any fixed number; serialises concurrent migrations from several cold-starting instances.
_MIGRATION_LOCK_ID = 7_302_419_551


def _make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"check_same_thread": False}, future=True)

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover - trivial
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

        return engine
    # Server-side prepared statements break behind transaction-mode poolers (Neon, PgBouncer); disable them.
    return create_engine(url, pool_pre_ping=True, pool_recycle=300, future=True,
                         connect_args={"prepare_threshold": None})


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        settings.ensure_dirs()
        _engine = _make_engine(settings.resolved_database_url)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False, future=True)
    return _engine


def reset_engine() -> None:
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine, _SessionLocal = None, None


def init_db() -> None:
    """Prepare the schema: Alembic migrations when RIP_AUTO_MIGRATE is on, else create the tables directly."""
    from app import models  # noqa: F401  (register tables)

    if get_settings().auto_migrate:
        migrate_db()
    else:
        Base.metadata.create_all(get_engine())


def migrate_db() -> None:
    """Run `alembic upgrade head` in-process. On PostgreSQL a transaction-level advisory lock makes concurrent
    starts wait for each other, so only one of them applies a migration."""
    from alembic.config import Config

    from alembic import command
    from app.config import BACKEND_DIR

    cfg = Config()
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    with _migrate_lock, get_engine().begin() as conn:
        if conn.dialect.name == "postgresql":
            conn.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": _MIGRATION_LOCK_ID})
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")


@contextmanager
def session_scope() -> Iterator[Session]:
    get_engine()
    assert _SessionLocal is not None
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    with session_scope() as s:
        yield s
