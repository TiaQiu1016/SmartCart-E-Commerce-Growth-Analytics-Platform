"""
propensity_model.py

Predicts 30-day purchase propensity using a leakage-free time-split design.

Label: the customer makes at least one purchase in the 30 days after the cutoff date.
Features: computed only from transactions on or before the cutoff.

Why a separate model from churn (90-day horizon):
  Churn identifies customers the retailer is about to lose permanently.
  Propensity identifies who to activate in a next-30-day campaign — a shorter,
  action-oriented window. The inter-purchase interval features (avg_days_between_orders,
  purchase_regularity, recency_ratio) capture purchase rhythm and are especially
  informative at this horizon.

Models: logistic regression (baseline) + XGBoost, both hyperparameter-tuned via
randomized/grid search with stratified 5-fold cross-validation. Tuning matters here:
an untuned XGBoost previously underperformed the logistic baseline (0.762 vs 0.781
AUC), which is unusual and a sign of mistuned defaults rather than a genuine
ranking of the two model families on this problem.

Outputs:
  SQLite table  — propensity_scores (customer_id, propensity_score)
  Figures       — propensity_roc.png, propensity_feature_importance.png,
                  propensity_by_segment.png, propensity_gain_chart.png

Usage:
    python src/propensity_model.py
"""

from pathlib import Path
import sqlite3

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, roc_auc_score, roc_curve
from sklearn.model_selection import GridSearchCV, RandomizedSearchCV, StratifiedKFold, train_test_split
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "smartcart.db"
OUT_DIR = ROOT / "reports" / "figures"
HORIZON_DAYS = 30
BLUE, ACCENT = "#234A70", "#E08A3C"

FEATURES = [
    "recency_days",
    "frequency",
    "monetary",
    "tenure_days",
    "avg_basket_size",
    "avg_days_between_orders",
    "purchase_regularity",   # CV of inter-purchase gaps; lower = more regular buyer
    "recency_ratio",         # recency_days / avg_days_between_orders; <1 = due to buy soon
]


def build_dataset(db_path: Path) -> pd.DataFrame:
    with sqlite3.connect(db_path) as con:
        tx = pd.read_sql(
            "SELECT customer_id, invoice, stock_code, invoice_date, revenue "
            "FROM transactions",
            con,
            parse_dates=["invoice_date"],
        )

    max_date = tx["invoice_date"].max()
    cutoff = max_date - pd.Timedelta(days=HORIZON_DAYS)

    pre = tx[tx["invoice_date"] <= cutoff]
    post_customers = set(tx[tx["invoice_date"] > cutoff]["customer_id"].unique())

    # ── base RFM + behavioural features ─────────────────────────────────────
    g = pre.groupby("customer_id")
    feats = pd.DataFrame(
        {
            "recency_days": (cutoff - g["invoice_date"].max()).dt.days,
            "frequency": g["invoice"].nunique(),
            "monetary": g["revenue"].sum(),
            "tenure_days": (cutoff - g["invoice_date"].min()).dt.days,
            "avg_basket_size": (
                pre.groupby(["customer_id", "invoice"])["stock_code"]
                .nunique()
                .groupby("customer_id")
                .mean()
            ),
        }
    ).reset_index()

    # ── inter-purchase interval features (vectorised) ────────────────────────
    # One row per (customer, invoice), earliest timestamp per invoice
    inv_dates = (
        pre.groupby(["customer_id", "invoice"])["invoice_date"]
        .min()
        .reset_index()
        .sort_values(["customer_id", "invoice_date"])
    )
    inv_dates["prev_date"] = inv_dates.groupby("customer_id")["invoice_date"].shift(1)
    inv_dates["gap_days"] = (inv_dates["invoice_date"] - inv_dates["prev_date"]).dt.days
    gaps = inv_dates.dropna(subset=["gap_days"])

    gap_stats = (
        gaps.groupby("customer_id")["gap_days"]
        .agg(avg_days_between_orders="mean", std_days_between_orders="std")
        .reset_index()
    )
    gap_stats["purchase_regularity"] = (
        gap_stats["std_days_between_orders"] / gap_stats["avg_days_between_orders"]
    )

    feats = feats.merge(
        gap_stats[["customer_id", "avg_days_between_orders", "purchase_regularity"]],
        on="customer_id",
        how="left",
    )

    # Single-purchase customers have no gap stats — fill with population medians
    med_interval = feats["avg_days_between_orders"].median()
    med_regularity = feats["purchase_regularity"].median()
    feats["avg_days_between_orders"] = feats["avg_days_between_orders"].fillna(med_interval)
    feats["purchase_regularity"] = feats["purchase_regularity"].fillna(med_regularity)

    # recency_ratio: how overdue the customer is relative to their own rhythm
    feats["recency_ratio"] = feats["recency_days"] / feats["avg_days_between_orders"].clip(lower=1)

    # ── label ────────────────────────────────────────────────────────────────
    feats["will_purchase"] = feats["customer_id"].isin(post_customers).astype(int)

    print(f"Cutoff: {cutoff.date()}  |  customers in pre-window: {len(feats):,}")
    print(f"Purchase rate (label=1): {feats['will_purchase'].mean():.1%}")
    return feats


def tune_logreg(X_tr_scaled: np.ndarray, y_tr: pd.Series) -> tuple[LogisticRegression, dict, float]:
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    grid = GridSearchCV(
        LogisticRegression(max_iter=1000, class_weight="balanced"),
        param_grid={"C": [0.01, 0.05, 0.1, 0.5, 1, 5, 10]},
        scoring="roc_auc",
        cv=cv,
    )
    grid.fit(X_tr_scaled, y_tr)
    return grid.best_estimator_, grid.best_params_, grid.best_score_


def tune_xgboost(X_tr: pd.DataFrame, y_tr: pd.Series, spw: float) -> tuple[XGBClassifier, dict, float]:
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    param_dist = {
        "n_estimators": [100, 150, 200, 300, 400, 500],
        "max_depth": [2, 3, 4, 5, 6],
        "learning_rate": [0.01, 0.03, 0.05, 0.1, 0.2],
        "subsample": [0.6, 0.7, 0.8, 0.9, 1.0],
        "colsample_bytree": [0.6, 0.7, 0.8, 0.9, 1.0],
        "min_child_weight": [1, 3, 5, 7, 10],
        "gamma": [0, 0.1, 0.3, 0.5, 1.0],
        "reg_alpha": [0, 0.1, 0.5, 1.0],
        "reg_lambda": [0.5, 1.0, 1.5, 2.0],
    }
    base = XGBClassifier(eval_metric="logloss", random_state=42, scale_pos_weight=spw)
    search = RandomizedSearchCV(
        base, param_dist, n_iter=40, scoring="roc_auc", cv=cv, random_state=42, n_jobs=-1,
    )
    search.fit(X_tr, y_tr)
    return search.best_estimator_, search.best_params_, search.best_score_


def gain_curve(y_true: pd.Series, scores: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    order = np.argsort(-scores)
    y_sorted = np.asarray(y_true)[order]
    cum_positives = np.cumsum(y_sorted)
    total_positives = y_sorted.sum()
    pct_population = np.arange(1, len(y_sorted) + 1) / len(y_sorted)
    pct_captured = cum_positives / total_positives
    return pct_population, pct_captured


def plot_gain_chart(
    y_te: pd.Series, xgb_prob: np.ndarray, lr_prob: np.ndarray, out_dir: Path
) -> None:
    fig, ax = plt.subplots(figsize=(6.5, 5))
    for prob, name, color in [
        (xgb_prob, "XGBoost (tuned)", BLUE),
        (lr_prob, "Logistic Regression (tuned)", ACCENT),
    ]:
        pct_pop, pct_cap = gain_curve(y_te, prob)
        ax.plot(pct_pop * 100, pct_cap * 100, color=color, label=name)
    ax.plot([0, 100], [0, 100], "k--", alpha=0.4, label="Random targeting")
    ax.set_xlabel("% of customers targeted (ranked by propensity score)")
    ax.set_ylabel("% of actual 30-day buyers captured")
    ax.set_title("Cumulative Gain Chart")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(out_dir / "propensity_gain_chart.png", dpi=150)
    plt.close(fig)

    print("\nGain / lift at key targeting thresholds (XGBoost, tuned):")
    pct_pop, pct_cap = gain_curve(y_te, xgb_prob)
    for pct in (0.1, 0.2, 0.3):
        idx = int(len(y_te) * pct) - 1
        capture = pct_cap[idx]
        lift = capture / pct
        print(f"  Top {int(pct * 100)}% of customers by score: captures {capture:.1%} of actual buyers ({lift:.1f}x lift over random)")


def main(db_path: Path = DB_PATH, out_dir: Path = OUT_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    data = build_dataset(db_path)

    X, y = data[FEATURES], data["will_purchase"]
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # ── logistic regression, tuned via 5-fold CV grid search over C ───────────
    scaler = StandardScaler().fit(X_tr)
    X_tr_scaled, X_te_scaled = scaler.transform(X_tr), scaler.transform(X_te)
    lr, lr_params, lr_cv_auc = tune_logreg(X_tr_scaled, y_tr)
    lr_prob = lr.predict_proba(X_te_scaled)[:, 1]
    lr_auc = roc_auc_score(y_te, lr_prob)

    # ── XGBoost, tuned via randomized search (40 draws, 5-fold CV) ────────────
    # scale_pos_weight handles class imbalance without discarding majority-class signal
    spw = (y_tr == 0).sum() / max((y_tr == 1).sum(), 1)
    xgb, xgb_params, xgb_cv_auc = tune_xgboost(X_tr, y_tr, spw)
    xgb_prob = xgb.predict_proba(X_te)[:, 1]
    xgb_auc = roc_auc_score(y_te, xgb_prob)

    print(f"\nLogistic Regression — best C={lr_params['C']}, CV AUC={lr_cv_auc:.3f}, test AUC={lr_auc:.3f}")
    print(f"XGBoost — CV AUC={xgb_cv_auc:.3f}, test AUC={xgb_auc:.3f}")
    print(f"  best params: {xgb_params}")
    print("\nXGBoost classification report (threshold 0.5):")
    print(classification_report(y_te, (xgb_prob >= 0.5).astype(int), digits=3))

    # ── write scores to SQLite ───────────────────────────────────────────────
    scores = data[["customer_id"]].copy()
    scores["propensity_score"] = xgb.predict_proba(X)[:, 1].round(4)
    with sqlite3.connect(db_path) as con:
        scores.to_sql("propensity_scores", con, if_exists="replace", index=False)
        con.commit()
    print(f"\npropensity_scores written to SQLite ({len(scores):,} rows)")

    # ── figure 1: ROC curves ─────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(6, 5))
    for prob, auc, name, color in [
        (lr_prob, lr_auc, "Logistic Regression", ACCENT),
        (xgb_prob, xgb_auc, "XGBoost", BLUE),
    ]:
        fpr, tpr, _ = roc_curve(y_te, prob)
        ax.plot(fpr, tpr, color=color, label=f"{name} (AUC = {auc:.3f})")
    ax.plot([0, 1], [0, 1], "k--", alpha=0.4)
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("Purchase Propensity ROC Curves (30-day horizon)")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(out_dir / "propensity_roc.png", dpi=150)
    plt.close(fig)

    # ── figure 2: feature importance ─────────────────────────────────────────
    imp = pd.Series(xgb.feature_importances_, index=FEATURES).sort_values()
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.barh(imp.index, imp.values, color=BLUE)
    ax.set_title("Purchase Propensity Drivers (XGBoost feature importance)")
    fig.tight_layout()
    fig.savefig(out_dir / "propensity_feature_importance.png", dpi=150)
    plt.close(fig)

    # ── figure 3: propensity by K-Means segment ──────────────────────────────
    try:
        with sqlite3.connect(db_path) as con:
            segs = pd.read_sql("SELECT customer_id, segment FROM segments", con)
        seg_scores = scores.merge(segs, on="customer_id", how="inner")
        if not seg_scores.empty:
            order = (
                seg_scores.groupby("segment")["propensity_score"]
                .mean()
                .sort_values(ascending=False)
            )
            fig, ax = plt.subplots(figsize=(8, 4.5))
            ax.bar(order.index, order.values, color=ACCENT)
            ax.set_title("Avg 30-Day Purchase Propensity by Segment")
            ax.set_ylabel("Mean propensity score")
            ax.set_ylim(0, 1)
            ax.tick_params(axis="x", rotation=20)
            fig.tight_layout()
            fig.savefig(out_dir / "propensity_by_segment.png", dpi=150)
            plt.close(fig)
    except Exception as exc:
        print(f"Skipping propensity_by_segment.png: {exc}")

    # ── figure 4: cumulative gain / lift chart ───────────────────────────────
    plot_gain_chart(y_te, xgb_prob, lr_prob, out_dir)

    print(f"\nFigures written to {out_dir}")


if __name__ == "__main__":
    main()
