"""
Export a deployment-ready SQLite database for Streamlit Community Cloud.

Copies all tables from data/smartcart.db EXCEPT `transactions` (805K rows, ~100MB).
The resulting data/smartcart_deploy.db is tracked in git and used automatically
by the dashboard when present (see dashboard/utils.py DB_PATH logic).

Usage:
    python src/export_deploy_db.py
"""

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC  = ROOT / "data" / "smartcart.db"
DST  = ROOT / "data" / "smartcart_deploy.db"

SKIP = {"transactions"}


def export() -> None:
    if not SRC.exists():
        raise FileNotFoundError(
            f"Source DB not found: {SRC}\nRun src/build_database.py first."
        )

    DST.unlink(missing_ok=True)

    with sqlite3.connect(SRC) as src, sqlite3.connect(DST) as dst:
        tables = [
            r[0]
            for r in src.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]

        dst.execute("PRAGMA journal_mode=WAL")

        for table in tables:
            if table in SKIP:
                print(f"  skip   {table}")
                continue

            schema = src.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()[0]
            dst.execute(schema)

            rows = src.execute(f"SELECT * FROM {table}").fetchall()
            if rows:
                placeholders = ",".join(["?"] * len(rows[0]))
                dst.executemany(f"INSERT INTO {table} VALUES ({placeholders})", rows)

            dst.commit()
            print(f"  copied {table}: {len(rows):,} rows")

    size_mb = DST.stat().st_size / 1_000_000
    print(f"\nDeploy DB written to {DST.relative_to(ROOT)} ({size_mb:.1f} MB)")
    print("Commit this file and push — Streamlit Community Cloud will use it automatically.")


if __name__ == "__main__":
    export()
