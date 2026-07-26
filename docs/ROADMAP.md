# Roadmap

## Milestone 1: Understand and verify the core mathematics

- [x] Black–Scholes call and put pricing
- [x] Implied-volatility inversion
- [x] Price-bound checks
- [x] Strike monotonicity
- [x] Butterfly convexity
- [x] Put–call parity
- [x] Unit tests using synthetic examples

## Milestone 2: Add real option-chain data

- [ ] Choose the first provider
- [ ] Create a personal developer token
- [ ] Test one chain request manually
- [ ] Normalize provider response
- [ ] Save the exact raw response
- [ ] Record an underlying quote at collection time
- [ ] Add rate and dividend inputs

## Milestone 3: Collect repeated snapshots

- [ ] Define a collection interval
- [ ] Store snapshots in Parquet
- [ ] Partition data by date and expiration
- [ ] Track quote age and missing values
- [ ] Add recovery after network failures

## Milestone 4: Produce the first research report

- [ ] Count raw midpoint anomalies
- [ ] Remove invalid records
- [ ] Count cleaned midpoint anomalies
- [ ] Count bid/ask survivors
- [ ] Break results down by moneyness and liquidity
- [ ] Document limitations honestly

## Milestone 5: Improve presentation

- [ ] Add dashboard filters
- [ ] Add violation drill-down
- [ ] Add implied-volatility chart
- [ ] Add raw-versus-clean funnel
- [ ] Add screenshots to README

## Full ArbLens extensions

- [ ] Quote-repair optimizer
- [ ] Repaired volatility surface
- [ ] Stale-quote tracking
- [ ] Event replay
- [ ] Cost and size model
- [ ] Paper-trading integration
- [ ] FastAPI service
- [ ] Performance benchmarks
