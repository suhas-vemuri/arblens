from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from arblens.liquidity import LiquidityFilter
from arblens.providers.tradier import TradierAPIError, TradierProvider
from arblens.ranking import opportunities_to_frame
from arblens.reporting import save_frame_csv, save_watchlist_report, watchlist_result_to_frame
from arblens.watchlist import load_watchlist, scan_watchlist


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan multiple symbols and expirations from a watchlist"
    )
    parser.add_argument("watchlist")
    parser.add_argument("--maximum-expirations", type=int, default=2)
    parser.add_argument("--maximum-sync-gap-seconds", type=float, default=300.0)
    parser.add_argument("--minimum-volume", type=int, default=1)
    parser.add_argument("--minimum-open-interest", type=int, default=1)
    parser.add_argument("--maximum-relative-spread", type=float, default=0.25)
    parser.add_argument("--rate", type=float, default=0.04)
    parser.add_argument("--dividend-yield", type=float, default=0.0)
    parser.add_argument("--contract-multiplier", type=int, default=100)
    parser.add_argument("--commission-per-contract", type=float, default=0.65)
    parser.add_argument("--fee-per-contract", type=float, default=0.05)
    parser.add_argument("--minimum-net-edge", type=float, default=0.0)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--ranking-output", type=Path)
    parser.add_argument("--allow-production", action="store_true")
    return parser


def default_output_path(captured_at: datetime) -> Path:
    return Path("data", "reports", f"watchlist_scan_{captured_at:%Y%m%dT%H%M%SZ}.csv")


def default_ranking_path(captured_at: datetime) -> Path:
    return Path("data", "reports", f"watchlist_ranked_{captured_at:%Y%m%dT%H%M%SZ}.csv")


def run(args: argparse.Namespace) -> int:
    provider = TradierProvider()
    if provider.environment == "production" and not args.allow_production:
        raise ValueError(
            "Tradier production access is blocked by default; rerun with --allow-production"
        )

    captured_at = datetime.now(UTC)
    result = scan_watchlist(
        provider,
        load_watchlist(args.watchlist),
        maximum_expirations=args.maximum_expirations,
        captured_at=captured_at,
        rate=args.rate,
        dividend_yield=args.dividend_yield,
        maximum_sync_gap_seconds=args.maximum_sync_gap_seconds,
        liquidity_filter=LiquidityFilter(
            minimum_volume=args.minimum_volume,
            minimum_open_interest=args.minimum_open_interest,
            maximum_relative_spread=args.maximum_relative_spread,
        ),
        contract_multiplier=args.contract_multiplier,
        commission_per_contract=args.commission_per_contract,
        fee_per_contract=args.fee_per_contract,
        minimum_net_edge=args.minimum_net_edge,
    )

    summary = watchlist_result_to_frame(result)
    ranking = opportunities_to_frame(result)
    print(f"Provider environment: {provider.environment}")
    print(f"Requested symbols: {len(result.requested_symbols)}")
    print(f"Completed symbols: {result.completed_symbols}")
    print(f"Failed symbols: {result.failed_symbols}")
    print()

    columns = [
        "symbol",
        "expiration",
        "status",
        "raw_rows",
        "liquid_rows",
        "liquidity_removed_rows",
        "executable_violations",
        "opportunities_after_costs",
        "error",
    ]
    print(
        "No watchlist rows were produced."
        if summary.empty
        else summary[columns].to_string(index=False)
    )

    summary_path = args.output or default_output_path(captured_at)
    ranking_path = args.ranking_output or default_ranking_path(captured_at)
    save_watchlist_report(result, summary_path)
    save_frame_csv(ranking, ranking_path)
    print()
    print(f"Combined report saved: {summary_path}")
    print(f"Ranked report saved: {ranking_path}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (TradierAPIError, ValueError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
