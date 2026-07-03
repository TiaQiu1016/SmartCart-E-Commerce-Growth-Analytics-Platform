# Customer-Group Comparison Methodology

This note documents `src/group_comparison.py`, the Version 1 customer-group
comparison module for SmartCart.

## Purpose

The goal is to test whether important customer groups differ in behavior and
value, then provide dashboard/report-ready evidence for segment-level business
recommendations. This is an observational comparison of historical customers,
not a randomized A/B experiment.

## Groups Compared

Version 1 focuses on groups that are easy to explain and already supported by
the current SQLite outputs:

- **UK vs Non-UK customers**: geography-based comparison aligned with the
  proposal's customer-group comparison scope.
- **Champions vs Hibernating**: key K-Means segment comparison, chosen because
  these represent the clearest high-value vs low-value behavioral contrast.
- **All K-Means segments summary**: descriptive dashboard-ready profile across
  every segment.

## Metrics

Numeric metrics:

- `recency_days`
- `frequency`
- `monetary`
- `clv_estimate`

Categorical metric:

- `churned_snapshot`: a descriptive 90-day inactivity flag, defined as
  `recency_days > 90`.

The churn flag here is a descriptive snapshot, not the leakage-free predictive
churn model output from `src/churn_model.py`.

## Statistical Tests

For numeric two-group comparisons, the module reports:

- **Welch t-test**: compares group means without assuming equal variance.
- **Mann-Whitney U test**: non-parametric robustness check for skewed metrics
  such as monetary value and CLV.
- **Cohen's d**: effect size for the magnitude of the difference between two
  groups.

For categorical churn comparisons, the module reports:

- **Chi-square test**: tests whether churned vs active proportions differ by
  group.
- **Cramer's V**: effect size for the strength of categorical association.

## Outputs

SQLite tables:

- `group_comparison_results`: test results, p-values, and effect sizes.
- `segment_comparison_summary`: segment-level customer counts, average RFM,
  average CLV, snapshot churn rate, and UK share.

Figures:

- `reports/figures/group_clv_by_segment.png`
- `reports/figures/uk_nonuk_clv_comparison.png`
- `reports/figures/segment_churn_rate.png`

## Limitations

- These comparisons are observational; they identify differences, not causal
  treatment effects.
- Large sample sizes can make small differences statistically significant, so
  effect sizes should be interpreted alongside p-values.
- The segment-versus-churn snapshot association is partly circular because
  `recency_days` contributes to both K-Means segmentation and the definition of
  `churned_snapshot`. This result is descriptive and should not be interpreted
  as independent evidence that segment membership predicts or causes churn.
- Version 1 does not include model-predicted churn risk or purchase propensity
  scores. Those can be added later once the dashboard data contract is final.
- No multiple-testing correction is applied in Version 1 because the module
  keeps the tested comparisons deliberately narrow.
