"""Local SQLite-backed personal finance tracker."""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterator


class ValidationError(ValueError):
    """Raised when a transaction field is invalid."""


@dataclass(frozen=True)
class Transaction:
    id: int
    kind: str
    amount: Decimal
    category: str
    description: str
    transaction_date: str


def validate_date(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Date must be a valid ISO date (YYYY-MM-DD).") from exc
    if parsed.isoformat() != value:
        raise ValidationError("Date must use YYYY-MM-DD format.")
    return value


def validate_month(value: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}", value):
        raise ValidationError("Month must use YYYY-MM format.")
    try:
        date.fromisoformat(value + "-01")
    except ValueError as exc:
        raise ValidationError("Month must be a valid calendar month.") from exc
    return value


def parse_amount(value: str | Decimal) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError("Amount must be a positive number with at most two decimals.") from exc
    if not amount.is_finite() or amount <= 0 or amount.as_tuple().exponent < -2:
        raise ValidationError("Amount must be a positive number with at most two decimals.")
    return amount.quantize(Decimal("0.01"))


class FinanceTracker:
    def __init__(self, database: str | Path = "finance.db") -> None:
        self.database = str(database)
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY,
                    kind TEXT NOT NULL CHECK (kind IN ('income', 'expense')),
                    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
                    category TEXT NOT NULL,
                    description TEXT NOT NULL,
                    transaction_date TEXT NOT NULL
                )"""
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def add(
        self, kind: str, amount: str | Decimal, category: str, description: str,
        transaction_date: str | None = None,
    ) -> int:
        kind = kind.strip().lower()
        if kind not in {"income", "expense"}:
            raise ValidationError("Type must be income or expense.")
        value = parse_amount(amount)
        category, description = category.strip(), description.strip()
        if not category:
            raise ValidationError("Category cannot be empty.")
        if not description:
            raise ValidationError("Description cannot be empty.")
        day = validate_date(transaction_date or date.today().isoformat())
        cents = int(value * 100)
        with self._connect() as connection:
            cursor = connection.execute(
                """INSERT INTO transactions
                   (kind, amount_cents, category, description, transaction_date)
                   VALUES (?, ?, ?, ?, ?)""",
                (kind, cents, category, description, day),
            )
            return int(cursor.lastrowid)

    def list_transactions(self, month: str | None = None) -> list[Transaction]:
        query = (
            "SELECT id, kind, amount_cents, category, description, transaction_date "
            "FROM transactions"
        )
        parameters: tuple[str, ...] = ()
        if month is not None:
            month = validate_month(month)
            query += " WHERE substr(transaction_date, 1, 7) = ?"
            parameters = (month,)
        query += " ORDER BY transaction_date, id"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [
            Transaction(row[0], row[1], Decimal(row[2]) / 100, row[3], row[4], row[5])
            for row in rows
        ]

    def report(self, month: str) -> dict[str, object]:
        month = validate_month(month)
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT kind, category, SUM(amount_cents)
                   FROM transactions WHERE substr(transaction_date, 1, 7) = ?
                   GROUP BY kind, category ORDER BY kind, category""",
                (month,),
            ).fetchall()
        income = sum(row[2] for row in rows if row[0] == "income")
        expenses = sum(row[2] for row in rows if row[0] == "expense")
        by_category: dict[str, dict[str, Decimal]] = {}
        for kind, category, cents in rows:
            by_category.setdefault(category, {"income": Decimal("0.00"), "expense": Decimal("0.00")})
            by_category[category][kind] += Decimal(cents) / 100
        return {
            "month": month,
            "income": Decimal(income) / 100,
            "expenses": Decimal(expenses) / 100,
            "balance": Decimal(income - expenses) / 100,
            "categories": by_category,
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="finance.db", help="SQLite database path (default: finance.db)")
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add", help="Record income or an expense")
    add.add_argument("--type", choices=("income", "expense"), required=True)
    add.add_argument("--amount", required=True)
    add.add_argument("--category", required=True)
    add.add_argument("--description", required=True)
    add.add_argument("--date", dest="transaction_date")
    listing = commands.add_parser("list", help="List transactions")
    listing.add_argument("--month")
    report = commands.add_parser("report", help="Summarize a month")
    report.add_argument("--month", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    tracker = FinanceTracker(args.db)
    try:
        if args.command == "add":
            transaction_id = tracker.add(
                args.type, args.amount, args.category, args.description, args.transaction_date
            )
            print(f"Recorded transaction #{transaction_id}.")
        elif args.command == "list":
            transactions = tracker.list_transactions(args.month)
            if not transactions:
                print("No transactions found.")
            for item in transactions:
                print(
                    f"{item.transaction_date} | {item.kind:7} | ${item.amount:.2f} | "
                    f"{item.category} | {item.description}"
                )
        else:
            report = tracker.report(args.month)
            print(f"Monthly report: {report['month']}")
            print(f"Income:   ${report['income']:.2f}")
            print(f"Expenses: ${report['expenses']:.2f}")
            print(f"Balance:  ${report['balance']:.2f}")
            print("Category totals:")
            categories = report["categories"]
            if not categories:
                print("  No activity.")
            for category, totals in categories.items():
                print(
                    f"  {category}: income ${totals['income']:.2f}, "
                    f"expenses ${totals['expense']:.2f}"
                )
    except (ValidationError, OSError, sqlite3.Error) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
