from __future__ import annotations

import os
from typing import Any

import httpx
import pandas as pd
from dotenv import load_dotenv

from arblens.providers.base import OptionChainProvider

CHAIN_COLUMNS = [
    "symbol",
    "contract_symbol",
    "expiration",
    "option_type",
    "strike",
    "bid",
    "ask",
    "bid_size",
    "ask_size",
    "last",
    "volume",
    "open_interest",
    "quote_timestamp",
]


class TradierAPIError(RuntimeError):
    """Raised when Tradier returns an unusable response."""


class TradierProvider(OptionChainProvider):
    """Retrieve and normalize Tradier option-market data."""

    def __init__(
        self,
        token: str | None = None,
        base_url: str | None = None,
        *,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        load_dotenv()

        configured_token = token or os.getenv("TRADIER_ACCESS_TOKEN")
        configured_base_url = (
            base_url or os.getenv("TRADIER_BASE_URL") or "https://sandbox.tradier.com/v1"
        )

        if configured_token is None or not configured_token.strip():
            raise ValueError("TRADIER_ACCESS_TOKEN is not configured")

        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")

        self.token = configured_token.strip()
        self.base_url = configured_base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport

    @property
    def environment(self) -> str:
        """Identify whether this provider uses sandbox or production."""
        host = httpx.URL(self.base_url).host

        if host == "sandbox.tradier.com":
            return "sandbox"

        if host == "api.tradier.com":
            return "production"

        return "custom"

    def _request_json(
        self,
        path: str,
        params: dict[str, str],
    ) -> dict[str, Any]:
        """Send one authenticated GET request and return its JSON object."""
        url = f"{self.base_url}{path}"

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }

        try:
            with httpx.Client(
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                response = client.get(
                    url,
                    headers=headers,
                    params=params,
                )
        except httpx.RequestError as exc:
            raise TradierAPIError(f"Could not connect to Tradier: {exc}") from exc

        if response.is_error:
            detail = response.text.strip() or "no response body"

            raise TradierAPIError(
                f"Tradier request failed with status {response.status_code}: {detail}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise TradierAPIError("Tradier returned invalid JSON") from exc

        if not isinstance(payload, dict):
            raise TradierAPIError("Tradier returned JSON in an unexpected format")

        return payload

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        normalized_symbol = symbol.strip().upper()

        if not normalized_symbol:
            raise ValueError("symbol must not be empty")

        return normalized_symbol

    def get_expirations(self, symbol: str) -> list[str]:
        """Return available option-expiration dates for a symbol."""
        normalized_symbol = self._normalize_symbol(symbol)

        payload = self._request_json(
            "/markets/options/expirations",
            {
                "symbol": normalized_symbol,
            },
        )

        expiration_container = payload.get("expirations")

        if not isinstance(expiration_container, dict):
            return []

        expiration_dates = expiration_container.get("date", [])

        if isinstance(expiration_dates, str):
            expiration_dates = [expiration_dates]

        if not isinstance(expiration_dates, list):
            raise TradierAPIError("Tradier returned expirations in an unexpected format")

        return [str(expiration) for expiration in expiration_dates if expiration]

    def get_chain(
        self,
        symbol: str,
        expiration: str,
    ) -> pd.DataFrame:
        """Return one normalized option chain as a DataFrame."""
        normalized_symbol = self._normalize_symbol(symbol)
        normalized_expiration = expiration.strip()

        if not normalized_expiration:
            raise ValueError("expiration must not be empty")

        payload = self._request_json(
            "/markets/options/chains",
            {
                "symbol": normalized_symbol,
                "expiration": normalized_expiration,
                "greeks": "true",
            },
        )

        option_container = payload.get("options")

        if not isinstance(option_container, dict):
            return pd.DataFrame(columns=CHAIN_COLUMNS)

        options = option_container.get("option", [])

        if isinstance(options, dict):
            options = [options]

        if not isinstance(options, list):
            raise TradierAPIError("Tradier returned options in an unexpected format")

        rows: list[dict[str, object]] = []

        for option in options:
            if not isinstance(option, dict):
                continue

            rows.append(
                {
                    "symbol": normalized_symbol,
                    "contract_symbol": option.get("symbol"),
                    "expiration": (option.get("expiration_date") or normalized_expiration),
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

        return pd.DataFrame(rows, columns=CHAIN_COLUMNS)
