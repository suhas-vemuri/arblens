from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence

import pandas as pd

from arblens.cleaning import clean_quotes
from arblens.detection import (
    run_all_checks,
    violations_to_frame,
)
from arblens.io import (
    load_chain,
    save_timestamped_snapshot,
)
from arblens.providers.base import OptionChainProvider
from arblens.providers.tradier import (
    TradierAPIError,
    TradierProvider,
)

ProviderFactory = Callable[[], OptionChainProvider]


def add_analysis_arguments(
    parser: argparse.ArgumentParser,
    *,
    spot_default: float | None,
) -> None:
    """Add pricing assumptions shared by analysis commands."""
    parser.add_argument(
        "--spot",
        type=float,
        default=spot_default,
        help=("underlying spot price; for fetch, providing this also runs analysis"),
    )
    parser.add_argument(
        "--time",
        type=float,
        default=30 / 365,
        help="time to expiration in years",
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=0.04,
        help="annual risk-free interest rate",
    )
    parser.add_argument(
        "--dividend-yield",
        type=float,
        default=0.0,
        help="annual dividend yield",
    )


def add_provider_safety_argument(
    parser: argparse.ArgumentParser,
) -> None:
    """Add the explicit production-access confirmation flag."""
    parser.add_argument(
        "--allow-production",
        action="store_true",
        help=("explicitly allow requests to Tradier's production endpoint"),
    )


def build_parser() -> argparse.ArgumentParser:
    """Create the ArbLens command-line parser."""
    parser = argparse.ArgumentParser(
        description=("Analyze saved option chains or fetch Tradier snapshots")
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    analyze_parser = subparsers.add_parser(
        "analyze",
        help="analyze a saved CSV or Parquet option chain",
    )
    analyze_parser.add_argument(
        "path",
        help="CSV or Parquet option-chain file",
    )
    add_analysis_arguments(
        analyze_parser,
        spot_default=100.0,
    )

    expirations_parser = subparsers.add_parser(
        "expirations",
        help="list available Tradier option expirations",
    )
    expirations_parser.add_argument(
        "symbol",
        help="underlying symbol, such as SPY",
    )
    add_provider_safety_argument(expirations_parser)

    fetch_parser = subparsers.add_parser(
        "fetch",
        help="fetch and save one Tradier option chain",
    )
    fetch_parser.add_argument(
        "symbol",
        help="underlying symbol, such as SPY",
    )
    fetch_parser.add_argument(
        "--expiration",
        required=True,
        help="option expiration in YYYY-MM-DD format",
    )
    fetch_parser.add_argument(
        "--output-dir",
        default="data/snapshots",
        help="directory where snapshots are saved",
    )
    fetch_parser.add_argument(
        "--format",
        choices=("parquet", "csv"),
        default="parquet",
        help="snapshot file format",
    )
    add_provider_safety_argument(fetch_parser)
    add_analysis_arguments(
        fetch_parser,
        spot_default=None,
    )

    return parser


def normalize_arguments(
    argv: Sequence[str] | None,
) -> list[str]:
    """Preserve the original file-analysis command format."""
    arguments = list(sys.argv[1:] if argv is None else argv)

    commands = {
        "analyze",
        "expirations",
        "fetch",
        "-h",
        "--help",
    }

    if arguments and arguments[0] not in commands:
        arguments.insert(0, "analyze")

    return arguments


def validate_provider_environment(
    provider: OptionChainProvider,
    *,
    allow_production: bool,
) -> None:
    """Block accidental production requests."""
    environment = provider.environment

    if environment == "production" and not allow_production:
        raise ValueError(
            "Tradier production access is blocked by default; "
            "rerun with --allow-production to continue"
        )

    print(f"Provider environment: {environment}")


def print_analysis(
    raw: pd.DataFrame,
    *,
    spot: float,
    time: float,
    rate: float,
    dividend_yield: float,
) -> None:
    """Clean, analyze, and print one option-chain summary."""
    cleaned, issues = clean_quotes(raw)

    error_count = sum(issue.severity == "error" for issue in issues)
    warning_count = sum(issue.severity == "warning" for issue in issues)

    if cleaned.empty:
        average_spread = 0.0
    else:
        average_spread = float((cleaned["ask"] - cleaned["bid"]).mean())

    violations = run_all_checks(
        cleaned,
        spot=spot,
        time=time,
        rate=rate,
        dividend_yield=dividend_yield,
    )
    midpoint_violation_count = sum(violation.price_basis == "midpoint" for violation in violations)

    executable_violation_count = sum(violation.price_basis == "bid_ask" for violation in violations)
    print(f"Raw rows: {len(raw)}")
    print(f"Clean rows: {len(cleaned)}")
    print(f"Quote issues: {len(issues)}")
    print(f"Quote errors: {error_count}")
    print(f"Quote warnings: {warning_count}")
    print(f"Average bid-ask spread: {average_spread:.4f}")
    print(f"Violations: {len(violations)}")
    print(f"Midpoint violations: {midpoint_violation_count}")
    print(f"Executable violations: {executable_violation_count}")
    print()

    table = violations_to_frame(violations)

    if table.empty:
        print("No violations detected.")
    else:
        print(table.to_string(index=False))


def run_analyze(args: argparse.Namespace) -> None:
    """Analyze an existing local option-chain file."""
    raw = load_chain(args.path)

    print_analysis(
        raw,
        spot=args.spot,
        time=args.time,
        rate=args.rate,
        dividend_yield=args.dividend_yield,
    )


def run_expirations(
    args: argparse.Namespace,
    provider_factory: ProviderFactory,
) -> None:
    """List available option expirations for one symbol."""
    provider = provider_factory()

    validate_provider_environment(
        provider,
        allow_production=args.allow_production,
    )

    expirations = provider.get_expirations(args.symbol)
    normalized_symbol = args.symbol.strip().upper()

    print(f"Symbol: {normalized_symbol}")
    print(f"Available expirations: {len(expirations)}")

    if not expirations:
        print()
        print("No expirations returned.")
        return

    print()

    for expiration in expirations:
        print(expiration)


def run_fetch(
    args: argparse.Namespace,
    provider_factory: ProviderFactory,
) -> None:
    """Fetch, save, and optionally analyze a Tradier chain."""
    provider = provider_factory()

    validate_provider_environment(
        provider,
        allow_production=args.allow_production,
    )

    available_expirations = provider.get_expirations(args.symbol)

    if args.expiration not in available_expirations:
        normalized_symbol = args.symbol.strip().upper()

        raise ValueError(f"expiration {args.expiration} is not available for {normalized_symbol}")

    raw = provider.get_chain(
        args.symbol,
        args.expiration,
    )

    print(f"Fetched contracts: {len(raw)}")

    if raw.empty:
        print("No option contracts returned; snapshot was not saved.")
        return

    destination = save_timestamped_snapshot(
        raw,
        args.symbol,
        args.expiration,
        directory=args.output_dir,
        file_format=args.format,
    )

    print(f"Snapshot saved: {destination}")

    if args.spot is not None:
        print()

        print_analysis(
            raw,
            spot=args.spot,
            time=args.time,
            rate=args.rate,
            dividend_yield=args.dividend_yield,
        )


def main(
    argv: Sequence[str] | None = None,
    *,
    provider_factory: ProviderFactory = TradierProvider,
) -> int:
    """Run the ArbLens command-line application."""
    parser = build_parser()
    args = parser.parse_args(normalize_arguments(argv))

    try:
        if args.command == "analyze":
            run_analyze(args)
        elif args.command == "expirations":
            run_expirations(
                args,
                provider_factory,
            )
        elif args.command == "fetch":
            run_fetch(
                args,
                provider_factory,
            )
    except (
        FileNotFoundError,
        TradierAPIError,
        ValueError,
    ) as exc:
        parser.error(str(exc))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
