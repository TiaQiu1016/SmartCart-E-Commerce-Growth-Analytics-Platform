# Cohort Retention Analysis — Methodology

This note documents `src/cohort_analysis.py`.

## Problem Framing

Cohort retention answers a different question than the churn model: instead of scoring individual customers, it tracks what fraction of a group of customers acquired in the same month are still buying N months later. This is a diagnostic view of customer lifecycle patterns across the full dataset period, not a predictive score.

## Method

Each customer is assigned to an **acquisition cohort** — the calendar month of their first purchase. Retention in period N is defined as the share of the cohort who made at least one purchase exactly N months after their acquisition month.

Formally:

```
retention_rate[cohort, N] = customers who purchased in (cohort_month + N) / cohort_size
```

Period 0 is always 100% by definition (every customer purchased in their acquisition month). Period 1 is the first real retention signal — what fraction came back the following month.

Revenue is tracked alongside headcount: `avg_revenue_per_customer` in period N is the total revenue from that cohort in that period divided by the original cohort size (not the active subset), so it declines naturally as retention falls.

## Coverage

- **Cohorts:** 25 monthly cohorts from December 2009 to December 2011.
- **Periods tracked:** up to 24 months (the full observable window for the earliest cohorts).
- **Cohort sizes:** range from 28 (small months near dataset edges) to 955 customers (December 2009, the first full month of data).

Sample first-month retention rates by cohort:

| Cohort | Cohort size | Period 1 retention |
| --- | --- | --- |
| 2009-12 | 955 | 35.3% |
| 2010-01 | 383 | 20.6% |
| 2010-02 | 374 | 23.8% |
| 2010-03 | 443 | 19.0% |
| 2010-04 | 294 | 19.4% |

The December 2009 cohort's elevated period 1 retention (35%) compared to subsequent cohorts (~20%) likely reflects that early customers were established wholesale accounts already reordering regularly before the dataset period began.

## Outputs

Two tables are written to SQLite:

- **`cohort_retention`** — columns: `cohort_month`, `period`, `active_customers`, `cohort_size`, `retention_rate`.
- **`cohort_revenue`** — columns: `cohort_month`, `period`, `revenue`, `avg_revenue_per_customer`.

A heatmap (`reports/figures/cohort_retention_heatmap.png`) visualizes the full retention matrix: cohorts on the vertical axis, periods on the horizontal axis, color intensity proportional to retention rate.

## Limitations

- Later cohorts have fewer observable periods: a customer acquired in November 2011 can only be tracked for one month before the dataset ends. The heatmap naturally has a triangular shape — later cohorts have shorter rows.
- This is a descriptive, historical analysis. It does not control for seasonality, marketing activity, or product changes that may have driven differences between cohorts.
- "Active in period N" is a binary measure (any purchase vs. no purchase). It does not distinguish between a customer who placed one small order and one who placed many large orders.
