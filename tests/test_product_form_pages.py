"""The add and edit pages against a real MariaDB (test database only)."""
from decimal import Decimal

import pytest
from helpers import category_id_of, count, fetch_product, seed, token_from

from app import products as products_module

pytestmark = pytest.mark.integration

SAMPLE = [
    ("أرز بسمتي 1 كغم", "6291003100011", "12.50", 140),
    ("سكر أبيض 1 كغم", "6291003100028", "4.75", 220),
]
CATEGORY = "مواد غذائية"


def form_for(app, **changes):
    values = {
        "name": "شاي أخضر",
        "barcode": "6291009900011",
        "price": "6.25",
        "quantity": "30",
        "category_id": str(category_id_of(app, CATEGORY)),
    }
    values.update(changes)
    return values


def with_token(client, path="/products/new"):
    return token_from(client.get(path).get_data(as_text=True))


def test_add_page_shows_the_form_with_categories(shop):
    seed(shop, SAMPLE)
    html = shop.test_client().get("/products/new").get_data(as_text=True)
    assert 'dir="rtl"' in html and "إضافة منتج" in html
    for label in ("اسم المنتج", "الباركود", "التصنيف", "السعر", "الكمية"):
        assert label in html
    assert CATEGORY in html and "حفظ" in html and "إلغاء" in html
    assert 'name="csrf_token"' in html


def test_adding_a_product_saves_it_and_returns_to_the_list(shop):
    seed(shop, SAMPLE)
    client = shop.test_client()
    response = client.post("/products/new", data={**form_for(shop), "csrf_token": with_token(client)})
    assert response.status_code == 302 and response.headers["Location"].endswith("/")
    html = client.get("/").get_data(as_text=True)
    assert "تمت إضافة المنتج «شاي أخضر»" in html and "شاي أخضر" in html
    assert count(shop) == 3


def test_added_values_are_stored_exactly_including_zero_quantity(shop):
    seed(shop, SAMPLE)
    client = shop.test_client()
    data = form_for(shop, name="  حليب   طويل الأجل ", barcode="0291009900011", price="٣٫٥", quantity="0")
    client.post("/products/new", data={**data, "csrf_token": with_token(client)})
    with shop.app_context():
        from app import db
        with db.get_db().cursor() as cur:
            cur.execute("SELECT * FROM products WHERE barcode = %s", ("0291009900011",))
            row = cur.fetchone()
    assert row["name"] == "حليب طويل الأجل"
    assert row["price"] == Decimal("3.50") and row["quantity"] == 0
    assert row["barcode"] == "0291009900011"  # leading zero kept


def test_invalid_form_is_rejected_with_arabic_messages_and_keeps_input(shop):
    seed(shop, SAMPLE)
    client = shop.test_client()
    bad = form_for(shop, name="", price="-5", quantity="2.5", barcode="12")
    response = client.post("/products/new", data={**bad, "csrf_token": with_token(client)})
    html = response.get_data(as_text=True)
    assert response.status_code == 400
    for message in ("اسم المنتج مطلوب", "السعر يجب أن يكون أكبر من صفر",
                    "الكمية يجب أن تكون عددًا صحيحًا", "الباركود يجب أن يتكون من 4 إلى 32 رقمًا"):
        assert message in html
    assert 'value="-5"' in html and 'value="2.5"' in html and 'value="12"' in html
    assert count(shop) == 2


def test_duplicate_barcode_is_rejected(shop):
    seed(shop, SAMPLE)
    client = shop.test_client()
    data = form_for(shop, barcode="6291003100011")
    response = client.post("/products/new", data={**data, "csrf_token": with_token(client)})
    assert response.status_code == 400
    assert "هذا الباركود مستخدم لمنتج آخر" in response.get_data(as_text=True)
    assert count(shop) == 2


def test_duplicate_barcode_race_shows_the_field_error_not_a_server_error(shop, monkeypatch):
    """If another request wins between the check and the INSERT, MariaDB's UNIQUE key decides."""
    seed(shop, SAMPLE)
    real = products_module.validate_product
    monkeypatch.setattr(
        products_module, "validate_product",
        lambda form, *, category_ids, barcode_taken: real(
            form, category_ids=category_ids, barcode_taken=lambda _b: False),
    )
    client = shop.test_client()
    data = form_for(shop, barcode="6291003100011")
    response = client.post("/products/new", data={**data, "csrf_token": with_token(client)})
    assert response.status_code == 400
    assert "هذا الباركود مستخدم لمنتج آخر" in response.get_data(as_text=True)
    assert count(shop) == 2


def test_unknown_category_is_rejected(shop):
    seed(shop, SAMPLE)
    client = shop.test_client()
    response = client.post("/products/new",
                           data={**form_for(shop, category_id="99999"), "csrf_token": with_token(client)})
    assert response.status_code == 400 and "التصنيف غير صالح" in response.get_data(as_text=True)
    assert count(shop) == 2


def test_adding_needs_a_csrf_token(shop):
    seed(shop, SAMPLE)
    response = shop.test_client().post("/products/new", data=form_for(shop))
    assert response.status_code == 400 and count(shop) == 2


def test_edit_page_is_prefilled(shop):
    ids = seed(shop, SAMPLE)
    html = shop.test_client().get(f"/products/{ids[0]}/edit").get_data(as_text=True)
    assert "تعديل منتج" in html
    assert 'value="أرز بسمتي 1 كغم"' in html and 'value="6291003100011"' in html
    assert 'value="12.50"' in html and 'value="140"' in html
    assert "selected" in html


def test_editing_updates_the_product_and_keeps_the_others(shop):
    ids = seed(shop, SAMPLE)
    client = shop.test_client()
    path = f"/products/{ids[0]}/edit"
    data = form_for(shop, name="أرز مصري", barcode="6291003100011", price="9", quantity="0")
    response = client.post(path, data={**data, "csrf_token": with_token(client, path)})
    assert response.status_code == 302
    changed = fetch_product(shop, ids[0])
    assert changed["name"] == "أرز مصري" and changed["price"] == Decimal("9.00") and changed["quantity"] == 0
    untouched = fetch_product(shop, ids[1])
    assert untouched["name"] == "سكر أبيض 1 كغم" and untouched["price"] == Decimal("4.75")
    assert "تم تحديث المنتج «أرز مصري»" in client.get("/").get_data(as_text=True)


def test_editing_can_keep_its_own_barcode_but_not_take_another(shop):
    ids = seed(shop, SAMPLE)
    client = shop.test_client()
    path = f"/products/{ids[0]}/edit"
    token = with_token(client, path)
    same = client.post(path, data={**form_for(shop, barcode="6291003100011"), "csrf_token": token})
    assert same.status_code == 302
    other = client.post(path, data={**form_for(shop, barcode="6291003100028"), "csrf_token": token})
    assert other.status_code == 400
    assert "هذا الباركود مستخدم لمنتج آخر" in other.get_data(as_text=True)
    assert fetch_product(shop, ids[0])["barcode"] == "6291003100011"


def test_editing_an_unknown_product_gives_404(shop):
    seed(shop, SAMPLE)
    client = shop.test_client()
    assert client.get("/products/999999/edit").status_code == 404
    token = with_token(client)
    assert client.post("/products/999999/edit", data={**form_for(shop), "csrf_token": token}).status_code == 404


def test_list_page_links_to_add_and_edit(shop):
    ids = seed(shop, SAMPLE)
    html = shop.test_client().get("/").get_data(as_text=True)
    assert 'href="/products/new"' in html
    assert f'href="/products/{ids[0]}/edit"' in html and f'href="/products/{ids[1]}/edit"' in html
    empty_html = shop.test_client().get("/products/999999/edit")  # 404 page still renders in Arabic
    assert "الصفحة غير موجودة" in empty_html.get_data(as_text=True)


def test_empty_list_invites_adding_the_first_product(shop):
    html = shop.test_client().get("/").get_data(as_text=True)
    assert "أضف أول منتج" in html and 'href="/products/new"' in html
