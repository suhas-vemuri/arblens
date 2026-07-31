from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime

import pandas as pd

from arblens.cleaning import clean_quotes
from arblens.detection import run_all_checks, violations_to_frame
from arblens.execution import assess_opportunities, assessments_to_frame
from arblens.io import (
    load_chain,
    save_snapshot_metadata,
    save_timestamped_snapshot,
)
from arblens.market import (
    calculate_time_to_expiration,
    select_underlying_spot,
    summarize_chain_timestamps,
    validate_market_synchronization,
)
from arblens.providers.base import OptionChainProvider
from arblens.providers.tradier import TradierAPIError, TradierProvider

ProviderFactory = Callable[[], OptionChainProvider]


def add_analysis_arguments(
    parser: argparse.ArgumentParser,
    *,
    spot_default: float | None,
    time_default: float | None = 30 / 365,
) -> None:
    parser.add_argument("--spot", type=float, default=spot_default)
    parser.add_argument("--time", type=float, default=time_default)
    parser.add_argument("--rate", type=float, default=0.04)
    parser.add_argument("--dividend-yield", type=float, default=0.0)


def add_execution_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--contract-multiplier", type=int, default=100)
    parser.add_argument("--commission-per-contract", type=float, default=0.65)
    parser.add_argument("--fee-per-contract", type=float, default=0.05)
    parser.add_argument("--minimum-net-edge", type=float, default=0.0)


def add_provider_safety_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--allow-production", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze saved option chains or fetch Tradier snapshots"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze")
    analyze.add_argument("path")
    add_analysis_arguments(analyze, spot_default=100.0)
    add_execution_arguments(analyze)

    expirations = subparsers.add_parser("expirations")
    expirations.add_argument("symbol")
    add_provider_safety_argument(expirations)

    fetch = subparsers.add_parser("fetch")
    fetch.add_argument("symbol")
    fetch.add_argument("--expiration", required=True)
    fetch.add_argument("--output-dir", default="data/snapshots")
    fetch.add_argument("--format", choices=("parquet", "csv"), default="parquet")
    fetch.add_argument(
        "--maximum-sync-gap-seconds",
        type=float,
        default=300.0,
        help="largest allowed time gap between stock and option quotes",
    )
    add_provider_safety_argument(fetch)
    add_analysis_arguments(fetch, spot_default=None, time_default=None)
    add_execution_arguments(fetch)
    return parser


def normalize_arguments(argv: Sequence[str] | None) -> list[str]:
    arguments = list(sys.argv[1:] if argv is None else argv)
    commands = {"analyze", "expirations", "fetch", "-h", "--help"}
    if arguments and arguments[0] not in commands:
        arguments.insert(0, "analyze")
    return arguments


def validate_provider_environment(
    provider: OptionChainProvider,
    *,
    allow_production: bool,
) -> None:
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
    spot: float | None,
    time: float | None,
    rate: float,
    dividend_yield: float,
    contract_multiplier: int,
    commission_per_contract: float,
    fee_per_contract: float,
    minimum_net_edge: float,
) -> None:
    cleaned, issues = clean_quotes(raw)
    error_count = sum(i.severity == "error" for i in issues)
    warning_count = sum(i.severity == "warning" for i in issues)
    average_spread = 0.0 if cleaned.empty else float((cleaned["ask"] - cleaned["bid"]).mean())

    violations = run_all_checks(
        cleaned,
        spot=spot,
        time=time,
        rate=rate,
        dividend_yield=dividend_yield,
    )
    midpoint_count = sum(v.price_basis == "midpoint" for v in violations)
    executable_count = sum(v.price_basis == "bid_ask" for v in violations)

    assessments = assess_opportunities(
        violations,
        contract_multiplier=contract_multiplier,
        commission_per_contract=commission_per_contract,
        fee_per_contract=fee_per_contract,
        minimum_net_edge=minimum_net_edge,
    )
    after_costs = sum(a.profitable_after_costs for a in assessments)
    removed_spread = sum(a.status == "removed_by_spread" for a in assessments)
    removed_costs = sum(a.status == "removed_by_costs" for a in assessments)

    print(f"Raw rows: {len(raw)}")
    print(f"Clean rows: {len(cleaned)}")
    print(f"Quote issues: {len(issues)}")
    print(f"Quote errors: {error_count}")
    print(f"Quote warnings: {warning_count}")
    print(f"Average bid-ask spread: {average_spread:.4f}")
    print(f"Violations: {len(violations)}")
    print(f"Midpoint violations: {midpoint_count}")
    print(f"Executable violations: {executable_count}")
    print(f"Opportunities after costs: {after_costs}")
    print(f"Removed by bid-ask spread: {removed_spread}")
    print(f"Removed by transaction costs: {removed_costs}")
    print()

    violation_table = violations_to_frame(violations)
    print(
        "No violations detected."
        if violation_table.empty
        else violation_table.to_string(index=False)
    )
    print()
    print("Opportunity assessment:")
    assessment_table = assessments_to_frame(assessments)
    print(
        "No opportunities to assess."
        if assessment_table.empty
        else assessment_table.to_string(index=False)
    )


def run_analyze(args: argparse.Namespace) -> None:
    raw = load_chain(args.path)
    print_analysis(
        raw,
        spot=args.spot,
        time=args.time,
        rate=args.rate,
        dividend_yield=args.dividend_yield,
        contract_multiplier=args.contract_multiplier,
        commission_per_contract=args.commission_per_contract,
        fee_per_contract=args.fee_per_contract,
        minimum_net_edge=args.minimum_net_edge,
    )


def run_expirations(
    args: argparse.Namespace,
    provider_factory: ProviderFactory,
) -> None:
    provider = provider_factory()
    validate_provider_environment(provider, allow_production=args.allow_production)
    symbol = args.symbol.strip().upper()
    expirations = provider.get_expirations(symbol)
    print(f"Symbol: {symbol}")
    print(f"Available expirations: {len(expirations)}")
    if expirations:
        print()
        for expiration in expirations:
            print(expiration)
    else:
        print()
        print("No expirations returned.")


def run_fetch(
    args: argparse.Namespace,
    provider_factory: ProviderFactory,
) -> None:
    provider = provider_factory()
    validate_provider_environment(provider, allow_production=args.allow_production)
    symbol = args.symbol.strip().upper()
    available = provider.get_expirations(symbol)
    if args.expiration not in available:
        raise ValueError(f"expiration {args.expiration} is not available for {symbol}")

    captured_at = datetime.now(UTC)
    raw = provider.get_chain(symbol, args.expiration)
    print(f"Fetched contracts: {len(raw)}")
    if raw.empty:
        print("No option contracts returned; snapshot was not saved.")
        return

    destination = save_timestamped_snapshot(
        raw,
        symbol,
        args.expiration,
        captured_at=captured_at,
        directory=args.output_dir,
        file_format=args.format,
    )
    print(f"Snapshot saved: {destination}")

    selected_spot: float | None = args.spot
    selected_time: float | None = args.time
    spot_source = "manual_override" if args.spot is not None else "unavailable"
    spot_reason = (
        "spot was supplied with --spot"
        if args.spot is not None
        else "underlying quote was not evaluated"
    )
    spot_warnings: tuple[str, ...] = ()
    quote = None
    synchronization = None

    quote_method = getattr(provider, "get_underlying_quote", None)
    if selected_spot is None and callable(quote_method):
        try:
            quote = quote_method(symbol)
            selection = select_underlying_spot(quote, now=captured_at)
            selected_spot = selection.spot
            spot_source = selection.source
            spot_reason = selection.reason
            spot_warnings = selection.warnings
        except (NotImplementedError, TradierAPIError, ValueError) as exc:
            spot_reason = str(exc)
    elif selected_spot is None:
        spot_reason = "provider does not support underlying quotes"

    if selected_time is None:
        calculation = calculate_time_to_expiration(args.expiration, now=captured_at)
        selected_time = calculation.years_remaining
        time_source = "automatic"
        time_reason = f"{calculation.days_remaining:.4f} calendar days remaining"
    else:
        time_source = "manual_override"
        time_reason = "time was supplied with --time"

    chain_summary = summarize_chain_timestamps(raw)
    if quote is not None:
        synchronization = validate_market_synchronization(
            quote,
            chain_summary,
            maximum_difference_seconds=args.maximum_sync_gap_seconds,
        )
        if not synchronization.synchronized:
            selected_spot = None
            spot_source = "blocked_by_synchronization"
            spot_reason = synchronization.reason

    metadata = {
        "schema_version": 1,
        "provider_environment": provider.environment,
        "symbol": symbol,
        "expiration": args.expiration,
        "snapshot_path": str(destination),
        "captured_at": captured_at,
        "contract_count": len(raw),
        "underlying_price": selected_spot,
        "underlying_price_source": spot_source,
        "underlying_price_reason": spot_reason,
        "underlying_warnings": list(spot_warnings),
        "time_to_expiration_years": selected_time,
        "time_source": time_source,
        "time_reason": time_reason,
        "risk_free_rate": args.rate,
        "dividend_yield": args.dividend_yield,
        "chain_timestamp_usable": chain_summary.usable,
        "chain_timestamp_reason": chain_summary.reason,
        "chain_representative_timestamp": chain_summary.representative_timestamp,
        "chain_oldest_timestamp": chain_summary.oldest_timestamp,
        "chain_newest_timestamp": chain_summary.newest_timestamp,
        "chain_valid_timestamp_count": chain_summary.valid_count,
        "chain_missing_timestamp_count": chain_summary.missing_count,
        "synchronization_passed": (synchronization.synchronized if synchronization else None),
        "synchronization_reason": (synchronization.reason if synchronization else "not evaluated"),
        "synchronization_gap_seconds": (
            synchronization.time_difference_seconds if synchronization else None
        ),
    }
    metadata_path = save_snapshot_metadata(destination, metadata)
    print(f"Metadata saved: {metadata_path}")

    print()
    print("Analysis assumptions:")
    print(f"Symbol: {symbol}")
    print(f"Expiration: {args.expiration}")
    print(f"Snapshot time: {captured_at.isoformat()}")
    print(
        "Underlying price: unavailable"
        if selected_spot is None
        else f"Underlying price: {selected_spot:.6f}"
    )
    print(f"Underlying price source: {spot_source}")
    print(f"Underlying price reason: {spot_reason}")
    for warning in spot_warnings:
        print(f"Underlying warning: {warning}")
    print(f"Option timestamp status: {chain_summary.reason}")
    if synchronization:
        print(f"Synchronization status: {synchronization.reason}")
    print(f"Time to expiration: {selected_time:.10f} years")
    print(f"Time source: {time_source}")
    print(f"Time reason: {time_reason}")
    print(f"Risk-free rate: {args.rate:.4%}")
    print(f"Dividend yield: {args.dividend_yield:.4%}")

    if selected_spot is None:
        print()
        print("Spot-dependent checks will be skipped.")
        print("Monotonicity and butterfly checks will still run.")

    print()
    print_analysis(
        raw,
        spot=selected_spot,
        time=selected_time if selected_spot is not None else None,
        rate=args.rate,
        dividend_yield=args.dividend_yield,
        contract_multiplier=args.contract_multiplier,
        commission_per_contract=args.commission_per_contract,
        fee_per_contract=args.fee_per_contract,
        minimum_net_edge=args.minimum_net_edge,
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    provider_factory: ProviderFactory = TradierProvider,
) -> int:
    parser = build_parser()
    args = parser.parse_args(normalize_arguments(argv))
    try:
        if args.command == "analyze":
            run_analyze(args)
        elif args.command == "expirations":
            run_expirations(args, provider_factory)
        elif args.command == "fetch":
            run_fetch(args, provider_factory)
    except (FileNotFoundError, TradierAPIError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
