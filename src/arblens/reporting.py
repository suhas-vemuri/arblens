from __future__ import annotations

from pathlib import Path

import pandas as pd

from arblens.scanning import SymbolScanResult
from arblens.watchlist import WatchlistScanResult

SCAN_REPORT_COLUMNS = [
    "symbol",
    "expiration",
    "status",
    "raw_rows",
    "clean_rows",
    "liquid_rows",
    "liquidity_removed_rows",
    "quote_issues",
    "quote_errors",
    "quote_warnings",
    "spot_used",
    "time_to_expiration_years",
    "synchronization_passed",
    "synchronization_reason",
    "spot_checks_skipped",
    "violations",
    "midpoint_violations",
    "executable_violations",
    "opportunities_after_costs",
    "error",
]


def scan_result_to_frame(result: SymbolScanResult) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for item in result.results:
        if item.error is not None:
            status = "failed"
        elif item.spot_dependent_checks_skipped:
            status = "completed_chain_only"
        else:
            status = "completed_full"

        rows.append(
            {
                "symbol": item.symbol,
                "expiration": item.expiration,
                "status": status,
                "raw_rows": item.raw_rows,
                "clean_rows": item.clean_rows,
                "liquid_rows": item.liquid_rows,
                "liquidity_removed_rows": item.liquidity_removed_rows,
                "quote_issues": item.quote_issues,
                "quote_errors": item.quote_errors,
                "quote_warnings": item.quote_warnings,
                "spot_used": item.spot_used,
                "time_to_expiration_years": item.time_to_expiration_years,
                "synchronization_passed": item.synchronization_passed,
                "synchronization_reason": item.synchronization_reason,
                "spot_checks_skipped": item.spot_dependent_checks_skipped,
                "violations": item.violation_count,
                "midpoint_violations": item.midpoint_violation_count,
                "executable_violations": item.executable_violation_count,
                "opportunities_after_costs": item.opportunities_after_costs,
                "error": item.error,
            }
        )
    return pd.DataFrame(rows, columns=SCAN_REPORT_COLUMNS)


def watchlist_result_to_frame(result: WatchlistScanResult) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for symbol_result in result.results:
        if symbol_result.scan is not None:
            frames.append(scan_result_to_frame(symbol_result.scan))
        else:
            frames.append(
                pd.DataFrame(
                    [
                        {
                            "symbol": symbol_result.symbol,
                            "status": "failed",
                            "error": symbol_result.error,
                        }
                    ],
                    columns=SCAN_REPORT_COLUMNS,
                )
            )
    if not frames:
        return pd.DataFrame(columns=SCAN_REPORT_COLUMNS)
    return pd.concat(frames, ignore_index=True)


def save_frame_csv(frame: pd.DataFrame, path: str | Path) -> Path:
    destination = Path(path)
    if destination.suffix.lower() != ".csv":
        raise ValueError("report path must end with .csv")
    destination.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(destination, index=False)
    return destination


def save_scan_report(result: SymbolScanResult, path: str | Path) -> Path:
    return save_frame_csv(scan_result_to_frame(result), path)


def save_watchlist_report(result: WatchlistScanResult, path: str | Path) -> Path:
    return save_frame_csv(watchlist_result_to_frame(result), path)
