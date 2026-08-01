from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from arblens.cleaning import clean_quotes
from arblens.detection import run_all_checks
from arblens.execution import assess_opportunities
from arblens.liquidity import LiquidityFilter, apply_liquidity_filters
from arblens.market import (
    UnderlyingQuote,
    calculate_time_to_expiration,
    select_underlying_spot,
    summarize_chain_timestamps,
    validate_market_synchronization,
)
from arblens.models import OpportunityAssessment
from arblens.providers.base import OptionChainProvider


@dataclass(frozen=True, slots=True)
class ExpirationScanResult:
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
    liquid_rows: int = 0
    liquidity_removed_rows: int = 0
    opportunities_after_costs: int = 0
    assessments: tuple[OpportunityAssessment, ...] = ()


@dataclass(frozen=True, slots=True)
class SymbolScanResult:
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
    available = list(
        dict.fromkeys(item.strip() for item in available_expirations if item and item.strip())
    )
    if requested_expirations is None:
        selected = available
    else:
        requested = list(
            dict.fromkeys(item.strip() for item in requested_expirations if item and item.strip())
        )
        unavailable = [item for item in requested if item not in available]
        if unavailable:
            raise ValueError("requested expirations are not available: " + ", ".join(unavailable))
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
    method = getattr(provider, "get_underlying_quote", None)
    if not callable(method):
        return None
    try:
        quote = method(symbol)
    except (NotImplementedError, RuntimeError, ValueError):
        return None
    return quote if isinstance(quote, UnderlyingQuote) else None


def _count_price_basis(violations: list[Any], price_basis: str) -> int:
    return sum(getattr(item, "price_basis", None) == price_basis for item in violations)


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
    liquidity_filter: LiquidityFilter | None = None,
    contract_multiplier: int = 100,
    commission_per_contract: float = 0.65,
    fee_per_contract: float = 0.05,
    minimum_net_edge: float = 0.0,
) -> SymbolScanResult:
    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol:
        raise ValueError("symbol must not be empty")
    if maximum_sync_gap_seconds <= 0:
        raise ValueError("maximum_sync_gap_seconds must be greater than zero")

    rules = liquidity_filter or LiquidityFilter()
    rules.validate()
    current_time = captured_at or datetime.now(UTC)
    current_time = (
        current_time.replace(tzinfo=UTC)
        if current_time.tzinfo is None
        else current_time.astimezone(UTC)
    )

    selected = select_expirations(
        provider.get_expirations(normalized_symbol),
        requested_expirations=expirations,
        maximum_expirations=maximum_expirations,
    )
    quote = _get_underlying_quote(provider, normalized_symbol)
    selection = select_underlying_spot(quote, now=current_time) if quote else None
    results: list[ExpirationScanResult] = []

    for expiration in selected:
        try:
            raw = provider.get_chain(normalized_symbol, expiration)
            if not isinstance(raw, pd.DataFrame):
                raise TypeError("provider option chain must be a pandas DataFrame")

            cleaned, issues = clean_quotes(raw)
            liquid, liquidity = apply_liquidity_filters(cleaned, rules)
            calculation = calculate_time_to_expiration(expiration, now=current_time)
            chain_summary = summarize_chain_timestamps(raw)

            sync_passed: bool | None = None
            sync_reason = "underlying quote unavailable"
            spot: float | None = None

            if quote is not None and selection is not None:
                sync = validate_market_synchronization(
                    quote,
                    chain_summary,
                    maximum_difference_seconds=maximum_sync_gap_seconds,
                )
                sync_passed = sync.synchronized
                sync_reason = sync.reason
                if selection.usable and sync.synchronized:
                    spot = selection.spot

            time_value = calculation.years_remaining if spot is not None else None
            violations = run_all_checks(
                liquid,
                spot=spot,
                time=time_value,
                rate=rate,
                dividend_yield=dividend_yield,
            )
            assessments = assess_opportunities(
                violations,
                contract_multiplier=contract_multiplier,
                commission_per_contract=commission_per_contract,
                fee_per_contract=fee_per_contract,
                minimum_net_edge=minimum_net_edge,
            )

            results.append(
                ExpirationScanResult(
                    symbol=normalized_symbol,
                    expiration=expiration,
                    raw_rows=len(raw),
                    clean_rows=len(cleaned),
                    quote_issues=len(issues),
                    quote_errors=sum(item.severity == "error" for item in issues),
                    quote_warnings=sum(item.severity == "warning" for item in issues),
                    spot_used=spot,
                    time_to_expiration_years=calculation.years_remaining,
                    synchronization_passed=sync_passed,
                    synchronization_reason=sync_reason,
                    spot_dependent_checks_skipped=spot is None,
                    violation_count=len(violations),
                    midpoint_violation_count=_count_price_basis(violations, "midpoint"),
                    executable_violation_count=_count_price_basis(violations, "bid_ask"),
                    liquid_rows=len(liquid),
                    liquidity_removed_rows=liquidity.removed_rows,
                    opportunities_after_costs=sum(
                        item.profitable_after_costs for item in assessments
                    ),
                    assessments=tuple(assessments),
                )
            )
        except (RuntimeError, TypeError, ValueError) as exc:
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
                    synchronization_reason="scan failed",
                    spot_dependent_checks_skipped=True,
                    violation_count=0,
                    midpoint_violation_count=0,
                    executable_violation_count=0,
                    error=str(exc),
                )
            )

    failed = sum(item.error is not None for item in results)
    return SymbolScanResult(
        symbol=normalized_symbol,
        requested_expirations=tuple(selected),
        completed_expirations=len(results) - failed,
        failed_expirations=failed,
        results=tuple(results),
    )
