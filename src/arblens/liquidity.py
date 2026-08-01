from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True, slots=True)
class LiquidityFilter:
    minimum_volume: int = 0
    minimum_open_interest: int = 0
    maximum_relative_spread: float | None = None
    require_positive_bid: bool = True

    def validate(self) -> None:
        if self.minimum_volume < 0:
            raise ValueError("minimum_volume must be non-negative")
        if self.minimum_open_interest < 0:
            raise ValueError("minimum_open_interest must be non-negative")
        if self.maximum_relative_spread is not None and self.maximum_relative_spread < 0:
            raise ValueError("maximum_relative_spread must be non-negative")


@dataclass(frozen=True, slots=True)
class LiquiditySummary:
    input_rows: int
    output_rows: int
    removed_rows: int
    removed_for_bid: int
    removed_for_spread: int
    removed_for_volume: int
    removed_for_open_interest: int


def apply_liquidity_filters(
    frame: pd.DataFrame,
    rules: LiquidityFilter,
) -> tuple[pd.DataFrame, LiquiditySummary]:
    rules.validate()

    if frame.empty:
        return frame.copy(), LiquiditySummary(0, 0, 0, 0, 0, 0, 0)

    working = frame.copy()
    bid = pd.to_numeric(working["bid"], errors="coerce")
    ask = pd.to_numeric(working["ask"], errors="coerce")
    midpoint = (bid + ask) / 2.0
    relative_spread = (ask - bid) / midpoint.where(midpoint > 0)
    keep = pd.Series(True, index=working.index)

    bid_failure = pd.Series(False, index=working.index)
    if rules.require_positive_bid:
        bid_failure = bid.isna() | (bid <= 0)
        keep &= ~bid_failure

    spread_failure = pd.Series(False, index=working.index)
    if rules.maximum_relative_spread is not None:
        spread_failure = relative_spread.isna() | (relative_spread > rules.maximum_relative_spread)
        keep &= ~spread_failure

    volume_failure = pd.Series(False, index=working.index)
    if rules.minimum_volume > 0:
        if "volume" not in working.columns:
            volume_failure = pd.Series(True, index=working.index)
        else:
            volume = pd.to_numeric(working["volume"], errors="coerce").fillna(0)
            volume_failure = volume < rules.minimum_volume
        keep &= ~volume_failure

    open_interest_failure = pd.Series(False, index=working.index)
    if rules.minimum_open_interest > 0:
        if "open_interest" not in working.columns:
            open_interest_failure = pd.Series(True, index=working.index)
        else:
            open_interest = pd.to_numeric(working["open_interest"], errors="coerce").fillna(0)
            open_interest_failure = open_interest < rules.minimum_open_interest
        keep &= ~open_interest_failure

    filtered = working.loc[keep].reset_index(drop=True)
    summary = LiquiditySummary(
        input_rows=len(working),
        output_rows=len(filtered),
        removed_rows=int((~keep).sum()),
        removed_for_bid=int(bid_failure.sum()),
        removed_for_spread=int(spread_failure.sum()),
        removed_for_volume=int(volume_failure.sum()),
        removed_for_open_interest=int(open_interest_failure.sum()),
    )
    return filtered, summary
