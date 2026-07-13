# Module Output Audit for Stage 3

## Purpose

This audit records which computed outputs are currently available for the
dashboard, group-comparison V2, and future AI insight-brief generator. It is a
working checklist, not a final methodology document.

## Current SQLite outputs checked locally

Local database checked: `data/smartcart.db`.

| Module | SQLite output | Current status | Notes |
| --- | --- | --- | --- |
| Transactions | `transactions` | Available | Core cleaned transaction table used by downstream modules. |
| RFM | `rfm` | Available | Contains `customer_id`, `recency_days`, `frequency`, and `monetary`. |
| Segmentation | `segments`, `segment_profiles`, `segmentation_metrics` | Available | Supports dashboard and segment-level summaries. |
| Baseline CLV | `clv` | Available | Contains capped baseline CLV inputs and `clv_estimate`. |
| Enhanced CLV | `clv_bgnbd` | Code available; local table may need regeneration | Run `python src/clv_bgnbd.py` after rebuilding the database. |
| Propensity | `propensity_scores` | Available | Customer-level score only; model diagnostics are documented separately. |
| Market basket | `association_rules`, `product_recommendations` | Available | Supports top product-pair recommendations. |
| Group comparison V1 | `group_comparison_results`, `segment_comparison_summary` | Available | Descriptive comparisons and effect sizes are available. |
| Predictive churn | `churn_scores` | Code available; local table written after `src/churn_model.py` runs | Needed for leakage-free group-comparison V2 and AI churn summaries. |
| Cohort retention | `cohort_retention`, `cohort_revenue` | Code available; local tables written after `src/cohort_analysis.py` runs | Supports retention heatmap and cohort revenue dashboard views. |

## Stage 3 implications

The dashboard and AI input layer can already use segmentation, baseline CLV,
propensity, market-basket, group-comparison V1, churn, and cohort outputs.
Enhanced CLV can be added after the BG/NBD script writes `clv_bgnbd` to SQLite.

Group-comparison V2 should not use the current recency-based churn snapshot as
evidence that segments independently predict churn, because the snapshot and
the segment labels both depend on recency. The new `churn_scores` table provides
customer-level future churn labels and prediction probabilities from a strict
feature-window / label-window split. A fully leakage-free segment validation
still needs segment labels computed at the same cutoff.

## Immediate follow-up checklist

1. Regenerate the local database if the raw CSV has changed.
2. Run the enhanced CLV script and confirm `clv_bgnbd` exists.
3. Add `segments_at_cutoff` if the team wants a fully leakage-free segment vs.
   future churn V2 analysis.
4. Re-run `src/prepare_insight_inputs.py` and review `unavailable_modules`.
5. Use the completed outputs to build group-comparison V2 and the first
   AI-generated insight brief.
