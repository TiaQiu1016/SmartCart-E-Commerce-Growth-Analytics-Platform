"""
AI Insight Brief page: reviewable business narrative from computed outputs.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from utils import ACCENT, BLUE, render_sidebar

ROOT = Path(__file__).resolve().parents[2]
BRIEF_PATH = ROOT / "reports" / "ai_insight_brief_draft.md"
LLM_BRIEF_PATH = ROOT / "reports" / "ai_insight_brief_llm.md"
APPROVED_PATH = ROOT / "reports" / "ai_insight_brief_llm_approved.json"
VALIDATION_PATH = ROOT / "reports" / "ai_insight_brief_llm_validation.md"
INPUT_PATH = ROOT / "data" / "insight_inputs.json"

_REVIEW_CHECKLIST = [
    "Every number in the brief matches `data/insight_inputs.json`",
    "No observational result is described as a causal effect",
    "Every segment has one data-backed recommended action",
    "API-generated wording is appropriate for final submission",
    "No customer-level identifiers are exposed",
]

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
approval = load_json(APPROVED_PATH)
llm_brief_text = LLM_BRIEF_PATH.read_text(encoding="utf-8") if LLM_BRIEF_PATH.exists() else ""
deterministic_text = BRIEF_PATH.read_text(encoding="utf-8") if BRIEF_PATH.exists() else ""
validation_text = VALIDATION_PATH.read_text(encoding="utf-8") if VALIDATION_PATH.exists() else ""
llm_approved = bool(approval.get("approved"))

# Determine which brief to surface
if llm_brief_text and llm_approved:
    active_brief = llm_brief_text
    brief_source = "llm"
elif deterministic_text:
    active_brief = deterministic_text
    brief_source = "deterministic"
else:
    active_brief = ""
    brief_source = "none"

if not payload:
    st.warning(
        "`data/insight_inputs.json` is not available. Run "
        "`python src/prepare_insight_inputs.py` before reviewing the brief."
    )

if brief_source == "none":
    st.warning(
        "No brief is available. Run `python src/generate_insight_brief.py` first."
    )
    st.stop()

# Show a banner when the LLM brief exists but hasn't been reviewed yet
if llm_brief_text and not llm_approved:
    st.warning(
        "An LLM-generated brief exists but has not been reviewed by a team member. "
        "The deterministic brief is shown below. Open the **Review Guardrails** tab to review "
        "and approve the LLM brief."
    )

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
k4.metric("Churn Segments", f"{len(churn)}")

st.caption(
    "Source: computed SQLite outputs only. The brief should be reviewed by the "
    "team before dashboard publication or final-report use."
)

st.divider()

tab1, tab2, tab3 = st.tabs(["Insight Brief", "Evidence Status", "Review Guardrails"])

with tab1:
    if brief_source == "llm":
        st.success(
            f"AI-generated insight brief approved for dashboard use by "
            f"**{approval.get('approved_by', 'team member')}** on "
            f"{approval.get('approved_at', '')[:10]}."
        )
    else:
        st.info(
            "Showing the deterministic evidence brief. Review and approve the "
            "LLM-generated version in the Review Guardrails tab to publish it here."
        )

    st.markdown('<div class="brief-box">', unsafe_allow_html=True)
    st.markdown(active_brief)
    st.markdown("</div>", unsafe_allow_html=True)

with tab2:
    st.subheader("Structured Input Status")

    status_rows = [
        {"Input": "Segment summaries", "Status": "Available" if segments else "Missing", "Records": len(segments)},
        {"Input": "Predictive churn by segment", "Status": "Available" if churn else "Missing", "Records": len(churn)},
        {"Input": "Group comparisons", "Status": "Available" if groups else "Missing", "Records": len(groups)},
        {"Input": "Product recommendations", "Status": "Available" if recommendations else "Missing", "Records": len(recommendations)},
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

    st.subheader("Validation Report")
    if validation_text:
        st.success(
            "Automated validation report is available. Confirmed warnings are "
            "documented before the LLM brief is shown as approved."
        )
        with st.expander("View validation report"):
            st.markdown(validation_text)
    else:
        st.warning(
            "`reports/ai_insight_brief_llm_validation.md` is missing. Re-run "
            "`python src/generate_insight_brief_llm.py` before approving the LLM brief."
        )

    st.divider()

    st.info(
        "**Approval must be done locally and committed to git.** "
        "Approvals made on Streamlit Cloud are written to the running container only "
        "and are lost on the next deploy. After approving, commit "
        "`reports/ai_insight_brief_llm_approved.json` to the repository so the "
        "audit trail is preserved."
    )

    if not llm_brief_text:
        st.info(
            "No LLM brief found. Run `python src/generate_insight_brief_llm.py` "
            "to generate one, then return here to approve it."
        )
    elif llm_approved:
        st.success(
            f"LLM brief approved by **{approval.get('approved_by', '—')}** "
            f"at {approval.get('approved_at', '—')} using model `{approval.get('model', '—')}`."
        )
        if st.button("Revoke approval"):
            APPROVED_PATH.unlink(missing_ok=True)
            st.rerun()
    else:
        st.subheader("Human Review — LLM Brief")
        st.markdown(
            "Read the LLM brief carefully before approving. "
            "Check every item below, then enter your name and click **Approve**."
        )

        all_checked = all(
            st.checkbox(item, key=f"check_{i}")
            for i, item in enumerate(_REVIEW_CHECKLIST)
        )

        reviewer = st.text_input("Your name (for the audit record)")

        if st.button("Approve LLM brief", disabled=not (all_checked and reviewer.strip())):
            approval_record = {
                "approved": True,
                "approved_by": reviewer.strip(),
                "approved_at": datetime.now(timezone.utc).isoformat(),
                "model": approval.get("model", "gpt-4.1-mini"),
            }
            APPROVED_PATH.write_text(
                json.dumps(approval_record, indent=2) + "\n", encoding="utf-8"
            )
            st.success("Brief approved. The LLM version will now appear on the Insight Brief tab.")
            st.rerun()

st.divider()
st.caption(
    "All numbers in the brief are traceable back to the underlying transaction data. "
    "The brief should be reviewed by the team before sharing with stakeholders."
)
