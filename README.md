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

## Team

- Tian Qiu (Tia) — tian.qiu3@mail.mcgill.ca
- Xuechen Hong — xuechen.hong@mail.mcgill.ca

## AI Use

Generative AI tools were used to assist this project; see [AI_USE.md](AI_USE.md).

## License

[MIT](LICENSE)
