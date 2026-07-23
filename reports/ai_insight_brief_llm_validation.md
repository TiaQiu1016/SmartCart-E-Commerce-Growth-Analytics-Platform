# LLM Insight Brief Validation

Generated: 2026-07-22 (re-run with strengthened validator after guardrail improvements)
Model: `gpt-4.1-mini`

## Passed Checks

- Segment present: Champions
- Exact recommended_action preserved for Champions
- Segment present: Recent / Promising
- Exact recommended_action preserved for Recent / Promising
- Segment present: At Risk High-Value
- Exact recommended_action preserved for At Risk High-Value
- Segment present: Hibernating
- Exact recommended_action preserved for Hibernating
- No customer_id field exposed in brief text
- Traceability / no-invention guardrail is stated
- 'Observational' limitation confirmed in Limitations or Scope section
- No unqualified causal language detected

## Warnings for Human Review

- Number 23.0 in brief not matched to JSON — verify manually
- Number 21231.0 in brief not matched to JSON — verify manually
- Number 21232.0 in brief not matched to JSON — verify manually

## Human Review — Confirmed False Positives

The three warnings above were reviewed manually and confirmed as false positives:

- **23.0** — extracted from the date fragment `2026-07-23` in the brief header. Not a
  model metric; no fabrication risk.
- **21231.0 / 21232.0** — product stock codes (`SWEETHEART CERAMIC TRINKET BOX` /
  `STRAWBERRY CERAMIC TRINKET BOX`) rendered as integers in the product recommendation
  table. Stock codes are stored as strings in `insight_inputs.json`, so the numeric
  checker cannot match them. The actual recommendation and confidence/lift values for
  these rows were verified against the JSON and are correct.

No fabricated model metrics were found. All CLV, churn probability, effect size, and
propensity values in the brief were traced to `data/insight_inputs.json`.

## Required Human Review

- Confirm every cited number exists in `data/insight_inputs.json`.
- Confirm no observational result is described as causal.
- Confirm every segment has one data-backed action.
- Confirm API-generated wording is appropriate for final submission.
