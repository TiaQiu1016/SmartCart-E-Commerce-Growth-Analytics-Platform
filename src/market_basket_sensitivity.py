"""
market_basket_sensitivity.py

Threshold sensitivity analysis for market_basket.py's Apriori rule mining.

market_basket.py hardcodes MIN_SUPPORT=0.02, MIN_CONFIDENCE=0.3, MIN_LIFT=1.5
based on intuition (the resulting rule count looked sensible), not a
systematic sweep. This script is the market-basket equivalent of the
propensity model's hyperparameter tuning: it tests whether those values sit
in a stable region (rule count changes smoothly nearby) or on a cliff edge
(a small threshold change causes a large swing), which either justifies
keeping them or shows they need adjusting.

Usage:
    python src/market_basket_sensitivity.py
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from mlxtend.frequent_patterns import apriori, association_rules

from market_basket import (
    MIN_CONFIDENCE,
    MIN_LIFT,
    MIN_SUPPORT,
    build_basket_matrix,
    load_transactions,
)

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "smartcart.db"
OUT_DIR = ROOT / "reports" / "figures"
BLUE, ACCENT = "#234A70", "#E08A3C"

SUPPORT_GRID = [0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05]
CONFIDENCE_GRID = [0.2, 0.3, 0.4, 0.5, 0.6]
LIFT_GRID = [1.0, 1.5, 2.0, 3.0, 5.0]


def rules_at_support(basket: pd.DataFrame, min_support: float) -> pd.DataFrame:
    """All candidate rules (lift >= 1.0) at a given support level, for downstream filtering."""
    freq = apriori(basket, min_support=min_support, use_colnames=True, max_len=3)
    if freq.empty:
        return pd.DataFrame(columns=["support", "confidence", "lift"])
    rules = association_rules(freq, metric="lift", min_threshold=1.0)
    return rules[["support", "confidence", "lift"]]


def count_rules(rules: pd.DataFrame, confidence: float, lift: float) -> int:
    if rules.empty:
        return 0
    return int(((rules["confidence"] >= confidence) & (rules["lift"] >= lift)).sum())


def plot_heatmap(
    matrix: pd.DataFrame, xlabel: str, ylabel: str, title: str, cmap: str,
    highlight_row: float, highlight_col: float, out_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(7, 5.5))
    im = ax.imshow(matrix.values, cmap=cmap, aspect="auto")
    ax.set_xticks(range(len(matrix.columns)))
    ax.set_xticklabels(matrix.columns)
    ax.set_yticks(range(len(matrix.index)))
    ax.set_yticklabels(matrix.index)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)

    vmax = matrix.values.max() if matrix.values.size else 1
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            val = matrix.values[i, j]
            ax.text(
                j, i, int(val), ha="center", va="center", fontsize=8,
                color="white" if val > vmax / 2 else "black",
            )

    if highlight_col in list(matrix.columns) and highlight_row in list(matrix.index):
        i = list(matrix.index).index(highlight_row)
        j = list(matrix.columns).index(highlight_col)
        ax.add_patch(
            plt.Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, edgecolor=ACCENT, linewidth=3)
        )

    plt.colorbar(im, ax=ax, label="Rule count")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main(db_path: Path = DB_PATH, out_dir: Path = OUT_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    tx, _ = load_transactions(db_path)
    basket = build_basket_matrix(tx)

    print(f"Current operating point: min_support={MIN_SUPPORT}, "
          f"min_confidence={MIN_CONFIDENCE}, min_lift={MIN_LIFT}")
    print(f"Sweeping {len(SUPPORT_GRID)} support levels "
          f"(confidence/lift grids applied via filtering, no re-mining needed)...")

    rules_by_support = {}
    for s in SUPPORT_GRID:
        rules_by_support[s] = rules_at_support(basket, s)
        print(f"  support={s}: {len(rules_by_support[s]):,} candidate rules mined (lift >= 1.0)")

    # ── heatmap A: support x lift, confidence fixed at MIN_CONFIDENCE ─────────
    heat_a = pd.DataFrame(index=SUPPORT_GRID, columns=LIFT_GRID, dtype=float)
    for s in SUPPORT_GRID:
        for l in LIFT_GRID:
            heat_a.loc[s, l] = count_rules(rules_by_support[s], MIN_CONFIDENCE, l)
    plot_heatmap(
        heat_a, xlabel="min_lift", ylabel="min_support",
        title=f"Rule Count vs. Support/Lift (confidence >= {MIN_CONFIDENCE})",
        cmap="Blues", highlight_row=MIN_SUPPORT, highlight_col=MIN_LIFT,
        out_path=out_dir / "basket_sensitivity_support_lift.png",
    )

    # ── heatmap B: support x confidence, lift fixed at MIN_LIFT ──────────────
    heat_b = pd.DataFrame(index=SUPPORT_GRID, columns=CONFIDENCE_GRID, dtype=float)
    for s in SUPPORT_GRID:
        for c in CONFIDENCE_GRID:
            heat_b.loc[s, c] = count_rules(rules_by_support[s], c, MIN_LIFT)
    plot_heatmap(
        heat_b, xlabel="min_confidence", ylabel="min_support",
        title=f"Rule Count vs. Support/Confidence (lift >= {MIN_LIFT})",
        cmap="Oranges", highlight_row=MIN_SUPPORT, highlight_col=MIN_CONFIDENCE,
        out_path=out_dir / "basket_sensitivity_support_confidence.png",
    )

    # ── local sensitivity around the current operating point ─────────────────
    base_rules = rules_by_support[MIN_SUPPORT]
    base_count = count_rules(base_rules, MIN_CONFIDENCE, MIN_LIFT)
    print(f"\nBaseline at current thresholds: {base_count} rules")

    print("\nSensitivity to support (confidence/lift held at current values):")
    for s in SUPPORT_GRID:
        if s == MIN_SUPPORT:
            continue
        c = count_rules(rules_by_support[s], MIN_CONFIDENCE, MIN_LIFT)
        print(f"  support={s}: {c} rules ({c - base_count:+d} vs baseline)")

    print("\nSensitivity to confidence (support/lift held at current values):")
    for c_val in CONFIDENCE_GRID:
        if c_val == MIN_CONFIDENCE:
            continue
        c = count_rules(base_rules, c_val, MIN_LIFT)
        print(f"  confidence={c_val}: {c} rules ({c - base_count:+d} vs baseline)")

    print("\nSensitivity to lift (support/confidence held at current values):")
    for l_val in LIFT_GRID:
        if l_val == MIN_LIFT:
            continue
        c = count_rules(base_rules, MIN_CONFIDENCE, l_val)
        print(f"  lift={l_val}: {c} rules ({c - base_count:+d} vs baseline)")

    print(f"\nFigures written to {out_dir}")


if __name__ == "__main__":
    main()
