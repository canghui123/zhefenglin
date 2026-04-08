"""Engine, session factory, and dependency for FastAPI."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session and closes it after use."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
