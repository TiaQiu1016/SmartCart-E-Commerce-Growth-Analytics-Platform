"""
Group Insights page — statistical group comparisons.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import (
    LOGO_FAVICON,
    LOGO_ICON,
    ACCENT,
    BLUE,
    CURRENCY,
    PLOTLY_LAYOUT,
    load_clv,
    load_group_comparison,
    load_segment_summary,
    load_segment_churn_v2_results,
    load_segment_churn_v2_summary,
    load_segments,
    render_sidebar,
)

st.set_page_config(page_title="Group Insights — SmartCart", page_icon=LOGO_FAVICON, layout="wide")

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
    .sig {{ color: #c0392b; font-weight: bold; }}
    .insig {{ color: #7f8c8d; }}
    </style>
    """,
    unsafe_allow_html=True,
)

render_sidebar()

st.title("Customer Group Insights")
st.markdown(
    "Are different customer groups behaving differently? This page compares groups — "
    "UK vs. Non-UK customers, and Champions vs. Hibernating — across key metrics like "
    "revenue, order frequency, and lifetime value. "
    "These are **observational comparisons**, not experiments: they show where differences "
    "exist, not why."
)
st.info(
    "**Note:** The inactive rate in the Segment Profiles tab shows customers who haven't "
    "purchased in the past 90 days — it's a descriptive snapshot. "
    "For predictive churn scores, see the **Churn Risk** page."
)

# ── data ──────────────────────────────────────────────────────────────────────
comp = load_group_comparison()
summary = load_segment_summary()
segments = load_segments()
clv = load_clv()
try:
    churn_v2_summary = load_segment_churn_v2_summary()
    churn_v2_results = load_segment_churn_v2_results()
except Exception:
    churn_v2_summary = None
    churn_v2_results = None

# ── tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["UK vs. Non-UK", "Champions vs. Hibernating", "Segment Profiles", "Future Churn Validation"])

with tab1:
    st.subheader("UK vs. Non-UK Customers")
    uk_comp = comp[comp["comparison"] == "UK vs Non-UK"].copy()

    uk_count = (segments["segment"].notna()).sum()
    uk_seg = segments.merge(clv[["customer_id", "clv_estimate"]], on="customer_id")

    uk_n = uk_comp.iloc[0]["group_a_n"] if not uk_comp.empty else 0
    nonuk_n = uk_comp.iloc[0]["group_b_n"] if not uk_comp.empty else 0

    k1, k2 = st.columns(2)
    k1.metric("UK Customers", f"{uk_n:,}")
    k2.metric("Non-UK Customers", f"{nonuk_n:,}")

    st.markdown("#### Test Results")

    # Welch t-test rows
    welch = uk_comp[uk_comp["test_type"] == "Welch t-test"]
    for _, row in welch.iterrows():
        sig_class = "sig" if row["p_value"] < 0.05 else "insig"
        sig_label = "Notable difference" if row["p_value"] < 0.05 else "Similar"
        st.markdown(
            f"**{row['metric']}** &nbsp;|&nbsp; "
            f"UK avg: {row['group_a_mean']:.1f} &nbsp;·&nbsp; Non-UK avg: {row['group_b_mean']:.1f} "
            f"&nbsp;|&nbsp; Difference size: {row['effect_size']:.3f} "
            f"&nbsp;<span class='{sig_class}'>({sig_label})</span>",
            unsafe_allow_html=True,
        )

    # Bar chart: group means by metric
    metrics_to_show = welch["metric"].unique().tolist()
    if metrics_to_show:
        st.markdown("#### Group Means Comparison")
        metric_sel = st.selectbox("Select metric", metrics_to_show, key="uk_metric")
        row = welch[welch["metric"] == metric_sel].iloc[0]

        fig_bar = go.Figure([
            go.Bar(name="UK", x=["UK"], y=[row["group_a_mean"]], marker_color=BLUE,
                   text=[f"{row['group_a_mean']:.1f}"], textposition="outside"),
            go.Bar(name="Non-UK", x=["Non-UK"], y=[row["group_b_mean"]], marker_color=ACCENT,
                   text=[f"{row['group_b_mean']:.1f}"], textposition="outside"),
        ])
        fig_bar.update_layout(**PLOTLY_LAYOUT, title=f"{metric_sel}: UK vs. Non-UK",
                               yaxis_title=metric_sel, showlegend=True, barmode="group")
        st.plotly_chart(fig_bar, use_container_width=True)

    # Effect size dot plot
    st.markdown("#### How Large Is the Difference? (by Metric)")
    effect_df = welch.drop_duplicates("metric")[["metric", "effect_size", "p_value"]].copy()
    effect_df["significant"] = effect_df["p_value"] < 0.05
    effect_df["color"] = effect_df["significant"].map({True: BLUE, False: "#cccccc"})
    effect_df = effect_df.sort_values("effect_size", ascending=True)

    fig_eff = px.bar(
        effect_df,
        x="effect_size",
        y="metric",
        orientation="h",
        color="significant",
        color_discrete_map={True: BLUE, False: "#cccccc"},
        labels={"effect_size": "Difference size", "metric": "", "significant": "Notable difference"},
        text=effect_df["effect_size"].map("{:.3f}".format),
    )
    fig_eff.add_vline(x=0.2, line_dash="dot", line_color="#aaa", annotation_text="small (0.2)")
    fig_eff.add_vline(x=0.5, line_dash="dot", line_color="#888", annotation_text="medium (0.5)")
    fig_eff.update_traces(textposition="outside")
    fig_eff.update_layout(**PLOTLY_LAYOUT, xaxis_range=[0, max(effect_df["effect_size"].max() * 1.3, 0.6)])
    st.plotly_chart(fig_eff, use_container_width=True)

with tab2:
    st.subheader("Champions vs. Hibernating Customers")
    champ_comp = comp[comp["comparison"] == "Champions vs Hibernating"].copy()

    if champ_comp.empty:
        st.info("Champions vs. Hibernating comparison data not available.")
    else:
        champ_n = int(champ_comp.iloc[0]["group_a_n"])
        hiber_n = int(champ_comp.iloc[0]["group_b_n"])

        k1, k2 = st.columns(2)
        k1.metric("Champions", f"{champ_n:,}")
        k2.metric("Hibernating", f"{hiber_n:,}")

        welch_ch = champ_comp[champ_comp["test_type"] == "Welch t-test"]
        for _, row in welch_ch.iterrows():
            sig_class = "sig" if row["p_value"] < 0.05 else "insig"
            sig_label = "Notable difference" if row["p_value"] < 0.05 else "Similar"
            st.markdown(
                f"**{row['metric']}** &nbsp;|&nbsp; "
                f"Champions avg: {row['group_a_mean']:.1f} &nbsp;·&nbsp; "
                f"Hibernating avg: {row['group_b_mean']:.1f} "
                f"&nbsp;|&nbsp; Difference size: {row['effect_size']:.3f} "
                f"&nbsp;<span class='{sig_class}'>({sig_label})</span>",
                unsafe_allow_html=True,
            )

        # Effect sizes
        st.markdown("#### How Large Is the Difference?")
        effect_ch = welch_ch.drop_duplicates("metric")[["metric", "effect_size", "p_value"]].copy()
        effect_ch["significant"] = effect_ch["p_value"] < 0.05
        effect_ch = effect_ch.sort_values("effect_size", ascending=True)

        fig_ch = px.bar(
            effect_ch,
            x="effect_size",
            y="metric",
            orientation="h",
            color="significant",
            color_discrete_map={True: ACCENT, False: "#cccccc"},
            text=effect_ch["effect_size"].map("{:.2f}".format),
            labels={"effect_size": "Difference size", "metric": "", "significant": "Notable difference"},
        )
        fig_ch.add_vline(x=0.2, line_dash="dot", line_color="#aaa", annotation_text="small")
        fig_ch.add_vline(x=0.8, line_dash="dot", line_color="#888", annotation_text="large")
        fig_ch.update_traces(textposition="outside")
        fig_ch.update_layout(**PLOTLY_LAYOUT)
        st.plotly_chart(fig_ch, use_container_width=True)

        # Radar chart: Champions vs Hibernating on normalized metrics
        st.markdown("#### Profile Comparison — Champions vs. Hibernating")
        merged = segments.merge(clv[["customer_id", "clv_estimate"]], on="customer_id")
        champ_df = merged[merged["segment"] == "Champions"]
        hiber_df = merged[merged["segment"] == "Hibernating"]

        metrics_radar = ["recency_days", "frequency", "monetary", "clv_estimate"]
        labels_radar = ["Recency (days)", "Frequency", "Revenue", "CLV"]

        # Normalize to 0-1 for radar
        norm_vals = {}
        for m in metrics_radar:
            combined = merged[m]
            mn, mx = combined.min(), combined.max()
            norm_vals[m] = {
                "champions": (champ_df[m].mean() - mn) / (mx - mn) if mx > mn else 0.5,
                "hibernating": (hiber_df[m].mean() - mn) / (mx - mn) if mx > mn else 0.5,
            }

        fig_radar = go.Figure()
        for grp, color, name in [("champions", BLUE, "Champions"), ("hibernating", ACCENT, "Hibernating")]:
            vals = [norm_vals[m][grp] for m in metrics_radar]
            vals.append(vals[0])  # close polygon
            fig_radar.add_trace(go.Scatterpolar(
                r=vals,
                theta=labels_radar + [labels_radar[0]],
                fill="toself",
                name=name,
                line_color=color,
                fillcolor=color,
                opacity=0.25,
            ))
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
            showlegend=True,
            paper_bgcolor="white",
            plot_bgcolor="white",
        )
        st.plotly_chart(fig_radar, use_container_width=True)

with tab3:
    st.subheader("Cross-Segment Summary")
    st.markdown(
        "All four segments compared on key metrics. "
        "Inactive rate = share of customers who have not purchased in 90+ days."
    )

    disp = summary.copy()
    disp["avg_recency_days"] = disp["avg_recency_days"].map("{:.0f}".format)
    disp["avg_frequency"] = disp["avg_frequency"].map("{:.1f}".format)
    disp["avg_monetary"] = disp["avg_monetary"].map(lambda v: f"{CURRENCY}{v:,.0f}")
    disp["avg_clv_estimate"] = disp["avg_clv_estimate"].map(lambda v: f"{CURRENCY}{v:,.0f}")
    disp["churn_rate_snapshot"] = (summary["churn_rate_snapshot"] * 100).map("{:.1f}%".format)
    disp["uk_share"] = (summary["uk_share"] * 100).map("{:.1f}%".format)
    disp = disp.rename(columns={
        "segment": "Segment",
        "customers": "Customers",
        "avg_recency_days": "Avg Recency (days)",
        "avg_frequency": "Avg Orders",
        "avg_monetary": f"Avg Revenue ({CURRENCY})",
        "avg_clv_estimate": f"Avg CLV ({CURRENCY})",
        "churn_rate_snapshot": "Inactive Rate",
        "uk_share": "UK Share",
    })
    disp = disp.sort_values("Customers", ascending=False)
    st.dataframe(disp, use_container_width=True, hide_index=True)

    # Multi-metric bar chart
    st.markdown("#### Visual Comparison")
    metric_opt = st.selectbox(
        "Compare segments on",
        ["avg_monetary", "avg_frequency", "avg_recency_days", "avg_clv_estimate"],
        format_func=lambda x: {
            "avg_monetary": f"Avg Revenue ({CURRENCY})",
            "avg_frequency": "Avg Orders",
            "avg_recency_days": "Avg Recency (days)",
            "avg_clv_estimate": f"Avg CLV ({CURRENCY})",
        }[x],
        key="seg_metric",
    )
    fig_seg = px.bar(
        summary.sort_values(metric_opt, ascending=False),
        x="segment",
        y=metric_opt,
        color_discrete_sequence=[BLUE],
        text=summary.sort_values(metric_opt, ascending=False)[metric_opt].map("{:.0f}".format),
    )
    fig_seg.update_traces(textposition="outside")
    fig_seg.update_layout(**PLOTLY_LAYOUT, xaxis_title=None)
    st.plotly_chart(fig_seg, use_container_width=True)


with tab4:
    st.subheader("Which Segments Are Most Likely to Go Quiet?")
    st.markdown(
        "This tab checks whether the customer segment someone belongs to — "
        "Champions, Loyal, At Risk, or Hibernating — predicts whether they actually "
        "stopped buying over the following 90 days. "
        "It uses only purchase history up to a fixed reference date, then checks "
        "what each group did afterward."
    )

    if churn_v2_summary is None or churn_v2_summary.empty:
        st.info("Churn-by-segment data is not yet available.")
    else:
        heldout = churn_v2_summary[churn_v2_summary["validation_scope"] == "heldout_test"].copy()
        if heldout.empty:
            heldout = churn_v2_summary.copy()

        cutoff = heldout["feature_cutoff_date"].iloc[0]
        label_window = int(heldout["label_window_days"].iloc[0])
        st.caption(
            f"Based on purchase history through {cutoff}. "
            f"\"Went quiet\" = no purchase in the following {label_window} days."
        )

        k1, k2, k3 = st.columns(3)
        highest = heldout.sort_values("actual_future_churn_rate", ascending=False).iloc[0]
        lowest = heldout.sort_values("actual_future_churn_rate", ascending=True).iloc[0]
        k1.metric("Highest Future Churn", highest["segment"], f"{highest['actual_future_churn_rate']:.1%}")
        k2.metric("Lowest Future Churn", lowest["segment"], f"{lowest['actual_future_churn_rate']:.1%}")
        k3.metric("Evaluated Customers", f"{int(heldout['evaluated_customers'].sum()):,}")

        chart_df = heldout.sort_values("actual_future_churn_rate", ascending=False).copy()
        chart_df["Actual future churn"] = chart_df["actual_future_churn_rate"]
        chart_df["Predicted churn"] = chart_df["avg_predicted_churn_probability"]
        long_df = chart_df.melt(
            id_vars=["segment"],
            value_vars=["Actual future churn", "Predicted churn"],
            var_name="Measure",
            value_name="Rate",
        )
        fig_churn = px.bar(
            long_df,
            x="segment",
            y="Rate",
            color="Measure",
            barmode="group",
            text=long_df["Rate"].map("{:.0%}".format),
            color_discrete_sequence=[ACCENT, BLUE],
        )
        fig_churn.update_traces(textposition="outside")
        fig_churn.update_layout(**PLOTLY_LAYOUT, xaxis_title=None, yaxis_tickformat=".0%")
        st.plotly_chart(fig_churn, use_container_width=True)

        display = heldout[[
            "segment",
            "evaluated_customers",
            "actual_future_churn_rate",
            "avg_predicted_churn_probability",
        ]].rename(columns={
            "segment": "Segment",
            "evaluated_customers": "Held-out Customers",
            "actual_future_churn_rate": "Actual Future Churn",
            "avg_predicted_churn_probability": "Avg Predicted Churn",
        })
        display["Actual Future Churn"] = display["Actual Future Churn"].map("{:.1%}".format)
        display["Avg Predicted Churn"] = display["Avg Predicted Churn"].map("{:.1%}".format)
        st.dataframe(display, use_container_width=True, hide_index=True)

        if churn_v2_results is not None and not churn_v2_results.empty:
            st.markdown("#### Do the Segments Separate Churn Risk?")
            for _, row in churn_v2_results.iterrows():
                sig = row["p_value"] < 0.05
                label = "Notable difference" if sig else "Similar across segments"
                st.markdown(
                    f"**{row['metric']}**: {label} "
                    f"(difference size: {row['effect_size']:.2f})"
                )

        st.success(
            "Takeaway: a customer's segment is a reliable signal for who will go quiet — "
            "so targeting by segment is a meaningful complement to the individual churn scores "
            "on the Churn Risk page."
        )

st.divider()
st.caption(
    "Observational comparisons only — differences are descriptive, not causal. "
    "Blue bars indicate a notable difference between groups; grey bars indicate groups are similar."
)
