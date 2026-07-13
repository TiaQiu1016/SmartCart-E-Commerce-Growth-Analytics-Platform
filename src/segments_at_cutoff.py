"""
Build leakage-free segment labels at the churn feature cutoff.

The production `segments` table uses the full observation window. That is useful
for current-state dashboarding, but it should not be used as final evidence that
segments predict future churn. This script rebuilds RFM features using only
transactions on or before the churn `feature_cutoff_date`, assigns K-Means
segments on that historical window, and joins to `churn_scores` for V2
validation summaries.

Outputs written to SQLite:
  - segments_at_cutoff
  - segment_churn_v2_summary
  - segment_churn_v2_results

Usage:
    python src/segments_at_cutoff.py
"""

from __future__ import annotations

from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd
from scipy import stats

from segmentation_clv import prepare_rfm_features, select_k, fit_segments


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "smartcart.db"
DEFAULT_LABEL_WINDOW_DAYS = 90


def table_exists(con: sqlite3.Connection, table: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def get_cutoff(con: sqlite3.Connection, tx: pd.DataFrame) -> tuple[pd.Timestamp, int]:
    if table_exists(con, "churn_scores"):
        meta = pd.read_sql(
            """
            SELECT feature_cutoff_date, label_window_days, COUNT(*) AS rows
            FROM churn_scores
            GROUP BY feature_cutoff_date, label_window_days
            ORDER BY rows DESC
            LIMIT 1
            """,
            con,
        )
        if not meta.empty:
            return (
                pd.to_datetime(meta.iloc[0]["feature_cutoff_date"]),
                int(meta.iloc[0]["label_window_days"]),
            )

    cutoff = tx["invoice_date"].max() - pd.Timedelta(days=DEFAULT_LABEL_WINDOW_DAYS)
    return cutoff.normalize(), DEFAULT_LABEL_WINDOW_DAYS


def load_transactions(db_path: Path) -> tuple[pd.DataFrame, pd.Timestamp, int]:
    with sqlite3.connect(db_path) as con:
        tx = pd.read_sql(
            "SELECT customer_id, invoice, invoice_date, revenue FROM transactions",
            con,
            parse_dates=["invoice_date"],
        )
        cutoff, label_window_days = get_cutoff(con, tx)
    return tx, cutoff, label_window_days


def build_cutoff_rfm(tx: pd.DataFrame, cutoff: pd.Timestamp) -> pd.DataFrame:
    pre = tx[tx["invoice_date"] <= cutoff].copy()
    if pre.empty:
        raise ValueError("No pre-cutoff transactions available for segments_at_cutoff.")

    grouped = pre.groupby("customer_id")
    rfm = pd.DataFrame(
        {
            "customer_id": grouped.size().index,
            "recency_days": (cutoff - grouped["invoice_date"].max()).dt.days,
            "frequency": grouped["invoice"].nunique().astype(float),
            "monetary": grouped["revenue"].sum().astype(float),
        }
    ).reset_index(drop=True)
    return rfm


def cramers_v(table: pd.DataFrame) -> float:
    chi2 = stats.chi2_contingency(table)[0]
    n = table.to_numpy().sum()
    if n == 0:
        return np.nan
    r, k = table.shape
    return float(np.sqrt((chi2 / n) / max(min(k - 1, r - 1), 1)))


def build_v2_outputs(
    segments_at_cutoff: pd.DataFrame,
    db_path: Path,
    cutoff: pd.Timestamp,
    label_window_days: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    with sqlite3.connect(db_path) as con:
        if not table_exists(con, "churn_scores"):
            return pd.DataFrame(), pd.DataFrame()
        churn = pd.read_sql("SELECT * FROM churn_scores", con)

    joined = churn.merge(
        segments_at_cutoff[["customer_id", "segment", "recency_days", "frequency", "monetary"]],
        on="customer_id",
        how="inner",
    )

    summaries = []
    for scope, frame in [
        ("heldout_test", joined[joined.get("is_test_set", 0) == 1]),
        ("all_scored", joined),
    ]:
        if frame.empty:
            continue
        summary = (
            frame.groupby("segment")
            .agg(
                evaluated_customers=("customer_id", "nunique"),
                actual_future_churn_rate=("actual_churn_label", "mean"),
                avg_predicted_churn_probability=("predicted_churn_probability", "mean"),
                avg_recency_days=("recency_days", "mean"),
                avg_frequency=("frequency", "mean"),
                avg_monetary=("monetary", "mean"),
            )
            .round(6)
            .reset_index()
        )
        summary["validation_scope"] = scope
        summary["feature_cutoff_date"] = cutoff.date().isoformat()
        summary["label_window_days"] = label_window_days
        summaries.append(summary)

    summary_out = pd.concat(summaries, ignore_index=True) if summaries else pd.DataFrame()

    test = joined[joined.get("is_test_set", 0) == 1].copy()
    if test.empty:
        test = joined.copy()
        scope = "all_scored"
    else:
        scope = "heldout_test"

    result_rows = []
    contingency = pd.crosstab(test["segment"], test["actual_churn_label"])
    if contingency.shape[0] >= 2 and contingency.shape[1] >= 2:
        chi2, p_value, dof, _ = stats.chi2_contingency(contingency)
        result_rows.append(
            {
                "comparison": "segments_at_cutoff by actual_future_churn",
                "metric": "actual_churn_label",
                "test_type": "Chi-square",
                "validation_scope": scope,
                "statistic": chi2,
                "p_value": p_value,
                "effect_size_name": "Cramer's V",
                "effect_size": cramers_v(contingency),
                "degrees_of_freedom": dof,
                "feature_cutoff_date": cutoff.date().isoformat(),
                "label_window_days": label_window_days,
            }
        )

    groups = [
        grp["predicted_churn_probability"].dropna().astype(float)
        for _, grp in test.groupby("segment")
    ]
    groups = [grp for grp in groups if len(grp) > 0]
    if len(groups) >= 2:
        stat, p_value = stats.kruskal(*groups)
        result_rows.append(
            {
                "comparison": "segments_at_cutoff by predicted_churn_probability",
                "metric": "predicted_churn_probability",
                "test_type": "Kruskal-Wallis",
                "validation_scope": scope,
                "statistic": stat,
                "p_value": p_value,
                "effect_size_name": "epsilon_squared",
                "effect_size": float((stat - len(groups) + 1) / (len(test) - len(groups))),
                "degrees_of_freedom": len(groups) - 1,
                "feature_cutoff_date": cutoff.date().isoformat(),
                "label_window_days": label_window_days,
            }
        )

    results_out = pd.DataFrame(result_rows).round(6)
    return summary_out, results_out


def write_outputs(
    db_path: Path,
    segments_at_cutoff: pd.DataFrame,
    summary: pd.DataFrame,
    results: pd.DataFrame,
) -> None:
    with sqlite3.connect(db_path) as con:
        segments_at_cutoff.to_sql("segments_at_cutoff", con, if_exists="replace", index=False)
        if not summary.empty:
            summary.to_sql("segment_churn_v2_summary", con, if_exists="replace", index=False)
        if not results.empty:
            results.to_sql("segment_churn_v2_results", con, if_exists="replace", index=False)
        con.commit()


def main(db_path: Path = DB_PATH) -> None:
    tx, cutoff, label_window_days = load_transactions(db_path)
    rfm = build_cutoff_rfm(tx, cutoff)
    features, _, _ = prepare_rfm_features(rfm)
    metrics = select_k(features)
    segments, profile = fit_segments(rfm, features, metrics)
    segments["feature_cutoff_date"] = cutoff.date().isoformat()
    segments["label_window_days"] = label_window_days

    summary, results = build_v2_outputs(segments, db_path, cutoff, label_window_days)
    write_outputs(db_path, segments, summary, results)

    best = metrics.sort_values(["silhouette_score", "k"], ascending=[False, True]).iloc[0]
    print(f"Feature cutoff date: {cutoff.date()}")
    print(f"Label window days: {label_window_days}")
    print(f"Customers segmented at cutoff: {len(segments):,}")
    print(f"Selected k: {int(best['k'])} | silhouette: {best['silhouette_score']:.3f}")
    print("\nCutoff segment profiles:")
    print(profile.sort_values("monetary", ascending=False).to_string(index=False))
    if not summary.empty:
        print("\nSegment churn V2 summary:")
        print(summary.to_string(index=False))
    if not results.empty:
        print("\nSegment churn V2 tests:")
        print(results.to_string(index=False))
    print("\nTables written: segments_at_cutoff, segment_churn_v2_summary, segment_churn_v2_results")


if __name__ == "__main__":
    main()
