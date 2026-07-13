"""
Prepare structured, computed inputs for the future AI insight-brief generator.

This script does not call an LLM. It reads existing SQLite outputs, aggregates
them into a compact JSON contract, and explicitly reports unavailable modules.

Usage:
    python src/prepare_insight_inputs.py
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "smartcart.db"
OUTPUT_PATH = ROOT / "data" / "insight_inputs.json"


def table_exists(con: sqlite3.Connection, table: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def table_columns(con: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in con.execute(f'PRAGMA table_info("{table}")')}


def records(df: pd.DataFrame) -> list[dict[str, Any]]:
    clean = df.astype(object).where(pd.notna(df), None)
    return clean.to_dict(orient="records")


def finite_or_none(value: Any) -> float | None:
    if value is None or not math.isfinite(float(value)):
        return None
    return round(float(value), 4)


def build_segment_inputs(con: sqlite3.Connection) -> list[dict[str, Any]]:
    required = {"segments", "clv"}
    if not all(table_exists(con, table) for table in required):
        return []

    segment_cols = table_columns(con, "segments")
    action_sql = (
        "MAX(s.recommended_action) AS recommended_action"
        if "recommended_action" in segment_cols
        else "NULL AS recommended_action"
    )
    propensity_join = ""
    propensity_select = "NULL AS avg_propensity_score"
    if table_exists(con, "propensity_scores"):
        propensity_join = (
            "LEFT JOIN propensity_scores p ON s.customer_id = p.customer_id"
        )
        propensity_select = "AVG(p.propensity_score) AS avg_propensity_score"
    bgnbd_join = ""
    bgnbd_select = """
            NULL AS avg_clv_bgnbd,
            NULL AS avg_p_alive,
            NULL AS avg_pred_active_purchase_weeks_12m,
            NULL AS insufficient_repeat_history_share
    """
    if table_exists(con, "clv_bgnbd"):
        bgnbd_cols = table_columns(con, "clv_bgnbd")
        required_bgnbd = {
            "customer_id",
            "clv_bgnbd",
            "p_alive",
            "pred_active_purchase_weeks_12m",
            "repeat_history",
        }
        if required_bgnbd.issubset(bgnbd_cols):
            bgnbd_join = "LEFT JOIN clv_bgnbd b ON s.customer_id = b.customer_id"
            bgnbd_select = """
            AVG(b.clv_bgnbd) AS avg_clv_bgnbd,
            AVG(b.p_alive) AS avg_p_alive,
            AVG(b.pred_active_purchase_weeks_12m) AS avg_pred_active_purchase_weeks_12m,
            AVG(CASE WHEN b.repeat_history = 'insufficient' THEN 1.0 ELSE 0.0 END)
                AS insufficient_repeat_history_share
            """

    query = f"""
        SELECT
            s.segment,
            COUNT(DISTINCT s.customer_id) AS customer_count,
            AVG(s.recency_days) AS avg_recency_days,
            AVG(s.frequency) AS avg_frequency,
            AVG(s.monetary) AS avg_monetary,
            AVG(c.clv_estimate) AS avg_clv_estimate,
            {bgnbd_select},
            {propensity_select},
            {action_sql}
        FROM segments s
        LEFT JOIN clv c ON s.customer_id = c.customer_id
        {propensity_join}
        {bgnbd_join}
        GROUP BY s.segment
        ORDER BY avg_clv_estimate DESC
    """
    frame = pd.read_sql(query, con)
    numeric = [
        "avg_recency_days",
        "avg_frequency",
        "avg_monetary",
        "avg_clv_estimate",
        "avg_clv_bgnbd",
        "avg_p_alive",
        "avg_pred_active_purchase_weeks_12m",
        "insufficient_repeat_history_share",
        "avg_propensity_score",
    ]
    for column in numeric:
        frame[column] = frame[column].map(finite_or_none)
    return records(frame)


def build_group_comparisons(con: sqlite3.Connection) -> list[dict[str, Any]]:
    if not table_exists(con, "group_comparison_results"):
        return []
    frame = pd.read_sql(
        """
        SELECT comparison, test_type, metric, group_a, group_b,
               group_a_n, group_b_n, group_a_mean, group_b_mean,
               statistic, p_value, effect_size, effect_size_name
        FROM group_comparison_results
        ORDER BY comparison, metric, test_type
        """,
        con,
    )
    for column in [
        "group_a_mean",
        "group_b_mean",
        "statistic",
        "p_value",
        "effect_size",
    ]:
        frame[column] = frame[column].map(finite_or_none)
    return records(frame)


def build_market_basket_inputs(con: sqlite3.Connection) -> list[dict[str, Any]]:
    if not table_exists(con, "product_recommendations"):
        return []
    columns = table_columns(con, "product_recommendations")
    desired = [
        "stock_code",
        "description",
        "recommended_stock_code",
        "recommended_description",
        "rule_type",
        "support",
        "confidence",
        "lift",
    ]
    selected = [column for column in desired if column in columns]
    if not selected:
        return []
    quoted = ", ".join(f'"{column}"' for column in selected)
    order = '"lift" DESC' if "lift" in selected else "rowid"
    frame = pd.read_sql(
        f"SELECT {quoted} FROM product_recommendations ORDER BY {order} LIMIT 10",
        con,
    )
    for column in ["support", "confidence", "lift"]:
        if column in frame:
            frame[column] = frame[column].map(finite_or_none)
    return records(frame)


def build_predictive_churn_inputs(
    con: sqlite3.Connection,
) -> tuple[list[dict[str, Any]], str | None]:
    if table_exists(con, "segment_churn_v2_summary"):
        frame = pd.read_sql(
            """
            SELECT
                segment,
                evaluated_customers,
                actual_future_churn_rate,
                avg_predicted_churn_probability,
                validation_scope,
                feature_cutoff_date,
                label_window_days
            FROM segment_churn_v2_summary
            WHERE validation_scope = 'heldout_test'
            ORDER BY actual_future_churn_rate DESC
            """,
            con,
        )
        if not frame.empty:
            for column in [
                "actual_future_churn_rate",
                "avg_predicted_churn_probability",
            ]:
                frame[column] = frame[column].map(finite_or_none)
            return records(frame), None

    table = "churn_scores"
    required = {
        "customer_id",
        "actual_churn_label",
        "predicted_churn_probability",
    }
    if not table_exists(con, table):
        return [], (
            "Predictive churn input is unavailable: expected table `churn_scores` "
            "has not been written by the churn module."
        )
    if not required.issubset(table_columns(con, table)):
        missing = sorted(required - table_columns(con, table))
        return [], f"Predictive churn input is unavailable: missing columns {missing}."
    if not table_exists(con, "segments"):
        return [], "Predictive churn input is unavailable: `segments` table is missing."

    churn_cols = table_columns(con, table)
    where_clause = "WHERE c.is_test_set = 1" if "is_test_set" in churn_cols else ""
    frame = pd.read_sql(
        f"""
        SELECT
            s.segment,
            COUNT(*) AS evaluated_customers,
            AVG(c.actual_churn_label) AS actual_future_churn_rate,
            AVG(c.predicted_churn_probability) AS avg_predicted_churn_probability
        FROM churn_scores c
        INNER JOIN segments s ON c.customer_id = s.customer_id
        {where_clause}
        GROUP BY s.segment
        ORDER BY actual_future_churn_rate DESC
        """,
        con,
    )
    for column in [
        "actual_future_churn_rate",
        "avg_predicted_churn_probability",
    ]:
        frame[column] = frame[column].map(finite_or_none)
    return records(frame), None


def build_payload(db_path: Path) -> dict[str, Any]:
    if not db_path.exists():
        raise FileNotFoundError(
            f"Database not found: {db_path}. Run the analysis pipeline first."
        )

    unavailable: list[str] = []
    with sqlite3.connect(db_path) as con:
        if not table_exists(con, "clv_bgnbd"):
            unavailable.append(
                "Enhanced CLV input is unavailable: `clv_bgnbd` is missing. "
                "Run `python src/clv_bgnbd.py` after rebuilding the database."
            )
        elif not {
            "customer_id",
            "clv_bgnbd",
            "p_alive",
            "pred_active_purchase_weeks_12m",
            "repeat_history",
        }.issubset(table_columns(con, "clv_bgnbd")):
            unavailable.append(
                "Enhanced CLV input is unavailable: `clv_bgnbd` exists but is "
                "missing one or more required BG/NBD output columns."
            )

        if not table_exists(con, "propensity_scores"):
            unavailable.append(
                "Purchase-propensity input is unavailable: "
                "`propensity_scores` is missing."
            )

        segments = build_segment_inputs(con)
        if not segments:
            unavailable.append(
                "Segmentation/CLV input is unavailable: `segments` or `clv` is missing."
            )

        group_comparisons = build_group_comparisons(con)
        if not group_comparisons:
            unavailable.append(
                "Group comparison input is unavailable: "
                "`group_comparison_results` is missing."
            )

        market_basket = build_market_basket_inputs(con)
        if not market_basket:
            unavailable.append(
                "Market-basket input is unavailable: "
                "`product_recommendations` is missing."
            )

        churn_by_segment, churn_note = build_predictive_churn_inputs(con)
        if churn_note:
            unavailable.append(churn_note)

    return {
        "metadata": {
            "schema_version": "1.1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "source": "Computed SmartCart SQLite outputs only",
        },
        "segments": segments,
        "predictive_churn_by_segment": churn_by_segment,
        "group_comparisons": group_comparisons,
        "top_product_recommendations": market_basket,
        "unavailable_modules": unavailable,
        "generation_requirements": {
            "one_data_backed_action_per_segment": True,
            "must_cite_input_fields": True,
            "must_report_limitations": True,
            "may_invent_metrics": False,
            "causal_language_allowed": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(args.db)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    try:
        display_path = args.output.resolve().relative_to(ROOT)
    except ValueError:
        display_path = args.output.name
    print(f"Insight inputs written to {display_path.as_posix()}")
    for note in payload["unavailable_modules"]:
        print(f"Unavailable: {note}")


if __name__ == "__main__":
    main()
