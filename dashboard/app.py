"""
SmartCart — AI-Powered E-Commerce Growth Analytics Dashboard
Overview / landing page.
Usage: streamlit run dashboard/app.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import plotly.express as px
import streamlit as st

from utils import (
    ACCENT,
    BLUE,
    CURRENCY,
    PLOTLY_LAYOUT,
    load_clv,
    load_segment_profiles,
    load_segment_summary,
    load_segments,
    load_transactions_summary,
    render_sidebar,
)

st.set_page_config(
    page_title="SmartCart Analytics",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    f"""
    <style>
    h1, h2, h3 {{ color: {BLUE}; }}
    [data-testid="stMetric"] {{
        background: white;
        border-radius: 10px;
        padding: 16px 20px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    }}
    [data-testid="stMetricValue"] {{ color: {BLUE} !important; font-weight: 700; font-size: 1.4rem !important; }}
    [data-testid="stMetricLabel"] {{ color: #666; font-size: 0.8rem; }}
    .stApp {{ background-color: #F5F7FA; }}
    .block-container {{ padding-top: 2rem; }}
    </style>
    """,
    unsafe_allow_html=True,
)

render_sidebar()

# ── data ─────────────────────────────────────────────────────────────────────
summary = load_transactions_summary()
segments = load_segments()
clv = load_clv()
profiles = load_segment_profiles()
seg_summary = load_segment_summary()

repeat_pct = 100 * summary["repeat_customers"] / summary["n_customers"]
avg_clv = clv["clv_estimate"].mean()

# ── header ────────────────────────────────────────────────────────────────────
st.markdown(f"# SmartCart Growth Analytics")
st.markdown(
    "Turn transaction data into segmentation, lifetime value, churn signals, "
    "product recommendations, and group insights — all from a single SQLite database."
)
st.divider()

# ── KPI row ───────────────────────────────────────────────────────────────────
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Customers", f"{summary['n_customers']:,}")
k2.metric("Total Revenue", f"{CURRENCY}{summary['total_revenue']/1_000_000:.1f}M")
k3.metric("Total Invoices", f"{summary['n_invoices']:,}")
k4.metric("Repeat Customer Rate", f"{repeat_pct:.1f}%")
k5.metric("Avg Baseline CLV", f"{CURRENCY}{avg_clv:,.0f}", help="RFM-based baseline estimate. See Segmentation page for BG/NBD CLV.")

st.divider()

# ── charts row ───────────────────────────────────────────────────────────────
col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("Customers by Segment")
    order = profiles.sort_values("customers", ascending=False)["segment"].tolist()
    fig_seg = px.bar(
        profiles.sort_values("customers", ascending=False),
        x="segment",
        y="customers",
        color_discrete_sequence=[BLUE],
        text="customers",
    )
    fig_seg.update_traces(textposition="outside")
    fig_seg.update_layout(
        **PLOTLY_LAYOUT,
        xaxis_title=None,
        yaxis_title="Customers",
        showlegend=False,
    )
    st.plotly_chart(fig_seg, use_container_width=True)

with col_right:
    st.subheader("Revenue Distribution by Segment")
    seg_rev = (
        segments[["customer_id", "segment"]]
        .merge(clv[["customer_id", "monetary"]], on="customer_id")
        .groupby("segment", as_index=False)["monetary"]
        .sum()
        .sort_values("monetary", ascending=False)
    )
    fig_rev = px.pie(
        seg_rev,
        names="segment",
        values="monetary",
        color_discrete_sequence=[BLUE, ACCENT, "#4A90C4", "#E8C07D", "#8AB4C8"],
        hole=0.45,
    )
    fig_rev.update_traces(textposition="outside", textinfo="percent+label")
    fig_rev.update_layout(**PLOTLY_LAYOUT, showlegend=False)
    st.plotly_chart(fig_rev, use_container_width=True)

# ── segment summary table ─────────────────────────────────────────────────────
st.subheader("Segment At-a-Glance")

display_cols = {
    "segment": "Segment",
    "customers": "Customers",
    "avg_recency_days": "Avg Recency (days)",
    "avg_frequency": "Avg Orders",
    "avg_monetary": "Avg Revenue (£)",
    "avg_clv_estimate": "Avg CLV (£)",
    "churn_rate_snapshot": "Inactive Rate",
    "uk_share": "UK Share",
}
tbl = seg_summary[list(display_cols.keys())].rename(columns=display_cols).copy()
tbl["Avg Revenue (£)"] = tbl["Avg Revenue (£)"].map(lambda v: f"{CURRENCY}{v:,.0f}")
tbl["Avg CLV (£)"] = tbl["Avg CLV (£)"].map(lambda v: f"{CURRENCY}{v:,.0f}")
tbl["Avg Recency (days)"] = tbl["Avg Recency (days)"].map("{:.0f}".format)
tbl["Avg Orders"] = tbl["Avg Orders"].map("{:.1f}".format)
tbl["Inactive Rate"] = (seg_summary["churn_rate_snapshot"] * 100).map("{:.1f}%".format)
tbl["UK Share"] = (seg_summary["uk_share"] * 100).map("{:.1f}%".format)
tbl = tbl.sort_values("Customers", ascending=False)

st.dataframe(tbl, use_container_width=True, hide_index=True)

st.divider()
st.caption(
    "Data: Online Retail II (UCI / Kaggle, CC BY 4.0) · Dec 2009 – Dec 2011 · "
    "805,549 cleaned transactions · BUSA 649, McGill Desautels MMA"
)
