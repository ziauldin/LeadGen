"""CSV export hardening against formula injection (CWE-1236)."""

from __future__ import annotations

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value: object) -> object:
    """Prefix text that a spreadsheet would evaluate as a formula with a single quote."""
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def safe_row(row: dict[str, object]) -> dict[str, object]:
    return {key: safe_cell(value) for key, value in row.items()}
