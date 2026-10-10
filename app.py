"""Product Manager: a two-page Flask app (products list, add/edit form)."""
import hmac
import re
import secrets
from decimal import Decimal, InvalidOperation

import pymysql
from flask import (Flask, abort, flash, redirect, render_template, request,
                   session, url_for)

import config
from db import close_db, get_db

app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY
app.teardown_appcontext(close_db)

# Arabic-Indic digits and the Arabic decimal mark are accepted and converted.
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٫", "0123456789.")
MAX_PRICE = Decimal("99999999.99")
MAX_QUANTITY = 1_000_000_000


# ---------- CSRF protection ----------

def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def check_csrf():
    if request.method == "POST":
        expected = session.get("_csrf", "")
        sent = request.form.get("_csrf", "")
        if not expected or not hmac.compare_digest(expected.encode(), sent.encode()):
            abort(400)


# ---------- Helpers ----------

def get_categories():
    with get_db().cursor() as cur:
        cur.execute("SELECT id, name FROM categories ORDER BY name")
        return cur.fetchall()


def get_product_or_404(product_id):
    with get_db().cursor() as cur:
        cur.execute(
            "SELECT id, name, barcode, price, quantity, category_id "
            "FROM products WHERE id = %s",
            (product_id,),
        )
        product = cur.fetchone()
    if product is None:
        abort(404)
    return product


def validate_product(form, product_id=None):
    """Return (clean_values, errors). Error messages are in Arabic."""
    errors = {}
    name = form.get("name", "").strip()
    barcode = form.get("barcode", "").strip()
    price_raw = form.get("price", "").strip().translate(ARABIC_DIGITS)
    quantity_raw = form.get("quantity", "").strip().translate(ARABIC_DIGITS)
    category_raw = form.get("category_id", "").strip()

    # name
    if not name:
        errors["name"] = "اسم المنتج مطلوب."
    elif len(name) > 150:
        errors["name"] = "اسم المنتج يجب ألا يتجاوز 150 حرفًا."

    # barcode (required, unique)
    if not barcode:
        errors["barcode"] = "الباركود مطلوب."
    elif len(barcode) > 50:
        errors["barcode"] = "الباركود يجب ألا يتجاوز 50 حرفًا."
    else:
        with get_db().cursor() as cur:
            cur.execute(
                "SELECT id FROM products WHERE barcode = %s AND id <> %s",
                (barcode, product_id or 0),
            )
            if cur.fetchone():
                errors["barcode"] = "هذا الباركود مستخدم لمنتج آخر."

    # price (required, positive number, at most 2 decimals)
    price = None
    if not price_raw:
        errors["price"] = "السعر مطلوب."
    else:
        try:
            price = Decimal(price_raw)
            if not price.is_finite():
                raise InvalidOperation
        except InvalidOperation:
            errors["price"] = "السعر يجب أن يكون رقمًا صحيحًا."
        else:
            if price <= 0:
                errors["price"] = "السعر يجب أن يكون أكبر من صفر."
            elif price != price.quantize(Decimal("0.01")):
                errors["price"] = "السعر يجب ألا يحتوي على أكثر من خانتين عشريتين."
            elif price > MAX_PRICE:
                errors["price"] = "السعر كبير جدًا."

    # quantity (required, positive whole number)
    quantity = None
    if not quantity_raw:
        errors["quantity"] = "الكمية مطلوبة."
    elif not re.fullmatch(r"\d+", quantity_raw):
        errors["quantity"] = "الكمية يجب أن تكون عددًا صحيحًا."
    else:
        quantity = int(quantity_raw)
        if quantity <= 0:
            errors["quantity"] = "الكمية يجب أن تكون أكبر من صفر."
        elif quantity > MAX_QUANTITY:
            errors["quantity"] = "الكمية كبيرة جدًا."

    # category (required, must exist)
    category_id = None
    if not category_raw:
        errors["category_id"] = "التصنيف مطلوب."
    elif not category_raw.isdigit():
        errors["category_id"] = "التصنيف غير صالح."
    else:
        with get_db().cursor() as cur:
            cur.execute("SELECT id FROM categories WHERE id = %s", (int(category_raw),))
            if cur.fetchone():
                category_id = int(category_raw)
            else:
                errors["category_id"] = "التصنيف غير صالح."

    values = {
        "name": name,
        "barcode": barcode,
        "price": price,
        "quantity": quantity,
        "category_id": category_id,
    }
    return values, errors


def form_values_for_redisplay():
    """Raw submitted values, so the form keeps what the user typed."""
    return {
        "name": request.form.get("name", ""),
        "barcode": request.form.get("barcode", ""),
        "price": request.form.get("price", ""),
        "quantity": request.form.get("quantity", ""),
        "category_id": request.form.get("category_id", ""),
    }


# ---------- Page 1: products list ----------

@app.route("/")
def products():
    q = request.args.get("q", "").strip()
    sql = (
        "SELECT p.id, p.name, p.barcode, p.price, p.quantity, c.name AS category "
        "FROM products p JOIN categories c ON c.id = p.category_id "
    )
    params = ()
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{escaped}%"
        sql += "WHERE p.name LIKE %s OR p.barcode LIKE %s "
        params = (like, like)
    sql += "ORDER BY p.name"
    with get_db().cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return render_template("products.html", products=rows, q=q)


@app.post("/products/<int:product_id>/delete")
def delete_product(product_id):
    product = get_product_or_404(product_id)
    db = get_db()
    with db.cursor() as cur:
        cur.execute("DELETE FROM products WHERE id = %s", (product_id,))
    db.commit()
    flash(f"تم حذف المنتج «{product['name']}».", "success")
    return redirect(url_for("products"))


# ---------- Page 2: add / edit form ----------

def save_and_redirect(sql, params, success_message, form_template_args):
    """Run an INSERT/UPDATE; on a barcode race, show the duplicate error."""
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(sql, params)
        db.commit()
    except pymysql.err.IntegrityError as exc:
        db.rollback()
        if exc.args and exc.args[0] == 1062:
            form_template_args["errors"] = {"barcode": "هذا الباركود مستخدم لمنتج آخر."}
            return render_template("product_form.html", **form_template_args), 400
        raise
    flash(success_message, "success")
    return redirect(url_for("products"))


@app.route("/products/new", methods=["GET", "POST"])
def add_product():
    ctx = {
        "title": "إضافة منتج",
        "categories": get_categories(),
        "values": {"name": "", "barcode": "", "price": "", "quantity": "", "category_id": ""},
        "errors": {},
    }
    if request.method == "POST":
        clean, errors = validate_product(request.form)
        ctx["values"] = form_values_for_redisplay()
        if errors:
            ctx["errors"] = errors
            return render_template("product_form.html", **ctx), 400
        return save_and_redirect(
            "INSERT INTO products (name, barcode, price, quantity, category_id) "
            "VALUES (%s, %s, %s, %s, %s)",
            (clean["name"], clean["barcode"], clean["price"],
             clean["quantity"], clean["category_id"]),
            f"تمت إضافة المنتج «{clean['name']}».",
            ctx,
        )
    return render_template("product_form.html", **ctx)


@app.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
def edit_product(product_id):
    product = get_product_or_404(product_id)
    ctx = {
        "title": "تعديل منتج",
        "categories": get_categories(),
        "values": {
            "name": product["name"],
            "barcode": product["barcode"],
            "price": f"{product['price']:.2f}",
            "quantity": str(product["quantity"]),
            "category_id": str(product["category_id"]),
        },
        "errors": {},
    }
    if request.method == "POST":
        clean, errors = validate_product(request.form, product_id=product_id)
        ctx["values"] = form_values_for_redisplay()
        if errors:
            ctx["errors"] = errors
            return render_template("product_form.html", **ctx), 400
        return save_and_redirect(
            "UPDATE products SET name = %s, barcode = %s, price = %s, "
            "quantity = %s, category_id = %s WHERE id = %s",
            (clean["name"], clean["barcode"], clean["price"],
             clean["quantity"], clean["category_id"], product_id),
            f"تم تحديث المنتج «{clean['name']}».",
            ctx,
        )
    return render_template("product_form.html", **ctx)


# ---------- Error pages (Arabic) ----------

@app.errorhandler(400)
def bad_request(_):
    return render_template(
        "error.html", heading="طلب غير صالح",
        message="انتهت صلاحية الصفحة أو أن الطلب غير صحيح. أعد تحميل الصفحة وحاول مرة أخرى."), 400


@app.errorhandler(404)
def not_found(_):
    return render_template(
        "error.html", heading="الصفحة غير موجودة",
        message="لم نعثر على ما تبحث عنه. ربما حُذف المنتج."), 404


@app.errorhandler(pymysql.err.OperationalError)
def database_unavailable(_):
    return render_template(
        "error.html", heading="تعذّر الاتصال بقاعدة البيانات",
        message="تأكد من تشغيل MariaDB ومن صحة إعدادات الملف .env "
                "(المضيف، المنفذ، المستخدم، كلمة المرور)."), 500


if __name__ == "__main__":
    app.run(debug=True)
