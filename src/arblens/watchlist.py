from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from arblens.liquidity import LiquidityFilter
from arblens.providers.base import OptionChainProvider
from arblens.scanning import SymbolScanResult, scan_symbol_expirations


@dataclass(frozen=True, slots=True)
class WatchlistSymbolResult:
    symbol: str
    scan: SymbolScanResult | None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class WatchlistScanResult:
    requested_symbols: tuple[str, ...]
    completed_symbols: int
    failed_symbols: int
    results: tuple[WatchlistSymbolResult, ...]


def normalize_symbols(symbols: list[str]) -> list[str]:
    normalized: list[str] = []
    for symbol in symbols:
        cleaned = symbol.strip().upper()
        if cleaned and cleaned not in normalized:
            normalized.append(cleaned)
    return normalized


def load_watchlist(path: str | Path) -> list[str]:
    source = Path(path)
    if not source.exists():
        raise ValueError(f"watchlist file does not exist: {source}")
    if not source.is_file():
        raise ValueError(f"watchlist path is not a file: {source}")
    symbols = normalize_symbols(source.read_text(encoding="utf-8").splitlines())
    if not symbols:
        raise ValueError("watchlist does not contain any symbols")
    return symbols


def scan_watchlist(
    provider: OptionChainProvider,
    symbols: list[str],
    *,
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
) -> WatchlistScanResult:
    normalized = normalize_symbols(symbols)
    if not normalized:
        raise ValueError("at least one symbol is required")

    current_time = captured_at or datetime.now(UTC)
    current_time = (
        current_time.replace(tzinfo=UTC)
        if current_time.tzinfo is None
        else current_time.astimezone(UTC)
    )
    results: list[WatchlistSymbolResult] = []

    for symbol in normalized:
        try:
            scan = scan_symbol_expirations(
                provider,
                symbol,
                maximum_expirations=maximum_expirations,
                captured_at=current_time,
                rate=rate,
                dividend_yield=dividend_yield,
                maximum_sync_gap_seconds=maximum_sync_gap_seconds,
                liquidity_filter=liquidity_filter,
                contract_multiplier=contract_multiplier,
                commission_per_contract=commission_per_contract,
                fee_per_contract=fee_per_contract,
                minimum_net_edge=minimum_net_edge,
            )
            results.append(WatchlistSymbolResult(symbol=symbol, scan=scan))
        except (RuntimeError, TypeError, ValueError) as exc:
            results.append(WatchlistSymbolResult(symbol=symbol, scan=None, error=str(exc)))

    failed = sum(item.error is not None for item in results)
    return WatchlistScanResult(
        requested_symbols=tuple(normalized),
        completed_symbols=len(results) - failed,
        failed_symbols=failed,
        results=tuple(results),
    )
