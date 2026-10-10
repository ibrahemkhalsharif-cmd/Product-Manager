"""Search, paging and text helpers. No database needed."""
import pytest

from app.products import (MAX_QUERY_LENGTH, build_filter, clean_query, page_window,
                          parse_page)
from app.textutil import escape_like, normalize_digits


def test_normalize_digits_converts_arabic_indic_and_persian_digits():
    assert normalize_digits("٠١٢٣٤٥٦٧٨٩") == "0123456789"
    assert normalize_digits("۰۱۲۳۴۵۶۷۸۹") == "0123456789"
    assert normalize_digits("١٢٫٥٠") == "12.50"      # Arabic decimal separator
    assert normalize_digits("١٬٢٠٠") == "1200"        # Arabic thousands separator is dropped
    assert normalize_digits("عصير 1 لتر") == "عصير 1 لتر"


def test_escape_like_makes_wildcards_literal():
    assert escape_like("50%") == "50\\%"
    assert escape_like("a_b") == "a\\_b"
    assert escape_like("a\\b") == "a\\\\b"


def test_empty_query_has_no_filter():
    assert build_filter("") == ("", ())


@pytest.mark.parametrize("q", ["6291003", "0291", "٦٢٩١٠٠٣", "9" * 32])
def test_four_to_thirty_two_digits_is_a_barcode_prefix_search(q):
    where, params = build_filter(q)
    assert where == "WHERE barcode LIKE %s"
    assert params[0].endswith("%") and not params[0].startswith("%")
    assert params[0][:-1].isascii() and params[0][:-1].isdigit()


@pytest.mark.parametrize("q", ["500", "12", "عصير", "أرز 1 كغم", "6291 0031", "9" * 33, "62910a"])
def test_everything_else_is_a_name_contains_search(q):
    where, params = build_filter(q)
    assert where == "WHERE name LIKE %s"
    assert params[0].startswith("%") and params[0].endswith("%")


def test_name_search_escapes_wildcards():
    assert build_filter("100%")[1] == ("%100\\%%",)
    assert build_filter("a_b")[1] == ("%a\\_b%",)


@pytest.mark.parametrize(
    "raw, expected",
    [(None, 1), ("", 1), ("abc", 1), ("0", 1), ("-4", 1), ("1.5", 1), ("3", 3), (" 7 ", 7)],
)
def test_parse_page_never_returns_less_than_one(raw, expected):
    assert parse_page(raw) == expected


def test_clean_query_trims_and_limits_length():
    assert clean_query(None) == ""
    assert clean_query("  أرز  ") == "أرز"
    assert len(clean_query("x" * 500)) == MAX_QUERY_LENGTH


@pytest.mark.parametrize(
    "page, pages, expected",
    [
        (1, 1, [1]),
        (1, 3, [1, 2, 3]),
        (1, 20, [1, 2, 3, None, 20]),
        (10, 20, [1, None, 8, 9, 10, 11, 12, None, 20]),
        (20, 20, [1, None, 18, 19, 20]),
        (4, 7, [1, 2, 3, 4, 5, 6, 7]),
    ],
)
def test_page_window_collapses_long_ranges(page, pages, expected):
    assert page_window(page, pages) == expected
