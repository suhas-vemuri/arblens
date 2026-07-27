from __future__ import annotations

import os

import httpx
import pandas as pd

from arblens.providers.base import OptionChainProvider


class TradierProvider(OptionChainProvider):
    """Minimal Tradier option-chain adapter.

    This connector is deliberately isolated from the analysis engine. It is not
    activated unless the user supplies a token through an environment variable.
    """

    def __init__(self, token: str | None = None, base_url: str | None = None) -> None:
        self.token = token or os.getenv("TRADIER_ACCESS_TOKEN")
        self.base_url = (
            base_url or os.getenv("TRADIER_BASE_URL") or "https://api.tradier.com/v1"
        ).rstrip("/")
        if not self.token:
            raise ValueError("TRADIER_ACCESS_TOKEN is not configured")

    def get_chain(self, symbol: str, expiration: str) -> pd.DataFrame:
        url = f"{self.base_url}/markets/options/chains"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        params = {
            "symbol": symbol.upper(),
            "expiration": expiration,
            "greeks": "true",
        }
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, headers=headers, params=params)
            response.raise_for_status()
            payload = response.json()

        options = payload.get("options", {}).get("option", [])
        if isinstance(options, dict):
            options = [options]
        if not options:
            return pd.DataFrame()

        rows = []
        for option in options:
            rows.append(
                {
                    "symbol": symbol.upper(),
                    "contract_symbol": option.get("symbol"),
                    "expiration": option.get("expiration_date") or expiration,
                    "option_type": option.get("option_type"),
                    "strike": option.get("strike"),
                    "bid": option.get("bid"),
                    "ask": option.get("ask"),
                    "bid_size": option.get("bidsize"),
                    "ask_size": option.get("asksize"),
                    "last": option.get("last"),
                    "volume": option.get("volume"),
                    "open_interest": option.get("open_interest"),
                    "quote_timestamp": option.get("trade_date"),
                }
            )
        return pd.DataFrame(rows)
