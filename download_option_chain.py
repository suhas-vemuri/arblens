"""Download Tradier option chains and save them for ArbLens."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tradier_client import TradierClient, TradierError


SNAPSHOT_DIRECTORY = Path("data") / "snapshots"


def create_timestamp() -> str:
    """Return the current UTC time in a Windows-safe filename format."""

    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def choose_expiration(
    expirations: list[str],
    requested_expiration: str | None,
) -> str:
    """Select the requested expiration or the nearest available date."""

    if not expirations:
        raise ValueError("Tradier returned no option expirations.")

    if requested_expiration is None:
        return expirations[0]

    if requested_expiration not in expirations:
        available_preview = ", ".join(expirations[:10])

        raise ValueError(
            f"Expiration {requested_expiration} is unavailable. "
            f"First available dates: {available_preview}"
        )

    return requested_expiration


def save_snapshot(
    symbol: str,
    expiration: str,
    contracts: list[dict[str, Any]],
) -> Path:
    """Save a complete option chain as a timestamped JSON file."""

    SNAPSHOT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    downloaded_at = datetime.now(timezone.utc)
    timestamp = downloaded_at.strftime("%Y%m%dT%H%M%SZ")

    filename = (
        f"{symbol.upper()}_{expiration}_{timestamp}.json"
    )

    output_path = SNAPSHOT_DIRECTORY / filename

    snapshot = {
        "schema_version": 1,
        "source": "tradier",
        "underlying": symbol.upper(),
        "expiration": expiration,
        "downloaded_at_utc": downloaded_at.isoformat(),
        "contract_count": len(contracts),
        "contracts": contracts,
    }

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            snapshot,
            file,
            indent=2,
            sort_keys=True,
            default=str,
        )

    return output_path


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line arguments for the downloader."""

    parser = argparse.ArgumentParser(
        description=(
            "Download one Tradier option chain and save it "
            "as an ArbLens JSON snapshot."
        )
    )

    parser.add_argument(
        "--symbol",
        default="AAPL",
        help="Underlying symbol. Default: AAPL",
    )

    parser.add_argument(
        "--expiration",
        default=None,
        help=(
            "Expiration in YYYY-MM-DD format. "
            "The nearest expiration is used when omitted."
        ),
    )

    parser.add_argument(
        "--no-greeks",
        action="store_true",
        help="Download the option chain without Greeks.",
    )

    return parser


def main() -> None:
    """Download and save one option-chain snapshot."""

    arguments = build_parser().parse_args()

    symbol = arguments.symbol.strip().upper()

    if not symbol:
        print("Download failed: a symbol is required.")
        raise SystemExit(1)

    try:
        client = TradierClient()

        print(f"Retrieving available expirations for {symbol}...")

        expirations = client.get_option_expirations(symbol)

        expiration = choose_expiration(
            expirations=expirations,
            requested_expiration=arguments.expiration,
        )

        print(
            f"Downloading {symbol} option chain "
            f"for {expiration}..."
        )

        contracts = client.get_option_chain(
            symbol=symbol,
            expiration=expiration,
            include_greeks=not arguments.no_greeks,
        )

        if not contracts:
            raise ValueError(
                "Tradier returned an empty option chain."
            )

        output_path = save_snapshot(
            symbol=symbol,
            expiration=expiration,
            contracts=contracts,
        )

        print("\nDownload successful.")
        print("Symbol:", symbol)
        print("Expiration:", expiration)
        print("Contracts saved:", len(contracts))
        print("Snapshot file:", output_path)

    except (TradierError, ValueError) as error:
        print("\nDownload failed:")
        print(error)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()