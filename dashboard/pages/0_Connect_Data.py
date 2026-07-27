"""
Connect Data page  upload your CSV, validate columns, run the pipeline.

This page lets any retailer onboard their transaction data without
touching any Python code. Edit config.yaml to map your column names,
then upload your CSV and run the pipeline here.
"""

import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils import BLUE, ACCENT, CONFIG, CONFIG_PATH, ROOT, DB_PATH, render_sidebar

st.set_page_config(page_title="Connect Data - SmartCart", layout="wide")

st.markdown(
    f"""
    <style>
    h1, h2, h3 {{ color: {BLUE}; }}
    .stApp {{ background-color: #F5F7FA; }}
    .step-card {{
        background: white; border-left: 4px solid {BLUE};
        padding: 14px 18px; border-radius: 8px; margin-bottom: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.07);
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

render_sidebar()

st.title("Connect Your Data")
st.markdown(
    "SmartCart works with a retailer transaction export. "
    "This setup page checks the file, confirms the column mapping, and refreshes demo outputs."
)

st.divider()

#  Step 1: Current config
st.subheader("Step 1 - Confirm store settings")
st.markdown(
    f"Review the store settings and column names SmartCart will use for this demo. "
    f"For a production version, these settings would be managed through a guided setup form."
)

col_cfg, col_req = st.columns([1, 1])

with col_cfg:
    st.markdown("**Company settings**")
    company = CONFIG.get("company", {})
    st.markdown(f"- Name: `{company.get('name', '')}`")
    st.markdown(f"- Currency: `{company.get('currency_symbol', '')}`")

    data_cfg = CONFIG.get("data", {})
    st.markdown("**Data file**")
    st.markdown(f"- Path: `{data_cfg.get('file', '')}`")
    st.markdown(f"- Encoding: `{data_cfg.get('encoding', 'utf-8')}`")

    flt = CONFIG.get("filters", {})
    st.markdown("**Filters**")
    st.markdown(f"- Min quantity: `{flt.get('min_quantity', 1)}` (rows below this are dropped)")
    st.markdown(f"- Min price: `{flt.get('min_price', 0.0)}`")

with col_req:
    st.markdown("**Column mapping** (your CSV -> SmartCart internal)")
    col_map = CONFIG.get("columns", {})
    mapping_df = pd.DataFrame(
        [{"SmartCart field": k, "Your CSV column": v} for k, v in col_map.items()]
    )
    st.dataframe(mapping_df, use_container_width=True, hide_index=True)

with st.expander("Advanced: setup file"):
    if CONFIG_PATH.exists():
        raw_cfg = CONFIG_PATH.read_text()
        st.code(raw_cfg, language="yaml")
        st.info("For this demo, settings are stored in config.yaml. Admin users can edit it and reload the page.")

st.divider()

#  Step 2: Upload and validate
st.subheader("Step 2 - Upload and check your CSV")
st.markdown(
    "Upload a transaction CSV to check that required columns are present "
    "and the data looks ready before SmartCart refreshes the outputs."
)

uploaded = st.file_uploader("Upload transaction CSV", type=["csv"])

REQUIRED_INTERNAL = ["customer_id", "invoice", "quantity", "invoice_date", "price"]

if uploaded:
    try:
        encoding = CONFIG.get("data", {}).get("encoding", "utf-8")
        df_preview = pd.read_csv(uploaded, encoding=encoding, nrows=5000)
        uploaded.seek(0)

        col_map = CONFIG.get("columns", {})
        reverse_map = {v: k for k, v in col_map.items()}

        # Check which required source columns are present
        missing = []
        found = []
        for internal, source in col_map.items():
            if source in df_preview.columns:
                found.append(source)
            elif internal in REQUIRED_INTERNAL:
                missing.append(f"`{source}` (required for {internal})")

        v1, v2 = st.columns(2)
        with v1:
            st.markdown(f"**Rows in sample:** {len(df_preview):,}")
            st.markdown(f"**Columns found:** {len(df_preview.columns)}")
        with v2:
            if missing:
                st.error(f"Missing required columns: {', '.join(missing)}")
            else:
                st.success("All required columns found.")

        # Rename and show sample
        df_renamed = df_preview.rename(columns=reverse_map)
        flt = CONFIG.get("filters", {})
        min_qty = flt.get("min_quantity", 1)
        min_price = flt.get("min_price", 0.0)

        if "quantity" in df_renamed.columns and "price" in df_renamed.columns:
            df_renamed = df_renamed.dropna(subset=["customer_id"])
            df_clean = df_renamed[(df_renamed["quantity"] >= min_qty) & (df_renamed["price"] > min_price)]
            est_rows = int(len(df_preview) * len(df_clean) / max(len(df_renamed), 1))
            st.markdown(f"**Est. cleaned rows** (from sample): ~{est_rows:,} of {len(df_preview):,}")

        st.markdown("**Preview (first 5 rows after column rename):**")
        st.dataframe(df_renamed.head(5), use_container_width=True, hide_index=True)

        # Save to data/ folder
        if not missing:
            data_dir = ROOT / "data"
            data_dir.mkdir(exist_ok=True)
            target_path = ROOT / CONFIG.get("data", {}).get("file", "data/upload.csv")
            target_path.parent.mkdir(exist_ok=True)

            if st.button("Save uploaded file to data folder", type="primary"):
                with open(target_path, "wb") as f:
                    f.write(uploaded.getvalue())
                st.success(f"Saved to `{target_path.relative_to(ROOT)}`")

    except Exception as e:
        st.error(f"Could not read file: {e}")

st.divider()

#  Step 3: Run the pipeline
st.subheader("Step 3 - Refresh SmartCart outputs")
st.markdown(
    "Use this section when new transaction data has been added. "
    "In this demo, the button rebuilds the cleaned transaction database; "
    "the full model refresh is run by an admin from the backend pipeline."
)

data_file = ROOT / CONFIG.get("data", {}).get("file", "data/online_retail_II.csv")
file_exists = data_file.exists()

if not file_exists:
    st.warning(f"Data file not found: `{data_file.relative_to(ROOT)}`. Upload it in Step 2 first.")

pipeline_scripts = [
    ("build_database.py",    "Load & clean data, build transactions + RFM tables"),
    ("segmentation_clv.py",  "K-Means segmentation + baseline CLV"),
    ("clv_bgnbd.py",         "BG/NBD + Gamma-Gamma probabilistic CLV (optional)"),
    ("churn_model.py",       "Leakage-free churn model"),
    ("propensity_model.py",  "30-day purchase propensity model"),
    ("market_basket.py",     "Apriori association rules"),
    ("group_comparison.py",  "Statistical group comparisons"),
]

st.markdown("**Admin run order**")
steps_df = pd.DataFrame(pipeline_scripts, columns=["Script", "Description"])
steps_df.index = steps_df.index + 1
st.dataframe(steps_df, use_container_width=True)

if st.button("Build Transaction Database", disabled=not file_exists, type="primary"):
    with st.spinner("Running build_database.py..."):
        result = subprocess.run(
            [sys.executable, str(ROOT / "src" / "build_database.py")],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
    if result.returncode == 0:
        st.success("Pipeline step completed successfully.")
        st.code(result.stdout, language="text")
        st.info(
            "Next: run the remaining scripts from your terminal in the order shown above, "
            "then reload the dashboard pages to see your data."
        )
    else:
        st.error("Pipeline failed.")
        st.code(result.stderr, language="text")

st.divider()
with st.expander("Advanced: backend commands"):
    st.markdown("Admin users can run the full refresh in this order:")
    st.code(
        "\n".join([f"python src/{s}" for s, _ in pipeline_scripts]),
        language="bash"
    )

