"""
Generate an LLM-powered SmartCart insight brief from computed JSON inputs.

This optional script calls the OpenAI API. It keeps the deterministic generator
as the default/fallback path, while allowing the team to produce a true
LLM-written brief from the same evidence contract and guardrails.

Safety rules:
- API keys are read from OPENAI_API_KEY or a local .env file and are never
  written to GitHub.
- The model receives only `data/insight_inputs.json` plus explicit guardrails.
- Segment actions must preserve the exact `recommended_action` text from the
  structured input so recommendations stay traceable.

Usage:
    python src/generate_insight_brief_llm.py
    python src/generate_insight_brief_llm.py --model gpt-4.1-mini
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openai import OpenAI


# Causal trigger phrases that suggest the LLM has drifted beyond observational framing.
_CAUSAL_PHRASES = [
    "causes",
    "caused by",
    "leads to",
    "led to",
    "resulted in",
    "is responsible for",
    "proves that",
    "treatment effect",
    "directly impacts",
    "directly affects",
    "causal relationship",
    "prove causation",
]


ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / "data" / "insight_inputs.json"
OUTPUT_PATH = ROOT / "reports" / "ai_insight_brief_llm.md"
VALIDATION_PATH = ROOT / "reports" / "ai_insight_brief_llm_validation.md"
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


def load_env_file() -> None:
    """Load a local .env file without adding an extra dependency."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"Insight input not found: {path}. Run src/prepare_insight_inputs.py first."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def build_system_prompt() -> str:
    return """
You are writing SmartCart's final evidence-based AI insight brief for a business audience.
Use only the JSON evidence provided by the user. Do not invent, extrapolate, or silently
recompute any metric. Do not expose customer-level identifiers. Do not make causal claims;
statistical comparisons are observational unless the evidence explicitly says otherwise.

Required behavior:
- Include one actionable recommendation for every segment in the JSON.
- For each segment, preserve the exact recommended_action text from the JSON.
- Cite the supporting numbers next to each action.
- Use BG/NBD CLV when available, otherwise use baseline CLV.
- Explain predictive churn only from held-out/cutoff-based outputs when available.
- Preserve limitations: observational comparisons, leakage-free churn split, BG/NBD
  one-time-buyer/P(alive) caveat if relevant, and no invented metrics.
- Write concise Markdown suitable for a dashboard/report appendix.
""".strip()


def build_user_prompt(payload: dict[str, Any]) -> str:
    evidence_json = json.dumps(payload, indent=2, ensure_ascii=False)
    return f"""
Create the SmartCart AI Insight Brief from the JSON evidence below.

Use this exact Markdown structure:
# SmartCart AI Insight Brief - LLM Generated Candidate
## Scope and Guardrails
## Executive Summary
## Segment Actions
## Predictive Churn Signals
## Group Comparison Signals
## Product Recommendation Signals
## Limitations and Human Review Checklist

Important: every number in the brief must appear in the JSON. For each segment action,
use the segment's exact `recommended_action` text.

JSON evidence:
```json
{evidence_json}
```
""".strip()


def call_openai(payload: dict[str, Any], model: str) -> str:
    load_env_file()
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Set it in PowerShell with "
            "$env:OPENAI_API_KEY='your_key' or put it in a local .env file."
        )

    client = OpenAI()
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": build_system_prompt()},
            {"role": "user", "content": build_user_prompt(payload)},
        ],
        temperature=0.2,
    )
    return response.output_text.strip()


def _extract_numbers(text: str) -> list[float]:
    """Extract all numeric values from brief text, including percentage conversions."""
    results = []
    for match in re.finditer(r'\b([\d,]+(?:\.\d+)?)\s*(%?)', text):
        raw = match.group(1).replace(',', '')
        try:
            val = float(raw)
        except ValueError:
            continue
        if match.group(2) == '%':
            results.append(val)
            results.append(round(val / 100, 6))
        else:
            results.append(val)
    return results


def _flatten_numbers(obj: Any, _depth: int = 0) -> list[float]:
    """Recursively collect all finite numeric values from a JSON-like object."""
    if _depth > 12:
        return []
    if isinstance(obj, bool):
        return []
    if isinstance(obj, (int, float)):
        v = float(obj)
        if math.isfinite(v):
            return [v, round(v * 100, 6)]
    if isinstance(obj, dict):
        out: list[float] = []
        for val in obj.values():
            out.extend(_flatten_numbers(val, _depth + 1))
        return out
    if isinstance(obj, list):
        out = []
        for item in obj:
            out.extend(_flatten_numbers(item, _depth + 1))
        return out
    return []


def _matches_json(value: float, json_values: list[float], tol: float = 0.015) -> bool:
    """True if value is within tol (relative) of any JSON numeric value."""
    if value == 0.0:
        return 0.0 in json_values
    return any(abs(value - j) / max(abs(j), 1e-9) <= tol for j in json_values)


def validate_brief(text: str, payload: dict[str, Any]) -> tuple[list[str], list[str]]:
    passed: list[str] = []
    warnings: list[str] = []

    # --- Existing checks ---
    segments = payload.get("segments", [])
    for segment in segments:
        name = str(segment.get("segment", "")).strip()
        action = str(segment.get("recommended_action", "")).strip()
        if name and name in text:
            passed.append(f"Segment present: {name}")
        else:
            warnings.append(f"Missing segment name: {name}")
        if action and action in text:
            passed.append(f"Exact recommended_action preserved for {name}")
        else:
            warnings.append(f"Exact recommended_action not found for {name}")

    if "customer_id" not in text:
        passed.append("No customer_id field exposed in brief text")
    else:
        warnings.append("Brief text contains customer_id; review before use")

    if "invent" in text.lower() or "computed" in text.lower() or "json" in text.lower():
        passed.append("Traceability / no-invention guardrail is stated")
    else:
        warnings.append("Traceability / no-invention guardrail may be missing")

    # --- NEW: number traceability check ---
    json_values = _flatten_numbers(payload)
    unmatched = [
        n for n in _extract_numbers(text)
        if n >= 10 and not _matches_json(n, json_values)
    ]
    if not unmatched:
        passed.append("All cited numbers traced to JSON values within 1.5% tolerance")
    else:
        for n in unmatched[:5]:
            warnings.append(
                f"Number {n} in brief not matched to JSON — verify manually"
            )
        if len(unmatched) > 5:
            warnings.append(
                f"...and {len(unmatched) - 5} more unmatched numbers — review the full brief"
            )

    # --- NEW: enhanced causal language check ---
    text_lower = text.lower()

    # "observational" must appear in the Limitations or Scope section, not just anywhere
    anchor = ""
    for heading in ("## Limitations", "## Scope"):
        idx = text.find(heading)
        if idx != -1:
            anchor += text[idx:]
    if "observational" in anchor.lower():
        passed.append("'Observational' limitation confirmed in Limitations or Scope section")
    else:
        warnings.append(
            "'Observational' not found in Limitations or Scope section — add explicit caveat"
        )

    # Scan for strong causal trigger phrases not immediately qualified
    causal_hits: list[str] = []
    for phrase in _CAUSAL_PHRASES:
        start = 0
        while True:
            idx = text_lower.find(phrase, start)
            if idx == -1:
                break
            context = text_lower[max(0, idx - 40): idx + len(phrase) + 40]
            negated = any(
                q in context
                for q in ("does not", "not causal", "observational", "does not imply", "no causal")
            )
            if not negated:
                causal_hits.append(phrase)
            start = idx + 1

    if not causal_hits:
        passed.append("No unqualified causal language detected")
    else:
        for phrase in dict.fromkeys(causal_hits):
            warnings.append(f"Possible causal language: '{phrase}' — review in context")

    return passed, warnings


def write_validation(path: Path, passed: list[str], warnings: list[str], model: str) -> None:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# LLM Insight Brief Validation",
        "",
        f"Generated: {generated_at}",
        f"Model: `{model}`",
        "",
        "## Passed Checks",
        "",
    ]
    lines.extend(f"- {item}" for item in passed)
    lines.extend(["", "## Warnings for Human Review", ""])
    if warnings:
        lines.extend(f"- {item}" for item in warnings)
    else:
        lines.append("- No warnings from automated validation.")
    lines.extend(
        [
            "",
            "## Required Human Review",
            "",
            "- Confirm every cited number exists in `data/insight_inputs.json`.",
            "- Confirm no observational result is described as causal.",
            "- Confirm every segment has one data-backed action.",
            "- Confirm API-generated wording is appropriate for final submission.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=INPUT_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--validation-output", type=Path, default=VALIDATION_PATH)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = load_payload(args.input)
    brief = call_openai(payload, args.model)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(brief + "\n", encoding="utf-8")

    passed, warnings = validate_brief(brief, payload)
    write_validation(args.validation_output, passed, warnings, args.model)

    print(f"LLM insight brief written to {args.output.relative_to(ROOT).as_posix()}")
    print(f"Validation report written to {args.validation_output.relative_to(ROOT).as_posix()}")
    if warnings:
        print("Warnings require human review:")
        for warning in warnings:
            print(f"- {warning}")


if __name__ == "__main__":
    main()
