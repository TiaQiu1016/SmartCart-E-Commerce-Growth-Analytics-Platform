# LLM Insight Brief Validation

Generated: 2026-07-23 11:14 UTC
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
- Observational limitation is stated
- No customer_id field exposed in brief text
- Traceability / no-invention guardrail is stated

## Warnings for Human Review

- No warnings from automated validation.

## Required Human Review

- Confirm every cited number exists in `data/insight_inputs.json`.
- Confirm no observational result is described as causal.
- Confirm every segment has one data-backed action.
- Confirm API-generated wording is appropriate for final submission.
