"""
reports.py
==========
Calculations and terminal display for Python Smart Expense Tracker.

The first half of this module works with data only (totals, category
breakdowns, monthly summaries, insights). The second half prints that
information with plain ASCII tables so the app looks the same in any
terminal and needs no third-party libraries.
"""

import shutil
from datetime import date

import budget
import expenses


# ---------------------------------------------------------------------------
# Calculations
# ---------------------------------------------------------------------------

def records_in(data, month=None):
    """Return all transactions, optionally limited to one month."""
    records = data.get("transactions", [])
    if month is None:
        return list(records)

    month = expenses.normalize_month(month)
    return [record for record in records if str(record.get("date", ""))[:7] == month]


def total_income(data, month=None):
    total = sum(
        float(record.get("amount", 0))
        for record in records_in(data, month)
        if record.get("type") == expenses.INCOME
    )
    return round(total, 2)


def total_expenses(data, month=None):
    total = sum(
        float(record.get("amount", 0))
        for record in records_in(data, month)
        if record.get("type") == expenses.EXPENSE
    )
    return round(total, 2)


def remaining_balance(data, month=None):
    return round(total_income(data, month) - total_expenses(data, month), 2)


def average_expense(data, month=None):
    """Average size of an expense in the period (0 when there are none)."""
    amounts = [
        float(record.get("amount", 0))
        for record in records_in(data, month)
        if record.get("type") == expenses.EXPENSE
    ]
    if not amounts:
        return 0.0
    return round(sum(amounts) / len(amounts), 2)


def category_totals(data, month=None):
    """Expense totals per category, largest first.

    Returns a list of {"category", "amount", "share"} dictionaries where
    share is a percentage of total expenses in the period.
    """
    totals = {}
    for record in records_in(data, month):
        if record.get("type") != expenses.EXPENSE:
            continue
        category = str(record.get("category", "Other"))
        totals[category] = totals.get(category, 0.0) + float(record.get("amount", 0))

    overall = round(sum(totals.values()), 2)
    rows = []
    for category, amount in totals.items():
        share = (amount / overall * 100) if overall > 0 else 0.0
        rows.append({
            "category": category,
            "amount": round(amount, 2),
            "share": round(share, 1),
        })

    rows.sort(key=lambda item: (-item["amount"], item["category"]))
    return rows


def highest_spending_category(data, month=None):
    rows = category_totals(data, month)
    return rows[0] if rows else None


def top_expenses(data, month=None, limit=5):
    expenses_only = [
        record for record in records_in(data, month)
        if record.get("type") == expenses.EXPENSE
    ]
    expenses_only.sort(key=lambda record: float(record.get("amount", 0)), reverse=True)
    return expenses_only[:limit]


def monthly_summary(data):
    """Return one summary dictionary per month, newest first."""
    months = set()
    for record in data.get("transactions", []):
        months.add(str(record.get("date", ""))[:7])
    for month in data.get("budgets", {}):
        try:
            months.add(expenses.normalize_month(month))
        except ValueError:
            continue

    rows = []
    for month in sorted(months, reverse=True):
        income = total_income(data, month)
        spent = total_expenses(data, month)
        budget_amount = budget.get_budget(data, month)

        if budget_amount is None:
            status = "-"
            remaining = None
        else:
            remaining = round(budget_amount - spent, 2)
            if spent > budget_amount:
                status = "Over"
            elif spent >= budget_amount * 0.8:
                status = "Near"
            else:
                status = "On track"

        rows.append({
            "month": month,
            "label": expenses.month_label(month),
            "income": income,
            "expenses": spent,
            "net": round(income - spent, 2),
            "budget": budget_amount,
            "remaining": remaining,
            "status": status,
        })

    return rows


def spending_insights(data, month=None):
    """Return a list of short, useful observations about a month."""
    month = expenses.normalize_month(month or expenses.current_month())
    spent = total_expenses(data, month)
    label = expenses.month_label(month)
    currency = expenses.get_currency(data)

    if spent <= 0:
        return ["No expenses recorded for {} yet.".format(label)]

    insights = []

    top = highest_spending_category(data, month)
    if top is not None:
        insights.append("Top category: {} at {} ({:.0f}% of spending).".format(
            top["category"],
            expenses.format_money(top["amount"], currency),
            top["share"],
        ))

    largest = top_expenses(data, month, limit=1)
    if largest:
        record = largest[0]
        insights.append("Largest single expense: {} on {}.".format(
            record.get("description", "Unknown"),
            expenses.format_date(record.get("date", "")),
        ))

    total_days = expenses.days_in_month(month)
    today = date.today()
    this_month = today.strftime("%Y-%m")
    if month == this_month:
        elapsed = max(1, today.day)
    elif month < this_month:
        elapsed = total_days
    else:
        elapsed = 0

    if elapsed > 0:
        per_day = spent / elapsed
        insights.append("Average daily spending: {} over {} day{}.".format(
            expenses.format_money(per_day, currency), elapsed, "" if elapsed == 1 else "s"
        ))
        if month == this_month and elapsed < total_days:
            projected = spent / elapsed * total_days
            insights.append("At this pace, {} will end near {} by month end.".format(
                label, expenses.format_money(projected, currency)
            ))

    previous = expenses.previous_month(month)
    previous_spent = total_expenses(data, previous)
    if previous_spent > 0:
        change = (spent - previous_spent) / previous_spent * 100
        if abs(change) < 0.5:
            insights.append("Spending is about the same as {}.".format(
                expenses.month_label(previous)
            ))
        else:
            direction = "more" if change > 0 else "less"
            insights.append("Spending is {:.1f}% {} than {}.".format(
                abs(change), direction, expenses.month_label(previous)
            ))

    return insights


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def terminal_width(limit=110):
    """Return a comfortable output width that works when piped too."""
    columns = shutil.get_terminal_size((96, 24)).columns
    return max(64, min(columns, limit))


def print_rule(char="-", width=None):
    print(char * (width or terminal_width()))


def print_banner(title, subtitle=""):
    width = terminal_width()
    print()
    print("=" * width)
    print("  {}".format(title.upper()))
    if subtitle:
        print("  {}".format(subtitle))
    print("=" * width)


def print_section(title):
    print()
    print_rule()
    print("  {}".format(title.upper()))
    print_rule()


def print_field(label, value, width=18):
    print("  {:<{}}: {}".format(label, width, value))


def print_info(message):
    print("  [i] {}".format(message))


def print_success(message):
    print("  [OK] {}".format(message))


def print_error(message):
    print("  [!] {}".format(message))


def friendly_today():
    today = date.today()
    return "{} {}, {}".format(expenses.MONTH_NAMES[today.month - 1], today.day, today.year)


def _fit(text, width, align="<"):
    """Truncate and pad one table cell."""
    text = str(text).replace("\n", " ")
    if len(text) > width:
        if width > 3:
            text = text[:width - 3] + "..."
        else:
            text = text[:width]
    if align == ">":
        return text.rjust(width)
    if align == "^":
        return text.center(width)
    return text.ljust(width)


def print_table(headers, rows, aligns=None, max_column_width=42):
    """Print an ASCII table that adapts to the terminal width."""
    headers = [str(header).upper() for header in headers]
    columns = len(headers)
    aligns = aligns or ["<"] * columns
    text_rows = [[str(cell) for cell in row] for row in rows]

    widths = []
    for index, header in enumerate(headers):
        widest = len(header)
        for row in text_rows:
            if index < len(row):
                widest = max(widest, len(row[index]))
        widths.append(min(widest, max_column_width))

    available = terminal_width()
    while sum(widths) + 3 * columns + 1 > available:
        widest = max(widths)
        index = widths.index(widest)
        if widest <= 8:
            break
        widths[index] = widest - 1

    border = "+" + "+".join("-" * (width + 2) for width in widths) + "+"
    header_border = "+" + "+".join("=" * (width + 2) for width in widths) + "+"

    print("  " + border)
    print("  | " + " | ".join(
        _fit(headers[index], widths[index], "^") for index in range(columns)
    ) + " |")
    print("  " + header_border)

    for row in text_rows:
        cells = []
        for index in range(columns):
            value = row[index] if index < len(row) else ""
            cells.append(_fit(value, widths[index], aligns[index]))
        print("  | " + " | ".join(cells) + " |")

    print("  " + border)


def print_transactions(records, currency="$"):
    """Print a table of transactions with signed amounts."""
    if not records:
        print_info("No transactions to show.")
        return

    rows = []
    for record in records:
        sign = "-" if record.get("type") == expenses.EXPENSE else "+"
        readable_type = "Expense" if record.get("type") == expenses.EXPENSE else "Income"
        rows.append([
            record.get("id", ""),
            expenses.format_date(record.get("date", "")),
            readable_type,
            record.get("category", ""),
            record.get("description", ""),
            sign + expenses.format_money(record.get("amount", 0), currency),
        ])

    print_table(
        ["ID", "Date", "Type", "Category", "Description", "Amount"],
        rows,
        aligns=["<", "<", "<", "<", "<", ">"],
    )


def print_transaction(record, currency="$"):
    """Print one transaction as a small detail card."""
    kind = "Expense" if record.get("type") == expenses.EXPENSE else "Income"
    sign = "-" if record.get("type") == expenses.EXPENSE else "+"

    print()
    print("  {}  |  {}  |  {}".format(record.get("id", ""), kind, record.get("category", "")))
    print("  {}".format(record.get("description", "")))
    print_field("Amount", sign + expenses.format_money(record.get("amount", 0), currency))
    print_field("Date", expenses.format_date(record.get("date", "")))
    if record.get("note"):
        print_field("Note", record["note"])


def print_totals(data, month=None, heading=None):
    """Print income, expenses and balance for a period."""
    currency = expenses.get_currency(data)
    if heading:
        print("  {}".format(heading))
    print_field("Total income", expenses.format_money(total_income(data, month), currency))
    print_field("Total expenses", expenses.format_money(total_expenses(data, month), currency))
    print_field("Balance", expenses.format_money(remaining_balance(data, month), currency))


def print_category_table(data, month=None):
    """Print the category breakdown with a small bar for each row."""
    currency = expenses.get_currency(data)
    rows = category_totals(data, month)

    if not rows:
        print_info("No expenses in this period.")
        return

    table_rows = []
    for item in rows:
        table_rows.append([
            item["category"],
            expenses.format_money(item["amount"], currency),
            "{:.1f}%".format(item["share"]),
            budget.progress_bar(item["share"], width=18),
        ])

    print_table(
        ["Category", "Amount", "Share", "Spending"],
        table_rows,
        aligns=["<", ">", ">", "<"],
        max_column_width=26,
    )


def print_month_report(data, month):
    """Print the full monthly summary: totals, budget, categories, insights."""
    currency = expenses.get_currency(data)
    summary = budget.budget_summary(data, month)
    records = expenses.transactions_in_month(data, month)

    print_banner(summary["label"], "Monthly summary")

    if not records and summary["budget"] is None:
        print_info("There is no activity or budget for {}.".format(summary["label"]))
        return

    print_field("Transactions", len(records))
    print_field("Income", expenses.format_money(summary["income"], currency))
    print_field("Expenses", expenses.format_money(summary["spent"], currency))
    print_field(
        "Net balance",
        expenses.format_money(summary["income"] - summary["spent"], currency),
    )

    print()
    print("  BUDGET")
    if summary["budget"] is None:
        print_info("No budget set. Choose option 8 from the main menu to add one.")
    else:
        print_field("Monthly budget", expenses.format_money(summary["budget"], currency))
        bar = budget.progress_bar(summary["percent_used"])
        print("  {:<18}: {} {:.1f}% used".format(
            "Budget used", bar, summary["percent_used"]
        ))
        print_field("Remaining", expenses.format_money(summary["remaining"], currency))
        print_field("Status", budget.status_label(summary))
        print("  {}".format(budget.budget_message(summary, currency)))

    print()
    print("  SPENDING BY CATEGORY")
    print_category_table(data, month)

    print()
    print("  INSIGHTS")
    for line in spending_insights(data, month):
        print("    - {}".format(line))


def print_budget_status(data, month):
    """Print just the budget section for one month."""
    currency = expenses.get_currency(data)
    summary = budget.budget_summary(data, month)

    print_banner("Budget - {}".format(summary["label"]))
    print_field("Income", expenses.format_money(summary["income"], currency))
    print_field("Expenses", expenses.format_money(summary["spent"], currency))

    if summary["budget"] is None:
        print()
        print_info("No budget is set for {}.".format(summary["label"]))
        print_info("Use option 1 in this menu to create one.")
        return

    print_field("Budget", expenses.format_money(summary["budget"], currency))
    print_field("Remaining", expenses.format_money(summary["remaining"], currency))
    print_field("Status", budget.status_label(summary))
    print("  {:<18}: {} {:.1f}% used".format(
        "Progress", budget.progress_bar(summary["percent_used"]), summary["percent_used"]
    ))

    if summary["daily_allowance"] is not None:
        print_field("Safe per day", "{} for {} days".format(
            expenses.format_money(summary["daily_allowance"], currency),
            summary["days_left"],
        ))
    if summary["projected"] is not None:
        print_field("Projected total", expenses.format_money(summary["projected"], currency))

    print()
    print("  {}".format(budget.budget_message(summary, currency)))


def print_budget_alert(data, month=None):
    """Show a warning after spending, but only near/over the budget."""
    summary = budget.budget_summary(data, month or expenses.current_month())
    if summary["budget"] is None:
        return
    if summary["status"] not in (budget.WARNING, budget.OVER):
        return

    currency = expenses.get_currency(data)
    print()
    print_rule("!")
    print("  BUDGET ALERT - {}".format(budget.status_label(summary)))
    print("  {}".format(budget.budget_message(summary, currency)))
    print("  {} spent of {}.".format(
        expenses.format_money(summary["spent"], currency),
        expenses.format_money(summary["budget"], currency),
    ))
    print_rule("!")


def print_dashboard(data):
    """Print the overall report used by the Reports menu."""
    currency = expenses.get_currency(data)
    records = data.get("transactions", [])

    print_banner("Reports & Totals", "A snapshot of your money habits")

    if not records:
        print_info("There are no transactions yet. Add one to see reports.")
        return

    expense_count = sum(
        1 for record in records if record.get("type") == expenses.EXPENSE
    )
    income_count = len(records) - expense_count

    print_field("Transactions", "{} ({} expenses, {} income)".format(
        len(records), expense_count, income_count
    ))
    print_totals(data, heading=None)

    print()
    print("  ALL-TIME CATEGORIES")
    print_category_table(data)

    overall_top = highest_spending_category(data)
    if overall_top is not None:
        print()
        print_field("Top category", "{} ({})".format(
            overall_top["category"],
            expenses.format_money(overall_top["amount"], currency),
        ))
    print_field("Average expense", expenses.format_money(average_expense(data), currency))

    print()
    print("  TOP 5 LARGEST EXPENSES")
    top = top_expenses(data, limit=5)
    if top:
        print_transactions(top, currency)
    else:
        print_info("No expenses recorded.")

    print()
    print("  MONTHLY OVERVIEW")
    rows = []
    for item in monthly_summary(data):
        rows.append([
            item["label"],
            expenses.format_money(item["income"], currency),
            expenses.format_money(item["expenses"], currency),
            expenses.format_money(item["net"], currency),
            expenses.format_money(item["budget"], currency) if item["budget"] is not None else "-",
            item["status"],
        ])
    print_table(
        ["Month", "Income", "Expenses", "Net", "Budget", "Status"],
        rows,
        aligns=["<", ">", ">", ">", ">", "<"],
        max_column_width=24,
    )

    current = expenses.current_month()
    print()
    print("  THIS MONTH ({})".format(expenses.month_label(current)))
    print_field("Expenses", expenses.format_money(total_expenses(data, current), currency))
    print_field("Balance", expenses.format_money(remaining_balance(data, current), currency))
    summary = budget.budget_summary(data, current)
    if summary["budget"] is None:
        print_info("No budget set for this month.")
    else:
        print_field("Budget status", "{} ({} left)".format(
            budget.status_label(summary),
            expenses.format_money(summary["remaining"], currency),
        ))

    print()
    print("  INSIGHTS")
    for line in spending_insights(data, current):
        print("    - {}".format(line))
