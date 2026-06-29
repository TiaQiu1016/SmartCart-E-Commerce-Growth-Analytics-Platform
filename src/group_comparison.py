"""
group_comparison.py

Runs observational customer-group comparisons for SmartCart.

This module is not an A/B test. It compares existing historical customer groups
and reports both significance tests and effect sizes:
  - UK vs Non-UK customers
  - K-Means segment-level comparisons

Outputs:
  SQLite tables — group_comparison_results, segment_comparison_summary
  Figures       — group_clv_by_segment.png, uk_nonuk_clv_comparison.png,
                  segment_churn_rate.png

Usage:
    python src/group_comparison.py
"""

from pathlib import Path
import sqlite3

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "smartcart.db"
OUT_DIR = ROOT / "reports" / "figures"

BLUE = "#234A70"
ACCENT = "#E08A3C"
GREEN = "#4F7C52"
GRAY = "#6B7280"

NUMERIC_METRICS = ["recency_days", "frequency", "monetary", "clv_estimate"]


def load_customer_dataset(db_path: Path) -> pd.DataFrame:
    with sqlite3.connect(db_path) as con:
        rfm = pd.read_sql("SELECT customer_id, recency_days, frequency, monetary FROM rfm", con)
        seg = pd.read_sql("SELECT customer_id, segment FROM segments", con)
        clv = pd.read_sql("SELECT customer_id, clv_estimate FROM clv", con)
        countries = pd.read_sql(
            """
            SELECT customer_id,
                   CASE WHEN SUM(CASE WHEN country = 'United Kingdom' THEN 1 ELSE 0 END)
                             >= SUM(CASE WHEN country <> 'United Kingdom' THEN 1 ELSE 0 END)
                        THEN 'UK' ELSE 'Non-UK' END AS region
            FROM transactions
            GROUP BY customer_id
            """,
            con,
        )

    df = (
        rfm.merge(seg, on="customer_id", how="left")
        .merge(clv, on="customer_id", how="left")
        .merge(countries, on="customer_id", how="left")
    )
    df["churned_snapshot"] = (df["recency_days"] > 90).astype(int)
    return df


def cohens_d(a: pd.Series, b: pd.Series) -> float:
    a = a.dropna().astype(float)
    b = b.dropna().astype(float)
    if len(a) < 2 or len(b) < 2:
        return np.nan
    pooled = np.sqrt(((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1)) / (len(a) + len(b) - 2))
    if pooled == 0:
        return 0.0
    return float((a.mean() - b.mean()) / pooled)


def cramers_v(table: pd.DataFrame) -> float:
    chi2 = stats.chi2_contingency(table)[0]
    n = table.to_numpy().sum()
    if n == 0:
        return np.nan
    r, k = table.shape
    return float(np.sqrt((chi2 / n) / max(min(k - 1, r - 1), 1)))


def two_group_numeric_tests(df: pd.DataFrame, group_col: str, group_a: str, group_b: str) -> pd.DataFrame:
    rows = []
    for metric in NUMERIC_METRICS:
        a = df.loc[df[group_col] == group_a, metric].dropna().astype(float)
        b = df.loc[df[group_col] == group_b, metric].dropna().astype(float)
        t_stat, t_p = stats.ttest_ind(a, b, equal_var=False, nan_policy="omit")
        u_stat, u_p = stats.mannwhitneyu(a, b, alternative="two-sided")
        rows.append({
            "comparison": f"{group_a} vs {group_b}",
            "grouping": group_col,
            "metric": metric,
            "test_type": "Welch t-test",
            "group_a": group_a,
            "group_b": group_b,
            "group_a_n": len(a),
            "group_b_n": len(b),
            "group_a_mean": a.mean(),
            "group_b_mean": b.mean(),
            "statistic": t_stat,
            "p_value": t_p,
            "effect_size_name": "Cohen's d",
            "effect_size": cohens_d(a, b),
        })
        rows.append({
            "comparison": f"{group_a} vs {group_b}",
            "grouping": group_col,
            "metric": metric,
            "test_type": "Mann-Whitney U",
            "group_a": group_a,
            "group_b": group_b,
            "group_a_n": len(a),
            "group_b_n": len(b),
            "group_a_mean": a.mean(),
            "group_b_mean": b.mean(),
            "statistic": u_stat,
            "p_value": u_p,
            "effect_size_name": "Cohen's d",
            "effect_size": cohens_d(a, b),
        })
    return pd.DataFrame(rows)


def chi_square_churn(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    table = pd.crosstab(df[group_col], df["churned_snapshot"])
    if table.shape[0] < 2 or table.shape[1] < 2:
        return pd.DataFrame()
    chi2, p_value, dof, _ = stats.chi2_contingency(table)
    return pd.DataFrame([{
        "comparison": f"{group_col} by churned_snapshot",
        "grouping": group_col,
        "metric": "churned_snapshot",
        "test_type": "Chi-square",
        "group_a": None,
        "group_b": None,
        "group_a_n": None,
        "group_b_n": None,
        "group_a_mean": None,
        "group_b_mean": None,
        "statistic": chi2,
        "p_value": p_value,
        "effect_size_name": "Cramer's V",
        "effect_size": cramers_v(table),
        "degrees_of_freedom": dof,
    }])


def segment_pair_tests(df: pd.DataFrame) -> pd.DataFrame:
    profiles = (
        df.groupby("segment")
        .agg(customers=("customer_id", "count"), clv_estimate=("clv_estimate", "mean"))
        .sort_values("clv_estimate", ascending=False)
    )
    top_segment = profiles.index[0]
    bottom_segment = profiles.index[-1]
    return two_group_numeric_tests(df, "segment", top_segment, bottom_segment)


def segment_summary(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby("segment")
        .agg(
            customers=("customer_id", "count"),
            avg_recency_days=("recency_days", "mean"),
            avg_frequency=("frequency", "mean"),
            avg_monetary=("monetary", "mean"),
            avg_clv_estimate=("clv_estimate", "mean"),
            churn_rate_snapshot=("churned_snapshot", "mean"),
            uk_share=("region", lambda s: (s == "UK").mean()),
        )
        .round(4)
        .reset_index()
        .sort_values("avg_clv_estimate", ascending=False)
    )


def write_outputs(db_path: Path, results: pd.DataFrame, summary: pd.DataFrame) -> None:
    with sqlite3.connect(db_path) as con:
        results.to_sql("group_comparison_results", con, if_exists="replace", index=False)
        summary.to_sql("segment_comparison_summary", con, if_exists="replace", index=False)
        con.commit()


def plot_outputs(df: pd.DataFrame, summary: pd.DataFrame) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    ordered = summary.sort_values("avg_clv_estimate", ascending=False)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(ordered["segment"], ordered["avg_clv_estimate"], color=BLUE)
    ax.set_title("Average CLV Estimate by Segment")
    ax.set_ylabel("Average CLV estimate ($)")
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "group_clv_by_segment.png", dpi=150)
    plt.close(fig)

    region_clv = df.groupby("region", as_index=False)["clv_estimate"].mean()
    fig, ax = plt.subplots(figsize=(5.5, 4))
    ax.bar(region_clv["region"], region_clv["clv_estimate"], color=[BLUE, ACCENT])
    ax.set_title("Average CLV: UK vs Non-UK")
    ax.set_ylabel("Average CLV estimate ($)")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "uk_nonuk_clv_comparison.png", dpi=150)
    plt.close(fig)

    churn = summary.sort_values("churn_rate_snapshot", ascending=False)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(churn["segment"], churn["churn_rate_snapshot"] * 100, color=ACCENT)
    ax.set_title("Snapshot Churn Rate by Segment")
    ax.set_ylabel("Customers inactive >90 days (%)")
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "segment_churn_rate.png", dpi=150)
    plt.close(fig)


def main(db_path: Path = DB_PATH) -> None:
    df = load_customer_dataset(db_path)
    uk_tests = two_group_numeric_tests(df, "region", "UK", "Non-UK")
    segment_tests = segment_pair_tests(df)
    chi_region = chi_square_churn(df, "region")
    chi_segment = chi_square_churn(df, "segment")

    results = pd.concat([uk_tests, segment_tests, chi_region, chi_segment], ignore_index=True)
    summary = segment_summary(df)
    write_outputs(db_path, results.round(6), summary)
    plot_outputs(df, summary)

    print("Group comparison results written to SQLite:")
    print("  - group_comparison_results")
    print("  - segment_comparison_summary")
    print("\nSegment summary:")
    print(summary.to_string(index=False))
    print("\nKey tests:")
    cols = ["comparison", "metric", "test_type", "p_value", "effect_size_name", "effect_size"]
    print(results[cols].round(4).to_string(index=False))
    print(f"\nFigures written to {OUT_DIR}")


if __name__ == "__main__":
    main()
