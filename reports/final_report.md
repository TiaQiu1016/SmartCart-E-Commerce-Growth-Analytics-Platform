# SmartCart Final Report

## Technical Summary

SmartCart is an open-source e-commerce growth analytics platform for small and mid-sized online retailers that currently rely on spreadsheets or no analytics process. Using a retailer transaction export, SmartCart builds customer segments, baseline and probabilistic CLV, churn risk, 30-day purchase likelihood, product recommendations, cohort retention views, statistical group comparisons, and a reviewed AI insight brief.

The final pipeline is reproducible from Online Retail II: 805,549 cleaned transactions, 36,969 invoices, 4,631 products, and 5,878 customers. SQLite is the single source of truth, and all customer-level modules use the same integer `customer_id` key. The Streamlit dashboard is the delivery layer for non-technical users, while `config.yaml` controls retailer-specific values such as currency, dataset label, and churn risk thresholds.

The main technical risks raised during proposal and progress-report feedback were addressed. RFM normalization is pinned before K-Means, churn and propensity models use strict feature-window / label-window splits, segment-level churn validation uses pre-cutoff segment membership instead of full-period segments, and the AI brief requires traceable numbers, one action per segment, no unsupported causal language, and human approval before publication.

## Problem and Audience

Small and mid-sized online retailers often have useful transaction data but lack the budget, time, and technical staff needed to turn it into growth decisions. Enterprise platforms can support this work, but the realistic alternative for the long-tail retailer is usually a spreadsheet or no customer analytics system at all.

SmartCart targets that gap. It is designed to answer practical questions a retailer can act on:

- Which customer groups should we protect, grow, or win back?
- Which customers are most likely to churn or buy again soon?
- Which products should be bundled or recommended together?
- How is customer retention changing by acquisition month?
- What are the most important data-backed actions this week?

The project goal is therefore not just to build models. It is to convert transaction history into a retailer-facing operating tool.

## Data Foundation and System Design

SmartCart uses Online Retail II as the primary dataset. The raw dataset is cleaned into 805,549 usable transaction rows after removing returns, invalid prices, and rows without customer identifiers. The final cleaned data covers 5,878 customers, 36,969 invoices, and GBP 17.7M in revenue.

SQLite is used as the shared analytics layer. The `data_contract.md` file pins `customer_id` as the single customer identifier and documents table schemas and join checks. Core customer-level tables include `rfm`, `segments`, `clv`, `clv_bgnbd`, `propensity_scores`, `churn_scores`, and `segments_at_cutoff`. Aggregate outputs include segmentation metrics, product association rules, cohort retention, group comparison results, and segment-level churn validation summaries.

This design directly reduces module drift. Every module reads from or writes to the same database contract, and downstream dashboard pages use those tables rather than separate ad hoc notebook outputs.

## Customer Segmentation Produces Four Actionable Groups

SmartCart groups customers using RFM features: recency, frequency, and monetary value. Because these variables have different scales and skewed distributions, the pipeline applies `log1p` transformations and then `StandardScaler` before fitting K-Means. This locks down the RFM normalization choice requested in proposal feedback.

K-Means was tested for k = 4 through k = 8. The selected k = 4 solution has the strongest silhouette score among the tested options: 0.363 versus 0.336 for k = 5, 0.333 for k = 6, 0.305 for k = 7, and 0.309 for k = 8. The four clusters are translated into retailer-readable segments:

| Segment | Customers | Avg recency | Avg orders | Avg revenue |
| --- | ---: | ---: | ---: | ---: |
| Hibernating | 2,077 | 390 days | 1.42 | GBP 349 |
| At Risk High-Value | 1,503 | 205 days | 5.48 | GBP 2,179 |
| Recent / Promising | 1,211 | 27 days | 3.04 | GBP 858 |
| Champions | 1,087 | 24 days | 20.34 | GBP 11,687 |

Each segment carries one recommended action. This enforces the project rule that analytics must become advice, not just a profile table. Champions should receive VIP retention and growth offers; Recent / Promising customers should receive second-purchase nudges; At Risk High-Value customers should receive win-back messaging; Hibernating customers should receive low-cost reactivation rather than expensive incentives.

The segmentation limitation is that K-Means is descriptive and distance-based. Segment names are human interpretations of cluster profiles, not externally observed truths. For predictive churn validation, SmartCart therefore uses `segments_at_cutoff`, not the full-period segment table.

## CLV Supports Spend Prioritization

SmartCart includes two CLV layers. The baseline CLV is transparent: average order value multiplied by annualized order rate and a recency weight. The short-tenure inflation issue identified during review is addressed by flooring the observation window at 90 days and capping annualized order rate at the 95th percentile.

The enhanced CLV layer uses BG/NBD for future purchase activity and Gamma-Gamma for expected monetary value. Segment-level BG/NBD averages show a clear value gradient:

| Segment | Avg BG/NBD CLV | Avg p_alive | Predicted active purchase weeks, 12m |
| --- | ---: | ---: | ---: |
| Champions | GBP 5,698 | 0.981 | 8.19 |
| Recent / Promising | GBP 1,093 | 0.967 | 3.22 |
| At Risk High-Value | GBP 951 | 0.840 | 2.27 |
| Hibernating | GBP 217 | 0.916 | 0.76 |

The main caveat is that BG/NBD has limited information for one-time buyers. For customers without repeat-purchase history, `p_alive` can look deceptively high because the model has little evidence to estimate permanent inactivity. For this reason, the report and dashboard interpret CLV and p_alive together rather than using p_alive alone.

## Churn Prediction Is Leakage-Free by Design

The churn model predicts whether a customer will make no purchase in the 90 days after a fixed cutoff date. The final cutoff is 2011-09-10. Features are computed only from transactions on or before the cutoff, while labels are computed only from the future 90-day window.

This design addresses the main methodology risk in the professor's feedback: label leakage. A naive churn definition such as "no purchase in the last 90 days" would be partly encoded by recency and would overstate model quality. SmartCart avoids that by separating the feature window from the label window.

XGBoost is selected as the production churn model. It reaches 0.802 test AUC on 1,057 held-out customers, above the project target of AUC >= 0.75. The held-out set has a 56.6% observed churn rate, and average predicted churn probability is 56.4%, indicating that the model is calibrated at the aggregate level for this evaluation slice.

Customer-level churn probabilities are written to `churn_scores`. The dashboard groups them into High, Medium, and Low risk bands using configurable thresholds. The model still depends only on transaction history; it does not observe marketing exposure, browsing behavior, or customer-service contacts.

## Purchase Propensity Turns Campaign Targeting Into a Ranked List

The purchase-propensity module predicts which customers are likely to purchase in the next 30 days. It uses a leakage-free cutoff design similar to churn, but with a shorter business horizon.

Features include RFM, customer tenure, basket size, average days between orders, purchase regularity, and recency relative to a customer's own purchase rhythm. Tuned XGBoost reaches 0.787 test AUC, ahead of the logistic baseline after cross-validation corrected an earlier overfitting issue.

The practical value appears in the cumulative-gain results. Contacting the top 20% of customers by propensity score captures 47.0% of actual buyers, a 2.3x lift over random targeting. This makes the dashboard's Campaign Budget Planner usable for real decisions: a retailer can choose how many customers to contact and see the expected concentration of likely buyers.

The limitation is that the test set is moderate in size and the Online Retail II purchase rhythm is more wholesale-like than many consumer retail businesses. A production retailer should retrain and revalidate on its own transaction history.

## Market Basket Finds Stable Cross-Sell Opportunities

The market-basket module uses Apriori association rules on multi-item invoices. Olist was kept as a backup dataset, but Online Retail II is better suited for this module because it has enough multi-item baskets.

At the selected thresholds, 68 rules survive. The strongest rule pairs GREEN REGENCY TEACUP AND SAUCER with ROSES REGENCY TEACUP AND SAUCER at 79.8% confidence and 25.4 lift. Product recommendations are separated into two business types:

- Complete the Set: variants from the same product line, useful for merchandising and restocking.
- Often Bought With: different products frequently purchased together, useful for cross-sell modules and bundles.

Threshold sensitivity shows support is the most sensitive parameter, but bootstrap stability supports the chosen rule set: 56 of 68 rules survive in every resample, and none are classified as unstable. This reduces the risk that recommendations are purely noise from one sample.

## Cohort Retention Adds a Lifecycle View

Cohort retention groups customers by first-purchase month and measures whether they continue buying in later months. It complements churn prediction because it shows lifecycle behavior across acquisition periods rather than only scoring individual customers at one cutoff.

The output contains 25 monthly acquisition cohorts from December 2009 through December 2011. Average month-1 retention is 21.2%, and average month-6 retention is 17.8%. The dashboard visualizes this as a retention heatmap and revenue-per-customer view.

Cohort analysis is descriptive. Later cohorts have fewer observable months by construction, so the heatmap has a triangular shape. It also does not control for seasonality or marketing changes that are not present in the dataset.

## Group Comparisons Are Observational, Not Causal

The group-comparison module tests whether customer groups differ in behavior and value. UK vs. non-UK comparisons and Champions vs. Hibernating comparisons are written to `group_comparison_results`, with both p-values and effect sizes.

Champions differ strongly from Hibernating customers across the core business metrics. Average frequency is 20.34 orders for Champions versus 1.42 for Hibernating customers, with Cohen's d = 1.269. Recency is 24.1 days versus 390.3 days, with Cohen's d = -2.358. CLV and monetary value also differ materially.

UK vs. non-UK differences are statistically detectable but smaller in practical size. For example, UK average baseline CLV is GBP 1,447 versus GBP 2,570 for non-UK customers, with Cohen's d = -0.222. Frequency differences are not meaningful. This distinction is important: the dashboard reports effect sizes so users do not overreact to p-values driven by sample size.

All group-comparison results are observational. They describe differences and support targeting hypotheses, but they do not prove that geography or segment membership causes the outcome.

## Segment-Level Churn Validation Avoids Circularity

The original segment-vs-churn snapshot comparison was partly circular because both segment assignment and snapshot inactivity depend on recency. SmartCart addresses this with a V2 validation.

The V2 design builds `segments_at_cutoff` using only pre-cutoff RFM behavior, then joins those historical segments to future churn labels from `churn_scores`. This tests whether historical segment membership is related to future churn without using future behavior to define the segment.

On the held-out set, the relationship is strong:

| Historical segment | Held-out customers | Actual future churn | Avg predicted churn |
| --- | ---: | ---: | ---: |
| Hibernating | 420 | 81.2% | 79.6% |
| At Risk High-Value | 329 | 54.1% | 53.1% |
| Recent / Promising | 128 | 43.8% | 44.7% |
| Champions | 180 | 12.8% | 16.8% |

The categorical segment-vs-future-churn test has Cramer's V = 0.490 on the held-out set. The predicted churn probability comparison across segments has epsilon-squared = 0.570. These results support using historical segment labels as an interpretation layer for churn risk, while keeping the churn probability itself as the predictive source of truth.

## AI Insight Brief Uses LLM Output With Guardrails

The AI insight brief converts computed outputs into a plain-language business summary. SmartCart supports both a deterministic fallback and an optional OpenAI API path. The LLM path uses `gpt-4.1-mini` to generate a candidate brief from structured evidence in `data/insight_inputs.json`.

The AI brief is constrained by explicit guardrails:

- Use only computed SmartCart outputs.
- Include one data-backed action for each customer segment.
- Do not expose customer-level identifiers.
- Do not make causal claims from observational comparisons.
- Trace every cited number back to the structured input.
- Require human review before the LLM brief becomes the approved dashboard version.

The strengthened validation report confirms that segment actions were preserved, no customer IDs were exposed, observational limitations were stated, and no unqualified causal language was detected. Three automated warnings were manually confirmed as false positives: one date fragment and two product stock codes stored as strings. No fabricated model metrics were found.

Live AI generation is disabled by default in the public demo so viewers cannot spend API credits. Admins can enable it only by setting `SMARTCART_ENABLE_LIVE_AI=true` and providing an API key. This makes the feature real, but controlled.

## Dashboard and Deployment

The dashboard is the product layer. It includes Overview, Connect Data, Customer Groups, Purchase Forecast, Product Pairings, Group Insights, Retention, Churn Risk, Insight Brief, and User Guide pages. The latest dashboard polish reduces technical and course-project wording so the demo feels more like a retailer-facing tool than a classroom artifact.

The app uses `smartcart_deploy.db` for deployment, a smaller SQLite database that excludes the full transaction table but preserves dashboard-ready outputs. Streamlit Community Cloud is connected to GitHub, so pushes to `main` redeploy automatically. The User Guide page gives non-technical users page-by-page guidance without requiring them to read the repository.

The main deployment limitation is operational staleness: Streamlit's free tier can briefly serve an older container after a push. The team mitigates this with manual smoke tests across all dashboard pages after deployment.

## Remaining Limitations and Boundaries

SmartCart is a decision-support system, not a causal engine, universal model, or autonomous marketing advisor. The project reduces several major technical risks through leakage-free splits, data contracts, validation reports, and human review, but several interpretation boundaries remain.

First, the group comparisons and cohort patterns are observational. They identify associations and meaningful differences between customer groups, regions, and lifecycle periods, but they do not prove that geography, segment membership, or another factor caused the observed outcome. Controlled experiments would be required before making causal claims about campaign effects.

Second, the Online Retail II dataset is an older, wholesale-oriented transaction dataset covering 2009 to 2011. Customer behavior, purchase frequency, seasonality, and model performance may differ for modern B2C retailers or other industries. For production use, the pipeline should be rerun and revalidated on each retailer's own data before decisions are made from the scores.

Third, the churn, propensity, and CLV outputs should be interpreted as prioritization signals rather than certain outcomes. The churn and propensity models use transaction history only; they do not include browsing behavior, marketing exposure, customer-service interactions, inventory changes, or external market factors. BG/NBD CLV is also less reliable for one-time buyers or customers with limited repeat-purchase history.

Finally, the AI brief converts verified analytics outputs into plain-language recommendations, but it still requires human judgment. Automated number tracing and causal-language checks reduce the risk of fabricated or overclaimed insights, but they do not eliminate the need for a named reviewer to confirm that the wording is appropriate for the retailer's business context.

## Risk Register

| Risk | Why it matters | Mitigation |
| --- | --- | --- |
| Churn label leakage | Recency could accidentally encode churn labels and inflate performance. | Strict feature-window / label-window split; held-out AUC reported only from data not used in training. |
| Module drift | Dashboard joins can become inconsistent if modules use different keys or definitions. | `customer_id` data contract, SQLite as source of truth, join QA checks. |
| Dataset generalizability | Online Retail II is wholesale-like and may not represent every retailer. | Config-driven pipeline; production users must rerun and revalidate on their own data. |
| Small held-out test sets | Churn and propensity metrics may shift under another cutoff or seed. | Report point estimates with limitations; recommend rolling validation in production. |
| Market-basket threshold sensitivity | Small support changes can change rule counts. | Sensitivity testing and bootstrap stability checks. |
| AI hallucination or overclaiming | LLM wording could invent numbers or imply causality. | Structured evidence input, number tracing, causal-language scan, human approval gate. |
| Deployment staleness | Streamlit Cloud can briefly serve old code after push. | Manual live smoke test and app reboot if needed. |
| Customer data exposure | Customer-level identifiers should not appear in AI summaries. | Anonymized source IDs plus AI guardrail forbidding customer-level identifiers. |

## Final Business Impact

SmartCart turns a transaction CSV into a working growth analytics product. A retailer can open the dashboard, review customer groups, prioritize retention and purchase campaigns, inspect product bundles, understand cohort retention, and read a reviewed AI-generated business brief.

The project is stronger than a static model dump because it connects model outputs to specific actions. The segmentation and CLV modules identify customer value; churn and propensity rank near-term outreach; market basket suggests merchandising actions; cohort retention shows lifecycle patterns; group comparisons and V2 churn validation provide evidence checks; and the AI brief translates the evidence into plain language with guardrails.

The final result is a reusable, transparent, and auditable demo of how small retailers could access growth analytics without enterprise software.
