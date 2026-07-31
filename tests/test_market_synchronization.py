from datetime import UTC, datetime

import pandas as pd

from arblens.market import (
    ChainTimestampSummary,
    UnderlyingQuote,
    summarize_chain_timestamps,
    validate_market_synchronization,
)


def test_synchronized_quotes_pass() -> None:
    frame = pd.DataFrame(
        {
            "quote_timestamp": [
                "2026-07-30T20:00:00Z",
                "2026-07-30T20:00:20Z",
                "2026-07-30T20:00:40Z",
            ]
        }
    )

    summary = summarize_chain_timestamps(frame)

    quote = UnderlyingQuote(
        symbol="AAPL",
        bid=313.0,
        ask=313.1,
        last=313.05,
        bid_timestamp=datetime(
            2026,
            7,
            30,
            20,
            1,
            tzinfo=UTC,
        ),
        ask_timestamp=datetime(
            2026,
            7,
            30,
            20,
            1,
            tzinfo=UTC,
        ),
        trade_timestamp=datetime(
            2026,
            7,
            30,
            20,
            1,
            tzinfo=UTC,
        ),
    )

    result = validate_market_synchronization(
        quote,
        summary,
    )

    assert result.synchronized is True


def test_after_hours_stock_and_regular_options_fail() -> None:
    summary = ChainTimestampSummary(
        usable=True,
        representative_timestamp=datetime(
            2026,
            7,
            30,
            20,
            0,
            tzinfo=UTC,
        ),
        newest_timestamp=datetime(
            2026,
            7,
            30,
            20,
            0,
            tzinfo=UTC,
        ),
        oldest_timestamp=datetime(
            2026,
            7,
            30,
            20,
            0,
            tzinfo=UTC,
        ),
        valid_count=100,
        missing_count=0,
        reason=("option quote timestamps are internally consistent"),
    )

    quote = UnderlyingQuote(
        symbol="AAPL",
        bid=313.0,
        ask=313.1,
        last=333.43,
        bid_timestamp=datetime(
            2026,
            7,
            30,
            23,
            38,
            tzinfo=UTC,
        ),
        ask_timestamp=datetime(
            2026,
            7,
            30,
            23,
            38,
            tzinfo=UTC,
        ),
        trade_timestamp=datetime(
            2026,
            7,
            30,
            20,
            0,
            tzinfo=UTC,
        ),
    )

    result = validate_market_synchronization(
        quote,
        summary,
    )

    assert result.synchronized is False

    assert result.time_difference_seconds == 13080.0


def test_missing_chain_timestamps_fail_safely() -> None:
    frame = pd.DataFrame(
        {
            "quote_timestamp": [
                None,
                None,
            ]
        }
    )

    summary = summarize_chain_timestamps(frame)

    assert summary.usable is False

    assert "no valid" in summary.reason
