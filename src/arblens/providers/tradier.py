from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import httpx
import pandas as pd
from dotenv import load_dotenv

from arblens.market import UnderlyingQuote
from arblens.providers.base import (
    OptionChainProvider,
)

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
    "implied_volatility",
    "delta",
    "gamma",
    "theta",
    "vega",
    "rho",
]


class TradierAPIError(RuntimeError):
    """Raised when Tradier returns unusable data."""


class TradierProvider(OptionChainProvider):
    """Retrieve and normalize Tradier market data."""

    def __init__(
        self,
        token: str | None = None,
        base_url: str | None = None,
        *,
        timeout: float = 30.0,
        transport: (httpx.BaseTransport | None) = None,
    ) -> None:
        load_dotenv()

        configured_token = token or os.getenv("TRADIER_TOKEN") or os.getenv("TRADIER_ACCESS_TOKEN")

        configured_base_url = (
            base_url or os.getenv("TRADIER_BASE_URL") or ("https://sandbox.tradier.com/v1")
        )

        if configured_token is None or not configured_token.strip():
            raise ValueError(
                "Tradier token is not configured. Add TRADIER_TOKEN to your .env file."
            )

        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")

        self.token = configured_token.strip()

        self.base_url = configured_base_url.rstrip("/")

        self.timeout = timeout
        self.transport = transport

    @property
    def environment(self) -> str:
        """Identify the Tradier environment."""

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
        """Send one authenticated GET request."""

        url = f"{self.base_url}{path}"

        headers = {
            "Authorization": (f"Bearer {self.token}"),
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

        if response.status_code == 401:
            raise TradierAPIError(
                "Tradier authentication failed with status 401. Check the API token and endpoint."
            )

        if response.status_code == 429:
            raise TradierAPIError("Tradier rate limit reached with status 429.")

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
    def _normalize_symbol(
        symbol: str,
    ) -> str:
        """Standardize a stock symbol."""

        normalized_symbol = symbol.strip().upper()

        if not normalized_symbol:
            raise ValueError("symbol must not be empty")

        return normalized_symbol

    @staticmethod
    def _parse_timestamp(
        value: object,
    ) -> datetime | None:
        """Convert a Tradier timestamp into UTC."""

        if value is None:
            return None

        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=UTC)

            return value.astimezone(UTC)

        if isinstance(value, str):
            stripped_value = value.strip()

            if not stripped_value:
                return None

            try:
                numeric_value = float(stripped_value)

            except ValueError:
                numeric_value = None

            if numeric_value is not None:
                return TradierProvider._parse_timestamp(numeric_value)

            parsed_value = pd.to_datetime(
                stripped_value,
                utc=True,
                errors="coerce",
            )

            if pd.isna(parsed_value):
                return None

            return parsed_value.to_pydatetime()

        if isinstance(
            value,
            (int, float),
        ):
            numeric_value = float(value)

            if abs(numeric_value) > 10_000_000_000:
                numeric_value /= 1000.0

            try:
                return datetime.fromtimestamp(
                    numeric_value,
                    tz=UTC,
                )

            except (
                OverflowError,
                OSError,
                ValueError,
            ):
                return None

        return None

    @staticmethod
    def _extract_greek(
        greeks: dict[str, Any],
        name: str,
    ) -> Any:
        """Read one Greek safely."""

        value = greeks.get(name)

        if value is None and name == "implied_volatility":
            value = greeks.get("mid_iv")

        return value

    def get_underlying_quote(
        self,
        symbol: str,
    ) -> UnderlyingQuote:
        """Return one stock or ETF quote."""

        normalized_symbol = self._normalize_symbol(symbol)

        payload = self._request_json(
            "/markets/quotes",
            {
                "symbols": normalized_symbol,
                "greeks": "false",
            },
        )

        quotes_container = payload.get("quotes")

        if not isinstance(
            quotes_container,
            dict,
        ):
            raise TradierAPIError("Tradier did not return an underlying quote")

        raw_quotes = quotes_container.get("quote")

        if isinstance(raw_quotes, dict):
            quote_items = [raw_quotes]

        elif isinstance(raw_quotes, list):
            quote_items = raw_quotes

        else:
            raise TradierAPIError("Tradier returned quotes in an unexpected format")

        selected_quote: dict[str, Any] | None = None

        for quote_item in quote_items:
            if not isinstance(
                quote_item,
                dict,
            ):
                continue

            returned_symbol = (
                str(
                    quote_item.get(
                        "symbol",
                        "",
                    )
                )
                .strip()
                .upper()
            )

            if returned_symbol == normalized_symbol:
                selected_quote = quote_item
                break

        if selected_quote is None:
            raise TradierAPIError(f"Tradier did not return a quote for {normalized_symbol}")

        return UnderlyingQuote(
            symbol=normalized_symbol,
            bid=selected_quote.get("bid"),
            ask=selected_quote.get("ask"),
            last=selected_quote.get("last"),
            bid_timestamp=(self._parse_timestamp(selected_quote.get("bid_date"))),
            ask_timestamp=(self._parse_timestamp(selected_quote.get("ask_date"))),
            trade_timestamp=(self._parse_timestamp(selected_quote.get("trade_date"))),
        )

    def get_expirations(
        self,
        symbol: str,
    ) -> list[str]:
        """Return available option expirations."""

        normalized_symbol = self._normalize_symbol(symbol)

        payload = self._request_json(
            "/markets/options/expirations",
            {
                "symbol": normalized_symbol,
                "includeAllRoots": "true",
                "strikes": "false",
            },
        )

        expiration_container = payload.get("expirations")

        if not isinstance(
            expiration_container,
            dict,
        ):
            return []

        expiration_dates = expiration_container.get(
            "date",
            [],
        )

        if isinstance(
            expiration_dates,
            str,
        ):
            expiration_dates = [expiration_dates]

        if not isinstance(
            expiration_dates,
            list,
        ):
            raise TradierAPIError("Tradier returned expirations in an unexpected format")

        return [str(expiration) for expiration in expiration_dates if expiration]

    def get_chain(
        self,
        symbol: str,
        expiration: str,
    ) -> pd.DataFrame:
        """Return one normalized option chain."""

        normalized_symbol = self._normalize_symbol(symbol)

        normalized_expiration = expiration.strip()

        if not normalized_expiration:
            raise ValueError("expiration must not be empty")

        payload = self._request_json(
            "/markets/options/chains",
            {
                "symbol": normalized_symbol,
                "expiration": (normalized_expiration),
                "greeks": "true",
            },
        )

        option_container = payload.get("options")

        if not isinstance(
            option_container,
            dict,
        ):
            return pd.DataFrame(columns=CHAIN_COLUMNS)

        options = option_container.get(
            "option",
            [],
        )

        if isinstance(options, dict):
            options = [options]

        if not isinstance(options, list):
            raise TradierAPIError("Tradier returned options in an unexpected format")

        rows: list[dict[str, object]] = []

        for option in options:
            if not isinstance(
                option,
                dict,
            ):
                continue

            raw_greeks = option.get("greeks")

            if isinstance(
                raw_greeks,
                dict,
            ):
                greeks = raw_greeks

            else:
                greeks = {}

            timestamp_candidates = [
                self._parse_timestamp(option.get("ask_date")),
                self._parse_timestamp(option.get("bid_date")),
                self._parse_timestamp(option.get("trade_date")),
            ]

            valid_timestamps = [
                timestamp for timestamp in timestamp_candidates if timestamp is not None
            ]

            quote_timestamp = max(valid_timestamps) if valid_timestamps else None

            rows.append(
                {
                    "symbol": (normalized_symbol),
                    "contract_symbol": (option.get("symbol")),
                    "expiration": (option.get("expiration_date") or normalized_expiration),
                    "option_type": (option.get("option_type")),
                    "strike": option.get("strike"),
                    "bid": option.get("bid"),
                    "ask": option.get("ask"),
                    "bid_size": option.get("bidsize"),
                    "ask_size": option.get("asksize"),
                    "last": option.get("last"),
                    "volume": option.get("volume"),
                    "open_interest": (option.get("open_interest")),
                    "quote_timestamp": (quote_timestamp),
                    "implied_volatility": (
                        self._extract_greek(
                            greeks,
                            "implied_volatility",
                        )
                    ),
                    "delta": (
                        self._extract_greek(
                            greeks,
                            "delta",
                        )
                    ),
                    "gamma": (
                        self._extract_greek(
                            greeks,
                            "gamma",
                        )
                    ),
                    "theta": (
                        self._extract_greek(
                            greeks,
                            "theta",
                        )
                    ),
                    "vega": (
                        self._extract_greek(
                            greeks,
                            "vega",
                        )
                    ),
                    "rho": (
                        self._extract_greek(
                            greeks,
                            "rho",
                        )
                    ),
                }
            )

        return pd.DataFrame(
            rows,
            columns=CHAIN_COLUMNS,
        )
