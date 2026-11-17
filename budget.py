"""
budget.py
=========
Monthly budget rules for Python Smart Expense Tracker.

A budget is stored in data["budgets"] as { "2026-11": 1000.0 }.
Only the Python standard library is used.
"""

from datetime import date

import expenses


# Status values used by the rest of the program.
NO_BUDGET = "no_budget"
ON_TRACK = "on_track"
WARNING = "warning"
OVER = "over"

# At 80% of the budget the user gets a gentle "near limit" warning.
WARNING_PERCENT = 80.0


def set_budget(data, month, amount):
    """Set or update the budget for a month. Returns the saved amount."""
    month = expenses.normalize_month(month)
    value = expenses.parse_amount(amount)

    if not isinstance(data.get("budgets"), dict):
        data["budgets"] = {}
    data["budgets"][month] = value
    return value


def get_budget(data, month):
    """Return the budget for a month, or None when no budget is set."""
    month = expenses.normalize_month(month)
    budgets = data.get("budgets", {})
    if not isinstance(budgets, dict):
        return None

    value = budgets.get(month)
    if value is None:
        return None
    try:
        value = round(float(value), 2)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def remove_budget(data, month):
    """Remove a month's budget. Returns True if something was removed."""
    month = expenses.normalize_month(month)
    budgets = data.get("budgets", {})
    if isinstance(budgets, dict) and month in budgets:
        del budgets[month]
        return True
    return False


def month_expenses(data, month):
    """Total expenses recorded in a month, rounded to cents."""
    month = expenses.normalize_month(month)
    total = 0.0
    for record in data.get("transactions", []):
        if record.get("type") != expenses.EXPENSE:
            continue
        if str(record.get("date", ""))[:7] == month:
            total += float(record.get("amount", 0))
    return round(total, 2)


def month_income(data, month):
    """Total income recorded in a month, rounded to cents."""
    month = expenses.normalize_month(month)
    total = 0.0
    for record in data.get("transactions", []):
        if record.get("type") != expenses.INCOME:
            continue
        if str(record.get("date", ""))[:7] == month:
            total += float(record.get("amount", 0))
    return round(total, 2)


def budget_summary(data, month=None):
    """Build a dictionary describing a month's budget situation.

    Keys: month, label, budget, spent, income, remaining, percent_used,
    status, total_days, days_elapsed, days_left, daily_allowance, projected.
    """
    month = expenses.normalize_month(month or expenses.current_month())
    today = date.today()
    this_month = today.strftime("%Y-%m")

    budget_amount = get_budget(data, month)
    spent = month_expenses(data, month)
    income = month_income(data, month)
    total_days = expenses.days_in_month(month)

    if month == this_month:
        days_elapsed = today.day
        days_left = total_days - today.day
    elif month < this_month:
        days_elapsed = total_days
        days_left = 0
    else:
        days_elapsed = 0
        days_left = total_days

    summary = {
        "month": month,
        "label": expenses.month_label(month),
        "budget": budget_amount,
        "spent": spent,
        "income": income,
        "remaining": None,
        "percent_used": None,
        "status": NO_BUDGET,
        "total_days": total_days,
        "days_elapsed": days_elapsed,
        "days_left": days_left,
        "daily_allowance": None,
        "projected": None,
    }

    if budget_amount is not None:
        remaining = round(budget_amount - spent, 2)
        percent = (spent / budget_amount) * 100

        summary["remaining"] = remaining
        summary["percent_used"] = percent

        if spent > budget_amount:
            summary["status"] = OVER
        elif percent >= WARNING_PERCENT:
            summary["status"] = WARNING
        else:
            summary["status"] = ON_TRACK

        if month == this_month and days_left > 0 and remaining > 0:
            summary["daily_allowance"] = round(remaining / days_left, 2)

        if month == this_month and days_elapsed > 0:
            summary["projected"] = round(spent / days_elapsed * total_days, 2)

    return summary


def status_label(summary):
    """Return a short human-readable label for a budget summary."""
    labels = {
        NO_BUDGET: "No budget",
        ON_TRACK: "On track",
        WARNING: "Near limit",
        OVER: "OVER BUDGET",
    }
    return labels.get(summary.get("status"), "Unknown")


def budget_message(summary, currency="$"):
    """Write one helpful sentence about the budget."""
    if summary.get("budget") is None:
        return "No budget set for {}. Use the budget manager to add one.".format(
            summary.get("label", "this month")
        )

    remaining = summary.get("remaining", 0)
    percent = summary.get("percent_used", 0)
    label = summary.get("label", "this month")

    if summary.get("status") == OVER:
        return "You are over budget by {}. Consider slowing down for the rest of {}.".format(
            expenses.format_money(-remaining, currency), label
        )

    if summary.get("status") == WARNING:
        return "{} of your budget is used - only {} left in {}.".format(
            expenses.format_percent(percent),
            expenses.format_money(remaining, currency),
            label,
        )

    return "{} left ({} of the budget unused). Nice work.".format(
        expenses.format_money(remaining, currency),
        expenses.format_percent(100 - percent),
    )


def progress_bar(percent, width=24):
    """Return an ASCII progress bar such as [#######---------]."""
    try:
        percent = float(percent)
    except (TypeError, ValueError):
        percent = 0.0

    percent = max(0.0, min(percent, 100.0))
    filled = int(round(percent / 100.0 * width))
    return "[" + "#" * filled + "-" * (width - filled) + "]"
