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
