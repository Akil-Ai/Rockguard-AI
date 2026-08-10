"""SQLAlchemy engine / session wiring.

Defaults to a local SQLite file so the demo runs with zero setup.
Point DATABASE_URL at PostgreSQL/Supabase to swap backends without code changes.
"""
from __future__ import annotations

import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import BACKEND_DIR, settings

# SQLite relative paths must resolve against the backend dir, not the shell cwd.
url = settings.database_url
if url.startswith("sqlite:///./"):
    abs_path = (BACKEND_DIR / url.replace("sqlite:///./", "")).resolve()
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    url = f"sqlite:///{abs_path.as_posix()}"

connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401  (registers mappers)

    os.makedirs(BACKEND_DIR / "data", exist_ok=True)
    Base.metadata.create_all(bind=engine)
