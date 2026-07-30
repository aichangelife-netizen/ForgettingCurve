from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.db.database import DATABASE_URL_ENV_VAR


BACKEND_DIR = Path(__file__).resolve().parents[1]


def alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_alembic_upgrade_from_empty_temporary_database_succeeds(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'migration.sqlite3'}"
    monkeypatch.setenv(DATABASE_URL_ENV_VAR, database_url)

    command.upgrade(alembic_config(database_url), "head")

    engine = create_engine(database_url)
    try:
        table_names = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert {
        "participants",
        "vocabulary_items",
        "test_designs",
        "test_design_groups",
        "test_design_items",
        "test_assignments",
        "vocabulary_attempts",
        "curve_models",
        "alembic_version",
    }.issubset(table_names)


def test_alembic_downgrade_and_upgrade_succeeds(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'migration-roundtrip.sqlite3'}"
    monkeypatch.setenv(DATABASE_URL_ENV_VAR, database_url)
    config = alembic_config(database_url)

    command.upgrade(config, "head")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
