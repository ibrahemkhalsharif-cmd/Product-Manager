"""Product Manager: a small two-page Flask app (Products, Add/Edit)."""
from __future__ import annotations

from pathlib import Path

import pymysql
from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_wtf.csrf import CSRFProtect

from . import db, errors, products
from .config import Settings, validate_secret_key

ROOT = Path(__file__).resolve().parent.parent
csrf = CSRFProtect()


def create_app(settings: Settings | None = None) -> Flask:
    if settings is None:
        load_dotenv(ROOT / ".env", encoding="utf-8")
        settings = Settings.from_env()
    validate_secret_key(settings.secret_key)

    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.update(
        SECRET_KEY=settings.secret_key,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=settings.cookie_secure,
        MAX_CONTENT_LENGTH=64 * 1024,  # forms only: reject anything bigger
        WTF_CSRF_TIME_LIMIT=8 * 3600,
    )
    app.extensions["settings"] = settings

    csrf.init_app(app)
    db.init_app(app)
    errors.init_app(app)
    app.register_blueprint(products.bp)

    @app.get("/health")
    def health():
        try:
            with db.get_db().cursor() as cur:
                cur.execute("SELECT 1 AS ok")
                cur.fetchone()
        except pymysql.MySQLError:
            app.logger.exception("Health check failed")
            return jsonify(status="error"), 503
        return jsonify(status="ok")

    return app
