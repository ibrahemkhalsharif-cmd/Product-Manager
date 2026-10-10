"""Database-layer tests against a real MariaDB (test database only)."""
import pymysql
import pytest

from app import db

pytestmark = pytest.mark.integration


def test_health_is_ok_when_database_is_reachable(db_app):
    response = db_app.test_client().get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_connection_is_strict_and_utf8mb4(db_app):
    with db_app.app_context():
        with db.get_db().cursor() as cur:
            cur.execute(
                "SELECT @@sql_mode AS mode, @@character_set_client AS cs, "
                "@@character_set_connection AS cc, @@character_set_results AS cr"
            )
            row = cur.fetchone()
    assert "STRICT_ALL_TABLES" in row["mode"]
    assert row["cs"] == row["cc"] == row["cr"] == "utf8mb4"


def test_one_connection_per_request_and_closed_afterwards(db_app):
    with db_app.app_context():
        first = db.get_db()
        assert db.get_db() is first
        assert first.open
    assert not first.open


def test_connection_is_closed_even_when_the_request_fails(db_app):
    seen = []

    @db_app.get("/fail")
    def fail():
        seen.append(db.get_db())
        raise RuntimeError("boom")

    response = db_app.test_client().get("/fail")
    assert response.status_code == 500
    assert seen and not seen[0].open


def test_uncommitted_changes_are_discarded_at_request_end(db_app):
    with db_app.app_context():
        with db.get_db().cursor() as cur:
            cur.execute("INSERT INTO categories (name) VALUES (%s)", ("لن يُحفظ",))
    with db_app.app_context():
        with db.get_db().cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM categories WHERE name = %s", ("لن يُحفظ",))
            assert cur.fetchone()["n"] == 0


def test_arabic_text_round_trips(db_app):
    text = "مشروبات غازية"
    with db_app.app_context():
        conn = db.get_db()
        with conn.cursor() as cur:
            cur.execute("INSERT INTO categories (name) VALUES (%s)", (text,))
            cur.execute("SELECT name FROM categories WHERE name = %s", (text,))
            assert cur.fetchone()["name"] == text
        conn.rollback()


def test_strict_mode_rejects_overlong_barcode_instead_of_cutting_it(db_app):
    with db_app.app_context():
        conn = db.get_db()
        with conn.cursor() as cur:
            cur.execute("INSERT INTO categories (name) VALUES (%s)", ("اختبار",))
            category_id = cur.lastrowid
            with pytest.raises(pymysql.err.DataError):
                cur.execute(
                    "INSERT INTO products (name, barcode, price, quantity, category_id) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    ("منتج", "1" * 33, "1.00", 1, category_id),
                )
        conn.rollback()
