"""Small text helpers shared by the search box and form validation."""
from __future__ import annotations

# Arabic-Indic digits (U+0660-0669) and Persian digits (U+06F0-06F9) become 0-9.
# U+066B (Arabic decimal separator) becomes "."; U+066C (Arabic thousands separator) is dropped.
_DIGIT_MAP: dict[int, int | None] = {
    **{0x0660 + i: 0x30 + i for i in range(10)},
    **{0x06F0 + i: 0x30 + i for i in range(10)},
    0x066B: ord("."),
    0x066C: None,
}


def normalize_digits(text: str) -> str:
    """Turn Arabic-Indic and Persian digits into ASCII digits."""
    return text.translate(_DIGIT_MAP)


def escape_like(text: str) -> str:
    """Make %, _ and \\ literal inside a SQL LIKE pattern."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
