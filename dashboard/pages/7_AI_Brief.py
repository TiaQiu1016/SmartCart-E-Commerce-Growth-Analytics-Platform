"""
AI Insight Brief page: reviewable business narrative from computed outputs.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from utils import ACCENT, BLUE, render_sidebar

ROOT = Path(__file__).resolve().parents[2]
BRIEF_PATH = ROOT / "reports" / "ai_insight_brief_draft.md"
INPUT_PATH = ROOT / "data" / "insight_inputs.json"

st.set_page_config(page_title="AI Insight Brief - SmartCart", layout="wide")

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
    .brief-box {{
        background: white; border-left: 4px solid {ACCENT};
        padding: 18px 22px; border-radius: 6px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

render_sidebar()

st.title("AI Insight Brief")
st.markdown(
    "A plain-language summary of what your customer data is telling you — segment health, "
    "who is at risk of churning, which products drive cross-sell revenue, and where groups "
    "of customers behave differently. All numbers are pulled directly from the analysis; "
    "no metrics are invented."
)


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


payload = load_json(INPUT_PATH)
brief_text = BRIEF_PATH.read_text(encoding="utf-8") if BRIEF_PATH.exists() else ""

if not payload:
    st.warning(
        "`data/insight_inputs.json` is not available. Run "
        "`python src/prepare_insight_inputs.py` before reviewing the brief."
    )

if not brief_text:
    st.warning(
        "`reports/ai_insight_brief_draft.md` is not available. Run "
        "`python src/generate_insight_brief.py` before opening this page."
    )
    st.stop()

metadata = payload.get("metadata", {})
segments = payload.get("segments", [])
churn = payload.get("predictive_churn_by_segment", [])
groups = payload.get("group_comparisons", [])
recommendations = payload.get("top_product_recommendations", [])
unavailable = payload.get("unavailable_modules", [])

k1, k2, k3, k4 = st.columns(4)
k1.metric("Segments Analyzed", f"{len(segments)}")
k2.metric("Group Comparisons", f"{len(groups)}")
k3.metric("Product Suggestions", f"{len(recommendations)}")
k4.metric("Churn Segments", f"{len(payload.get('predictive_churn_by_segment', []))}")

st.caption(
    "Source: computed SQLite outputs only. The brief should be reviewed by the "
    "team before dashboard publication or final-report use."
)

st.divider()

tab1, tab2, tab3 = st.tabs(["Brief Draft", "Input Status", "Guardrails"])

with tab1:
    st.subheader("Generated Brief Draft")
    st.markdown('<div class="brief-box">', unsafe_allow_html=True)
    st.markdown(brief_text)
    st.markdown("</div>", unsafe_allow_html=True)

with tab2:
    st.subheader("Structured Input Status")

    status_rows = [
        {
            "Input": "Segment summaries",
            "Status": "Available" if segments else "Missing",
            "Records": len(segments),
        },
        {
            "Input": "Predictive churn by segment",
            "Status": "Available" if churn else "Missing",
            "Records": len(churn),
        },
        {
            "Input": "Group comparisons",
            "Status": "Available" if groups else "Missing",
            "Records": len(groups),
        },
        {
            "Input": "Product recommendations",
            "Status": "Available" if recommendations else "Missing",
            "Records": len(recommendations),
        },
    ]
    st.dataframe(status_rows, use_container_width=True, hide_index=True)

    st.markdown("#### Missing Inputs")
    if unavailable:
        for note in unavailable:
            st.warning(note)
    else:
        st.success("No unavailable modules were reported in the structured input.")

    with st.expander("Raw metadata"):
        st.json(metadata)

with tab3:
    st.subheader("Generation Guardrails")
    guardrails = payload.get("generation_requirements", {})
    if guardrails:
        st.json(guardrails)
    else:
        st.info("No machine-readable guardrails found in the structured input.")

    st.markdown(
        """
        **Before sharing with stakeholders**

        - Verify every number in the brief against the underlying analysis outputs.
        - Keep at least one data-backed action for every segment.
        - Preserve model limitations and observational caveats.
        - Do not expose customer-level identifiers or raw transaction records.
        - Do not describe observational comparisons as causal effects.
        """
    )

st.divider()
st.caption(
    "All numbers in the brief are traceable back to the underlying transaction data. "
    "The brief should be reviewed by the team before sharing with stakeholders."
)
