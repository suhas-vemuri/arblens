"""Read-only Tradier API client for ArbLens."""

from __future__ import annotations

import os
from typing import Any

import requests
from dotenv import load_dotenv


load_dotenv()


class TradierError(RuntimeError):
    """Raised when a Tradier API request fails."""


class TradierClient:
    """Connects ArbLens to Tradier market-data endpoints."""

    def __init__(self) -> None:
        self.token = os.getenv("TRADIER_TOKEN")
        self.base_url = os.getenv(
            "TRADIER_BASE_URL",
            "https://api.tradier.com/v1",
        ).rstrip("/")

        if not self.token:
            raise TradierError(
                "TRADIER_TOKEN was not found in the .env file."
            )

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
            }
        )

    def _get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send one authenticated GET request to Tradier."""

        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            response = self.session.get(
                url,
                params=params,
                timeout=20,
            )
        except requests.RequestException as exc:
            raise TradierError(
                f"Could not connect to Tradier: {exc}"
            ) from exc

        if response.status_code == 401:
            raise TradierError(
                "Tradier returned 401 Unauthorized. Check that your "
                "production token is correct and that the base URL is "
                "https://api.tradier.com/v1."
            )

        if response.status_code == 429:
            raise TradierError(
                "Tradier's request limit was reached. Wait one minute "
                "and try again."
            )

        if not response.ok:
            raise TradierError(
                f"Tradier returned HTTP {response.status_code}: "
                f"{response.text}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise TradierError(
                "Tradier returned data that was not valid JSON."
            ) from exc

        if not isinstance(data, dict):
            raise TradierError(
                "Tradier returned an unexpected response format."
            )

        return data

    @staticmethod
    def _as_list(value: Any) -> list[Any]:
        """Convert one object, many objects, or no object into a list."""

        if value is None:
            return []

        if isinstance(value, list):
            return value

        return [value]

    def test_authentication(self) -> bool:
        """Confirm that the production token is accepted."""

        data = self._get("/user/profile")
        return isinstance(data.get("profile"), dict)

    def get_quotes(
        self,
        symbols: str | list[str],
    ) -> list[dict[str, Any]]:
        """Get current quotes for one or more symbols."""

        if isinstance(symbols, list):
            symbols_text = ",".join(symbols)
        else:
            symbols_text = symbols

        symbols_text = symbols_text.strip().upper()

        if not symbols_text:
            raise ValueError("At least one symbol is required.")

        data = self._get(
            "/markets/quotes",
            params={
                "symbols": symbols_text,
                "greeks": "false",
            },
        )

        quotes = data.get("quotes", {})

        if not isinstance(quotes, dict):
            return []

        return [
            item
            for item in self._as_list(quotes.get("quote"))
            if isinstance(item, dict)
        ]

    def get_option_expirations(
        self,
        symbol: str,
    ) -> list[str]:
        """Get every available option expiration for a symbol."""

        symbol = symbol.strip().upper()

        if not symbol:
            raise ValueError("A symbol is required.")

        data = self._get(
            "/markets/options/expirations",
            params={
                "symbol": symbol,
                "includeAllRoots": "true",
                "strikes": "false",
            },
        )

        expirations = data.get("expirations", {})

        if not isinstance(expirations, dict):
            return []

        return [
            str(item)
            for item in self._as_list(expirations.get("date"))
            if item
        ]

    def get_option_chain(
        self,
        symbol: str,
        expiration: str,
        include_greeks: bool = True,
    ) -> list[dict[str, Any]]:
        """Download one complete options chain."""

        symbol = symbol.strip().upper()
        expiration = expiration.strip()

        if not symbol:
            raise ValueError("A symbol is required.")

        if not expiration:
            raise ValueError("An expiration date is required.")

        data = self._get(
            "/markets/options/chains",
            params={
                "symbol": symbol,
                "expiration": expiration,
                "greeks": str(include_greeks).lower(),
            },
        )

        options = data.get("options", {})

        if not isinstance(options, dict):
            return []

        return [
            item
            for item in self._as_list(options.get("option"))
            if isinstance(item, dict)
        ]