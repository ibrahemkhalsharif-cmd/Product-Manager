"""Products pages: list with search, paging and delete, plus the add/edit form."""
from __future__ import annotations

import math
import re

import pymysql
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .db import get_db
from .textutil import escape_like, normalize_digits
from .validation import MESSAGES, validate_product

bp = Blueprint("products", __name__)

PAGE_SIZE = 20
MAX_QUERY_LENGTH = 100
# schema.sql allows barcodes of 4 to 32 digits, so only such a query can be a barcode.
BARCODE_QUERY = re.compile(r"[0-9]{4,32}")

# Paging is done on the id list first (answered from the name index alone), and the full rows
# are fetched only for the 20 ids on the page. Selecting every column inside the inner query
# made deep pages ~100x slower in measurements on 500,000 rows.
LIST_SQL = """
    SELECT p.id, p.name, p.barcode, p.price, p.quantity, c.name AS category
    FROM (
        SELECT id FROM products {where} ORDER BY name, id LIMIT %s OFFSET %s
    ) AS pg
    JOIN products AS p ON p.id = pg.id
    JOIN categories AS c ON c.id = p.category_id
    ORDER BY p.name, p.id
"""


def build_filter(q: str) -> tuple[str, tuple]:
    """WHERE clause and parameters for the search text.

    Digits only (4-32 of them) means a barcode search: the barcode STARTS with the text, which
    uses the unique barcode index. Anything else is a name search: the name CONTAINS the text.
    A contains-search cannot use an index, so it reads the whole table (about 0.6 s per
    500,000 rows).
    """
    if not q:
        return "", ()
    digits = normalize_digits(q)
    if BARCODE_QUERY.fullmatch(digits):
        return "WHERE barcode LIKE %s", (escape_like(digits) + "%",)
    return "WHERE name LIKE %s", ("%" + escape_like(q) + "%",)


def parse_page(raw: str | None) -> int:
    try:
        return max(int(raw), 1)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 1


def clean_query(raw: str | None) -> str:
    return (raw or "").strip()[:MAX_QUERY_LENGTH]


def page_window(page: int, pages: int, span: int = 2) -> list[int | None]:
    """Page numbers to show, with None where a gap is collapsed: 1 ... 4 5 [6] 7 8 ... 20."""
    shown = sorted({1, pages, *range(max(1, page - span), min(pages, page + span) + 1)})
    result: list[int | None] = []
    previous = 0
    for number in shown:
        if number - previous > 1:
            result.append(None)
        result.append(number)
        previous = number
    return result


@bp.get("/")
def index():
    q = clean_query(request.args.get("q"))
    where, params = build_filter(q)
    with get_db().cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS n FROM products {where}", params)  # noqa: S608 (fixed text)
        total = cur.fetchone()["n"]
        pages = max(1, math.ceil(total / PAGE_SIZE))
        page = min(parse_page(request.args.get("page")), pages)
        cur.execute(
            LIST_SQL.format(where=where),
            (*params, PAGE_SIZE, (page - 1) * PAGE_SIZE),
        )
        rows = cur.fetchall()
    return render_template(
        "products.html",
        products=rows,
        q=q,
        page=page,
        pages=pages,
        total=total,
        page_numbers=page_window(page, pages),
    )


@bp.post("/products/<int:product_id>/delete")
def delete(product_id: int):
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT name FROM products WHERE id = %s", (product_id,))
        product = cur.fetchone()
        if product is None:
            abort(404)
        cur.execute("DELETE FROM products WHERE id = %s", (product_id,))
    db.commit()
    flash(f"تم حذف المنتج «{product['name']}».", "success")
    page = parse_page(request.form.get("page"))
    return redirect(
        url_for(
            "products.index",
            q=clean_query(request.form.get("q")) or None,
            page=page if page > 1 else None,
        )
    )


# ---------- Add / edit form ----------

DUPLICATE_KEY = 1062  # MariaDB error number for a UNIQUE violation

BLANK_VALUES = {"name": "", "barcode": "", "price": "", "quantity": "", "category_id": ""}
FORM_FIELDS = tuple(BLANK_VALUES)


def _form_page(product_id: int | None):
    """One handler for both pages: product_id is None when adding."""
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT id, name FROM categories ORDER BY name")
        categories = cur.fetchall()

        existing = None
        if product_id is not None:
            cur.execute(
                "SELECT id, name, barcode, price, quantity, category_id FROM products WHERE id = %s",
                (product_id,),
            )
            existing = cur.fetchone()
            if existing is None:
                abort(404)

        if request.method == "POST":
            def barcode_taken(barcode: str) -> bool:
                cur.execute(
                    "SELECT 1 FROM products WHERE barcode = %s AND id <> %s LIMIT 1",
                    (barcode, product_id or 0),
                )
                return cur.fetchone() is not None

            product, errors = validate_product(
                request.form,
                category_ids={c["id"] for c in categories},
                barcode_taken=barcode_taken,
            )
            if product is not None:
                values = (product.name, product.barcode, product.price,
                          product.quantity, product.category_id)
                try:
                    if product_id is None:
                        cur.execute(
                            "INSERT INTO products (name, barcode, price, quantity, category_id) "
                            "VALUES (%s, %s, %s, %s, %s)",
                            values,
                        )
                        message = f"تمت إضافة المنتج «{product.name}»."
                    else:
                        cur.execute(
                            "UPDATE products SET name = %s, barcode = %s, price = %s, "
                            "quantity = %s, category_id = %s WHERE id = %s",
                            (*values, product_id),
                        )
                        message = f"تم تحديث المنتج «{product.name}»."
                    db.commit()
                except pymysql.err.IntegrityError as exc:
                    # Someone saved the same barcode between our check and our write.
                    db.rollback()
                    if exc.args[0] != DUPLICATE_KEY:
                        raise
                    errors = {"barcode": MESSAGES["barcode_taken"]}
                else:
                    flash(message, "success")
                    return redirect(url_for("products.index"))
            shown = {f: request.form.get(f, "") for f in FORM_FIELDS}
            return render_template(
                "product_form.html",
                title="تعديل منتج" if product_id is not None else "إضافة منتج",
                categories=categories, values=shown, errors=errors,
            ), 400

    if existing is None:
        shown = dict(BLANK_VALUES)
    else:
        shown = {
            "name": existing["name"],
            "barcode": existing["barcode"],
            "price": f"{existing['price']:.2f}",
            "quantity": str(existing["quantity"]),
            "category_id": str(existing["category_id"]),
        }
    return render_template(
        "product_form.html",
        title="تعديل منتج" if product_id is not None else "إضافة منتج",
        categories=categories, values=shown, errors={},
    )


@bp.route("/products/new", methods=["GET", "POST"])
def add():
    return _form_page(None)


@bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
def edit(product_id: int):
    return _form_page(product_id)
