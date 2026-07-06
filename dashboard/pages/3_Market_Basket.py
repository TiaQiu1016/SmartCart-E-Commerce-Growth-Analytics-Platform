"""
Market Basket page — Apriori association rules and product recommendations.
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
    PLOTLY_LAYOUT,
    load_association_rules,
    load_recommendations,
)

st.set_page_config(page_title="Market Basket — SmartCart", layout="wide")

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
    .rule-card {{
        background: white; border-left: 4px solid {BLUE};
        padding: 10px 14px; border-radius: 6px; margin-bottom: 6px;
        font-size: 0.92rem;
    }}
    .rule-card.cross {{
        border-left-color: {ACCENT};
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Market-Basket Recommendations")
st.markdown(
    "Apriori association-rule mining on 33,897 multi-item invoices. "
    "Thresholds: `min_support=0.02`, `min_confidence=0.30`, `min_lift=1.5`. "
    "Rules are split into **Complete the Set** (same product line variants) and "
    "**Often Bought With** (cross-category pairs)."
)

# ── data ──────────────────────────────────────────────────────────────────────
rules = load_association_rules()
recs = load_recommendations()

complete = rules[rules["rule_type"] == "Complete the Set"]
cross = rules[rules["rule_type"] == "Often Bought With"]

# ── KPI row ───────────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Rules", f"{len(rules)}")
k2.metric("Complete the Set", f"{len(complete)}")
k3.metric("Often Bought With", f"{len(cross)}")
k4.metric("Top Lift", f"{rules['lift'].max():.1f}×")

st.divider()

# ── tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["Top Rules", "Product Lookup", "Rule Explorer"])

with tab1:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Top 10 by Lift — Complete the Set")
        top_complete = complete.nlargest(10, "lift")[
            ["antecedents", "consequents", "support", "confidence", "lift"]
        ].copy()
        top_complete.columns = ["Antecedent", "Consequent", "Support", "Confidence", "Lift"]
        top_complete["Support"] = top_complete["Support"].map("{:.3f}".format)
        top_complete["Confidence"] = top_complete["Confidence"].map("{:.2f}".format)
        top_complete["Lift"] = top_complete["Lift"].map("{:.1f}×".format)
        st.dataframe(top_complete, use_container_width=True, hide_index=True)

    with col2:
        st.subheader("Top 10 by Lift — Often Bought With")
        top_cross = cross.nlargest(10, "lift")[
            ["antecedents", "consequents", "support", "confidence", "lift"]
        ].copy()
        top_cross.columns = ["Antecedent", "Consequent", "Support", "Confidence", "Lift"]
        top_cross["Support"] = top_cross["Support"].map("{:.3f}".format)
        top_cross["Confidence"] = top_cross["Confidence"].map("{:.2f}".format)
        top_cross["Lift"] = top_cross["Lift"].map("{:.1f}×".format)
        st.dataframe(top_cross, use_container_width=True, hide_index=True)

    st.subheader("Lift Distribution by Rule Type")
    fig_lift = px.box(
        rules,
        x="rule_type",
        y="lift",
        color="rule_type",
        color_discrete_map={"Complete the Set": BLUE, "Often Bought With": ACCENT},
        points="all",
        hover_data={"antecedents": True, "consequents": True},
    )
    fig_lift.update_layout(**PLOTLY_LAYOUT, showlegend=False, xaxis_title=None, yaxis_title="Lift")
    st.plotly_chart(fig_lift, use_container_width=True)

    st.subheader("Support vs. Confidence (colored by Lift)")
    fig_sc = px.scatter(
        rules,
        x="support",
        y="confidence",
        size="lift",
        color="lift",
        color_continuous_scale=[[0, "#C8D8E8"], [1, BLUE]],
        symbol="rule_type",
        hover_data={"antecedents": True, "consequents": True, "lift": ":.2f"},
        labels={"support": "Support", "confidence": "Confidence", "lift": "Lift"},
        size_max=25,
    )
    fig_sc.update_layout(**PLOTLY_LAYOUT)
    st.plotly_chart(fig_sc, use_container_width=True)

with tab2:
    st.subheader("Product Recommendation Lookup")
    st.markdown("Search for a product to see what it's frequently bought with.")

    all_products = sorted(recs["description"].unique().tolist())
    selected = st.selectbox("Select a product", all_products)

    if selected:
        product_recs = recs[recs["description"] == selected].sort_values("lift", ascending=False)

        complete_recs = product_recs[product_recs["rule_type"] == "Complete the Set"]
        cross_recs = product_recs[product_recs["rule_type"] == "Often Bought With"]

        r1, r2 = st.columns(2)

        with r1:
            st.markdown(f"**Complete the Set** ({len(complete_recs)} variants)")
            if complete_recs.empty:
                st.info("No variant rules found for this product.")
            else:
                for _, row in complete_recs.iterrows():
                    st.markdown(
                        f"""<div class="rule-card">
                        <strong>{row['recommended_description']}</strong>
                        &nbsp; (code: {row['recommended_stock_code']})<br/>
                        Confidence: {row['confidence']:.0%} &nbsp;·&nbsp; Lift: {row['lift']:.1f}×
                        &nbsp;·&nbsp; Support: {row['support']:.3f}
                        </div>""",
                        unsafe_allow_html=True,
                    )

        with r2:
            st.markdown(f"**Often Bought With** ({len(cross_recs)} rules)")
            if cross_recs.empty:
                st.info("No cross-category rules found for this product.")
            else:
                for _, row in cross_recs.iterrows():
                    st.markdown(
                        f"""<div class="rule-card cross">
                        <strong>{row['recommended_description']}</strong>
                        &nbsp; (code: {row['recommended_stock_code']})<br/>
                        Confidence: {row['confidence']:.0%} &nbsp;·&nbsp; Lift: {row['lift']:.1f}×
                        &nbsp;·&nbsp; Support: {row['support']:.3f}
                        </div>""",
                        unsafe_allow_html=True,
                    )

with tab3:
    st.subheader("Full Rule Table")
    st.markdown("Filter and explore all 68 rules.")

    rule_type_filter = st.multiselect(
        "Rule type",
        ["Complete the Set", "Often Bought With"],
        default=["Complete the Set", "Often Bought With"],
    )
    min_lift_filter = st.slider("Minimum lift", 1.0, float(rules["lift"].max()), 1.5, step=0.5)

    filtered = rules[
        (rules["rule_type"].isin(rule_type_filter)) &
        (rules["lift"] >= min_lift_filter)
    ][["antecedents", "consequents", "rule_type", "support", "confidence", "lift"]].sort_values(
        "lift", ascending=False
    ).copy()

    filtered.columns = ["Antecedent", "Consequent", "Type", "Support", "Confidence", "Lift"]
    filtered["Support"] = filtered["Support"].map("{:.4f}".format)
    filtered["Confidence"] = filtered["Confidence"].map("{:.3f}".format)
    filtered["Lift"] = filtered["Lift"].map("{:.2f}".format)

    st.markdown(f"Showing **{len(filtered)}** rules")
    st.dataframe(filtered, use_container_width=True, hide_index=True)

st.divider()
st.caption(
    "Apriori via mlxtend · 33,897 multi-item invoices · 4,621 products · "
    "Bootstrap stability: 82% of rules survive all 20 resamples. "
    "Sensitivity: support is the dominant parameter — confidence and lift are non-binding at this operating point."
)
