# ArbLens Phase 6 — Final Interactive Portfolio Demo

## Included
- Direct-to-dashboard Streamlit experience
- Lowercase silver `arblens` brand treatment
- Up to 10 custom ticker symbols
- Demo mode and limited live Tradier mode
- Clickable analysis timeline
- Quant-method explainers for implemented checks
- Elimination funnel and ranked results
- CSV download and deployment configuration

## Run locally
```powershell
streamlit run dashboard/app.py
```

## Deploy
Use Streamlit Community Cloud, select `dashboard/app.py`, and add `TRADIER_TOKEN` plus `TRADIER_BASE_URL` as private app secrets. Never commit the real secrets file.

## Safety
Educational research demo only. No order placement, fill guarantees, or investment advice.
