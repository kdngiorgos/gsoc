from decimal import Decimal
import pytest
from transformers.amount_parser import parse_amount


@pytest.mark.parametrize("raw,expected", [
    ("1.661.761,40", Decimal("1661761.40")),
    ("71.372,00",    Decimal("71372.00")),
    ("492.293,95",   Decimal("492293.95")),
    ("0,00",         Decimal("0.00")),
    ("65.000,00",    Decimal("65000.00")),
    ("100",          Decimal("100")),
    ("22.166.211,04", Decimal("22166211.04")),
    ("-1.000,50",    Decimal("-1000.50")),
])
def test_valid_amounts(raw, expected):
    assert parse_amount(raw) == expected


@pytest.mark.parametrize("raw", [
    "",
    "   ",
    "-",
    "—",
    "..",
    "N/A",
    None,
])
def test_returns_none_for_empty_or_invalid(raw):
    assert parse_amount(raw) is None


def test_handles_non_breaking_space():
    assert parse_amount("\xa071.372,00") == Decimal("71372.00")
