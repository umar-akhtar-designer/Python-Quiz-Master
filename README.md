# Python Smart Expense Tracker

A beginner-friendly, menu-driven personal finance tracker built with the
Python standard library. Add expenses and income, organise spending by
category, set monthly budgets, and read clear reports - all from the terminal,
with your data saved safely between sessions.

This project was created as a personal final project while taking
**Stanford Code in Place**. It is not affiliated with, approved by, or
endorsed by Stanford University.

---

## Why this project

Most beginner finance scripts stop at "add a number, print a total". This one
tries to behave like a small real application:

- records are validated before they are saved
- data survives restarts, and a damaged file cannot silently wipe your history
- budgets are month-aware and give useful warnings
- reports explain *where* the money went, not just how much was spent
- every module has one clear job, so the code stays readable

---

## Features

**Transactions**
- Add an expense with description, amount, date, category and optional note
- Add income with a source, amount, date and optional note
- View all transactions in a clean table (most recent first)
- Search by description, category, date, ID, note or amount
- Filter expenses by category, for one month or all time
- Delete a transaction by ID, with a confirmation prompt

**Budgets**
- Set a monthly budget for any month
- See how much is spent, how much remains, and the percentage used
- "Safe to spend per day" and a projected month-end total
- Warnings at 80% of the budget and when the budget is exceeded
- Remove a budget for a month

**Reports**
- All-time income, expenses and balance
- Monthly income, expenses, net balance and budget status
- Spending by category with relative bars
- Highest spending category
- Top five largest expenses
- Automatic insights: average daily spend, largest expense, change versus
  the previous month, and a month-end projection

**Data and reliability**
- JSON storage in `data/transactions.json`
- Atomic saves (write a temporary file, then replace)
- Automatic `.bak` backup of the previous good file
- Corrupted files are moved aside (never deleted) and the backup is restored
  when possible
- Loaded records are validated and repaired; bad records are skipped with a
  clear message
- CSV export for spreadsheets
- Built-in sample data with three months of realistic transactions

**User experience**
- Clear numbered menus and consistent section headers
- Friendly validation messages instead of tracebacks
- Confirmation before saving or deleting
- Blank input cancels an action where it makes sense
- `Ctrl+C` / `Ctrl+D` exits cleanly
- No colours or Unicode box characters, so the interface works in any
  terminal, including Windows `cmd` and Replit

---

## Screenshots

Screenshots make a project page much easier to read. Suggested shots:

| File name | What to capture |
| --- | --- |
| `docs/screenshots/main-menu.png` | The welcome banner and main menu |
| `docs/screenshots/add-expense.png` | A completed expense confirmation |
| `docs/screenshots/monthly-summary.png` | Monthly totals, budget bar and insights |
| `docs/screenshots/reports.png` | Category table and monthly overview |
| `docs/screenshots/budget-warning.png` | The over-budget alert |

How to take them:

1. Make the terminal window roughly 90-100 columns wide.
2. Run `python3 main.py --sample` to load the demo data.
3. Use your operating system's screenshot tool, or a terminal recorder such
   as [asciinema](https://asciinema.org/) if you prefer a text recording.
4. Save the images in `docs/screenshots/` and add them below this section:

```markdown
![Main menu](docs/screenshots/main-menu.png)
```

`docs/screenshots/README.md` repeats these instructions so the folder is not
empty in the repository.

---

## Project structure

```
smart-expense-tracker/
    main.py                 # menus, input helpers and program flow
    expenses.py             # transaction rules, validation and formatting
    reports.py              # totals, insights and table rendering
    budget.py               # monthly budget logic and warnings
    storage.py              # JSON loading, saving, recovery, sample data, CSV
    data/
        transactions.json   # sample data included; your live data lives here
    tests/
        __init__.py
        test_tracker.py     # 26 standard-library unit tests
    docs/
        screenshots/
            README.md       # guidance for adding screenshots
    README.md
    requirements.txt
    .gitignore
    LICENSE
```

---

## Requirements

- Python 3.8 or newer
- No third-party packages

Check your version:

```bash
python3 --version
```

On Windows, use `python` instead of `python3` if that is how Python is
installed on your machine.

---

## Installation

```bash
git clone https://github.com/YOUR-USERNAME/smart-expense-tracker.git
cd smart-expense-tracker
```

That is all. There is nothing to install. If you want to follow the usual
Python convention anyway:

```bash
python3 -m pip install -r requirements.txt
```

The file only contains comments explaining that no dependencies are needed.

---

## Running the application

```bash
python3 main.py
```

On first run, if `data/transactions.json` is missing, the app creates it and
starts with an empty tracker.

### Load the demo data

The repository ships with sample data. To regenerate three months of fresh
demo records relative to today's date:

```bash
python3 main.py --sample
```

The previous data file is preserved as `data/transactions.json.bak`.

### Other flags

```bash
python3 main.py --help
python3 main.py --version
```

---

## Usage examples

### 1. Add an expense

Choose option `1` and follow the prompts. Invalid input is rejected and the
question is asked again:

```
  Description (blank to cancel): Coffee and bagel
  Amount ($): 5.25
  Categories:
    1. Food
    2. Transport
    3. Education
    4. Shopping
    5. Bills
    6. Other
  Category (1-6): 1
  Date (YYYY-MM-DD or 'yesterday') [2026-11-17]:
  Note (optional):

  Please check the details:
    Description : Coffee and bagel
    Amount      : $5.25
    Category    : Food
    Date        : November 17, 2026

  Save this expense? [Y/n]:
  [OK] Expense TXN-0042 saved.
```

After saving, the app checks the current month's budget and shows an alert if
spending is near or over the limit.

### 2. Monthly summary

Option `6`, then press Enter for the current month or type `2026-10`:

```
================================================================================
  OCTOBER 2026
  Monthly summary
================================================================================
  Transactions      : 16
  Income            : $3,350.00
  Expenses          : $1,138.08
  Net balance       : $2,211.92

  BUDGET
  Monthly budget    : $1,280.00
  Budget used       : [#####################---] 88.9% used
  Remaining         : $141.92
  Status            : Near limit
  88.9% of your budget is used - only $141.92 left in October 2026.

  SPENDING BY CATEGORY
  +-----------+---------+-------+----------------------+
  |  CATEGORY |  AMOUNT | SHARE |       SPENDING       |
  +===========+=========+=======+======================+
  | Bills     | $687.99 | 60.5% | [###########-------] |
  | Food      | $177.60 | 15.6% | [###---------------] |
  | Education | $115.00 | 10.1% | [##----------------] |
  | ...       |         |       |                      |
  +-----------+---------+-------+----------------------+
```

### 3. Set a budget

Option `8` -> `1`, choose the month, then enter the amount. The app
immediately shows spent, remaining and status. Option `8` -> `2` shows the
safe daily allowance and a month-end projection.

### 4. Search

Option `4`, then type one or more words. Every word must match somewhere in
the record:

```
  Search (text, category, date or ID; blank to cancel): coffee food
```

Search also understands category names (`Bills`), months (`2026-11`) and IDs
(`TXN-0004`).

### 5. Export

Option `10`. Press Enter to accept
`exports/transactions-YYYY-MM-DD.csv`, or type another path. The CSV opens in
Excel, Numbers, Google Sheets or LibreOffice.

---

## Data format

`data/transactions.json` is human-readable:

```json
{
  "version": 1,
  "settings": {
    "currency": "$",
    "created_at": "2026-11-17 09:00:00"
  },
  "transactions": [
    {
      "id": "TXN-0001",
      "type": "expense",
      "description": "Groceries",
      "amount": 64.3,
      "date": "2026-11-03",
      "category": "Food",
      "note": "Weekly shop",
      "created_at": "2026-11-03 12:00:00"
    }
  ],
  "budgets": {
    "2026-11": 1010.0
  }
}
```

Rules enforced when loading:

- `type` must be `expense` or `income`
- `amount` must be a positive number
- `date` must be `YYYY-MM-DD`, year 2000 or later
- expense categories are `Food`, `Transport`, `Education`, `Shopping`,
  `Bills`, `Other`; income uses `Income`
- budget keys are `YYYY-MM`

If a record is beyond repair it is skipped, the reason is printed, and the
rest of the file is kept. Nothing is silently discarded without a message.

### Backup and recovery

Every save copies the previous good file to `data/transactions.json.bak`
before replacing it. If the main file becomes unreadable, the app:

1. moves it to `data/transactions.json.corrupt-YYYYMMDD-HHMMSS.json`
2. tries to load the `.bak` file
3. starts empty only if both copies are unusable

---

## How the modules fit together

| Module | Responsibility | Depends on |
| --- | --- | --- |
| `main.py` | Menus, prompts, actions, program loop | all other modules |
| `expenses.py` | Validation, transaction creation, search, formatting | standard library only |
| `budget.py` | Budget storage view, monthly status, warnings | `expenses.py` |
| `reports.py` | Totals, categories, insights, tables | `expenses.py`, `budget.py` |
| `storage.py` | JSON load/save, repair, sample data, CSV | `expenses.py` |

The dependency graph has no cycles. Display helpers live in `reports.py`;
storage never prints menus and the domain modules never call `input()`.

---

## Python concepts demonstrated

| Concept | Where to look |
| --- | --- |
| Variables and data types | `expenses.py` constants, transaction dictionaries |
| Functions and parameters | every module; small single-purpose helpers |
| Return values | `parse_amount`, `budget_summary`, `create_sample_data` |
| `if` / `elif` / `else` | menu dispatch in `main.py`, status checks in `budget.py` |
| `while` loops | input validation and the main menu loop |
| `for` loops | totals, filtering, table rendering |
| Lists | `CATEGORIES`, `transactions`, table rows |
| Dictionaries | each transaction, `budgets`, report summaries |
| String formatting | money, dates, percentages, aligned tables |
| File handling | `storage.load_data`, `storage.save_data`, CSV export |
| JSON | `json.load`, `json.dump`, schema repair |
| Exception handling | `ValueError` validation, `OSError`, `JSONDecodeError`, `KeyboardInterrupt` |
| Modules and imports | five cooperating files, no circular imports |

---

## Testing

Run the automated tests from the project folder:

```bash
python3 -m unittest discover -s tests -v
```

Expected result:

```
Ran 26 tests in 0.02s

OK
```

The suite covers amount and date validation, transaction creation, search,
filtering, totals, category reports, budget thresholds, JSON round trips,
corrupt-file recovery from backup, CSV export, and sample data integrity.

Tests use temporary folders, so your real data is never modified.

Manual checks worth trying:

- enter `abc` as an amount, then a valid amount
- enter category `9`
- enter date `2026-13-01`
- set a budget below what you have already spent
- delete a transaction and confirm with `y`
- copy `data/transactions.json`, break the copy on purpose, and reload

---

## Troubleshooting

**`python3: command not found`**
Use `python` on Windows, or install Python from python.org and make sure
"Add Python to PATH" is ticked.

**`Permission denied` when saving**
The project folder is not writable. Move the project to your home folder, or
fix the folder permissions. The app keeps your changes in memory and tells you
when a save fails.

**My data file was reset**
Look in `data/` for `transactions.json.corrupt-*.json` (the damaged original)
and `transactions.json.bak` (the previous good copy). Copy the `.bak` file over
`transactions.json` and restart.

**The table wraps awkwardly**
Use a terminal at least 80 columns wide. Tables shrink automatically but very
narrow windows cannot fit six columns.

**I want to start over**
Run `python3 main.py --sample` for demo data, or delete
`data/transactions.json`; the app recreates an empty file on the next run.

---

## Publishing to GitHub

From inside the `smart-expense-tracker` folder:

```bash
git init
git add .
git commit -m "Add Python Smart Expense Tracker final project"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/smart-expense-tracker.git
git push -u origin main
```

Before pushing:

- replace `YOUR-USERNAME` in this README and in the clone command
- put your name in `LICENSE` if it is different from the current copyright line
- add screenshots to `docs/screenshots/` and reference them in the README
- check that `git status` does not include venvs, `__pycache__`, exports or
  `*.bak` files (`.gitignore` already covers these)
- never commit real financial data; the included data is fictional

If you do not have a repository yet, create an empty one on GitHub first, then
run the commands above.

---

## Ideas for future versions

- Recurring transactions for rent and subscriptions
- Multiple budgets per category
- Edit an existing transaction instead of delete-and-re-add
- Savings goals
- A simple chart library or web front end
- Currency conversion
- Password protection for the data file

These are deliberately left out to keep the core beginner-friendly.

---

## License

MIT License. See [LICENSE](LICENSE).

---

## Disclaimer

This is an educational project, not financial advice. The sample data is
fictional. Python Smart Expense Tracker is an independent project and is not
affiliated with, approved by, or endorsed by Stanford University or the
Stanford Code in Place team.
