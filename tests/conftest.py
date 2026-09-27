"""Общая временная SQLite для тестов репозиториев и окна."""

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from auth import Session
from database.db import Base


@pytest.fixture
def users_db(tmp_path: Path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    import database.models  # noqa: F401

    Base.metadata.create_all(engine)
    factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    monkeypatch.setattr("database.repositories.SessionLocal", factory)
    yield factory
    Session.logout()
    engine.dispose()
