from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

import numpy as np
import pandas as pd

MAX_WATCHLIST_SYMBOLS = 10


@dataclass(frozen=True, slots=True)
class DashboardMetrics:
    symbols_scanned: int
    expirations_scanned: int
    raw_contracts: int
    clean_contracts: int
    liquid_contracts: int
    violations_found: int
    executable_violations: int
    opportunities_after_costs: int
    synchronized_expirations: int


def parse_symbols(value: str, *, maximum: int = MAX_WATCHLIST_SYMBOLS) -> list[str]:
    normalized = value.replace("\n", ",").replace(" ", ",")
    symbols: list[str] = []
    for item in normalized.split(","):
        symbol = item.strip().upper()
        if not symbol:
            continue
        if not all(character.isalnum() or character in ".-_" for character in symbol):
            raise ValueError(f"unsupported symbol: {symbol}")
        if symbol not in symbols:
            symbols.append(symbol)
    if not symbols:
        raise ValueError("enter at least one ticker symbol")
    if len(symbols) > maximum:
        raise ValueError(f"enter no more than {maximum} ticker symbols")
    return symbols


def calculate_metrics(summary: pd.DataFrame) -> DashboardMetrics:
    if summary.empty:
        return DashboardMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0)
    synchronized = summary.get(
        "synchronization_passed", pd.Series(False, index=summary.index)
    ).fillna(False)
    return DashboardMetrics(
        symbols_scanned=int(summary["symbol"].nunique()),
        expirations_scanned=int(len(summary)),
        raw_contracts=int(summary.get("raw_rows", pd.Series(dtype=float)).fillna(0).sum()),
        clean_contracts=int(summary.get("clean_rows", pd.Series(dtype=float)).fillna(0).sum()),
        liquid_contracts=int(summary.get("liquid_rows", pd.Series(dtype=float)).fillna(0).sum()),
        violations_found=int(summary.get("violations", pd.Series(dtype=float)).fillna(0).sum()),
        executable_violations=int(
            summary.get("executable_violations", pd.Series(dtype=float)).fillna(0).sum()
        ),
        opportunities_after_costs=int(
            summary.get("opportunities_after_costs", pd.Series(dtype=float)).fillna(0).sum()
        ),
        synchronized_expirations=int(synchronized.sum()),
    )


def build_elimination_frame(summary: pd.DataFrame) -> pd.DataFrame:
    metrics = calculate_metrics(summary)

    return pd.DataFrame(
        [
            {
                "stage": "Raw contracts",
                "remaining": metrics.raw_contracts,
            },
            {
                "stage": "Clean quotes",
                "remaining": metrics.clean_contracts,
            },
            {
                "stage": "Liquid contracts",
                "remaining": metrics.liquid_contracts,
            },
            {
                "stage": "Synchronized expirations",
                "remaining": metrics.synchronized_expirations,
            },
            {
                "stage": "Executable violations",
                "remaining": metrics.executable_violations,
            },
            {
                "stage": "After costs",
                "remaining": metrics.opportunities_after_costs,
            },
        ]
    )


def readable_check_name(value: str) -> str:
    return {
        "put_call_parity": "Put-call parity",
        "strike_monotonicity": "Strike monotonicity",
        "butterfly_convexity": "Butterfly convexity",
        "price_bound": "European price bounds",
    }.get(value, value.replace("_", " ").title())


def _rng(symbols: list[str]) -> np.random.Generator:
    seed = int.from_bytes(sha256(",".join(symbols).encode()).digest()[:8], "big") % (2**32)
    return np.random.default_rng(seed)


def demo_summary(symbols: list[str], max_expirations: int) -> pd.DataFrame:
    rng = _rng(symbols)
    rows = []
    base = pd.Timestamp("2026-08-01")
    for symbol in symbols:
        for number in range(1, max_expirations + 1):
            raw = int(rng.integers(110, 420))
            clean = int(raw * rng.uniform(0.86, 0.97))
            liquid = int(clean * rng.uniform(0.2, 0.48))
            violations = int(rng.integers(0, 18))
            executable = int(rng.integers(0, min(violations, 4) + 1))
            after = int(rng.integers(0, executable + 1))
            rows.append(
                {
                    "symbol": symbol,
                    "expiration": (base + pd.Timedelta(days=7 * number)).date().isoformat(),
                    "status": "completed_full",
                    "raw_rows": raw,
                    "clean_rows": clean,
                    "liquid_rows": liquid,
                    "liquidity_removed_rows": clean - liquid,
                    "quote_issues": raw - clean,
                    "quote_errors": max(raw - clean - 2, 0),
                    "quote_warnings": 2,
                    "spot_used": float(rng.uniform(90, 600)),
                    "time_to_expiration_years": 7 * number / 365,
                    "synchronization_passed": True,
                    "synchronization_reason": "quotes are from the same time window",
                    "spot_checks_skipped": False,
                    "violations": violations,
                    "midpoint_violations": violations,
                    "executable_violations": executable,
                    "opportunities_after_costs": after,
                    "error": None,
                }
            )
    return pd.DataFrame(rows)


def demo_rankings(symbols: list[str]) -> pd.DataFrame:
    rng = _rng(symbols + ["rankings"])
    checks = ["put_call_parity", "strike_monotonicity", "butterfly_convexity", "price_bound"]
    rows = []
    for symbol in symbols:
        for _ in range(int(rng.integers(1, 3))):
            edge = round(float(rng.uniform(0.02, 0.85)), 3)
            cost = round(float(rng.uniform(0.7, 2.8)), 2)
            net = round(edge * 100 - cost, 2)
            strike = round(float(rng.uniform(80, 500)) / 5) * 5
            rows.append(
                {
                    "rank": 0,
                    "symbol": symbol,
                    "violation_type": str(rng.choice(checks)),
                    "expiration": "2026-08-21",
                    "strikes": f"{strike:g}",
                    "executable_magnitude": edge,
                    "estimated_transaction_cost": cost,
                    "net_edge_per_contract": net,
                    "persistence_count": int(rng.integers(1, 5)),
                    "status": "passes_cost_filter" if net > 0 else "removed_by_costs",
                }
            )
    frame = (
        pd.DataFrame(rows)
        .sort_values("net_edge_per_contract", ascending=False)
        .reset_index(drop=True)
    )
    frame["rank"] = range(1, len(frame) + 1)
    return frame
