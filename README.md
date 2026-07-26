# ArbLens

**ArbLens** is an options-market integrity research platform. It ingests option-chain data, cleans unreliable quotes, calculates implied volatility, and checks whether related option prices violate static no-arbitrage relationships.

This starter repository is **Version 0.1**: a working local prototype built around sample data. It is intentionally structured so it can grow into a real-data analytical platform.

## What works now

- European Black–Scholes call and put pricing
- Implied-volatility inversion using Brent's method
- Quote cleaning and validation
- Price-bound checks
- Call/put strike-monotonicity checks
- Butterfly-convexity checks
- Put–call parity checks
- Midpoint versus executable bid/ask comparison
- A Streamlit dashboard using a sample option chain
- Automated unit tests and GitHub Actions
- A configurable Tradier connector skeleton for later real-data use

## What does not exist yet

- A production market-data subscription
- Repeated live snapshots
- A historical database
- Quote-repair optimization
- Brokerage paper-order execution
- A claim that any detected anomaly is profitable

## Repository structure

```text
arblens-starter/
├── dashboard/                 # Streamlit user interface
├── data/                      # Sample chain and future snapshots
├── docs/                      # Project plan, roadmap, and GitHub guide
├── scripts/                   # Utility scripts
├── src/arblens/               # Core Python package
│   └── providers/             # Market-data adapters
├── tests/                     # Automated tests
├── .github/workflows/         # Continuous integration
├── .env.example               # Safe API-key template
└── pyproject.toml             # Python dependencies and tool settings
```

## Quick start

### 1. Install Python

Use Python 3.11 or newer.

### 2. Create a virtual environment

**Windows PowerShell**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**macOS/Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install the project

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

### 4. Run the tests

```bash
pytest
```

### 5. Analyze the sample chain in the terminal

```bash
python -m arblens data/sample_chain.csv
```

### 6. Launch the dashboard

```bash
streamlit run dashboard/app.py
```

## Current research question

> How many apparent option-price violations remain after invalid records are removed and executable bid/ask prices are used instead of midpoints?

## Safety and research scope

ArbLens is an educational and research project. It does not provide financial advice, does not guarantee an arbitrage opportunity, and does not place live orders in Version 0.1.

## Next milestone

Connect a real option-chain provider, collect timestamped snapshots, and compare raw midpoint anomalies with bid/ask-aware violations over time. See [`docs/ROADMAP.md`](docs/ROADMAP.md).
