from __future__ import annotations

from pathlib import Path

import pandas as pd

from arblens.scanning import SymbolScanResult

SCAN_REPORT_COLUMNS = [
    "symbol",
    "expiration",
    "status",
    "raw_rows",
    "clean_rows",
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
    "error",
]


def scan_result_to_frame(
    result: SymbolScanResult,
) -> pd.DataFrame:
    """Convert one symbol scan into a compact table."""

    rows: list[dict[str, object]] = []

    for expiration_result in result.results:
        if expiration_result.error is not None:
            status = "failed"

        elif expiration_result.spot_dependent_checks_skipped:
            status = "completed_chain_only"

        else:
            status = "completed_full"

        rows.append(
            {
                "symbol": expiration_result.symbol,
                "expiration": (expiration_result.expiration),
                "status": status,
                "raw_rows": (expiration_result.raw_rows),
                "clean_rows": (expiration_result.clean_rows),
                "quote_issues": (expiration_result.quote_issues),
                "quote_errors": (expiration_result.quote_errors),
                "quote_warnings": (expiration_result.quote_warnings),
                "spot_used": (expiration_result.spot_used),
                "time_to_expiration_years": (expiration_result.time_to_expiration_years),
                "synchronization_passed": (expiration_result.synchronization_passed),
                "synchronization_reason": (expiration_result.synchronization_reason),
                "spot_checks_skipped": (expiration_result.spot_dependent_checks_skipped),
                "violations": (expiration_result.violation_count),
                "midpoint_violations": (expiration_result.midpoint_violation_count),
                "executable_violations": (expiration_result.executable_violation_count),
                "error": expiration_result.error,
            }
        )

    return pd.DataFrame(
        rows,
        columns=SCAN_REPORT_COLUMNS,
    )


def save_scan_report(
    result: SymbolScanResult,
    path: str | Path,
) -> Path:
    """Save one compact multi-expiration report."""

    destination = Path(path)

    if destination.suffix.lower() != ".csv":
        raise ValueError("scan report path must end with .csv")

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    report = scan_result_to_frame(result)

    report.to_csv(
        destination,
        index=False,
    )

    return destination
