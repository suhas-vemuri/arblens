from datetime import UTC, datetime

import pandas as pd
import pytest

from arblens.market import UnderlyingQuote
from arblens.scanning import (
    scan_symbol_expirations,
    select_expirations,
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
    expiration: str,
    timestamp: datetime,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "expiration": expiration,
                "option_type": "call",
                "strike": 200.0,
                "bid": 10.00,
                "ask": 10.20,
                "quote_timestamp": timestamp,
            },
            {
                "symbol": "AAPL",
                "expiration": expiration,
                "option_type": "call",
                "strike": 205.0,
                "bid": 7.00,
                "ask": 7.20,
                "quote_timestamp": timestamp,
            },
            {
                "symbol": "AAPL",
                "expiration": expiration,
                "option_type": "call",
                "strike": 210.0,
                "bid": 5.00,
                "ask": 5.20,
                "quote_timestamp": timestamp,
            },
        ]
    )


class FakeProvider:
    environment = "sandbox"

    def __init__(
        self,
        *,
        fail_expiration: (str | None) = None,
        option_timestamp: (datetime | None) = None,
    ) -> None:
        self.fail_expiration = fail_expiration

        self.option_timestamp = option_timestamp or NOW

        self.expirations = [
            "2026-08-07",
            "2026-08-14",
            "2026-08-21",
        ]

    def get_expirations(
        self,
        symbol: str,
    ) -> list[str]:
        assert symbol == "AAPL"

        return self.expirations

    def get_underlying_quote(
        self,
        symbol: str,
    ) -> UnderlyingQuote:
        return UnderlyingQuote(
            symbol=symbol,
            bid=220.00,
            ask=220.10,
            last=220.05,
            bid_timestamp=NOW,
            ask_timestamp=NOW,
            trade_timestamp=NOW,
        )

    def get_chain(
        self,
        symbol: str,
        expiration: str,
    ) -> pd.DataFrame:
        assert symbol == "AAPL"

        if expiration == self.fail_expiration:
            raise RuntimeError("temporary provider failure")

        return build_chain(
            expiration,
            self.option_timestamp,
        )


def test_selects_first_two_expirations() -> None:
    selected = select_expirations(
        [
            "2026-08-07",
            "2026-08-14",
            "2026-08-21",
        ],
        maximum_expirations=2,
    )

    assert selected == [
        "2026-08-07",
        "2026-08-14",
    ]


def test_rejects_unavailable_requested_expiration() -> None:
    with pytest.raises(
        ValueError,
        match="not available",
    ):
        select_expirations(
            [
                "2026-08-07",
                "2026-08-14",
            ],
            requested_expirations=["2026-09-18"],
        )


def test_scans_multiple_expirations() -> None:
    result = scan_symbol_expirations(
        FakeProvider(),
        "aapl",
        maximum_expirations=2,
        captured_at=NOW,
    )

    assert result.symbol == "AAPL"

    assert result.requested_expirations == (
        "2026-08-07",
        "2026-08-14",
    )

    assert result.completed_expirations == 2

    assert result.failed_expirations == 0

    assert len(result.results) == 2

    assert all(scan.synchronization_passed is True for scan in result.results)

    assert all(scan.spot_used == pytest.approx(220.05) for scan in result.results)


def test_one_expiration_failure_does_not_stop_scan() -> None:
    result = scan_symbol_expirations(
        FakeProvider(fail_expiration=("2026-08-14")),
        "AAPL",
        captured_at=NOW,
    )

    assert result.completed_expirations == 2

    assert result.failed_expirations == 1

    failed_result = next(scan for scan in result.results if scan.expiration == "2026-08-14")

    assert failed_result.error == "temporary provider failure"


def test_unsynchronized_data_skips_spot_checks() -> None:
    old_option_timestamp = datetime(
        2026,
        8,
        1,
        12,
        0,
        tzinfo=UTC,
    )

    result = scan_symbol_expirations(
        FakeProvider(option_timestamp=(old_option_timestamp)),
        "AAPL",
        maximum_expirations=1,
        captured_at=NOW,
    )

    scan = result.results[0]

    assert scan.synchronization_passed is False

    assert scan.spot_used is None

    assert scan.spot_dependent_checks_skipped is True

    assert scan.executable_violation_count == 0
