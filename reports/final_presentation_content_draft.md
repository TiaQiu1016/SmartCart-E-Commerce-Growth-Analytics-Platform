# SmartCart Final Presentation: Updated Outline and Slide Content

This updates the original 20-minute outline with everything completed since it was drafted, then drafts speaker-ready content for every slide. Tia's sections are full drafts. Xuechen's sections are drafted from her existing `presentation_outline_xuechen.md` and should get her pass before being treated as final.

## What changed since the original outline

1. **Dashboard is now live and QA'd.** Deployed to Streamlit Cloud, connected to the GitHub repo for auto-redeploy. The 8 core analytics pages were manually verified against the live deployment, not just locally, and a ninth User Guide page was added for non-technical users.
2. **The dashboard is now retailer-agnostic, not just Online-Retail-II-specific.** Currency symbol, churn risk-band thresholds, and sidebar labels are all read from `config.yaml` instead of hardcoded, so the same code runs for a different retailer's data without a code change.
3. **The AI brief now uses a real LLM call, not just the deterministic fallback.** `generate_insight_brief_llm.py` sends the structured evidence to the OpenAI API (`gpt-4.1-mini`) and writes a candidate brief. This is what the dashboard shows by default now, not the deterministic-only version the original outline described.
4. **AI brief guardrails were substantially strengthened.** Beyond the original "use only computed numbers, one action per segment" checks, the validator now traces every number in the brief back to the structured JSON input (within 1.5% tolerance), scans for 12 causal-language trigger phrases, and requires a named human reviewer to approve the brief before it becomes the dashboard default. The approval record is committed to git so it persists across Streamlit Cloud redeploys. Live API generation is demo-safe by default: the button is visible, but disabled unless `SMARTCART_ENABLE_LIVE_AI=true` and an API key are configured.
5. **Leakage-free segment churn validation (V2) has concrete results worth a dedicated beat.** Using `segments_at_cutoff` (segments built only from pre-cutoff behavior), held-out validation shows Hibernating customers have an 81.2% future churn rate versus 12.8% for Champions, confirming historical segments are a legitimate action layer for churn risk without leaking future information into the grouping.
6. **A risk register now exists**, reframing churn label leakage explicitly as a technical risk (not operational) with the time-split design as its stated mitigation, addressing the professor's feedback directly.

## Updated Master Outline (20 min)

Format: Slides (with figures), switching to a dashboard screen recording per module.

1. **Problem and Context** (Xuechen, 1.5 min, slides): unchanged.
2. **Data and Pipeline** (Tia, 2 min, slides + brief repo view): add the config-driven scalability point.
3. **Customer Segmentation + CLV** (Xuechen, 3.5 min, slides to Segmentation page): unchanged.
4. **Churn Prediction + Purchase Propensity** (Tia, 3 min, slides to Churn + Purchase Likelihood pages): unchanged, numbers already verified live.
5. **Market Basket + Cohort Retention** (Tia, 2.5 min, slides to Market Basket + Cohort pages): unchanged, numbers already verified live.
6. **Group Comparison + Segment Churn Validation + AI Brief** (Xuechen, 3.5 min, slides to Group Insights + AI Brief pages): expanded to add the V2 segment churn validation result and the updated, LLM-plus-guardrails AI brief description (+0.5 min versus original).
7. **Limitations** (Xuechen, 1 min, slides): add the human-review-gate caveat for the AI brief.
8. **Impact and Close** (Both, 1.5 min, slides): strengthen with confirmed live deployment and config-driven generalizability.

Total: still 20 minutes (Group Comparison section absorbed the extra 0.5 min from a slightly tighter Data and Pipeline section).

---

## Slide-by-slide content

### 1. Problem and Context (Xuechen, 1.5 min)

- Small retailers manage customer analytics with a spreadsheet, or nothing at all.
- Enterprise tools (Salesforce, Klaviyo) cost thousands per month, out of reach for the long tail.
- SmartCart: free, open-source, runs on any retailer's own transaction CSV.

*No change from original; kept for continuity.*

### 2. Data and Pipeline (Tia, 2 min, slides + brief repo view)

- Online Retail II: 1,067,371 raw rows cleaned to 805,549, covering 5,878 customers, Dec 2009 to Dec 2011.
- SQLite as the single source of truth. Twelve Python modules run in a fixed, reproducible order.
- Every retailer-specific value (currency symbol, churn risk thresholds, dataset labels) is driven by one `config.yaml` file, not hardcoded. The same pipeline and dashboard can run on a different retailer's export without touching the code.
- Switch to dashboard: Overview page, show KPIs and revenue breakdown live.

**Speaker note:** Emphasize that the config-driven design is what makes this a reusable tool rather than a one-off analysis of a single dataset.

### 3. Customer Segmentation + CLV (Xuechen, 3.5 min, slides to Segmentation page)

- RFM feature engineering. K-Means with k=4, chosen by silhouette score.
- Four segments: Champions, Recent / Promising, At Risk High-Value, Hibernating.
- Baseline CLV versus BG/NBD probabilistic CLV. Note the P(alive) caveat for the Hibernating segment.
- One data-backed action per segment: this is the line between analytics and advice.
- Switch to dashboard: Segmentation page, scatter, CLV comparison, recommended actions.

*Carried over from the original outline and Xuechen's own slide draft; no factual changes needed here.*

### 4. Churn Prediction + Purchase Propensity (Tia, 3 min, slides to Churn + Purchase Likelihood pages)

- Churn: leakage-free time split. Features are computed before the cutoff date; the label is no purchase in the following 90 days. Test AUC: 0.802.
- 1,842 customers currently flagged high-risk on the live dashboard.
- Propensity: 30-day purchase-likelihood horizon. Test AUC: 0.787. The top 20% of customers by score captures 47% of actual buyers.
- Switch to dashboard: Churn Risk page (high-risk list), then Purchase Likelihood page (campaign budget planner).

**Speaker note:** If time allows, mention the risk-band thresholds (High, Medium, Low) are configurable in `config.yaml`, tying back to the pipeline slide's generalizability point.

### 5. Market Basket + Cohort Retention (Tia, 2.5 min, slides to Market Basket + Cohort pages)

- Apriori on 33,897 multi-item invoices. Rules split into Complete the Set versus Often Bought With. Strongest pairing shows a 25.4x lift over random chance.
- Cohort heatmap: average month-1 retention across all cohorts is 21.2%.
- Switch to dashboard: Market Basket page (product lookup), then Cohort page (retention heatmap).

*Numbers confirmed against the live dashboard during QA; unchanged from the original outline.*

### 6. Group Comparison + Segment Churn Validation + AI Brief (Xuechen, 3.5 min, slides to Group Insights + AI Brief pages)

- UK vs. Non-UK, Champions vs. Hibernating: observational comparisons with effect sizes, not causal claims.
- Leakage-free segment churn validation (new beat): using segments built only from pre-cutoff behavior, held-out results show Hibernating customers have an 81.2% future churn rate versus 12.8% for Champions. Historical segments hold up as a legitimate action layer for churn risk without leaking future information into the grouping.
- AI Brief (updated): the brief is now generated by an LLM (OpenAI, `gpt-4.1-mini`) from the same computed outputs, not the deterministic template alone. Guardrails trace every number in the brief back to the structured input within 1.5% tolerance, scan for causal-language phrasing, and require a named human reviewer to approve the brief before it becomes the dashboard default. The Generate / Refresh button shows the product workflow but is locked in demo-safe mode unless live API generation is explicitly enabled.
- Switch to dashboard: Group Insights page (Future Churn Validation tab), then AI Brief page (show the approved brief and the Guardrails tab).

**Speaker note:** The approval banner on the live AI Brief page ("reviewed and approved by Tia") is a good visual to point at directly during the demo, it makes the human-in-the-loop guardrail concrete rather than something described only in slides.

### 7. Limitations (Xuechen, 1 min, slides)

- Observational group comparisons cannot claim causality.
- BG/NBD P(alive) can overestimate survival for one-time buyers with no repeat-purchase history, most visible in the Hibernating segment.
- Static Dec 2009 to Dec 2011 dataset. Production use would require periodic retraining.
- The AI brief is a decision-support artifact, not a fully autonomous advisor. A named human reviewer must approve it before it is shown as the dashboard default.

### 8. Impact and Close (Both, 1.5 min, slides)

- Tia: Free and reproducible from one CSV. Deployed and publicly accessible on Streamlit Cloud, core analytics pages QA'd end-to-end against the live deployment, with a User Guide page added for non-technical users. GitHub repo and dashboard URL on screen.
- Xuechen: What SmartCart gives a retailer that a spreadsheet never could. Closing statement.

---

## Open items before this is final

- Xuechen should confirm the wording for sections 1, 3, 6, and 7, especially the new segment-churn-validation and AI-brief bullets in section 6.
- Timing for section 6 grew by about 0.5 minutes to fit the new content; double-check the full run-through still lands at 20 minutes.
- Confirm whether the 1,842 high-risk count and 21.2% month-1 retention figure should be re-pulled right before the recording, since both are live dashboard numbers that would shift slightly if the underlying data or model re-runs.
