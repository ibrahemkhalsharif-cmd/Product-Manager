"""Shared fixtures. Integration tests only ever touch a database whose name ends in _test."""
import os
from pathlib import Path

import pymysql
import pytest
from dotenv import load_dotenv

from app import create_app
from app.config import Settings

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", encoding="utf-8")  # reuse your local DB login if .env exists

SECRET = "t" * 32  # only length and "not the placeholder" are checked


def make_settings(**overrides) -> Settings:
    values = dict(
        db_host=os.getenv("DB_HOST", "127.0.0.1"),
        db_port=int(os.getenv("DB_PORT", "3306")),
        db_user=os.getenv("DB_USER", "root"),
        db_password=os.getenv("DB_PASSWORD", ""),
        db_name=os.getenv("TEST_DB_NAME", "shop_db_test"),
        db_ssl_disabled=True,
        secret_key=SECRET,
    )
    values.update(overrides)
    return Settings(**values)


def _statements(sql_text: str, db_name: str) -> list[str]:
    text = sql_text.replace("shop_db", db_name)
    lines = [line for line in text.splitlines() if not line.strip().startswith("--")]
    return [part.strip() for part in "\n".join(lines).split(";") if part.strip()]


@pytest.fixture(scope="session")
def test_db_settings():
    """Create a fresh test database from sql/schema.sql (never the real shop_db)."""
    settings = make_settings()
    assert settings.db_name.endswith("_test"), "refusing to run tests on a non-test database"
    try:
        conn = pymysql.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            connect_timeout=3,
            ssl_disabled=True,
        )
    except pymysql.MySQLError as exc:
        message = f"MariaDB not reachable ({type(exc).__name__}). Start it and check DB_* settings."
        if os.getenv("REQUIRE_DB") == "1":
            pytest.fail(message)
        pytest.skip(message)
    try:
        with conn.cursor() as cur:
            schema = (ROOT / "sql" / "schema.sql").read_text(encoding="utf-8")
            for statement in _statements(schema, settings.db_name):
                cur.execute(statement)
        conn.commit()
    finally:
        conn.close()
    return settings


@pytest.fixture()
def flask_app():
    return create_app(make_settings())


@pytest.fixture()
def client(flask_app):
    return flask_app.test_client()


@pytest.fixture()
def db_app(test_db_settings):
    return create_app(test_db_settings)
