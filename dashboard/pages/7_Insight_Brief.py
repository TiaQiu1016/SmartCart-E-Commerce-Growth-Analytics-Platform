"""
Insight Brief page: reviewable business narrative from computed outputs.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from utils import LOGO_ICON, ACCENT, BLUE, render_sidebar

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

BRIEF_PATH = ROOT / "reports" / "ai_insight_brief_draft.md"
LLM_BRIEF_PATH = ROOT / "reports" / "ai_insight_brief_llm.md"
APPROVED_PATH = ROOT / "reports" / "ai_insight_brief_llm_approved.json"
VALIDATION_PATH = ROOT / "reports" / "ai_insight_brief_llm_validation.md"
INPUT_PATH = ROOT / "data" / "insight_inputs.json"
LIVE_AI_FLAG = "SMARTCART_ENABLE_LIVE_AI"

_REVIEW_CHECKLIST = [
    "Every number in the brief matches SmartCart's analytics outputs",
    "No pattern is described as a proven cause",
    "Every customer group has one data-backed recommended action",
    "AI wording is appropriate for customer-facing use",
    "No customer-level identifiers are exposed",
]

st.set_page_config(page_title="Insight Brief - SmartCart", page_icon=LOGO_ICON, layout="wide")

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

st.title("Insight Brief")
st.markdown(
    "A plain-language summary of what the customer data is telling you: which groups need attention, "
    "where churn risk is highest, and which product pairings can support cross-sell campaigns. "
    "All numbers come from SmartCart's verified analysis outputs; the AI does not invent metrics."
)


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def configure_api_key_from_secrets() -> bool:
    """Return True when the OpenAI key is available from env, .env, or Streamlit secrets."""
    if os.getenv("OPENAI_API_KEY"):
        return True

    env_path = ROOT / ".env"
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line.startswith("OPENAI_API_KEY="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value:
                    os.environ["OPENAI_API_KEY"] = value
                    return True

    try:
        secret_key = st.secrets.get("OPENAI_API_KEY")
    except Exception:
        secret_key = None
    if secret_key:
        os.environ["OPENAI_API_KEY"] = str(secret_key)
        return True
    return False


def live_generation_enabled() -> bool:
    """Live AI generation is opt-in so demo viewers cannot spend API credits."""
    flag = os.getenv(LIVE_AI_FLAG, "").strip().lower()
    if flag in {"1", "true", "yes", "on"}:
        return True
    try:
        secret_flag = str(st.secrets.get(LIVE_AI_FLAG, "")).strip().lower()
    except Exception:
        secret_flag = ""
    return secret_flag in {"1", "true", "yes", "on"}


payload = load_json(INPUT_PATH)
approval = load_json(APPROVED_PATH)
llm_brief_text = LLM_BRIEF_PATH.read_text(encoding="utf-8") if LLM_BRIEF_PATH.exists() else ""
deterministic_text = BRIEF_PATH.read_text(encoding="utf-8") if BRIEF_PATH.exists() else ""
validation_text = VALIDATION_PATH.read_text(encoding="utf-8") if VALIDATION_PATH.exists() else ""
llm_approved = bool(approval.get("approved"))
api_key_available = configure_api_key_from_secrets()
live_ai_enabled = live_generation_enabled()

if llm_brief_text and llm_approved:
    active_brief = llm_brief_text
    brief_source = "ai"
elif deterministic_text:
    active_brief = deterministic_text
    brief_source = "rule_based"
else:
    active_brief = ""
    brief_source = "none"

if not payload:
    st.warning("The evidence file is not available. Ask an admin to refresh SmartCart outputs before reviewing the brief.")

if brief_source == "none":
    st.warning("No brief is available yet. Ask an admin to generate the first SmartCart insight brief.")
    st.stop()

if llm_brief_text and not llm_approved:
    st.warning(
        "An AI-generated brief exists but has not been reviewed by a team member. "
        "The rule-based evidence brief is shown below. Open Review & Controls to review and approve the AI brief."
    )

metadata = payload.get("metadata", {})
segments = payload.get("segments", [])
churn = payload.get("predictive_churn_by_segment", [])
groups = payload.get("group_comparisons", [])
recommendations = payload.get("top_product_recommendations", [])
unavailable = payload.get("unavailable_modules", [])

k1, k2, k3, k4 = st.columns(4)
k1.metric("Customer Groups", f"{len(segments)}")
k2.metric("Group Insights", f"{len(groups)}")
k3.metric("Product Suggestions", f"{len(recommendations)}")
k4.metric("Churn Risk Groups", f"{len(churn)}")

st.caption("Source: SmartCart's verified analytics outputs. AI wording is reviewed before publication.")
st.divider()

tab1, tab2, tab3 = st.tabs(["Insight Brief", "Evidence Used", "Review & Controls"])

with tab1:
    if brief_source == "ai":
        st.success(
            f"AI insight brief approved for dashboard use by **{approval.get('approved_by', 'team member')}** "
            f"on {approval.get('approved_at', '')[:10]}."
        )
    else:
        st.info(
            "Showing the rule-based evidence brief. Review and approve the AI-generated version "
            "in Review & Controls to publish it here."
        )

    st.markdown('<div class="brief-box">', unsafe_allow_html=True)
    st.markdown(active_brief)
    st.markdown("</div>", unsafe_allow_html=True)

with tab2:
    st.subheader("Evidence Used in This Brief")
    status_rows = [
        {"Input": "Customer group summaries", "Status": "Available" if segments else "Missing", "Records": len(segments)},
        {"Input": "Churn risk by group", "Status": "Available" if churn else "Missing", "Records": len(churn)},
        {"Input": "Group comparison insights", "Status": "Available" if groups else "Missing", "Records": len(groups)},
        {"Input": "Product recommendations", "Status": "Available" if recommendations else "Missing", "Records": len(recommendations)},
    ]
    st.dataframe(status_rows, use_container_width=True, hide_index=True)

    st.markdown("#### Unavailable Insights")
    if unavailable:
        for note in unavailable:
            st.warning(note)
    else:
        st.success("All planned insight inputs are available.")

    with st.expander("Advanced: source metadata"):
        st.json(metadata)

with tab3:
    st.subheader("Generate or Refresh Brief")
    st.markdown(
        "Use this when a retailer uploads new data or reruns the analytics refresh. "
        "A new AI brief is generated only when this button is clicked; simply loading the dashboard does not call an AI provider."
    )

    model_name = st.text_input("Model", value=approval.get("model", "gpt-4.1-mini"))
    if api_key_available and live_ai_enabled:
        generate_clicked = st.button("Generate / Refresh Insight Brief")
    else:
        generate_clicked = st.button("Generate / Refresh Insight Brief", disabled=True)
        if not live_ai_enabled:
            st.info(
                "Live AI generation is disabled for this public demo, so viewers cannot spend API credits. "
                "The approved brief remains available. Admins can enable live generation in a controlled environment."
            )
        else:
            st.info(
                "No AI provider key is configured for this environment. "
                "The approved demo brief remains available without calling live AI."
            )

    if generate_clicked:
        try:
            from generate_insight_brief_llm import call_openai, validate_brief, write_validation

            with st.spinner("Generating a new AI insight brief from computed outputs..."):
                refreshed_payload = load_json(INPUT_PATH)
                if not refreshed_payload:
                    raise RuntimeError("Structured evidence is missing. Refresh SmartCart outputs first.")
                new_brief = call_openai(refreshed_payload, model_name.strip() or "gpt-4.1-mini")
                LLM_BRIEF_PATH.write_text(new_brief + "\n", encoding="utf-8")
                passed, warnings = validate_brief(new_brief, refreshed_payload)
                write_validation(VALIDATION_PATH, passed, warnings, model_name.strip() or "gpt-4.1-mini")
                APPROVED_PATH.unlink(missing_ok=True)

            st.success("New AI brief generated. Review the evidence check and approve it before publishing.")
            st.rerun()
        except Exception as exc:
            st.error(f"Unable to generate AI brief: {exc}")

    st.divider()
    st.subheader("Review Rules")
    guardrails = payload.get("generation_requirements", {})
    if guardrails:
        st.markdown(
            "- Use only numbers already produced by SmartCart.\n"
            "- Include one clear action for every customer group.\n"
            "- Avoid causal claims from observational comparisons.\n"
            "- Do not expose customer-level identifiers."
        )
        with st.expander("Advanced: machine-readable rules"):
            st.json(guardrails)
    else:
        st.info("No review rules were found in the structured evidence file.")

    st.subheader("Evidence Check")
    if validation_text:
        st.success("Automated evidence checks are available. Confirmed warnings are documented before approval.")
        with st.expander("Advanced: view evidence-check report"):
            st.markdown(validation_text)
    else:
        st.warning("The evidence-check report is missing. Regenerate the AI brief before approving it.")

    st.divider()
    with st.expander("Advanced: approval persistence note"):
        st.info(
            "Approvals made on Streamlit Cloud are written to the running container only and are lost on the next deploy. "
            "For the submitted demo, approve locally and commit reports/ai_insight_brief_llm_approved.json to the repository."
        )

    if not llm_brief_text:
        st.info("No AI-generated brief found yet. Generate one from the admin environment, then return here to approve it.")
    elif llm_approved:
        st.success(
            f"AI brief approved by **{approval.get('approved_by', '-')}** "
            f"at {approval.get('approved_at', '-')} using model `{approval.get('model', '-')}`."
        )
        if st.button("Revoke Approval"):
            APPROVED_PATH.unlink(missing_ok=True)
            st.rerun()
    else:
        st.subheader("Human Review")
        st.markdown("Read the AI brief carefully before approving. Check every item below, then enter your name and click Approve.")

        all_checked = all(st.checkbox(item, key=f"check_{i}") for i, item in enumerate(_REVIEW_CHECKLIST))
        reviewer = st.text_input("Your name (for the audit record)")

        if st.button("Approve Insight Brief", disabled=not (all_checked and reviewer.strip())):
            approval_record = {
                "approved": True,
                "approved_by": reviewer.strip(),
                "approved_at": datetime.now(timezone.utc).isoformat(),
                "model": approval.get("model", "gpt-4.1-mini"),
            }
            APPROVED_PATH.write_text(json.dumps(approval_record, indent=2) + "\n", encoding="utf-8")
            st.success("Brief approved. The AI version will now appear on the Insight Brief tab.")
            st.rerun()

st.divider()
st.caption(
    "All numbers in the brief are traceable back to the underlying transaction data. "
    "A team member reviews the brief before it is used with stakeholders."
)

