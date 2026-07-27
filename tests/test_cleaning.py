from datetime import UTC, datetime

import pandas as pd
import pytest

from arblens.cleaning import clean_quotes, validate_quotes


def make_quote(**overrides: object) -> dict[str, object]:
    quote: dict[str, object] = {
        "symbol": "TEST",
        "expiration": "2026-12-18",
        "option_type": "call",
        "strike": 100,
        "bid": 5.0,
        "ask": 5.2,
    }
    quote.update(overrides)
    return quote


def test_crossed_quote_is_removed() -> None:
    frame = pd.DataFrame(
        [
            make_quote(bid=5.5, ask=5.0),
            make_quote(strike=105, bid=3.0, ask=3.2),
        ]
    )

    cleaned, issues = clean_quotes(frame)

    assert len(cleaned) == 1
    assert any(issue.code == "crossed_market" for issue in issues)


def test_missing_required_column_raises() -> None:
    frame = pd.DataFrame([{"symbol": "TEST"}])

    with pytest.raises(ValueError, match="missing required columns"):
        validate_quotes(frame)


def test_invalid_expiration_is_removed() -> None:
    frame = pd.DataFrame(
        [
            make_quote(expiration="not-a-date"),
            make_quote(strike=105),
        ]
    )

    cleaned, issues = clean_quotes(frame)

    assert len(cleaned) == 1
    assert any(issue.code == "invalid_expiration" for issue in issues)


def test_nonnumeric_quote_is_removed() -> None:
    frame = pd.DataFrame(
        [
            make_quote(bid="unknown"),
            make_quote(strike=105),
        ]
    )

    cleaned, issues = clean_quotes(frame)

    assert len(cleaned) == 1
    assert any(issue.code == "invalid_quote" for issue in issues)


def test_invalid_strike_is_removed() -> None:
    frame = pd.DataFrame(
        [
            make_quote(strike="unknown"),
            make_quote(strike=105),
        ]
    )

    cleaned, issues = clean_quotes(frame)

    assert len(cleaned) == 1
    assert any(issue.code == "invalid_strike" for issue in issues)


def test_wide_spread_creates_warning_but_keeps_quote() -> None:
    frame = pd.DataFrame([make_quote(bid=0.5, ask=4.5)])

    cleaned, issues = clean_quotes(frame)

    assert len(cleaned) == 1

    wide_spread_issue = next(issue for issue in issues if issue.code == "wide_spread")

    assert wide_spread_issue.severity == "warning"


def test_numeric_strings_are_normalized() -> None:
    frame = pd.DataFrame(
        [
            make_quote(
                symbol=" test ",
                expiration="2026/12/18",
                option_type=" CALL ",
                strike="100",
                bid="1.25",
                ask="1.50",
            )
        ]
    )

    cleaned, issues = clean_quotes(frame)

    assert not any(issue.severity == "error" for issue in issues)
    assert cleaned.loc[0, "symbol"] == "TEST"
    assert cleaned.loc[0, "option_type"] == "call"
    assert cleaned.loc[0, "strike"] == 100.0
    assert cleaned.loc[0, "bid"] == 1.25
    assert cleaned.loc[0, "ask"] == 1.50
    assert cleaned.loc[0, "expiration"] == "2026-12-18"
    assert cleaned.loc[0, "mid"] == 1.375


def test_zero_liquidity_creates_warnings_but_keeps_quote() -> None:
    frame = pd.DataFrame(
        [
            make_quote(
                volume=0,
                open_interest=0,
            )
        ]
    )

    cleaned, issues = clean_quotes(frame)

    issue_codes = {issue.code for issue in issues}

    assert len(cleaned) == 1
    assert "zero_volume" in issue_codes
    assert "zero_open_interest" in issue_codes
    assert all(issue.severity == "warning" for issue in issues)


def test_stale_timestamp_creates_warning_but_keeps_quote() -> None:
    current_time = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)

    frame = pd.DataFrame(
        [
            make_quote(
                quote_timestamp="2026-07-27T11:58:00Z",
            )
        ]
    )

    cleaned, issues = clean_quotes(
        frame,
        now=current_time,
        max_quote_age_seconds=60,
    )

    stale_issue = next(issue for issue in issues if issue.code == "stale_quote")

    assert len(cleaned) == 1
    assert stale_issue.severity == "warning"


def test_invalid_timestamp_creates_warning_but_keeps_quote() -> None:
    frame = pd.DataFrame(
        [
            make_quote(
                quote_timestamp="not-a-timestamp",
            )
        ]
    )

    cleaned, issues = clean_quotes(
        frame,
        max_quote_age_seconds=60,
    )

    timestamp_issue = next(issue for issue in issues if issue.code == "invalid_timestamp")

    assert len(cleaned) == 1
    assert timestamp_issue.severity == "warning"


def test_normalized_duplicate_contracts_are_removed() -> None:
    frame = pd.DataFrame(
        [
            make_quote(
                symbol="test",
                expiration="2026-12-18",
                option_type="call",
                strike=100,
            ),
            make_quote(
                symbol=" TEST ",
                expiration="2026/12/18",
                option_type=" CALL ",
                strike="100",
            ),
        ]
    )

    cleaned, issues = clean_quotes(frame)

    duplicate_issues = [issue for issue in issues if issue.code == "duplicate_contract"]

    assert cleaned.empty
    assert len(duplicate_issues) == 2
