# SmartCart Final Report Draft

This combined draft assembles Tian's and Xuechen's final-report sections into one report structure. It is ready to use as the working final-report source, but the team should still do one final pass for length, formatting, and any course-specific submission template requirements.

## 1. Problem Statement

Most small and mid-sized online retailers manage customer analytics with a spreadsheet, or nothing at all. They have the same raw transaction data that powers enterprise analytics platforms, but not the budget or technical team to turn it into churn scores, customer value estimates, product recommendations, and plain-language actions.

SmartCart closes that gap. It takes a retailer's own transaction export and turns it into segmentation, CLV, churn and purchase-propensity signals, market-basket recommendations, group comparisons, cohort retention, and an AI-generated insight brief. The realistic alternative for this audience is not a weaker enterprise platform. It is a spreadsheet or no analytics process at all.

## 2. Data and System Design

SmartCart uses Online Retail II as the primary dataset. The cleaned SQLite database is the single source of truth for the modelling pipeline, and every customer-level table uses `customer_id` as the shared key. Retailer-specific settings such as currency symbol, dataset labels, and churn risk thresholds live in `config.yaml`, so the dashboard is designed as a reusable product rather than a one-off notebook analysis.

The pipeline writes reproducible outputs for transactions, RFM, segments, CLV, BG/NBD CLV, churn scores, propensity scores, market-basket rules, cohort retention, group comparisons, and AI brief inputs. `data_contract.md` records the expected table schemas and join checks.

## 3. Customer Segmentation

SmartCart groups customers using RFM features: recency, frequency, and monetary value. Because these variables have very different scales and skewed distributions, the pipeline applies `log1p` transformations and then `StandardScaler` before fitting K-Means. This locks down the RFM normalization requested in the proposal feedback.

The selected solution uses four clusters, translated into business-readable segments: Champions, Recent / Promising, At Risk High-Value, and Hibernating. Each segment carries a recommended action, making the output directly usable for campaign planning rather than only descriptive analysis.

Limitations remain: K-Means imposes distance-based clusters, segment names are human interpretations of profiles, and the full-period segment table is descriptive. Predictive churn validation therefore uses a separate pre-cutoff segmentation table to avoid future leakage.

## 4. Customer Lifetime Value

SmartCart includes both a transparent baseline CLV and a probabilistic BG/NBD + Gamma-Gamma enhancement. Baseline CLV multiplies average order value, annualized order rate, and a recency weight. The short-tenure inflation issue identified during review is addressed with a 90-day minimum observation window and a cap on annualized order rate.

The BG/NBD enhancement estimates future purchase activity and probability alive, while Gamma-Gamma estimates expected monetary value. One-time buyers are handled carefully and flagged because insufficient repeat-purchase history can make `p_alive` less informative.

CLV helps retailers decide where high-touch campaigns are justified and where lower-cost outreach is more appropriate.

## 5. Churn Prediction

The churn model predicts whether a customer will make no purchase in the 90 days after a fixed cutoff date. Its most important technical design choice is leakage prevention: features are computed only from transactions before the cutoff, while labels are computed only from the future 90-day window.

XGBoost is selected as the production churn model and achieves 0.802 test AUC on the held-out set, clearing the professor's AUC >= 0.75 bar without leaking label-window information. Customer-level probabilities are written to `churn_scores`, and risk bands are configurable in `config.yaml`.

The model uses only transaction history. It does not observe marketing exposure, browsing behavior, or customer-service interactions, so future production use should retrain and revalidate on each retailer's own data.

## 6. Purchase Propensity

The propensity module predicts which customers are likely to purchase in the next 30 days. It uses a leakage-free cutoff design similar to the churn model, but the business question is shorter term: who should be contacted in the next campaign.

Features include RFM, tenure, basket size, average days between orders, purchase regularity, and recency relative to a customer's own purchase rhythm. Tuned XGBoost reaches 0.787 test AUC. The top 20% of customers by score captures 47.0% of actual buyers, giving retailers a concrete way to choose campaign budget thresholds.

## 7. Product Recommendation and Market Basket

The market-basket module uses Apriori association rules on multi-item invoices. It identifies product pairs with support, confidence, and lift, then separates rules into Complete the Set and Often Bought With recommendations.

At the selected thresholds, 68 rules survive. Sensitivity testing shows support is the most sensitive parameter, while bootstrap stability confirms the chosen rule set is not dominated by noise: 56 of 68 rules survive in every resample.

These recommendations support bundling, on-site cross-sell modules, merchandising, and inventory planning.

## 8. Cohort Retention

Cohort retention tracks customer groups by acquisition month and measures whether they continue purchasing in later months. This is descriptive rather than predictive, but it gives retailers a lifecycle view that individual churn scores do not provide.

The cohort heatmap helps show whether newer customers retain at better or worse rates than earlier cohorts. Later cohorts naturally have fewer observable periods, so the interpretation must account for the triangular shape of cohort data.

## 9. Customer Group Comparison

Group comparison tests whether important customer groups differ in behavior and value. Version 1 compares UK vs. non-UK customers and Champions vs. Hibernating customers across recency, frequency, monetary value, and CLV. Numeric metrics use Welch t-tests, Mann-Whitney U tests, and Cohen's d; categorical metrics use chi-square tests and Cramer's V.

These comparisons are observational. They identify meaningful differences and effect sizes, but they do not establish causality.

## 10. Segment-Level Future Churn Validation

To avoid circular reasoning between recency-based segmentation and churn snapshots, SmartCart builds `segments_at_cutoff` using only pre-cutoff RFM behavior. These historical segments are then compared against future churn labels from `churn_scores`.

This V2 validation shows that historical segment membership is meaningfully related to future churn without using future behavior to define the segment. Hibernating customers have the highest observed future churn rate, while Champions have the lowest. This supports using segments as an action layer on top of churn probabilities.

## 11. AI Insight Brief and Guardrails

The AI insight brief converts computed outputs into a plain-language business summary. SmartCart supports a deterministic fallback and an optional OpenAI API LLM path. The LLM path uses `gpt-4.1-mini` to generate a candidate brief from structured evidence in `data/insight_inputs.json`.

Guardrails require one data-backed action per segment, number traceability to computed outputs, no customer-level identifiers, no unsupported causal language, and human review before the LLM brief becomes the approved dashboard version. The validation report documents matched checks and human-reviewed warnings. Live API generation in the dashboard is demo-safe by default and requires `SMARTCART_ENABLE_LIVE_AI=true` plus an API key before it can spend credits.

## 12. Dashboard and Deployment

The Streamlit dashboard is the delivery layer for non-technical retailers. It includes Overview, Data Setup, Segmentation, Purchase Likelihood, Market Basket, Group Insights, Cohort, Churn Risk, AI Brief, and User Guide pages. The deployment uses a smaller `smartcart_deploy.db` that excludes the full transaction table while preserving dashboard-ready outputs.

Streamlit Community Cloud is connected to GitHub so pushes to `main` redeploy automatically. The core analytics pages have been QA'd against the live deployment, and the User Guide page makes the product easier to use without reading the repository.

## 13. Risk Register

Key risks include churn label leakage, moderate held-out test sizes, dataset generalizability, market-basket threshold sensitivity, AI brief hallucination or causal overclaiming, deployment staleness, and customer data exposure. The project addresses these with strict time splits, explicit limitations, bootstrap and sensitivity checks, a data contract, AI validation reports, human approval gates, and live deployment QA.

## 14. Business Impact

SmartCart turns a transaction CSV into an actionable growth analytics platform. A small retailer can identify customer segments, prioritize high-value and high-risk customers, decide who to contact in a campaign, choose product bundles, understand cohort retention, and read an approved AI-generated brief. The result is closer to an accessible operating tool than a static model dump.
