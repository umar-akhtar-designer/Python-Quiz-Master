"""
storage.py
==========
JSON storage for Python Smart Expense Tracker.

Responsibilities:
  * load and save data/transactions.json
  * repair or recover damaged files safely
  * create realistic sample data
  * export transactions to CSV

The file layout is:

    {
      "version": 1,
      "settings": {"currency": "$", "created_at": "..."},
      "transactions": [ {...}, {...} ],
      "budgets": {"2026-11": 1000.0}
    }

Only the Python standard library is used.
"""

import csv
import json
import math
import os
import re
import shutil
from datetime import date, datetime

import expenses

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DATA_FILE = os.path.join(DATA_DIR, "transactions.json")
EXPORT_DIR = os.path.join(BASE_DIR, "exports")
SCHEMA_VERSION = 1


def display_path(path=DATA_FILE):
    """Return a short path for messages, relative to the project folder."""
    try:
        return os.path.relpath(path, BASE_DIR)
    except ValueError:
        return path


def default_data():
    """Return a brand new, empty data dictionary."""
    return {
        "version": SCHEMA_VERSION,
        "settings": {
            "currency": "$",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
        "transactions": [],
        "budgets": {},
    }


# ---------------------------------------------------------------------------
# Validation and repair
# ---------------------------------------------------------------------------

def _clean_transaction(item):
    """Validate one stored record.

    Returns (record, problem). A problem means the record was skipped.
    """
    if not isinstance(item, dict):
        return None, "record is not a JSON object"

    txn_type = str(item.get("type", "")).strip().lower()
    if txn_type not in (expenses.EXPENSE, expenses.INCOME):
        return None, "unknown transaction type"

    description = expenses.clean_text(item.get("description"), max_length=80)
    if not description:
        return None, "missing description"

    try:
        amount = expenses.parse_amount(item.get("amount"))
    except ValueError:
        return None, "invalid amount"

    date_text = str(item.get("date", "")).strip()
    try:
        parsed_date = datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError:
        return None, "invalid date"
    if parsed_date.year < expenses.MIN_DATE_YEAR:
        return None, "date is too old"

    if txn_type == expenses.EXPENSE:
        try:
            category = expenses.resolve_category(item.get("category"))
        except ValueError:
            category = "Other"
    else:
        category = expenses.INCOME_CATEGORY

    note = expenses.clean_text(item.get("note"), max_length=120)

    record_id = str(item.get("id", "")).strip().upper()
    if re.fullmatch(r"TXN-\d{1,6}", record_id) is None:
        record_id = ""  # assigned a fresh ID below

    created_at = str(item.get("created_at", "")).strip()

    record = {
        "id": record_id,
        "type": txn_type,
        "description": description,
        "amount": amount,
        "date": parsed_date.strftime("%Y-%m-%d"),
        "category": category,
        "note": note,
        "created_at": created_at,
    }
    return record, ""


def _assign_missing_ids(records):
    """Give a unique TXN-#### ID to records that need one."""
    used = set()
    highest = 0
    for record in records:
        record_id = record.get("id", "")
        if record_id:
            used.add(record_id)
            match = re.fullmatch(r"TXN-(\d+)", record_id)
            if match is not None:
                highest = max(highest, int(match.group(1)))

    counter = highest
    for record in records:
        if record.get("id"):
            continue
        counter += 1
        candidate = "TXN-{:04d}".format(counter)
        while candidate in used:
            counter += 1
            candidate = "TXN-{:04d}".format(counter)
        record["id"] = candidate
        used.add(candidate)


def validate_data(raw):
    """Return (clean_data, problems).

    Works on any value loaded from JSON and never raises. Repairable values
    are fixed; hopeless records are skipped and described in `problems`.
    """
    problems = []
    data = default_data()

    if not isinstance(raw, dict):
        return data, ["The data file was not a JSON object."]

    settings = raw.get("settings")
    if isinstance(settings, dict):
        currency = settings.get("currency")
        if isinstance(currency, str) and 0 < len(currency.strip()) <= 3:
            data["settings"]["currency"] = currency.strip()
        else:
            problems.append("Currency setting was invalid; using $.")
        created_at = settings.get("created_at")
        if isinstance(created_at, str) and created_at.strip():
            data["settings"]["created_at"] = created_at.strip()
    else:
        problems.append("Settings were missing; defaults were used.")

    raw_transactions = raw.get("transactions")
    if not isinstance(raw_transactions, list):
        problems.append("The transactions list was invalid and was reset.")
        raw_transactions = []

    cleaned = []
    seen_ids = set()
    for index, item in enumerate(raw_transactions, start=1):
        record, problem = _clean_transaction(item)
        if record is None:
            problems.append("Skipped record #{}: {}.".format(index, problem))
            continue
        if record["id"] and record["id"] in seen_ids:
            problems.append("Record #{} had a duplicate ID; a new one was assigned.".format(index))
            record["id"] = ""
        if record["id"]:
            seen_ids.add(record["id"])
        cleaned.append(record)

    _assign_missing_ids(cleaned)
    data["transactions"] = cleaned

    raw_budgets = raw.get("budgets")
    budgets = {}
    if isinstance(raw_budgets, dict):
        for month_text, value in raw_budgets.items():
            try:
                month = expenses.normalize_month(month_text)
                amount = expenses.parse_amount(value)
            except ValueError:
                problems.append("Skipped invalid budget for {!r}.".format(month_text))
                continue
            budgets[month] = amount
    elif raw_budgets is not None:
        problems.append("Budget list was invalid and was reset.")

    data["budgets"] = budgets
    data["version"] = SCHEMA_VERSION
    return data, problems


# ---------------------------------------------------------------------------
# Loading and saving
# ---------------------------------------------------------------------------

def _read_json(path):
    """Read a JSON file. Returns (value, error_message)."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle), None
    except FileNotFoundError:
        return None, "file not found"
    except json.JSONDecodeError as error:
        return None, "invalid JSON on line {}: {}".format(error.lineno, error.msg)
    except UnicodeDecodeError:
        return None, "the file is not valid UTF-8 text"
    except OSError as error:
        return None, str(error)


def _recover(path, reason):
    """Move a bad data file aside and try to restore the .bak copy."""
    print("  [!] The data file could not be read: {}".format(reason))

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    damaged_path = "{}.corrupt-{}.json".format(path, stamp)
    try:
        os.replace(path, damaged_path)
        print("  [i] The damaged file was kept as {}.".format(os.path.basename(damaged_path)))
    except OSError as error:
        print("  [!] Could not move the damaged file: {}".format(error))

    backup_path = path + ".bak"
    if os.path.exists(backup_path):
        raw, backup_error = _read_json(backup_path)
        if backup_error is None:
            recovered, _ = validate_data(raw)
            save_data(recovered, path)
            print("  [OK] Recovered your most recent backup.")
            return recovered
        print("  [!] The backup could not be read either: {}".format(backup_error))

    fresh = default_data()
    save_data(fresh, path)
    print("  [i] Started a new empty data file. Check the damaged copy if needed.")
    return fresh


def load_data(path=DATA_FILE):
    """Load the data file, creating or repairing it when necessary."""
    directory = os.path.dirname(os.path.abspath(path))
    try:
        os.makedirs(directory, exist_ok=True)
    except OSError as error:
        print("  [!] Could not create the data folder: {}".format(error))
        return default_data()

    if not os.path.exists(path):
        print("  [i] No saved data found. A new data file will be created.")
        data = default_data()
        save_data(data, path)
        return data

    raw, error = _read_json(path)
    if error is not None:
        return _recover(path, error)

    data, problems = validate_data(raw)
    if problems:
        print("  [!] Your data file needed a little repair:")
        for problem in problems[:6]:
            print("      - {}".format(problem))
        if len(problems) > 6:
            print("      - ... and {} more.".format(len(problems) - 6))
        save_data(data, path)
        print("  [OK] Repairs were saved.")

    return data


def save_data(data, path=DATA_FILE):
    """Save data safely. Returns True on success.

    Steps:
      1. clean the data
      2. copy the current good file to transactions.json.bak
      3. write a temporary file
      4. atomically replace the real file
    """
    clean, _ = validate_data(data)
    directory = os.path.dirname(os.path.abspath(path))

    try:
        os.makedirs(directory, exist_ok=True)
    except OSError as error:
        print("  [!] Could not create the data folder: {}".format(error))
        return False

    if os.path.exists(path):
        raw, error = _read_json(path)
        if error is None and isinstance(raw, dict):
            try:
                shutil.copyfile(path, path + ".bak")
            except OSError:
                pass  # a missing backup should never block a save

    temp_path = path + ".tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(clean, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(temp_path, path)
        return True
    except OSError as error:
        print("  [!] Could not save data: {}".format(error))
        try:
            os.remove(temp_path)
        except OSError:
            pass
        return False


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

def default_export_path():
    """Return exports/transactions-YYYY-MM-DD.csv."""
    filename = "transactions-{}.csv".format(date.today().isoformat())
    return os.path.join(EXPORT_DIR, filename)


def export_csv(data, path):
    """Write transactions to a CSV file. Returns (row_count, full_path)."""
    full_path = os.path.expanduser(str(path).strip())
    if not os.path.isabs(full_path):
        full_path = os.path.join(BASE_DIR, full_path)

    directory = os.path.dirname(full_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    records = expenses.sort_transactions(data.get("transactions", []), newest_first=False)

    with open(full_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "date", "type", "category", "description", "amount", "note"])
        for record in records:
            writer.writerow([
                record.get("id", ""),
                record.get("date", ""),
                record.get("type", ""),
                record.get("category", ""),
                record.get("description", ""),
                "{:.2f}".format(float(record.get("amount", 0))),
                record.get("note", ""),
            ])

    return len(records), full_path


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

# (months_back, day, description, amount, category, note)
SAMPLE_EXPENSES = [
    (0, 1, "Rent share", 620.00, "Bills", "Apartment rent"),
    (0, 3, "Groceries", 64.30, "Food", "Weekly shop"),
    (0, 4, "Bus pass", 35.00, "Transport", "Monthly top-up"),
    (0, 6, "Coffee and bagel", 5.25, "Food", ""),
    (0, 8, "Mobile phone bill", 28.00, "Bills", ""),
    (0, 10, "Python textbook", 42.99, "Education", "Used copy"),
    (0, 12, "Dinner with friends", 26.40, "Food", ""),
    (0, 14, "Hoodie", 45.00, "Shopping", "Sale price"),
    (0, 16, "Groceries", 51.20, "Food", "Fruit and vegetables"),
    (0, 17, "Study snacks", 7.80, "Food", ""),
    (1, 1, "Rent share", 620.00, "Bills", "Apartment rent"),
    (1, 2, "Internet bill", 39.99, "Bills", ""),
    (1, 5, "Groceries", 58.60, "Food", ""),
    (1, 7, "Bus pass", 35.00, "Transport", "Monthly top-up"),
    (1, 9, "Data structures book", 55.00, "Education", ""),
    (1, 11, "Lunch with classmates", 18.40, "Food", ""),
    (1, 13, "Streaming subscription", 12.99, "Other", ""),
    (1, 15, "Conference fee", 60.00, "Education", "Student rate"),
    (1, 18, "Groceries", 61.10, "Food", ""),
    (1, 20, "Dinner out", 32.75, "Food", ""),
    (1, 22, "Mobile phone bill", 28.00, "Bills", ""),
    (1, 24, "Running shoes", 64.50, "Shopping", "End of season sale"),
    (1, 26, "Concert ticket", 45.00, "Other", ""),
    (1, 28, "Coffee", 6.75, "Food", ""),
    (2, 1, "Rent share", 620.00, "Bills", "Apartment rent"),
    (2, 3, "Groceries", 49.85, "Food", ""),
    (2, 6, "Metro card", 30.00, "Transport", ""),
    (2, 9, "Online course", 24.99, "Education", "Python practice"),
    (2, 12, "Electricity bill", 47.30, "Bills", "Shared apartment"),
    (2, 15, "Groceries", 58.60, "Food", ""),
    (2, 18, "Mobile phone bill", 28.00, "Bills", ""),
    (2, 21, "Haircut", 25.00, "Other", ""),
    (2, 26, "Study snacks", 15.25, "Food", ""),
    (2, 28, "Winter jacket", 89.00, "Shopping", ""),
    (2, 28, "Internet bill", 39.99, "Bills", ""),
]

# (months_back, day, description, amount, note)
SAMPLE_INCOME = [
    (0, 1, "Monthly salary", 3200.00, "Part-time internship"),
    (0, 17, "Freelance design job", 180.00, "Small logo project"),
    (1, 1, "Monthly salary", 3200.00, "Part-time internship"),
    (1, 15, "Freelance writing", 150.00, ""),
    (2, 1, "Monthly salary", 3200.00, "Part-time internship"),
    (2, 24, "Birthday gift", 100.00, ""),
]


def _date_in_month(today, months_back, day):
    """Return a YYYY-MM-DD date that is `months_back` months before today."""
    year = today.year
    month = today.month - months_back
    while month <= 0:
        month += 12
        year -= 1

    last_day = expenses.days_in_month("{:04d}-{:02d}".format(year, month))
    safe_day = max(1, min(day, last_day))
    return "{:04d}-{:02d}-{:02d}".format(year, month, safe_day)


def create_sample_data():
    """Return a complete data dictionary filled with realistic demo records."""
    data = default_data()
    today = date.today()

    for months_back, day, description, amount, category, note in SAMPLE_EXPENSES:
        if months_back == 0 and day > today.day:
            continue  # do not create spending in the future
        date_text = _date_in_month(today, months_back, day)
        expenses.add_expense(
            data, description, amount, date_text, category, note,
            created_at="{} 12:00:00".format(date_text),
        )

    for months_back, day, description, amount, note in SAMPLE_INCOME:
        if months_back == 0 and day > today.day:
            continue
        date_text = _date_in_month(today, months_back, day)
        expenses.add_income(
            data, description, amount, date_text, note,
            created_at="{} 09:00:00".format(date_text),
        )

    # Give each month a sensible budget with a little breathing room.
    months = sorted({record["date"][:7] for record in data["transactions"]})
    multipliers = [1.25, 1.12, 1.08]
    for index, month in enumerate(months):
        spent = 0.0
        for record in data["transactions"]:
            if record["type"] == expenses.EXPENSE and record["date"][:7] == month:
                spent += record["amount"]
        multiplier = multipliers[index] if index < len(multipliers) else 1.10
        if spent > 0:
            data["budgets"][month] = float(math.ceil(spent * multiplier / 10.0) * 10)

    return data
