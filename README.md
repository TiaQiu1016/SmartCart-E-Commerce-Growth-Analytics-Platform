# SmartCart

**An AI-Powered E-Commerce Growth Analytics Platform for Small & Mid-Sized Online Retailers**

SmartCart turns a retailer's own transaction data into actionable marketing intelligence —
customer segmentation, lifetime value, churn signals, product recommendations, and a
plain-language AI growth brief — as a free, open-source alternative to expensive enterprise
analytics tools.

BUSA 649 Community Analytics Project (Summer 2026) · McGill Desautels MMA.

## Modules

| Module | Method | Dataset |
| --- | --- | --- |
| Customer Segmentation | RFM + K-Means | Online Retail II |
| Customer Lifetime Value | RFM-based CLV (BG/NBD + Gamma-Gamma if time allows) | Online Retail II |
| Churn Prediction | Logistic Regression baseline + XGBoost | Online Retail II |
| Purchase-Propensity Prediction | Logistic Regression + XGBoost | Online Retail II |
| Product Recommendation | Market-basket analysis (Apriori / association rules) | Online Retail II |
| Customer Group Comparison | t-tests / chi-square with effect sizes | Online Retail II |
| AI Insight Brief | LLM-generated executive summary | All module outputs |

Primary dataset: **Online Retail II** (UCI / Kaggle). **Olist** is examined and kept in
reserve as a backup source.

## Tech Stack

Python (pandas, numpy, scikit-learn, XGBoost, mlxtend, optionally lifetimes),
SQLite for the SQL data layer and aggregation, Plotly + Streamlit for the dashboard,
an LLM API (such as Claude) for AI-generated briefs, and GitHub for version control.

## Repository Structure

```
data/        # local data (not committed; see .gitignore)
sql/         # SQL scripts: schema, RFM aggregation, cohorts
notebooks/   # exploration and modelling notebooks
src/         # reusable Python modules
dashboard/   # Streamlit app
reports/     # progress reports and final technical report
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Download Online Retail II from Kaggle
(https://www.kaggle.com/datasets/mashlyn/online-retail-ii-uci) and place the cleaned file
in `data/` (raw data is not committed).

## Reproducing the Analysis

Run the scripts in this order (each builds on the SQLite tables written by the previous step):

```bash
python src/build_database.py     # loads + cleans data, builds `transactions` and `rfm`
python src/segmentation_clv.py   # K-Means segments + baseline CLV -> `segments`, `clv`
python src/churn_model.py        # leakage-free churn model (logistic + XGBoost)
python src/make_figures.py       # EDA / descriptive figures
```

SQL scripts in `sql/` can be run standalone, e.g. `sqlite3 data/smartcart.db < sql/eda_summary.sql`.

**Two things to read correctly:**

- *Segmentation:* the authoritative segments come from K-Means (`segments` table,
  `segmentation_clv.py`). The SQL quartile version (`rfm_scored`, from `sql/rfm_segments.sql`)
  is a transparent baseline cross-check, not the production segmentation.
- *Churn:* two distinct definitions are intentional. The descriptive churn split
  (`churn_split.png`, from `sql/churn_labels.sql`) is a 90-day **recency snapshot** of who is
  currently inactive. The churn **model** (`churn_model.py`) uses a leakage-free time split
  (features before a cutoff, label = no purchase in the following 90 days). The two percentages
  differ because they measure different things.

## Team

- Tian Qiu (Tia) — tian.qiu3@mail.mcgill.ca
- Xuechen Hong — xuechen.hong@mail.mcgill.ca

## AI Use

Generative AI tools were used to assist this project; see [AI_USE.md](AI_USE.md).

## License

[MIT](LICENSE)
