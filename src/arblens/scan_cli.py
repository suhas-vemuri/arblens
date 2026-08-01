from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from arblens.providers.tradier import (
    TradierAPIError,
    TradierProvider,
)
from arblens.reporting import (
    save_scan_report,
    scan_result_to_frame,
)
from arblens.scanning import (
    scan_symbol_expirations,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the multi-expiration scan command."""

    parser = argparse.ArgumentParser(description=("Scan several option expirations for one symbol"))

    parser.add_argument(
        "symbol",
        help=("stock or ETF symbol, such as AAPL or SPY"),
    )

    parser.add_argument(
        "--expiration",
        action="append",
        dest="expirations",
        help=(
            "specific expiration to scan; "
            "use this option more than once "
            "to request multiple expirations"
        ),
    )

    parser.add_argument(
        "--maximum-expirations",
        type=int,
        default=None,
        help=("maximum number of expirations to scan"),
    )

    parser.add_argument(
        "--maximum-sync-gap-seconds",
        type=float,
        default=300.0,
        help=("largest allowed time difference between stock and option quotes"),
    )

    parser.add_argument(
        "--rate",
        type=float,
        default=0.04,
        help="annual risk-free rate",
    )

    parser.add_argument(
        "--dividend-yield",
        type=float,
        default=0.0,
        help="annual dividend yield",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=("optional CSV report path"),
    )

    parser.add_argument(
        "--allow-production",
        action="store_true",
        help=("allow the Tradier production API"),
    )

    return parser


def validate_environment(
    provider: TradierProvider,
    *,
    allow_production: bool,
) -> None:
    """Block accidental production access."""

    if provider.environment == "production" and not allow_production:
        raise ValueError(
            "Tradier production access is blocked by default; rerun with --allow-production"
        )


def default_output_path(
    symbol: str,
    captured_at: datetime,
) -> Path:
    """Build a timestamped report filename."""

    normalized_symbol = symbol.strip().upper()

    return Path(
        "data",
        "reports",
        (f"{normalized_symbol}_scan_{captured_at:%Y%m%dT%H%M%SZ}.csv"),
    )


def run(
    args: argparse.Namespace,
) -> int:
    """Run one multi-expiration scan."""

    provider = TradierProvider()

    validate_environment(
        provider,
        allow_production=(args.allow_production),
    )

    captured_at = datetime.now(UTC)

    result = scan_symbol_expirations(
        provider,
        args.symbol,
        expirations=args.expirations,
        maximum_expirations=(args.maximum_expirations),
        captured_at=captured_at,
        rate=args.rate,
        dividend_yield=(args.dividend_yield),
        maximum_sync_gap_seconds=(args.maximum_sync_gap_seconds),
    )

    report = scan_result_to_frame(result)

    print(f"Provider environment: {provider.environment}")

    print(f"Symbol: {result.symbol}")

    print(f"Requested expirations: {len(result.requested_expirations)}")

    print(f"Completed expirations: {result.completed_expirations}")

    print(f"Failed expirations: {result.failed_expirations}")

    print()

    if report.empty:
        print("No expirations were scanned.")

    else:
        display_columns = [
            "expiration",
            "status",
            "raw_rows",
            "quote_errors",
            "synchronization_passed",
            "spot_checks_skipped",
            "violations",
            "executable_violations",
            "error",
        ]

        print(report[display_columns].to_string(index=False))

    output_path = (
        args.output
        if args.output is not None
        else default_output_path(
            result.symbol,
            captured_at,
        )
    )

    saved_path = save_scan_report(
        result,
        output_path,
    )

    print()
    print(f"Report saved: {saved_path}")

    return 0


def main(
    argv: Sequence[str] | None = None,
) -> int:
    """Parse command-line arguments."""

    parser = build_parser()

    args = parser.parse_args(argv)

    try:
        return run(args)

    except (
        TradierAPIError,
        ValueError,
    ) as exc:
        parser.error(str(exc))

    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
