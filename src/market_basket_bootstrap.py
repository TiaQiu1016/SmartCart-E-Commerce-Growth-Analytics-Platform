"""
market_basket_bootstrap.py

Bootstrap stability check for market_basket.py's Apriori rules.

market_basket_sensitivity.py showed min_support is the most consequential,
sensitive parameter, but sensitivity alone only describes the slope around
the current operating point -- it doesn't say whether the 68 rules mined
there are genuine signal or could shift under a different sample of
invoices. This script resamples invoices with replacement (the standard
bootstrap), re-mines rules at the exact same thresholds each time, and
reports what fraction of resamples each original rule survives in.

Usage:
    python src/market_basket_bootstrap.py
"""

from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
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
BLUE = "#234A70"

N_BOOTSTRAP = 20
RANDOM_STATE = 42


def mine_rules(basket: pd.DataFrame) -> set[tuple[frozenset, frozenset]]:
    freq = apriori(basket, min_support=MIN_SUPPORT, use_colnames=True, max_len=3)
    if freq.empty:
        return set()
    rules = association_rules(freq, metric="lift", min_threshold=MIN_LIFT)
    rules = rules[rules["confidence"] >= MIN_CONFIDENCE]
    return set(zip(rules["antecedents"], rules["consequents"]))


def main(db_path: Path = DB_PATH, out_dir: Path = OUT_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    tx, _ = load_transactions(db_path)
    basket = build_basket_matrix(tx)
    n = len(basket)

    print(f"Original basket: {n:,} invoices")
    original_rules = mine_rules(basket)
    print(
        f"Original rule set: {len(original_rules)} rules at "
        f"support>={MIN_SUPPORT}, confidence>={MIN_CONFIDENCE}, lift>={MIN_LIFT}"
    )

    survival_counts: Counter = Counter()
    new_rule_counts: Counter = Counter()
    rng = np.random.RandomState(RANDOM_STATE)

    print(f"\nRunning {N_BOOTSTRAP} bootstrap resamples (with replacement)...")
    for i in range(N_BOOTSTRAP):
        sample_idx = rng.randint(0, n, size=n)
        boot_basket = basket.iloc[sample_idx].reset_index(drop=True)
        boot_rules = mine_rules(boot_basket)

        for r in original_rules:
            if r in boot_rules:
                survival_counts[r] += 1
        for r in boot_rules:
            if r not in original_rules:
                new_rule_counts[r] += 1

        print(f"  resample {i + 1}/{N_BOOTSTRAP}: {len(boot_rules)} rules mined")

    stability = pd.DataFrame(
        [
            {
                "antecedents": ", ".join(sorted(a)),
                "consequents": ", ".join(sorted(b)),
                "survival_rate": survival_counts[(a, b)] / N_BOOTSTRAP,
            }
            for a, b in original_rules
        ]
    ).sort_values("survival_rate", ascending=False)

    print(f"\nOriginal-rule stability across {N_BOOTSTRAP} bootstrap resamples:")
    print(f"  Survive in 100% of resamples: {(stability['survival_rate'] == 1.0).sum()} / {len(stability)}")
    print(f"  Survive in >=80% of resamples: {(stability['survival_rate'] >= 0.8).sum()} / {len(stability)}")
    print(f"  Survive in >=50% of resamples: {(stability['survival_rate'] >= 0.5).sum()} / {len(stability)}")
    print(f"  Survive in <50% of resamples (unstable): {(stability['survival_rate'] < 0.5).sum()} / {len(stability)}")

    if new_rule_counts:
        top_new = sorted(new_rule_counts.items(), key=lambda kv: -kv[1])[:5]
        print(f"\nTop rules NOT in the original 68 but appearing often under resampling:")
        for (a, b), cnt in top_new:
            print(f"  {', '.join(sorted(a))} -> {', '.join(sorted(b))}: in {cnt}/{N_BOOTSTRAP} resamples")
    else:
        print("\nNo rules appeared under resampling that weren't already in the original set.")

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.hist(stability["survival_rate"], bins=np.arange(0, 1.05, 0.05), color=BLUE, edgecolor="white")
    ax.set_xlabel(f"Fraction of {N_BOOTSTRAP} bootstrap resamples a rule survives in")
    ax.set_ylabel("Number of rules")
    ax.set_title("Bootstrap Stability of Market-Basket Rules")
    fig.tight_layout()
    fig.savefig(out_dir / "basket_bootstrap_stability.png", dpi=150)
    plt.close(fig)

    print(f"\nFigure written to {out_dir}")


if __name__ == "__main__":
    main()
