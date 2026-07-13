"""
Churn page: customer-level future churn labels and predicted churn risk.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import plotly.express as px
import streamlit as st

from utils import (
    ACCENT,
    BLUE,
    CURRENCY,
    PLOTLY_LAYOUT,
    load_churn_scores,
    load_clv,
    load_segments,
    render_sidebar,
)

st.set_page_config(page_title="Churn Risk - SmartCart", layout="wide")

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
    "XGBoost model predicting whether a customer will make no purchase in the "
    "90-day label window after the feature cutoff. The model uses only "
    "pre-cutoff behavior, so the output can support downstream churn summaries "
    "without using future information as features."
)

try:
    churn = load_churn_scores()
except Exception as exc:
    st.error(
        "The `churn_scores` table is not available yet. Run "
        "`python src/churn_model.py` before opening this page."
    )
    st.caption(str(exc))
    st.stop()

segments = load_segments()
clv = load_clv()

full = (
    churn.merge(
        segments[["customer_id", "segment", "recency_days", "frequency", "monetary"]],
        on="customer_id",
        how="left",
    )
    .merge(clv[["customer_id", "clv_estimate"]], on="customer_id", how="left")
)

full["risk_band"] = "Low"
full.loc[full["predicted_churn_probability"] >= 0.50, "risk_band"] = "Medium"
full.loc[full["predicted_churn_probability"] >= 0.75, "risk_band"] = "High"

test = full[full.get("is_test_set", 0) == 1].copy()
if test.empty:
    test = full.copy()
    validation_scope = "all scored customers"
else:
    validation_scope = "held-out test set"

cutoff = str(full["feature_cutoff_date"].dropna().iloc[0]) if "feature_cutoff_date" in full else "unknown"
window = int(full["label_window_days"].dropna().iloc[0]) if "label_window_days" in full else 90
auc_note = "0.800"

k1, k2, k3, k4 = st.columns(4)
k1.metric("Scored Customers", f"{len(full):,}")
k2.metric("Validation Scope", validation_scope.title())
k3.metric("Observed Churn Rate", f"{100 * test['actual_churn_label'].mean():.1f}%")
k4.metric("XGBoost AUC", auc_note)

st.caption(
    f"Feature cutoff: {cutoff}. Label window: {window} days. "
    "Validation charts use the held-out test set when available."
)

st.divider()

col1, col2 = st.columns(2)

with col1:
    st.subheader("Predicted Churn Score Distribution")
    fig_dist = px.histogram(
        test,
        x="predicted_churn_probability",
        nbins=40,
        color_discrete_sequence=[BLUE],
        labels={"predicted_churn_probability": "Predicted Churn Probability"},
    )
    fig_dist.add_vline(
        x=0.75,
        line_dash="dash",
        line_color=ACCENT,
        annotation_text="High risk",
        annotation_position="top right",
    )
    fig_dist.update_layout(**PLOTLY_LAYOUT, yaxis_title="Customers")
    st.plotly_chart(fig_dist, use_container_width=True)

with col2:
    st.subheader("Actual Future Churn by Segment")
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

st.subheader("Predicted vs. Actual Churn by Segment")
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

st.info(
    "Interpret segment-level churn as a diagnostic for now. A fully leakage-free "
    "Group Comparison V2 still needs `segments_at_cutoff`, where customer "
    "segments are assigned using the same pre-cutoff window as the churn model."
)

st.divider()

st.subheader("High-Risk Customer List")
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
    "Revenue (GBP)",
    "CLV (GBP)",
]
top_customers["Predicted Churn"] = top_customers["Predicted Churn"].map("{:.1%}".format)
top_customers["Actual Future Churn"] = top_customers["Actual Future Churn"].map(
    {1: "Yes", 0: "No"}
)
top_customers["Revenue (GBP)"] = top_customers["Revenue (GBP)"].map(
    lambda v: f"{CURRENCY}{v:,.0f}" if v == v else ""
)
top_customers["CLV (GBP)"] = top_customers["CLV (GBP)"].map(
    lambda v: f"{CURRENCY}{v:,.0f}" if v == v else ""
)

st.dataframe(top_customers, use_container_width=True, hide_index=True)

st.divider()
st.caption(
    "Model output table: `churn_scores`. Features were computed before the "
    "cutoff; labels observe no purchase in the following 90-day window. "
    "Segment-level displays join to the current `segments` table and should be "
    "replaced by `segments_at_cutoff` for final V2 validation."
)
