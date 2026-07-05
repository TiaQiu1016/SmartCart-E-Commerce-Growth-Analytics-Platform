"""
clv_bgnbd.py

BG/NBD + Gamma-Gamma CLV enhancement for SmartCart.

The baseline CLV in segmentation_clv.py uses a simple formula:
    avg_order_value * annual_order_rate * recency_weight

This script adds a probabilistic enhancement using the lifetimes library:
  - BG/NBD (Beta-Geometric / Negative-Binomial Distribution): models the
    latent "alive" probability and future transaction rate for each customer.
  - Gamma-Gamma: models expected monetary value per transaction, conditional
    on the customer making at least one repeat purchase.

Design notes:
  - lifetimes excludes the first purchase from monetary_value for one-time
    buyers, producing monetary_value=0 for the 1,708 customers (29%) with
    no repeat purchases. This script patches those values with each customer's
    actual average revenue from raw transactions so their CLV is non-zero.
  - p_alive for one-time buyers (frequency=0) is always 1.0 in BG/NBD --
    the model has no evidence of churn without a repeat-purchase window.
    These customers are flagged repeat_history="insufficient" in the output.
  - Gamma-Gamma independence assumption verified: Pearson r(frequency,
    monetary_value) = 0.035 on this dataset -- well within acceptable range.
  - Holdout validation: fits on data up to 6 months before the observation
    end, predicts the holdout period, and reports MAE on transaction counts.

Outputs written to SQLite:
  - clv_bgnbd: per-customer predicted transactions (12-month), predicted
    monetary value, BG/NBD CLV estimate, alongside baseline for comparison.

Usage:
    python src/clv_bgnbd.py
"""

from pathlib import Path
import sqlite3
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from lifetimes import BetaGeoFitter, GammaGammaFitter
from lifetimes.utils import summary_data_from_transaction_data

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "smartcart.db"
OUT_DIR = ROOT / "reports" / "figures"

BLUE = "#234A70"
ACCENT = "#E08A3C"

HORIZON_DAYS = 365
MIN_FREQUENCY = 1
BGNBD_PENALIZER = 0.001
HOLDOUT_MONTHS = 6


def load_transactions(db_path: Path) -> pd.DataFrame:
    with sqlite3.connect(db_path) as con:
        tx = pd.read_sql(
            "SELECT customer_id, invoice, invoice_date, revenue FROM transactions",
            con,
            parse_dates=["invoice_date"],
        )
    return tx


def avg_order_value_by_customer(tx: pd.DataFrame) -> pd.Series:
    """Invoice-level average order value (sum per invoice, then mean across invoices)."""
    invoice_totals = tx.groupby(["customer_id", "invoice"])["revenue"].sum()
    return invoice_totals.groupby("customer_id").mean()


def build_rfm_summary(tx: pd.DataFrame) -> pd.DataFrame:
    """
    Build lifetimes-format RFM summary. frequency = repeat purchases
    (total orders - 1), so one-time buyers have frequency=0 and lifetimes
    sets their monetary_value=0. Patched below with actual avg revenue.
    """
    observation_end = tx["invoice_date"].max()
    summary = summary_data_from_transaction_data(
        tx,
        customer_id_col="customer_id",
        datetime_col="invoice_date",
        monetary_value_col="revenue",
        observation_period_end=observation_end,
        freq="W",
    )
    # Patch one-time buyer monetary_value: lifetimes returns 0 for them
    # because it excludes the first purchase from the monetary calculation.
    # Use invoice-level average order value (not line-item mean) to avoid
    # underestimating customers whose orders contain many line items.
    one_time_mask = summary["frequency"] == 0
    if one_time_mask.any():
        avg_ov = avg_order_value_by_customer(tx)
        summary.loc[one_time_mask, "monetary_value"] = (
            avg_ov.reindex(summary.index[one_time_mask]).values
        )
    return summary


def check_gamma_gamma_assumption(summary: pd.DataFrame) -> float:
    repeat = summary[summary["frequency"] >= MIN_FREQUENCY]
    r = repeat["frequency"].corr(repeat["monetary_value"])
    status = "OK" if abs(r) < 0.10 else "WARNING: exceeds threshold"
    print(f"Gamma-Gamma independence check: Pearson r(frequency, monetary_value) = {r:.4f} ({status})")
    return r


def fit_bgnbd(summary: pd.DataFrame) -> BetaGeoFitter:
    bgf = BetaGeoFitter(penalizer_coef=BGNBD_PENALIZER)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        bgf.fit(summary["frequency"], summary["recency"], summary["T"])
    print(
        f"BG/NBD fitted:  a={bgf.params_['a']:.4f}  b={bgf.params_['b']:.4f}  "
        f"r={bgf.params_['r']:.4f}  alpha={bgf.params_['alpha']:.4f}"
    )
    return bgf


def fit_gamma_gamma(summary: pd.DataFrame) -> GammaGammaFitter:
    gg_data = summary[
        (summary["frequency"] >= MIN_FREQUENCY) & (summary["monetary_value"] > 0)
    ].copy()
    n_one_time = (summary["frequency"] == 0).sum()
    print(
        f"Gamma-Gamma: training on {len(gg_data):,} repeat customers "
        f"({n_one_time:,} one-time buyers excluded from fitting)"
    )
    ggf = GammaGammaFitter(penalizer_coef=0.0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ggf.fit(gg_data["frequency"], gg_data["monetary_value"])
    print(
        f"Gamma-Gamma fitted:  p={ggf.params_['p']:.4f}  q={ggf.params_['q']:.4f}  "
        f"v={ggf.params_['v']:.4f}"
    )
    return ggf


def predict_clv(
    summary: pd.DataFrame,
    bgf: BetaGeoFitter,
    ggf: GammaGammaFitter,
) -> pd.DataFrame:
    t_weeks = HORIZON_DAYS / 7

    pred_tx = bgf.predict(
        t_weeks, summary["frequency"], summary["recency"], summary["T"]
    )
    p_alive = bgf.conditional_probability_alive(
        summary["frequency"], summary["recency"], summary["T"]
    )

    repeat_mask = (summary["frequency"] >= MIN_FREQUENCY) & (summary["monetary_value"] > 0)
    exp_monetary = pd.Series(np.nan, index=summary.index)
    if repeat_mask.any():
        exp_monetary[repeat_mask] = ggf.conditional_expected_average_profit(
            summary.loc[repeat_mask, "frequency"],
            summary.loc[repeat_mask, "monetary_value"],
        )
    # One-time buyers: use patched actual avg revenue (already in monetary_value)
    exp_monetary[~repeat_mask] = summary.loc[~repeat_mask, "monetary_value"]
    exp_monetary = exp_monetary.clip(lower=0)

    result = summary.copy()
    result["pred_active_purchase_weeks_12m"] = pred_tx.round(4)
    result["p_alive"] = p_alive.round(4)
    result["exp_monetary_per_tx"] = exp_monetary.round(4)
    result["clv_bgnbd"] = (pred_tx * exp_monetary).round(2)
    # Flag: p_alive=1.0 for one-time buyers is a BG/NBD model artefact
    result["repeat_history"] = np.where(
        summary["frequency"] >= MIN_FREQUENCY, "yes", "insufficient"
    )
    return result.reset_index()


def holdout_validation(tx: pd.DataFrame) -> dict:
    """
    Calibration/holdout split: fit BG/NBD on data up to HOLDOUT_MONTHS
    before observation end, predict holdout period, report MAE.
    """
    obs_end = tx["invoice_date"].max()
    holdout_start = obs_end - pd.DateOffset(months=HOLDOUT_MONTHS)
    cal_tx = tx[tx["invoice_date"] < holdout_start]
    hold_tx = tx[tx["invoice_date"] >= holdout_start]

    if cal_tx.empty:
        return {}

    cal_summary = summary_data_from_transaction_data(
        cal_tx,
        customer_id_col="customer_id",
        datetime_col="invoice_date",
        monetary_value_col="revenue",
        observation_period_end=holdout_start,
        freq="W",
    )
    bgf_cal = BetaGeoFitter(penalizer_coef=BGNBD_PENALIZER)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        bgf_cal.fit(cal_summary["frequency"], cal_summary["recency"], cal_summary["T"])

    t_hold_weeks = (obs_end - holdout_start).days / 7
    pred = bgf_cal.predict(
        t_hold_weeks, cal_summary["frequency"], cal_summary["recency"], cal_summary["T"]
    )
    # Count distinct active purchase weeks per customer in the holdout period.
    # This matches what BG/NBD predicts (freq="W" collapses same-week orders).
    hold_in_cal = hold_tx[hold_tx["customer_id"].isin(cal_summary.index)].copy()
    hold_in_cal["week"] = hold_in_cal["invoice_date"].dt.to_period("W")
    actual = (
        hold_in_cal.groupby("customer_id")["week"]
        .nunique()
        .reindex(cal_summary.index, fill_value=0)
    )
    mae = float(np.abs(pred - actual).mean())
    corr = float(np.corrcoef(pred, actual)[0, 1])
    print(f"\nHoldout validation ({HOLDOUT_MONTHS}-month holdout, actual = distinct purchase weeks):")
    print(f"  Predicted mean: {pred.mean():.3f}  Actual mean: {actual.mean():.3f}")
    print(f"  MAE: {mae:.3f}  Pearson r: {corr:.3f}")
    return {"holdout_mae": mae, "holdout_corr": corr}


def merge_with_baseline(clv_bgnbd: pd.DataFrame, db_path: Path) -> pd.DataFrame:
    with sqlite3.connect(db_path) as con:
        baseline = pd.read_sql(
            "SELECT customer_id, clv_estimate AS clv_baseline, avg_order_value FROM clv", con
        )
        segments = pd.read_sql("SELECT customer_id, segment FROM segments", con)
    merged = (
        clv_bgnbd[[
            "customer_id", "frequency", "recency", "T", "monetary_value",
            "pred_active_purchase_weeks_12m", "p_alive", "repeat_history",
            "exp_monetary_per_tx", "clv_bgnbd",
        ]]
        .merge(baseline, on="customer_id", how="left")
        .merge(segments, on="customer_id", how="left")
    )
    return merged


def plot_outputs(result: pd.DataFrame) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    cap = result["clv_bgnbd"].quantile(0.98)
    plot_df = result[result["clv_bgnbd"] <= cap].copy()
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(plot_df["clv_baseline"], plot_df["clv_bgnbd"],
               alpha=0.25, s=10, color=BLUE)
    lim = max(plot_df["clv_baseline"].max(), plot_df["clv_bgnbd"].max()) * 1.05
    ax.plot([0, lim], [0, lim], "--", color=ACCENT, linewidth=1, label="y = x")
    ax.set_xlabel("Baseline CLV (GBP)")
    ax.set_ylabel("BG/NBD CLV (GBP)")
    ax.set_title("Baseline vs. BG/NBD CLV Estimates")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_DIR / "clv_bgnbd_vs_baseline.png", dpi=150)
    plt.close(fig)

    seg_clv = (
        result.groupby("segment")[["clv_baseline", "clv_bgnbd"]]
        .mean()
        .sort_values("clv_bgnbd", ascending=False)
        .reset_index()
    )
    x = np.arange(len(seg_clv))
    width = 0.35
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(x - width / 2, seg_clv["clv_baseline"], width, label="Baseline CLV", color=BLUE)
    ax.bar(x + width / 2, seg_clv["clv_bgnbd"], width, label="BG/NBD CLV", color=ACCENT)
    ax.set_xticks(x)
    ax.set_xticklabels(seg_clv["segment"], rotation=15, ha="right")
    ax.set_ylabel("Avg CLV Estimate (GBP)")
    ax.set_title("Average CLV by Segment: Baseline vs. BG/NBD")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_DIR / "clv_bgnbd_by_segment.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    for seg, grp in result.groupby("segment"):
        ax.hist(grp["p_alive"], bins=30, alpha=0.6, label=seg, density=True)
    ax.set_xlabel("P(alive)")
    ax.set_ylabel("Density")
    ax.set_title(
        "BG/NBD P(alive) by Segment\n"
        "(one-time buyers always show p_alive=1.0 -- BG/NBD model artefact, not a meaningful signal)"
    )
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "clv_bgnbd_palive.png", dpi=150)
    plt.close(fig)

    print("Figures written to reports/figures/")


def write_output(result: pd.DataFrame, db_path: Path) -> None:
    cols = [
        "customer_id", "segment",
        "frequency", "recency", "T", "monetary_value",
        "pred_active_purchase_weeks_12m", "p_alive", "repeat_history",
        "exp_monetary_per_tx", "clv_bgnbd",
        "clv_baseline", "avg_order_value",
    ]
    with sqlite3.connect(db_path) as con:
        result[cols].to_sql("clv_bgnbd", con, if_exists="replace", index=False)
        con.commit()
    print(f"clv_bgnbd table written: {len(result):,} rows")


def main(db_path: Path = DB_PATH) -> None:
    print("Loading transactions...")
    tx = load_transactions(db_path)
    print(f"  {len(tx):,} transactions, {tx['customer_id'].nunique():,} customers")

    print("\nBuilding lifetimes RFM summary (weekly time unit)...")
    summary = build_rfm_summary(tx)
    n_one_time = (summary["frequency"] == 0).sum()
    print(f"  {len(summary):,} customers in summary")
    print(
        f"  One-time buyers (frequency=0): {n_one_time:,} ({100*n_one_time/len(summary):.1f}%) -- "
        f"monetary patched from raw transactions; p_alive=1.0 is a model artefact for this group"
    )

    print("\nChecking Gamma-Gamma independence assumption...")
    check_gamma_gamma_assumption(summary)

    print("\nFitting BG/NBD model...")
    bgf = fit_bgnbd(summary)

    print("\nFitting Gamma-Gamma model...")
    ggf = fit_gamma_gamma(summary)

    print(f"\nPredicting CLV over {HORIZON_DAYS}-day horizon...")
    clv_pred = predict_clv(summary, bgf, ggf)

    holdout_validation(tx)

    result = merge_with_baseline(clv_pred, db_path)

    print("\n=== BG/NBD CLV vs Baseline ===")
    print(
        f"  Baseline CLV  -- mean: GBP {result['clv_baseline'].mean():,.0f}  "
        f"median: GBP {result['clv_baseline'].median():,.0f}"
    )
    print(
        f"  BG/NBD CLV    -- mean: GBP {result['clv_bgnbd'].mean():,.0f}  "
        f"median: GBP {result['clv_bgnbd'].median():,.0f}"
    )
    zero_clv = (result["clv_bgnbd"] == 0).sum()
    print(f"  Customers with clv_bgnbd=0: {zero_clv} (should be 0 after one-time buyer patch)")
    print(f"  Avg P(alive) -- all: {result['p_alive'].mean():.3f}  "
          f"repeat-only: {result[result['repeat_history']=='yes']['p_alive'].mean():.3f}")

    print("\n=== BG/NBD CLV by Segment ===")
    seg_summary = (
        result.groupby("segment")[["clv_baseline", "clv_bgnbd", "p_alive", "pred_active_purchase_weeks_12m"]]
        .mean()
        .round(2)
        .sort_values("clv_bgnbd", ascending=False)
    )
    print(seg_summary.to_string())

    write_output(result, db_path)
    plot_outputs(result)


if __name__ == "__main__":
    main()
