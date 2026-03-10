"""Tests for the Tier-2 text-mode regex extractor."""

import pytest
from decimal import Decimal

from extractors.text_extractor import _parse_budget_lines, _parse_technical_lines


# ---------------------------------------------------------------------------
# _parse_budget_lines
# ---------------------------------------------------------------------------

class TestParseBudgetLines:

    def test_leaf_item_four_amounts(self):
        lines = ["00-6031 Αμοιβές και έξοδα 1.000,00 2.000,00 3.000,00 100,00"]
        items = _parse_budget_lines(lines)
        assert len(items) == 1
        item = items[0]
        assert item["code"] == "00-6031"
        assert item["description"] == "Αμοιβές και έξοδα"
        assert item["amount2024"] == Decimal("1000.00")
        assert item["amountMidYear"] == Decimal("2000.00")
        assert item["amount2025"] == Decimal("3000.00")
        assert item["amountVariance"] == Decimal("100.00")

    def test_leaf_item_one_amount(self):
        lines = ["00-6031 Αμοιβές 5.500,50"]
        items = _parse_budget_lines(lines)
        assert len(items) == 1
        assert items[0]["amount2024"] == Decimal("5500.50")
        assert items[0]["amountMidYear"] is None
        assert items[0]["amount2025"] is None

    def test_category_header_no_amounts(self):
        """A KAE line with no amounts should produce a header dict (all amounts None)."""
        lines = ["00-60 Αμοιβές"]
        items = _parse_budget_lines(lines)
        assert len(items) == 1
        item = items[0]
        assert item["code"] == "00-60"
        assert item["description"] == "Αμοιβές"
        assert item["amount2024"] is None
        assert item["amount2025"] is None

    def test_subtotal_line_not_filtered_by_parser(self):
        """text_extractor does NOT filter subtotals — that is budget_extractor's job."""
        lines = ["00-60 Σύνολο κατηγορίας 1.000,00"]
        items = _parse_budget_lines(lines)
        # Parser returns the item; classification happens in budget_extractor
        assert len(items) == 1
        assert items[0]["code"] == "00-60"

    def test_non_kae_line_ignored(self):
        lines = ["Αυτή είναι μια κανονική γραμμή χωρίς κωδικό"]
        items = _parse_budget_lines(lines)
        assert items == []

    def test_empty_lines_ignored(self):
        lines = ["", "   ", "\t"]
        assert _parse_budget_lines(lines) == []

    def test_format_b_code(self):
        """Format B code (4-digit, e.g. 0111) is recognised."""
        lines = ["0111 Τακτικά έσοδα 10.000,00"]
        items = _parse_budget_lines(lines)
        assert len(items) == 1
        assert items[0]["code"] == "0111"

    def test_format_b_leaf_code(self):
        lines = ["0111.00000 Φόροι ακίνητης περιουσίας 500,00"]
        items = _parse_budget_lines(lines)
        assert len(items) == 1
        assert items[0]["code"] == "0111.00000"

    @pytest.mark.parametrize("line,expected_code", [
        ("00 Γενικά 1.000,00",               "00"),
        ("00-60 Ομάδα 1.000,00",             "00-60"),
        ("00-603 Άρθρο 1.000,00",            "00-603"),
        ("00-6031 Υποκατηγορία 1.000,00",    "00-6031"),
        ("00-6031.0001 Λεπτομέρεια 1.000,00","00-6031.0001"),
    ])
    def test_all_format_a_levels(self, line, expected_code):
        items = _parse_budget_lines([line])
        assert len(items) == 1
        assert items[0]["code"] == expected_code

    def test_multiple_lines(self):
        lines = [
            "00-60 Ομάδα",
            "00-6031 Αμοιβές 1.000,00",
            "Κεφάλαιο 1",
            "00-6032 Έξοδα 2.000,00",
        ]
        items = _parse_budget_lines(lines)
        assert len(items) == 3
        assert items[0]["code"] == "00-60"
        assert items[1]["code"] == "00-6031"
        assert items[2]["code"] == "00-6032"


# ---------------------------------------------------------------------------
# _parse_technical_lines
# ---------------------------------------------------------------------------

class TestParseTechnicalLines:

    def test_basic_project(self):
        lines = ["1.1 25-7412.007 Κατασκευή αγωγού 1.000,00"]
        projects = _parse_technical_lines(lines)
        assert len(projects) == 1
        p = projects[0]
        assert p["projectCode"] == "25-7412.007"
        assert p["section"] == "1.1"
        assert p["description"] == "Κατασκευή αγωγού"
        assert len(p["items"]) == 1
        assert p["items"][0]["amount"] == Decimal("1000.00")
        assert p["items"][0]["label"] == "Προϋπολογισμός Μελέτης"

    def test_project_multiple_amounts(self):
        lines = ["2.3 30-7323.096 Οδοποιία 10.000,00 8.000,00 2.000,00"]
        projects = _parse_technical_lines(lines)
        assert len(projects) == 1
        assert len(projects[0]["items"]) == 3
        assert projects[0]["items"][1]["label"] == "Εγκεκριμένη Πίστωση"

    def test_budget_ref_extracted(self):
        lines = ["1.2 25-7412.008 Έργο ..9762.05.049 5.000,00"]
        projects = _parse_technical_lines(lines)
        assert len(projects) == 1
        assert projects[0]["budgetRef"] == "..9762.05.049"

    def test_multiline_description_buffered(self):
        lines = [
            "1.1 25-7412.007 Κατασκευή",
            "αγωγού ύδρευσης",           # continuation — no amounts
            "2.1 30-7311.001 Άλλο έργο 500,00",
        ]
        projects = _parse_technical_lines(lines)
        assert len(projects) == 2
        # Description continuation should be buffered into the first project
        assert "αγωγού ύδρευσης" in projects[0]["description"]

    def test_no_project_code_yields_empty(self):
        lines = ["Αυτή είναι μια γραμμή", "1.1 κάτι άλλο"]
        assert _parse_technical_lines(lines) == []

    def test_project_without_section(self):
        lines = ["25-7412.007 Έργο χωρίς ενότητα 3.000,00"]
        projects = _parse_technical_lines(lines)
        assert len(projects) == 1
        assert projects[0]["section"] == ""
        assert projects[0]["projectCode"] == "25-7412.007"

    def test_amount_line_between_projects_not_added_to_description(self):
        lines = [
            "1.1 25-7412.007 Πρώτο έργο 1.000,00",
            "1.000,00 2.000,00",          # pure-amount summary line
            "1.2 25-7413.001 Δεύτερο έργο 500,00",
        ]
        projects = _parse_technical_lines(lines)
        assert len(projects) == 2
        # Pure-amount line must not contaminate first project description
        assert "1.000,00" not in projects[0]["description"]
