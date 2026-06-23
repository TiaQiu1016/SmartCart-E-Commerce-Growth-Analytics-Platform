"""
poc_dash/app.py

Dash prototype for the SmartCart dashboard platform evaluation.
Pulls live data from data/smartcart.db (segments, clv, segment_profiles)
and renders the same content as poc_streamlit/app.py, for a hands-on comparison.

Usage:
    python dashboard/poc_dash/app.py
"""

from pathlib import Path
import sqlite3

import pandas as pd
import plotly.express as px
from dash import Dash, dash_table, dcc, html

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "smartcart.db"
BLUE, ACCENT = "#234A70", "#E08A3C"

with sqlite3.connect(DB_PATH) as con:
    segments = pd.read_sql("SELECT * FROM segments", con)
    clv = pd.read_sql("SELECT * FROM clv", con)
    profile = pd.read_sql("SELECT * FROM segment_profiles", con)

clv_seg = (
    segments[["customer_id", "segment"]]
    .merge(clv[["customer_id", "clv_estimate"]], on="customer_id")
    .groupby("segment", as_index=False)["clv_estimate"]
    .mean()
    .sort_values("clv_estimate", ascending=False)
)

fig1 = px.bar(
    profile.sort_values("customers", ascending=False),
    x="segment", y="customers", color_discrete_sequence=[BLUE],
    title="Customers by Segment",
)
fig1.update_layout(plot_bgcolor="white", paper_bgcolor="white")

fig2 = px.bar(
    clv_seg, x="segment", y="clv_estimate", color_discrete_sequence=[ACCENT],
    title="Avg CLV by Segment",
)
fig2.update_layout(plot_bgcolor="white", paper_bgcolor="white")


def kpi_card(label: str, value: str) -> html.Div:
    return html.Div(
        [
            html.Div(label, style={"fontSize": "14px", "color": "#6B7280"}),
            html.Div(value, style={"fontSize": "28px", "fontWeight": "bold", "color": BLUE}),
        ],
        style={
            "backgroundColor": "white", "padding": "16px", "borderRadius": "8px",
            "boxShadow": "0 1px 3px rgba(0,0,0,0.08)", "flex": "1", "margin": "0 8px",
        },
    )


app = Dash(__name__)

app.layout = html.Div(
    [
        html.H1("SmartCart — Customer Segments (Dash POC)", style={"color": BLUE}),
        html.Div(
            [
                kpi_card("Total Customers", f"{len(segments):,}"),
                kpi_card("Total Revenue", f"${clv['monetary'].sum():,.0f}"),
                kpi_card("Avg CLV Estimate", f"${clv['clv_estimate'].mean():,.0f}"),
            ],
            style={"display": "flex", "marginBottom": "24px"},
        ),
        html.Div(
            [
                dcc.Graph(figure=fig1, style={"flex": "1"}),
                dcc.Graph(figure=fig2, style={"flex": "1"}),
            ],
            style={"display": "flex", "marginBottom": "24px"},
        ),
        html.H3("Segment Profiles", style={"color": BLUE}),
        dash_table.DataTable(
            data=profile.to_dict("records"),
            columns=[{"name": c, "id": c} for c in profile.columns],
            style_cell={"textAlign": "left", "padding": "6px"},
            style_header={"backgroundColor": BLUE, "color": "white", "fontWeight": "bold"},
        ),
    ],
    style={"backgroundColor": "#FAFAFA", "padding": "24px", "fontFamily": "Arial"},
)

if __name__ == "__main__":
    app.run(debug=True, port=8051)
