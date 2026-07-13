# SmartCart AI Insight Brief Draft

Generated: 2026-07-11 11:26 UTC

## Scope and Guardrails

This draft is generated from computed SmartCart outputs only. It does not invent metrics, recompute models, or make causal claims. A team member should verify the cited numbers before using the wording in the dashboard or final report.

## Executive Summary

- The highest-value segment is **Champions**, with average BG/NBD CLV of GBP 5,698 and average purchase propensity of 77.5%.
- The lowest-value segment is **Hibernating**, with average BG/NBD CLV of GBP 217 and average purchase propensity of 20.5%.
- Recommendations below are segment-specific and evidence-backed; they should be reviewed before being shown to retailers.

## Segment Actions

- **Champions:** Protect and grow with VIP retention, early access, and referral offers. Evidence: avg CLV GBP 5,698, purchase propensity 77.5%, BG/NBD p_alive 98.0%, insufficient repeat history 0.2%.
- **Recent / Promising:** Trigger a second-purchase campaign while recency is still strong. Evidence: avg CLV GBP 1,093, purchase propensity 49.3%, BG/NBD p_alive 96.7%, insufficient repeat history 19.2%.
- **At Risk High-Value:** Prioritize win-back messaging because past value is high but recent activity is weak. Evidence: avg CLV GBP 951, purchase propensity 41.7%, BG/NBD p_alive 84.0%, insufficient repeat history 1.9%.
- **Hibernating:** Use low-cost reactivation only; avoid heavy discount spend unless basket value improves. Evidence: avg CLV GBP 217, purchase propensity 20.5%, BG/NBD p_alive 91.6%, insufficient repeat history 69.6%.

## Group Comparison Signals

- Champions vs Hibernating on `recency_days`: Cohen's d = -2.358, p = 0.0000. Interpret this as observational evidence, not a causal effect.
- Champions vs Hibernating on `frequency`: Cohen's d = 1.269, p = 0.0000. Interpret this as observational evidence, not a causal effect.
- Champions vs Hibernating on `clv_estimate`: Cohen's d = 0.730, p = 0.0000. Interpret this as observational evidence, not a causal effect.
- Champions vs Hibernating on `monetary`: Cohen's d = 0.591, p = 0.0000. Interpret this as observational evidence, not a causal effect.
- UK vs Non-UK on `clv_estimate`: Cohen's d = -0.222, p = 0.0000. Interpret this as observational evidence, not a causal effect.

## Predictive Churn Signals

- **Hibernating**: observed future churn rate 99.7% across 388 evaluated customers; average predicted churn probability 77.8%.
- **At Risk High-Value**: observed future churn rate 68.2% across 302 evaluated customers; average predicted churn probability 53.8%.
- **Champions**: observed future churn rate 2.3% across 216 evaluated customers; average predicted churn probability 20.2%.
- **Recent / Promising**: observed future churn rate 0.0% across 151 evaluated customers; average predicted churn probability 58.7%.
- Interpret this as a model-output diagnostic. A fully leakage-free segment validation still needs segment labels created at the same feature cutoff as the churn model.

## Product Recommendation Signals

- When customers buy **GREEN REGENCY TEACUP AND SAUCER**, consider recommending **ROSES REGENCY TEACUP AND SAUCER** (confidence 79.8%, lift 25.37).
- When customers buy **ROSES REGENCY TEACUP AND SAUCER**, consider recommending **GREEN REGENCY TEACUP AND SAUCER** (confidence 70.7%, lift 25.37).
- When customers buy **ALARM CLOCK BAKELIKE GREEN**, consider recommending **ALARM CLOCK BAKELIKE RED** (confidence 67.8%, lift 20.08).
- When customers buy **ALARM CLOCK BAKELIKE RED**, consider recommending **ALARM CLOCK BAKELIKE GREEN** (confidence 61.4%, lift 20.08).
- When customers buy **CHARLOTTE BAG PINK POLKADOT**, consider recommending **RED RETROSPOT CHARLOTTE BAG** (confidence 63.4%, lift 14.39).

## Missing Inputs and Limitations

- No unavailable modules were reported in the structured input.
- Statistical group comparisons are observational. They should guide business review, not be presented as randomized treatment effects.

## Human Review Checklist

- Confirm every number against `data/insight_inputs.json`.
- Keep at least one data-backed action for every segment.
- Preserve limitations when moving this draft into the dashboard.
- Do not expose customer-level identifiers in the final brief.
