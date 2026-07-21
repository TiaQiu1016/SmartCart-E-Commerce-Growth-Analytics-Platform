# Customer Segmentation — Methodology

This note documents the K-Means segmentation in `src/segmentation_clv.py`.

## Problem Framing

Segmentation groups 5,878 customers into behaviorally distinct clusters based on their RFM (Recency, Frequency, Monetary) profile. The goal is a small number of actionable, interpretable groups — not the most statistically optimal partition — so each segment can be assigned a single concrete marketing action.

## Feature Engineering and Normalization

Raw RFM values are heavily right-skewed: a small number of high-frequency, high-revenue customers pull the distribution. Applying K-Means directly to raw values would allow these outliers to dominate cluster boundaries.

Two transformations are applied in sequence, as pinned in the proposal feedback:

1. **log1p transform** on each of `recency_days`, `frequency`, and `monetary`. This compresses the long right tail without dropping outliers.
2. **StandardScaler** (zero mean, unit variance) applied to the log-transformed values. This ensures no single dimension dominates the distance calculation due to scale differences.

These transformations are fit on the full customer population and applied consistently whenever the model is used.

## K Selection

K-Means is fitted for k = 4 through k = 8 with `n_init=50` and `random_state=42`. The silhouette score — which measures how similar each customer is to its own cluster compared to other clusters — is used to select k:

| k | Silhouette score | Inertia |
| --- | --- | --- |
| **4** | **0.363** | 5003 |
| 5 | 0.336 | 4171 |
| 6 | 0.333 | 3616 |
| 7 | 0.305 | 3237 |
| 8 | 0.309 | 2931 |

**k = 4** is selected (highest silhouette score). This also produces the minimum number of segments required by the project scope, which aids interpretability.

## Segment Labels and Recommended Actions

Cluster labels are assigned algorithmically based on each cluster's mean RFM profile, using a weighted value score (recency 25%, frequency 35%, monetary 40%):

| Segment | Customers | Avg Recency (days) | Avg Frequency | Avg Revenue (£) | Recommended Action |
| --- | --- | --- | --- | --- | --- |
| Champions | 1,087 | 24 | 20.3 | 11,687 | Protect and grow with VIP retention, early access, and referral offers. |
| Recent / Promising | 1,211 | 27 | 3.0 | 858 | Trigger a second-purchase campaign while recency is still strong. |
| At Risk High-Value | 1,503 | 205 | 5.5 | 2,179 | Prioritize win-back messaging because past value is high but recent activity is weak. |
| Hibernating | 2,077 | 390 | 1.4 | 349 | Use low-cost reactivation only; avoid heavy discount spend unless basket value improves. |

Labels are not hardcoded: they are assigned each run by ranking clusters on the value score and mapping to the named tiers. This means a different dataset would produce different cluster-to-label assignments automatically.

## Output

Segment assignments (`customer_id`, `segment`, `recommended_action`, `recency_days`, `frequency`, `monetary`, `cluster`) are written to the `segments` SQLite table. Cluster-level profiles are written to `segment_profiles`. A summary comparison table across all four segments is written to `segment_comparison_summary`.

The K-Means `segments` table is the authoritative segmentation used throughout the dashboard and downstream models. A SQL-based RFM quartile baseline (`rfm_scored`) is retained as a cross-check only.

## Limitations

- K-Means assumes clusters of roughly equal density and works best with roughly spherical boundaries. RFM data, even after log-transformation, does not strictly meet this assumption.
- The silhouette score selects k = 4 by a margin (0.363 vs. 0.336 for k = 5). A different dataset or a different random seed could shift this selection to k = 5.
- Segment names and actions are assigned by a rule-based heuristic on cluster means, not learned from labels. Edge cases — e.g., a cluster that scores high on frequency but low on monetary — may not map cleanly to the intended label.
- Segmentation is static: it reflects customer behavior through the pipeline run date and does not update as new transactions arrive.
