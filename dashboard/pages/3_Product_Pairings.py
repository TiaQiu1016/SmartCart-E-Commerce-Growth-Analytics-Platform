"""
Product Pairings page — Apriori association rules and product recommendations.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import (
    LOGO_ICON,
    ACCENT,
    BLUE,
    PLOTLY_LAYOUT,
    load_association_rules,
    load_recommendations,
    render_sidebar,
)

st.set_page_config(page_title="Product Pairings — SmartCart", page_icon=LOGO_ICON, layout="wide")

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

render_sidebar()

st.title("Product Recommendations")
st.markdown(
    "Which products are bought together — and how strongly? "
    "SmartCart analyzed **33,897 orders** to find product pairs that appear together "
    "far more often than chance. Rules are split into two types: "
    "**Complete the Set** (color or size variants of the same product line) and "
    "**Often Bought With** (genuinely different products customers combine)."
)

# ── data ──────────────────────────────────────────────────────────────────────
try:
    rules = load_association_rules()
    recs = load_recommendations()
except Exception:
    st.error("Product recommendation tables are not available yet. Ask an admin to refresh SmartCart outputs before opening this page.")
    st.stop()

desc_map = {str(row["stock_code"]): row["description"] for _, row in recs.iterrows()}
rules["antecedent_name"] = rules["antecedents"].map(lambda c: desc_map.get(str(c), str(c)))
rules["consequent_name"] = rules["consequents"].map(lambda c: desc_map.get(str(c), str(c)))
complete = rules[rules["rule_type"] == "Complete the Set"]
cross = rules[rules["rule_type"] == "Often Bought With"]

# ── KPI row ───────────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
k1.metric("Product Pairs Found", f"{len(rules)}")
k2.metric("Complete the Set", f"{len(complete)}", help="Same product in different colors/sizes")
k3.metric("Often Bought With", f"{len(cross)}", help="Different products bought in the same order")
k4.metric("Strongest Association", f"{rules['lift'].max():.1f}×", help="How much more likely than random chance")

st.divider()

# ── tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["Top Rules", "Product Lookup", "Rule Explorer"])

with tab1:
    st.info(
        "**How to read these numbers:** "
        "**Frequency** = share of all orders that contain this pair. "
        "**Buy rate** = when a customer buys the first product, how often they also buy the second. "
        "**Strength** = how much more likely the pair is compared to random chance (1× = no association; 25× = 25 times more likely)."
    )

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Complete the Set — Top Pairs")
        top_complete = complete.nlargest(10, "lift")[
            ["antecedent_name", "consequent_name", "support", "confidence", "lift"]
        ].copy()
        top_complete.columns = ["If customer buys", "They often also buy", "Frequency", "Buy rate", "Strength"]
        top_complete["Frequency"] = top_complete["Frequency"].map("{:.1%}".format)
        top_complete["Buy rate"] = top_complete["Buy rate"].map("{:.0%}".format)
        top_complete["Strength"] = top_complete["Strength"].map("{:.1f}×".format)
        st.dataframe(top_complete, use_container_width=True, hide_index=True)

    with col2:
        st.subheader("Often Bought With — Top Pairs")
        top_cross = cross.nlargest(10, "lift")[
            ["antecedent_name", "consequent_name", "support", "confidence", "lift"]
        ].copy()
        top_cross.columns = ["If customer buys", "They often also buy", "Frequency", "Buy rate", "Strength"]
        top_cross["Frequency"] = top_cross["Frequency"].map("{:.1%}".format)
        top_cross["Buy rate"] = top_cross["Buy rate"].map("{:.0%}".format)
        top_cross["Strength"] = top_cross["Strength"].map("{:.1f}×".format)
        st.dataframe(top_cross, use_container_width=True, hide_index=True)

    st.subheader("Association Strength by Rule Type")
    fig_lift = px.box(
        rules,
        x="rule_type",
        y="lift",
        color="rule_type",
        color_discrete_map={"Complete the Set": BLUE, "Often Bought With": ACCENT},
        points="all",
        hover_data={"antecedent_name": True, "consequent_name": True},
        labels={"lift": "Strength (×)", "rule_type": "", "antecedent_name": "If customer buys", "consequent_name": "They also buy"},
    )
    fig_lift.update_layout(**PLOTLY_LAYOUT, showlegend=False, xaxis_title=None, yaxis_title="Strength (higher = stronger association)")
    st.plotly_chart(fig_lift, use_container_width=True)

    st.subheader("How common vs. how reliable — each product pair")
    st.caption("Bubble size = association strength. Larger and darker = stronger pair.")
    fig_sc = px.scatter(
        rules,
        x="support",
        y="confidence",
        size="lift",
        color="lift",
        color_continuous_scale=[[0, "#C8D8E8"], [1, BLUE]],
        symbol="rule_type",
        hover_data={"antecedent_name": True, "consequent_name": True, "lift": ":.2f"},
        labels={"support": "How common (% of orders)", "confidence": "Buy rate (when A is bought, % also buy B)", "lift": "Strength", "rule_type": "Type", "antecedent_name": "If customer buys", "consequent_name": "They also buy"},
        size_max=25,
    )
    fig_sc.update_layout(
        **{**PLOTLY_LAYOUT, "margin": dict(l=40, r=20, t=40, b=100)},
        legend=dict(
            title="Pairing type",
            orientation="h",
            yanchor="bottom",
            y=-0.28,
            xanchor="left",
            x=0,
        ),
        coloraxis_colorbar=dict(
            title="Strength",
            thickness=12,
            len=0.6,
            yanchor="top",
            y=1,
        ),
    )
    st.plotly_chart(fig_sc, use_container_width=True)

with tab2:
    st.subheader("Product Recommendation Lookup")
    st.markdown("Select a product to see what customers frequently buy alongside it.")

    all_products = sorted(recs["description"].unique().tolist())
    selected = st.selectbox("Select a product", all_products)

    if selected:
        product_recs = recs[recs["description"] == selected].sort_values("lift", ascending=False)

        complete_recs = product_recs[product_recs["rule_type"] == "Complete the Set"]
        cross_recs = product_recs[product_recs["rule_type"] == "Often Bought With"]

        r1, r2 = st.columns(2)

        with r1:
            st.markdown(f"**Complete the Set** — {len(complete_recs)} variant(s)")
            st.caption("Same product line in a different color or size")
            if complete_recs.empty:
                st.info("No variant pairings found for this product.")
            else:
                for _, row in complete_recs.iterrows():
                    st.markdown(
                        f"""<div class="rule-card">
                        <strong>{row['recommended_description']}</strong>
                        &nbsp; (code: {row['recommended_stock_code']})<br/>
                        Bought together in {row['confidence']:.0%} of orders &nbsp;·&nbsp; {row['lift']:.1f}× stronger than random chance
                        </div>""",
                        unsafe_allow_html=True,
                    )

        with r2:
            st.markdown(f"**Often Bought With** — {len(cross_recs)} pairing(s)")
            st.caption("Different products that customers frequently order together")
            if cross_recs.empty:
                st.info("No cross-product pairings found for this product.")
            else:
                for _, row in cross_recs.iterrows():
                    st.markdown(
                        f"""<div class="rule-card cross">
                        <strong>{row['recommended_description']}</strong>
                        &nbsp; (code: {row['recommended_stock_code']})<br/>
                        Bought together in {row['confidence']:.0%} of orders &nbsp;·&nbsp; {row['lift']:.1f}× stronger than random chance
                        </div>""",
                        unsafe_allow_html=True,
                    )

with tab3:
    st.subheader("All Product Pairs")
    st.markdown("Filter and explore every product pairing found in the data.")

    rule_type_filter = st.multiselect(
        "Pairing type",
        ["Complete the Set", "Often Bought With"],
        default=["Complete the Set", "Often Bought With"],
    )
    min_lift_filter = st.slider("Minimum strength (×)", 1.0, float(rules["lift"].max()), 1.5, step=0.5)

    filtered = rules[
        (rules["rule_type"].isin(rule_type_filter)) &
        (rules["lift"] >= min_lift_filter)
    ][["antecedent_name", "consequent_name", "rule_type", "support", "confidence", "lift"]].sort_values(
        "lift", ascending=False
    ).copy()

    filtered.columns = ["If customer buys", "They often also buy", "Type", "Frequency", "Buy rate", "Strength"]
    filtered["Frequency"] = filtered["Frequency"].map("{:.1%}".format)
    filtered["Buy rate"] = filtered["Buy rate"].map("{:.0%}".format)
    filtered["Strength"] = filtered["Strength"].map("{:.1f}×".format)

    st.markdown(f"Showing **{len(filtered)}** product pairs")
    st.dataframe(filtered, use_container_width=True, hide_index=True)

st.divider()
st.caption(
    "Analysis based on 33,897 orders containing multiple products · 4,621 distinct products · "
    "82% of product pairs are stable across repeated sampling of the data."
)

