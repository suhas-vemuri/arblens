import pandas as pd

from arblens.cleaning import add_midpoint
from arblens.detection import (
    detect_butterfly_violations,
    detect_executable_monotonicity_violations,
    detect_monotonicity_violations,
)


def test_call_midpoint_monotonicity_violation() -> None:
    frame = add_midpoint(
        pd.DataFrame(
            [
                {"symbol": "T", "expiration": "2026-12-18", "option_type": "call", "strike": 100, "bid": 6.9, "ask": 7.1},
                {"symbol": "T", "expiration": "2026-12-18", "option_type": "call", "strike": 105, "bid": 7.9, "ask": 8.1},
            ]
        )
    )
    violations = detect_monotonicity_violations(frame)
    assert len(violations) == 1
    assert violations[0].magnitude == 1.0


def test_executable_call_monotonicity_violation() -> None:
    frame = add_midpoint(
        pd.DataFrame(
            [
                {"symbol": "T", "expiration": "2026-12-18", "option_type": "call", "strike": 100, "bid": 6.9, "ask": 7.0},
                {"symbol": "T", "expiration": "2026-12-18", "option_type": "call", "strike": 105, "bid": 8.0, "ask": 8.1},
            ]
        )
    )
    violations = detect_executable_monotonicity_violations(frame)
    assert len(violations) == 1
    assert violations[0].magnitude == 1.0


def test_butterfly_violation() -> None:
    frame = add_midpoint(
        pd.DataFrame(
            [
                {"symbol": "T", "expiration": "2026-12-18", "option_type": "call", "strike": 100, "bid": 7.9, "ask": 8.1},
                {"symbol": "T", "expiration": "2026-12-18", "option_type": "call", "strike": 105, "bid": 7.4, "ask": 7.6},
                {"symbol": "T", "expiration": "2026-12-18", "option_type": "call", "strike": 110, "bid": 1.9, "ask": 2.1},
            ]
        )
    )
    violations = detect_butterfly_violations(frame)
    assert len(violations) == 1
    assert violations[0].magnitude == 5.0
