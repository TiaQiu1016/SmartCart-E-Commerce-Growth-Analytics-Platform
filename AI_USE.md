# AI Use Disclosure

Generative AI tools were used to assist with this project, including drafting and
editing documentation, structuring code, reviewing methodology risks, and improving
plain-language explanations. The project design, analytical decisions, code review,
and final outputs remain the team's own responsibility.

SmartCart also includes an optional OpenAI API workflow for the AI insight brief.
`src/generate_insight_brief_llm.py` sends a structured JSON file of computed model
outputs and guardrails to the API, then writes a candidate Markdown brief and a
validation report. The LLM is not allowed to invent metrics, recompute model
outputs, expose customer-level identifiers, or make causal claims from
observational comparisons.

All cited numbers in the AI brief are checked against `data/insight_inputs.json`,
and the brief requires one data-backed actionable recommendation per customer
segment. The LLM-generated wording is treated as a candidate output only; a human
reviewer must verify traceability, limitations, and business appropriateness before
using it in the dashboard, final report, or presentation.
