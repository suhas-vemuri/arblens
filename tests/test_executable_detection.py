import pandas as pd
import pytest

from arblens.cleaning import clean_quotes
from arblens.detection import (
    detect_executable_price_bound_violations,
    run_all_checks,
)
from arblens.io import load_chain


def test_executable_price_bounds_use_ask_and_bid() -> None:
    frame = pd.DataFrame(
        [
            {
                "symbol": "TEST",
                "expiration": "2026-12-18",
                "option_type": "call",
                "strike": 90.0,
                "bid": 4.80,
                "ask": 5.00,
                "mid": 4.90,
            },
            {
                "symbol": "TEST",
                "expiration": "2026-12-18",
                "option_type": "call",
                "strike": 110.0,
                "bid": 101.00,
                "ask": 101.20,
                "mid": 101.10,
            },
        ]
    )

    violations = detect_executable_price_bound_violations(
        frame,
        spot=100.0,
        time=1.0,
        rate=0.0,
    )

    assert len(violations) == 2

    assert all(violation.price_basis == "bid_ask" for violation in violations)

    assert violations[0].magnitude == pytest.approx(5.0)
    assert violations[1].magnitude == pytest.approx(1.0)


def test_sample_midpoint_violations_do_not_survive_spread() -> None:
    raw = load_chain("data/sample_chain.csv")
    cleaned, issues = clean_quotes(raw)

    violations = run_all_checks(
        cleaned,
        spot=100.0,
        time=30 / 365,
        rate=0.04,
        dividend_yield=0.0,
    )

    midpoint_violations = [
        violation for violation in violations if violation.price_basis == "midpoint"
    ]

    executable_violations = [
        violation for violation in violations if violation.price_basis == "bid_ask"
    ]

    assert not any(issue.severity == "error" for issue in issues)

    assert len(midpoint_violations) == 3
    assert executable_violations == []
