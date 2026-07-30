from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from collections.abc import Callable, Sequence

import pandas as pd

from arblens.cleaning import clean_quotes
from arblens.detection import (
    run_all_checks,
    violations_to_frame,
)
from arblens.execution import (
    assess_opportunities,
    assessments_to_frame,
)
from arblens.io import (
    load_chain,
    save_timestamped_snapshot,
)
from arblens.market import (
    calculate_time_to_expiration,
    select_underlying_spot,
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
    time_default: float | None = 30 / 365,
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
        default=time_default,
        help=(
            "time to expiration in years; "
            "fetch calculates this automatically "
            "when omitted"
        ),
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


def add_execution_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    """Add assumptions used for executable-edge analysis."""
    parser.add_argument(
        "--contract-multiplier",
        type=int,
        default=100,
        help=("underlying units represented by one option contract"),
    )
    parser.add_argument(
        "--commission-per-contract",
        type=float,
        default=0.65,
        help=("estimated commission charged for each option contract"),
    )
    parser.add_argument(
        "--fee-per-contract",
        type=float,
        default=0.05,
        help=("additional estimated fees for each option contract"),
    )
    parser.add_argument(
        "--minimum-net-edge",
        type=float,
        default=0.0,
        help=("required net edge per strategy after estimated costs"),
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
    add_execution_arguments(analyze_parser)

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
        time_default=None,
    )
    add_execution_arguments(fetch_parser)

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
            "Tradier production access is blocked by "
            "default; rerun with --allow-production "
            "to continue"
        )

    print(f"Provider environment: {environment}")


def print_analysis(
    raw: pd.DataFrame,
    *,
    spot: float | None,
    time: float | None,
    rate: float,
    dividend_yield: float,
    contract_multiplier: int,
    commission_per_contract: float,
    fee_per_contract: float,
    minimum_net_edge: float,
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

    assessments = assess_opportunities(
        violations,
        contract_multiplier=contract_multiplier,
        commission_per_contract=(commission_per_contract),
        fee_per_contract=fee_per_contract,
        minimum_net_edge=minimum_net_edge,
    )

    opportunities_after_costs = sum(assessment.profitable_after_costs for assessment in assessments)

    removed_by_spread = sum(assessment.status == "removed_by_spread" for assessment in assessments)

    removed_by_costs = sum(assessment.status == "removed_by_costs" for assessment in assessments)

    print(f"Raw rows: {len(raw)}")
    print(f"Clean rows: {len(cleaned)}")
    print(f"Quote issues: {len(issues)}")
    print(f"Quote errors: {error_count}")
    print(f"Quote warnings: {warning_count}")
    print(f"Average bid-ask spread: {average_spread:.4f}")
    print(f"Violations: {len(violations)}")
    print(f"Midpoint violations: {midpoint_violation_count}")
    print(f"Executable violations: {executable_violation_count}")
    print(f"Opportunities after costs: {opportunities_after_costs}")
    print(f"Removed by bid-ask spread: {removed_by_spread}")
    print(f"Removed by transaction costs: {removed_by_costs}")
    print()

    violation_table = violations_to_frame(violations)

    if violation_table.empty:
        print("No violations detected.")
    else:
        print(violation_table.to_string(index=False))

    print()
    print("Opportunity assessment:")

    assessment_table = assessments_to_frame(assessments)

    if assessment_table.empty:
        print("No opportunities to assess.")
    else:
        print(assessment_table.to_string(index=False))


def run_analyze(
    args: argparse.Namespace,
) -> None:
    """Analyze an existing local option-chain file."""
    raw = load_chain(args.path)

    print_analysis(
        raw,
        spot=args.spot,
        time=args.time,
        rate=args.rate,
        dividend_yield=args.dividend_yield,
        contract_multiplier=(args.contract_multiplier),
        commission_per_contract=(args.commission_per_contract),
        fee_per_contract=(args.fee_per_contract),
        minimum_net_edge=(args.minimum_net_edge),
    )


def run_expirations(
    args: argparse.Namespace,
    provider_factory: ProviderFactory,
) -> None:
    """List available option expirations for one symbol."""
    provider = provider_factory()

    validate_provider_environment(
        provider,
        allow_production=(args.allow_production),
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
    """Fetch, save, and analyze a Tradier option chain."""

    provider = provider_factory()

    validate_provider_environment(
        provider,
        allow_production=args.allow_production,
    )

    normalized_symbol = args.symbol.strip().upper()

    available_expirations = provider.get_expirations(
        normalized_symbol
    )

    if args.expiration not in available_expirations:
        raise ValueError(
            f"expiration {args.expiration} is not available "
            f"for {normalized_symbol}"
        )

    captured_at = datetime.now(UTC)

    raw = provider.get_chain(
        normalized_symbol,
        args.expiration,
    )

    print(f"Fetched contracts: {len(raw)}")

    if raw.empty:
        print(
            "No option contracts returned; "
            "snapshot was not saved."
        )
        return

    destination = save_timestamped_snapshot(
        raw,
        normalized_symbol,
        args.expiration,
        captured_at=captured_at,
        directory=args.output_dir,
        file_format=args.format,
    )

    print(f"Snapshot saved: {destination}")

    selected_spot: float | None = None
    selected_time: float | None = None

    spot_source = "unavailable"
    spot_reason = "underlying quote was not evaluated"
    spot_warnings: tuple[str, ...] = ()

    if args.spot is not None:
        selected_spot = args.spot
        spot_source = "manual_override"
        spot_reason = "spot was supplied with --spot"

    else:
        quote_method = getattr(
            provider,
            "get_underlying_quote",
            None,
        )

        if not callable(quote_method):
            spot_reason = (
                "provider does not support underlying quotes"
            )

        else:
            try:
                underlying_quote = quote_method(
                    normalized_symbol
                )

                spot_selection = select_underlying_spot(
                    underlying_quote,
                    now=captured_at,
                )

                selected_spot = spot_selection.spot
                spot_source = spot_selection.source
                spot_reason = spot_selection.reason
                spot_warnings = spot_selection.warnings

            except (
                NotImplementedError,
                TradierAPIError,
                ValueError,
            ) as exc:
                spot_reason = str(exc)

    if args.time is not None:
        selected_time = args.time
        time_source = "manual_override"
        time_reason = "time was supplied with --time"

    else:
        try:
            expiration_result = calculate_time_to_expiration(
                args.expiration,
                now=captured_at,
            )

            selected_time = expiration_result.years_remaining
            time_source = "automatic"
            time_reason = (
                f"{expiration_result.days_remaining:.4f} "
                "calendar days remaining"
            )

        except ValueError as exc:
            time_source = "unavailable"
            time_reason = str(exc)

    print()
    print("Analysis assumptions:")
    print(f"Symbol: {normalized_symbol}")
    print(f"Expiration: {args.expiration}")
    print(
        f"Snapshot time: "
        f"{captured_at.isoformat()}"
    )

    if selected_spot is None:
        print("Underlying price: unavailable")
    else:
        print(
            f"Underlying price: "
            f"{selected_spot:.6f}"
        )

    print(f"Underlying price source: {spot_source}")
    print(f"Underlying price reason: {spot_reason}")

    for warning in spot_warnings:
        print(f"Underlying warning: {warning}")

    if selected_time is None:
        print("Time to expiration: unavailable")
    else:
        print(
            f"Time to expiration: "
            f"{selected_time:.10f} years"
        )

    print(f"Time source: {time_source}")
    print(f"Time reason: {time_reason}")
    print(f"Risk-free rate: {args.rate:.4%}")
    print(
        f"Dividend yield: "
        f"{args.dividend_yield:.4%}"
    )

    if selected_spot is None or selected_time is None:
        print()
        print(
            "Spot-dependent checks will be skipped."
        )
        print(
            "Monotonicity and butterfly checks "
            "will still run."
        )

    print()

    print_analysis(
        raw,
        spot=selected_spot,
        time=selected_time,
        rate=args.rate,
        dividend_yield=args.dividend_yield,
        contract_multiplier=args.contract_multiplier,
        commission_per_contract=(
            args.commission_per_contract
        ),
        fee_per_contract=args.fee_per_contract,
        minimum_net_edge=args.minimum_net_edge,
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
