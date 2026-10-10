"""MariaDB connection handling: one connection per request, always closed."""
from __future__ import annotations

import pymysql
import pymysql.cursors
from flask import Flask, current_app, g

from .config import Settings

# MariaDB cuts over-long values silently unless the session is strict, so every
# connection forces strict mode regardless of the server's own default.
STRICT_SQL_MODE = "STRICT_ALL_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION"


def connect(settings: Settings) -> pymysql.connections.Connection:
    """Open a new connection. Transactions are explicit: call commit() after writes."""
    return pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
        connect_timeout=settings.db_connect_timeout,
        read_timeout=30,
        write_timeout=30,
        init_command=f"SET SESSION sql_mode='{STRICT_SQL_MODE}'",
        ssl_disabled=settings.db_ssl_disabled,
    )


def get_db() -> pymysql.connections.Connection:
    """The connection for the current request, opened on first use."""
    if "db" not in g:
        g.db = connect(current_app.extensions["settings"])
    return g.db


def close_db(_exc: BaseException | None = None) -> None:
    """Runs at the end of every request, also after errors."""
    db = g.pop("db", None)
    if db is None:
        return
    try:
        if db.open:
            db.rollback()  # discards anything not committed; harmless after a commit
    except pymysql.MySQLError:
        pass
    finally:
        db.close()


def init_app(app: Flask) -> None:
    app.teardown_appcontext(close_db)
