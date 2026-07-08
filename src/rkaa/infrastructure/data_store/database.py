"""Database engine and session management for RKAA."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from rkaa.core.config import Settings, load_settings

_session_factory: sessionmaker[Session] | None = None
_engine: Engine | None = None


def create_engine_from_url(database_url: str) -> Engine:
    connect_args: dict[str, object] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    return create_engine(
        database_url,
        future=True,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


def initialize_database(settings: Settings | None = None) -> sessionmaker[Session]:
    global _engine, _session_factory

    config = settings or load_settings()
    _engine = create_engine_from_url(config.database.url)
    _session_factory = sessionmaker(
        bind=_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )
    return _session_factory


def get_engine() -> Engine:
    if _engine is None:
        initialize_database()
    assert _engine is not None
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    if _session_factory is None:
        initialize_database()
    assert _session_factory is not None
    return _session_factory


@contextmanager
def session_scope() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
