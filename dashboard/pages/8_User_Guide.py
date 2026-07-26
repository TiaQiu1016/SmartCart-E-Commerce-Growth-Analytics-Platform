"""
Customer-facing guide for using the SmartCart dashboard.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from utils import ACCENT, BLUE, COMPANY_NAME, render_sidebar

ROOT = Path(__file__).resolve().parents[2]
FULL_GUIDE_PATH = ROOT / "reports" / "dashboard_user_guide.md"

st.set_page_config(page_title="User Guide - SmartCart", layout="wide")

st.markdown(
    f"""
    <style>
    h1, h2, h3 {{ color: {BLUE}; }}
    .stApp {{ background-color: #F5F7FA; }}
    .guide-card {{
        background: white;
        border-left: 4px solid {ACCENT};
        border-radius: 6px;
        padding: 16px 20px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08);
        min-height: 138px;
    }}
    .guide-card h4 {{ margin-top: 0; color: {BLUE}; }}
    .block-container {{ padding-top: 2rem; }}
    </style>
    """,
    unsafe_allow_html=True,
)

render_sidebar()

st.title("User Guide")
st.markdown(
    f"Use SmartCart to turn {COMPANY_NAME}'s transaction history into customer "
    "segments, churn signals, product recommendations, and an approved AI insight brief."
)

st.divider()

st.subheader("Start Here")
c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(
        """
        <div class="guide-card">
        <h4>1. Check the data</h4>
        Use <b>Data Setup</b> to confirm the transaction file, required columns,
        and cleaned preview before trusting the analytics.
        </div>
        """,
        unsafe_allow_html=True,
    )
with c2:
    st.markdown(
        """
        <div class="guide-card">
        <h4>2. Review the customer story</h4>
        Start with <b>Overview</b>, then use <b>Segmentation</b>, <b>Churn Risk</b>,
        and <b>Purchase Likelihood</b> to decide who to prioritize.
        </div>
        """,
        unsafe_allow_html=True,
    )
with c3:
    st.markdown(
        """
        <div class="guide-card">
        <h4>3. Turn insights into action</h4>
        Use <b>Market Basket</b> for cross-sell ideas and <b>AI Insight Brief</b>
        for a plain-language action summary.
        </div>
        """,
        unsafe_allow_html=True,
    )

st.divider()

st.subheader("Page-by-Page Guide")

with st.expander("Overview", expanded=True):
    st.markdown(
        """
        The Overview page gives the top-line business picture: total customers,
        total revenue, invoices, repeat customer rate, average CLV, and revenue
        distribution by segment. Use it first when explaining the dashboard to a
        stakeholder.
        """
    )

with st.expander("Data Setup"):
    st.markdown(
        """
        Use this page when connecting a new retailer's CSV. Confirm the column
        mapping in `config.yaml`, upload the file, inspect the cleaned preview,
        and run the database build process before using downstream pages.
        """
    )

with st.expander("Segmentation"):
    st.markdown(
        """
        Segmentation groups customers into Champions, Recent / Promising,
        At Risk High-Value, and Hibernating. Each group has a recommended action.
        Use this page to decide which customer group needs retention, nurture,
        win-back, or low-cost reactivation.
        """
    )

with st.expander("Purchase Likelihood"):
    st.markdown(
        """
        This page ranks customers by their probability of purchasing in the next
        30 days. Use the campaign budget planner to decide how many customers to
        target and what score cutoff to use.
        """
    )

with st.expander("Market Basket"):
    st.markdown(
        """
        This page identifies products that are commonly bought together. Use
        confidence and lift to choose product bundles, "also bought with" offers,
        or complete-the-set recommendations.
        """
    )

with st.expander("Group Insights"):
    st.markdown(
        """
        This page compares customer groups using statistical tests and effect
        sizes. Treat these as observational differences, not causal proof. Use
        them to understand where customer behavior differs enough to guide
        strategy.
        """
    )

with st.expander("Cohort"):
    st.markdown(
        """
        Cohort views show how customers retained or generated revenue over time
        based on when they first purchased. Use this page to understand whether
        customer retention is improving across acquisition cohorts.
        """
    )

with st.expander("Churn Risk"):
    st.markdown(
        """
        Churn Risk shows which customers are most likely to stop purchasing.
        The model uses a leakage-free time split, so it predicts future inactivity
        from past behavior rather than using future data by accident.
        """
    )

with st.expander("AI Insight Brief"):
    st.markdown(
        """
        The approved AI brief summarizes customer segments, churn signals, CLV,
        group differences, and product recommendations in plain language.

        The **Generate / Refresh AI Brief** button is intentionally disabled in
        demo-safe mode unless live AI generation is explicitly enabled. Opening
        the dashboard does not call OpenAI or spend API credits.
        """
    )

st.divider()

st.subheader("Common Questions")

with st.expander("Why is Generate / Refresh AI Brief disabled?"):
    st.markdown(
        """
        Live generation is off in the public demo so viewers cannot accidentally
        spend API credits. The approved demo brief is still shown. In a controlled
        environment, set `SMARTCART_ENABLE_LIVE_AI=true` and provide
        `OPENAI_API_KEY` to enable generation.
        """
    )

with st.expander("Are the AI brief numbers invented by AI?"):
    st.markdown(
        """
        No. The AI brief is generated from structured model outputs in
        `data/insight_inputs.json`. The validation report checks that cited
        numbers trace back to computed outputs, and a human approval step is
        required before the LLM version is shown as approved.
        """
    )

with st.expander("Can SmartCart prove what caused churn or sales differences?"):
    st.markdown(
        """
        No. SmartCart uses observational transaction data. It can identify
        patterns, differences, and predictive signals, but it does not prove
        causal effects without randomized testing.
        """
    )

if FULL_GUIDE_PATH.exists():
    with st.expander("Full technical guide"):
        st.markdown(FULL_GUIDE_PATH.read_text(encoding="utf-8"))
