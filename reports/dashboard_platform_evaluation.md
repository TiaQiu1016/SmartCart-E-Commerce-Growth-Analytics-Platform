# Dashboard Platform Evaluation

The proposal named Streamlit as an example dashboard tool, but the team had not
formally evaluated alternatives. Before committing several weeks of build time,
we compared **Streamlit** and **Dash (Plotly)** hands-on by building matching
working prototypes against the real `smartcart.db` data, rather than deciding
on paper alone.

**Gradio was ruled out** at the desk-research stage: it is built for
single-model input/output demos, not multi-page BI dashboards with tables,
filters, and cross-linked charts, which is the shape SmartCart needs.

## Method

Built one page in each framework showing identical content pulled live from
`segments`, `clv`, and `segment_profiles`: three KPI cards (total customers,
total revenue, average CLV estimate), a "customers by segment" bar chart, an
"average CLV by segment" bar chart, and a segment profile table. Both apps use
the project's BLUE (`#234A70`) / ACCENT (`#E08A3C`) colors and Plotly for
charting, so the chart layer is directly comparable.

Code: [`dashboard/poc_streamlit/app.py`](../dashboard/poc_streamlit/app.py),
[`dashboard/poc_dash/app.py`](../dashboard/poc_dash/app.py).

## Findings

| | Streamlit | Dash |
| --- | --- | --- |
| Lines of code for identical output | ~85 | ~95 |
| KPI cards | Built-in `st.metric` widget, near-zero styling needed | No built-in equivalent; required a hand-written `kpi_card()` helper with inline CSS |
| Layout | `st.columns()`, declarative | Manual flexbox via nested `html.Div` + inline style dicts |
| Charts | Plotly (identical output to Dash) | Plotly (identical output to Streamlit) |
| Data table | Hit a real bug: `pyarrow 14.0.2` crashed on `st.dataframe()` due to a NumPy 2.x incompatibility; fixed by upgrading pyarrow to 24.0.0 | No issue. `dash_table` serializes via plain JSON and never touches Arrow |
| Default chrome | Small "Deploy" button (removable) | Dev toolbar at bottom (Plotly Cloud / Errors / Callbacks); needs `debug=False` for production |
| Caching | Built-in `@st.cache_data` decorator | Requires manual caching setup (e.g. Flask-Caching) |
| Deployment | One-click Streamlit Community Cloud | Needs a WSGI host (Render, Heroku, etc.) |

## Decision: Streamlit

Streamlit produced the same visual result in fewer lines, mainly because of
its built-in KPI/column widgets, which matters given the team's ~5-week
runway and Python-only (pandas/scikit-learn) skill set. The one real mark
against it, the pyarrow/NumPy dependency conflict, is a one-time environment
fix rather than a recurring development cost. Dash's main advantage,
avoiding that dependency chain, did not outweigh its extra boilerplate for
every KPI card and its weaker built-in caching and deployment story.

The full SmartCart dashboard will be built in Streamlit, wired to the
`segments`, `clv`, `churn`, `propensity_scores`, and `association_rules`
tables.
