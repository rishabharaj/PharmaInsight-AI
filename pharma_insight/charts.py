"""Small chart helpers keep the Streamlit page focused on presentation."""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


BLUE = "#2563eb"
TEAL = "#0d9488"


def monthly_chart(frame: pd.DataFrame) -> go.Figure:
    fig = px.line(frame, x="month", y="revenue_inr", markers=True,
                  labels={"month": "Month", "revenue_inr": "Revenue (₹)"})
    fig.update_traces(line_color=BLUE, line_width=3, marker_size=7,
                      fill="tozeroy", fillcolor="rgba(37, 99, 235, 0.10)")
    fig.update_layout(margin=dict(l=8, r=8, t=18, b=8), height=330,
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      hovermode="x unified", yaxis_tickprefix="₹", xaxis_type="category")
    return fig


def product_chart(frame: pd.DataFrame) -> go.Figure:
    shown = frame.head(6).sort_values("revenue_inr")
    fig = px.bar(shown, x="revenue_inr", y="product_name", orientation="h",
                 color_discrete_sequence=[BLUE],
                 labels={"revenue_inr": "Revenue (₹)", "product_name": "Product"})
    fig.update_layout(margin=dict(l=8, r=8, t=18, b=8), height=330,
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      xaxis_tickprefix="₹", showlegend=False)
    return fig


def region_chart(frame: pd.DataFrame) -> go.Figure:
    shown = frame.sort_values("revenue_inr")
    fig = px.bar(shown, x="revenue_inr", y="region_name", orientation="h",
                 color_discrete_sequence=[TEAL],
                 labels={"revenue_inr": "Revenue (₹)", "region_name": "Region"})
    fig.update_layout(margin=dict(l=8, r=8, t=18, b=8), height=330,
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      xaxis_tickprefix="₹", showlegend=False)
    return fig
