"""
poc_streamlit/app.py

Streamlit prototype for the SmartCart dashboard platform evaluation.
Pulls live data from data/smartcart.db (segments, clv, segment_profiles)
and renders the same content as poc_dash/app.py, for a hands-on comparison.

Usage:
    streamlit run dashboard/poc_streamlit/app.py
"""

from pathlib import Path
import sqlite3

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "smartcart.db"
BLUE, ACCENT = "#234A70", "#E08A3C"

st.set_page_config(page_title="SmartCart POC — Streamlit", layout="wide")

st.markdown(
    f"""
    <style>
    .stApp {{ background-color: #FAFAFA; }}
    h1, h2, h3 {{ color: {BLUE}; }}
    [data-testid="stMetric"] {{
        background-color: white; border-radius: 8px; padding: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def load_data():
    with sqlite3.connect(DB_PATH) as con:
        segments = pd.read_sql("SELECT * FROM segments", con)
        clv = pd.read_sql("SELECT * FROM clv", con)
        profile = pd.read_sql("SELECT * FROM segment_profiles", con)
    return segments, clv, profile


segments, clv, profile = load_data()
clv_seg = (
    segments[["customer_id", "segment"]]
    .merge(clv[["customer_id", "clv_estimate"]], on="customer_id")
    .groupby("segment", as_index=False)["clv_estimate"]
    .mean()
    .sort_values("clv_estimate", ascending=False)
)

st.title("SmartCart — Customer Segments (Streamlit POC)")

c1, c2, c3 = st.columns(3)
c1.metric("Total Customers", f"{len(segments):,}")
c2.metric("Total Revenue", f"${clv['monetary'].sum():,.0f}")
c3.metric("Avg CLV Estimate", f"${clv['clv_estimate'].mean():,.0f}")

st.divider()

col1, col2 = st.columns(2)
with col1:
    st.subheader("Customers by Segment")
    fig1 = px.bar(
        profile.sort_values("customers", ascending=False),
        x="segment", y="customers", color_discrete_sequence=[BLUE],
    )
    fig1.update_layout(plot_bgcolor="white", paper_bgcolor="white")
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    st.subheader("Avg CLV by Segment")
    fig2 = px.bar(
        clv_seg, x="segment", y="clv_estimate", color_discrete_sequence=[ACCENT],
    )
    fig2.update_layout(plot_bgcolor="white", paper_bgcolor="white")
    st.plotly_chart(fig2, use_container_width=True)

st.subheader("Segment Profiles")
st.dataframe(profile, use_container_width=True)
