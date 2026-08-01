from __future__ import annotations

import pandas as pd

from arblens.watchlist import WatchlistScanResult

RANKING_COLUMNS = [
    "rank",
    "symbol",
    "expiration",
    "violation_type",
    "option_type",
    "strikes",
    "midpoint_magnitude",
    "executable_magnitude",
    "gross_edge_per_contract",
    "estimated_transaction_cost",
    "net_edge_per_contract",
    "profitable_after_costs",
    "status",
    "persistence_count",
]


def opportunities_to_frame(result: WatchlistScanResult) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    for symbol_result in result.results:
        if symbol_result.scan is None:
            continue
        for expiration_result in symbol_result.scan.results:
            for item in expiration_result.assessments:
                rows.append(
                    {
                        "symbol": symbol_result.symbol,
                        "expiration": item.expiration,
                        "violation_type": item.violation_type,
                        "option_type": item.option_type,
                        "strikes": ", ".join(f"{strike:g}" for strike in item.strikes),
                        "midpoint_magnitude": item.midpoint_magnitude,
                        "executable_magnitude": item.executable_magnitude,
                        "gross_edge_per_contract": item.gross_edge_per_contract,
                        "estimated_transaction_cost": item.estimated_transaction_cost,
                        "net_edge_per_contract": item.net_edge_per_contract,
                        "profitable_after_costs": item.profitable_after_costs,
                        "status": item.status,
                    }
                )

    if not rows:
        return pd.DataFrame(columns=RANKING_COLUMNS)

    frame = pd.DataFrame(rows)
    keys = ["symbol", "expiration", "violation_type", "option_type", "strikes"]
    persistence = frame.groupby(keys, dropna=False).size().rename("persistence_count")
    frame = frame.merge(persistence, on=keys, how="left")
    frame = frame.sort_values(
        [
            "profitable_after_costs",
            "net_edge_per_contract",
            "executable_magnitude",
            "persistence_count",
        ],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)
    frame.insert(0, "rank", range(1, len(frame) + 1))
    return frame[RANKING_COLUMNS]
