"""Form validation rules. No database needed."""
from decimal import Decimal

import pytest

from app.validation import MAX_QUANTITY, MESSAGES, validate_product

CATEGORIES = {1, 2, 3}
GOOD = {
    "name": "أرز بسمتي 1 كغم",
    "barcode": "6291003100011",
    "price": "12.50",
    "quantity": "140",
    "category_id": "1",
}


def check(taken=(), **changes):
    form = {**GOOD, **changes}
    return validate_product(form, category_ids=CATEGORIES, barcode_taken=lambda b: b in taken)


def only_error(field, message_key, **changes):
    product, errors = check(**changes)
    assert product is None
    assert errors == {field: MESSAGES[message_key]}


def test_valid_form_returns_clean_values():
    product, errors = check()
    assert errors == {}
    assert (product.name, product.barcode, product.price, product.quantity, product.category_id) == (
        "أرز بسمتي 1 كغم", "6291003100011", Decimal("12.50"), 140, 1)


def test_name_is_trimmed_and_inner_whitespace_collapsed():
    assert check(name="  أرز   بسمتي \n 1 كغم ")[0].name == "أرز بسمتي 1 كغم"


def test_name_required_and_limits():
    only_error("name", "name_required", name="")
    only_error("name", "name_required", name="   \t ")
    only_error("name", "name_long", name="ا" * 151)
    assert check(name="ا" * 150)[1] == {}


def test_name_rejects_control_characters():
    only_error("name", "name_invalid", name="منتج\x00خفي")


@pytest.mark.parametrize("barcode", ["1234", "0123", "9" * 32, "٦٢٩١٠٠٣١٠٠٠١١"])
def test_good_barcodes(barcode):
    assert check(barcode=barcode)[1] == {}


def test_barcode_keeps_leading_zeros_and_converts_arabic_digits():
    assert check(barcode="0291003100042")[0].barcode == "0291003100042"
    assert check(barcode="٦٢٩١٠٠٣١٠٠٠١١")[0].barcode == "6291003100011"


@pytest.mark.parametrize("barcode", ["123", "9" * 33, "6291-0031", "62910 031", "62910a31", "٦٢٩.١٠٠"])
def test_bad_barcode_format(barcode):
    only_error("barcode", "barcode_format", barcode=barcode)


def test_barcode_required_and_unique():
    only_error("barcode", "barcode_required", barcode="  ")
    product, errors = check(taken={"6291003100011"})
    assert product is None and errors == {"barcode": MESSAGES["barcode_taken"]}


def test_taken_barcode_is_checked_after_normalising_digits():
    product, errors = check(taken={"6291003100011"}, barcode="٦٢٩١٠٠٣١٠٠٠١١")
    assert errors == {"barcode": MESSAGES["barcode_taken"]}


@pytest.mark.parametrize(
    "raw, expected",
    [("12.50", "12.50"), ("12.5", "12.50"), ("12", "12.00"), ("0.01", "0.01"), ("12.500", "12.50"),
     ("١٢٫٥٠", "12.50"), ("99999999.99", "99999999.99"), (" 7.25 ", "7.25")],
)
def test_good_prices(raw, expected):
    product, errors = check(price=raw)
    assert errors == {} and product.price == Decimal(expected)


def test_price_errors():
    only_error("price", "price_required", price="")
    for raw in ("abc", "12,50", "1e3", "NaN", "Infinity", "12.", ".5", "--3", "1 2"):
        only_error("price", "price_number", price=raw)
    for raw in ("0", "0.00", "-1", "-0.01"):
        only_error("price", "price_positive", price=raw)
    only_error("price", "price_decimals", price="1.234")
    only_error("price", "price_large", price="100000000")
    only_error("price", "price_large", price="9" * 40)


@pytest.mark.parametrize("raw, expected", [("0", 0), ("1", 1), ("140", 140), (" 25 ", 25),
                                           ("٥٠", 50), (str(MAX_QUANTITY), MAX_QUANTITY)])
def test_good_quantities_zero_is_allowed(raw, expected):
    product, errors = check(quantity=raw)
    assert errors == {} and product.quantity == expected


def test_quantity_errors():
    only_error("quantity", "quantity_required", quantity="")
    for raw in ("2.5", "abc", "1e3", "٣٫٥", "1,000"):
        only_error("quantity", "quantity_integer", quantity=raw)
    only_error("quantity", "quantity_negative", quantity="-1")
    only_error("quantity", "quantity_large", quantity=str(MAX_QUANTITY + 1))


def test_category_must_be_chosen_and_exist():
    only_error("category_id", "category_required", category_id="")
    for raw in ("99", "0", "abc", "-1", "1.5", "1 OR 1=1"):
        only_error("category_id", "category_invalid", category_id=raw)
    assert check(category_id="3")[0].category_id == 3


def test_missing_fields_are_all_reported_at_once():
    product, errors = validate_product({}, category_ids=CATEGORIES, barcode_taken=lambda b: False)
    assert product is None
    assert set(errors) == {"name", "barcode", "price", "quantity", "category_id"}
