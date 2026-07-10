"""
Segmentation page — RFM K-Means segments, CLV, recommended actions.
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
    load_clv_bgnbd,
    load_segment_profiles,
    load_segments,
)

st.set_page_config(page_title="Segmentation — SmartCart", layout="wide")

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
    .action-card {{
        background: white; border-left: 4px solid {ACCENT};
        padding: 12px 16px; border-radius: 6px; margin-bottom: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Customer Segmentation")
st.markdown(
    "RFM-based K-Means clustering (k=4). Segments are assigned by recency, "
    "frequency, and monetary value — each customer carries a data-backed recommended action."
)

# ── data ──────────────────────────────────────────────────────────────────────
segments = load_segments()
clv = load_clv()
profiles = load_segment_profiles()
try:
    clv_bgnbd = load_clv_bgnbd()
    has_bgnbd = True
except Exception:
    has_bgnbd = False

merged = segments.merge(clv[["customer_id", "clv_estimate"]], on="customer_id")

clv_by_seg = (
    merged.groupby("segment", as_index=False)["clv_estimate"]
    .mean()
    .sort_values("clv_estimate", ascending=False)
)

# ── KPI row ───────────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Customers", f"{len(segments):,}")
k2.metric("Segments", "4")
k3.metric("Highest-CLV Segment", clv_by_seg.iloc[0]["segment"])
k4.metric(
    "Champions Share",
    f"{100 * (segments['segment'] == 'Champions').sum() / len(segments):.1f}%",
)

st.divider()

# ── two bar charts ────────────────────────────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    st.subheader("Customers per Segment")
    prof_sorted = profiles.sort_values("customers", ascending=False)
    fig1 = px.bar(
        prof_sorted,
        x="segment",
        y="customers",
        color_discrete_sequence=[BLUE],
        text="customers",
    )
    fig1.update_traces(textposition="outside")
    fig1.update_layout(**PLOTLY_LAYOUT, xaxis_title=None, yaxis_title="Customers")
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    st.subheader("Average CLV by Segment")
    fig2 = px.bar(
        clv_by_seg,
        x="segment",
        y="clv_estimate",
        color_discrete_sequence=[ACCENT],
        text=clv_by_seg["clv_estimate"].map(lambda v: f"{CURRENCY}{v:,.0f}"),
    )
    fig2.update_traces(textposition="outside")
    fig2.update_layout(**PLOTLY_LAYOUT, xaxis_title=None, yaxis_title="Avg CLV (£)")
    st.plotly_chart(fig2, use_container_width=True)

# ── RFM scatter ────────────────────────────────────────────────────────────────
st.subheader("RFM Scatter — Frequency vs. Recency")
st.markdown("Each point is a customer. Bubble size = total revenue.")

palette = {
    "Champions": BLUE,
    "Recent / Promising": "#4A90C4",
    "At Risk High-Value": ACCENT,
    "Hibernating": "#999999",
}

sample = merged.sample(min(2000, len(merged)), random_state=42)
fig3 = px.scatter(
    sample,
    x="recency_days",
    y="frequency",
    size="monetary",
    color="segment",
    color_discrete_map=palette,
    hover_data={"customer_id": True, "monetary": ":.0f", "clv_estimate": ":.0f"},
    labels={
        "recency_days": "Days Since Last Purchase",
        "frequency": "Number of Orders",
        "monetary": "Revenue (£)",
        "clv_estimate": "CLV Estimate (£)",
    },
    size_max=30,
    opacity=0.7,
)
fig3.update_layout(**PLOTLY_LAYOUT)
st.plotly_chart(fig3, use_container_width=True)

# ── RFM box plots ─────────────────────────────────────────────────────────────
st.subheader("RFM Distribution by Segment")
metric_choice = st.selectbox(
    "Select metric", ["recency_days", "frequency", "monetary"],
    format_func=lambda x: {"recency_days": "Recency (days)", "frequency": "Order Frequency", "monetary": "Revenue (£)"}[x],
)
fig4 = px.box(
    segments,
    x="segment",
    y=metric_choice,
    color="segment",
    color_discrete_map=palette,
    points=False,
)
fig4.update_layout(**PLOTLY_LAYOUT, showlegend=False, xaxis_title=None)
st.plotly_chart(fig4, use_container_width=True)

# ── BG/NBD vs Baseline CLV comparison ────────────────────────────────────────
if has_bgnbd:
    st.subheader("CLV: Baseline vs. BG/NBD Probabilistic Model")
    st.markdown(
        "The **baseline CLV** uses avg order value × annual order rate × recency decay. "
        "The **BG/NBD CLV** uses a probabilistic model (BG/NBD for purchase timing, "
        "Gamma-Gamma for monetary value per transaction). "
        "The prediction unit is **active purchase weeks** over 12 months — "
        "same-week orders are collapsed since the model runs at weekly frequency."
    )

    import plotly.graph_objects as go

    seg_compare = (
        clv_bgnbd.groupby("segment")[
            ["clv_baseline", "clv_bgnbd", "p_alive", "pred_active_purchase_weeks_12m"]
        ]
        .mean()
        .round(2)
        .sort_values("clv_bgnbd", ascending=False)
        .reset_index()
    )

    col_b1, col_b2 = st.columns(2)
    with col_b1:
        x = seg_compare["segment"]
        fig_cmp = go.Figure([
            go.Bar(name="Baseline CLV", x=x, y=seg_compare["clv_baseline"],
                   marker_color=BLUE, text=seg_compare["clv_baseline"].map(lambda v: f"{CURRENCY}{v:,.0f}"),
                   textposition="outside"),
            go.Bar(name="BG/NBD CLV", x=x, y=seg_compare["clv_bgnbd"],
                   marker_color=ACCENT, text=seg_compare["clv_bgnbd"].map(lambda v: f"{CURRENCY}{v:,.0f}"),
                   textposition="outside"),
        ])
        fig_cmp.update_layout(**PLOTLY_LAYOUT, barmode="group",
                               xaxis_title=None, yaxis_title="Avg CLV (£)")
        st.plotly_chart(fig_cmp, use_container_width=True)

    with col_b2:
        st.markdown("**Avg P(Alive) by Segment**")
        fig_alive = px.bar(
            seg_compare, x="segment", y="p_alive",
            color_discrete_sequence=[BLUE],
            text=seg_compare["p_alive"].map("{:.2f}".format),
        )
        fig_alive.update_traces(textposition="outside")
        fig_alive.update_layout(**PLOTLY_LAYOUT, xaxis_title=None,
                                 yaxis_title="P(Alive)", yaxis_range=[0, 1.1])
        st.plotly_chart(fig_alive, use_container_width=True)

    # Segment detail table including purchase weeks prediction
    seg_tbl = seg_compare.copy()
    seg_tbl.columns = ["Segment", "Baseline CLV (£)", "BG/NBD CLV (£)",
                        "Avg P(Alive)", "Pred. Purchase Weeks (12m)"]
    seg_tbl["Baseline CLV (£)"] = seg_tbl["Baseline CLV (£)"].map(lambda v: f"{CURRENCY}{v:,.0f}")
    seg_tbl["BG/NBD CLV (£)"] = seg_tbl["BG/NBD CLV (£)"].map(lambda v: f"{CURRENCY}{v:,.0f}")
    seg_tbl["Avg P(Alive)"] = seg_tbl["Avg P(Alive)"].map("{:.2f}".format)
    seg_tbl["Pred. Purchase Weeks (12m)"] = seg_tbl["Pred. Purchase Weeks (12m)"].map("{:.1f}".format)
    st.dataframe(seg_tbl, use_container_width=True, hide_index=True)

    # Repeat vs one-time buyer breakdown
    n_insufficient = (clv_bgnbd["repeat_history"] == "insufficient").sum()
    n_total = len(clv_bgnbd)
    st.info(
        f"**P(Alive) note:** {n_insufficient:,} of {n_total:,} customers ({100*n_insufficient/n_total:.0f}%) "
        f"have no repeat purchase history. BG/NBD assigns p_alive=1.0 to these customers by design — "
        f"the model has no evidence of churn without a repeat-purchase window. "
        f"This inflates segment-level P(Alive) averages (especially Hibernating, where ~70% are one-time buyers). "
        f"Interpret P(Alive) for repeat customers only."
    )

    with st.expander("Methodology limitations"):
        st.markdown(
            "- **Prediction unit:** active purchase weeks, not strict order count. "
            "Multiple orders in the same week are counted as one event (weekly frequency).\n"
            "- **No discount rate:** `clv_bgnbd` represents expected 12-month revenue, "
            "not discounted to present value.\n"
            "- **Holdout scope:** the 6-month holdout validates purchase frequency (MAE=1.01, r=0.80) "
            "but does not validate the revenue prediction independently."
        )

st.divider()

# ── Recommended actions ───────────────────────────────────────────────────────
st.subheader("Data-Backed Recommended Actions")
st.markdown("One action per segment, derived from the segment's RFM profile.")

for _, row in profiles.sort_values("customers", ascending=False).iterrows():
    st.markdown(
        f"""
        <div class="action-card">
            <strong style="color:{BLUE}">{row['segment']}</strong>
            &nbsp;·&nbsp; {int(row['customers']):,} customers
            &nbsp;·&nbsp; Avg CLV: £{row['monetary']:.0f}
            <br/><span style="color:#444">{row['recommended_action']}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ── detailed profile table ────────────────────────────────────────────────────
st.subheader("Segment Profile Detail")
disp = profiles[["segment", "customers", "recency_days", "frequency", "monetary"]].copy()
disp.columns = ["Segment", "Customers", "Avg Recency (days)", "Avg Orders", "Avg Revenue (£)"]
disp["Avg Revenue (£)"] = disp["Avg Revenue (£)"].map(lambda v: f"{CURRENCY}{v:,.0f}")
disp["Avg Recency (days)"] = disp["Avg Recency (days)"].map("{:.0f}".format)
disp["Avg Orders"] = disp["Avg Orders"].map("{:.1f}".format)
disp = disp.sort_values("Customers", ascending=False)
st.dataframe(disp, use_container_width=True, hide_index=True)
