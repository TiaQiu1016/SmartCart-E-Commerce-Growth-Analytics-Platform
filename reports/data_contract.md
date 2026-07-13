# SmartCart — Data Contract

This document pins the single customer identifier, the schema of every SQLite
table, and the join QA results confirming all modules agree on customer coverage.

---

## Single Customer Identifier

**`customer_id` — integer, sourced from `Customer ID` in Online Retail II.**

Every customer-level table in `smartcart.db` uses `customer_id` as its primary key.
No module uses any other identifier. All cross-module joins are performed on this
column exclusively.

---

## Database: `data/smartcart.db`

Tables fall into two categories: **customer-level** (one row per customer, joinable
on `customer_id`) and **aggregate/rule** (no customer key; produced by summarising
across customers or invoices).

### Customer-Level Tables

| Table | Rows | Distinct customers | Source script |
| --- | --- | --- | --- |
| `transactions` | 805,549 | 5,878 | `src/build_database.py` |
| `rfm` | 5,878 | 5,878 | `sql/rfm.sql` |
| `segments` | 5,878 | 5,878 | `src/segmentation_clv.py` |
| `clv` | 5,878 | 5,878 | `src/segmentation_clv.py` |
| `clv_bgnbd` | 5,878 | 5,878 | `src/clv_bgnbd.py` |
| `propensity_scores` | 5,717 | 5,717 | `src/propensity_model.py` |
| `churn_scores` | 5,281 | 5,281 | `src/churn_model.py` |
| `segments_at_cutoff` | 5,281 | 5,281 | `src/segments_at_cutoff.py` |

**Note on propensity_scores:** 161 customers are absent from `propensity_scores`
because they had no transaction history before the model cutoff date and therefore
could not be assigned features. This is expected by design — the propensity model
requires a pre-cutoff observation window, and customers who only appear after the
cutoff cannot be scored. They are present in all other tables.

**Note on churn_scores:** 597 customers are absent from `churn_scores` because
the churn model only scores customers with usable pre-cutoff transaction history.
This is expected by design. The churn table includes `is_test_set` so downstream
validation can report held-out customers separately from the full scored set.

### Aggregate and Rule Tables

These tables have no `customer_id` column and are not joined to customer-level outputs.

| Table | Rows | Key columns | Source script |
| --- | --- | --- | --- |
| `segmentation_metrics` | 5 | `k` | `src/segmentation_clv.py` |
| `segment_profiles` | 4 | `segment` | `src/segmentation_clv.py` |
| `segment_comparison_summary` | 4 | `segment` | `src/group_comparison.py` |
| `group_comparison_results` | 18 | `comparison`, `metric` | `src/group_comparison.py` |
| `association_rules` | 68 | `antecedents`, `consequents` | `src/market_basket.py` |
| `product_recommendations` | 35 | `stock_code` | `src/market_basket.py` |
| `cohort_retention` | 325 | `cohort_month`, `period` | `src/cohort_analysis.py` |
| `cohort_revenue` | 325 | `cohort_month`, `period` | `src/cohort_analysis.py` |
| `segment_churn_v2_summary` | 8 | `segment`, `validation_scope` | `src/segments_at_cutoff.py` |
| `segment_churn_v2_results` | 2 | `comparison`, `test_type` | `src/segments_at_cutoff.py` |

---

## Column Schemas — Customer-Level Tables

### `transactions`
| Column | Type | Notes |
| --- | --- | --- |
| `customer_id` | INTEGER | Foreign key to all customer-level tables |
| `invoice` | TEXT | Invoice identifier |
| `stock_code` | TEXT | Product code |
| `description` | TEXT | Product description |
| `quantity` | INTEGER | Units ordered |
| `invoice_date` | TEXT | ISO datetime string (`YYYY-MM-DD HH:MM:SS`) |
| `price` | REAL | Unit price |
| `country` | TEXT | Customer country |
| `revenue` | REAL | `quantity × price` |

### `rfm`
| Column | Type | Notes |
| --- | --- | --- |
| `customer_id` | INTEGER | Primary key |
| `recency_days` | REAL | Days since last purchase (at observation end) |
| `frequency` | REAL | Number of distinct invoices |
| `monetary` | REAL | Total revenue |

### `segments`
| Column | Type | Notes |
| --- | --- | --- |
| `customer_id` | INTEGER | Primary key |
| `recency_days` | REAL | |
| `frequency` | REAL | |
| `monetary` | REAL | |
| `cluster` | INTEGER | K-Means cluster index (0-based) |
| `segment` | TEXT | Human-readable label (Champions, Recent / Promising, At Risk High-Value, Hibernating) |
| `recommended_action` | TEXT | One data-backed action per segment |

### `clv`
| Column | Type | Notes |
| --- | --- | --- |
| `customer_id` | INTEGER | Primary key |
| `avg_order_value` | REAL | Total revenue / order count |
| `annual_order_rate` | REAL | Orders per year, capped at 95th percentile |
| `annual_order_rate_raw` | REAL | Uncapped rate (for reference) |
| `observed_days` | REAL | Days since first purchase, floored at 90 |
| `recency_weight` | REAL | `exp(-recency_days / 365.25)` |
| `frequency` | REAL | |
| `monetary` | REAL | |
| `clv_estimate` | REAL | Baseline CLV = `avg_order_value × annual_order_rate × recency_weight` |

### `clv_bgnbd`
| Column | Type | Notes |
| --- | --- | --- |
| `customer_id` | INTEGER | Primary key |
| `segment` | TEXT | Joined from `segments` |
| `frequency` | REAL | Repeat purchases (lifetimes definition: total orders − 1) |
| `recency` | REAL | Weeks between first and last purchase |
| `T` | REAL | Weeks since first purchase (observation age) |
| `monetary_value` | REAL | Avg order value (patched for one-time buyers) |
| `pred_active_purchase_weeks_12m` | REAL | BG/NBD predicted active purchase weeks over 12 months |
| `p_alive` | REAL | Probability customer has not permanently churned |
| `repeat_history` | TEXT | `"yes"` or `"insufficient"` (one-time buyers) |
| `exp_monetary_per_tx` | REAL | Gamma-Gamma expected revenue per transaction |
| `clv_bgnbd` | REAL | `pred_active_purchase_weeks_12m × exp_monetary_per_tx` |
| `clv_baseline` | REAL | Joined from `clv.clv_estimate` for comparison |
| `avg_order_value` | REAL | Joined from `clv` |

### `propensity_scores`
| Column | Type | Notes |
| --- | --- | --- |
| `customer_id` | INTEGER | Primary key (5,717 of 5,878 customers — see note above) |
| `propensity_score` | REAL | XGBoost predicted probability of purchase in next 30 days (0–1) |

### `churn_scores`
| Column | Type | Notes |
| --- | --- | --- |
| `customer_id` | INTEGER | Primary key for scored customers |
| `feature_cutoff_date` | TEXT | Last date allowed for feature construction |
| `label_window_days` | INTEGER | Future outcome window length; currently 90 days |
| `actual_churn_label` | INTEGER | 1 if no purchase occurred in the post-cutoff label window, else 0 |
| `predicted_churn_probability` | REAL | XGBoost predicted probability of churn |
| `baseline_logistic_churn_probability` | REAL | Logistic regression baseline probability |
| `is_test_set` | INTEGER | 1 for held-out validation rows, 0 for training rows |
| `model_name` | TEXT | Model used for the primary prediction, currently `xgboost` |

### `segments_at_cutoff`
| Column | Type | Notes |
| --- | --- | --- |
| `customer_id` | INTEGER | Primary key for customers with pre-cutoff history |
| `recency_days` | REAL | Days since last pre-cutoff purchase |
| `frequency` | REAL | Distinct invoices on or before the cutoff |
| `monetary` | REAL | Revenue on or before the cutoff |
| `cluster` | INTEGER | K-Means cluster assigned from pre-cutoff RFM |
| `segment` | TEXT | Human-readable historical segment label |
| `recommended_action` | TEXT | Action attached to the historical segment |
| `feature_cutoff_date` | TEXT | Cutoff matching `churn_scores.feature_cutoff_date` |
| `label_window_days` | INTEGER | Future churn label window, currently 90 days |

---

## Join QA Results

Verified on `data/smartcart.db` as of Jul 12, 2026:

| Join | Result |
| --- | --- |
| `segments` → `rfm` on `customer_id` | 5,878 / 5,878 match (100%) |
| `segments` → `clv` on `customer_id` | 5,878 / 5,878 match (100%) |
| `segments` → `clv_bgnbd` on `customer_id` | 5,878 / 5,878 match (100%) |
| `segments` → `propensity_scores` on `customer_id` | 5,717 / 5,878 match (97.3%) — 161 unscored by design |
| `segments` → `churn_scores` on `customer_id` | 5,281 / 5,878 match (89.8%) — 597 unscored by churn cutoff design |
| `churn_scores` → `segments_at_cutoff` on `customer_id` | 5,281 / 5,281 match (100%) |
| Orphan `customer_id` in any table not in `transactions` | 0 |

All customer-level modules use the same 5,878 integer customer IDs derived from
`build_database.py`. No module introduces a surrogate key or alternative identifier.

---

## Data Lineage

```
online_retail_II.csv
    └── build_database.py
            ├── transactions       (raw grain)
            └── rfm                (SQL aggregation via sql/rfm.sql)
                    ├── segmentation_clv.py
                    │       ├── segments
                    │       ├── clv
                    │       ├── segment_profiles
                    │       └── segmentation_metrics
                    ├── clv_bgnbd.py
                    │       └── clv_bgnbd          (joins segments + clv)
                    ├── churn_model.py             (leakage-free time split)
                    │       └── churn_scores       (customer-level labels + model probabilities)
                    ├── segments_at_cutoff.py
                    │       ├── segments_at_cutoff
                    │       ├── segment_churn_v2_summary
                    │       └── segment_churn_v2_results
                    ├── propensity_model.py        (leakage-free time split)
                    │       └── propensity_scores
                    ├── market_basket.py
                    │       ├── association_rules
                    │       └── product_recommendations
                    ├── group_comparison.py
                    │       ├── group_comparison_results
                    │       └── segment_comparison_summary
                    └── cohort_analysis.py
                            ├── cohort_retention
                            └── cohort_revenue
```

Generated AI artifacts sit outside the SQLite contract:

- `data/insight_inputs.json` is a local JSON generated by
  `src/prepare_insight_inputs.py` from computed SQLite outputs.
- `reports/ai_insight_brief_draft.md` is a reviewable Markdown draft generated
  by `src/generate_insight_brief.py`.

These files must not introduce new metrics or alternate customer identifiers.
They only summarize existing computed outputs.

---

## Conventions

- **Date format:** all `invoice_date` values are stored as `TEXT` in `YYYY-MM-DD HH:MM:SS`
  format. Parse with `pd.to_datetime()` or `datetime.strptime`.
- **Currency:** all monetary values are in GBP (£). Configurable via `config.yaml`
  `company.currency_symbol` for other retailers.
- **Null handling:** `customer_id` is never null in any table (enforced in
  `build_database.py`). All other nullable columns are documented per-table above.
- **Column naming:** internal column names follow `snake_case`. Original Online Retail II
  column names (e.g. `Customer ID`, `InvoiceDate`) are mapped via `config.yaml` and
  renamed on ingest.
