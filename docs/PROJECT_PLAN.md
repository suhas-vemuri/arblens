# ArbLens regular-platform project plan

## Product goal

Build a reliable analytical platform that explains whether an apparent options-price inconsistency is caused by midpoint arithmetic, structurally bad data, or a violation that remains visible at quoted bid/ask prices.

## Version 0.1 — Local mathematical prototype

**Delivered in this starter repository**

- Sample option chain
- Quote validation and cleaning
- Black–Scholes pricing
- Implied-volatility solver
- Price-bound checks
- Monotonicity checks
- Butterfly checks
- Put–call parity checks
- Midpoint versus bid/ask labels
- Streamlit dashboard
- Tests and continuous integration

## Version 0.2 — Real-data snapshot collector

- Select one provider and one product
- Add authenticated option-chain download
- Save immutable raw snapshots
- Add metadata: collection time, provider, underlying price, rate input
- Preserve secrets only in `.env`
- Add retry and rate-limit handling

**Definition of done:** at least one trading session of timestamped snapshots can be collected without manual file editing.

## Version 0.3 — Research dataset

- Add repeated scheduled collection
- Store Parquet partitions by date, symbol, and expiration
- Add quote-age and synchronization checks
- Create a daily summary table
- Compare raw, clean, midpoint, and bid/ask-surviving counts

**Definition of done:** generate a reproducible report from one week of data.

## Version 0.4 — Professional dashboard

- Date and expiration filters
- Raw-versus-clean funnel
- Violation detail page
- Quote-quality indicators
- Raw and cleaned volatility views
- Downloadable research summary

## Version 0.5 — Regular platform release

- Stable data collection
- Strong cleaning
- Implied-volatility calculation
- Four core no-arbitrage checks
- Midpoint versus bid/ask comparison
- Repeated historical snapshots
- Professional dashboard
- Automated tests
- Written findings

## Full-version extensions

- Minimum-change quote repair using constrained optimization
- Raw versus repaired volatility surfaces
- Stale-quote persistence analysis
- Historical event replay
- Fee and displayed-size model
- Paper brokerage integration
- API service
- Performance benchmarking and optional C++ acceleration
