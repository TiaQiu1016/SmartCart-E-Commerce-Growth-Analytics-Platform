# Dashboard Review for Stage 3

## Review Scope

Reviewed the current Streamlit dashboard files under `dashboard/` after the
Stage 2 analytics modules were merged into `main`. This review focuses on
readiness for Stage 3 integration, not visual polish.

## Current Dashboard Coverage

| Page | Status | Notes |
| --- | --- | --- |
| Overview | Working structure | Shows core KPIs, segment count, revenue distribution, and segment summary. |
| Data Setup | Available | Supports config-driven data upload and validation. |
| Segmentation | Strong coverage | Includes K-Means segments, baseline CLV, BG/NBD CLV, P(alive), and segment actions. |
| Propensity | Working structure | Shows score distribution, segment score differences, campaign threshold planner, and top customers. |
| Market Basket | Strong coverage | Includes top rules, product lookup, rule explorer, and plain-language metric explanations. |
| Group Insights | Working structure | Shows UK vs. non-UK, Champions vs. Hibernating, and segment summaries with effect sizes. |
| Churn | Missing | Needs a page built on top of the new `churn_scores` table. |
| AI Insight Brief | Missing | Needs a page or section that displays `reports/ai_insight_brief_draft.md` or a generated brief artifact. |

## Validation Completed

- Ran Python syntax checks on all dashboard pages and shared dashboard utilities.
- Confirmed dashboard utility loaders include core tables such as `segments`,
  `clv`, `clv_bgnbd`, `propensity_scores`, market-basket outputs, and group
  comparison outputs.
- Confirmed the dashboard is currently blocked from a churn page only because
  the required `churn_scores` output was missing before this update.

## Issues and Follow-ups

1. **Churn page is the main missing dashboard page.** It should use
   `churn_scores` after `src/churn_model.py` is run. Recommended views:
   score distribution, actual churn rate by segment, predicted churn probability
   by segment, test-set-only validation KPIs, and a table of high-risk customers.
2. **AI brief is not yet displayed in the dashboard.** The deterministic draft
   is generated at `reports/ai_insight_brief_draft.md`. A later page can read
   and display this file, then replace it with an LLM-generated version once the
   team finalizes the guardrails.
3. **Group Insights should keep the circularity caveat visible.** Current
   recency-based churn snapshots are descriptive. Final V2 should use
   `churn_scores` and, ideally, `segments_at_cutoff`.
4. **Overview KPIs still use baseline CLV.** This is acceptable for now, but the
   dashboard should eventually clarify whether a KPI uses baseline CLV or
   BG/NBD CLV.

## Recommended Next Dashboard Work

1. Add a `5_Churn.py` page using `churn_scores`.
2. Add a lightweight `6_AI_Brief.py` page to display the generated brief draft.
3. Update Overview to mention whether displayed CLV is baseline or BG/NBD.
4. Add missing-table handling in dashboard utilities so the app fails with a
   friendly message when a module has not been run yet.
