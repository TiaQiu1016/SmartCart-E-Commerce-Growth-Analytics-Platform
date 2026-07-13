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
| Cohort Retention | V1 available | Shows cohort retention heatmap, retention curves, and revenue per customer by acquisition cohort. |
| Churn | V1 available | Uses `churn_scores` for score distribution, segment churn diagnostics, and a high-risk customer list. |
| AI Insight Brief | V1 available | Displays `reports/ai_insight_brief_draft.md`, structured input status, and generation guardrails. |

## Validation Completed

- Ran Python syntax checks on all dashboard pages and shared dashboard utilities.
- Confirmed dashboard utility loaders include core tables such as `segments`,
  `clv`, `clv_bgnbd`, `propensity_scores`, market-basket outputs, and group
  comparison outputs, plus cohort and churn outputs after the merge.
- Confirmed the dashboard is currently blocked from a churn page only because
  the required `churn_scores` output was missing before this update.

## Issues and Follow-ups

1. **Churn page V1 is available.** It uses `churn_scores` after
   `src/churn_model.py` is run. The remaining improvement is to replace current
   segment joins with `segments_at_cutoff` once that table exists.
2. **AI brief page V1 is available.** It displays the deterministic draft at
   `reports/ai_insight_brief_draft.md` and the structured input status from
   `data/insight_inputs.json`. A later version can replace the deterministic
   draft with an LLM-generated version once the team finalizes the prompt and
   guardrails.
3. **Group Insights should keep the circularity caveat visible.** Current
   recency-based churn snapshots are descriptive. Final V2 should use
   `churn_scores` and, ideally, `segments_at_cutoff`.
4. **Overview KPIs still use baseline CLV.** This is acceptable for now, but the
   dashboard should eventually clarify whether a KPI uses baseline CLV or
   BG/NBD CLV.

## Recommended Next Dashboard Work

1. Update Overview to mention whether displayed CLV is baseline or BG/NBD.
2. Add missing-table handling in dashboard utilities so the app fails with a
   friendly message when a module has not been run yet.
3. Add `segments_at_cutoff` and update the Churn page once final V2 validation
   is ready.
