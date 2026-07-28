from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from string import ascii_letters, digits

import pandas as pd

ALLOWED_SYMBOL_CHARACTERS = set(ascii_letters + digits + "._-")


def load_chain(path: str | Path) -> pd.DataFrame:
    """Load an option chain from a CSV or Parquet file."""
    source = Path(path)

    if not source.exists():
        raise FileNotFoundError(source)

    if source.suffix.lower() == ".csv":
        return pd.read_csv(source)

    if source.suffix.lower() in {".parquet", ".pq"}:
        return pd.read_parquet(source)

    raise ValueError("supported formats are CSV and Parquet")


def save_snapshot(
    frame: pd.DataFrame,
    path: str | Path,
) -> Path:
    """Save an option-chain snapshot to CSV or Parquet."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.suffix.lower() == ".csv":
        frame.to_csv(destination, index=False)
    elif destination.suffix.lower() in {".parquet", ".pq"}:
        frame.to_parquet(destination, index=False)
    else:
        raise ValueError("supported formats are CSV and Parquet")

    return destination


def build_snapshot_path(
    symbol: str,
    expiration: str,
    *,
    captured_at: datetime | None = None,
    directory: str | Path = "data/snapshots",
    file_format: str = "parquet",
) -> Path:
    """Build a predictable, timestamped snapshot path."""
    normalized_symbol = symbol.strip().upper()

    if not normalized_symbol:
        raise ValueError("symbol must not be empty")

    if any(character not in ALLOWED_SYMBOL_CHARACTERS for character in normalized_symbol):
        raise ValueError("symbol contains unsupported filename characters")

    try:
        normalized_expiration = date.fromisoformat(expiration.strip()).isoformat()
    except ValueError as exc:
        raise ValueError("expiration must be an ISO date such as 2026-08-21") from exc

    normalized_format = file_format.strip().lower().lstrip(".")

    if normalized_format == "pq":
        normalized_format = "parquet"

    if normalized_format not in {"csv", "parquet"}:
        raise ValueError("file format must be CSV or Parquet")

    timestamp = captured_at or datetime.now(UTC)

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    else:
        timestamp = timestamp.astimezone(UTC)

    extension = ".csv" if normalized_format == "csv" else ".parquet"

    filename = f"{normalized_symbol}_{normalized_expiration}_{timestamp:%Y%m%dT%H%M%SZ}{extension}"

    return Path(directory) / filename


def save_timestamped_snapshot(
    frame: pd.DataFrame,
    symbol: str,
    expiration: str,
    *,
    captured_at: datetime | None = None,
    directory: str | Path = "data/snapshots",
    file_format: str = "parquet",
) -> Path:
    """Save a chain using a symbol, expiration, and UTC timestamp."""
    destination = build_snapshot_path(
        symbol,
        expiration,
        captured_at=captured_at,
        directory=directory,
        file_format=file_format,
    )

    return save_snapshot(frame, destination)
