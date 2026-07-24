# Final Report Draft Sections - Xuechen

These sections are drafted for integration into the final SmartCart report. They cover the modules primarily owned or reviewed by Xuechen: segmentation interpretation, CLV, group comparison, segment-level churn validation, and AI insight-brief guardrails.

## 1. Customer Segmentation

### Objective

The segmentation module groups customers into a small number of behaviorally distinct and business-actionable segments. The goal is not to maximize statistical complexity, but to create clear customer groups that a small or mid-sized retailer can understand and act on without enterprise analytics tools.

### Method

SmartCart uses RFM features: recency, frequency, and monetary value. Because these variables live on different scales and are heavily skewed, the pipeline applies `log1p` to each RFM variable and then standardizes the transformed features with `StandardScaler` before fitting K-Means. This directly addresses the proposal feedback about locking down RFM normalization before clustering.

K-Means is tested for k = 4 through k = 8. The selected solution uses k = 4 because it has the strongest silhouette score among the tested options while keeping the result simple enough for business users. Clusters are translated into four named segments: Champions, Recent / Promising, At Risk High-Value, and Hibernating. Each segment is assigned one recommended action stored in the `segments` output table.

### Validation and Output

The final segmentation output contains 5,878 customers in the `segments` table, using `customer_id` as the shared key. Segment profiles and silhouette diagnostics are saved for documentation and dashboard use. The K-Means segmentation is the authoritative segmentation used by the dashboard, while the SQL RFM scoring is kept as a transparent baseline cross-check.

### Limitations

K-Means assumes distance-based clusters and may not capture every retail behavior pattern. Segment names are rule-based interpretations of cluster profiles, not labels learned from an external truth source. The full-period `segments` table describes historical customer state; predictive churn validation uses a separate `segments_at_cutoff` table to avoid time leakage.

### Business Implication

The segmentation layer turns raw transaction history into a practical action map. Champions should receive retention and growth offers, Recent / Promising customers should be encouraged toward a second purchase, At Risk High-Value customers should receive targeted win-back messaging, and Hibernating customers should receive lower-cost reactivation campaigns.

## 2. Customer Lifetime Value

### Objective

The CLV module estimates expected customer value so retailers can prioritize marketing spend across segments and customers. SmartCart includes both a transparent baseline CLV and a probabilistic BG/NBD + Gamma-Gamma enhancement.

### Method

The baseline CLV is calculated as average order value multiplied by annualized order rate and an exponential recency weight. To prevent unrealistic estimates for new or short-tenure customers, the annualized order rate uses a 90-day minimum observation window and is capped at the 95th percentile. This fix addresses the one-time or short-tenure buyer inflation issue identified during review.

The enhanced CLV uses BG/NBD to estimate future purchase activity and probability alive, then Gamma-Gamma to estimate expected monetary value for repeat customers. For one-time buyers, SmartCart patches the monetary input using invoice-level average order value so they are not assigned zero value simply because they lack repeat history.

### Validation and Output

The baseline CLV table is written to `clv`, and the enhanced probabilistic output is written to `clv_bgnbd`. BG/NBD holdout validation predicts active purchase weeks over a six-month holdout period with strong correlation between predicted and actual activity. The final AI input uses BG/NBD CLV fields when available, including `clv_bgnbd`, `p_alive`, predicted active purchase weeks, and repeat-history flags.

### Limitations

Baseline CLV is easy to explain but deterministic and parameter-driven. BG/NBD is more statistically grounded but has important assumptions: purchase frequency and monetary value should be approximately independent, same-week purchases are collapsed in the weekly model, and `p_alive` can be inflated for one-time buyers because the model has insufficient repeat-purchase history for them.

### Business Implication

CLV supports prioritization. High-CLV customers can justify more expensive retention and upsell offers, while low-CLV or uncertain customers should receive lower-cost campaigns until more evidence of value appears.

## 3. Customer Group Comparison

### Objective

The group comparison module tests whether important customer groups differ in behavior and value. It supports dashboard-ready interpretation for geography and segment comparisons while clearly separating descriptive evidence from causal claims.

### Method

Version 1 compares UK vs. non-UK customers and Champions vs. Hibernating customers across recency, frequency, monetary value, and baseline CLV. Numeric outcomes use Welch t-tests and Mann-Whitney U tests, with Cohen's d reported as an effect size. Categorical snapshot inactivity uses chi-square tests and Cramer's V.

### Validation and Output

Results are written to `group_comparison_results`, and segment-level summaries are written to `segment_comparison_summary`. The dashboard presents both p-values and effect sizes so users can distinguish statistically detectable differences from practically meaningful ones.

### Limitations

These comparisons are observational, not randomized experiments. They show where customer groups differ, but not why. The original segment vs. churn snapshot comparison is partly circular because recency contributes to both segmentation and the snapshot inactivity definition. For this reason, final churn-related claims rely on the leakage-free V2 validation described below.

### Business Implication

Group comparisons help retailers decide where to focus attention. For example, strong differences between Champions and Hibernating customers justify different campaign strategies, but the recommendations should be framed as evidence-informed actions rather than causal effects.

## 4. Segment-Level Churn Validation

### Objective

The segment-level churn validation tests whether historical customer segments are meaningfully related to future churn outcomes without leaking future information into the segment definitions.

### Method

The churn model uses a fixed feature cutoff date of 2011-09-10. Features are computed only from transactions on or before the cutoff, and the churn label is whether the customer made no purchase in the following 90 days. To align segmentation with this leakage-free design, SmartCart creates `segments_at_cutoff`: a segment assignment using only pre-cutoff RFM behavior. These historical segments are then joined to post-cutoff actual churn labels and predicted churn probabilities.

### Validation and Output

The V2 validation writes three outputs: `segments_at_cutoff`, `segment_churn_v2_summary`, and `segment_churn_v2_results`. On held-out customers, Hibernating customers have the highest observed future churn rate, while Champions have the lowest. The dashboard now includes a Future Churn Validation view that displays actual future churn and average predicted churn by historical segment.

### Limitations

This validation supports the claim that historical segments are related to future churn, but it is still observational. Segment membership is not a treatment and does not cause churn. The validation also depends on a single cutoff date and 90-day label window; future deployments should re-check performance under different cutoffs or rolling validation windows.

### Business Implication

The V2 result makes segmentation more useful for action planning. Retailers can use historical segments as an interpretation layer for churn risk while keeping the churn model probability as the predictive source of truth.

## 5. AI Insight Brief and Guardrails

### Objective

The AI insight-brief component converts computed analytics outputs into a plain-language business summary for non-technical retailers. Its purpose is to make the model results actionable without allowing the system to invent numbers or overstate evidence.

### Method

`src/prepare_insight_inputs.py` reads verified SQLite outputs and creates a structured JSON contract. SmartCart then supports two generation paths. The deterministic fallback, `src/generate_insight_brief.py`, converts that JSON into a reviewed Markdown candidate brief without calling an external model. The optional LLM path, `src/generate_insight_brief_llm.py`, sends the same structured evidence and guardrails to the OpenAI API and writes an LLM-generated candidate brief plus a validation report. This keeps the AI feature aligned with the project requirement that recommendations remain traceable to computed model outputs.

The brief includes segment actions, CLV and propensity evidence, group comparison signals, predictive churn signals, and product recommendation signals. Each customer segment must have at least one actionable recommendation tied to computed metrics.

### Validation and Guardrails

The generator must use only fields present in `data/insight_inputs.json`, identify unavailable modules explicitly, preserve observational limitations, and avoid causal language. It must not recompute metrics, invent missing values, expose customer-level identifiers, or recommend discriminatory targeting based on protected characteristics.

### Limitations

The current brief is a decision-support artifact rather than a fully autonomous AI advisor. A human reviewer must verify that every number matches the structured input and that recommendations are appropriate before including the wording in the dashboard, report, or presentation.

### Business Implication

The AI brief is the bridge between analytics and business action. It gives small retailers a readable summary of what to do next while keeping the underlying evidence traceable to the models and database outputs.
