# SmartCart Dashboard — User Guide

This guide explains what each page of the SmartCart dashboard shows and how to act on it.
It is written for a non-technical retailer, not a data scientist.

---

## How to run the dashboard

```bash
pip install -r requirements.txt
streamlit run dashboard/app.py
```

Then open the URL printed in your terminal (usually `http://localhost:8501`).
Use the sidebar to navigate between pages.

---

## Page 0 — Data Setup

**What it does:** Onboards your own transaction data into SmartCart.

**Steps:**
1. Edit `config.yaml` to map your CSV column names (e.g. your "OrderID" becomes SmartCart's
   "invoice"). The current configuration is displayed live so you can confirm it looks right.
2. Upload your CSV. The page reads a sample, checks that all required columns are present,
   and shows a preview of the cleaned data.
3. Click "Run build_database.py" to process the file, or copy the terminal commands shown
   at the bottom and run the full pipeline yourself.

**Required columns:** customer ID, invoice/order ID, quantity, date, and unit price.
Country, product code, and description are optional but enable the market-basket and
group-comparison modules.

---

## Page 1 — Segmentation

**What it does:** Divides all customers into four groups based on how recently they bought,
how often they buy, and how much they spend. The groups are derived from a K-Means clustering
model, not arbitrary labels.

**The four segments:**

| Segment | Who they are | What to do |
| --- | --- | --- |
| Champions | Bought recently, buy often, spend a lot | Reward loyalty; use them to test new products |
| Recent / Promising | Bought recently but not yet frequent | Nurture with onboarding sequences to build habit |
| At Risk High-Value | Were high spenders but haven't bought recently | Win-back campaign before they lapse permanently |
| Hibernating | Long inactive, low frequency | Low-cost re-engagement or accept as churned |

**How to read the RFM scatter chart:** each dot is one customer. Dots in the top-left
(high frequency, low recency days) are active, frequent buyers. Dots in the bottom-right
(low frequency, high recency days) are dormant.

**Recommended actions:** the colored cards below the charts show one specific, data-backed
action for each segment derived from that segment's average RFM profile.

**BG/NBD section (if available):** shows a probabilistic CLV alongside the simpler baseline.
P(alive) is the model's estimate of whether a customer has permanently churned. Note that
customers with only one purchase always show P(alive) = 1.0 — this is a known limitation of
the model, not a meaningful signal. The info box on the page explains this.

---

## Page 2 — Propensity Scoring

**What it does:** Scores every customer from 0 to 1 on the probability they will make a
purchase in the next 30 days. Built with an XGBoost model (test AUC: 0.787).

**How to use it:**

- **Campaign Budget Planner:** choose how much of your customer base you can afford to contact.
  The page shows the score cutoff, how many customers that reaches, and their average lifetime
  value. "Top 20%" is the recommended starting point — it captures 47% of all likely buyers
  at 2.3x the hit rate of a random mailing.
- **Top 50 table:** the highest-scoring customers by name, with their segment and CLV visible
  so you can prioritize outreach.

**What the score means:** a score of 0.80 means the model estimates an 80% chance the
customer buys something in the next 30 days based on their purchase history. It does not
guarantee a purchase.

**What it does not do:** the model uses transaction history only — it cannot see whether a
customer opened an email, visited the website, or saw an ad. Those signals would improve
accuracy further.

---

## Page 3 — Market Basket

**What it does:** Finds products that are frequently bought together and turns them into
cross-sell recommendations.

**How to read the rules table:**

- **Support:** how common this product pair is across all orders. 0.03 means 3% of all
  invoices contain both products.
- **Confidence:** given a customer bought product A, how often did they also buy product B.
  0.65 means 65% of customers who bought A also bought B.
- **Lift:** how much more likely the pair is compared to random chance. Lift of 10 means
  the products are bought together 10x more than you'd expect if buying habits were unrelated.
  Anything above 1.5 is a real association.

**Two types of rules:**

- **Often Bought With:** different product types that customers combine. Use these for
  "you might also like" recommendations or bundle promotions.
- **Complete the Set:** color or size variants of the same product line. Use these to
  suggest the matching variant ("also available in green") rather than a cross-sell.

**Product lookup:** select any product from the dropdown to see its variant pairings
("Complete the Set") and cross-category recommendations ("Often Bought With"), each with
confidence, lift, and support scores. Use the Rule Explorer tab to filter the full rule set
by type and minimum lift.

---

## Page 4 — Group Insights

**What it does:** Statistically tests whether different customer groups behave differently,
with effect sizes to tell you whether a difference is practically meaningful (not just
statistically significant due to sample size).

**UK vs. Non-UK tab:** compares the 4,372 UK customers to the 1,506 from other countries
on recency, purchase frequency, revenue, and CLV. Cohen's d tells you the magnitude:

- d < 0.2: negligible difference
- d 0.2–0.5: small but noticeable
- d 0.5–0.8: medium, worth acting on
- d > 0.8: large

**Champions vs. Hibernating tab:** confirms that the segmentation model's groups are
genuinely distinct, not just labels on a continuous spectrum.

**Segment Profiles tab:** a single table showing all four segments side-by-side. Use it
to quickly compare average revenue, CLV, inactive rate, and UK share across segments.

**Important note:** these are observational comparisons of historical data, not randomized
experiments. A statistically significant difference between groups tells you the groups are
distinct — it does not prove that geography or segment membership *caused* the difference.

---

## Overview page

The landing page shows five top-line KPIs (total customers, total revenue, total invoices,
repeat customer rate, average CLV) and a revenue distribution by segment. It is designed as
an executive summary — use it to orient stakeholders before drilling into individual pages.

---

## Frequently asked questions

**Why does the revenue on the Overview page show "£" but my data uses "$"?**
Change `currency_symbol` in `config.yaml` and reload the dashboard.

**A segment shows "—" or a chart is blank. What happened?**
The pipeline script that produces that module's output has not been run yet, or the SQLite
table is missing. Check the Data Setup page and run the missing scripts.

**The propensity scores look low for customers I expect to be active buyers. Why?**
The model scores customers relative to each other on a 0-to-1 scale. A score of 0.4 in a
population where most customers have scores below 0.3 is still a relatively high-propensity
customer. Use the decile chart to read scores in context, not in isolation.

**What does "inactive rate" mean in the Segment Profiles table?**
It is a descriptive snapshot: the share of customers in that segment who have not purchased
in the last 90 days at the time the pipeline was run. It is not the output of the churn
prediction model.
