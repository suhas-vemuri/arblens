from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from math import isfinite
from zoneinfo import ZoneInfo

import pandas as pd

NEW_YORK = ZoneInfo("America/New_York")
SECONDS_PER_YEAR = 365.0 * 24.0 * 60.0 * 60.0


@dataclass(frozen=True, slots=True)
class UnderlyingQuote:
    """One stock or ETF quote used as the underlying price."""

    symbol: str
    bid: float | None
    ask: float | None
    last: float | None
    bid_timestamp: datetime | None = None
    ask_timestamp: datetime | None = None
    trade_timestamp: datetime | None = None


@dataclass(frozen=True, slots=True)
class SpotSelection:
    """Result of deciding whether an underlying price is safe."""

    usable: bool
    spot: float | None
    source: str
    reason: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExpirationCalculation:
    """Calculated time remaining before an option expires."""

    expiration_timestamp: datetime
    seconds_remaining: float
    days_remaining: float
    years_remaining: float


@dataclass(frozen=True, slots=True)
class ChainTimestampSummary:
    """Summary of timestamps found throughout an option chain."""

    usable: bool
    representative_timestamp: datetime | None
    newest_timestamp: datetime | None
    oldest_timestamp: datetime | None
    valid_count: int
    missing_count: int
    reason: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MarketSynchronization:
    """Result of comparing stock and option quote times."""

    synchronized: bool
    time_difference_seconds: float | None
    underlying_timestamp: datetime | None
    chain_timestamp: datetime | None
    reason: str
    warnings: tuple[str, ...] = ()


def _positive_finite(
    value: object,
) -> float | None:
    """Return a valid positive number or None."""

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not isfinite(number) or number <= 0:
        return None

    return number


def _as_utc(
    value: datetime | None,
) -> datetime | None:
    """Convert a datetime to timezone-aware UTC."""

    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)

    return value.astimezone(UTC)


def _age_seconds(
    timestamp: datetime | None,
    *,
    now: datetime,
) -> float | None:
    """Measure how old a timestamp is in seconds."""

    normalized_timestamp = _as_utc(timestamp)

    if normalized_timestamp is None:
        return None

    return (now - normalized_timestamp).total_seconds()


def select_underlying_spot(
    quote: UnderlyingQuote,
    *,
    now: datetime | None = None,
    max_quote_age_seconds: float = 300.0,
    max_trade_age_seconds: float = 300.0,
    max_relative_spread: float = 0.02,
    max_last_midpoint_difference: float = 0.03,
) -> SpotSelection:
    """Choose a safe underlying price from a market quote."""

    current_time = _as_utc(now) or datetime.now(UTC)

    bid = _positive_finite(quote.bid)
    ask = _positive_finite(quote.ask)
    last = _positive_finite(quote.last)

    warnings: list[str] = []

    if bid is not None and ask is not None:
        if bid > ask:
            return SpotSelection(
                usable=False,
                spot=None,
                source="none",
                reason=("underlying market is crossed because the bid is above the ask"),
            )

        midpoint = (bid + ask) / 2.0

        relative_spread = (ask - bid) / midpoint

        if relative_spread > max_relative_spread:
            return SpotSelection(
                usable=False,
                spot=None,
                source="none",
                reason=(
                    f"underlying relative spread is "
                    f"{relative_spread:.2%}, above the "
                    f"{max_relative_spread:.2%} limit"
                ),
            )

        bid_age = _age_seconds(
            quote.bid_timestamp,
            now=current_time,
        )

        ask_age = _age_seconds(
            quote.ask_timestamp,
            now=current_time,
        )

        if bid_age is None or ask_age is None:
            return SpotSelection(
                usable=False,
                spot=None,
                source="none",
                reason=("underlying bid or ask timestamp is unavailable"),
            )

        if bid_age > max_quote_age_seconds or ask_age > max_quote_age_seconds:
            return SpotSelection(
                usable=False,
                spot=None,
                source="none",
                reason="underlying bid or ask is stale",
            )

        if bid_age < -5 or ask_age < -5:
            return SpotSelection(
                usable=False,
                spot=None,
                source="none",
                reason=("underlying quote timestamp is in the future"),
            )

        if last is not None:
            trade_age = _age_seconds(
                quote.trade_timestamp,
                now=current_time,
            )

            if trade_age is not None and trade_age > max_trade_age_seconds:
                warnings.append(
                    f"last trade is {trade_age:.1f} seconds old; "
                    "it was ignored and the bid-ask midpoint "
                    "was used"
                )

            else:
                if trade_age is None:
                    warnings.append("last-trade timestamp was unavailable")

                last_difference = abs(last - midpoint) / midpoint

                if last_difference > max_last_midpoint_difference:
                    return SpotSelection(
                        usable=False,
                        spot=None,
                        source="none",
                        reason=(
                            "current last trade differs from "
                            "the bid-ask midpoint by "
                            f"{last_difference:.2%}, above the "
                            f"{max_last_midpoint_difference:.2%} "
                            "limit"
                        ),
                        warnings=tuple(warnings),
                    )

        return SpotSelection(
            usable=True,
            spot=midpoint,
            source="bid_ask_midpoint",
            reason=("current bid and ask formed a valid market midpoint"),
            warnings=tuple(warnings),
        )

    if last is None:
        return SpotSelection(
            usable=False,
            spot=None,
            source="none",
            reason=("no usable underlying bid-ask market or last trade was available"),
        )

    trade_age = _age_seconds(
        quote.trade_timestamp,
        now=current_time,
    )

    if trade_age is None:
        return SpotSelection(
            usable=False,
            spot=None,
            source="none",
            reason="last-trade timestamp is unavailable",
        )

    if trade_age > max_trade_age_seconds:
        return SpotSelection(
            usable=False,
            spot=None,
            source="none",
            reason="last trade is stale",
        )

    if trade_age < -5:
        return SpotSelection(
            usable=False,
            spot=None,
            source="none",
            reason="last-trade timestamp is in the future",
        )

    warnings.append("bid-ask market was unavailable; current last trade was used")

    return SpotSelection(
        usable=True,
        spot=last,
        source="last_trade",
        reason="a current last trade was available",
        warnings=tuple(warnings),
    )


def expiration_timestamp(
    expiration: str | date,
) -> datetime:
    """Return the option expiration at 4 PM New York time."""

    if isinstance(expiration, date):
        expiration_date = expiration

    else:
        expiration_date = date.fromisoformat(expiration.strip())

    local_close = datetime.combine(
        expiration_date,
        time(16, 0),
        tzinfo=NEW_YORK,
    )

    return local_close.astimezone(UTC)


def calculate_time_to_expiration(
    expiration: str | date,
    *,
    now: datetime | None = None,
) -> ExpirationCalculation:
    """Calculate time remaining before expiration."""

    current_time = _as_utc(now) or datetime.now(UTC)

    expiration_time = expiration_timestamp(expiration)

    seconds_remaining = (expiration_time - current_time).total_seconds()

    if seconds_remaining <= 0:
        raise ValueError("expiration has already passed")

    return ExpirationCalculation(
        expiration_timestamp=expiration_time,
        seconds_remaining=seconds_remaining,
        days_remaining=(seconds_remaining / 86400.0),
        years_remaining=(seconds_remaining / SECONDS_PER_YEAR),
    )


def summarize_chain_timestamps(
    frame: pd.DataFrame,
    *,
    column: str = "quote_timestamp",
    maximum_missing_fraction: float = 0.25,
    maximum_internal_span_seconds: float = 900.0,
) -> ChainTimestampSummary:
    """Validate the timestamps across an option chain."""

    if frame.empty:
        return ChainTimestampSummary(
            usable=False,
            representative_timestamp=None,
            newest_timestamp=None,
            oldest_timestamp=None,
            valid_count=0,
            missing_count=0,
            reason="option chain is empty",
        )

    if column not in frame.columns:
        return ChainTimestampSummary(
            usable=False,
            representative_timestamp=None,
            newest_timestamp=None,
            oldest_timestamp=None,
            valid_count=0,
            missing_count=len(frame),
            reason=(f"option chain does not contain {column}"),
        )

    parsed_timestamps = pd.to_datetime(
        frame[column],
        utc=True,
        errors="coerce",
    )

    valid_timestamps = parsed_timestamps.dropna()

    missing_count = int(parsed_timestamps.isna().sum())

    if valid_timestamps.empty:
        return ChainTimestampSummary(
            usable=False,
            representative_timestamp=None,
            newest_timestamp=None,
            oldest_timestamp=None,
            valid_count=0,
            missing_count=missing_count,
            reason=("option chain contains no valid quote timestamps"),
        )

    missing_fraction = missing_count / len(frame)

    oldest_timestamp = valid_timestamps.min().to_pydatetime()

    newest_timestamp = valid_timestamps.max().to_pydatetime()

    sorted_timestamps = valid_timestamps.sort_values()

    middle_index = len(sorted_timestamps) // 2

    representative_timestamp = sorted_timestamps.iloc[middle_index].to_pydatetime()

    internal_span_seconds = (newest_timestamp - oldest_timestamp).total_seconds()

    warnings: list[str] = []

    if missing_count:
        warnings.append(f"{missing_count} of {len(frame)} option rows have missing timestamps")

    if missing_fraction > maximum_missing_fraction:
        return ChainTimestampSummary(
            usable=False,
            representative_timestamp=(representative_timestamp),
            newest_timestamp=newest_timestamp,
            oldest_timestamp=oldest_timestamp,
            valid_count=len(valid_timestamps),
            missing_count=missing_count,
            reason=(
                f"{missing_fraction:.1%} of option "
                "timestamps are missing, above the "
                f"{maximum_missing_fraction:.1%} limit"
            ),
            warnings=tuple(warnings),
        )

    if internal_span_seconds > maximum_internal_span_seconds:
        return ChainTimestampSummary(
            usable=False,
            representative_timestamp=(representative_timestamp),
            newest_timestamp=newest_timestamp,
            oldest_timestamp=oldest_timestamp,
            valid_count=len(valid_timestamps),
            missing_count=missing_count,
            reason=(
                "option quote timestamps span "
                f"{internal_span_seconds:.1f} seconds, "
                "above the "
                f"{maximum_internal_span_seconds:.1f}"
                "-second limit"
            ),
            warnings=tuple(warnings),
        )

    return ChainTimestampSummary(
        usable=True,
        representative_timestamp=(representative_timestamp),
        newest_timestamp=newest_timestamp,
        oldest_timestamp=oldest_timestamp,
        valid_count=len(valid_timestamps),
        missing_count=missing_count,
        reason=("option quote timestamps are internally consistent"),
        warnings=tuple(warnings),
    )


def validate_market_synchronization(
    quote: UnderlyingQuote,
    chain: ChainTimestampSummary,
    *,
    maximum_difference_seconds: float = 300.0,
) -> MarketSynchronization:
    """Compare the stock quote time with the option-chain time."""

    underlying_timestamps = [
        timestamp
        for timestamp in (
            _as_utc(quote.bid_timestamp),
            _as_utc(quote.ask_timestamp),
        )
        if timestamp is not None
    ]

    if not chain.usable or chain.representative_timestamp is None:
        return MarketSynchronization(
            synchronized=False,
            time_difference_seconds=None,
            underlying_timestamp=(max(underlying_timestamps) if underlying_timestamps else None),
            chain_timestamp=(chain.representative_timestamp),
            reason=(f"option timestamp validation failed: {chain.reason}"),
            warnings=chain.warnings,
        )

    if not underlying_timestamps:
        return MarketSynchronization(
            synchronized=False,
            time_difference_seconds=None,
            underlying_timestamp=None,
            chain_timestamp=(chain.representative_timestamp),
            reason=("underlying bid-ask timestamps are unavailable"),
        )

    underlying_timestamp = max(underlying_timestamps)

    time_difference_seconds = abs(
        (underlying_timestamp - chain.representative_timestamp).total_seconds()
    )

    if time_difference_seconds > maximum_difference_seconds:
        return MarketSynchronization(
            synchronized=False,
            time_difference_seconds=(time_difference_seconds),
            underlying_timestamp=(underlying_timestamp),
            chain_timestamp=(chain.representative_timestamp),
            reason=(
                "underlying and option quotes differ by "
                f"{time_difference_seconds:.1f} seconds, "
                "above the "
                f"{maximum_difference_seconds:.1f}"
                "-second limit"
            ),
            warnings=chain.warnings,
        )

    return MarketSynchronization(
        synchronized=True,
        time_difference_seconds=(time_difference_seconds),
        underlying_timestamp=(underlying_timestamp),
        chain_timestamp=(chain.representative_timestamp),
        reason=("underlying and option quotes are from the same time window"),
        warnings=chain.warnings,
    )
