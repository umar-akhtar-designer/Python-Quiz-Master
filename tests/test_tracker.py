"""
test_tracker.py
===============
Automated tests for Python Smart Expense Tracker.

Run from the project folder:

    python3 -m unittest discover -s tests -v

The tests use temporary folders, so your real data file is never touched.
"""

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, timedelta

import budget
import expenses
import reports
import storage


class AmountAndDateTests(unittest.TestCase):
    def test_valid_amounts(self):
        self.assertEqual(expenses.parse_amount("12.5"), 12.5)
        self.assertEqual(expenses.parse_amount("$1,200.50"), 1200.50)
        self.assertEqual(expenses.parse_amount(" 3 "), 3.0)
        self.assertEqual(expenses.parse_amount(19.999), 20.0)

    def test_invalid_amounts(self):
        for value in ["", "   ", "abc", "0", "-5", "0.001", "1e999"]:
            with self.assertRaises(ValueError):
                expenses.parse_amount(value)

    def test_valid_dates(self):
        today = date(2026, 11, 17)
        self.assertEqual(expenses.parse_date("2026-11-17", today), "2026-11-17")
        self.assertEqual(expenses.parse_date("", today), "2026-11-17")
        self.assertEqual(expenses.parse_date("yesterday", today), "2026-11-16")
        self.assertEqual(expenses.parse_date("2027-01-01", today), "2027-01-01")

    def test_invalid_dates(self):
        today = date(2026, 11, 17)
        for value in ["17/11/2026", "1999-12-31", "2028-01-01", "not-a-date"]:
            with self.assertRaises(ValueError):
                expenses.parse_date(value, today)

    def test_month_helpers(self):
        self.assertEqual(expenses.normalize_month("2026-1"), "2026-01")
        self.assertEqual(expenses.previous_month("2026-01"), "2025-12")
        self.assertEqual(expenses.month_label("2026-11"), "November 2026")
        with self.assertRaises(ValueError):
            expenses.normalize_month("2026-13")


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.data = storage.default_data()

    def test_add_expense_and_income(self):
        first = expenses.add_expense(self.data, "Groceries", 42.5, "2026-11-01", "Food")
        second = expenses.add_income(self.data, "Salary", 3200, "2026-11-01")

        self.assertEqual(first["id"], "TXN-0001")
        self.assertEqual(second["id"], "TXN-0002")
        self.assertEqual(first["category"], "Food")
        self.assertEqual(second["category"], expenses.INCOME_CATEGORY)
        self.assertEqual(len(self.data["transactions"]), 2)

    def test_invalid_category_is_rejected(self):
        with self.assertRaises(ValueError):
            expenses.add_expense(self.data, "Mystery", 10, "2026-11-01", "Spaceships")

    def test_category_is_case_insensitive(self):
        record = expenses.add_expense(self.data, "Bus", 2.5, "2026-11-01", "transport")
        self.assertEqual(record["category"], "Transport")

    def test_search_matches_every_word(self):
        expenses.add_expense(self.data, "Coffee and bagel", 5.25, "2026-11-02", "Food")
        expenses.add_expense(self.data, "Bus pass", 35.00, "2026-11-03", "Transport")

        self.assertEqual(len(expenses.search_transactions(self.data, "coffee food")), 1)
        self.assertEqual(len(expenses.search_transactions(self.data, "2026-11")), 2)
        self.assertEqual(len(expenses.search_transactions(self.data, "spaceship")), 0)

    def test_filter_by_category_and_month(self):
        expenses.add_expense(self.data, "Lunch", 12, "2026-11-02", "Food")
        expenses.add_expense(self.data, "Dinner", 20, "2026-11-03", "Food")
        expenses.add_expense(self.data, "Old lunch", 15, "2026-10-02", "Food")
        expenses.add_expense(self.data, "Bus", 3, "2026-11-04", "Transport")

        november_food = expenses.filter_expenses_by_category(self.data, "Food", "2026-11")
        self.assertEqual(len(november_food), 2)

        all_food = expenses.filter_expenses_by_category(self.data, "Food", None)
        self.assertEqual(len(all_food), 3)

    def test_delete_transaction(self):
        record = expenses.add_expense(self.data, "Snack", 2, "2026-11-02", "Food")
        removed = expenses.delete_transaction(self.data, record["id"].lower())

        self.assertIsNotNone(removed)
        self.assertEqual(len(self.data["transactions"]), 0)
        self.assertIsNone(expenses.delete_transaction(self.data, "TXN-9999"))


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.data = storage.default_data()
        expenses.add_income(self.data, "Salary", 3000, "2026-11-01")
        expenses.add_expense(self.data, "Rent", 800, "2026-11-02", "Bills")
        expenses.add_expense(self.data, "Lunch", 20, "2026-11-03", "Food")
        expenses.add_expense(self.data, "Bus", 10, "2026-11-04", "Transport")
        expenses.add_expense(self.data, "Old shopping", 50, "2026-10-10", "Shopping")

    def test_totals(self):
        self.assertEqual(reports.total_income(self.data, "2026-11"), 3000.0)
        self.assertEqual(reports.total_expenses(self.data, "2026-11"), 830.0)
        self.assertEqual(reports.remaining_balance(self.data, "2026-11"), 2170.0)
        self.assertEqual(reports.total_expenses(self.data), 880.0)

    def test_category_breakdown(self):
        rows = reports.category_totals(self.data, "2026-11")
        self.assertEqual(rows[0]["category"], "Bills")
        self.assertEqual(rows[0]["amount"], 800.0)
        total_share = round(sum(row["share"] for row in rows), 1)
        self.assertAlmostEqual(total_share, 100.0, places=1)

    def test_highest_spending_category(self):
        top = reports.highest_spending_category(self.data, "2026-11")
        self.assertEqual(top["category"], "Bills")
        self.assertIsNone(reports.highest_spending_category(self.data, "2025-01"))

    def test_monthly_summary(self):
        rows = reports.monthly_summary(self.data)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["month"], "2026-11")
        self.assertEqual(rows[1]["month"], "2026-10")

    def test_insights_are_helpful(self):
        lines = reports.spending_insights(self.data, "2026-11")
        self.assertTrue(any("Top category" in line for line in lines))
        self.assertTrue(any("Largest single expense" in line for line in lines))


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.data = storage.default_data()
        self.month = expenses.current_month()

    def add_expense_today(self, amount):
        return expenses.add_expense(
            self.data, "Test expense", amount, date.today().isoformat(), "Other"
        )

    def test_set_get_remove_budget(self):
        budget.set_budget(self.data, self.month, "$500")
        self.assertEqual(budget.get_budget(self.data, self.month), 500.0)
        self.assertTrue(budget.remove_budget(self.data, self.month))
        self.assertIsNone(budget.get_budget(self.data, self.month))

    def test_status_on_track_warning_and_over(self):
        budget.set_budget(self.data, self.month, 100)
        self.add_expense_today(50)
        summary = budget.budget_summary(self.data, self.month)
        self.assertEqual(summary["status"], budget.ON_TRACK)
        self.assertEqual(summary["remaining"], 50.0)

        self.add_expense_today(40)
        summary = budget.budget_summary(self.data, self.month)
        self.assertEqual(summary["status"], budget.WARNING)

        self.add_expense_today(20)
        summary = budget.budget_summary(self.data, self.month)
        self.assertEqual(summary["status"], budget.OVER)
        self.assertEqual(summary["remaining"], -10.0)
        self.assertIn("over budget", budget.budget_message(summary).lower())

    def test_progress_bar_limits(self):
        self.assertEqual(budget.progress_bar(0, 10), "[----------]")
        self.assertEqual(budget.progress_bar(100, 10), "[##########]")
        self.assertEqual(budget.progress_bar(250, 10), "[##########]")


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp_dir.name, "data", "transactions.json")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_missing_file_is_created(self):
        with redirect_stdout(io.StringIO()):
            data = storage.load_data(self.path)
        self.assertEqual(data["transactions"], [])
        self.assertTrue(os.path.exists(self.path))

    def test_save_and_load_round_trip(self):
        data = storage.default_data()
        data["settings"]["currency"] = "€"
        record = expenses.add_expense(data, "Train ticket", 12.75, "2026-11-05", "Transport", "To campus")

        self.assertTrue(storage.save_data(data, self.path))
        loaded = storage.load_data(self.path)

        self.assertEqual(loaded["settings"]["currency"], "€")
        self.assertEqual(len(loaded["transactions"]), 1)
        self.assertEqual(loaded["transactions"][0]["id"], record["id"])
        self.assertEqual(loaded["transactions"][0]["note"], "To campus")

    def test_corrupt_file_is_quarantined(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("{ this is not json")

        with redirect_stdout(io.StringIO()):
            data = storage.load_data(self.path)

        self.assertEqual(data["transactions"], [])
        names = os.listdir(os.path.dirname(self.path))
        self.assertTrue(any(".corrupt-" in name for name in names))

    def test_backup_is_used_when_main_file_is_corrupt(self):
        first = storage.default_data()
        expenses.add_expense(first, "First record", 10, "2026-11-01", "Food")
        storage.save_data(first, self.path)

        second = storage.default_data()
        expenses.add_expense(second, "Second record", 20, "2026-11-02", "Food")
        storage.save_data(second, self.path)  # creates .bak containing first

        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("broken")

        with redirect_stdout(io.StringIO()):
            recovered = storage.load_data(self.path)

        self.assertEqual(len(recovered["transactions"]), 1)
        self.assertEqual(recovered["transactions"][0]["description"], "First record")

    def test_validator_repairs_broken_records(self):
        raw = {
            "settings": {"currency": "DOLLARS"},
            "transactions": [
                {"id": "TXN-0001", "type": "expense", "description": "Good", "amount": 5,
                 "date": "2026-11-01", "category": "food"},
                {"id": "TXN-0002", "type": "expense", "description": "Bad amount",
                 "amount": "lots", "date": "2026-11-01", "category": "Food"},
                {"type": "unknown", "description": "Bad type", "amount": 3, "date": "2026-11-01"},
            ],
            "budgets": {"2026-11": 100, "not-a-month": 50},
        }

        data, problems = storage.validate_data(raw)
        self.assertEqual(len(data["transactions"]), 1)
        self.assertEqual(data["transactions"][0]["category"], "Food")
        self.assertEqual(data["settings"]["currency"], "$")
        self.assertEqual(data["budgets"], {"2026-11": 100.0})
        self.assertGreaterEqual(len(problems), 3)

    def test_csv_export(self):
        data = storage.default_data()
        expenses.add_expense(data, "Lunch", 9.5, "2026-11-01", "Food", "Campus cafe")
        expenses.add_income(data, "Gift", 50, "2026-11-02")

        export_path = os.path.join(self.temp_dir.name, "export.csv")
        count, saved_path = storage.export_csv(data, export_path)

        self.assertEqual(count, 2)
        self.assertTrue(os.path.exists(saved_path))
        with open(saved_path, "r", encoding="utf-8") as handle:
            contents = handle.read()
        self.assertIn("id,date,type,category,description,amount,note", contents)
        self.assertIn("Lunch", contents)


class SampleDataTests(unittest.TestCase):
    def test_sample_data_is_complete(self):
        data = storage.create_sample_data()

        self.assertGreaterEqual(len(data["transactions"]), 20)
        months = {record["date"][:7] for record in data["transactions"]}
        self.assertEqual(len(months), 3)
        self.assertEqual(set(data["budgets"].keys()), months)

        for amount in data["budgets"].values():
            self.assertGreater(amount, 0)

        for record in data["transactions"]:
            self.assertIn(record["type"], (expenses.EXPENSE, expenses.INCOME))
            if record["type"] == expenses.EXPENSE:
                self.assertIn(record["category"], expenses.CATEGORIES)
            else:
                self.assertEqual(record["category"], expenses.INCOME_CATEGORY)


if __name__ == "__main__":
    unittest.main()
