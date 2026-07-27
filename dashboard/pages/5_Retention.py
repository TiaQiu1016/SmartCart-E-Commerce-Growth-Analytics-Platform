"""
Retention page  monthly customer retention and revenue by acquisition cohort.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import pandas as pd

from utils import (
    ACCENT,
    BLUE,
    CURRENCY,
    PLOTLY_LAYOUT,
    load_cohort_retention,
    load_cohort_revenue,
    render_sidebar,
)

st.set_page_config(page_title="Retention  SmartCart", layout="wide")

st.markdown(
    f"""
    <style>
    h1, h2, h3 {{ color: {BLUE}; }}
    .stApp {{ background-color: #F5F7FA; }}
    </style>
    """,
    unsafe_allow_html=True,
)

render_sidebar()

st.title("Customer Retention Over Time")
st.markdown(
    "Customers are grouped by the **month they first purchased** (acquisition cohort). "
    "Each cell shows what percentage of that cohort was still active  "
    "made at least one purchase  in each subsequent month. "
    "Month 0 is always 100% (the first purchase month itself)."
)

#  data
try:
    retention = load_cohort_retention()
    revenue = load_cohort_revenue()
except Exception:
    st.error("Retention tables are not available yet. Ask an admin to refresh SmartCart outputs before opening this page.")
    st.stop()

#  KPI row
m1 = retention[retention["period"] == 1]["retention_rate"].mean()
m3 = retention[retention["period"] == 3]["retention_rate"].mean()
m6 = retention[retention["period"] == 6]["retention_rate"].mean()
avg_cohort_size = retention[retention["period"] == 0]["cohort_size"].mean()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Avg New-Customer Group Size", f"{avg_cohort_size:,.0f} customers")
k2.metric("Avg Month-1 Retention", f"{m1:.1%}", help="Share still buying one month after acquisition")
k3.metric("Avg Month-3 Retention", f"{m3:.1%}")
k4.metric("Avg Month-6 Retention", f"{m6:.1%}")

st.divider()

#  retention heatmap
st.subheader("Retention by First-Purchase Month")
st.markdown(
    "Each row is an acquisition cohort. Each column is months since first purchase. "
    "**Darker = higher retention.** Grey cells = cohort not old enough to have reached that period yet."
)

max_period = st.slider("Show up to month", 3, 24, 12, step=1)

pivot = (
    retention[retention["period"] <= max_period]
    .pivot_table(index="cohort_month", columns="period", values="retention_rate")
    .sort_index()
)

# Build text annotations
text_vals = pivot.map(lambda v: f"{v:.0%}" if pd.notna(v) else "-")

fig_heat = go.Figure(
    go.Heatmap(
        z=pivot.values,
        x=[f"M+{c}" for c in pivot.columns],
        y=pivot.index.tolist(),
        text=text_vals.values,
        texttemplate="%{text}",
        textfont=dict(size=10),
        colorscale=[[0, "#EAF1F8"], [0.3, "#4A90C4"], [1, BLUE]],
        zmin=0,
        zmax=1,
        colorbar=dict(title="Retention", tickformat=".0%", thickness=14),
        hovertemplate="Group: %{y}<br>Period: %{x}<br>Retention: %{z:.1%}<extra></extra>",
    )
)
fig_heat.update_layout(
    **{**PLOTLY_LAYOUT, "margin": dict(l=80, r=20, t=20, b=40)},
    xaxis_title="Months since first purchase",
    yaxis_title="Acquisition cohort",
    height=520,
)
st.plotly_chart(fig_heat, use_container_width=True)

st.divider()

#  retention by calendar month
st.subheader("Retention by Calendar Month")
st.markdown(
    "The heatmap above groups retention by *months since first purchase*, so a "
    "seasonal effect tied to the actual calendar falls on a different diagonal "
    "for every cohort and is easy to miss. This chart re-aggregates the same "
    "underlying data by the actual calendar month of the return purchase."
)

cal = retention[retention["period"] > 0].copy()
cohort_dt = pd.to_datetime(cal["cohort_month"])
target = cohort_dt.values.astype("datetime64[M]") + cal["period"].values.astype("timedelta64[M]")
cal["target_month_num"] = pd.to_datetime(target).month

monthly = (
    cal.groupby("target_month_num")["retention_rate"]
    .mean()
    .reindex(range(1, 13))
)
month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

bar_colors = [BLUE] * 12
bar_colors[10] = ACCENT     # November: peak
bar_colors[11] = "#999999"  # December: trough

fig_cal = go.Figure(
    go.Bar(
        x=month_labels,
        y=monthly.values,
        marker_color=bar_colors,
        text=[f"{v:.0%}" if pd.notna(v) else "" for v in monthly.values],
        textposition="outside",
        hovertemplate="%{x}: %{y:.1%}<extra></extra>",
    )
)
fig_cal.update_layout(
    **PLOTLY_LAYOUT,
    xaxis_title="Calendar month of the return purchase",
    yaxis_title="Average retention rate",
    yaxis_tickformat=".0%",
)
st.plotly_chart(fig_cal, use_container_width=True)

nov_val = monthly.iloc[10]
dec_val = monthly.iloc[11]
st.caption(
    f"Retention peaks at {nov_val:.0%} in November and drops to {dec_val:.0%} in December, "
    "consistent with wholesale buyers restocking ahead of the holiday season rather than during it."
)

st.divider()

#  retention curves
st.subheader("Retention Trend by Customer Group")
st.markdown(
    "How each cohort's retention evolves over time. "
    "Select specific cohorts to compare, or view all."
)

all_cohorts = sorted(retention["cohort_month"].unique().tolist())
col_sel, col_avg = st.columns([2, 1])

with col_sel:
    selected = st.multiselect(
        "Highlight cohorts (leave empty to show all)",
        all_cohorts,
        default=[],
    )

show_avg = col_avg.checkbox("Show average retention line", value=True)

fig_line = go.Figure()

cohorts_to_plot = selected if selected else all_cohorts
for cohort in cohorts_to_plot:
    cohort_data = retention[
        (retention["cohort_month"] == cohort) & (retention["period"] <= max_period)
    ].sort_values("period")
    fig_line.add_trace(
        go.Scatter(
            x=cohort_data["period"],
            y=cohort_data["retention_rate"],
            mode="lines",
            name=cohort,
            line=dict(width=1.5, color=BLUE),
            opacity=0.35 if not selected else 0.8,
            showlegend=bool(selected),
        )
    )

if show_avg:
    avg_curve = (
        retention[retention["period"] <= max_period]
        .groupby("period")["retention_rate"]
        .mean()
        .reset_index()
    )
    fig_line.add_trace(
        go.Scatter(
            x=avg_curve["period"],
            y=avg_curve["retention_rate"],
            mode="lines+markers",
            name="Average",
            line=dict(width=3, color=ACCENT, dash="solid"),
            marker=dict(size=5),
        )
    )

fig_line.update_layout(
    **PLOTLY_LAYOUT,
    xaxis_title="Months since first purchase",
    yaxis_title="Retention rate",
    yaxis_tickformat=".0%",
    yaxis_range=[0, 1.05],
    legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="left", x=0),
)
st.plotly_chart(fig_line, use_container_width=True)

st.divider()

#  cohort revenue
st.subheader("Revenue per Customer Over Time")
st.markdown(
    "Average revenue generated per cohort customer in each month. "
    "High early-period revenue indicates strong initial basket size; "
    "sustained revenue in later periods indicates loyal, high-value customers."
)

avg_rev = (
    revenue[revenue["period"] <= max_period]
    .groupby("period")["avg_revenue_per_customer"]
    .mean()
    .reset_index()
)

fig_rev = px.bar(
    avg_rev,
    x="period",
    y="avg_revenue_per_customer",
    color_discrete_sequence=[BLUE],
    labels={
        "period": "Months since first purchase",
        "avg_revenue_per_customer": f"Avg revenue per customer ({CURRENCY})",
    },
    text=avg_rev["avg_revenue_per_customer"].map(lambda v: f"{CURRENCY}{v:,.0f}"),
)
fig_rev.update_traces(textposition="outside")
fig_rev.update_layout(**PLOTLY_LAYOUT)
st.plotly_chart(fig_rev, use_container_width=True)

st.divider()
st.caption(
    f"25 monthly acquisition cohorts  Dec 2009  Dec 2011  "
    f"Avg month-1 retention: {m1:.1%}  Avg month-6 retention: {m6:.1%}"
)

