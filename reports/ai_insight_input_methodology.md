# AI Insight Brief: Structured Input and Guardrails

## Purpose

`src/prepare_insight_inputs.py` creates a compact JSON input for the future AI
insight-brief generator. It does not call an LLM and does not calculate new
model predictions. Its purpose is to separate verified analytics outputs from
the later natural-language generation step.

Default local output: `data/insight_inputs.json`.

`src/generate_insight_brief.py` creates a deterministic Markdown brief draft
from that JSON. It is a reviewable bridge toward the future AI-generated brief:
it applies the same guardrails, cites only computed fields, and does not call
an external model.

## Input contract

The JSON contains:

- `metadata`: schema version, generation time, and source statement.
- `segments`: customer count, average RFM, average CLV, average purchase
  propensity when available, and the existing segment action. When the enhanced
  CLV table is available, this section also includes average BG/NBD CLV,
  average `p_alive`, average predicted active purchase weeks over the next
  12 months, and the share of customers with insufficient repeat-purchase
  history.
- `predictive_churn_by_segment`: actual future churn rate and average predicted
  churn probability, but only when a valid customer-level `churn_scores` table
  exists. If `is_test_set` is present, this section uses held-out test-set
  customers only.
- `group_comparisons`: statistical tests and effect sizes when
  `group_comparison_results` exists.
- `top_product_recommendations`: the ten highest-lift product recommendations.
- `unavailable_modules`: explicit notes for expected outputs that do not yet
  exist.
- `generation_requirements`: machine-readable rules for the future generator.

The optional enhanced CLV table is:

| Column | Meaning |
| --- | --- |
| `customer_id` | Join key shared with segmentation and baseline CLV |
| `clv_bgnbd` | BG/NBD + Gamma-Gamma 12-month CLV estimate |
| `p_alive` | BG/NBD probability that the customer is still active |
| `pred_active_purchase_weeks_12m` | Expected active purchase weeks over the next 12 months |
| `repeat_history` | Whether the customer has sufficient repeat-purchase history for the repeat-customer model |

The expected future churn table is:

| Column | Meaning |
| --- | --- |
| `customer_id` | Join key shared with the segmentation output |
| `actual_churn_label` | Observed outcome in the post-cutoff 90-day window |
| `predicted_churn_probability` | Model probability generated from pre-cutoff features |
| `is_test_set` | Recommended field identifying held-out evaluation customers |

The segment and churn analyses must use compatible feature cutoffs before their
outputs are interpreted together.

If `segments_at_cutoff` is not available, predictive churn by segment should be
treated as a useful interim diagnostic rather than the final leakage-free V2
comparison, because the production `segments` table may have been created from
the full observation window.

## Generation guardrails

The future AI brief must:

1. Use only numbers present in the structured JSON.
2. Give at least one data-backed action for every reported customer segment.
3. Identify the input fields supporting each action.
4. State when an expected module is unavailable instead of filling the gap.
5. Distinguish descriptive snapshots from future observed labels and model
   predictions.
6. Report effect sizes alongside p-values when discussing group differences.
7. Preserve important limitations and uncertainty in plain language.

The future AI brief must not:

1. Invent, extrapolate, or silently recompute metrics.
2. describe observational associations as causal effects.
3. Treat statistical significance alone as business importance.
4. Use the recency-based churn snapshot as evidence that segments independently
   predict churn.
5. recommend discriminatory targeting based on protected characteristics.
6. expose customer-level identifiers or transaction records in the brief.

## Human review

The brief remains a decision-support artifact. A team member must verify every
number against the JSON, confirm that each recommendation is supported by the
named evidence, and approve the final wording before dashboard publication.

Missing `clv_bgnbd`, `propensity_scores`, product recommendations, group
comparisons, or predictive churn outputs are reported explicitly. A `null`
metric must never be interpreted as a zero value.

## Current limitation

The current local database may not contain the enhanced `clv_bgnbd` table until
`src/clv_bgnbd.py` is run after rebuilding `data/smartcart.db`. The current
churn module does not write customer-level actual labels and predicted
probabilities to SQLite. Until that output is available with its cutoff and
label window documented, predictive churn comparisons remain explicitly
unavailable in the structured input.
