"""Validation of the add/edit product form.

Pure functions: no database access here. The two things that need the database (does this
category exist, is this barcode taken) are passed in by the caller. The rules match
sql/schema.sql, which stays the final backstop.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Container, Mapping
from dataclasses import dataclass
from decimal import Decimal

from .textutil import normalize_digits

NAME_MAX = 150
BARCODE_PATTERN = re.compile(r"[0-9]{4,32}")
NUMBER_PATTERN = re.compile(r"-?[0-9]+(\.[0-9]+)?")
INTEGER_PATTERN = re.compile(r"-?[0-9]+")
MAX_PRICE = Decimal("99999999.99")  # DECIMAL(10,2)
MAX_QUANTITY = 2_147_483_647        # INT (signed)
CENT = Decimal("0.01")

MESSAGES = {
    "name_required": "اسم المنتج مطلوب.",
    "name_long": f"اسم المنتج يجب ألا يتجاوز {NAME_MAX} حرفًا.",
    "name_invalid": "اسم المنتج يحتوي على رموز غير مسموحة.",
    "barcode_required": "الباركود مطلوب.",
    "barcode_format": "الباركود يجب أن يتكون من 4 إلى 32 رقمًا فقط.",
    "barcode_taken": "هذا الباركود مستخدم لمنتج آخر.",
    "price_required": "السعر مطلوب.",
    "price_number": "السعر يجب أن يكون رقمًا، مثل 12.50.",
    "price_positive": "السعر يجب أن يكون أكبر من صفر.",
    "price_decimals": "السعر يجب ألا يزيد عن خانتين عشريتين.",
    "price_large": "السعر كبير جدًا.",
    "quantity_required": "الكمية مطلوبة.",
    "quantity_integer": "الكمية يجب أن تكون عددًا صحيحًا.",
    "quantity_negative": "الكمية لا يمكن أن تكون سالبة.",
    "quantity_large": "الكمية كبيرة جدًا.",
    "category_required": "التصنيف مطلوب.",
    "category_invalid": "التصنيف غير صالح.",
}


@dataclass(frozen=True)
class ProductData:
    name: str
    barcode: str
    price: Decimal
    quantity: int
    category_id: int


def _clean_name(raw: str) -> tuple[str, str | None]:
    name = " ".join(raw.split())  # trims and collapses runs of whitespace
    if not name:
        return name, "name_required"
    if len(name) > NAME_MAX:
        return name, "name_long"
    if any(unicodedata.category(ch) == "Cc" for ch in name):
        return name, "name_invalid"
    return name, None


def _clean_price(raw: str) -> tuple[Decimal | None, str | None]:
    text = normalize_digits(raw.strip())
    if not text:
        return None, "price_required"
    if not NUMBER_PATTERN.fullmatch(text):
        return None, "price_number"
    value = Decimal(text)
    if value <= 0:
        return None, "price_positive"
    if value > MAX_PRICE:
        return None, "price_large"
    if value != value.quantize(CENT):
        return None, "price_decimals"
    return value.quantize(CENT), None


def _clean_quantity(raw: str) -> tuple[int | None, str | None]:
    text = normalize_digits(raw.strip())
    if not text:
        return None, "quantity_required"
    if not INTEGER_PATTERN.fullmatch(text):
        return None, "quantity_integer"
    value = int(text)
    if value < 0:
        return None, "quantity_negative"
    if value > MAX_QUANTITY:
        return None, "quantity_large"
    return value, None  # 0 is allowed: it means out of stock


def validate_product(
    form: Mapping[str, str],
    *,
    category_ids: Container[int],
    barcode_taken: Callable[[str], bool],
) -> tuple[ProductData | None, dict[str, str]]:
    """Return (product, errors). product is None when errors is not empty."""
    errors: dict[str, str] = {}

    name, problem = _clean_name(form.get("name") or "")
    if problem:
        errors["name"] = MESSAGES[problem]

    barcode = normalize_digits((form.get("barcode") or "").strip())
    if not barcode:
        errors["barcode"] = MESSAGES["barcode_required"]
    elif not BARCODE_PATTERN.fullmatch(barcode):
        errors["barcode"] = MESSAGES["barcode_format"]
    elif barcode_taken(barcode):
        errors["barcode"] = MESSAGES["barcode_taken"]

    price, problem = _clean_price(form.get("price") or "")
    if problem:
        errors["price"] = MESSAGES[problem]

    quantity, problem = _clean_quantity(form.get("quantity") or "")
    if problem:
        errors["quantity"] = MESSAGES[problem]

    category_raw = (form.get("category_id") or "").strip()
    category_id = None
    if not category_raw:
        errors["category_id"] = MESSAGES["category_required"]
    elif category_raw.isascii() and category_raw.isdigit() and int(category_raw) in category_ids:
        category_id = int(category_raw)
    else:
        errors["category_id"] = MESSAGES["category_invalid"]

    if errors:
        return None, errors
    return ProductData(name, barcode, price, quantity, category_id), {}  # type: ignore[arg-type]
