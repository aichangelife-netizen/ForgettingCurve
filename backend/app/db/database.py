from collections.abc import Generator
from datetime import datetime, timezone
import os
from sqlite3 import Connection as SQLiteConnection

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker


DATABASE_URL_ENV_VAR = "FORGETTING_CURVE_DATABASE_URL"
DEFAULT_DATABASE_URL = "sqlite:///./forgetting_curve.sqlite3"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_database_url() -> str:
    return os.getenv(DATABASE_URL_ENV_VAR, DEFAULT_DATABASE_URL)


def create_database_engine(database_url: str | None = None) -> Engine:
    url = database_url or get_database_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


@event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
    if isinstance(dbapi_connection, SQLiteConnection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


engine = create_database_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
