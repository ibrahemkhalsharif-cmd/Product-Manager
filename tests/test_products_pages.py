"""The products page against a real MariaDB (test database only)."""
import re

import pytest
from helpers import count, seed, token_from

pytestmark = pytest.mark.integration


SAMPLE = [
    ("أرز بسمتي 1 كغم", "6291003100011", "12.50", 140),
    ("سكر أبيض 1 كغم", "6291003100028", "4.75", 220),
    ("معكرونة سباغيتي", "0291003100042", "3.25", 0),
    ("قلم 5000", "1111000011110", "1.00", 10),
]


def test_empty_database_shows_arabic_empty_message(shop):
    html = shop.test_client().get("/").get_data(as_text=True)
    assert 'dir="rtl"' in html and "لا توجد منتجات بعد" in html


def test_list_shows_columns_prices_and_out_of_stock_badge(shop):
    seed(shop, SAMPLE)
    html = shop.test_client().get("/").get_data(as_text=True)
    for heading in ("الاسم", "الباركود", "التصنيف", "السعر", "الكمية"):
        assert heading in html
    assert "أرز بسمتي 1 كغم" in html and "مواد غذائية" in html
    assert "12.50" in html and "4.75" in html
    assert html.count("نفد") == 1  # only the product with quantity 0
    assert "إجمالي المنتجات: 4" in html


def test_list_is_sorted_by_name(shop):
    seed(shop, SAMPLE)
    html = shop.test_client().get("/").get_data(as_text=True)
    positions = [html.index(name) for name in ("أرز", "سكر", "قلم", "معكرونة")]
    assert positions == sorted(positions)


def test_search_by_name_substring(shop):
    seed(shop, SAMPLE)
    html = shop.test_client().get("/?q=سكر").get_data(as_text=True)
    assert "سكر أبيض" in html and "أرز بسمتي" not in html
    assert "عدد النتائج: 1" in html


def test_search_by_barcode_prefix_including_leading_zero(shop):
    seed(shop, SAMPLE)
    client = shop.test_client()
    html = client.get("/?q=6291003").get_data(as_text=True)
    assert "أرز بسمتي" in html and "سكر أبيض" in html and "معكرونة" not in html
    html = client.get("/?q=0291").get_data(as_text=True)
    assert "معكرونة" in html and "أرز بسمتي" not in html


def test_search_by_barcode_accepts_arabic_indic_digits(shop):
    seed(shop, SAMPLE)
    html = shop.test_client().get("/?q=٦٢٩١٠٠٣").get_data(as_text=True)
    assert "أرز بسمتي" in html and "سكر أبيض" in html


def test_four_digits_search_barcodes_but_shorter_numbers_search_names(shop):
    seed(shop, SAMPLE)
    client = shop.test_client()
    # "5000" has 4 digits: treated as a barcode prefix, so the name "قلم 5000" is not matched.
    assert "لا توجد منتجات تطابق" in client.get("/?q=5000").get_data(as_text=True)
    # "500" has 3 digits: treated as a name search.
    assert "قلم 5000" in client.get("/?q=500").get_data(as_text=True)


def test_search_without_results_says_so(shop):
    seed(shop, SAMPLE)
    html = shop.test_client().get("/?q=لا يوجد").get_data(as_text=True)
    assert "لا توجد منتجات تطابق «لا يوجد»" in html


def test_like_wildcards_are_treated_as_plain_text(shop):
    seed(shop, SAMPLE)
    client = shop.test_client()
    for q in ("%", "_", "أرز_بسمتي", "أرز%كغم"):
        assert "لا توجد منتجات تطابق" in client.get("/", query_string={"q": q}).get_data(as_text=True)


def test_sql_injection_attempt_is_harmless(shop):
    seed(shop, SAMPLE)
    response = shop.test_client().get("/", query_string={"q": "' OR '1'='1' --"})
    assert response.status_code == 200
    assert "لا توجد منتجات تطابق" in response.get_data(as_text=True)
    assert count(shop) == 4


def test_product_names_are_html_escaped(shop):
    seed(shop, [("<script>alert(1)</script>", "6291000000001", "1.00", 1)])
    html = shop.test_client().get("/").get_data(as_text=True)
    assert "<script>alert(1)" not in html and "&lt;script&gt;" in html


def test_paging_splits_the_list_in_pages_of_twenty(shop):
    seed(shop, [(f"منتج {i:02d}", f"629100{i:07d}", "1.00", 1) for i in range(1, 46)])
    client = shop.test_client()
    page1 = client.get("/").get_data(as_text=True)
    assert page1.count("<tr>") == 21 and "منتج 01" in page1 and "منتج 21" not in page1
    assert "الصفحة 1 من 3" in page1 and "التالي" in page1 and "السابق" not in page1
    page3 = client.get("/?page=3").get_data(as_text=True)
    assert page3.count("<tr>") == 6 and "منتج 41" in page3 and "منتج 45" in page3
    assert "السابق" in page3 and "التالي" not in page3


def test_page_number_is_clamped_to_a_valid_page(shop):
    seed(shop, [(f"منتج {i:02d}", f"629100{i:07d}", "1.00", 1) for i in range(1, 46)])
    client = shop.test_client()
    assert "الصفحة 3 من 3" in client.get("/?page=999").get_data(as_text=True)
    for bad in ("abc", "0", "-5", ""):
        assert "الصفحة 1 من 3" in client.get("/", query_string={"page": bad}).get_data(as_text=True)


def test_paging_links_keep_the_search_text(shop):
    seed(shop, [(f"منتج {i:02d}", f"629100{i:07d}", "1.00", 1) for i in range(1, 46)])
    html = shop.test_client().get("/", query_string={"q": "منتج"}).get_data(as_text=True)
    assert "عدد النتائج: 45" in html
    assert re.search(r'href="/\?q=[^"]+&amp;page=2"', html)


def test_delete_removes_product_and_shows_message(shop):
    ids = seed(shop, SAMPLE)
    client = shop.test_client()
    token = token_from(client.get("/").get_data(as_text=True))
    response = client.post(f"/products/{ids[0]}/delete", data={"csrf_token": token})
    assert response.status_code == 302
    html = client.get("/").get_data(as_text=True)
    assert "تم حذف المنتج «أرز بسمتي 1 كغم»" in html
    assert count(shop) == 3 and count(shop, "id = %s", (ids[0],)) == 0


def test_delete_returns_to_the_same_search_and_page(shop):
    ids = seed(shop, SAMPLE)
    client = shop.test_client()
    token = token_from(client.get("/").get_data(as_text=True))
    response = client.post(
        f"/products/{ids[1]}/delete", data={"csrf_token": token, "q": "كغم", "page": "1"}
    )
    assert "q=" in response.headers["Location"]


def test_delete_without_csrf_token_is_refused(shop):
    ids = seed(shop, SAMPLE)
    response = shop.test_client().post(f"/products/{ids[0]}/delete")
    assert response.status_code == 400
    assert count(shop) == 4


def test_delete_needs_post_and_a_known_id(shop):
    ids = seed(shop, SAMPLE)
    client = shop.test_client()
    assert client.get(f"/products/{ids[0]}/delete").status_code == 405
    token = token_from(client.get("/").get_data(as_text=True))
    response = client.post("/products/999999/delete", data={"csrf_token": token})
    assert response.status_code == 404 and "الصفحة غير موجودة" in response.get_data(as_text=True)
    assert count(shop) == 4


def test_every_delete_button_asks_for_confirmation(shop):
    seed(shop, SAMPLE)
    html = shop.test_client().get("/").get_data(as_text=True)
    assert html.count("data-confirm=") == 4
    assert "هل تريد حذف المنتج" in html
