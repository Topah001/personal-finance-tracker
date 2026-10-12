# Personal Finance Tracker

A Python 3.13 command-line app for recording income and expenses in a local SQLite database and reviewing monthly totals.

## Requirements

- Python 3.13 (standard library only)

## Run

```powershell
python finance_tracker.py add --type income --amount 2500.00 --category Salary --description "October pay" --date 2026-10-01
python finance_tracker.py add --type expense --amount 42.50 --category Groceries --description "Market"
python finance_tracker.py report --month 2026-10
python finance_tracker.py list --month 2026-10
```

The database defaults to `finance.db` in the current directory. Supply `--db path\to\file.db` before a command to use another file. Dates default to today; month reports use `YYYY-MM`. Amounts must be positive and are stored as exact cents.

## Tests

```powershell
python -m unittest discover -s tests -v
```

Data stays local; the database is excluded from version control.
