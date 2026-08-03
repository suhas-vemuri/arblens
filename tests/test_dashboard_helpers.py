import pandas as pd
import pytest

from dashboard.helpers import (
    build_elimination_frame,
    calculate_metrics,
    parse_symbols,
    readable_check_name,
)


def test_parse_symbols():
    assert parse_symbols("aapl, MSFT aapl\nSPY") == ["AAPL", "MSFT", "SPY"]


def test_too_many():
    with pytest.raises(ValueError, match="no more than"):
        parse_symbols(",".join(f"T{i}" for i in range(11)))


def test_metrics():
    frame = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "raw_rows": 100,
                "clean_rows": 90,
                "liquid_rows": 40,
                "violations": 5,
                "executable_violations": 1,
                "opportunities_after_costs": 1,
                "synchronization_passed": True,
            }
        ]
    )
    m = calculate_metrics(frame)
    assert m.raw_contracts == 100
    assert m.liquid_contracts == 40
    assert m.violations_found == 5


def test_funnel():
    frame = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "raw_rows": 100,
                "clean_rows": 90,
                "liquid_rows": 40,
                "violations": 5,
                "executable_violations": 1,
                "opportunities_after_costs": 0,
                "synchronization_passed": True,
                "spot_checks_skipped": False,
            }
        ]
    )
    result = build_elimination_frame(frame)
    assert result.iloc[0].remaining == 100
    assert result.iloc[-1].remaining == 0


def test_name():
    assert readable_check_name("put_call_parity") == "Put-call parity"
