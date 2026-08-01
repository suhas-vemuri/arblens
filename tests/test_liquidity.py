import pandas as pd

from arblens.liquidity import LiquidityFilter, apply_liquidity_filters


def test_filters_low_liquidity_rows() -> None:
    frame = pd.DataFrame(
        [
            {"bid": 1.00, "ask": 1.10, "volume": 10, "open_interest": 20},
            {"bid": 0.00, "ask": 1.00, "volume": 10, "open_interest": 20},
            {"bid": 1.00, "ask": 2.00, "volume": 10, "open_interest": 20},
            {"bid": 1.00, "ask": 1.10, "volume": 0, "open_interest": 20},
            {"bid": 1.00, "ask": 1.10, "volume": 10, "open_interest": 0},
        ]
    )
    filtered, summary = apply_liquidity_filters(
        frame,
        LiquidityFilter(
            minimum_volume=1,
            minimum_open_interest=1,
            maximum_relative_spread=0.25,
        ),
    )
    assert len(filtered) == 1
    assert summary.removed_rows == 4
