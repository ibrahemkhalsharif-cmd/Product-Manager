"""Helpers shared by the page tests that work on committed data in the test database."""
import re

from app import db


def seed(app, rows, category="مواد غذائية"):
    """rows: (name, barcode, price, quantity). Returns the new product ids."""
    ids = []
    with app.app_context():
        conn = db.get_db()
        with conn.cursor() as cur:
            cur.execute("INSERT INTO categories (name) VALUES (%s)", (category,))
            category_id = cur.lastrowid
            for name, barcode, price, quantity in rows:
                cur.execute(
                    "INSERT INTO products (name, barcode, price, quantity, category_id) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (name, barcode, price, quantity, category_id),
                )
                ids.append(cur.lastrowid)
        conn.commit()
    return ids


def count(app, where="1=1", params=()):
    with app.app_context():
        with db.get_db().cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS n FROM products WHERE {where}", params)  # noqa: S608
            return cur.fetchone()["n"]


def fetch_product(app, product_id):
    with app.app_context():
        with db.get_db().cursor() as cur:
            cur.execute("SELECT * FROM products WHERE id = %s", (product_id,))
            return cur.fetchone()


def category_id_of(app, name):
    with app.app_context():
        with db.get_db().cursor() as cur:
            cur.execute("SELECT id FROM categories WHERE name = %s", (name,))
            return cur.fetchone()["id"]


def token_from(html):
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
