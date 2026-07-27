from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from arblens.cleaning import clean_quotes  # noqa: E402
from arblens.detection import run_all_checks, violations_to_frame  # noqa: E402

st.set_page_config(page_title="ArbLens", page_icon="🔎", layout="wide")

st.title("ArbLens")
st.caption("Options Market Integrity Dashboard — Version 0.1")

with st.sidebar:
    st.header("Analysis settings")
    uploaded = st.file_uploader("Upload an option-chain CSV", type=["csv"])
    spot = st.number_input("Underlying price", min_value=0.01, value=100.0, step=1.0)
    days = st.number_input("Days to expiration", min_value=1, value=30, step=1)
    rate = st.number_input("Risk-free rate", value=0.04, step=0.005, format="%.4f")
    dividend = st.number_input("Dividend yield", value=0.0, step=0.005, format="%.4f")

if uploaded is not None:
    raw = pd.read_csv(uploaded)
else:
    raw = pd.read_csv(PROJECT_ROOT / "data" / "sample_chain.csv")

cleaned, issues = clean_quotes(raw)
violations = run_all_checks(
    cleaned,
    spot=spot,
    time=float(days) / 365.0,
    rate=rate,
    dividend_yield=dividend,
)
violations_frame = violations_to_frame(violations)

midpoint_count = (
    int((violations_frame["price_basis"] == "midpoint").sum()) if not violations_frame.empty else 0
)
bid_ask_count = (
    int((violations_frame["price_basis"] == "bid_ask").sum()) if not violations_frame.empty else 0
)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Raw contracts", len(raw))
col2.metric("Clean contracts", len(cleaned))
col3.metric("Midpoint anomalies", midpoint_count)
col4.metric("Bid/ask survivors", bid_ask_count)

st.caption(
    "Bid/ask survivors are stronger, but they still do not prove that "
    "a live order would fill or remain profitable after fees."
)

left, right = st.columns([1.35, 1.0])
with left:
    st.subheader("Clean option chain")
    display_columns = [
        column
        for column in [
            "symbol",
            "expiration",
            "option_type",
            "strike",
            "bid",
            "ask",
            "mid",
            "volume",
            "open_interest",
        ]
        if column in cleaned.columns
    ]
    st.dataframe(cleaned[display_columns], use_container_width=True, hide_index=True)

with right:
    st.subheader("Midpoint curve")
    chart = px.line(
        cleaned,
        x="strike",
        y="mid",
        color="option_type",
        markers=True,
        title="Option midpoint by strike",
    )
    st.plotly_chart(chart, use_container_width=True)

st.subheader("Detected violations")
if violations_frame.empty:
    st.success("No violations detected with the current settings.")
else:
    st.dataframe(violations_frame, use_container_width=True, hide_index=True)

with st.expander("Quote-cleaning issues"):
    if not issues:
        st.write("No structural quote issues were found.")
    else:
        st.dataframe(
            pd.DataFrame([asdict(issue) for issue in issues]),
            use_container_width=True,
            hide_index=True,
        )

st.subheader("How to interpret this dashboard")
st.markdown(
    """
1. **Raw contracts** are the records loaded from the source file.
2. **Clean contracts** remain after structurally invalid records are removed.
3. **Midpoint anomalies** break a mathematical rule using the center of the bid–ask spread.
4. **Bid/ask survivors** still look inconsistent using executable top-of-book prices.
5. Version 0.1 does **not** account for fees, latency, margin,
   or whether a broker would fill the complete strategy.
"""
)
