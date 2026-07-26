from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_chain(path: str | Path) -> pd.DataFrame:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)
    if source.suffix.lower() == ".csv":
        return pd.read_csv(source)
    if source.suffix.lower() in {".parquet", ".pq"}:
        return pd.read_parquet(source)
    raise ValueError("supported formats are CSV and Parquet")


def save_snapshot(frame: pd.DataFrame, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.suffix.lower() == ".csv":
        frame.to_csv(destination, index=False)
    elif destination.suffix.lower() in {".parquet", ".pq"}:
        frame.to_parquet(destination, index=False)
    else:
        raise ValueError("supported formats are CSV and Parquet")
    return destination
