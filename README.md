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
| Customer Lifetime Value | RFM-based CLV (baseline) + BG/NBD + Gamma-Gamma (probabilistic) | Online Retail II |
| Churn Prediction | Logistic Regression baseline + XGBoost | Online Retail II |
| Purchase-Propensity Prediction | Logistic Regression + XGBoost | Online Retail II |
| Product Recommendation | Market-basket analysis (Apriori / association rules) | Online Retail II |
| Customer Group Comparison | t-tests / chi-square with effect sizes | Online Retail II |
| AI Insight Brief | LLM-generated executive summary | All module outputs |

Primary dataset: **Online Retail II** (UCI / Kaggle). **Olist** is examined and kept in
reserve as a backup source.

## Tech Stack

Python (pandas, numpy, scikit-learn, XGBoost, mlxtend, lifetimes),
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

### Using the demo dataset (Online Retail II)

Download Online Retail II from Kaggle
(https://www.kaggle.com/datasets/mashlyn/online-retail-ii-uci) and place the file
in `data/` (raw data is not committed). The default `config.yaml` is already configured
for this dataset — no changes needed.

### Adapting SmartCart to your own data

SmartCart is designed to work with any retailer's transaction CSV without modifying Python
code. All dataset-specific settings live in `config.yaml` at the project root.

**1. Edit `config.yaml`** to match your CSV:

```yaml
company:
  name: "Your Company Name"
  currency_symbol: "$"      # shown throughout the dashboard

data:
  file: "data/your_file.csv"
  encoding: "utf-8"         # use "ISO-8859-1" for Windows-exported CSVs

columns:                    # map SmartCart's internal names to your column headers
  customer_id:  "CustomerID"
  invoice:      "OrderID"
  stock_code:   "SKU"
  description:  "ProductName"
  quantity:     "Qty"
  invoice_date: "OrderDate"
  price:        "UnitPrice"
  country:      "Country"

filters:
  min_quantity: 1           # rows below this are dropped (removes returns/cancellations)
  min_price: 0.0
```

Required columns are `customer_id`, `invoice`, `quantity`, `invoice_date`, and `price`.
`stock_code`, `description`, and `country` are used by the market-basket and group-comparison
modules but are not strictly required for segmentation and CLV.

**2. Upload and validate via the dashboard** (recommended):

```bash
streamlit run dashboard/app.py
```

Navigate to **Data Setup** in the sidebar. The page reads your `config.yaml`, lets you upload
your CSV, validates that all mapped columns are present, previews the cleaned data, and
runs `build_database.py` with one click.

**3. Or run the pipeline directly from the terminal** (see below).

## Reproducing the Analysis

Run the scripts in this order (each builds on the SQLite tables written by the previous step):

```bash
python src/build_database.py     # loads + cleans data, builds `transactions` and `rfm`
python src/segmentation_clv.py   # K-Means segments + baseline CLV -> `segments`, `clv`
python src/clv_bgnbd.py          # BG/NBD + Gamma-Gamma CLV enhancement -> `clv_bgnbd`
python src/churn_model.py        # leakage-free churn model (logistic + XGBoost)
python src/propensity_model.py   # leakage-free 30-day purchase propensity model -> `propensity_scores`
python src/market_basket.py      # Apriori association rules -> `association_rules`, `product_recommendations`
python src/group_comparison.py   # observational group tests -> `group_comparison_results`, `segment_comparison_summary`
python src/make_figures.py       # EDA / descriptive figures
python src/prepare_insight_inputs.py  # computed module outputs -> local structured JSON
python src/generate_insight_brief.py  # structured JSON -> reviewable Markdown insight brief draft
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
