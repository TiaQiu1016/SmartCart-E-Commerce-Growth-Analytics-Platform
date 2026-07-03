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

# Prediction horizon: 12 months in days
HORIZON_DAYS = 365
# Minimum repeat purchases to include a customer in Gamma-Gamma
MIN_FREQUENCY = 1
# Penalizer for BG/NBD (regularisation — avoids extreme parameter values)
BGNBD_PENALIZER = 0.001


def load_transactions(db_path: Path) -> pd.DataFrame:
    with sqlite3.connect(db_path) as con:
        tx = pd.read_sql(
            "SELECT customer_id, invoice_date, revenue FROM transactions",
            con,
            parse_dates=["invoice_date"],
        )
    return tx


def build_rfm_summary(tx: pd.DataFrame) -> pd.DataFrame:
    """
    Build the lifetimes-format RFM summary from raw transactions.

    lifetimes uses a non-standard RFM definition:
      frequency      = number of repeat transactions (total orders - 1)
      recency        = time from first to last purchase (in weeks)
      T              = age of customer from first purchase to observation end (in weeks)
      monetary_value = mean revenue per repeat transaction (excludes first order)
    """
    observation_end = tx["invoice_date"].max()
    summary = summary_data_from_transaction_data(
        tx,
        customer_id_col="customer_id",
        datetime_col="invoice_date",
        monetary_value_col="revenue",
        observation_period_end=observation_end,
        freq="W",  # weeks — stable time unit for this dataset
    )
    return summary


def fit_bgnbd(summary: pd.DataFrame) -> BetaGeoFitter:
    bgf = BetaGeoFitter(penalizer_coef=BGNBD_PENALIZER)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        bgf.fit(
            summary["frequency"],
            summary["recency"],
            summary["T"],
        )
    print(f"BG/NBD fitted:  a={bgf.params_['a']:.4f}  b={bgf.params_['b']:.4f}  "
          f"r={bgf.params_['r']:.4f}  alpha={bgf.params_['alpha']:.4f}")
    return bgf


def fit_gamma_gamma(summary: pd.DataFrame) -> GammaGammaFitter:
    # Gamma-Gamma requires at least one repeat purchase and positive monetary value
    gg_data = summary[(summary["frequency"] >= MIN_FREQUENCY) & (summary["monetary_value"] > 0)].copy()
    print(f"Gamma-Gamma training on {len(gg_data):,} customers with ≥1 repeat purchase")

    ggf = GammaGammaFitter(penalizer_coef=0.0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ggf.fit(gg_data["frequency"], gg_data["monetary_value"])
    print(f"Gamma-Gamma fitted:  p={ggf.params_['p']:.4f}  q={ggf.params_['q']:.4f}  "
          f"v={ggf.params_['v']:.4f}")
    return ggf


def predict_clv(
    summary: pd.DataFrame,
    bgf: BetaGeoFitter,
    ggf: GammaGammaFitter,
) -> pd.DataFrame:
    t_weeks = HORIZON_DAYS / 7

    # Predicted number of transactions in the next 12 months
    pred_tx = bgf.predict(
        t_weeks,
        summary["frequency"],
        summary["recency"],
        summary["T"],
    )

    # Alive probability
    p_alive = bgf.conditional_probability_alive(
        summary["frequency"],
        summary["recency"],
        summary["T"],
    )

    # Gamma-Gamma expected monetary per transaction (only for repeat customers)
    repeat_mask = (summary["frequency"] >= MIN_FREQUENCY) & (summary["monetary_value"] > 0)
    exp_monetary = pd.Series(np.nan, index=summary.index)
    if repeat_mask.any():
        exp_monetary[repeat_mask] = ggf.conditional_expected_average_profit(
            summary.loc[repeat_mask, "frequency"],
            summary.loc[repeat_mask, "monetary_value"],
        )
    # For one-time buyers, use their observed monetary_value as best estimate
    exp_monetary[~repeat_mask] = summary.loc[~repeat_mask, "monetary_value"]
    exp_monetary = exp_monetary.clip(lower=0)

    result = summary.copy()
    result["pred_transactions_12m"] = pred_tx.round(4)
    result["p_alive"] = p_alive.round(4)
    result["exp_monetary_per_tx"] = exp_monetary.round(4)
    result["clv_bgnbd"] = (pred_tx * exp_monetary).round(2)
    return result.reset_index()


def merge_with_baseline(clv_bgnbd: pd.DataFrame, db_path: Path) -> pd.DataFrame:
    with sqlite3.connect(db_path) as con:
        baseline = pd.read_sql(
            "SELECT customer_id, clv_estimate AS clv_baseline, avg_order_value FROM clv", con
        )
        segments = pd.read_sql("SELECT customer_id, segment FROM segments", con)

    merged = (
        clv_bgnbd[["customer_id", "frequency", "recency", "T", "monetary_value",
                    "pred_transactions_12m", "p_alive", "exp_monetary_per_tx", "clv_bgnbd"]]
        .merge(baseline, on="customer_id", how="left")
        .merge(segments, on="customer_id", how="left")
    )
    return merged


def plot_outputs(result: pd.DataFrame) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. BG/NBD vs Baseline CLV scatter
    cap = result["clv_bgnbd"].quantile(0.98)
    plot_df = result[result["clv_bgnbd"] <= cap].copy()

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(
        plot_df["clv_baseline"],
        plot_df["clv_bgnbd"],
        alpha=0.25,
        s=10,
        color=BLUE,
    )
    lim = max(plot_df["clv_baseline"].max(), plot_df["clv_bgnbd"].max()) * 1.05
    ax.plot([0, lim], [0, lim], "--", color=ACCENT, linewidth=1, label="y = x")
    ax.set_xlabel("Baseline CLV (£)")
    ax.set_ylabel("BG/NBD CLV (£)")
    ax.set_title("Baseline vs. BG/NBD CLV Estimates")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_DIR / "clv_bgnbd_vs_baseline.png", dpi=150)
    plt.close(fig)

    # 2. BG/NBD CLV by segment
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
    ax.set_ylabel("Avg CLV Estimate (£)")
    ax.set_title("Average CLV by Segment: Baseline vs. BG/NBD")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_DIR / "clv_bgnbd_by_segment.png", dpi=150)
    plt.close(fig)

    # 3. P(alive) distribution by segment
    fig, ax = plt.subplots(figsize=(9, 5))
    for i, (seg, grp) in enumerate(result.groupby("segment")):
        ax.hist(grp["p_alive"], bins=30, alpha=0.6, label=seg, density=True)
    ax.set_xlabel("P(alive)")
    ax.set_ylabel("Density")
    ax.set_title("BG/NBD Alive Probability by Segment")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "clv_bgnbd_palive.png", dpi=150)
    plt.close(fig)

    print(f"Figures written to {OUT_DIR}")


def write_output(result: pd.DataFrame, db_path: Path) -> None:
    cols = [
        "customer_id", "segment",
        "frequency", "recency", "T", "monetary_value",
        "pred_transactions_12m", "p_alive",
        "exp_monetary_per_tx", "clv_bgnbd",
        "clv_baseline", "avg_order_value",
    ]
    out = result[cols]
    with sqlite3.connect(db_path) as con:
        out.to_sql("clv_bgnbd", con, if_exists="replace", index=False)
        con.commit()
    print(f"clv_bgnbd table written: {len(out):,} rows")


def main(db_path: Path = DB_PATH) -> None:
    print("Loading transactions...")
    tx = load_transactions(db_path)
    print(f"  {len(tx):,} transactions, {tx['customer_id'].nunique():,} customers")

    print("\nBuilding lifetimes RFM summary (weekly time unit)...")
    summary = build_rfm_summary(tx)
    print(f"  {len(summary):,} customers in summary")

    print("\nFitting BG/NBD model...")
    bgf = fit_bgnbd(summary)

    print("\nFitting Gamma-Gamma model...")
    ggf = fit_gamma_gamma(summary)

    print(f"\nPredicting CLV over {HORIZON_DAYS}-day horizon...")
    clv_pred = predict_clv(summary, bgf, ggf)

    result = merge_with_baseline(clv_pred, db_path)

    # Summary stats
    print("\n=== BG/NBD CLV vs Baseline ===")
    print(f"  Baseline CLV  — mean: £{result['clv_baseline'].mean():,.0f}  "
          f"median: £{result['clv_baseline'].median():,.0f}")
    print(f"  BG/NBD CLV    — mean: £{result['clv_bgnbd'].mean():,.0f}  "
          f"median: £{result['clv_bgnbd'].median():,.0f}")
    print(f"  Avg P(alive):  {result['p_alive'].mean():.3f}")

    print("\n=== BG/NBD CLV by Segment ===")
    seg_summary = (
        result.groupby("segment")[["clv_baseline", "clv_bgnbd", "p_alive", "pred_transactions_12m"]]
        .mean()
        .round(2)
        .sort_values("clv_bgnbd", ascending=False)
    )
    print(seg_summary.to_string())

    write_output(result, db_path)
    plot_outputs(result)


if __name__ == "__main__":
    main()
