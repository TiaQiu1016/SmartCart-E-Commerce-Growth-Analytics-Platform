"""
Generate a deterministic SmartCart insight brief from computed JSON inputs.

This script does not call an LLM. It converts `data/insight_inputs.json` into a
plain-language Markdown draft so the team can review the evidence, wording, and
guardrails before adding any future AI generation step.

Usage:
    python src/generate_insight_brief.py
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / "data" / "insight_inputs.json"
OUTPUT_PATH = ROOT / "reports" / "ai_insight_brief_draft.md"


def money(value: Any) -> str:
    if value is None:
        return "unavailable"
    return f"GBP {float(value):,.0f}"


def number(value: Any, digits: int = 2) -> str:
    if value is None:
        return "unavailable"
    return f"{float(value):,.{digits}f}"


def percent(value: Any, digits: int = 1) -> str:
    if value is None:
        return "unavailable"
    return f"{float(value) * 100:.{digits}f}%"


def load_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"Insight input not found: {path}. Run src/prepare_insight_inputs.py first."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def sort_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        segments,
        key=lambda row: (
            row.get("avg_clv_bgnbd")
            if row.get("avg_clv_bgnbd") is not None
            else row.get("avg_clv_estimate") or 0
        ),
        reverse=True,
    )


def segment_action(segment: dict[str, Any]) -> str:
    name = segment.get("segment", "Unknown segment")
    action = segment.get("recommended_action") or "Review this segment manually."
    clv = (
        segment.get("avg_clv_bgnbd")
        if segment.get("avg_clv_bgnbd") is not None
        else segment.get("avg_clv_estimate")
    )
    propensity = segment.get("avg_propensity_score")
    p_alive = segment.get("avg_p_alive")
    repeat_gap = segment.get("insufficient_repeat_history_share")

    evidence = [
        f"avg CLV {money(clv)}",
        f"purchase propensity {percent(propensity)}",
    ]
    if p_alive is not None:
        evidence.append(f"BG/NBD p_alive {percent(p_alive)}")
    if repeat_gap is not None:
        evidence.append(f"insufficient repeat history {percent(repeat_gap)}")

    return f"- **{name}:** {action} Evidence: {', '.join(evidence)}."


def top_group_findings(group_comparisons: list[dict[str, Any]], limit: int = 5) -> list[str]:
    usable = []
    seen: set[tuple[str, str]] = set()
    for row in group_comparisons:
        comparison = str(row.get("comparison", ""))
        metric = str(row.get("metric", ""))
        if row.get("effect_size") is None or not row.get("effect_size_name"):
            continue
        if "churned_snapshot" in comparison or metric == "churned_snapshot":
            continue
        key = (comparison, metric)
        if key in seen:
            continue
        seen.add(key)
        usable.append(row)
    usable.sort(key=lambda row: abs(float(row["effect_size"])), reverse=True)
    findings = []
    for row in usable[:limit]:
        findings.append(
            "- "
            f"{row.get('comparison')} on `{row.get('metric')}`: "
            f"{row.get('effect_size_name')} = {number(row.get('effect_size'), 3)}, "
            f"p = {number(row.get('p_value'), 4)}. "
            "Interpret this as observational evidence, not a causal effect."
        )
    return findings


def top_recommendations(recommendations: list[dict[str, Any]], limit: int = 5) -> list[str]:
    lines = []
    for row in recommendations[:limit]:
        item = (row.get("description") or row.get("stock_code") or "").strip()
        rec = (
            row.get("recommended_description")
            or row.get("recommended_stock_code")
            or ""
        ).strip()
        lines.append(
            "- "
            f"When customers buy **{item}**, consider recommending **{rec}** "
            f"(confidence {percent(row.get('confidence'))}, lift {number(row.get('lift'))})."
        )
    return lines


def build_brief(payload: dict[str, Any]) -> str:
    segments = sort_segments(payload.get("segments", []))
    group_comparisons = payload.get("group_comparisons", [])
    recommendations = payload.get("top_product_recommendations", [])
    unavailable = payload.get("unavailable_modules", [])
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# SmartCart AI Insight Brief Draft",
        "",
        f"Generated: {generated_at}",
        "",
        "## Scope and Guardrails",
        "",
        "This draft is generated from computed SmartCart outputs only. It does not "
        "invent metrics, recompute models, or make causal claims. A team member "
        "should verify the cited numbers before using the wording in the dashboard "
        "or final report.",
        "",
        "## Executive Summary",
        "",
    ]

    if segments:
        best = segments[0]
        lowest = segments[-1]
        lines.extend(
            [
                f"- The highest-value segment is **{best.get('segment')}**, with "
                f"average BG/NBD CLV of {money(best.get('avg_clv_bgnbd'))} "
                f"and average purchase propensity of {percent(best.get('avg_propensity_score'))}.",
                f"- The lowest-value segment is **{lowest.get('segment')}**, with "
                f"average BG/NBD CLV of {money(lowest.get('avg_clv_bgnbd'))} "
                f"and average purchase propensity of {percent(lowest.get('avg_propensity_score'))}.",
                "- Recommendations below are segment-specific and evidence-backed; "
                "they should be reviewed before being shown to retailers.",
            ]
        )
    else:
        lines.append("- Segment-level inputs are unavailable, so no segment actions are drafted.")

    lines.extend(["", "## Segment Actions", ""])
    if segments:
        lines.extend(segment_action(segment) for segment in segments)
    else:
        lines.append("Segment actions are unavailable until `segments` and CLV outputs exist.")

    lines.extend(["", "## Group Comparison Signals", ""])
    group_lines = top_group_findings(group_comparisons)
    if group_lines:
        lines.extend(group_lines)
    else:
        lines.append("No group-comparison results are available yet.")

    lines.extend(["", "## Product Recommendation Signals", ""])
    recommendation_lines = top_recommendations(recommendations)
    if recommendation_lines:
        lines.extend(recommendation_lines)
    else:
        lines.append("No product recommendation outputs are available yet.")

    lines.extend(["", "## Missing Inputs and Limitations", ""])
    if unavailable:
        lines.extend(f"- {note}" for note in unavailable)
    else:
        lines.append("- No unavailable modules were reported in the structured input.")
    lines.append(
        "- Statistical group comparisons are observational. They should guide "
        "business review, not be presented as randomized treatment effects."
    )

    lines.extend(
        [
            "",
            "## Human Review Checklist",
            "",
            "- Confirm every number against `data/insight_inputs.json`.",
            "- Keep at least one data-backed action for every segment.",
            "- Preserve limitations when moving this draft into the dashboard.",
            "- Do not expose customer-level identifiers in the final brief.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=INPUT_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = load_payload(args.input)
    brief = build_brief(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(brief, encoding="utf-8")
    try:
        display_path = args.output.resolve().relative_to(ROOT)
    except ValueError:
        display_path = args.output.name
    print(f"Insight brief draft written to {display_path.as_posix()}")


if __name__ == "__main__":
    main()
