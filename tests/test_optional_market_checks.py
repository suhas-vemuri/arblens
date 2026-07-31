import pandas as pd

from arblens.cleaning import clean_quotes
from arblens.detection import run_all_checks


def build_chain() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "symbol": "TEST",
                "expiration": "2026-08-21",
                "option_type": "call",
                "strike": 100.0,
                "bid": 5.90,
                "ask": 6.10,
            },
            {
                "symbol": "TEST",
                "expiration": "2026-08-21",
                "option_type": "call",
                "strike": 105.0,
                "bid": 6.90,
                "ask": 7.10,
            },
            {
                "symbol": "TEST",
                "expiration": "2026-08-21",
                "option_type": "call",
                "strike": 110.0,
                "bid": 1.90,
                "ask": 2.10,
            },
        ]
    )


def test_chain_only_checks_run_without_spot_or_time() -> None:
    cleaned, issues = clean_quotes(build_chain())

    assert not [issue for issue in issues if issue.severity == "error"]

    violations = run_all_checks(
        cleaned,
        spot=None,
        time=None,
        rate=0.04,
    )

    violation_types = {violation.violation_type for violation in violations}

    assert "strike_monotonicity" in violation_types
    assert "butterfly_convexity" in violation_types
    assert "price_bound" not in violation_types
    assert "put_call_parity" not in violation_types


def test_spot_dependent_checks_run_with_market_inputs() -> None:
    frame = pd.DataFrame(
        [
            {
                "symbol": "TEST",
                "expiration": "2026-08-21",
                "option_type": "call",
                "strike": 50.0,
                "bid": 0.90,
                "ask": 1.10,
            },
            {
                "symbol": "TEST",
                "expiration": "2026-08-21",
                "option_type": "call",
                "strike": 100.0,
                "bid": 5.90,
                "ask": 6.10,
            },
            {
                "symbol": "TEST",
                "expiration": "2026-08-21",
                "option_type": "call",
                "strike": 105.0,
                "bid": 6.90,
                "ask": 7.10,
            },
            {
                "symbol": "TEST",
                "expiration": "2026-08-21",
                "option_type": "call",
                "strike": 110.0,
                "bid": 1.90,
                "ask": 2.10,
            },
        ]
    )

    cleaned, _ = clean_quotes(frame)

    violations = run_all_checks(
        cleaned,
        spot=100.0,
        time=30 / 365,
        rate=0.04,
    )

    violation_types = {violation.violation_type for violation in violations}

    assert "strike_monotonicity" in violation_types
    assert "butterfly_convexity" in violation_types
    assert "price_bound" in violation_types
