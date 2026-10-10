"""One MariaDB connection per request, closed automatically afterwards."""
import pymysql
import pymysql.cursors
from flask import g

import config


def get_db():
    if "db" not in g:
        g.db = pymysql.connect(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database=config.DB_NAME,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )
    return g.db


def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()
