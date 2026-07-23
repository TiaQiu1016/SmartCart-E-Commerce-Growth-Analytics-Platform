# Final Presentation Outline - Xuechen Sections

This outline covers the sections Xuechen can own in the final recorded presentation. Timing assumes a 20-minute total presentation shared by two speakers.

## Suggested Speaker Split

- Tian: project overview, dashboard demo, churn model, propensity, market basket, cohort/deployment.
- Xuechen: segmentation, CLV, group insights, leakage-free segment churn validation, AI insight brief and guardrails.

Recommended Xuechen time: 8-10 minutes total.

## Slide 1 - Customer Segmentation: Turning Transactions into Action Groups

### Main message

SmartCart converts transaction history into four interpretable customer groups using RFM + K-Means.

### Visuals to use

- Segment count/profile chart from dashboard or `reports/figures/kmeans_segments.png`.
- Optional: segment scatter or segment profile table.

### Talking points

- RFM features: recency, frequency, monetary value.
- Normalization locked down: `log1p` then `StandardScaler` before K-Means.
- k = 4 chosen for interpretability and silhouette performance.
- Segments are not just labels; each one carries an action.

### Business takeaway

Retailers can move from one-size-fits-all marketing to segment-specific actions.

## Slide 2 - Segment Actions and Customer Value

### Main message

Each segment has a data-backed recommendation, not just a descriptive label.

### Visuals to use

- Segment action table from dashboard.
- CLV by segment chart.

### Talking points

- Champions: protect and grow.
- Recent / Promising: second-purchase campaign.
- At Risk High-Value: win-back messaging.
- Hibernating: low-cost reactivation.
- Actions are stored in the `segments.recommended_action` output and reused by the AI brief.

### Business takeaway

The segment output is designed to be immediately usable by a small retailer.

## Slide 3 - CLV: Baseline and BG/NBD Enhancement

### Main message

SmartCart uses both a transparent baseline CLV and a stronger probabilistic CLV model.

### Visuals to use

- `reports/figures/clv_by_segment.png`
- `reports/figures/clv_bgnbd_by_segment.png`
- Optional: BG/NBD vs baseline chart.

### Talking points

- Baseline CLV is easy to explain: order value x annual order rate x recency weight.
- We fixed the one-time/short-tenure buyer issue with a 90-day minimum window and order-rate cap.
- BG/NBD + Gamma-Gamma estimates 12-month value and probability alive.
- One-time buyers are flagged because P(alive) can be inflated.

### Business takeaway

CLV helps retailers prioritize who deserves high-touch campaigns and who should receive lower-cost outreach.

## Slide 4 - Group Insights: Evidence, Not Causality

### Main message

Group comparisons identify meaningful differences between customer groups, but they are observational.

### Visuals to use

- Group Insights dashboard page.
- Effect size chart for Champions vs Hibernating or UK vs Non-UK.

### Talking points

- Used Welch t-tests, Mann-Whitney U, chi-square, and effect sizes.
- Effect sizes are shown because p-values alone can be misleading with large samples.
- The original snapshot churn comparison was descriptive and partly circular, so we did not use it as final predictive evidence.

### Business takeaway

The group comparison module helps choose where to focus, while keeping limitations clear.

## Slide 5 - Leakage-Free Segment Churn Validation

### Main message

We corrected the timing issue by comparing pre-cutoff segments with future churn outcomes.

### Visuals to use

- Group Insights `Future Churn Validation` tab.
- Churn dashboard segment chart.

### Talking points

- Churn model cutoff: 2011-09-10.
- Segment labels for V2 come from `segments_at_cutoff`, using only pre-cutoff RFM behavior.
- Future churn is measured in the following 90-day label window.
- Held-out results show Hibernating customers have the highest future churn and Champions the lowest.

### Business takeaway

Segments can be used as an action layer for churn risk without leaking future information into the grouping.

## Slide 6 - AI Insight Brief: Plain-Language Recommendations with Guardrails

### Main message

The AI brief turns computed model outputs into a plain-language business summary without inventing numbers.

### Visuals to use

- AI Brief dashboard page.
- Example segment action from `reports/ai_insight_brief_draft.md`.

### Talking points

- `prepare_insight_inputs.py` creates structured JSON from verified SQLite outputs.
- `generate_insight_brief.py` creates a reviewed candidate brief from that JSON.
- Submitted version is deterministic and evidence-based, not an external LLM call.
- Guardrails: use only computed numbers, one action per segment, preserve limitations, no causal claims.

### Business takeaway

The brief gives small retailers an accessible explanation of what the analytics mean and what to do next.

## Closing Sentence for Xuechen Portion

Together, these modules make SmartCart more than a dashboard of model outputs: they connect segmentation, value, churn risk, and recommendations into actions that a non-technical retailer can review and apply.
