# Market-Basket (Apriori) Analysis — Methodology

This note documents `src/market_basket.py` and the threshold sensitivity
check in `src/market_basket_sensitivity.py`.

## Problem framing

Find product sets that are bought together more often than chance would
predict, using each invoice as a "basket." Online Retail II is used
exclusively — Olist (the backup dataset) has only ~3.3% multi-item orders
and is unsuitable for this kind of analysis. After filtering to multi-item
invoices, 33,897 of the 36,969 total invoices remain in scope, covering
4,621 distinct products.

## Method

Standard Apriori frequent-itemset mining (`mlxtend`) on a boolean
invoice-by-product basket matrix, followed by association-rule generation.
Three thresholds control which rules survive:

- **Support** — `support(A, B) = (invoices containing both A and B) / (total invoices)`.
  How common the combination is, period. Filters out coincidences that only
  happened in a handful of invoices.
- **Confidence** — `confidence(A → B) = support(A, B) / support(A)`, i.e.
  P(buy B | bought A). Directional: confidence(A→B) and confidence(B→A) are
  generally different numbers, since the denominator (how many people bought
  A vs. B) differs.
- **Lift** — `lift(A → B) = confidence(A → B) / support(B)`. Corrects
  confidence for how popular B already is on its own. Lift = 1 means no real
  association (A tells you nothing about B); lift = 25 means buying A makes B
  25x more likely than the baseline rate. This is what separates a genuine
  association from "B is just a bestseller that shows up in everything."

Current thresholds: `min_support=0.02`, `min_confidence=0.3`, `min_lift=1.5`,
producing 68 rules.

## Rule classification: Complete the Set vs. Often Bought With

Many of the highest-lift rules turned out to be color/size/theme variants of
the same product line (e.g., Green vs. Roses Regency Teacup Set, lift 25x).
This makes sense for this dataset specifically: Online Retail II is a
**wholesale** dataset — customers are gift shops and small retailers
stocking inventory, not individual consumers — so buying both color variants
to stock the shelf is a real, common pattern, not noise.

Rules are split into two types by checking whether the antecedent and
consequent share 2+ significant description words (e.g., "Teacup",
"Saucer", "Regency"):

- **Complete the Set** (23 rules) — variant pairs; the recommendation is
  "stock/offer both colors/sizes," not a cross-category discovery.
- **Often Bought With** (45 rules) — genuinely different products bought
  together; these are the cross-category recommendations a "customers also
  bought" feature would normally surface.

## Threshold sensitivity analysis

The three thresholds above were originally chosen by intuition (values that
produced a reasonable-looking rule count), not a systematic sweep. This is
the market-basket equivalent of the propensity model's hyperparameter tuning:
testing whether the chosen values sit in a stable region or on a cliff edge.

Swept `min_support` across 0.01–0.05, `min_confidence` across 0.2–0.6, and
`min_lift` across 1.0–5.0, re-mining frequent itemsets once per support level
and filtering the resulting candidate rules across the confidence/lift grid
(see `basket_sensitivity_support_lift.png`, `basket_sensitivity_support_confidence.png`).

**Finding: support is the dominant, sensitive parameter; confidence and lift are not.**

| Parameter | Behavior |
| --- | --- |
| `min_support` (0.02) | Highly sensitive. One step down to 0.015 nearly triples the rule count (175 vs. 68); to 0.01, it's 9x (638 rules, mostly noise from a much larger candidate pool). One step up to 0.025 cuts rules by more than half; by 0.04 there are zero rules left. This sits on a real slope, not a stable plateau. |
| `min_confidence` (0.3) | Smooth, well-behaved — degrades gradually (74→68→50→21→10 across 0.2→0.6). No cliff edge nearby. |
| `min_lift` (1.5) | Essentially non-binding. Raising it to 3.0 loses zero rules — every rule clearing the confidence filter already has lift ≥ 3.0. At this operating point, confidence is doing all the real filtering; lift is redundant. |

**Conclusion:** `0.02` support is a defensible middle ground — not noisy like
0.01 (638 candidate rules, many likely spurious), not empty like 0.03+ — but
it is the threshold to flag as consequential if the rule count is questioned.
`0.3` confidence is solid. `1.5` lift adds no practical filtering at this
operating point and could be raised with zero cost.

## Limitations

- Rule counts and the sensitivity results are specific to this dataset's
  multi-item invoice population (33,897 invoices); they would shift on a
  different or larger dataset.
- No statistical significance testing (e.g., bootstrap resampling of
  invoices) was done to check whether the top rules are stable signal or
  could change materially under resampling — a natural next refinement.
- The "Complete the Set" vs. "Often Bought With" split uses a simple
  word-overlap heuristic (2+ shared significant words), not a learned or
  validated classifier; edge cases (e.g., differently-worded variants) could
  be misclassified.
