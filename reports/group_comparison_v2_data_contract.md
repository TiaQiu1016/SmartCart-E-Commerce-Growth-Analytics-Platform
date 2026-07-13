# Group Comparison V2 Data Contract

## Objective

Group Comparison V2 should test whether historical customer groups are useful
for understanding future behavior. This is different from V1, which mainly
describes current differences between countries and segments.

The main methodological issue to avoid is circularity. A comparison such as
`segment` vs. `churned_snapshot` is partly circular because the segment model
uses `recency_days`, and the churn snapshot is also defined from recency. V2
should therefore compare pre-cutoff segment labels with post-cutoff outcomes.

## Required churn output

Expected table: `churn_scores`.

| Column | Required | Meaning |
| --- | --- | --- |
| `customer_id` | Yes | Join key shared with segmentation and transaction outputs. |
| `feature_cutoff_date` | Yes | Last date allowed for feature construction. |
| `label_window_days` | Yes | Length of the future outcome window, for example 90 days. |
| `actual_churn_label` | Yes | Observed future churn outcome after the cutoff. |
| `predicted_churn_probability` | Yes | Model score generated only from pre-cutoff features. |
| `is_test_set` | Strongly recommended | Identifies held-out records for unbiased reporting. |

## Required segment output

For a fully leakage-free V2, segment labels should be computed from customer
features available on or before the same `feature_cutoff_date` used by the
churn model. If the current `segments` table is based on the full observation
period, it can be used only as an exploratory comparison and must be labelled
as such.

Recommended table for V2: `segments_at_cutoff`.

| Column | Required | Meaning |
| --- | --- | --- |
| `customer_id` | Yes | Join key. |
| `feature_cutoff_date` | Yes | Cutoff matching the churn table. |
| `segment` | Yes | Segment assigned using only pre-cutoff RFM features. |
| `recency_days` | Recommended | Pre-cutoff RFM value used for segment assignment. |
| `frequency` | Recommended | Pre-cutoff RFM value used for segment assignment. |
| `monetary` | Recommended | Pre-cutoff RFM value used for segment assignment. |

## Planned V2 comparisons

1. Segment vs. actual future churn rate on the held-out set.
2. Segment vs. average predicted churn probability.
3. UK vs. non-UK future churn rate and predicted churn probability.
4. Segment vs. future repeat-purchase indicator if available.
5. Segment vs. future revenue if a post-cutoff revenue table is available.

## Planned tests and effect sizes

| Comparison type | Test | Effect size |
| --- | --- | --- |
| Categorical outcome by group | Chi-square test | Cramer's V |
| Continuous score by two groups | Welch t-test and Mann-Whitney U | Cohen's d |
| Continuous score across segments | ANOVA or Kruskal-Wallis | Eta-squared or rank-based effect size |

P-values should not be interpreted alone. The report should prioritize effect
sizes and business relevance, then translate only meaningful differences into
actions.

## Current status

`src/churn_model.py` writes the required `churn_scores` table after the churn
model runs. `src/segments_at_cutoff.py` now writes the required
`segments_at_cutoff` table and V2 validation outputs:

- `segments_at_cutoff`
- `segment_churn_v2_summary`
- `segment_churn_v2_results`

The V2 comparison now uses pre-cutoff segment labels joined to post-cutoff
future churn outcomes. The current dashboard can still show the full-period
`segments` table for current-state business views, but V2 evidence should use
`segments_at_cutoff`.
