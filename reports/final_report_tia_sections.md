# Final Report Draft Sections - Tia

These sections are drafted for integration into the final SmartCart report. They cover the modules primarily owned by Tia: the problem statement, purchase-propensity prediction, churn prediction, product recommendation (market basket), cohort retention, dashboard/deployment, and the project risk register.

## 0. Problem Statement

Most small and mid-sized online retailers manage customer analytics with a spreadsheet, or nothing at all. They have the same raw transaction data that powers enterprise analytics platforms, but not the budget: tools like Salesforce Marketing Cloud or Klaviyo's higher tiers price out the long tail of small sellers who would benefit most from knowing which customers are about to churn, which are worth a retention offer, and which products to bundle together.

SmartCart's realistic alternative is therefore not "a worse enterprise tool" but "no tool at all." A retailer running analytics in a spreadsheet can compute total revenue and maybe a manual recency check, but cannot practically run a leakage-free churn model, a probabilistic CLV estimate, or association-rule mining across tens of thousands of invoices. SmartCart closes that specific gap: it takes the same transaction export a retailer already has and turns it into segmentation, CLV, churn and propensity scores, product recommendations, and a plain-language action brief, using only free and open-source tools.

## 1. Purchase-Propensity Prediction

### Objective

The propensity module predicts which customers are likely to make a purchase in the next 30 days, so a retailer can decide who to target in a marketing campaign right now. This is a shorter, more action-oriented horizon than the 90-day churn window: churn answers "who are we about to lose," propensity answers "who should we contact today."

### Method

`src/propensity_model.py` uses the same leakage-free time-split design as the churn model: the cutoff is set 30 days before the latest transaction date, features are computed only from transactions on or before the cutoff, and the label is whether the customer purchased anything after it. Features are standard RFM (recency, frequency, monetary, tenure, average basket size) plus three purchase-rhythm signals: `avg_days_between_orders`, `purchase_regularity`, and `recency_ratio` (how "due" a customer is to buy again relative to their own rhythm).

Both logistic regression and XGBoost are tuned with stratified 5-fold cross-validation on the training set only, never touching the held-out test set during tuning. An earlier, untuned XGBoost model actually scored below the logistic regression baseline (0.762 vs. 0.781 test AUC), a red flag, since gradient-boosted trees should not lose to a linear model on tabular data unless misconfigured. Cross-validated tuning found a shallower, more regularized tree (`max_depth=2`, `reg_lambda=2.0`), which raised XGBoost to 0.787 test AUC, ahead of logistic regression. This confirmed the original ordering was an overfitting artifact, not a genuine result about model choice.

### Validation and Output

Customer-level propensity scores are written to `propensity_scores`. The cumulative-gain analysis shows the model's practical value for campaign targeting: contacting the top 20% of customers by score reaches 47.0% of actual buyers (2.3x lift over random targeting), and the top 10% reaches 28.9% (2.9x lift). The dashboard's Campaign Budget Planner converts this into concrete score thresholds. For example, targeting the top 15% requires a score of 0.736 or higher, at 69% precision. SHAP feature attribution confirms the intuitive direction of every feature: recent, frequent, regular buyers score higher.

### Limitations

The test set is approximately 1,144 customers, so AUC and lift numbers carry sampling variance under a different seed or cutoff date. Online Retail II is a wholesale dataset with more regular reorder rhythms than typical consumer retail, so the strong performance of the rhythm features may not transfer as cleanly to a B2C retailer. No external signal (marketing exposure, browsing behavior) is available, only transaction history.

### Business Implication

The propensity score turns "who should we email this week" from a guess into a ranked list with a known capture rate. A retailer with a fixed campaign budget can pick the row of the threshold table that matches how many customers they can afford to contact, and know in advance roughly what precision and recall to expect.

## 2. Churn Prediction Model

### Objective

The churn model predicts whether a customer will make no purchase in the next 90 days, so a retailer can act on risk before a customer actually goes quiet. This is the module the professor's leakage feedback focused on directly, so its design is documented here in full.

### Method

Churn is framed as churned = 1 if the customer made zero purchases in the 90 days after a fixed cutoff date (2011-09-10), churned = 0 otherwise. The critical design constraint is avoiding label leakage: defining churn as "no purchase in the last 90 days" and then using recency as a feature would let the feature directly encode the label, producing inflated performance that would not hold on new data. SmartCart enforces a strict time split instead: all five features (`recency_days`, `frequency`, `monetary`, `tenure_days`, `avg_basket_size`) are computed only from transactions on or before the cutoff, and the label uses only the 90 days after it. No information from the label window ever touches the features.

Logistic regression (with `class_weight="balanced"` to account for the 56.6% base churn rate) and XGBoost are both trained on an 80/20 stratified split. XGBoost is selected as the production model.

### Validation and Output

XGBoost achieves 0.802 test AUC, computed only on the 1,057-customer held-out test set that never influenced training. This clears the professor's ≥ 0.75 AUC bar with the leakage-free design intact. Customer-level probabilities are written to `churn_scores`, and the dashboard buckets customers into High (≥ 75%), Medium (50-75%), and Low (< 50%) risk bands. Both thresholds are configurable in `config.yaml` rather than hardcoded, so the same dashboard code works for a retailer with a different risk tolerance. Feature importance consistently ranks recency first, then frequency and tenure, which matches the intuitive story: a customer silent longer than their usual rhythm is at high risk.

### Limitations

The 56.6% base churn rate is partly a data artifact: the 90-day label window falls near the end of the dataset, so customers who simply had not yet repurchased by the data cutoff are labeled churned even if still active. Online Retail II's wholesale reorder patterns may not transfer directly to a B2C retailer with more irregular buying behavior. The 1,057-customer test set carries sampling variance under a different seed or cutoff choice. Only transactional features are used; marketing exposure and browsing behavior are not available in this dataset.

### Business Implication

The High-Risk Customer List gives a retailer a prioritized, actionable set of accounts to contact before they disengage, rather than a single aggregate churn rate. Because the underlying design is leakage-free, the 0.802 AUC is a defensible estimate of how the model would perform on genuinely new, unseen customers going forward, not an artifact of the label being visible in the features.

## 3. Product Recommendation (Market-Basket Analysis)

### Objective

The market-basket module finds product combinations that are bought together more often than chance would predict, so a retailer can decide what to bundle, cross-sell, or stock together.

### Method

`src/market_basket.py` runs Apriori frequent-itemset mining on invoice-level "baskets" from Online Retail II, the only dataset of the two considered suitable for this analysis, since Olist's orders are almost entirely single-item (~3.3% multi-item) and cannot support meaningful association-rule mining. After filtering to multi-item invoices, 33,897 of 36,969 total invoices remain in scope, covering 4,621 distinct products. Three thresholds control which rules survive: support (how common the pair is overall), confidence (P(buy B | bought A)), and lift (how much more likely B is given A, versus B's own baseline popularity). At `min_support=0.02`, `min_confidence=0.3`, `min_lift=1.5`, 68 rules survive.

Rules are further split by whether the antecedent and consequent share 2+ significant description words: 23 "Complete the Set" rules (color/size variants of the same product line, a real wholesale restocking pattern, not noise) and 45 "Often Bought With" rules (genuinely different products, the cross-category recommendations a "customers also bought" feature would surface).

### Validation and Output

A threshold sensitivity sweep found that `min_support` is the sensitive parameter (one step down to 0.015 nearly triples the rule count, and one step up to 0.025 cuts it by more than half), while `min_confidence` degrades smoothly and `min_lift` is essentially non-binding at this operating point. A follow-up bootstrap stability check resampled the 33,897 invoices 20 times and re-mined rules at the same thresholds: 56 of 68 rules (82%) survive in every single resample, and zero rules are unstable. This confirms the chosen thresholds, while sensitive in the abstract, produce a genuinely stable rule set rather than noise.

### Limitations

Rule counts and the sensitivity/bootstrap results are specific to this dataset's multi-item invoice population and would shift on a different or larger dataset. The "Complete the Set" vs. "Often Bought With" split uses a simple word-overlap heuristic rather than a learned classifier, so edge cases could be misclassified. The bootstrap used 20 resamples for runtime reasons; a larger run would narrow the survival-rate estimate further.

### Business Implication

The dashboard's Product Recommendations page lets a retailer look up any product and see its most reliable pairings, split into "stock both variants" versus "genuine cross-sell" recommendations, directly actionable for merchandising, bundling, and on-site "frequently bought together" placement.

## 4. Cohort Retention Analysis

### Objective

Cohort retention answers a different question than the churn model: instead of scoring individual customers, it tracks what fraction of customers acquired in the same month are still buying N months later. This is a diagnostic view of customer lifecycle patterns across the full dataset period, not a predictive score.

### Method

`src/cohort_analysis.py` assigns each customer to an acquisition cohort, the calendar month of their first purchase, and computes `retention_rate[cohort, N]` as the share of that cohort who purchased again exactly N months after acquisition. Revenue per cohort is tracked the same way, dividing by the original cohort size (not the active subset) so it declines naturally as retention falls.

### Validation and Output

The dataset yields 25 monthly cohorts from December 2009 to December 2011, tracked for up to 24 periods, with cohort sizes ranging from 28 to 955 customers. Results are written to `cohort_retention` and `cohort_revenue`, and visualized as a heatmap on the dashboard's Cohort page (cohorts on one axis, months-since-acquisition on the other, color intensity proportional to retention). The December 2009 cohort shows a notably higher period-1 retention (35.3%) than subsequent cohorts (~20%), consistent with those early customers being established wholesale accounts already reordering regularly before the dataset period began.

### Limitations

Later cohorts have fewer observable periods by construction. A customer acquired in November 2011 can only be tracked for one month, so the heatmap is naturally triangular. This is a descriptive, historical analysis that does not control for seasonality or marketing activity, and "active in period N" is a binary measure that does not distinguish a small order from a large one.

### Business Implication

Cohort retention gives a retailer a lifecycle view that complements the individual-level churn score: it shows whether retention is structurally improving or declining across acquisition periods, which the churn model alone (a single snapshot in time) cannot show.

## 5. Dashboard and Deployment

### Objective

The dashboard is the delivery layer that makes every other module usable by a non-technical retailer, and the deployment makes it accessible without any local setup.

### Method

Before committing build time, Streamlit and Dash (Plotly) were compared hands-on by building matching prototype pages against the real `smartcart.db` data (Gradio was ruled out earlier as unsuited to a multi-page BI dashboard). Streamlit produced the same visual output in fewer lines of code, mainly due to built-in KPI and layout widgets, and was chosen given the team's ~5-week runway and Python-only skill set.

The resulting dashboard has eight pages: Overview, Data Setup, Segmentation, Purchase Likelihood, Market Basket, Group Insights, Cohort, Churn Risk, and AI Brief. It is wired to the K-Means `segments` table as the authoritative segmentation (the SQL `rfm_scored` baseline is kept only as a transparent cross-check), and to `clv`, `clv_bgnbd`, `propensity_scores`, `churn_scores`, and `association_rules`. All retailer-specific values (currency symbol, churn risk-band thresholds, course/data-source labels) are read from `config.yaml` rather than hardcoded, so the same codebase generalizes to a different dataset or a different retailer's risk tolerance without a code change.

### Validation and Output

The dashboard is deployed on Streamlit Community Cloud, connected directly to the GitHub repository so pushes to `main` redeploy automatically. All eight pages were manually QA'd against the live deployment (not just locally): every page loads without error, currency labels render dynamically, the Cohort page's pandas 2.1+ compatibility fix (`applymap` → `map`) works in production, the churn risk thresholds pull correctly from `config.yaml`, and the AI Insight Brief's human-approval gate persists correctly across redeploys because the approval record is committed to git rather than left as container-local state.

### Limitations

Streamlit Community Cloud's free tier can leave a stale container running old code briefly after a push until it fully restarts; one QA pass surfaced exactly this (an `ImportError` on the Churn page referencing constants added in the latest commit) and it resolved after a manual reboot. This is an operational deployment risk, not a code defect, and is tracked in the risk register below.

### Business Implication

A retailer, instructor, or hiring reviewer can open the dashboard's public URL directly and interact with the same live data and models described in this report, with no installation required.

## 6. Risk Register

| # | Risk | Type | Description | Mitigation |
| --- | --- | --- | --- | --- |
| 1 | Churn label leakage | Technical | Defining churn as "no purchase in the last 90 days" and then using recency as a feature would let the feature directly encode the label, inflating measured performance in a way that would not hold on new data. | Strict time-split design in `src/churn_model.py`: all features computed only from transactions on or before a fixed cutoff date; the label uses only the 90-day window after it. Reported AUC (0.802) is measured on a held-out test set never touched during feature construction or training. |
| 2 | Small held-out test sets | Technical | Churn (1,057 customers) and propensity (~1,144 customers) test sets are moderate in size; AUC and lift figures carry sampling variance under a different random seed or cutoff date. | Report figures as point estimates with this caveat explicit in each module's limitations; avoid over-claiming precision beyond what the sample size supports. |
| 3 | Dataset generalizability | Data | Online Retail II is a wholesale (B2B) dataset with more regular reorder rhythms than typical consumer (B2C) retail; model weights and rule counts may not transfer directly to a different retailer. | Every module's limitations section names this explicitly; `config.yaml` is designed so the same code can be re-run against a different retailer's data without a code change, allowing re-validation rather than assuming transfer. |
| 4 | Market-basket threshold sensitivity | Technical | The chosen `min_support=0.02` sits on a sensitive part of the parameter space, where small changes swing the rule count sharply. | A bootstrap stability check (20 resamples) confirmed 82% of the 68 rules survive in every resample and none are unstable, showing the specific rule set is robust even though the raw parameter is sensitive. |
| 5 | AI brief invents or misstates numbers | Technical / AI | An LLM-generated brief could state a number not actually present in the computed model outputs, or use causal language the underlying analysis does not support. | Guardrails in `src/generate_insight_brief_llm.py` trace every number in the brief back to the structured JSON input (within 1.5% tolerance), scan for causal-language trigger phrases, and require a named human reviewer to approve the brief before it is shown as the dashboard default. |
| 6 | Deployment staleness | Operational | Streamlit Community Cloud's running container can briefly serve an older version of the code after a push, causing import errors for newly added names until it fully restarts. | Verify each deployment with a full manual QA pass across all dashboard pages after pushing; reboot the app manually if a stale-container error is observed. |
| 7 | Customer data exposure | Compliance | The AI insight brief or dashboard could surface customer-level identifiers inappropriately. | Online Retail II customer IDs are already anonymized integers with no PII; AI brief guardrails additionally forbid exposing customer-level identifiers or recommending targeting based on protected characteristics. |
