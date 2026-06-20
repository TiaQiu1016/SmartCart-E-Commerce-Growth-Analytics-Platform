"""
market_basket.py

Finds product association rules (Apriori) from Online Retail II invoice data.

Each invoice is treated as a basket; items are stock codes. The analysis
identifies product sets that are disproportionately often bought together,
measured by support, confidence, and lift.

Only multi-item invoices are used (single-item baskets cannot produce rules).
Online Retail II is used exclusively — Olist has only ~3.3% multi-item orders
and is unsuitable for this analysis.

Outputs:
  SQLite table  — association_rules (antecedents, consequents, support,
                  confidence, lift, leverage, conviction)
  Figures       — basket_top_rules.png, basket_support_confidence.png

Usage:
    python src/market_basket.py
"""

from pathlib import Path
import sqlite3

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from mlxtend.frequent_patterns import apriori, association_rules

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "smartcart.db"
OUT_DIR = ROOT / "reports" / "figures"

MIN_SUPPORT = 0.02
MIN_CONFIDENCE = 0.3
MIN_LIFT = 1.5
TOP_N = 15

BLUE, ACCENT = "#234A70", "#E08A3C"


def load_transactions(db_path: Path) -> tuple[pd.DataFrame, dict[str, str]]:
    with sqlite3.connect(db_path) as con:
        tx = pd.read_sql(
            "SELECT invoice, stock_code, description, quantity FROM transactions", con
        )
    desc_lookup = (
        tx.groupby("stock_code")["description"]
        .agg(lambda s: s.mode().iloc[0])
        .to_dict()
    )
    return tx, desc_lookup


def build_basket_matrix(tx: pd.DataFrame) -> pd.DataFrame:
    item_counts = tx.groupby("invoice")["stock_code"].nunique()
    multi_invoices = item_counts[item_counts >= 2].index
    tx_multi = tx[tx["invoice"].isin(multi_invoices)]

    print(f"Multi-item invoices:     {len(multi_invoices):,}")
    print(f"Unique products in scope: {tx_multi['stock_code'].nunique():,}")

    basket = (
        tx_multi.groupby(["invoice", "stock_code"])["quantity"]
        .sum()
        .unstack(fill_value=0)
        .astype(bool)
    )
    return basket


def fmt_items(items: frozenset, desc_lookup: dict[str, str], max_chars: int = 28) -> str:
    names = [desc_lookup.get(i, i).title()[:max_chars] for i in sorted(items)]
    return ", ".join(names)


def main(db_path: Path = DB_PATH, out_dir: Path = OUT_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    tx, desc_lookup = load_transactions(db_path)
    basket = build_basket_matrix(tx)

    # ── Apriori frequent itemsets ─────────────────────────────────────────────
    print(f"\nRunning Apriori (min_support={MIN_SUPPORT}) on "
          f"{basket.shape[0]:,} invoices × {basket.shape[1]:,} products ...")
    freq_items = apriori(basket, min_support=MIN_SUPPORT, use_colnames=True)
    print(f"Frequent itemsets: {len(freq_items):,}")

    if freq_items.empty:
        print("No frequent itemsets found — try lowering MIN_SUPPORT.")
        return

    # ── Association rules ─────────────────────────────────────────────────────
    rules = association_rules(freq_items, metric="lift", min_threshold=MIN_LIFT)
    rules = rules[rules["confidence"] >= MIN_CONFIDENCE].copy()
    rules = rules.sort_values("lift", ascending=False).reset_index(drop=True)
    print(f"Rules (lift >= {MIN_LIFT}, confidence >= {MIN_CONFIDENCE}): {len(rules):,}")

    if rules.empty:
        print("No rules met the thresholds. Try lowering MIN_LIFT or MIN_CONFIDENCE.")
        return

    # Human-readable rule labels
    rules["rule_label"] = rules.apply(
        lambda r: (
            fmt_items(r["antecedents"], desc_lookup)
            + " → "
            + fmt_items(r["consequents"], desc_lookup)
        ),
        axis=1,
    )

    # ── Write to SQLite ───────────────────────────────────────────────────────
    rules_db = rules[
        ["antecedents", "consequents", "support", "confidence", "lift", "leverage", "conviction"]
    ].copy()
    rules_db["antecedents"] = rules_db["antecedents"].apply(lambda s: ", ".join(sorted(s)))
    rules_db["consequents"] = rules_db["consequents"].apply(lambda s: ", ".join(sorted(s)))
    # conviction is inf when confidence == 1; replace with NULL for SQLite
    rules_db["conviction"] = rules_db["conviction"].replace([np.inf, -np.inf], np.nan)
    with sqlite3.connect(db_path) as con:
        rules_db.to_sql("association_rules", con, if_exists="replace", index=False)
        con.commit()
    print(f"association_rules written to SQLite ({len(rules_db):,} rows)")

    # ── Print top rules ───────────────────────────────────────────────────────
    print("\nTop 10 rules by lift:")
    for _, row in rules.head(10).iterrows():
        print(
            f"  lift={row['lift']:.2f}  conf={row['confidence']:.2f}"
            f"  sup={row['support']:.3f}  {row['rule_label']}"
        )

    # ── Figure 1: top N rules by lift ─────────────────────────────────────────
    top = rules.head(TOP_N).iloc[::-1]
    fig, ax = plt.subplots(figsize=(11, 6))
    bars = ax.barh(top["rule_label"], top["lift"], color=BLUE)
    ax.set_xlabel("Lift")
    ax.set_title(f"Top {TOP_N} Product Association Rules by Lift")
    ax.axvline(1.0, color="gray", linestyle="--", alpha=0.5)
    for bar, conf in zip(bars, top["confidence"]):
        ax.text(
            bar.get_width() + 0.05,
            bar.get_y() + bar.get_height() / 2,
            f"conf={conf:.2f}",
            va="center",
            fontsize=7.5,
        )
    fig.tight_layout()
    fig.savefig(out_dir / "basket_top_rules.png", dpi=150)
    plt.close(fig)

    # ── Figure 2: support vs confidence scatter (bubble size = lift) ──────────
    plot_rules = rules.head(200)
    fig, ax = plt.subplots(figsize=(7, 5))
    sc = ax.scatter(
        plot_rules["support"],
        plot_rules["confidence"],
        s=plot_rules["lift"] * 25,
        c=plot_rules["lift"],
        cmap="Blues",
        alpha=0.7,
        edgecolors=BLUE,
        linewidths=0.4,
    )
    plt.colorbar(sc, ax=ax, label="Lift")
    ax.set_xlabel("Support")
    ax.set_ylabel("Confidence")
    ax.set_title("Association Rules: Support vs Confidence\n(bubble size = lift)")
    fig.tight_layout()
    fig.savefig(out_dir / "basket_support_confidence.png", dpi=150)
    plt.close(fig)

    print(f"\nFigures written to {out_dir}")


if __name__ == "__main__":
    main()
