from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from arblens.providers.base import OptionChainProvider
from arblens.scanning import SymbolScanResult, scan_symbol_expirations


@dataclass(frozen=True, slots=True)
class WatchlistSymbolResult:
    """Result of scanning one watchlist symbol."""

    symbol: str
    scan: SymbolScanResult | None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class WatchlistScanResult:
    """Combined result for all watchlist symbols."""

    requested_symbols: tuple[str, ...]
    completed_symbols: int
    failed_symbols: int
    results: tuple[WatchlistSymbolResult, ...]


def normalize_symbols(
    symbols: list[str],
) -> list[str]:
    """Clean, capitalize, and remove duplicate symbols."""

    normalized: list[str] = []

    for symbol in symbols:
        cleaned_symbol = symbol.strip().upper()

        if not cleaned_symbol:
            continue

        if cleaned_symbol not in normalized:
            normalized.append(cleaned_symbol)

    return normalized


def load_watchlist(
    path: str | Path,
) -> list[str]:
    """Load one symbol from each line of a text file."""

    watchlist_path = Path(path)

    if not watchlist_path.exists():
        raise ValueError(f"watchlist file does not exist: {watchlist_path}")

    if not watchlist_path.is_file():
        raise ValueError(f"watchlist path is not a file: {watchlist_path}")

    symbols = normalize_symbols(watchlist_path.read_text(encoding="utf-8").splitlines())

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
) -> WatchlistScanResult:
    """Scan several symbols without allowing one failure to stop the rest."""

    normalized_symbols = normalize_symbols(symbols)

    if not normalized_symbols:
        raise ValueError("at least one symbol is required")

    current_time = captured_at or datetime.now(UTC)

    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=UTC)
    else:
        current_time = current_time.astimezone(UTC)

    results: list[WatchlistSymbolResult] = []

    for symbol in normalized_symbols:
        try:
            scan = scan_symbol_expirations(
                provider,
                symbol,
                maximum_expirations=maximum_expirations,
                captured_at=current_time,
                rate=rate,
                dividend_yield=dividend_yield,
                maximum_sync_gap_seconds=(maximum_sync_gap_seconds),
            )

            results.append(
                WatchlistSymbolResult(
                    symbol=symbol,
                    scan=scan,
                )
            )

        except (
            RuntimeError,
            TypeError,
            ValueError,
        ) as exc:
            results.append(
                WatchlistSymbolResult(
                    symbol=symbol,
                    scan=None,
                    error=str(exc),
                )
            )

    failed_symbols = sum(result.error is not None for result in results)

    return WatchlistScanResult(
        requested_symbols=tuple(normalized_symbols),
        completed_symbols=(len(results) - failed_symbols),
        failed_symbols=failed_symbols,
        results=tuple(results),
    )
