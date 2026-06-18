"""
segmentation_clv.py

Builds the PR2 customer segmentation and baseline CLV outputs.

Design choices carried forward from proposal feedback:
1. K-Means uses a pinned RFM normalization, not raw RFM values:
   log1p(recency_days), log1p(frequency), log1p(monetary), then StandardScaler.
2. k is selected with silhouette score from k=4..8, so the output satisfies the
   proposal requirement of at least four interpretable segments.
3. Results are written back to SQLite for downstream dashboard/model work.

Usage:
    python src/segmentation_clv.py
"""

from pathlib import Path
import sqlite3

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "smartcart.db"
OUT_DIR = ROOT / "reports" / "figures"
K_RANGE = range(4, 9)
RANDOM_STATE = 42

BLUE = "#234A70"
ACCENT = "#E08A3C"
GREEN = "#4F7C52"
GRAY = "#6B7280"


def load_inputs(db_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    with sqlite3.connect(db_path) as con:
        rfm = pd.read_sql("SELECT customer_id, recency_days, frequency, monetary FROM rfm", con)
        tx = pd.read_sql(
            "SELECT customer_id, invoice, invoice_date, revenue FROM transactions",
            con,
            parse_dates=["invoice_date"],
        )
    if rfm.empty:
        raise ValueError("rfm table is empty. Run src/build_database.py first.")
    return rfm, tx


def prepare_rfm_features(rfm: pd.DataFrame) -> tuple[np.ndarray, StandardScaler, pd.DataFrame]:
    transformed = pd.DataFrame({
        "recency_log": np.log1p(rfm["recency_days"]),
        "frequency_log": np.log1p(rfm["frequency"]),
        "monetary_log": np.log1p(rfm["monetary"]),
    })
    scaler = StandardScaler()
    scaled = scaler.fit_transform(transformed)
    return scaled, scaler, transformed


def select_k(features: np.ndarray) -> pd.DataFrame:
    rows = []
    for k in K_RANGE:
        model = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=50)
        labels = model.fit_predict(features)
        rows.append({
            "k": k,
            "silhouette_score": silhouette_score(features, labels),
            "inertia": model.inertia_,
        })
    return pd.DataFrame(rows)


def segment_labels(profile: pd.DataFrame) -> dict[int, tuple[str, str]]:
    labels: dict[int, tuple[str, str]] = {}
    p = profile.copy()
    p["recency_good"] = p["recency_days"].rank(ascending=False, pct=True)
    p["frequency_good"] = p["frequency"].rank(ascending=True, pct=True)
    p["monetary_good"] = p["monetary"].rank(ascending=True, pct=True)
    p["value_score"] = (
        0.25 * p["recency_good"] + 0.35 * p["frequency_good"] + 0.40 * p["monetary_good"]
    )

    champions = int(p["value_score"].idxmax())
    labels[champions] = (
        "Champions",
        "Protect and grow with VIP retention, early access, and referral offers.",
    )

    hibernating = int(p.drop(index=labels.keys())["value_score"].idxmin())
    labels[hibernating] = (
        "Hibernating",
        "Use low-cost reactivation only; avoid heavy discount spend unless basket value improves.",
    )

    remaining = p.drop(index=labels.keys())
    if not remaining.empty:
        recent = int(remaining["recency_good"].idxmax())
        labels[recent] = (
            "Recent / Promising",
            "Trigger a second-purchase campaign while recency is still strong.",
        )

    remaining = p.drop(index=labels.keys())
    if not remaining.empty:
        at_risk_candidates = remaining[remaining["recency_good"] <= remaining["recency_good"].median()]
        if at_risk_candidates.empty:
            at_risk_candidates = remaining
        at_risk = int(at_risk_candidates["monetary_good"].idxmax())
        labels[at_risk] = (
            "At Risk High-Value",
            "Prioritize win-back messaging because past value is high but recent activity is weak.",
        )

    remaining = p.drop(index=labels.keys())
    for i, cluster in enumerate(remaining.sort_values("value_score", ascending=False).index, start=1):
        if i == 1:
            labels[int(cluster)] = (
                "Steady Customers",
                "Maintain with cross-sell recommendations and periodic replenishment reminders.",
            )
        else:
            labels[int(cluster)] = (
                f"Developing Customers {i}",
                "Use light-touch nurture campaigns before committing high incentive spend.",
            )

    return labels


def fit_segments(rfm: pd.DataFrame, features: np.ndarray, metrics: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    best_k = int(metrics.sort_values(["silhouette_score", "k"], ascending=[False, True]).iloc[0]["k"])
    model = KMeans(n_clusters=best_k, random_state=RANDOM_STATE, n_init=50)
    clusters = model.fit_predict(features)

    seg = rfm.copy()
    seg["cluster"] = clusters

    profile = (
        seg.groupby("cluster")
        .agg(
            customers=("customer_id", "count"),
            recency_days=("recency_days", "mean"),
            frequency=("frequency", "mean"),
            monetary=("monetary", "mean"),
        )
        .round(2)
    )
    label_map = segment_labels(profile)
    seg["segment"] = seg["cluster"].map(lambda c: label_map[int(c)][0])
    seg["recommended_action"] = seg["cluster"].map(lambda c: label_map[int(c)][1])

    profile["segment"] = profile.index.map(lambda c: label_map[int(c)][0])
    profile["recommended_action"] = profile.index.map(lambda c: label_map[int(c)][1])
    profile = profile.reset_index()
    return seg, profile


def estimate_clv(rfm: pd.DataFrame, tx: pd.DataFrame) -> pd.DataFrame:
    latest_date = tx["invoice_date"].max()
    life = (
        tx.groupby("customer_id")
        .agg(first_purchase=("invoice_date", "min"), last_purchase=("invoice_date", "max"))
        .reset_index()
    )
    clv = rfm.merge(life, on="customer_id", how="left")
    clv["avg_order_value"] = clv["monetary"] / clv["frequency"].clip(lower=1)
    clv["observed_days"] = (latest_date - clv["first_purchase"]).dt.days.clip(lower=30)
    clv["observed_years"] = clv["observed_days"] / 365.25
    clv["annual_order_rate"] = clv["frequency"] / clv["observed_years"]
    clv["recency_weight"] = np.exp(-clv["recency_days"] / 365.25)
    clv["clv_estimate"] = (
        clv["avg_order_value"] * clv["annual_order_rate"] * clv["recency_weight"]
    ).round(2)
    return clv[
        [
            "customer_id",
            "avg_order_value",
            "annual_order_rate",
            "recency_weight",
            "frequency",
            "monetary",
            "clv_estimate",
        ]
    ].round(4)


def write_outputs(
    db_path: Path,
    segments: pd.DataFrame,
    clv: pd.DataFrame,
    metrics: pd.DataFrame,
    profile: pd.DataFrame,
) -> None:
    with sqlite3.connect(db_path) as con:
        segments.to_sql("segments", con, if_exists="replace", index=False)
        clv.to_sql("clv", con, if_exists="replace", index=False)
        metrics.to_sql("segmentation_metrics", con, if_exists="replace", index=False)
        profile.to_sql("segment_profiles", con, if_exists="replace", index=False)
        con.commit()


def plot_outputs(metrics: pd.DataFrame, profile: pd.DataFrame, segments: pd.DataFrame, clv: pd.DataFrame) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(metrics["k"], metrics["silhouette_score"], marker="o", color=BLUE)
    ax.set_title("K-Means Silhouette Score by k")
    ax.set_xlabel("Number of clusters")
    ax.set_ylabel("Silhouette score")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "kmeans_silhouette.png", dpi=150)
    plt.close(fig)

    ordered = profile.sort_values("monetary", ascending=False)
    fig, ax = plt.subplots(figsize=(9, 4.8))
    bars = ax.bar(ordered["segment"], ordered["customers"], color=BLUE)
    ax.set_title("K-Means Customer Segments")
    ax.set_ylabel("Customers")
    ax.tick_params(axis="x", rotation=20)
    for bar, monetary in zip(bars, ordered["monetary"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"avg ${monetary:,.0f}",
            ha="center",
            va="bottom",
            fontsize=8,
        )
    fig.tight_layout()
    fig.savefig(OUT_DIR / "kmeans_segments.png", dpi=150)
    plt.close(fig)

    clv_segment = (
        segments[["customer_id", "segment"]]
        .merge(clv[["customer_id", "clv_estimate"]], on="customer_id")
        .groupby("segment", as_index=False)["clv_estimate"]
        .mean()
        .sort_values("clv_estimate", ascending=False)
    )
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(clv_segment["segment"], clv_segment["clv_estimate"], color=ACCENT)
    ax.set_title("Average Baseline CLV by Segment")
    ax.set_ylabel("Estimated 12-month revenue value ($)")
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "clv_by_segment.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 5))
    colors = [BLUE, ACCENT, GREEN, GRAY, "#9B5DE5", "#00A6A6", "#C2410C", "#334155"]
    for i, (segment, df) in enumerate(segments.groupby("segment")):
        ax.scatter(
            np.log1p(df["frequency"]),
            np.log1p(df["monetary"]),
            s=16,
            alpha=0.55,
            label=segment,
            color=colors[i % len(colors)],
        )
    ax.set_title("Segments on Log Frequency vs Log Monetary")
    ax.set_xlabel("log1p(frequency)")
    ax.set_ylabel("log1p(monetary)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "segment_scatter.png", dpi=150)
    plt.close(fig)


def main(db_path: Path = DB_PATH) -> None:
    rfm, tx = load_inputs(db_path)
    features, _, _ = prepare_rfm_features(rfm)
    metrics = select_k(features)
    segments, profile = fit_segments(rfm, features, metrics)
    clv = estimate_clv(rfm, tx)
    write_outputs(db_path, segments, clv, metrics, profile)
    plot_outputs(metrics, profile, segments, clv)

    best = metrics.sort_values(["silhouette_score", "k"], ascending=[False, True]).iloc[0]
    print("RFM preprocessing: log1p(recency_days, frequency, monetary) + StandardScaler")
    print(f"Selected k: {int(best['k'])} | silhouette: {best['silhouette_score']:.3f}")
    print("\nSegment profiles:")
    print(profile.sort_values("monetary", ascending=False).to_string(index=False))
    print(f"\nTables written: segments, clv, segmentation_metrics, segment_profiles")
    print(f"Figures written to {OUT_DIR}")


if __name__ == "__main__":
    main()
