from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from arblens.cleaning import clean_quotes
from arblens.detection import run_all_checks
from arblens.market import (
    UnderlyingQuote,
    calculate_time_to_expiration,
    select_underlying_spot,
    summarize_chain_timestamps,
    validate_market_synchronization,
)
from arblens.providers.base import OptionChainProvider


@dataclass(frozen=True, slots=True)
class ExpirationScanResult:
    """Summary of one expiration scan."""

    symbol: str
    expiration: str
    raw_rows: int
    clean_rows: int
    quote_issues: int
    quote_errors: int
    quote_warnings: int
    spot_used: float | None
    time_to_expiration_years: float | None
    synchronization_passed: bool | None
    synchronization_reason: str
    spot_dependent_checks_skipped: bool
    violation_count: int
    midpoint_violation_count: int
    executable_violation_count: int
    error: str | None = None


@dataclass(frozen=True, slots=True)
class SymbolScanResult:
    """Combined result for one symbol."""

    symbol: str
    requested_expirations: tuple[str, ...]
    completed_expirations: int
    failed_expirations: int
    results: tuple[ExpirationScanResult, ...]


def select_expirations(
    available_expirations: list[str],
    *,
    requested_expirations: list[str] | None = None,
    maximum_expirations: int | None = None,
) -> list[str]:
    """Choose which expirations should be scanned."""

    available = list(
        dict.fromkeys(
            expiration.strip()
            for expiration in available_expirations
            if expiration and expiration.strip()
        )
    )

    if requested_expirations is None:
        selected = available

    else:
        requested = list(
            dict.fromkeys(
                expiration.strip()
                for expiration in requested_expirations
                if expiration and expiration.strip()
            )
        )

        unavailable = [expiration for expiration in requested if expiration not in available]

        if unavailable:
            unavailable_text = ", ".join(unavailable)

            raise ValueError(f"requested expirations are not available: {unavailable_text}")

        selected = requested

    if maximum_expirations is not None:
        if maximum_expirations <= 0:
            raise ValueError("maximum_expirations must be greater than zero")

        selected = selected[:maximum_expirations]

    return selected


def _get_underlying_quote(
    provider: OptionChainProvider,
    symbol: str,
) -> UnderlyingQuote | None:
    """Fetch an underlying quote when supported."""

    quote_method = getattr(
        provider,
        "get_underlying_quote",
        None,
    )

    if not callable(quote_method):
        return None

    try:
        quote = quote_method(symbol)

    except (
        NotImplementedError,
        RuntimeError,
        ValueError,
    ):
        return None

    if not isinstance(
        quote,
        UnderlyingQuote,
    ):
        return None

    return quote


def _count_price_basis(
    violations: list[Any],
    price_basis: str,
) -> int:
    """Count violations with one price basis."""

    return sum(
        getattr(
            violation,
            "price_basis",
            None,
        )
        == price_basis
        for violation in violations
    )


def scan_symbol_expirations(
    provider: OptionChainProvider,
    symbol: str,
    *,
    expirations: list[str] | None = None,
    maximum_expirations: int | None = None,
    captured_at: datetime | None = None,
    rate: float = 0.04,
    dividend_yield: float = 0.0,
    maximum_sync_gap_seconds: float = 300.0,
) -> SymbolScanResult:
    """Scan several expirations for one symbol."""

    normalized_symbol = symbol.strip().upper()

    if not normalized_symbol:
        raise ValueError("symbol must not be empty")

    if maximum_sync_gap_seconds <= 0:
        raise ValueError("maximum_sync_gap_seconds must be greater than zero")

    current_time = captured_at or datetime.now(UTC)

    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=UTC)

    else:
        current_time = current_time.astimezone(UTC)

    available_expirations = provider.get_expirations(normalized_symbol)

    selected_expirations = select_expirations(
        available_expirations,
        requested_expirations=expirations,
        maximum_expirations=(maximum_expirations),
    )

    underlying_quote = _get_underlying_quote(
        provider,
        normalized_symbol,
    )

    spot_selection = None

    if underlying_quote is not None:
        spot_selection = select_underlying_spot(
            underlying_quote,
            now=current_time,
        )

    results: list[ExpirationScanResult] = []

    for expiration in selected_expirations:
        try:
            raw = provider.get_chain(
                normalized_symbol,
                expiration,
            )

            if not isinstance(
                raw,
                pd.DataFrame,
            ):
                raise TypeError("provider option chain must be a pandas DataFrame")

            cleaned, quote_issues = clean_quotes(raw)

            quote_error_count = sum(issue.severity == "error" for issue in quote_issues)

            quote_warning_count = sum(issue.severity == "warning" for issue in quote_issues)

            expiration_calculation = calculate_time_to_expiration(
                expiration,
                now=current_time,
            )

            chain_timestamp_summary = summarize_chain_timestamps(raw)

            synchronization_passed: bool | None = None

            synchronization_reason = "underlying quote unavailable"

            spot_for_checks: float | None = None

            if underlying_quote is not None and spot_selection is not None:
                synchronization = validate_market_synchronization(
                    underlying_quote,
                    chain_timestamp_summary,
                    maximum_difference_seconds=(maximum_sync_gap_seconds),
                )

                synchronization_passed = synchronization.synchronized

                synchronization_reason = synchronization.reason

                if spot_selection.usable and synchronization.synchronized:
                    spot_for_checks = spot_selection.spot

            time_for_checks = (
                expiration_calculation.years_remaining if spot_for_checks is not None else None
            )

            violations = run_all_checks(
                cleaned,
                spot=spot_for_checks,
                time=time_for_checks,
                rate=rate,
                dividend_yield=(dividend_yield),
            )

            results.append(
                ExpirationScanResult(
                    symbol=normalized_symbol,
                    expiration=expiration,
                    raw_rows=len(raw),
                    clean_rows=len(cleaned),
                    quote_issues=len(quote_issues),
                    quote_errors=(quote_error_count),
                    quote_warnings=(quote_warning_count),
                    spot_used=spot_for_checks,
                    time_to_expiration_years=(expiration_calculation.years_remaining),
                    synchronization_passed=(synchronization_passed),
                    synchronization_reason=(synchronization_reason),
                    spot_dependent_checks_skipped=(spot_for_checks is None),
                    violation_count=len(violations),
                    midpoint_violation_count=(
                        _count_price_basis(
                            violations,
                            "midpoint",
                        )
                    ),
                    executable_violation_count=(
                        _count_price_basis(
                            violations,
                            "bid_ask",
                        )
                    ),
                )
            )

        except (
            RuntimeError,
            TypeError,
            ValueError,
        ) as exc:
            results.append(
                ExpirationScanResult(
                    symbol=normalized_symbol,
                    expiration=expiration,
                    raw_rows=0,
                    clean_rows=0,
                    quote_issues=0,
                    quote_errors=0,
                    quote_warnings=0,
                    spot_used=None,
                    time_to_expiration_years=None,
                    synchronization_passed=None,
                    synchronization_reason=("scan failed"),
                    spot_dependent_checks_skipped=True,
                    violation_count=0,
                    midpoint_violation_count=0,
                    executable_violation_count=0,
                    error=str(exc),
                )
            )

    failed_expirations = sum(result.error is not None for result in results)

    return SymbolScanResult(
        symbol=normalized_symbol,
        requested_expirations=tuple(selected_expirations),
        completed_expirations=(len(results) - failed_expirations),
        failed_expirations=(failed_expirations),
        results=tuple(results),
    )
