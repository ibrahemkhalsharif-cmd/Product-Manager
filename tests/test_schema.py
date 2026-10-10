"""The database must reject bad data on its own (the app also validates, this is the backstop)."""
from decimal import Decimal

import pymysql
import pytest

from app import db

pytestmark = pytest.mark.integration

CHECK_FAILED = 4025  # MariaDB: CONSTRAINT ... failed
DUPLICATE = 1062
DATA_TOO_LONG = 1406
OUT_OF_RANGE = 1264
NO_PARENT = 1452
HAS_CHILD = 1451


@pytest.fixture()
def tx(db_app):
    """A cursor inside an open transaction with one category. Always rolled back."""
    with db_app.app_context():
        conn = db.get_db()
        with conn.cursor() as cur:
            cur.execute("INSERT INTO categories (name) VALUES (%s)", ("اختبار",))
            yield cur, cur.lastrowid
        conn.rollback()


def insert(cur, category_id, *, name="منتج", barcode="6291000000001", price="1.00", quantity=1):
    cur.execute(
        "INSERT INTO products (name, barcode, price, quantity, category_id) VALUES (%s, %s, %s, %s, %s)",
        (name, barcode, price, quantity, category_id),
    )


def rejected_with(cur, category_id, expected_errno, **values):
    with pytest.raises(pymysql.MySQLError) as info:
        insert(cur, category_id, **values)
    assert info.value.args[0] == expected_errno


def test_duplicate_barcode_is_rejected(tx):
    cur, cid = tx
    insert(cur, cid, barcode="6291000000001")
    rejected_with(cur, cid, DUPLICATE, barcode="6291000000001")


@pytest.mark.parametrize("barcode", ["ABC12345", "123", " 123456", "12 3456"])
def test_bad_barcode_format_is_rejected(tx, barcode):
    cur, cid = tx
    rejected_with(cur, cid, CHECK_FAILED, barcode=barcode)


def test_33_digit_barcode_is_rejected(tx):
    cur, cid = tx
    rejected_with(cur, cid, DATA_TOO_LONG, barcode="1" * 33)


def test_leading_zeros_are_kept(tx):
    cur, cid = tx
    insert(cur, cid, barcode="00001234")
    cur.execute("SELECT barcode FROM products WHERE barcode = %s", ("00001234",))
    assert cur.fetchone()["barcode"] == "00001234"


@pytest.mark.parametrize("price", ["0", "-1", "-0.01"])
def test_price_must_be_positive(tx, price):
    cur, cid = tx
    rejected_with(cur, cid, CHECK_FAILED, price=price)


def test_price_too_large_is_rejected(tx):
    cur, cid = tx
    rejected_with(cur, cid, OUT_OF_RANGE, price="100000000")


def test_price_is_stored_exactly(tx):
    cur, cid = tx
    insert(cur, cid, price="19.99")
    cur.execute("SELECT price FROM products")
    assert cur.fetchone()["price"] == Decimal("19.99")


def test_quantity_zero_is_allowed(tx):
    cur, cid = tx
    insert(cur, cid, quantity=0)
    cur.execute("SELECT quantity FROM products")
    assert cur.fetchone()["quantity"] == 0


def test_negative_quantity_is_rejected(tx):
    cur, cid = tx
    rejected_with(cur, cid, CHECK_FAILED, quantity=-1)


@pytest.mark.parametrize("name", ["", "   "])
def test_blank_name_is_rejected(tx, name):
    cur, cid = tx
    rejected_with(cur, cid, CHECK_FAILED, name=name)


def test_unknown_category_is_rejected(tx):
    cur, _ = tx
    rejected_with(cur, 65000, NO_PARENT)


def test_category_in_use_cannot_be_deleted(tx):
    cur, cid = tx
    insert(cur, cid)
    with pytest.raises(pymysql.MySQLError) as info:
        cur.execute("DELETE FROM categories WHERE id = %s", (cid,))
    assert info.value.args[0] == HAS_CHILD
