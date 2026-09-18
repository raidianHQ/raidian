"""Verifies the actual Alembic migration files -- not just the in-memory
ORM metadata used by the other tests -- create and tear down the expected
schema. Run out-of-process so it exercises exactly what `alembic upgrade
head` would do in a real environment.
"""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]

EXPECTED_TABLES = {
    "decks",
    "reflection_sessions",
    "spreads",
    "cards",
    "readings",
    "spread_positions",
    "card_draws",
}


def _run_alembic(*args: str, db_path: Path) -> None:
    env = os.environ.copy()
    env["RAIDIAN_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def _table_names(db_path: Path) -> set[str]:
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    finally:
        con.close()
    return {row[0] for row in rows}


def test_migrations_create_and_drop_the_expected_tables(tmp_path):
    db_path = tmp_path / "migration_check.db"

    _run_alembic("upgrade", "head", db_path=db_path)
    assert EXPECTED_TABLES.issubset(_table_names(db_path))

    _run_alembic("downgrade", "base", db_path=db_path)
    assert EXPECTED_TABLES.isdisjoint(_table_names(db_path))
