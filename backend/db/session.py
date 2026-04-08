"""Engine, session factory, and dependency for FastAPI.

Engine creation is lazy so tests can override `DATABASE_URL` (e.g. point to
a temporary SQLite file) and then call `reset_engine()` to rebuild.
"""
import os
from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session

from config import settings

_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def _current_url() -> str:
    return os.environ.get("DATABASE_URL", settings.database_url)


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = _current_url()
        kwargs: dict = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            # SQLite needs this to be shared across the TestClient threads
            kwargs["connect_args"] = {"check_same_thread": False}
        else:
            kwargs["pool_size"] = 5
            kwargs["max_overflow"] = 10
        _engine = create_engine(url, **kwargs)
    return _engine


def get_sessionmaker() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(), autoflush=False, expire_on_commit=False
        )
    return _SessionLocal


def reset_engine() -> None:
    """Tear down the cached engine so the next call picks up a new DATABASE_URL."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a session and closes it after the request."""
    SessionLocal = get_sessionmaker()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
