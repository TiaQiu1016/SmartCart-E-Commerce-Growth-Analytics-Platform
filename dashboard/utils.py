"""Shared data-loading helpers for the SmartCart Streamlit dashboard."""

from pathlib import Path
import sqlite3

import pandas as pd
import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "smartcart.db"
CONFIG_PATH = ROOT / "config.yaml"

BLUE = "#234A70"
ACCENT = "#E08A3C"


def _read_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f)
    return {}


CONFIG = _read_config()
CURRENCY = CONFIG.get("company", {}).get("currency_symbol", "£")
COMPANY_NAME = CONFIG.get("company", {}).get("name", "SmartCart")

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
def load_clv_bgnbd() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as con:
        return pd.read_sql("SELECT * FROM clv_bgnbd", con)


@st.cache_data
def load_segment_summary() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as con:
        return pd.read_sql("SELECT * FROM segment_comparison_summary", con)


@st.cache_data
def load_transactions_summary() -> dict:
    with sqlite3.connect(DB_PATH) as con:
        row = pd.read_sql(
            """
            SELECT
                COUNT(DISTINCT customer_id) AS n_customers,
                SUM(revenue) AS total_revenue,
                COUNT(DISTINCT invoice) AS n_invoices,
                COUNT(DISTINCT stock_code) AS n_products
            FROM transactions
            """,
            con,
        ).iloc[0]
    repeat = pd.read_sql(
        "SELECT COUNT(*) AS n FROM segments WHERE frequency > 1",
        sqlite3.connect(DB_PATH),
    ).iloc[0, 0]
    return {
        "n_customers": int(row["n_customers"]),
        "total_revenue": float(row["total_revenue"]),
        "n_invoices": int(row["n_invoices"]),
        "n_products": int(row["n_products"]),
        "repeat_customers": int(repeat),
    }
