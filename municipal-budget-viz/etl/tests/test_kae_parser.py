import pytest
from transformers.kae_parser import get_parent_code, get_level, build_category_tree


# --- get_parent_code ---

@pytest.mark.parametrize("code,expected_parent", [
    # Format A
    ("00",           None),
    ("00-60",        "00"),
    ("00-603",       "00-60"),
    ("00-6031",      "00-603"),
    ("00-6031.0001", "00-6031"),
    # Format B
    ("0111",         None),
    ("0111.00000",   "0111"),
    ("0115.00001",   "0115"),
])
def test_get_parent_code(code, expected_parent):
    assert get_parent_code(code) == expected_parent


# --- get_level ---

@pytest.mark.parametrize("code,expected_level", [
    ("00",           0),
    ("00-60",        1),
    ("00-603",       2),
    ("00-6031",      3),
    ("00-6031.0001", 4),
    ("0111",         0),
    ("0111.00000",   1),
])
def test_get_level(code, expected_level):
    assert get_level(code) == expected_level


# --- build_category_tree ---

def test_build_category_tree_basic():
    rows = [
        {"code": "00",           "description": "Γενικές Υπηρεσίες"},
        {"code": "00-60",        "description": "Αμοιβές"},
        {"code": "00-603",       "description": "Αμοιβές υπαλλήλων"},
        {"code": "00-6031",      "description": "Τακτικές αποδοχές"},
        {"code": "00-6031.0001", "description": "Τακτικές αποδοχές - λεπτομέρεια"},
    ]
    nodes = build_category_tree(rows)
    assert len(nodes) == 5
    codes = [n.code for n in nodes]
    assert "00" in codes
    assert "00-6031.0001" in codes

    root = next(n for n in nodes if n.code == "00")
    assert root.parent_code is None
    assert root.level == 0

    detail = next(n for n in nodes if n.code == "00-6031.0001")
    assert detail.parent_code == "00-6031"
    assert detail.level == 4


def test_build_category_tree_deduplicates():
    rows = [
        {"code": "00-60", "description": "First"},
        {"code": "00-60", "description": "Duplicate"},
    ]
    nodes = build_category_tree(rows)
    assert len(nodes) == 1
    assert nodes[0].description == "First"


def test_build_category_tree_skips_empty_codes():
    rows = [
        {"code": "",     "description": "Should skip"},
        {"code": "00-60", "description": "Valid"},
    ]
    nodes = build_category_tree(rows)
    assert len(nodes) == 1
