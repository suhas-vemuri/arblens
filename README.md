# ArbLens

## About ArbLens

ArbLens is an options-market integrity and static-arbitrage research platform built in Python. It scans multiple stock and ETF option chains, cleans and validates quote data, filters contracts using liquidity requirements, verifies timestamp alignment, and applies quantitative no-arbitrage rules.

The project evaluates:

- Put-call parity
- Strike monotonicity
- Butterfly convexity
- European option-price bounds
- Quote quality and liquidity
- Bid-ask executable pricing
- Estimated transaction costs
- Repeated-scan persistence

ArbLens first identifies theoretical pricing violations using midpoint prices. It then repeats the analysis using displayed bid prices for sales and ask prices for purchases. Finally, it subtracts estimated transaction costs and ranks the findings by modeled net edge.

The interactive Streamlit dashboard allows users to enter custom tickers, control scan parameters, inspect each analysis stage, review eliminated contracts, study the quantitative methods, and understand how each result was calculated.

## Project Goal

The goal of ArbLens is not to promise profitable trades. Its purpose is to demonstrate how market-data engineering, quantitative finance, execution modeling, testing, and user-facing analytics can be combined into one complete research platform.

## Technology

- Python
- Pandas
- NumPy
- Streamlit
- Plotly
- Tradier API
- Pytest
- Ruff
- Git and GitHub

## Status

**ArbLens is complete.**

The final version includes the data provider, quote validation, liquidity screening, synchronization controls, static-arbitrage analysis, transaction-cost modeling, multi-symbol scanning, repeated scans, ranking, reporting, tests, documentation, and a deployed interactive dashboard.
