from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from math import isfinite
from zoneinfo import ZoneInfo


SECONDS_PER_YEAR = 365.0 * 24.0 * 60.0 * 60.0
DEFAULT_EXPIRATION_TIME = time(hour=16, minute=0)
NEW_YORK_TIME = ZoneInfo("America/New_York")


@dataclass(frozen=True, slots=True)
class UnderlyingQuote:
    """Normalized stock or ETF quote used by ArbLens."""

    symbol: str
    bid: float | None
    ask: float | None
    last: float | None
    bid_timestamp: datetime | None = None
    ask_timestamp: datetime | None = None
    trade_timestamp: datetime | None = None


@dataclass(frozen=True, slots=True)
class SpotSelection:
    """Explain which underlying price ArbLens selected."""

    usable: bool
    spot: float | None
    source: str
    warnings: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class ExpirationCalculation:
    """Time remaining until the option expiration timestamp."""

    expiration_timestamp: datetime
    seconds_remaining: float
    days_remaining: float
    years_remaining: float


def _finite_positive_number(
    value: object,
) -> float | None:
    """Return a positive finite float or None."""

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not isfinite(number) or number <= 0:
        return None

    return number


def _normalize_timestamp(
    value: datetime | None,
) -> datetime | None:
    """Convert a timestamp to timezone-aware UTC."""

    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)

    return value.astimezone(UTC)


def _timestamp_age_seconds(
    timestamp: datetime | None,
    *,
    now: datetime,
) -> float | None:
    """Return the age of a timestamp in seconds."""

    normalized = _normalize_timestamp(timestamp)

    if normalized is None:
        return None

    return (now - normalized).total_seconds()


def select_underlying_spot(
    quote: UnderlyingQuote,
    *,
    now: datetime | None = None,
    max_quote_age_seconds: float = 300.0,
    max_trade_age_seconds: float = 300.0,
    max_relative_spread: float = 0.02,
    max_last_midpoint_difference: float = 0.03,
) -> SpotSelection:
    """Choose a safe underlying price from a market quote.

    Selection order:

    1. Use a current, reasonable bid-ask midpoint.
    2. Use a current last trade when bid and ask are unavailable.
    3. Reject internally inconsistent or stale market data.
    """

    if max_quote_age_seconds < 0:
        raise ValueError(
            "max_quote_age_seconds must be non-negative"
        )

    if max_trade_age_seconds < 0:
        raise ValueError(
            "max_trade_age_seconds must be non-negative"
        )

    if max_relative_spread < 0:
        raise ValueError(
            "max_relative_spread must be non-negative"
        )

    if max_last_midpoint_difference < 0:
        raise ValueError(
            "max_last_midpoint_difference must be non-negative"
        )

    current_time = now or datetime.now(UTC)

    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=UTC)
    else:
        current_time = current_time.astimezone(UTC)

    bid = _finite_positive_number(quote.bid)
    ask = _finite_positive_number(quote.ask)
    last = _finite_positive_number(quote.last)

    warnings: list[str] = []

    if bid is not None and ask is not None:
        if bid > ask:
            return SpotSelection(
                usable=False,
                spot=None,
                source="none",
                warnings=(),
                reason=(
                    "underlying quote is crossed because bid "
                    "is greater than ask"
                ),
            )

        midpoint = (bid + ask) / 2.0
        relative_spread = (ask - bid) / midpoint

        if relative_spread > max_relative_spread:
            return SpotSelection(
                usable=False,
                spot=None,
                source="none",
                warnings=(),
                reason=(
                    f"underlying relative spread is "
                    f"{relative_spread:.2%}, above the "
                    f"{max_relative_spread:.2%} limit"
                ),
            )

        bid_age = _timestamp_age_seconds(
            quote.bid_timestamp,
            now=current_time,
        )
        ask_age = _timestamp_age_seconds(
            quote.ask_timestamp,
            now=current_time,
        )

        quote_ages = [
            age
            for age in (bid_age, ask_age)
            if age is not None
        ]

        if quote_ages and max(quote_ages) > max_quote_age_seconds:
            return SpotSelection(
                usable=False,
                spot=None,
                source="none",
                warnings=(),
                reason=(
                    "underlying bid-ask quote is stale; "
                    f"oldest side is {max(quote_ages):.1f} "
                    "seconds old"
                ),
            )

        if not quote_ages:
            warnings.append(
                "underlying bid and ask timestamps were unavailable"
            )

        if last is not None:
            trade_age = _timestamp_age_seconds(
                quote.trade_timestamp,
                now=current_time,
            )

            if (
                trade_age is not None
                and trade_age > max_trade_age_seconds
            ):
                warnings.append(
                    f"last trade is {trade_age:.1f} seconds old; "
                    "it was ignored and the bid-ask midpoint was used"
                )

            else:
                if trade_age is None:
                    warnings.append(
                        "last-trade timestamp was unavailable"
                    )

                last_difference = abs(last - midpoint) / midpoint

                if last_difference > max_last_midpoint_difference:
                    return SpotSelection(
                        usable=False,
                        spot=None,
                        source="none",
                        warnings=tuple(warnings),
                        reason=(
                            f"current last trade differs from the "
                            f"bid-ask midpoint by "
                            f"{last_difference:.2%}, above the "
                            f"{max_last_midpoint_difference:.2%} limit"
                        ),
                    )
        return SpotSelection(
            usable=True,
            spot=midpoint,
            source="bid_ask_midpoint",
            warnings=tuple(warnings),
            reason=(
                "current bid and ask formed a valid market midpoint"
            ),
        )

    if last is not None:
        trade_age = _timestamp_age_seconds(
            quote.trade_timestamp,
            now=current_time,
        )

        if (
            trade_age is not None
            and trade_age > max_trade_age_seconds
        ):
            return SpotSelection(
                usable=False,
                spot=None,
                source="none",
                warnings=(),
                reason=(
                    f"last trade is stale at "
                    f"{trade_age:.1f} seconds old"
                ),
            )

        if trade_age is None:
            warnings.append(
                "last-trade timestamp was unavailable"
            )

        return SpotSelection(
            usable=True,
            spot=last,
            source="last_trade",
            warnings=tuple(warnings),
            reason=(
                "valid last trade was used because a complete "
                "bid-ask quote was unavailable"
            ),
        )

    return SpotSelection(
        usable=False,
        spot=None,
        source="none",
        warnings=(),
        reason=(
            "underlying quote did not contain a usable bid-ask "
            "market or last trade"
        ),
    )


def expiration_timestamp(
    expiration: str,
) -> datetime:
    """Return 4:00 PM New York time for an ISO expiration date."""

    try:
        expiration_date = date.fromisoformat(
            expiration.strip()
        )
    except ValueError as exc:
        raise ValueError(
            "expiration must be an ISO date such as 2026-08-21"
        ) from exc

    local_expiration = datetime.combine(
        expiration_date,
        DEFAULT_EXPIRATION_TIME,
        tzinfo=NEW_YORK_TIME,
    )

    return local_expiration.astimezone(UTC)


def calculate_time_to_expiration(
    expiration: str,
    *,
    now: datetime | None = None,
) -> ExpirationCalculation:
    """Calculate remaining calendar time in seconds, days, and years."""

    current_time = now or datetime.now(UTC)

    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=UTC)
    else:
        current_time = current_time.astimezone(UTC)

    expiration_time = expiration_timestamp(expiration)
    seconds_remaining = (
        expiration_time - current_time
    ).total_seconds()

    if seconds_remaining <= 0:
        raise ValueError(
            "expiration has already passed"
        )

    return ExpirationCalculation(
        expiration_timestamp=expiration_time,
        seconds_remaining=seconds_remaining,
        days_remaining=(
            seconds_remaining / (24.0 * 60.0 * 60.0)
        ),
        years_remaining=(
            seconds_remaining / SECONDS_PER_YEAR
        ),
    )