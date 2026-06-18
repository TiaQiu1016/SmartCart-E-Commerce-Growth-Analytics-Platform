"""
make_figures.py

Generates PR1 visualizations from the SmartCart SQLite database and saves them
as PNGs in reports/figures/. Run build_database.py first.

Usage:
    python src/make_figures.py
"""

from pathlib import Path
import sqlite3
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "smartcart.db"
SQL_DIR = ROOT / "sql"
OUT_DIR = ROOT / "reports" / "figures"

BLUE = "#234A70"
ACCENT = "#E08A3C"


def _ensure_tables(con):
    # build derived tables the figures need (idempotent)
    for f in ["rfm.sql", "rfm_segments.sql", "churn_labels.sql"]:
        con.executescript((SQL_DIR / f).read_text())
    con.commit()


def fig_segments(con, out):
    df = pd.read_sql(
        "SELECT segment, COUNT(*) AS customers, AVG(monetary) AS avg_monetary "
        "FROM rfm_scored GROUP BY segment ORDER BY avg_monetary DESC", con)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar(df["segment"], df["customers"], color=BLUE)
    ax.set_title("Customer Segments (RFM scoring)")
    ax.set_ylabel("Number of customers")
    ax.tick_params(axis="x", rotation=20)
    for b, val in zip(bars, df["avg_monetary"]):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height(),
                f"avg ${val:,.0f}", ha="center", va="bottom", fontsize=8)
    fig.tight_layout(); fig.savefig(out / "rfm_segments.png", dpi=150); plt.close(fig)


def fig_monthly(con, out):
    df = pd.read_sql(
        "SELECT substr(invoice_date,1,7) AS month, "
        "COUNT(DISTINCT invoice) AS orders, SUM(revenue) AS revenue "
        "FROM transactions GROUP BY month ORDER BY month", con)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(df["month"], df["revenue"] / 1e6, color=BLUE, marker="o", label="Revenue ($M)")
    ax.set_title("Monthly Revenue (Online Retail II)")
    ax.set_ylabel("Revenue ($M)")
    ax.tick_params(axis="x", rotation=60)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout(); fig.savefig(out / "monthly_revenue.png", dpi=150); plt.close(fig)


def fig_top_products(con, out):
    df = pd.read_sql(
        "SELECT MAX(description) AS product, SUM(revenue) AS revenue "
        "FROM transactions GROUP BY stock_code ORDER BY revenue DESC LIMIT 10", con)
    df = df.iloc[::-1]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(df["product"].str.title().str[:30], df["revenue"] / 1e3, color=ACCENT)
    ax.set_title("Top 10 Products by Revenue")
    ax.set_xlabel("Revenue ($K)")
    fig.tight_layout(); fig.savefig(out / "top_products.png", dpi=150); plt.close(fig)


def fig_uk_vs_nonuk(con, out):
    df = pd.read_sql(
        "SELECT CASE WHEN country='United Kingdom' THEN 'UK' ELSE 'Non-UK' END AS region, "
        "SUM(revenue) AS revenue, SUM(revenue)/COUNT(DISTINCT invoice) AS aov "
        "FROM transactions GROUP BY region", con)
    fig, axes = plt.subplots(1, 2, figsize=(9, 4))
    axes[0].bar(df["region"], df["revenue"] / 1e6, color=BLUE)
    axes[0].set_title("Total Revenue"); axes[0].set_ylabel("$M")
    axes[1].bar(df["region"], df["aov"], color=ACCENT)
    axes[1].set_title("Average Order Value"); axes[1].set_ylabel("$")
    fig.suptitle("UK vs Non-UK Customers")
    fig.tight_layout(); fig.savefig(out / "uk_vs_nonuk.png", dpi=150); plt.close(fig)


def fig_churn(con, out):
    df = pd.read_sql(
        "SELECT CASE WHEN churned=1 THEN 'Churned' ELSE 'Active' END AS status, "
        "COUNT(*) AS customers FROM churn_labels GROUP BY churned", con)
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.pie(df["customers"], labels=df["status"], autopct="%1.1f%%",
           colors=[ACCENT, BLUE], startangle=90)
    ax.set_title("Churn Split (90-day inactivity window)")
    fig.tight_layout(); fig.savefig(out / "churn_split.png", dpi=150); plt.close(fig)


def main(db_path=DB_PATH, out_dir=OUT_DIR):
    out_dir.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    _ensure_tables(con)
    fig_segments(con, out_dir)
    fig_monthly(con, out_dir)
    fig_top_products(con, out_dir)
    fig_uk_vs_nonuk(con, out_dir)
    fig_churn(con, out_dir)
    con.close()
    print(f"Figures written to {out_dir}")


if __name__ == "__main__":
    main()
