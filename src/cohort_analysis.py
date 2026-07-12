"""
cohort_analysis.py

Monthly cohort retention analysis for SmartCart.

For each customer, the acquisition cohort is the calendar month of their
first purchase. Retention in period N = share of cohort customers who made
at least one purchase in month N after their first purchase month.

Outputs written to SQLite:
  - cohort_retention: cohort_month, period, active_customers, cohort_size,
                      retention_rate
  - cohort_revenue:   cohort_month, period, revenue, avg_revenue_per_customer

Usage:
    python src/cohort_analysis.py
"""

from pathlib import Path
import sqlite3

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "smartcart.db"
OUT_DIR = ROOT / "reports" / "figures"

BLUE = "#234A70"
ACCENT = "#E08A3C"


def load_transactions(db_path: Path) -> pd.DataFrame:
    with sqlite3.connect(db_path) as con:
        tx = pd.read_sql(
            "SELECT customer_id, invoice, invoice_date, revenue FROM transactions",
            con,
            parse_dates=["invoice_date"],
        )
    return tx


def build_cohort_retention(tx: pd.DataFrame) -> pd.DataFrame:
    tx = tx.copy()
    tx["order_month"] = tx["invoice_date"].dt.to_period("M")

    first_purchase = (
        tx.groupby("customer_id")["order_month"].min().rename("cohort_month")
    )
    tx = tx.join(first_purchase, on="customer_id")

    tx["period"] = (tx["order_month"] - tx["cohort_month"]).apply(lambda x: x.n)

    cohort_sizes = (
        tx[tx["period"] == 0]
        .groupby("cohort_month")["customer_id"]
        .nunique()
        .rename("cohort_size")
    )

    active = (
        tx.groupby(["cohort_month", "period"])["customer_id"]
        .nunique()
        .reset_index()
        .rename(columns={"customer_id": "active_customers"})
    )

    active = active.join(cohort_sizes, on="cohort_month")
    active["retention_rate"] = active["active_customers"] / active["cohort_size"]
    active["cohort_month"] = active["cohort_month"].astype(str)

    return active


def build_cohort_revenue(tx: pd.DataFrame) -> pd.DataFrame:
    tx = tx.copy()
    tx["order_month"] = tx["invoice_date"].dt.to_period("M")

    first_purchase = (
        tx.groupby("customer_id")["order_month"].min().rename("cohort_month")
    )
    tx = tx.join(first_purchase, on="customer_id")
    tx["period"] = (tx["order_month"] - tx["cohort_month"]).apply(lambda x: x.n)

    cohort_sizes = (
        tx[tx["period"] == 0]
        .groupby("cohort_month")["customer_id"]
        .nunique()
        .rename("cohort_size")
    )

    rev = (
        tx.groupby(["cohort_month", "period"])["revenue"]
        .sum()
        .reset_index()
    )
    rev = rev.join(cohort_sizes, on="cohort_month")
    rev["avg_revenue_per_customer"] = rev["revenue"] / rev["cohort_size"]
    rev["cohort_month"] = rev["cohort_month"].astype(str)

    return rev


def plot_retention_heatmap(retention: pd.DataFrame) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    pivot = retention.pivot_table(
        index="cohort_month", columns="period", values="retention_rate"
    )
    # Limit to first 12 periods for readability
    pivot = pivot.loc[:, pivot.columns <= 12]

    fig, ax = plt.subplots(figsize=(14, 8))
    im = ax.imshow(pivot.values, aspect="auto", cmap="Blues", vmin=0, vmax=1)

    # Annotate cells
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            val = pivot.values[i, j]
            if not np.isnan(val):
                ax.text(j, i, f"{val:.0%}", ha="center", va="center",
                        fontsize=7, color="white" if val > 0.5 else "#333")

    ax.set_xticks(range(pivot.shape[1]))
    ax.set_xticklabels([f"M+{c}" for c in pivot.columns], fontsize=8)
    ax.set_yticks(range(pivot.shape[0]))
    ax.set_yticklabels(pivot.index.tolist(), fontsize=8)
    ax.set_xlabel("Months since first purchase", fontsize=10)
    ax.set_ylabel("Acquisition cohort", fontsize=10)
    ax.set_title("Monthly Cohort Retention Rates", fontsize=12, fontweight="bold")

    plt.colorbar(im, ax=ax, label="Retention rate", shrink=0.6)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "cohort_retention_heatmap.png", dpi=150)
    plt.close(fig)
    print("Figure saved: cohort_retention_heatmap.png")


def write_outputs(retention: pd.DataFrame, revenue: pd.DataFrame, db_path: Path) -> None:
    with sqlite3.connect(db_path) as con:
        retention.to_sql("cohort_retention", con, if_exists="replace", index=False)
        revenue.to_sql("cohort_revenue", con, if_exists="replace", index=False)
        con.commit()
    print(f"cohort_retention: {len(retention):,} rows")
    print(f"cohort_revenue:   {len(revenue):,} rows")


def main(db_path: Path = DB_PATH) -> None:
    print("Loading transactions...")
    tx = load_transactions(db_path)
    print(f"  {len(tx):,} transactions, {tx['customer_id'].nunique():,} customers")

    print("\nBuilding cohort retention...")
    retention = build_cohort_retention(tx)
    n_cohorts = retention["cohort_month"].nunique()
    print(f"  {n_cohorts} monthly cohorts, {retention['period'].max()} max periods")

    # Print month-1 retention summary
    m1 = retention[retention["period"] == 1]
    print(f"  Avg month-1 retention: {m1['retention_rate'].mean():.1%}")
    m3 = retention[retention["period"] == 3]
    print(f"  Avg month-3 retention: {m3['retention_rate'].mean():.1%}")

    print("\nBuilding cohort revenue...")
    revenue = build_cohort_revenue(tx)

    write_outputs(retention, revenue, db_path)
    plot_retention_heatmap(retention)

    print("\nDone.")


if __name__ == "__main__":
    main()
