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
  SQLite tables — association_rules, product_recommendations
  Figures       — basket_top_rules.png, basket_support_confidence.png,
                  basket_network.png, basket_recommendations.png

Usage:
    python src/market_basket.py
"""

from pathlib import Path
import sqlite3

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import numpy as np
import pandas as pd
from mlxtend.frequent_patterns import apriori, association_rules

try:
    import networkx as nx
    _HAS_NX = True
except ImportError:
    _HAS_NX = False

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "smartcart.db"
OUT_DIR = ROOT / "reports" / "figures"

MIN_SUPPORT = 0.02
MIN_CONFIDENCE = 0.3
MIN_LIFT = 1.5
TOP_N = 15

BLUE, ACCENT = "#234A70", "#E08A3C"
TYPE_COLORS = {"Complete the Set": BLUE, "Often Bought With": ACCENT}

_STOPWORDS = {"and", "the", "of", "in", "a", "an", "to", "for", "with", "set"}


def classify_rule_type(
    antecedents: frozenset, consequents: frozenset, desc_lookup: dict[str, str]
) -> str:
    """Return 'Complete the Set' if antecedent and consequent share >=2 significant
    description words (colour/size/theme variants), else 'Often Bought With'."""
    def sig_words(items: frozenset) -> set[str]:
        words: set[str] = set()
        for code in items:
            for w in desc_lookup.get(code, "").lower().split():
                if len(w) >= 4 and w not in _STOPWORDS:
                    words.add(w)
        return words

    shared = sig_words(antecedents) & sig_words(consequents)
    return "Complete the Set" if len(shared) >= 2 else "Often Bought With"


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


def build_recommendations(rules: pd.DataFrame, desc_lookup: dict[str, str]) -> pd.DataFrame:
    """For each single-item antecedent, keep the highest-lift recommendation per rule_type."""
    single = rules[rules["antecedents"].apply(len) == 1].copy()
    single["src"] = single["antecedents"].apply(lambda s: next(iter(s)))
    single["dst"] = single["consequents"].apply(lambda s: next(iter(s)))
    best = (
        single.sort_values("lift", ascending=False)
        .drop_duplicates(subset=["src", "rule_type"])
        .reset_index(drop=True)
    )
    recs = pd.DataFrame({
        "stock_code": best["src"],
        "description": best["src"].map(desc_lookup),
        "recommended_stock_code": best["dst"],
        "recommended_description": best["dst"].map(desc_lookup),
        "rule_type": best["rule_type"],
        "support": best["support"].round(4),
        "confidence": best["confidence"].round(4),
        "lift": best["lift"].round(4),
    })
    return recs


def plot_network(rules: pd.DataFrame, desc_lookup: dict[str, str], out: Path) -> None:
    if not _HAS_NX:
        print("networkx not installed — skipping basket_network.png")
        return

    top_rules = rules.head(40)

    G = nx.DiGraph()
    for _, row in top_rules.iterrows():
        src = ", ".join(sorted(row["antecedents"]))
        dst = ", ".join(sorted(row["consequents"]))
        G.add_edge(src, dst, lift=row["lift"], rule_type=row["rule_type"])

    def short_label(code_str: str) -> str:
        codes = [c.strip() for c in code_str.split(",")]
        names = [desc_lookup.get(c, c).title()[:22] for c in codes]
        return "\n".join(names)

    labels = {n: short_label(n) for n in G.nodes()}
    lifts = [G[u][v]["lift"] for u, v in G.edges()]
    lift_min, lift_max = min(lifts), max(lifts)
    edge_colors = [TYPE_COLORS[G[u][v]["rule_type"]] for u, v in G.edges()]
    edge_widths = [1 + 4 * (l - lift_min) / max(lift_max - lift_min, 1) for l in lifts]

    node_degree = dict(G.degree())
    node_sizes = [300 + node_degree[n] * 200 for n in G.nodes()]
    pos = nx.spring_layout(G, seed=42, k=2.5)

    fig, ax = plt.subplots(figsize=(14, 10))
    nx.draw_networkx_nodes(G, pos, node_size=node_sizes, node_color="#4A6FA5", alpha=0.85, ax=ax)
    nx.draw_networkx_edges(
        G, pos, width=edge_widths, edge_color=edge_colors,
        arrows=True, arrowsize=14, connectionstyle="arc3,rad=0.08", ax=ax,
    )
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=6.5, font_color="white", ax=ax)

    from matplotlib.patches import Patch
    legend = [Patch(color=c, label=t) for t, c in TYPE_COLORS.items()]
    ax.legend(handles=legend, loc="upper left", fontsize=9)
    ax.set_title("Product Association Network (top 40 rules by lift)\nEdge colour = rule type  |  thickness = lift", pad=14)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(out / "basket_network.png", dpi=150)
    plt.close(fig)
    print("basket_network.png written")


def plot_recommendations(recs: pd.DataFrame, out: Path) -> None:
    """Two-panel bar chart: 'Complete the Set' (left) and 'Often Bought With' (right)."""
    def rule_str(row: pd.Series) -> str:
        src = str(row["description"] or row["stock_code"]).title()[:26]
        dst = str(row["recommended_description"] or row["recommended_stock_code"]).title()[:26]
        return f"{src}\n  → {dst}"

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    for ax, rtype in zip(axes, ["Complete the Set", "Often Bought With"]):
        subset = (
            recs[recs["rule_type"] == rtype]
            .sort_values("lift", ascending=False)
            .head(10)
            .iloc[::-1]
        )
        if subset.empty:
            ax.set_visible(False)
            continue
        labels = subset.apply(rule_str, axis=1)
        color = TYPE_COLORS[rtype]
        bars = ax.barh(labels, subset["lift"], color=color, alpha=0.85)
        for bar, conf in zip(bars, subset["confidence"]):
            ax.text(
                bar.get_width() + 0.1,
                bar.get_y() + bar.get_height() / 2,
                f"{conf:.0%}",
                va="center", fontsize=7.5,
            )
        ax.set_xlabel("Lift")
        ax.set_title(f"{rtype}", fontsize=12, fontweight="bold", color=color)
        ax.axvline(1.0, color="gray", linestyle="--", alpha=0.4)

    fig.suptitle("Product Recommendations by Rule Type", fontsize=13, y=1.01)
    fig.tight_layout()
    fig.savefig(out / "basket_recommendations.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("basket_recommendations.png written")


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

    # Classify each rule and attach human-readable labels
    rules["rule_type"] = rules.apply(
        lambda r: classify_rule_type(r["antecedents"], r["consequents"], desc_lookup), axis=1
    )
    rules["rule_label"] = rules.apply(
        lambda r: (
            fmt_items(r["antecedents"], desc_lookup)
            + " → "
            + fmt_items(r["consequents"], desc_lookup)
        ),
        axis=1,
    )

    type_counts = rules["rule_type"].value_counts()
    for rtype, n in type_counts.items():
        print(f"  {rtype}: {n} rules")

    # ── Write to SQLite ───────────────────────────────────────────────────────
    rules_db = rules[
        ["antecedents", "consequents", "rule_type", "support", "confidence", "lift", "leverage", "conviction"]
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

    # ── Figure 1: top N rules by lift, coloured by rule_type ─────────────────
    top = rules.head(TOP_N).iloc[::-1]
    bar_colors = [TYPE_COLORS[t] for t in top["rule_type"]]
    fig, ax = plt.subplots(figsize=(11, 6))
    bars = ax.barh(top["rule_label"], top["lift"], color=bar_colors)
    ax.set_xlabel("Lift")
    ax.set_title(f"Top {TOP_N} Product Association Rules by Lift")
    ax.axvline(1.0, color="gray", linestyle="--", alpha=0.5)
    for bar, conf in zip(bars, top["confidence"]):
        ax.text(
            bar.get_width() + 0.05,
            bar.get_y() + bar.get_height() / 2,
            f"conf={conf:.2f}",
            va="center", fontsize=7.5,
        )
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=c, label=t) for t, c in TYPE_COLORS.items()], fontsize=8)
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

    # ── Product recommendations table ─────────────────────────────────────────
    recs = build_recommendations(rules, desc_lookup)
    with sqlite3.connect(db_path) as con:
        recs.to_sql("product_recommendations", con, if_exists="replace", index=False)
        con.commit()
    print(f"product_recommendations written to SQLite ({len(recs):,} rows)")

    # ── Figure 3: network graph ───────────────────────────────────────────────
    plot_network(rules, desc_lookup, out_dir)

    # ── Figure 4: bundle recommendations bar chart ────────────────────────────
    plot_recommendations(recs, out_dir)

    print(f"\nFigures written to {out_dir}")


if __name__ == "__main__":
    main()
