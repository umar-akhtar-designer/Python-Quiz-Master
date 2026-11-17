"""
main.py
=======
Command-line interface for Python Smart Expense Tracker.

Run it with:

    python3 main.py

Useful flags:

    python3 main.py --sample    load three months of demo data
    python3 main.py --help      show usage
"""

import os
import sys
from datetime import date

import budget
import expenses
import reports
import storage


class InputCancelled(Exception):
    """Raised when the user leaves a required answer blank."""


MENU_ITEMS = [
    ("1", "Add an expense"),
    ("2", "Add income"),
    ("3", "View all transactions"),
    ("4", "Search transactions"),
    ("5", "Filter expenses by category"),
    ("6", "Monthly summary"),
    ("7", "Reports and totals"),
    ("8", "Budget manager"),
    ("9", "Delete a transaction"),
    ("10", "Export transactions to CSV"),
    ("0", "Save and exit"),
]


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------

def ask_raw(prompt, default=None):
    """Ask for text. A blank answer uses the default when there is one."""
    suffix = " [{}]".format(default) if default is not None else ""
    answer = input("  {}{}: ".format(prompt, suffix)).strip()
    if answer == "" and default is not None:
        return str(default)
    return answer


def ask_text(prompt, hint=None, default=None, allow_blank=False, max_length=80):
    """Ask for cleaned text, or cancel when a required answer is blank."""
    label = prompt
    if hint:
        label = "{} {}".format(prompt, hint)

    value = ask_raw(label, default)
    if value == "" and not allow_blank:
        raise InputCancelled
    return expenses.clean_text(value, max_length=max_length)


def ask_amount(prompt, currency):
    """Ask for an amount until it passes validation."""
    while True:
        raw = ask_raw("{} ({})".format(prompt, currency))
        if raw == "":
            raise InputCancelled
        try:
            return expenses.parse_amount(raw)
        except ValueError as error:
            reports.print_error(str(error))


def ask_date(prompt="Date"):
    """Ask for a date, defaulting to today."""
    default = date.today().isoformat()
    while True:
        raw = ask_raw("{} (YYYY-MM-DD or 'yesterday')".format(prompt), default)
        try:
            return expenses.parse_date(raw)
        except ValueError as error:
            reports.print_error(str(error))


def ask_month(prompt="Month", allow_all=False):
    """Ask for a month. Returns None when 'all' is allowed and chosen."""
    current = expenses.current_month()
    hint = "YYYY-MM or 'last'"
    if allow_all:
        hint = "YYYY-MM, 'last', or blank for all time"

    while True:
        raw = ask_raw("{} ({})".format(prompt, hint), None if allow_all else current)
        if raw == "":
            return None if allow_all else current

        lowered = raw.lower()
        if allow_all and lowered in ("all", "a", "*"):
            return None
        if lowered in ("last", "previous", "prev"):
            return expenses.previous_month()

        try:
            return expenses.normalize_month(raw)
        except ValueError as error:
            reports.print_error(str(error))


def confirm(prompt, default=True):
    """Ask a yes/no question and return True or False."""
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        answer = input("  {} {}: ".format(prompt, suffix)).strip().lower()
        if answer == "":
            return default
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        reports.print_error("Please answer 'y' or 'n'.")


def choose_category():
    """Show the category list and return the chosen category."""
    print()
    print("  Categories:")
    for index, category in enumerate(expenses.CATEGORIES, start=1):
        print("    {}. {}".format(index, category))

    while True:
        raw = ask_raw("Category (1-{}, blank to cancel)".format(len(expenses.CATEGORIES)))
        if raw == "":
            raise InputCancelled

        if raw.isdigit():
            number = int(raw)
            if 1 <= number <= len(expenses.CATEGORIES):
                return expenses.CATEGORIES[number - 1]

        for category in expenses.CATEGORIES:
            if category.lower() == raw.lower():
                return category

        reports.print_error("Choose a number from 1 to {}, or type a category name.".format(
            len(expenses.CATEGORIES)
        ))


def save_changes(data):
    """Write data to disk, or explain that it could not be saved."""
    if not storage.save_data(data):
        reports.print_error("Could not write the data file. Changes are only in memory.")


# ---------------------------------------------------------------------------
# Menu actions
# ---------------------------------------------------------------------------

def handle_add_expense(data):
    currency = expenses.get_currency(data)
    reports.print_section("Add an expense")

    description = ask_text("Description", hint="(blank to cancel)")
    amount = ask_amount("Amount", currency)
    category = choose_category()
    txn_date = ask_date("Date")
    note = ask_text("Note", hint="(optional)", allow_blank=True, max_length=120)

    print()
    print("  Please check the details:")
    print("    Description : {}".format(description))
    print("    Amount      : {}".format(expenses.format_money(amount, currency)))
    print("    Category    : {}".format(category))
    print("    Date        : {}".format(expenses.format_date(txn_date)))
    if note:
        print("    Note        : {}".format(note))

    if not confirm("Save this expense?"):
        reports.print_info("Not saved.")
        return

    record = expenses.add_expense(data, description, amount, txn_date, category, note)
    save_changes(data)
    reports.print_success("Expense {} saved.".format(record["id"]))
    reports.print_budget_alert(data, record["date"][:7])


def handle_add_income(data):
    currency = expenses.get_currency(data)
    reports.print_section("Add income")

    description = ask_text("Source", hint="(for example: salary, gift)")
    amount = ask_amount("Amount", currency)
    txn_date = ask_date("Date")
    note = ask_text("Note", hint="(optional)", allow_blank=True, max_length=120)

    print()
    print("  Please check the details:")
    print("    Source : {}".format(description))
    print("    Amount : {}".format(expenses.format_money(amount, currency)))
    print("    Date   : {}".format(expenses.format_date(txn_date)))
    if note:
        print("    Note   : {}".format(note))

    if not confirm("Save this income?"):
        reports.print_info("Not saved.")
        return

    record = expenses.add_income(data, description, amount, txn_date, note)
    save_changes(data)
    reports.print_success("Income {} saved.".format(record["id"]))


def handle_view_transactions(data):
    reports.print_section("All transactions")
    currency = expenses.get_currency(data)
    records = expenses.sort_transactions(data.get("transactions", []))

    if not records:
        reports.print_info("There are no transactions yet.")
        reports.print_info("Use option 1 to add an expense or option 2 to add income.")
        return

    limit = 30
    reports.print_transactions(records[:limit], currency)

    if len(records) > limit:
        print()
        reports.print_info("Showing the {} most recent of {} transactions.".format(
            limit, len(records)
        ))
        reports.print_info("Use option 4 (search) to find older records.")

    print()
    reports.print_totals(data, heading="ALL-TIME TOTALS")


def handle_search(data):
    reports.print_section("Search transactions")
    currency = expenses.get_currency(data)

    query = ask_text("Search", hint="(text, category, date or ID; blank to cancel)")
    results = expenses.search_transactions(data, query)

    print()
    if not results:
        reports.print_info('No matches for "{}".'.format(query))
        reports.print_info("Try a shorter word, a category like Food, or a date like 2026-11.")
        return

    reports.print_transactions(results, currency)
    print()
    reports.print_info("{} match{} found.".format(
        len(results), "" if len(results) == 1 else "es"
    ))


def handle_filter(data):
    reports.print_section("Filter expenses by category")
    currency = expenses.get_currency(data)

    category = choose_category()
    month = ask_month("Month", allow_all=True)
    results = expenses.filter_expenses_by_category(data, category, month)
    period = expenses.month_label(month) if month else "all time"

    print()
    reports.print_info("{} expenses in {} ({} found)".format(category, period, len(results)))
    reports.print_transactions(results, currency)

    total = round(sum(float(record.get("amount", 0)) for record in results), 2)
    period_total = reports.total_expenses(data, month)
    share = (total / period_total * 100) if period_total > 0 else 0.0

    print()
    reports.print_field("Total spent", expenses.format_money(total, currency))
    reports.print_field("Share of expenses", "{:.1f}%".format(share))


def handle_month_summary(data):
    reports.print_section("Monthly summary")
    month = ask_month("Month")
    reports.print_month_report(data, month)


def handle_reports(data):
    reports.print_dashboard(data)


def handle_budget_manager(data):
    currency = expenses.get_currency(data)

    while True:
        reports.print_section("Budget manager")
        print("   1. Set or update a monthly budget")
        print("   2. View budget status")
        print("   3. Remove a monthly budget")
        print("   0. Back to the main menu")
        reports.print_rule()

        choice = ask_raw("Choose an option")
        if choice == "":
            continue

        try:
            if choice == "0":
                return

            if choice == "1":
                month = ask_month("Budget month")
                existing = budget.get_budget(data, month)
                if existing is not None:
                    reports.print_info("Current budget for {}: {}".format(
                        expenses.month_label(month),
                        expenses.format_money(existing, currency),
                    ))
                amount = ask_amount("Budget for {}".format(expenses.month_label(month)), currency)
                budget.set_budget(data, month, amount)
                save_changes(data)

                print()
                reports.print_success("Budget for {} set to {}.".format(
                    expenses.month_label(month),
                    expenses.format_money(amount, currency),
                ))
                summary = budget.budget_summary(data, month)
                reports.print_field(
                    "Spent so far",
                    expenses.format_money(summary["spent"], currency),
                )
                reports.print_field(
                    "Remaining",
                    expenses.format_money(summary["remaining"], currency),
                )
                reports.print_field("Status", budget.status_label(summary))
                print("  {}".format(budget.budget_message(summary, currency)))

            elif choice == "2":
                month = ask_month("Budget month")
                reports.print_budget_status(data, month)

            elif choice == "3":
                month = ask_month("Budget month")
                if budget.get_budget(data, month) is None:
                    reports.print_info("There is no budget set for {}.".format(
                        expenses.month_label(month)
                    ))
                elif confirm(
                    "Remove the budget for {}?".format(expenses.month_label(month)),
                    False,
                ):
                    budget.remove_budget(data, month)
                    save_changes(data)
                    reports.print_success("Budget removed.")
                else:
                    reports.print_info("Nothing was removed.")

            else:
                reports.print_error("Choose 1, 2, 3 or 0.")

        except InputCancelled:
            reports.print_info("Cancelled.")


def handle_delete(data):
    reports.print_section("Delete a transaction")
    currency = expenses.get_currency(data)
    records = expenses.sort_transactions(data.get("transactions", []))

    if not records:
        reports.print_info("There are no transactions to delete.")
        return

    reports.print_transactions(records[:10], currency)
    print()
    reports.print_info("The 10 most recent transactions are shown above.")

    raw = ask_raw("Transaction ID (blank to cancel)")
    if raw == "":
        raise InputCancelled

    record = expenses.get_transaction(data, raw)
    if record is None:
        matches = expenses.search_transactions(data, raw)
        if len(matches) == 1:
            record = matches[0]
        elif len(matches) > 1:
            reports.print_error(
                "That text matches {} transactions. Use the exact ID.".format(len(matches))
            )
            reports.print_transactions(matches[:10], currency)
            return
        else:
            reports.print_error("No transaction found for '{}'.".format(raw))
            return

    reports.print_transaction(record, currency)
    print()

    if not confirm("Delete this transaction permanently?", default=False):
        reports.print_info("Nothing was deleted.")
        return

    expenses.delete_transaction(data, record["id"])
    save_changes(data)
    reports.print_success("Deleted {}.".format(record["id"]))


def handle_export(data):
    reports.print_section("Export transactions to CSV")
    records = data.get("transactions", [])
    if not records:
        reports.print_info("There are no transactions to export.")
        return

    default_path = storage.display_path(storage.default_export_path())
    target = ask_raw("File path", default_path)

    resolved = os.path.expanduser(target)
    if not os.path.isabs(resolved):
        resolved = os.path.join(storage.BASE_DIR, resolved)

    if os.path.exists(resolved) and not confirm("That file already exists. Overwrite it?", False):
        reports.print_info("Export cancelled.")
        return

    try:
        count, full_path = storage.export_csv(data, target)
    except OSError as error:
        reports.print_error("Could not export the file: {}".format(error))
        return

    reports.print_success("Exported {} transactions to {}.".format(
        count, storage.display_path(full_path)
    ))


# ---------------------------------------------------------------------------
# Screens and the main loop
# ---------------------------------------------------------------------------

def show_welcome(data):
    reports.print_banner(
        "Python Smart Expense Tracker",
        "Track spending. Build better habits.",
    )

    currency = expenses.get_currency(data)
    current = expenses.current_month()

    reports.print_field("Today", reports.friendly_today(), width=24)
    reports.print_field("Data file", storage.display_path(), width=24)
    reports.print_field("Transactions", str(len(data.get("transactions", []))), width=24)

    if not data.get("transactions"):
        print()
        reports.print_info("No transactions yet. Start with option 1 or 2.")
        reports.print_info("Tip: python3 main.py --sample loads three months of demo data.")
        return

    income = reports.total_income(data, current)
    spent = reports.total_expenses(data, current)

    print()
    reports.print_field("{} income".format(expenses.month_label(current)),
                        expenses.format_money(income, currency), width=24)
    reports.print_field("{} expenses".format(expenses.month_label(current)),
                        expenses.format_money(spent, currency), width=24)
    reports.print_field("{} balance".format(expenses.month_label(current)),
                        expenses.format_money(income - spent, currency), width=24)

    summary = budget.budget_summary(data, current)
    if summary["budget"] is not None:
        reports.print_field("Budget used", "{} of {} ({:.0f}%)".format(
            expenses.format_money(summary["spent"], currency),
            expenses.format_money(summary["budget"], currency),
            summary["percent_used"],
        ), width=24)


def show_menu():
    reports.print_section("Main menu")
    for number, label in MENU_ITEMS:
        print("   {:>2}. {}".format(number, label))
    reports.print_rule()


def finish(data):
    print()
    if storage.save_data(data):
        reports.print_success("Data saved to {}.".format(storage.display_path()))
    else:
        reports.print_error("There was a problem saving your data.")

    reports.print_banner(
        "Goodbye",
        "{} transactions are stored safely.".format(len(data.get("transactions", []))),
    )


def run(data):
    show_welcome(data)

    while True:
        show_menu()
        choice = ask_raw("Choose an option")

        if choice == "":
            continue

        if choice in ("0", "q", "quit", "exit"):
            finish(data)
            return

        try:
            if choice == "1":
                handle_add_expense(data)
            elif choice == "2":
                handle_add_income(data)
            elif choice == "3":
                handle_view_transactions(data)
            elif choice == "4":
                handle_search(data)
            elif choice == "5":
                handle_filter(data)
            elif choice == "6":
                handle_month_summary(data)
            elif choice == "7":
                handle_reports(data)
            elif choice == "8":
                handle_budget_manager(data)
            elif choice == "9":
                handle_delete(data)
            elif choice == "10":
                handle_export(data)
            else:
                reports.print_error(
                    "Unknown option '{}'. Choose a number from the menu.".format(choice)
                )

        except InputCancelled:
            reports.print_info("Cancelled - nothing was saved.")

        except EOFError:
            raise  # handled at the bottom of the file

        except Exception as error:
            if os.environ.get("SMART_TRACKER_DEBUG"):
                raise
            reports.print_error("Unexpected problem: {}".format(error))
            reports.print_info("Your saved data is safe. Please try the option again.")


def print_usage():
    print()
    print("  Python Smart Expense Tracker")
    print("  ----------------------------")
    print("  Usage:")
    print("    python3 main.py            start the tracker")
    print("    python3 main.py --sample   replace data with fresh sample data")
    print("    python3 main.py --help     show this message")
    print("    python3 main.py --version  show the version")
    print()


def main(argv=None):
    arguments = sys.argv[1:] if argv is None else list(argv)

    if "--help" in arguments or "-h" in arguments:
        print_usage()
        return 0

    if "--version" in arguments:
        print("Python Smart Expense Tracker 1.0.0")
        return 0

    known = {"--sample"}
    unknown = [item for item in arguments if item not in known]
    if unknown:
        print("  Unknown option: {}".format(" ".join(unknown)))
        print_usage()
        return 1

    if "--sample" in arguments:
        data = storage.create_sample_data()
        if not storage.save_data(data):
            print("  [!] Could not write the sample data file.")
            return 1
        print()
        print("  [OK] Sample data created in {}.".format(storage.display_path()))
        print("  [i] {} transactions across {} months.".format(
            len(data["transactions"]),
            len({record["date"][:7] for record in data["transactions"]}),
        ))
        print("  [i] Any previous file was kept as transactions.json.bak.")
        print("  [i] Start the app with: python3 main.py")
        print()
        return 0

    data = storage.load_data()
    run(data)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, EOFError):
        print("\n\n  Goodbye! Your data is saved.")
