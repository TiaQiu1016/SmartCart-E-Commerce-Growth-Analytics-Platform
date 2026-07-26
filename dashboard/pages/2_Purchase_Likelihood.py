"""
Propensity Scoring page  30-day purchase propensity scores.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import (
    ACCENT,
    BLUE,
    CURRENCY,
    PLOTLY_LAYOUT,
    load_clv,
    load_propensity,
    load_segments,
    render_sidebar,
)

st.set_page_config(page_title="Purchase Likelihood - SmartCart", layout="wide")

st.markdown(
    f"""
    <style>
    h1, h2, h3 {{ color: {BLUE}; }}
    [data-testid="stMetric"] {{
        background: white; border-radius: 10px; padding: 16px 20px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    }}
    [data-testid="stMetricValue"] {{ color: {BLUE} !important; font-weight: 700; }}
    .stApp {{ background-color: #F5F7FA; }}
    </style>
    """,
    unsafe_allow_html=True,
)

render_sidebar()

st.title("Purchase Likelihood")
st.markdown(
    "Which customers are most likely to buy again in the next 30 days? "
    "SmartCart analyzes each customer's purchase history to score their likelihood of returning. "
    "The top 20% of customers by score account for **47% of all actual buyers**; "
    "use the Campaign Budget Planner below to decide how many to target."
)

#  data
try:
    propensity = load_propensity()
except Exception:
    st.error("Purchase-likelihood scores are not available yet. Ask an admin to refresh SmartCart outputs before opening this page.")
    st.stop()
segments = load_segments()
clv = load_clv()

full = (
    propensity.merge(segments[["customer_id", "segment", "recency_days", "frequency", "monetary"]], on="customer_id")
    .merge(clv[["customer_id", "clv_estimate"]], on="customer_id")
)
full["score_pct"] = full["propensity_score"].rank(pct=True)
full["score_decile"] = (full["score_pct"] * 10).clip(upper=10).astype(int).clip(lower=1)

n_total = len(full)

#  KPI row
k1, k2, k3, k4 = st.columns(4)
k1.metric("Customers Scored", f"{n_total:,}")
k2.metric("Model Quality", "78.7%", help="How well SmartCart separates likely buyers from unlikely buyers")
k3.metric("Top 20% Capture Rate", "47%", help="The top 20% by score account for 47% of customers who actually bought")
k4.metric("Targeting Lift", "2.3x", help="Targeting the top 20% is 2.3x more effective than targeting customers at random")

st.divider()

#  score distribution
col1, col2 = st.columns(2)

with col1:
    st.subheader("Customer Score Distribution")
    fig1 = px.histogram(
        full,
        x="propensity_score",
        nbins=40,
        color_discrete_sequence=[BLUE],
        labels={"propensity_score": "Propensity Score (0-1)"},
    )
    fig1.add_vline(x=0.5, line_dash="dash", line_color=ACCENT,
                   annotation_text="0.5 threshold", annotation_position="top right")
    fig1.update_layout(**PLOTLY_LAYOUT, yaxis_title="Customers")
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    st.subheader("Score by Segment")
    palette = {
        "Champions": BLUE,
        "Recent / Promising": "#4A90C4",
        "At Risk High-Value": ACCENT,
        "Hibernating": "#999999",
    }
    fig2 = px.box(
        full,
        x="segment",
        y="propensity_score",
        color="segment",
        color_discrete_map=palette,
        points=False,
    )
    fig2.update_layout(**PLOTLY_LAYOUT, showlegend=False, xaxis_title=None,
                       yaxis_title="Propensity Score")
    st.plotly_chart(fig2, use_container_width=True)

#  decile lift chart
st.subheader("Customer Ranking by Score")
st.markdown("Rank customers by purchase-likelihood score. Group 10 contains the customers most likely to buy again.")

decile_avg = (
    full.groupby("score_decile")["propensity_score"]
    .mean()
    .reset_index()
    .sort_values("score_decile")
)

colors = [ACCENT if d >= 8 else BLUE for d in decile_avg["score_decile"]]
fig3 = px.bar(
    decile_avg,
    x="score_decile",
    y="propensity_score",
    color_discrete_sequence=[BLUE],
    labels={"score_decile": "Score Decile (10 = highest)", "propensity_score": "Avg Propensity Score"},
    text=decile_avg["propensity_score"].map("{:.2f}".format),
)
fig3.update_traces(marker_color=colors, textposition="outside")
fig3.update_layout(**PLOTLY_LAYOUT)
st.plotly_chart(fig3, use_container_width=True)

#  campaign threshold selector
st.subheader("Campaign Budget Planner")
st.markdown("Select a targeting threshold to see how many customers you would reach.")

THRESHOLDS = {
    "Top 10% (tightest targeting)": 0.90,
    "Top 20% (recommended)": 0.80,
    "Top 30% (broad reach)": 0.70,
    "Score >= 0.5 (majority rule)": 0.50,
}

budget_choice = st.selectbox("Budget level", list(THRESHOLDS.keys()))
pct_cutoff = THRESHOLDS[budget_choice]
score_cutoff = full["propensity_score"].quantile(pct_cutoff)
targeted = full[full["propensity_score"] >= score_cutoff]

t1, t2, t3 = st.columns(3)
t1.metric("Targeted Customers", f"{len(targeted):,}")
t2.metric("Minimum Score", f"{score_cutoff:.3f}")
t3.metric("Avg Customer Value in Target Group", f"{CURRENCY}{targeted['clv_estimate'].mean():,.0f}")

seg_counts = targeted["segment"].value_counts().reset_index()
seg_counts.columns = ["Segment", "Customers"]
fig4 = px.bar(
    seg_counts,
    x="Segment",
    y="Customers",
    color_discrete_sequence=[BLUE],
    text="Customers",
    title="Segment Breakdown in Target Group",
)
fig4.update_traces(textposition="outside")
fig4.update_layout(**PLOTLY_LAYOUT, xaxis_title=None)
st.plotly_chart(fig4, use_container_width=True)

#  top customers table
st.subheader("Top Customers to Contact")
top50 = (
    full.nlargest(50, "propensity_score")[
        ["customer_id", "propensity_score", "segment", "recency_days", "frequency", "monetary", "clv_estimate"]
    ].copy()
)
top50.columns = ["Customer ID", "Propensity Score", "Segment", "Recency (days)", "Orders", f"Revenue ({CURRENCY})", f"CLV ({CURRENCY})"]
top50["Propensity Score"] = top50["Propensity Score"].map("{:.3f}".format)
top50[f"Revenue ({CURRENCY})"] = top50[f"Revenue ({CURRENCY})"].map(lambda v: f"{CURRENCY}{v:,.0f}")
top50[f"CLV ({CURRENCY})"] = top50[f"CLV ({CURRENCY})"].map(lambda v: f"{CURRENCY}{v:,.0f}")
st.dataframe(top50, use_container_width=True, hide_index=True)

st.divider()
st.caption(
    "Scores are based on each customer's past purchase recency, frequency, revenue, tenure, "
    "average basket size, and regularity of orders. 30-day likelihood horizon."
)
