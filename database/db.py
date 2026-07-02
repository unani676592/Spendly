"""SQLite helpers for Spendly.

Public helpers:
    get_db()   — request-scoped connection (cached on flask.g), FK enforcement on
    close_db() — teardown handler that closes the request connection
    init_db()  — create all tables (idempotent)
    seed_db()  — insert sample development data (idempotent)
"""

import os
import sqlite3

from flask import g
from werkzeug.security import generate_password_hash

# spendly.db lives at the project root (see .gitignore).
DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "spendly.db",
)


def _connect():
    """Build a configured raw connection shared by request and standalone use."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # SQLite leaves foreign keys off by default — enable per connection.
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    """Return the request-scoped connection, opening one if needed."""
    if "db" not in g:
        g.db = _connect()
    return g.db


def close_db(e=None):
    """Close the request-scoped connection; registered as a teardown handler."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create all tables if they do not already exist."""
    conn = _connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                email         TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at    TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                amount      REAL NOT NULL,
                category    TEXT NOT NULL,
                description TEXT,
                date        TEXT NOT NULL,
                created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def seed_db():
    """Insert sample development data. Returns early if users already exist."""
    conn = _connect()
    try:
        # If any users exist, the database is already seeded — do nothing.
        if conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]:
            return

        conn.execute(
            """
            INSERT INTO users (name, email, password_hash)
            VALUES (?, ?, ?)
            """,
            ("Demo User", "demo@spendly.com", generate_password_hash("demo123")),
        )
        user_id = conn.execute(
            "SELECT id FROM users WHERE email = ?",
            ("demo@spendly.com",),
        ).fetchone()["id"]

        # 8 expenses covering every category (dates in the current month).
        sample_expenses = [
            (user_id, 249.00, "Food", "Lunch with friends", "2026-07-02"),
            (user_id, 89.50, "Transport", "Auto rides", "2026-07-03"),
            (user_id, 1200.00, "Bills", "Electricity bill", "2026-07-05"),
            (user_id, 450.00, "Health", "Pharmacy refill", "2026-07-08"),
            (user_id, 499.00, "Entertainment", "Movie tickets", "2026-07-12"),
            (user_id, 899.00, "Shopping", "New running shoes", "2026-07-15"),
            (user_id, 150.00, "Other", "Charity donation", "2026-07-20"),
            (user_id, 320.00, "Food", "Weekly groceries", "2026-07-25"),
        ]
        conn.executemany(
            """
            INSERT INTO expenses (user_id, amount, category, description, date)
            VALUES (?, ?, ?, ?, ?)
            """,
            sample_expenses,
        )

        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    # Allow `python database/db.py` to build and seed the database directly.
    init_db()
    seed_db()
    print(f"Database ready at {DB_PATH}")
