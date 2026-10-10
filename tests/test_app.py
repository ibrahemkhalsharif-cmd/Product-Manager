"""App-level behaviour that needs no database."""
import re

import pymysql
import pytest
from conftest import make_settings
from flask import render_template_string

from app import create_app
from app.config import ConfigError


def test_unknown_page_shows_arabic_404(client):
    response = client.get("/no-such-page")
    html = response.get_data(as_text=True)
    assert response.status_code == 404
    assert 'dir="rtl"' in html and "الصفحة غير موجودة" in html
    assert "Traceback" not in html


def test_unexpected_error_hides_details(flask_app, client):
    @flask_app.get("/boom")
    def boom():
        raise RuntimeError("super-secret-detail")

    response = client.get("/boom")
    html = response.get_data(as_text=True)
    assert response.status_code == 500
    assert "حدث خطأ غير متوقع" in html
    for leaked in ("super-secret-detail", "RuntimeError", "Traceback"):
        assert leaked not in html


def test_database_error_shows_503_without_details(flask_app, client):
    @flask_app.get("/db-fail")
    def db_fail():
        raise pymysql.err.OperationalError(2003, "can't connect to server at 10.1.2.3")

    response = client.get("/db-fail")
    html = response.get_data(as_text=True)
    assert response.status_code == 503
    assert "الخدمة غير متاحة" in html
    assert "10.1.2.3" not in html


def test_csrf_blocks_post_without_token(flask_app, client):
    @flask_app.post("/echo")
    def echo():
        return "ok"

    response = client.post("/echo", data={"a": "1"})
    assert response.status_code == 400
    assert "انتهت صلاحية الصفحة" in response.get_data(as_text=True)


def test_csrf_accepts_post_with_valid_token(flask_app, client):
    @flask_app.get("/form")
    def form():
        return render_template_string('<input name="csrf_token" value="{{ csrf_token() }}">')

    @flask_app.post("/echo")
    def echo():
        return "ok"

    token = re.search(r'value="([^"]+)"', client.get("/form").get_data(as_text=True)).group(1)
    assert client.post("/echo", data={"csrf_token": token}).status_code == 200


def test_oversized_request_is_rejected(flask_app, client):
    @flask_app.post("/echo")
    def echo():
        return "ok"

    response = client.post("/echo", data={"a": "x" * 70000})
    assert response.status_code == 413
    assert "الطلب كبير جدًا" in response.get_data(as_text=True)


def test_cookie_and_debug_defaults(flask_app):
    config = flask_app.config
    assert config["SESSION_COOKIE_HTTPONLY"] is True
    assert config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert config["SESSION_COOKIE_SECURE"] is False
    assert flask_app.debug is False


def test_secure_cookie_flag_follows_settings():
    assert create_app(make_settings(cookie_secure=True)).config["SESSION_COOKIE_SECURE"] is True


def test_factory_rejects_placeholder_secret_key():
    with pytest.raises(ConfigError):
        create_app(make_settings(secret_key="change-this-to-a-long-random-text"))


def test_health_reports_database_down_without_leaking_details():
    unreachable = create_app(make_settings(db_host="127.0.0.1", db_port=1, db_connect_timeout=1))
    response = unreachable.test_client().get("/health")
    assert response.status_code == 503
    assert response.get_json() == {"status": "error"}
    assert b"127.0.0.1" not in response.data
