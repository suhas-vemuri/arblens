from datetime import UTC, datetime

import httpx
import pytest

from arblens.providers.tradier import (
    TradierAPIError,
    TradierProvider,
)


def build_provider(
    handler,
) -> TradierProvider:
    return TradierProvider(
        token="test-token",
        base_url="https://example.test/v1",
        transport=httpx.MockTransport(handler),
    )


def test_get_underlying_quote_normalizes_values() -> None:
    timestamp_ms = 1785441600000

    def handle_request(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1/markets/quotes"
        assert request.url.params["symbols"] == "AAPL"
        assert request.url.params["greeks"] == "false"
        assert request.headers["Authorization"] == ("Bearer test-token")

        return httpx.Response(
            200,
            json={
                "quotes": {
                    "quote": {
                        "symbol": "AAPL",
                        "bid": 333.40,
                        "ask": 333.44,
                        "last": 333.42,
                        "bid_date": timestamp_ms,
                        "ask_date": timestamp_ms,
                        "trade_date": timestamp_ms,
                    }
                }
            },
        )

    provider = build_provider(handle_request)

    quote = provider.get_underlying_quote(" aapl ")

    expected_timestamp = datetime.fromtimestamp(
        timestamp_ms / 1000,
        tz=UTC,
    )

    assert quote.symbol == "AAPL"
    assert quote.bid == pytest.approx(333.40)
    assert quote.ask == pytest.approx(333.44)
    assert quote.last == pytest.approx(333.42)
    assert quote.bid_timestamp == expected_timestamp
    assert quote.ask_timestamp == expected_timestamp
    assert quote.trade_timestamp == expected_timestamp


def test_get_underlying_quote_selects_matching_symbol() -> None:
    def handle_request(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "quotes": {
                    "quote": [
                        {
                            "symbol": "MSFT",
                            "bid": 500.00,
                            "ask": 500.10,
                            "last": 500.05,
                        },
                        {
                            "symbol": "AAPL",
                            "bid": 333.40,
                            "ask": 333.44,
                            "last": 333.42,
                        },
                    ]
                }
            },
        )

    provider = build_provider(handle_request)

    quote = provider.get_underlying_quote("AAPL")

    assert quote.symbol == "AAPL"
    assert quote.bid == pytest.approx(333.40)


def test_get_underlying_quote_parses_iso_timestamp() -> None:
    def handle_request(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "quotes": {
                    "quote": {
                        "symbol": "AAPL",
                        "bid": 333.40,
                        "ask": 333.44,
                        "last": 333.42,
                        "bid_date": "2026-07-30T20:00:00Z",
                        "ask_date": "2026-07-30T20:00:00Z",
                        "trade_date": "2026-07-30T20:00:00Z",
                    }
                }
            },
        )

    provider = build_provider(handle_request)

    quote = provider.get_underlying_quote("AAPL")

    assert quote.trade_timestamp == datetime(
        2026,
        7,
        30,
        20,
        0,
        tzinfo=UTC,
    )


def test_missing_quote_container_raises() -> None:
    def handle_request(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "quotes": None,
            },
        )

    provider = build_provider(handle_request)

    with pytest.raises(
        TradierAPIError,
        match="did not return an underlying quote",
    ):
        provider.get_underlying_quote("AAPL")


def test_missing_requested_symbol_raises() -> None:
    def handle_request(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "quotes": {
                    "quote": {
                        "symbol": "MSFT",
                        "bid": 500.00,
                        "ask": 500.10,
                        "last": 500.05,
                    }
                }
            },
        )

    provider = build_provider(handle_request)

    with pytest.raises(
        TradierAPIError,
        match="did not return a quote for AAPL",
    ):
        provider.get_underlying_quote("AAPL")
