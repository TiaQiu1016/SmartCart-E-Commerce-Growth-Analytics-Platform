"""
build_database.py

Builds the SmartCart SQLite data layer from the raw Online Retail II CSV.

Steps:
1. Load the raw CSV.
2. Clean it (matches the team's data-check notebook):
   - drop rows with missing Customer ID
   - keep only Quantity > 0 and Price > 0 (removes returns / credit notes)
   - parse InvoiceDate and add a Revenue column
3. Write the cleaned data to SQLite as the `transactions` table (single source of truth).
4. Execute sql/rfm.sql to build the `rfm` feature table.
5. Print verification stats for the progress report.

Usage:
    python src/build_database.py
"""

from pathlib import Path
import sqlite3
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_CSV = ROOT / "data" / "online_retail_II.csv"
DB_PATH = ROOT / "data" / "smartcart.db"
RFM_SQL = ROOT / "sql" / "rfm.sql"

COLUMN_MAP = {
    "Invoice": "invoice",
    "StockCode": "stock_code",
    "Description": "description",
    "Quantity": "quantity",
    "InvoiceDate": "invoice_date",
    "Price": "price",
    "Customer ID": "customer_id",
    "Country": "country",
}


def load_and_clean(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, encoding="ISO-8859-1")
    raw_rows = len(df)

    df = df.dropna(subset=["Customer ID"]).copy()
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])
    df["Revenue"] = df["Quantity"] * df["Price"]
    df = df[(df["Quantity"] > 0) & (df["Price"] > 0)]

    df = df.rename(columns={**COLUMN_MAP, "Revenue": "revenue"})
    df["customer_id"] = df["customer_id"].astype(int)
    df["invoice_date"] = df["invoice_date"].dt.strftime("%Y-%m-%d %H:%M:%S")

    print(f"Raw rows:     {raw_rows:,}")
    print(f"Cleaned rows: {len(df):,}")
    return df


def write_transactions(df: pd.DataFrame, db_path: Path) -> None:
    with sqlite3.connect(db_path) as con:
        df.to_sql("transactions", con, if_exists="replace", index=False)
        cur = con.cursor()
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tx_customer ON transactions(customer_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tx_invoice  ON transactions(invoice)")
        con.commit()


def build_rfm(db_path: Path, rfm_sql: Path) -> None:
    script = rfm_sql.read_text()
    with sqlite3.connect(db_path) as con:
        con.executescript(script)
        con.commit()


def verify(db_path: Path) -> None:
    with sqlite3.connect(db_path) as con:
        cur = con.cursor()

        def scalar(q):
            return cur.execute(q).fetchone()[0]

        print("\n--- Verification ---")
        print(f"transactions rows: {scalar('SELECT COUNT(*) FROM transactions'):,}")
        print(f"unique customers:  {scalar('SELECT COUNT(DISTINCT customer_id) FROM transactions'):,}")
        print(f"unique invoices:   {scalar('SELECT COUNT(DISTINCT invoice) FROM transactions'):,}")
        print(f"unique products:   {scalar('SELECT COUNT(DISTINCT stock_code) FROM transactions'):,}")
        print(f"date range:        {scalar('SELECT MIN(invoice_date) FROM transactions')} "
              f"to {scalar('SELECT MAX(invoice_date) FROM transactions')}")

        repeat = scalar("SELECT COUNT(*) FROM (SELECT customer_id FROM transactions "
                        "GROUP BY customer_id HAVING COUNT(DISTINCT invoice) > 1)")
        total = scalar("SELECT COUNT(DISTINCT customer_id) FROM transactions")
        print(f"repeat customers:  {repeat:,} ({repeat / total * 100:.1f}%)")

        multi = scalar("SELECT COUNT(*) FROM (SELECT invoice FROM transactions "
                       "GROUP BY invoice HAVING COUNT(DISTINCT stock_code) > 1)")
        inv = scalar("SELECT COUNT(DISTINCT invoice) FROM transactions")
        print(f"multi-item invoices: {multi:,} ({multi / inv * 100:.1f}%)")

        print(f"\nrfm rows: {scalar('SELECT COUNT(*) FROM rfm'):,}")
        print("rfm sample (top 5 by monetary):")
        for row in cur.execute("SELECT * FROM rfm ORDER BY monetary DESC LIMIT 5"):
            print("  ", row)


def main() -> None:
    if not RAW_CSV.exists():
        raise FileNotFoundError(f"Missing {RAW_CSV}. Put the Online Retail II CSV in data/.")
    df = load_and_clean(RAW_CSV)
    write_transactions(df, DB_PATH)
    build_rfm(DB_PATH, RFM_SQL)
    verify(DB_PATH)
    print(f"\nDatabase written to {DB_PATH}")


if __name__ == "__main__":
    main()
