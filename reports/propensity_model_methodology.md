# Purchase-Propensity Model — Methodology

This note documents `src/propensity_model.py` in enough detail for someone who
did not build it (specifically the cross-validation tuning process) to
understand what was done and why, and to defend the results if asked.

## Problem framing

Predict whether a customer will make at least one purchase in the **30 days**
after a cutoff date. This is deliberately a shorter, more action-oriented
horizon than the churn model's 90-day window: churn answers "who are we about
to lose," propensity answers "who should we target in a campaign right now."

## Leakage-free design

Same time-split principle as `churn_model.py`: the cutoff is set 30 days
before the latest transaction date in the data. All features are computed
only from transactions on or before the cutoff. The label (`will_purchase`)
is whether the customer bought anything *after* the cutoff. No information
from the label window leaks into the features.

## Features

Standard RFM (`recency_days`, `frequency`, `monetary`, `tenure_days`,
`avg_basket_size`) plus three purchase-rhythm features unique to this model:

- `avg_days_between_orders` — mean gap between a customer's invoices
- `purchase_regularity` — coefficient of variation of those gaps (lower =
  more regular buyer)
- `recency_ratio` — `recency_days / avg_days_between_orders`; below 1 means
  the customer is "due" to buy again relative to their own rhythm

Customers with only one purchase have no gap statistics; these are filled
with the population median rather than dropped, since single-purchase
customers are a real and common segment, not missing data.

## Models and tuning

Two models: logistic regression (baseline) and XGBoost. Both are tuned via
**stratified 5-fold cross-validation** on the training set only (the test
set is never touched during tuning):

- **Logistic regression**: `GridSearchCV` over the regularization strength
  `C` (7 values).
- **XGBoost**: `RandomizedSearchCV`, sampling 40 combinations from a
  9-parameter grid (tree depth, learning rate, subsampling, regularization
  terms, etc.).

### Why tuning mattered here

An earlier, untuned version of this model used hardcoded XGBoost defaults
(`max_depth=4`, no explicit regularization) and scored **0.762 test AUC**,
*below* the untuned logistic regression baseline (**0.781**). That ordering
is a red flag: gradient-boosted trees should not lose to plain logistic
regression on a tabular problem like this unless something is misconfigured.

The cross-validated search found `max_depth=2` and `reg_lambda=2.0` (much
shallower and more regularized than the hardcoded defaults), which raised
XGBoost to **0.787 test AUC**, now ahead of logistic regression (which stayed
at 0.781 — the grid search confirmed `C=1`, sklearn's default, was already
near-optimal for this data). The conclusion: the original ranking was an
artifact of overfitting on a moderate-sized training set (~4,500 rows), not a
genuine result about which model family is better suited to this problem.

## Evaluation

- **Test AUC** is the only number that should be trusted for "how good is
  this model" — it's computed on the 20% held-out split that never
  participated in training or hyperparameter search. The CV AUC printed
  alongside it is a tuning diagnostic, not the final answer.
- **Cumulative gain / lift chart** (`propensity_gain_chart.png`): ranks test
  customers by predicted score and measures what fraction of actual buyers
  are captured at different targeting depths. Key numbers:
  - Top 10% of customers by score → captures 28.9% of actual buyers (2.9x lift)
  - Top 20% → captures 47.0% (2.3x lift)
  - Top 30% → captures 59.7% (2.0x lift)

  This is the metric that translates directly into a marketing decision:
  contacting the model's top-ranked 20% of customers reaches more than double
  the real buyers a random 20% sample would.

- **Precision-recall curve and campaign-budget operating points**
  (`propensity_precision_recall.png`): converts the ranked score list into
  concrete score thresholds for realistic budget levels:

  | Contact top | Score threshold | Precision | Recall |
  | --- | --- | --- | --- |
  | 10% | ≥ 0.801 | 75.4% | 28.9% |
  | 15% | ≥ 0.736 | 69.0% | 39.6% |
  | 20% | ≥ 0.675 | 61.4% | 47.0% |
  | 25% | ≥ 0.622 | 55.9% | 53.7% |
  | 30% | ≥ 0.576 | 51.9% | 59.7% |

  Read the 15% row as: "if we can only afford to contact 15% of customers,
  flag anyone with a propensity score of 0.736 or higher; about 69% of the
  people we contact will actually buy, and we'll have reached 40% of everyone
  who was going to buy." This is the threshold a production system would
  hardcode, rather than always recomputing "top 15%" at runtime.

- **SHAP feature attribution** (`propensity_shap_summary.png`): more reliable
  than XGBoost's built-in `feature_importances_`, and shows direction, not
  just magnitude. Confirms the intuitive story: low `recency_days` (bought
  recently) and short `avg_days_between_orders` (frequent rebuyer) push
  propensity up; high `frequency` and `avg_basket_size` also push it up.
  `recency_ratio` behaves as designed — low values (customer is "due" to buy
  relative to their own rhythm) push propensity up.

## Limitations

- Test set is ~1,144 customers; AUC and lift numbers carry some sampling
  variance and would shift slightly under a different random seed or a
  different cutoff date.
- Online Retail II is a wholesale dataset (gift shops and small retailers
  reordering stock), which likely has more regular, predictable repurchase
  rhythms than typical B2C retail. The strong performance of the rhythm
  features (`avg_days_between_orders`, `recency_ratio`) may not transfer
  as cleanly to a consumer-facing retailer with less regular buying patterns.
- No external signal (marketing exposure, browsing behavior, seasonality
  beyond what's implicit in the transaction dates) is available — only
  transactional history. A production system with those signals would likely
  improve further on this baseline.
