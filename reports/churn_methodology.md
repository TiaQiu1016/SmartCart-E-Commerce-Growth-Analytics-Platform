# Churn Prediction Model — Methodology

This note documents `src/churn_model.py`: the design rationale, features, models, and results.

## Problem Framing

The churn model predicts whether a customer will make no purchase in the next 90 days. A customer is labelled churned = 1 if they did not transact at all in the 90-day window after a fixed cutoff date, and churned = 0 if they did.

Of 5,281 customers active before the cutoff, 56.6% are labelled churned. The high base rate reflects the wholesale nature of the dataset: many small retailers order seasonally and naturally go quiet for months at a time.

## Leakage-Free Time Split

The most important design constraint is avoiding label leakage. Defining churn as "no purchase in the last 90 days" and then using recency as a feature would mean the feature directly encodes the label, producing inflated performance numbers that would not hold on new data.

SmartCart uses a strict time split instead:

- **Cutoff date:** 90 days before the last transaction in the dataset (2011-09-10).
- **Features:** computed from transactions on or before the cutoff only.
- **Label:** whether the customer made any purchase in the 90 days after the cutoff.

No information from the label window touches the features. This mirrors exactly how churn prediction would run in production.

## Features

Five features are derived from each customer's pre-cutoff transaction history:

| Feature | Description |
| --- | --- |
| `recency_days` | Days between the customer's last pre-cutoff purchase and the cutoff date |
| `frequency` | Number of distinct invoices before the cutoff |
| `monetary` | Total revenue before the cutoff |
| `tenure_days` | Days between the customer's first and last pre-cutoff purchase |
| `avg_basket_size` | Mean number of distinct products per invoice |

Features are standardized (zero mean, unit variance) before logistic regression; XGBoost uses the raw values directly.

## Models

Two models are trained on an 80/20 stratified split (test set: 1,057 customers):

- **Logistic Regression** — regularized baseline with `class_weight="balanced"` to account for the 56.6% churn base rate.
- **XGBoost** — gradient-boosted trees (`n_estimators=300`, `max_depth=4`, `learning_rate=0.1`, `subsample=0.9`, `colsample_bytree=0.9`).

XGBoost achieves **test AUC 0.802**, which is the reported model performance. This is computed on the held-out test set only; the training set never influences this number. XGBoost is selected as the production model; logistic regression is retained as a baseline for comparison.

Customer-level churn probabilities for both models are written to the `churn_scores` SQLite table. The dashboard Churn Risk page uses the XGBoost probability and buckets customers into three risk bands: High (≥ 75%), Medium (50–75%), and Low (< 50%).

## Feature Importance

XGBoost's built-in gain-based feature importance (see `reports/figures/churn_feature_importance.png`) consistently ranks recency as the dominant predictor, followed by frequency and tenure. This is intuitive: a customer who purchased recently and regularly is unlikely to churn; one who has been silent for months relative to their usual rhythm is at high risk.

## Limitations

- The test set covers 1,057 customers. AUC and risk-band proportions carry sampling variance and would shift under a different random seed or cutoff date.
- Only transactional features are used. External signals — marketing exposure, web browse behavior, promotional calendar — are unavailable in this dataset and would improve performance in a production system.
- Online Retail II is a wholesale dataset with more regular repurchase patterns than typical consumer retail. The model's churn rate and feature weights may not transfer directly to a B2C retailer where buying behavior is more irregular.
- The 56.6% base churn rate is partly a data artifact: the 90-day label window falls near the end of the dataset, so customers who simply had not yet repurchased by the data cutoff are labelled churned even if they were still active buyers.
