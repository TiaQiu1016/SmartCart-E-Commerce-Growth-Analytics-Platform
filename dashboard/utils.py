"""Shared data-loading helpers for the SmartCart Streamlit dashboard."""

from pathlib import Path
import sqlite3

import pandas as pd
import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parents[1]
_deploy_db = ROOT / "data" / "smartcart_deploy.db"
_local_db  = ROOT / "data" / "smartcart.db"
DB_PATH = _deploy_db if _deploy_db.exists() else _local_db
CONFIG_PATH = ROOT / "config.yaml"

BLUE = "#234A70"
ACCENT = "#E08A3C"


def _read_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f)
    return {}


CONFIG = _read_config()
CURRENCY = CONFIG.get("company", {}).get("currency_symbol", "GBP ")
COMPANY_NAME = CONFIG.get("company", {}).get("name", "SmartCart")
CHURN_HIGH = float(CONFIG.get("models", {}).get("churn_high_risk_threshold", 0.75))
CHURN_MEDIUM = float(CONFIG.get("models", {}).get("churn_medium_risk_threshold", 0.50))
COURSE_LABEL = CONFIG.get("project", {}).get("course", "")
DATA_SOURCE = CONFIG.get("project", {}).get("data_source", "")


@st.cache_data
def _sidebar_customer_count() -> int:
    try:
        with sqlite3.connect(DB_PATH) as con:
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "transactions_summary" in tables:
                row = con.execute("SELECT n_customers FROM transactions_summary").fetchone()
            elif "segments" in tables:
                row = con.execute("SELECT COUNT(DISTINCT customer_id) FROM segments").fetchone()
            else:
                return 0
            return int(row[0]) if row else 0
    except Exception:
        return 0


def render_sidebar() -> None:
    """Consistent SmartCart branding and shared CSS for every page."""
    st.markdown(
        f"""
        <style>
        [data-testid="stSidebar"] {{ background-color: {BLUE}; }}
        [data-testid="stSidebar"] * {{ color: white !important; }}
        [data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,0.2); }}
        h1, h2, h3 {{ color: {BLUE}; }}
        .stApp {{ background-color: #F5F7FA; }}
        [data-testid="stMetric"] {{
            background: white; border-radius: 10px; padding: 16px 20px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.08);
        }}
        [data-testid="stMetricValue"] {{
            color: {BLUE} !important; font-weight: 700; font-size: 1.4rem !important;
        }}
        [data-testid="stMetricLabel"] {{ color: #666; font-size: 0.8rem; }}
        .block-container {{ padding-top: 2rem; }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    with st.sidebar:
        st.markdown("## SmartCart")
        st.markdown("**Retail Growth Dashboard**")
        st.divider()
        n_customers = _sidebar_customer_count()
        customer_label = f"{n_customers:,} customers" if n_customers else "-"
        dataset_label = DATA_SOURCE.split("(")[0].strip() if DATA_SOURCE else COMPANY_NAME
        st.caption(f"{dataset_label} - {customer_label}")
        # Keep academic/project labels out of the customer-facing dashboard.
        st.divider()
        st.caption("Use the pages above to review customer groups, churn risk, product opportunities, and the AI summary.")


PLOTLY_LAYOUT = dict(
    plot_bgcolor="white",
    paper_bgcolor="white",
    font=dict(color="#333333"),
    margin=dict(l=40, r=20, t=40, b=40),
)


@st.cache_data
def load_segments() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as con:
        return pd.read_sql("SELECT * FROM segments", con)


@st.cache_data
def load_clv() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as con:
        return pd.read_sql("SELECT * FROM clv", con)


@st.cache_data
def load_segment_profiles() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as con:
        return pd.read_sql("SELECT * FROM segment_profiles", con)


@st.cache_data
def load_propensity() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as con:
        return pd.read_sql("SELECT * FROM propensity_scores", con)


@st.cache_data
def load_churn_scores() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as con:
        return pd.read_sql("SELECT * FROM churn_scores", con)


@st.cache_data
def load_association_rules() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as con:
        return pd.read_sql("SELECT * FROM association_rules", con)


@st.cache_data
def load_recommendations() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as con:
        return pd.read_sql("SELECT * FROM product_recommendations", con)


@st.cache_data
def load_group_comparison() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as con:
        return pd.read_sql("SELECT * FROM group_comparison_results", con)


@st.cache_data
def load_segment_churn_v2_summary() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as con:
        return pd.read_sql(
            """
            SELECT *
            FROM segment_churn_v2_summary
            ORDER BY validation_scope, actual_future_churn_rate DESC
            """,
            con,
        )


@st.cache_data
def load_segment_churn_v2_results() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as con:
        return pd.read_sql("SELECT * FROM segment_churn_v2_results", con)


@st.cache_data
def load_clv_bgnbd() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as con:
        return pd.read_sql("SELECT * FROM clv_bgnbd", con)


@st.cache_data
def load_cohort_retention() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as con:
        return pd.read_sql("SELECT * FROM cohort_retention", con)


@st.cache_data
def load_cohort_revenue() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as con:
        return pd.read_sql("SELECT * FROM cohort_revenue", con)


@st.cache_data
def load_segmentation_metrics() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as con:
        return pd.read_sql("SELECT * FROM segmentation_metrics ORDER BY k", con)


@st.cache_data
def load_segment_summary() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as con:
        return pd.read_sql("SELECT * FROM segment_comparison_summary", con)


@st.cache_data
def load_transactions_summary() -> dict:
    with sqlite3.connect(DB_PATH) as con:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "transactions_summary" in tables:
            row = pd.read_sql("SELECT * FROM transactions_summary", con).iloc[0]
        else:
            row = pd.read_sql(
                """
                SELECT
                    COUNT(DISTINCT customer_id) AS n_customers,
                    SUM(revenue)               AS total_revenue,
                    COUNT(DISTINCT invoice)    AS n_invoices,
                    COUNT(DISTINCT stock_code) AS n_products
                FROM transactions
                """,
                con,
            ).iloc[0]
        repeat = pd.read_sql(
            "SELECT COUNT(*) AS n FROM segments WHERE frequency > 1", con
        ).iloc[0, 0]
    return {
        "n_customers": int(row["n_customers"]),
        "total_revenue": float(row["total_revenue"]),
        "n_invoices": int(row["n_invoices"]),
        "n_products": int(row["n_products"]),
        "repeat_customers": int(repeat),
    }
