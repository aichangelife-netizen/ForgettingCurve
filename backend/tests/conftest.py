from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.database import create_database_engine, get_db
from app.db import models  # noqa: F401
from app.main import app


@pytest.fixture
def db_engine(tmp_path) -> Generator[Engine, None, None]:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'test.sqlite3'}")
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def current_time() -> datetime:
    return datetime.now(UTC)


@pytest.fixture
def db_session(db_engine: Engine) -> Generator[Session, None, None]:
    session_factory = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    with session_factory() as session:
        yield session


@pytest.fixture
def api_client(db_engine: Engine) -> Generator[TestClient, None, None]:
    session_factory = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)

    def override_get_db() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
