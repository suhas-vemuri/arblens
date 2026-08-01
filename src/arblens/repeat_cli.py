from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from arblens.liquidity import LiquidityFilter
from arblens.providers.tradier import TradierAPIError, TradierProvider
from arblens.ranking import opportunities_to_frame
from arblens.reporting import save_frame_csv, watchlist_result_to_frame
from arblens.watchlist import load_watchlist, scan_watchlist


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run repeated timestamped watchlist scans")
    parser.add_argument("watchlist")
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--interval-seconds", type=float, default=60.0)
    parser.add_argument("--maximum-expirations", type=int, default=1)
    parser.add_argument("--minimum-volume", type=int, default=1)
    parser.add_argument("--minimum-open-interest", type=int, default=1)
    parser.add_argument("--maximum-relative-spread", type=float, default=0.25)
    parser.add_argument("--maximum-sync-gap-seconds", type=float, default=300.0)
    parser.add_argument("--output-dir", type=Path, default=Path("data/history"))
    parser.add_argument("--allow-production", action="store_true")
    return parser


def run(args: argparse.Namespace) -> int:
    if args.runs <= 0:
        raise ValueError("runs must be greater than zero")
    if args.interval_seconds < 0:
        raise ValueError("interval_seconds must be non-negative")

    provider = TradierProvider()
    if provider.environment == "production" and not args.allow_production:
        raise ValueError(
            "Tradier production access is blocked by default; rerun with --allow-production"
        )

    symbols = load_watchlist(args.watchlist)
    rules = LiquidityFilter(
        minimum_volume=args.minimum_volume,
        minimum_open_interest=args.minimum_open_interest,
        maximum_relative_spread=args.maximum_relative_spread,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summaries: list[pd.DataFrame] = []
    rankings: list[pd.DataFrame] = []

    for run_number in range(1, args.runs + 1):
        captured_at = datetime.now(UTC)
        result = scan_watchlist(
            provider,
            symbols,
            maximum_expirations=args.maximum_expirations,
            captured_at=captured_at,
            maximum_sync_gap_seconds=args.maximum_sync_gap_seconds,
            liquidity_filter=rules,
        )
        summary = watchlist_result_to_frame(result)
        ranking = opportunities_to_frame(result)
        summary.insert(0, "run_number", run_number)
        summary.insert(1, "captured_at", captured_at.isoformat())
        ranking.insert(0, "run_number", run_number)
        ranking.insert(1, "captured_at", captured_at.isoformat())

        timestamp = captured_at.strftime("%Y%m%dT%H%M%SZ")
        save_frame_csv(summary, args.output_dir / f"scan_{run_number:03d}_{timestamp}.csv")
        save_frame_csv(ranking, args.output_dir / f"ranked_{run_number:03d}_{timestamp}.csv")
        summaries.append(summary)
        rankings.append(ranking)
        print(f"Completed run {run_number}/{args.runs}")

        if run_number < args.runs and args.interval_seconds:
            time.sleep(args.interval_seconds)

    save_frame_csv(pd.concat(summaries, ignore_index=True), args.output_dir / "combined_scans.csv")
    save_frame_csv(
        pd.concat(rankings, ignore_index=True), args.output_dir / "combined_rankings.csv"
    )
    print(f"History saved: {args.output_dir}")
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
