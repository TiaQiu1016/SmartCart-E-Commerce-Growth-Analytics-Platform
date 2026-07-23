# SmartCart AI Insight Brief - LLM Generated Candidate

## Scope and Guardrails
This brief is generated solely from computed SmartCart SQLite outputs (schema version 1.1) as of 2026-07-23. All metrics and insights are observational and based strictly on the provided JSON data. No causal claims are made. Customer-level identifiers are excluded. BG/NBD CLV estimates are used when available. Predictive churn signals are derived from held-out test data with a 90-day label window. Statistical comparisons are observational and report effect sizes without implying causality.

## Executive Summary
The customer base segments into four distinct groups with markedly different behaviors and values. Champions exhibit the highest purchase frequency (20.34) and BG/NBD CLV (5697.78), while Hibernating customers show low frequency (1.42) and CLV (216.55). Predictive churn probabilities align well with actual churn rates, especially for Hibernating (79.63% predicted vs. 81.19% actual). Significant differences exist between Champions and Hibernating segments across CLV, frequency, monetary value, and recency, with medium-to-large effect sizes (e.g., Cohen's d = 0.73 for CLV). Product recommendations highlight complementary pairs with high lift and confidence, supporting cross-sell opportunities.

## Segment Actions

- **Champions**  
  Recommended action: *Protect and grow with VIP retention, early access, and referral offers.*  
  Supporting data: BG/NBD CLV 5697.78, average frequency 20.34, average p_alive 0.9805, predicted active purchase weeks 8.19.

- **Recent / Promising**  
  Recommended action: *Trigger a second-purchase campaign while recency is still strong.*  
  Supporting data: BG/NBD CLV 1092.7, average frequency 3.04, average p_alive 0.9665, predicted active purchase weeks 3.22.

- **At Risk High-Value**  
  Recommended action: *Prioritize win-back messaging because past value is high but recent activity is weak.*  
  Supporting data: BG/NBD CLV 950.74, average frequency 5.48, average p_alive 0.8397, predicted active purchase weeks 2.27.

- **Hibernating**  
  Recommended action: *Use low-cost reactivation only; avoid heavy discount spend unless basket value improves.*  
  Supporting data: BG/NBD CLV 216.55, average frequency 1.42, average p_alive 0.9164, predicted active purchase weeks 0.76.

## Predictive Churn Signals
Predictive churn models were validated on held-out test sets with a 90-day label window:

- **Hibernating**: Predicted churn 79.63%, actual churn 81.19% (420 customers)  
- **At Risk High-Value**: Predicted churn 53.10%, actual churn 54.10% (329 customers)  
- **Recent / Promising**: Predicted churn 44.70%, actual churn 43.75% (128 customers)  
- **Champions**: Predicted churn 16.84%, actual churn 12.78% (180 customers)  

These segment-level results suggest the churn model is directionally well aligned with observed future churn, supporting its use for prioritization rather than causal claims.

## Group Comparison Signals
Significant differences between Champions (n=1087) and Hibernating (n=2077) segments highlight key behavioral and value gaps:

| Metric          | Champions Mean | Hibernating Mean | Effect Size (Cohen's d) | p-value |
|-----------------|----------------|------------------|-------------------------|---------|
| CLV Estimate    | 4783.70        | 191.83           | 0.7301                  | 0.0     |
| Frequency       | 20.34          | 1.42             | 1.2691                  | 0.0     |
| Monetary Value  | 11687.21       | 349.21           | 0.5909                  | 0.0     |
| Recency (days)  | 24.11          | 390.34           | -2.3576                 | 0.0     |

All differences are statistically significant (p < 0.001) with medium-to-large effect sizes, confirming distinct customer profiles.

Additionally, UK vs Non-UK customers show a significant difference in CLV estimate (UK mean 1446.56 vs Non-UK 2570.14, Cohen's d = -0.2221, p < 0.001) and monetary value (UK 2752.03 vs Non-UK 5719.85, Cohen's d = -0.2017, p = 0.0013), but no significant difference in frequency. These regional differences are statistically significant but relatively small in effect size, so they should be interpreted as secondary context rather than the main targeting logic.

## Product Recommendation Signals
Top product association rules with high lift and confidence suggest effective cross-sell opportunities:

| Base Product (Stock Code) | Base Description                 | Recommended Product (Stock Code) | Recommended Description           | Rule Type       | Support | Confidence | Lift    |
|---------------------------|--------------------------------|----------------------------------|---------------------------------|-----------------|---------|------------|---------|
| 22697                     | GREEN REGENCY TEACUP AND SAUCER| 22699                            | ROSES REGENCY TEACUP AND SAUCER | Complete the Set| 0.0222  | 0.7979     | 25.3714 |
| 22699                     | ROSES REGENCY TEACUP AND SAUCER| 22697                            | GREEN REGENCY TEACUP AND SAUCER | Complete the Set| 0.0222  | 0.7073     | 25.3714 |
| 22726                     | ALARM CLOCK BAKELIKE GREEN     | 22727                            | ALARM CLOCK BAKELIKE RED        | Complete the Set| 0.0207  | 0.6776     | 20.0776 |
| 22356                     | CHARLOTTE BAG PINK POLKADOT    | 20724                            | RED RETROSPOT CHARLOTTE BAG     | Often Bought With| 0.0207 | 0.6345     | 14.3859 |
| 21231                     | SWEETHEART CERAMIC TRINKET BOX | 21232                            | STRAWBERRY CERAMIC TRINKET BOX  | Complete the Set| 0.0253  | 0.7331     | 13.1691 |

These pairs indicate strong complementary purchase patterns to leverage in marketing and merchandising.

## Limitations and Human Review Checklist
- All comparisons are observational; no causal inferences should be drawn.  
- Predictive churn is based on held-out test data with a 90-day label window; longer-term churn dynamics are not captured.  
- BG/NBD CLV estimates assume model assumptions hold; one-time buyers and P(alive) probabilities may affect accuracy.  
- Segment definitions and boundaries may affect interpretation; human review recommended before operationalizing actions.  
- Product recommendation metrics (support, confidence, lift) are association-based and do not imply causality or profitability.  
- Regional differences (UK vs Non-UK) show small to moderate effect sizes; consider local context in strategy.  
- Ensure privacy and compliance standards are maintained when targeting segments.  

Human experts should validate these insights in the context of broader business strategy and operational constraints before implementation.
