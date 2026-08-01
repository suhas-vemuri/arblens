from datetime import UTC, datetime

import pandas as pd
import pytest

from arblens.market import UnderlyingQuote
from arblens.watchlist import (
    load_watchlist,
    normalize_symbols,
    scan_watchlist,
)

NOW = datetime(
    2026,
    8,
    1,
    15,
    0,
    tzinfo=UTC,
)


def build_chain(
    symbol: str,
    expiration: str,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "symbol": symbol,
                "expiration": expiration,
                "option_type": "call",
                "strike": 100.0,
                "bid": 10.00,
                "ask": 10.20,
                "quote_timestamp": NOW,
            },
            {
                "symbol": symbol,
                "expiration": expiration,
                "option_type": "call",
                "strike": 105.0,
                "bid": 7.00,
                "ask": 7.20,
                "quote_timestamp": NOW,
            },
            {
                "symbol": symbol,
                "expiration": expiration,
                "option_type": "call",
                "strike": 110.0,
                "bid": 5.00,
                "ask": 5.20,
                "quote_timestamp": NOW,
            },
        ]
    )


class FakeProvider:
    environment = "sandbox"

    def get_expirations(
        self,
        symbol: str,
    ) -> list[str]:
        if symbol == "FAIL":
            raise RuntimeError("symbol unavailable")

        return [
            "2026-08-07",
            "2026-08-14",
        ]

    def get_underlying_quote(
        self,
        symbol: str,
    ) -> UnderlyingQuote:
        return UnderlyingQuote(
            symbol=symbol,
            bid=120.00,
            ask=120.10,
            last=120.05,
            bid_timestamp=NOW,
            ask_timestamp=NOW,
            trade_timestamp=NOW,
        )

    def get_chain(
        self,
        symbol: str,
        expiration: str,
    ) -> pd.DataFrame:
        return build_chain(
            symbol,
            expiration,
        )


def test_normalizes_symbols() -> None:
    symbols = normalize_symbols(
        [
            " aapl ",
            "MSFT",
            "aapl",
            "",
            " spy ",
        ]
    )

    assert symbols == [
        "AAPL",
        "MSFT",
        "SPY",
    ]


def test_loads_watchlist_file(
    tmp_path,
) -> None:
    watchlist_path = tmp_path / "watchlist.txt"

    watchlist_path.write_text(
        "AAPL\nMSFT\naapl\n\nSPY\n",
        encoding="utf-8",
    )

    symbols = load_watchlist(watchlist_path)

    assert symbols == [
        "AAPL",
        "MSFT",
        "SPY",
    ]


def test_rejects_empty_watchlist(
    tmp_path,
) -> None:
    watchlist_path = tmp_path / "watchlist.txt"

    watchlist_path.write_text(
        "\n\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="does not contain",
    ):
        load_watchlist(watchlist_path)


def test_scans_multiple_symbols() -> None:
    result = scan_watchlist(
        FakeProvider(),
        [
            "aapl",
            "MSFT",
        ],
        maximum_expirations=1,
        captured_at=NOW,
    )

    assert result.requested_symbols == (
        "AAPL",
        "MSFT",
    )

    assert result.completed_symbols == 2
    assert result.failed_symbols == 0
    assert len(result.results) == 2

    assert all(symbol_result.scan is not None for symbol_result in result.results)

    assert all(
        symbol_result.scan.completed_expirations == 1
        for symbol_result in result.results
        if symbol_result.scan is not None
    )


def test_symbol_failure_does_not_stop_watchlist() -> None:
    result = scan_watchlist(
        FakeProvider(),
        [
            "AAPL",
            "FAIL",
            "MSFT",
        ],
        maximum_expirations=1,
        captured_at=NOW,
    )

    assert result.completed_symbols == 2
    assert result.failed_symbols == 1

    failed_result = next(
        symbol_result for symbol_result in result.results if symbol_result.symbol == "FAIL"
    )

    assert failed_result.scan is None

    assert failed_result.error == "symbol unavailable"
