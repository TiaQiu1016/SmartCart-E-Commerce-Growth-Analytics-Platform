# Customer Lifetime Value (CLV) Methodology

This note documents both CLV models in SmartCart: the baseline RFM-based estimate
(`src/segmentation_clv.py`) and the probabilistic BG/NBD + Gamma-Gamma enhancement
(`src/clv_bgnbd.py`). Both write to SQLite and appear side-by-side in the dashboard.

## 1. Baseline CLV

**Script:** `src/segmentation_clv.py` → SQLite table `clv`

### Formula

```
CLV = avg_order_value × annual_order_rate × recency_weight
```

Where:

- `avg_order_value` = total revenue / order count (floored at 1 to avoid division by zero)
- `annual_order_rate` = order count / observed years, **capped at the 95th percentile** across
  all customers. This prevents recently-acquired customers with only a few early purchases from
  projecting an implausibly high annualized rate.
- `observed_years` = days since first purchase / 365.25, **floored at 90 days** (`MIN_CLV_WINDOW_DAYS`).
  Without this floor, a customer with two purchases three days apart would show an annual rate
  of ~240 orders/year from two data points.
- `recency_weight` = `exp(-recency_days / 365.25)`. A customer who bought yesterday gets weight
  ≈ 1.0; one inactive for a full year gets weight ≈ 0.37. This discounts customers who are
  drifting toward churn without applying an arbitrary binary cutoff.

### Design decisions

| Decision | Rationale |
| --- | --- |
| 90-day minimum observation window | Prevents explosive rate estimates from short-tenure customers with few orders |
| 95th-percentile order rate cap | Limits outlier inflation while preserving variation across the bulk of the distribution |
| Exponential recency decay rather than binary churn flag | Continuous discount is more faithful to the data than an arbitrary "active/inactive" threshold |
| No discount rate | Consistent with the BG/NBD output; the estimate represents expected 12-month revenue, not present value |

### Limitations

- The formula is deterministic and symmetric: every customer with the same RFM profile gets the
  same CLV. It does not model the probability that a customer is still alive (i.e., has not
  permanently churned).
- The recency decay parameter (365.25 days) was chosen by inspection, not fitted to the data.
- The order rate cap (95th percentile) suppresses genuine high-frequency customers to avoid
  inflating population-level averages.

---

## 2. BG/NBD + Gamma-Gamma CLV

**Script:** `src/clv_bgnbd.py` → SQLite table `clv_bgnbd`

This model uses the `lifetimes` library to fit two probabilistic sub-models:

- **BG/NBD** (Beta-Geometric / Negative-Binomial Distribution): models the latent process by
  which each customer makes purchases (at some individual rate) and eventually "dies" (churns
  permanently). From each customer's purchase history it infers both their expected future
  transaction rate and their probability of still being alive.
- **Gamma-Gamma**: models expected monetary value per transaction, conditional on the customer
  being a repeat buyer. It assumes the average transaction value is gamma-distributed across
  customers and independent of purchase frequency.

### Time unit

The model runs at **weekly frequency** (`freq="W"`). Multiple orders placed in the same calendar
week are collapsed into one event. The prediction column `pred_active_purchase_weeks_12m` counts
expected active purchase weeks over 12 months, not strict order count. This is consistent with the
model's assumptions and is labeled clearly in the dashboard.

### One-time buyer monetary patch

`lifetimes` excludes the first purchase from its monetary calculation and sets `monetary_value=0`
for any customer with no repeat purchases. SmartCart patches this for the 1,708 one-time buyers
(29% of the customer base) by computing each customer's **invoice-level average order value**:
sum revenue within each invoice first, then average across invoices. Using the line-item mean
instead would underestimate order value by ~6x for customers with large multi-line baskets.

### Gamma-Gamma independence assumption

The Gamma-Gamma model requires that purchase frequency and average transaction value are
uncorrelated. Verified on this dataset: Pearson r(frequency, monetary_value) = 0.035 on repeat
customers, well within the acceptable range (|r| < 0.10).

### One-time buyer P(alive)

The BG/NBD model assigns `p_alive = 1.0` to every customer with no repeat purchases. This is not
a signal of genuine loyalty — it is a model artefact: without observing at least one gap between
purchases, BG/NBD has no evidence to estimate a churn probability and defaults to alive. These
customers are flagged `repeat_history = "insufficient"` in the output. Segment-level P(alive)
averages are inflated wherever one-time buyers are common (particularly Hibernating).

### Holdout validation

To validate the BG/NBD frequency predictions, the model is re-fitted on a calibration period
ending 6 months before the observation end date, then predicts the holdout period. Actual
purchase counts in the holdout are measured as **distinct active purchase weeks** (consistent
with the weekly frequency assumption).

| Metric | Value |
| --- | --- |
| Predicted mean purchase weeks | 1.496 |
| Actual mean purchase weeks | 1.486 |
| MAE | 1.013 |
| Pearson r (predicted vs. actual) | 0.799 |

The holdout validates purchase frequency only. Revenue per transaction (Gamma-Gamma output) is
not independently validated in this version.

### CLV computation

```
clv_bgnbd = pred_active_purchase_weeks_12m × exp_monetary_per_tx
```

Where `exp_monetary_per_tx` comes from the Gamma-Gamma model for repeat customers, and from the
patched invoice-level average order value for one-time buyers.

### Comparing baseline vs. BG/NBD

The two estimates measure different things and will not agree numerically:

| | Baseline CLV | BG/NBD CLV |
| --- | --- | --- |
| Unit | Expected annual revenue | Expected 12-month revenue (weekly events) |
| Alive probability | Implicit (recency decay) | Explicit (P(alive) per customer) |
| One-time buyers | Non-zero (recency decay applied) | Non-zero after monetary patch |
| Fitted to data | No (formula with fixed parameters) | Yes (MLE on transaction history) |

The BG/NBD estimate is preferred for individual customer ranking and targeting. The baseline
estimate is kept for transparency and as a sanity check.

### Limitations

- The 29% one-time buyer population has P(alive) = 1.0 by model design, inflating segment-level
  averages. Interpret P(alive) for repeat customers only.
- No discount rate is applied; `clv_bgnbd` is undiscounted expected 12-month revenue.
- The weekly frequency assumption collapses same-week orders. For retailers with very high
  intra-week order frequency this could underestimate transaction counts.
- Online Retail II is a wholesale dataset with more regular repurchase patterns than typical
  B2C retail; BG/NBD r and alpha parameters may differ substantially on a consumer-facing dataset.
