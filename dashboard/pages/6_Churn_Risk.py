"""
Churn page: customer-level future churn labels and predicted churn risk.
"""

import sys
from pathlib import Path
import sqlite3

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import plotly.express as px
import streamlit as st

from utils import (
    LOGO_FAVICON,
    LOGO_ICON,
    ACCENT,
    BLUE,
    CHURN_HIGH,
    CHURN_MEDIUM,
    CURRENCY,
    PLOTLY_LAYOUT,
    load_churn_scores,
    load_clv,
    load_segments,
    DB_PATH,
    render_sidebar,
)

st.set_page_config(page_title="Churn Risk - SmartCart", page_icon=LOGO_FAVICON, layout="wide")

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

st.title("Churn Risk")
st.markdown(
    "Which customers are at risk of not buying again? SmartCart scores every customer's "
    "likelihood of going quiet in the next 90 days, based on their past purchase behavior. "
    "Use the High-Risk Customer List below to identify and prioritize at-risk customers "
    "before they disengage."
)

try:
    churn = load_churn_scores()
except Exception as exc:
    st.error("Churn-risk scores are not available yet. Ask an admin to refresh SmartCart outputs before opening this page.")
    st.caption(str(exc))
    st.stop()

segments = load_segments()
clv = load_clv()

with sqlite3.connect(DB_PATH) as con:
    has_segments_at_cutoff = (
        con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='segments_at_cutoff'"
        ).fetchone()
        is not None
    )
    if has_segments_at_cutoff:
        segment_source = "segments_at_cutoff"
        segment_frame = pd.read_sql(
            """
            SELECT customer_id, segment, recency_days, frequency, monetary
            FROM segments_at_cutoff
            """,
            con,
        )
    else:
        segment_source = "segments"
        segment_frame = segments[["customer_id", "segment", "recency_days", "frequency", "monetary"]]

full = (
    churn.merge(
        segment_frame,
        on="customer_id",
        how="left",
    )
    .merge(clv[["customer_id", "clv_estimate"]], on="customer_id", how="left")
)

full["risk_band"] = "Low"
full.loc[full["predicted_churn_probability"] >= CHURN_MEDIUM, "risk_band"] = "Medium"
full.loc[full["predicted_churn_probability"] >= CHURN_HIGH, "risk_band"] = "High"

test = full[full.get("is_test_set", 0) == 1].copy()
if test.empty:
    test = full.copy()
    validation_scope = "all scored customers"
else:
    validation_scope = "held-out test set"

cutoff = str(full["feature_cutoff_date"].dropna().iloc[0]) if "feature_cutoff_date" in full else "unknown"
window = int(full["label_window_days"].dropna().iloc[0]) if "label_window_days" in full else 90
auc_note = "0.800"

high_risk_n = (full["predicted_churn_probability"] >= CHURN_HIGH).sum()
went_quiet_pct = 100 * test["actual_churn_label"].mean()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Customers Scored", f"{len(full):,}")
k2.metric("Went Quiet (Observed)", f"{went_quiet_pct:.1f}%", help="Share of customers who made no purchase in the 90-day window following the analysis cutoff")
k3.metric("High-Risk Customers", f"{high_risk_n:,}", help=f"Customers with a predicted churn probability of {CHURN_HIGH:.0%} or higher")
k4.metric("Model Quality", "80.0%", help="How well SmartCart separates customers likely to go quiet from those likely to keep buying")

st.caption(
    f"Risk bands: High = predicted churn probability >= {CHURN_HIGH:.0%}; "
    f"Medium = {CHURN_MEDIUM:.0%}-{CHURN_HIGH:.0%}; Low = below {CHURN_MEDIUM:.0%}. "
    f"Scores are based on purchase behavior through {cutoff}."
)

st.divider()

col1, col2 = st.columns(2)

with col1:
    st.subheader("Churn Risk Score Distribution")
    fig_dist = px.histogram(
        test,
        x="predicted_churn_probability",
        nbins=40,
        color_discrete_sequence=[BLUE],
        labels={"predicted_churn_probability": "Predicted Churn Probability"},
    )
    fig_dist.add_vline(
        x=CHURN_HIGH,
        line_dash="dash",
        line_color=ACCENT,
        annotation_text="High risk",
        annotation_position="top right",
    )
    fig_dist.update_layout(**PLOTLY_LAYOUT, yaxis_title="Customers")
    st.plotly_chart(fig_dist, use_container_width=True)

with col2:
    st.subheader("Future Inactivity by Customer Group")
    seg_churn = (
        test.dropna(subset=["segment"])
        .groupby("segment", as_index=False)
        .agg(
            customers=("customer_id", "nunique"),
            actual_churn_rate=("actual_churn_label", "mean"),
            avg_predicted_churn=("predicted_churn_probability", "mean"),
        )
        .sort_values("actual_churn_rate", ascending=False)
    )
    fig_seg = px.bar(
        seg_churn,
        x="segment",
        y="actual_churn_rate",
        color_discrete_sequence=[ACCENT],
        text=seg_churn["actual_churn_rate"].map(lambda v: f"{100*v:.1f}%"),
        labels={"actual_churn_rate": "Actual Future Churn Rate", "segment": "Segment"},
    )
    fig_seg.update_traces(textposition="outside")
    fig_seg.update_layout(**PLOTLY_LAYOUT, xaxis_title=None, yaxis_tickformat=".0%")
    st.plotly_chart(fig_seg, use_container_width=True)

st.subheader("Predicted vs. Observed Inactivity by Group")
compare = seg_churn.copy()
compare_long = compare.melt(
    id_vars=["segment", "customers"],
    value_vars=["actual_churn_rate", "avg_predicted_churn"],
    var_name="Metric",
    value_name="Rate",
)
compare_long["Metric"] = compare_long["Metric"].map(
    {
        "actual_churn_rate": "Observed Future Churn",
        "avg_predicted_churn": "Avg Predicted Churn",
    }
)
fig_compare = px.bar(
    compare_long,
    x="segment",
    y="Rate",
    color="Metric",
    barmode="group",
    color_discrete_map={
        "Observed Future Churn": ACCENT,
        "Avg Predicted Churn": BLUE,
    },
    text=compare_long["Rate"].map(lambda v: f"{100*v:.1f}%"),
)
fig_compare.update_traces(textposition="outside")
fig_compare.update_layout(**PLOTLY_LAYOUT, xaxis_title=None, yaxis_tickformat=".0%")
st.plotly_chart(fig_compare, use_container_width=True)


st.divider()

st.subheader("Customers to Review First")
st.markdown(
    "Operational list ranked by predicted churn probability. Use this for "
    "review and prioritization, not as an automated targeting rule."
)

segment_filter = st.multiselect(
    "Segment filter",
    sorted(full["segment"].dropna().unique().tolist()),
    default=sorted(full["segment"].dropna().unique().tolist()),
)
risk_filter = st.multiselect(
    "Risk band",
    ["High", "Medium", "Low"],
    default=["High", "Medium"],
)

filtered = full[
    full["segment"].isin(segment_filter) & full["risk_band"].isin(risk_filter)
].copy()

top_customers = filtered.nlargest(100, "predicted_churn_probability")[
    [
        "customer_id",
        "segment",
        "risk_band",
        "predicted_churn_probability",
        "actual_churn_label",
        "recency_days",
        "frequency",
        "monetary",
        "clv_estimate",
    ]
].copy()
top_customers.columns = [
    "Customer ID",
    "Segment",
    "Risk Band",
    "Predicted Churn",
    "Actual Future Churn",
    "Recency (days)",
    "Orders",
    f"Revenue ({CURRENCY})",
    f"CLV ({CURRENCY})",
]
top_customers["Predicted Churn"] = top_customers["Predicted Churn"].map("{:.1%}".format)
top_customers["Actual Future Churn"] = top_customers["Actual Future Churn"].map(
    {1: "Yes", 0: "No"}
)
top_customers[f"Revenue ({CURRENCY})"] = top_customers[f"Revenue ({CURRENCY})"].map(
    lambda v: f"{CURRENCY}{v:,.0f}" if v == v else "-"
)
top_customers[f"CLV ({CURRENCY})"] = top_customers[f"CLV ({CURRENCY})"].map(
    lambda v: f"{CURRENCY}{v:,.0f}" if v == v else "-"
)

st.dataframe(top_customers, use_container_width=True, hide_index=True)

st.divider()
st.caption(
    "Churn risk is computed from each customer's purchase recency, frequency, revenue, "
    "and order patterns. Customers labeled 'Went Quiet' made no purchase in the 90 days "
    "following the analysis cutoff date."
)

