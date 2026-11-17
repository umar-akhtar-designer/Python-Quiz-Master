"""
expenses.py
===========
Transaction logic for Python Smart Expense Tracker.

This module owns the "business rules" for transactions:
  * what a valid amount / date / category looks like
  * how to create, find, filter and delete transactions
  * how to format money and dates for the screen

It does not read files (that is storage.py) and it does not print menus
(that is main.py), which keeps each module small and easy to test.

Only the Python standard library is used.
"""

import calendar
import math
import re
from datetime import date, datetime, timedelta

# ---------------------------------------------------------------------------
# Constants shared by the whole project
# ---------------------------------------------------------------------------

EXPENSE = "expense"
INCOME = "income"

# The six categories requested in the project brief.
CATEGORIES = ["Food", "Transport", "Education", "Shopping", "Bills", "Other"]
INCOME_CATEGORY = "Income"

MAX_AMOUNT = 1_000_000
MIN_DATE_YEAR = 2000
MAX_FUTURE_DAYS = 365  # allow planned expenses up to one year ahead

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def clean_text(value, max_length=80):
    """Trim a value and collapse repeated spaces into one.

    Returns "" for None. Long text is cut to max_length characters so a
    single record cannot take over the whole screen.
    """
    if value is None:
        return ""
    text = " ".join(str(value).split())
    if max_length is not None and len(text) > max_length:
        text = text[:max_length].rstrip()
    return text


def get_currency(data):
    """Return the currency symbol stored in data["settings"], or "$"."""
    settings = data.get("settings", {}) if isinstance(data, dict) else {}
    if not isinstance(settings, dict):
        return "$"
    currency = settings.get("currency", "$")
    if not isinstance(currency, str):
        return "$"
    currency = currency.strip()
    if not currency or len(currency) > 3:
        return "$"
    return currency


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def parse_amount(raw):
    """Turn user text such as "$1,200.50" into a positive float.

    Raises ValueError with a friendly message when the text is not a
    sensible amount. Rounding happens here so totals stay tidy.
    """
    if raw is None:
        raise ValueError("Please enter an amount.")

    text = str(raw).strip()
    for symbol in ("$", "£", "€", ","):
        text = text.replace(symbol, "")
    text = text.strip()

    if text == "":
        raise ValueError("Please enter an amount, like 12.50.")

    try:
        amount = float(text)
    except ValueError:
        raise ValueError("Amount must be a number, like 12.50.")

    if not math.isfinite(amount):
        raise ValueError("Amount must be a normal number.")

    if amount <= 0:
        raise ValueError("Amount must be greater than zero.")

    if amount > MAX_AMOUNT:
        raise ValueError("Amount must be {:,.0f} or less.".format(MAX_AMOUNT))

    amount = round(amount, 2)
    if amount <= 0:
        raise ValueError("Amount must be at least 0.01.")

    return amount


def parse_date(raw, today=None):
    """Validate a date and return it as a "YYYY-MM-DD" string.

    Accepts:
      * blank, "today" or "now"  -> today
      * "yesterday"              -> yesterday
      * "YYYY-MM-DD"             -> that date

    Raises ValueError for bad input or dates outside the allowed range.
    """
    today = today or date.today()

    if raw is None:
        text = ""
    else:
        text = str(raw).strip().lower()

    if text in ("", "today", "now"):
        chosen = today
    elif text in ("yesterday", "yday"):
        chosen = today - timedelta(days=1)
    else:
        try:
            chosen = datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError(
                "Date must look like YYYY-MM-DD (for example 2026-11-17), "
                "or be 'today' or 'yesterday'."
            )

    if chosen.year < MIN_DATE_YEAR:
        raise ValueError("Date must be in the year {} or later.".format(MIN_DATE_YEAR))

    latest = today + timedelta(days=MAX_FUTURE_DAYS)
    if chosen > latest:
        raise ValueError("Date is too far in the future (maximum one year ahead).")

    return chosen.isoformat()


def resolve_category(raw):
    """Return the official spelling of a category (case-insensitive)."""
    text = clean_text(raw)
    for category in CATEGORIES:
        if category.lower() == text.lower():
            return category
    raise ValueError("Category must be one of: {}.".format(", ".join(CATEGORIES)))


def normalize_month(raw):
    """Validate a month such as "2026-11" and return it zero-padded."""
    text = str(raw).strip()
    match = re.fullmatch(r"(\d{4})-(\d{1,2})", text)
    if match is None:
        raise ValueError("Month must look like YYYY-MM (for example 2026-11).")

    year = int(match.group(1))
    month_number = int(match.group(2))

    if not 1 <= month_number <= 12:
        raise ValueError("Month number must be between 01 and 12.")
    if not 2000 <= year <= 2100:
        raise ValueError("Month year must be between 2000 and 2100.")

    return "{:04d}-{:02d}".format(year, month_number)


def split_month(month):
    """Return (year, month_number) for a "YYYY-MM" string."""
    normalized = normalize_month(month)
    year_text, month_text = normalized.split("-")
    return int(year_text), int(month_text)


# ---------------------------------------------------------------------------
# Month helpers
# ---------------------------------------------------------------------------

def current_month():
    """Return the current month as "YYYY-MM"."""
    return date.today().strftime("%Y-%m")


def previous_month(month=None):
    """Return the month before the given month (default: this month)."""
    year, month_number = split_month(month or current_month())
    if month_number == 1:
        return "{:04d}-12".format(year - 1)
    return "{:04d}-{:02d}".format(year, month_number - 1)


def month_label(month):
    """Return a friendly label such as "November 2026"."""
    year, month_number = split_month(month)
    return "{} {}".format(MONTH_NAMES[month_number - 1], year)


def days_in_month(month):
    """Return the number of days in a "YYYY-MM" month."""
    year, month_number = split_month(month)
    return calendar.monthrange(year, month_number)[1]


# ---------------------------------------------------------------------------
# Formatting for the terminal
# ---------------------------------------------------------------------------

def format_money(amount, currency="$"):
    """Format a number as money, for example -$12.50."""
    try:
        value = round(float(amount), 2)
    except (TypeError, ValueError):
        value = 0.0
    sign = "-" if value < 0 else ""
    return "{}{}{:,.2f}".format(sign, currency, abs(value))


def format_percent(value, digits=1):
    """Format a number as a percentage, for example 82.5%."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    return "{:.{}f}%".format(number, digits)


def format_date(value):
    """Turn "2026-11-17" into "November 17, 2026" when possible."""
    try:
        parsed = datetime.strptime(str(value), "%Y-%m-%d")
    except (TypeError, ValueError):
        return str(value)
    return "{} {}, {}".format(MONTH_NAMES[parsed.month - 1], parsed.day, parsed.year)


# ---------------------------------------------------------------------------
# Creating transactions
# ---------------------------------------------------------------------------

def next_transaction_id(transactions):
    """Return the next unused ID, for example TXN-0007."""
    highest = 0
    for record in transactions:
        if not isinstance(record, dict):
            continue
        match = re.fullmatch(r"TXN-(\d+)", str(record.get("id", "")).strip().upper())
        if match is not None:
            highest = max(highest, int(match.group(1)))
    return "TXN-{:04d}".format(highest + 1)


def add_transaction(data, txn_type, description, amount, txn_date=None,
                    category=None, note="", created_at=None):
    """Validate and append a transaction to data["transactions"].

    Returns the new record (a dictionary). Raises ValueError for bad data.
    """
    if txn_type not in (EXPENSE, INCOME):
        raise ValueError("Transaction type must be 'expense' or 'income'.")

    description = clean_text(description)
    if not description:
        raise ValueError("Description cannot be empty.")

    amount = parse_amount(amount)
    date_text = parse_date(txn_date)

    if txn_type == EXPENSE:
        if category is None:
            raise ValueError("An expense needs a category.")
        category = resolve_category(category)
    else:
        category = INCOME_CATEGORY

    note = clean_text(note, max_length=120)

    if not isinstance(data.get("transactions"), list):
        data["transactions"] = []
    transactions = data["transactions"]

    if created_at is None:
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    else:
        created_at = str(created_at).strip() or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    record = {
        "id": next_transaction_id(transactions),
        "type": txn_type,
        "description": description,
        "amount": amount,
        "date": date_text,
        "category": category,
        "note": note,
        "created_at": created_at,
    }

    transactions.append(record)
    return record


def add_expense(data, description, amount, txn_date=None, category="Other",
                note="", created_at=None):
    """Add an expense and return the saved record."""
    return add_transaction(
        data, EXPENSE, description, amount, txn_date, category, note, created_at
    )


def add_income(data, description, amount, txn_date=None, note="", created_at=None):
    """Add income and return the saved record."""
    return add_transaction(
        data, INCOME, description, amount, txn_date, None, note, created_at
    )


# ---------------------------------------------------------------------------
# Reading, searching and deleting transactions
# ---------------------------------------------------------------------------

def get_transaction(data, transaction_id):
    """Find a transaction by ID (case-insensitive). Returns None if missing."""
    target = clean_text(transaction_id).upper()
    if not target:
        return None
    for record in data.get("transactions", []):
        if str(record.get("id", "")).upper() == target:
            return record
    return None


def delete_transaction(data, transaction_id):
    """Remove a transaction by ID. Returns the removed record or None."""
    target = clean_text(transaction_id).upper()
    transactions = data.get("transactions", [])
    for index, record in enumerate(transactions):
        if str(record.get("id", "")).upper() == target:
            return transactions.pop(index)
    return None


def sort_transactions(records, newest_first=True):
    """Return a new list sorted by date (and then by creation time)."""
    def sort_key(record):
        return (
            str(record.get("date", "")),
            str(record.get("created_at", "")),
            str(record.get("id", "")),
        )

    return sorted(records, key=sort_key, reverse=newest_first)


def transactions_in_month(data, month):
    """Return every transaction (income and expenses) in a month."""
    normalized = normalize_month(month)
    matching = []
    for record in data.get("transactions", []):
        if str(record.get("date", ""))[:7] == normalized:
            matching.append(record)
    return sort_transactions(matching)


def search_transactions(data, query):
    """Search description, category, date, note, ID, type and amount.

    Every word in the query must appear somewhere in the record.
    """
    words = clean_text(query).lower().split()
    if not words:
        return []

    results = []
    for record in data.get("transactions", []):
        haystack = " ".join([
            str(record.get("id", "")),
            str(record.get("description", "")),
            str(record.get("category", "")),
            str(record.get("date", "")),
            str(record.get("note", "")),
            str(record.get("type", "")),
            "{:.2f}".format(float(record.get("amount", 0))),
            format_money(record.get("amount", 0)),
        ]).lower()

        if all(word in haystack for word in words):
            results.append(record)

    return sort_transactions(results)


def filter_expenses_by_category(data, category, month=None):
    """Return expenses in one category, optionally limited to one month."""
    category_text = clean_text(category).lower()
    month_text = normalize_month(month) if month else None

    matching = []
    for record in data.get("transactions", []):
        if record.get("type") != EXPENSE:
            continue
        if str(record.get("category", "")).lower() != category_text:
            continue
        if month_text and str(record.get("date", ""))[:7] != month_text:
            continue
        matching.append(record)

    return sort_transactions(matching)
