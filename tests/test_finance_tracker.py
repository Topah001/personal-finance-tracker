import unittest
from decimal import Decimal
from pathlib import Path

from finance_tracker import FinanceTracker, ValidationError, parse_amount


class FinanceTrackerTests(unittest.TestCase):
    def setUp(self):
        self.database = Path(__file__).with_name(".test_finance.db")
        self.database.unlink(missing_ok=True)
        self.addCleanup(self.database.unlink, missing_ok=True)
        self.tracker = FinanceTracker(self.database)

    def test_amount_validation(self):
        self.assertEqual(parse_amount("1.20"), Decimal("1.20"))
        for value in ("0", "-2", "NaN", "1.001", "abc"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                parse_amount(value)

    def test_month_report_totals_and_categories(self):
        self.tracker.add("income", "2500", "Salary", "Pay", "2026-10-01")
        self.tracker.add("expense", "12.35", "Food", "Lunch", "2026-10-02")
        self.tracker.add("expense", "7.65", "Food", "Coffee", "2026-10-02")
        self.tracker.add("income", "10", "Gift", "Gift", "2026-09-30")
        report = self.tracker.report("2026-10")
        self.assertEqual(report["income"], Decimal("2500"))
        self.assertEqual(report["expenses"], Decimal("20"))
        self.assertEqual(report["balance"], Decimal("2480"))
        self.assertEqual(report["categories"]["Food"]["expense"], Decimal("20"))
        self.assertEqual(len(self.tracker.list_transactions("2026-10")), 3)

    def test_invalid_fields_are_rejected(self):
        with self.assertRaises(ValidationError):
            self.tracker.add("transfer", "5", "Other", "x", "2026-01-01")
        with self.assertRaises(ValidationError):
            self.tracker.add("expense", "5", " ", "x", "2026-01-01")
        with self.assertRaises(ValidationError):
            self.tracker.add("expense", "5", "Other", "x", "2026-02-30")


if __name__ == "__main__":
    unittest.main()
