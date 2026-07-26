import pandas as pd

from arblens.cleaning import clean_quotes, validate_quotes


def test_crossed_quote_is_removed() -> None:
    frame = pd.DataFrame(
        [
            {
                "symbol": "TEST",
                "expiration": "2026-12-18",
                "option_type": "call",
                "strike": 100,
                "bid": 5.5,
                "ask": 5.0,
            },
            {
                "symbol": "TEST",
                "expiration": "2026-12-18",
                "option_type": "call",
                "strike": 105,
                "bid": 3.0,
                "ask": 3.2,
            },
        ]
    )
    cleaned, issues = clean_quotes(frame)
    assert len(cleaned) == 1
    assert any(issue.code == "crossed_market" for issue in issues)


def test_missing_required_column_raises() -> None:
    frame = pd.DataFrame([{"symbol": "TEST"}])
    try:
        validate_quotes(frame)
    except ValueError as error:
        assert "missing required columns" in str(error)
    else:
        raise AssertionError("expected ValueError")
