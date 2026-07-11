"""
churn_model.py

Predicts customer churn using a leakage-free, time-split design.

Why a time split: defining churn as "recency > 90 days" on the full dataset and then
using recency as a feature would leak the label. Instead we split on a cutoff date:
  - Features are computed only from transactions on/before the cutoff.
  - Label = the customer makes NO purchase in the 90 days AFTER the cutoff (churned = 1).
This mirrors how churn would actually be predicted in production.

Models: logistic regression (baseline) and XGBoost.

Usage:
    python src/churn_model.py
"""

from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, roc_curve, classification_report
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "smartcart.db"
OUT_DIR = ROOT / "reports" / "figures"
HORIZON_DAYS = 90
FEATURES = ["recency_days", "frequency", "monetary", "tenure_days", "avg_basket_size"]
BLUE, ACCENT = "#234A70", "#E08A3C"


def build_dataset(db_path: Path) -> pd.DataFrame:
    with sqlite3.connect(db_path) as con:
        tx = pd.read_sql("SELECT customer_id, invoice, stock_code, invoice_date, revenue "
                         "FROM transactions", con, parse_dates=["invoice_date"])

    max_date = tx["invoice_date"].max()
    cutoff = max_date - pd.Timedelta(days=HORIZON_DAYS)

    pre = tx[tx["invoice_date"] <= cutoff]
    post_customers = set(tx[tx["invoice_date"] > cutoff]["customer_id"].unique())

    g = pre.groupby("customer_id")
    feats = pd.DataFrame({
        "recency_days": (cutoff - g["invoice_date"].max()).dt.days,
        "frequency": g["invoice"].nunique(),
        "monetary": g["revenue"].sum(),
        "tenure_days": (cutoff - g["invoice_date"].min()).dt.days,
        "avg_basket_size": pre.groupby(["customer_id", "invoice"])["stock_code"].nunique()
                              .groupby("customer_id").mean(),
    }).reset_index()

    # churned = 1 if the customer did NOT purchase in the post-cutoff window
    feats["churned"] = (~feats["customer_id"].isin(post_customers)).astype(int)
    feats["feature_cutoff_date"] = cutoff.date().isoformat()
    feats["label_window_days"] = HORIZON_DAYS
    print(f"Cutoff date: {cutoff.date()}  |  customers active before cutoff: {len(feats):,}")
    print(f"Churn rate: {feats['churned'].mean():.1%}")
    return feats


def write_churn_scores(
    data: pd.DataFrame,
    lr_prob_all: np.ndarray,
    xgb_prob_all: np.ndarray,
    test_index: pd.Index,
    db_path: Path,
) -> None:
    """Write customer-level churn labels and scores for downstream modules."""
    output = data[
        [
            "customer_id",
            "feature_cutoff_date",
            "label_window_days",
            "churned",
        ]
    ].copy()
    output["actual_churn_label"] = output.pop("churned")
    output["predicted_churn_probability"] = xgb_prob_all.round(6)
    output["baseline_logistic_churn_probability"] = lr_prob_all.round(6)
    output["is_test_set"] = output.index.isin(test_index).astype(int)
    output["model_name"] = "xgboost"
    output = output[
        [
            "customer_id",
            "feature_cutoff_date",
            "label_window_days",
            "actual_churn_label",
            "predicted_churn_probability",
            "baseline_logistic_churn_probability",
            "is_test_set",
            "model_name",
        ]
    ]
    with sqlite3.connect(db_path) as con:
        output.to_sql("churn_scores", con, if_exists="replace", index=False)
        con.commit()
    print(f"churn_scores table written: {len(output):,} rows")


def main(db_path: Path = DB_PATH, out_dir: Path = OUT_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    data = build_dataset(db_path)
    X, y = data[FEATURES], data["churned"]
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    # Logistic regression baseline (scaled)
    scaler = StandardScaler().fit(X_tr)
    lr = LogisticRegression(max_iter=1000, class_weight="balanced")
    lr.fit(scaler.transform(X_tr), y_tr)
    lr_prob = lr.predict_proba(scaler.transform(X_te))[:, 1]
    lr_auc = roc_auc_score(y_te, lr_prob)

    # XGBoost
    xgb = XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.1,
                        subsample=0.9, colsample_bytree=0.9, eval_metric="logloss",
                        random_state=42)
    xgb.fit(X_tr, y_tr)
    xgb_prob = xgb.predict_proba(X_te)[:, 1]
    xgb_auc = roc_auc_score(y_te, xgb_prob)

    lr_prob_all = lr.predict_proba(scaler.transform(X))[:, 1]
    xgb_prob_all = xgb.predict_proba(X)[:, 1]

    print(f"\nLogistic Regression AUC: {lr_auc:.3f}")
    print(f"XGBoost AUC:             {xgb_auc:.3f}")
    print("\nXGBoost classification report (threshold 0.5):")
    print(classification_report(y_te, (xgb_prob >= 0.5).astype(int), digits=3))

    # ROC curves
    fig, ax = plt.subplots(figsize=(6, 5))
    for prob, auc, name, color in [(lr_prob, lr_auc, "Logistic Regression", ACCENT),
                                   (xgb_prob, xgb_auc, "XGBoost", BLUE)]:
        fpr, tpr, _ = roc_curve(y_te, prob)
        ax.plot(fpr, tpr, color=color, label=f"{name} (AUC = {auc:.3f})")
    ax.plot([0, 1], [0, 1], "k--", alpha=0.4)
    ax.set_xlabel("False Positive Rate"); ax.set_ylabel("True Positive Rate")
    ax.set_title("Churn Model ROC Curves"); ax.legend(loc="lower right")
    fig.tight_layout(); fig.savefig(out_dir / "churn_model_roc.png", dpi=150); plt.close(fig)

    # Feature importance (XGBoost)
    imp = pd.Series(xgb.feature_importances_, index=FEATURES).sort_values()
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.barh(imp.index, imp.values, color=BLUE)
    ax.set_title("Churn Drivers (XGBoost feature importance)")
    fig.tight_layout(); fig.savefig(out_dir / "churn_feature_importance.png", dpi=150); plt.close(fig)

    write_churn_scores(data, lr_prob_all, xgb_prob_all, X_te.index, db_path)

    print("\nFigures written to reports/figures")


if __name__ == "__main__":
    main()
