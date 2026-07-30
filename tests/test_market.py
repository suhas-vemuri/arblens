from datetime import UTC, datetime

import pytest

from arblens.market import (
    UnderlyingQuote,
    calculate_time_to_expiration,
    expiration_timestamp,
    select_underlying_spot,
)


NOW = datetime(
    2026,
    7,
    30,
    20,
    0,
    tzinfo=UTC,
)


def test_uses_valid_bid_ask_midpoint() -> None:
    quote = UnderlyingQuote(
        symbol="AAPL",
        bid=333.40,
        ask=333.44,
        last=333.42,
        bid_timestamp=NOW,
        ask_timestamp=NOW,
        trade_timestamp=NOW,
    )

    selection = select_underlying_spot(
        quote,
        now=NOW,
    )

    assert selection.usable is True
    assert selection.spot == pytest.approx(333.42)
    assert selection.source == "bid_ask_midpoint"
    assert selection.warnings == ()


def test_rejects_crossed_underlying_market() -> None:
    quote = UnderlyingQuote(
        symbol="AAPL",
        bid=333.50,
        ask=333.40,
        last=333.45,
        bid_timestamp=NOW,
        ask_timestamp=NOW,
        trade_timestamp=NOW,
    )

    selection = select_underlying_spot(
        quote,
        now=NOW,
    )

    assert selection.usable is False
    assert selection.spot is None
    assert "crossed" in selection.reason


def test_rejects_last_trade_far_from_midpoint() -> None:
    quote = UnderlyingQuote(
        symbol="AAPL",
        bid=311.00,
        ask=311.02,
        last=333.43,
        bid_timestamp=NOW,
        ask_timestamp=NOW,
        trade_timestamp=NOW,
    )

    selection = select_underlying_spot(
        quote,
        now=NOW,
    )

    assert selection.usable is False
    assert selection.spot is None
    assert "differs" in selection.reason


def test_rejects_stale_bid_ask_quote() -> None:
    stale_time = datetime(
        2026,
        7,
        30,
        19,
        50,
        tzinfo=UTC,
    )

    quote = UnderlyingQuote(
        symbol="AAPL",
        bid=333.40,
        ask=333.44,
        last=333.42,
        bid_timestamp=stale_time,
        ask_timestamp=stale_time,
        trade_timestamp=stale_time,
    )

    selection = select_underlying_spot(
        quote,
        now=NOW,
        max_quote_age_seconds=300.0,
    )

    assert selection.usable is False
    assert selection.spot is None
    assert "stale" in selection.reason


def test_uses_last_trade_when_bid_ask_is_incomplete() -> None:
    quote = UnderlyingQuote(
        symbol="AAPL",
        bid=None,
        ask=None,
        last=333.42,
        trade_timestamp=NOW,
    )

    selection = select_underlying_spot(
        quote,
        now=NOW,
    )

    assert selection.usable is True
    assert selection.spot == pytest.approx(333.42)
    assert selection.source == "last_trade"


def test_rejects_quote_without_usable_prices() -> None:
    quote = UnderlyingQuote(
        symbol="AAPL",
        bid=None,
        ask=None,
        last=None,
    )

    selection = select_underlying_spot(
        quote,
        now=NOW,
    )

    assert selection.usable is False
    assert selection.spot is None


def test_expiration_timestamp_uses_new_york_close() -> None:
    result = expiration_timestamp("2026-07-31")

    assert result == datetime(
        2026,
        7,
        31,
        20,
        0,
        tzinfo=UTC,
    )


def test_calculates_time_to_expiration() -> None:
    result = calculate_time_to_expiration(
        "2026-07-31",
        now=NOW,
    )

    assert result.seconds_remaining == pytest.approx(
        24 * 60 * 60
    )
    assert result.days_remaining == pytest.approx(1.0)
    assert result.years_remaining == pytest.approx(
        1 / 365
    )

def test_ignores_stale_last_trade_when_bid_ask_is_current() -> None:
    stale_trade_time = datetime(
        2026,
        7,
        30,
        16,
        0,
        tzinfo=UTC,
    )

    quote = UnderlyingQuote(
        symbol="AAPL",
        bid=313.89,
        ask=314.00,
        last=333.43,
        bid_timestamp=NOW,
        ask_timestamp=NOW,
        trade_timestamp=stale_trade_time,
    )

    selection = select_underlying_spot(
        quote,
        now=NOW,
        max_trade_age_seconds=300.0,
    )

    assert selection.usable is True
    assert selection.spot == pytest.approx(313.945)
    assert selection.source == "bid_ask_midpoint"
    assert len(selection.warnings) == 1
    assert "ignored" in selection.warnings[0]
def test_rejects_expired_date() -> None:
    with pytest.raises(
        ValueError,
        match="already passed",
    ):
        calculate_time_to_expiration(
            "2026-07-29",
            now=NOW,
        )