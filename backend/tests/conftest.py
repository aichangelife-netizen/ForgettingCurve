from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine

from app.db.base import Base
from app.db.database import create_database_engine
from app.db import models  # noqa: F401


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
