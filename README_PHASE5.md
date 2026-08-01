# ArbLens Phase 5

Phase 5 adds watchlist scanning, combined reports, liquidity filters, repeated timestamped scans, and ranked opportunity reports.

## Watchlist scan

```powershell
python -m arblens.watchlist_cli data\watchlists\starter.txt --maximum-expirations 2 --minimum-volume 1 --minimum-open-interest 1 --maximum-relative-spread 0.25 --allow-production
```

## Repeated scan

```powershell
python -m arblens.repeat_cli data\watchlists\starter.txt --runs 2 --interval-seconds 10 --maximum-expirations 1 --allow-production
```

Generated results are research outputs and do not guarantee execution or profit.
