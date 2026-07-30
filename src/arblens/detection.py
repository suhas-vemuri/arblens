from __future__ import annotations

import math
from collections.abc import Iterable

import pandas as pd

from arblens.models import Violation
from arblens.pricing import european_price_bounds


def _group(frame: pd.DataFrame) -> Iterable[tuple[tuple[str, str], pd.DataFrame]]:
    return frame.groupby(["expiration", "option_type"], sort=True)


def detect_price_bound_violations(
    frame: pd.DataFrame,
    *,
    spot: float,
    time: float,
    rate: float,
    dividend_yield: float = 0.0,
    tolerance: float = 1e-8,
) -> list[Violation]:
    violations: list[Violation] = []
    for row in frame.itertuples():
        lower, upper = european_price_bounds(
            spot=spot,
            strike=float(row.strike),
            time=time,
            rate=rate,
            option_type=row.option_type,
            dividend_yield=dividend_yield,
        )
        if row.mid < lower - tolerance:
            violations.append(
                Violation(
                    "price_bound",
                    row.option_type,
                    str(row.expiration),
                    (float(row.strike),),
                    lower - float(row.mid),
                    "midpoint",
                    f"midpoint {row.mid:.4f} is below lower bound {lower:.4f}",
                )
            )
        elif row.mid > upper + tolerance:
            violations.append(
                Violation(
                    "price_bound",
                    row.option_type,
                    str(row.expiration),
                    (float(row.strike),),
                    float(row.mid) - upper,
                    "midpoint",
                    f"midpoint {row.mid:.4f} is above upper bound {upper:.4f}",
                )
            )
    return violations


def detect_executable_price_bound_violations(
    frame: pd.DataFrame,
    *,
    spot: float,
    time: float,
    rate: float,
    dividend_yield: float = 0.0,
    tolerance: float = 1e-8,
) -> list[Violation]:
    """Detect price-bound violations using tradable bid and ask prices."""
    violations: list[Violation] = []

    for row in frame.itertuples():
        lower, upper = european_price_bounds(
            spot=spot,
            strike=float(row.strike),
            time=time,
            rate=rate,
            option_type=row.option_type,
            dividend_yield=dividend_yield,
        )

        ask = float(row.ask)
        bid = float(row.bid)

        if ask < lower - tolerance:
            violations.append(
                Violation(
                    "price_bound",
                    row.option_type,
                    str(row.expiration),
                    (float(row.strike),),
                    lower - ask,
                    "bid_ask",
                    (f"option ask {ask:.4f} is below lower bound {lower:.4f}"),
                )
            )
        elif bid > upper + tolerance:
            violations.append(
                Violation(
                    "price_bound",
                    row.option_type,
                    str(row.expiration),
                    (float(row.strike),),
                    bid - upper,
                    "bid_ask",
                    (f"option bid {bid:.4f} is above upper bound {upper:.4f}"),
                )
            )

    return violations


def detect_monotonicity_violations(
    frame: pd.DataFrame,
    *,
    tolerance: float = 1e-8,
) -> list[Violation]:
    violations: list[Violation] = []

    for (expiration, option_type), group in _group(frame):
        ordered = group.sort_values("strike")
        rows = list(ordered.itertuples())
        for left, right in zip(rows, rows[1:], strict=False):
            if option_type == "call" and right.mid > left.mid + tolerance:
                violations.append(
                    Violation(
                        "strike_monotonicity",
                        option_type,
                        str(expiration),
                        (float(left.strike), float(right.strike)),
                        float(right.mid - left.mid),
                        "midpoint",
                        "higher-strike call midpoint exceeds lower-strike call midpoint",
                    )
                )
            elif option_type == "put" and right.mid + tolerance < left.mid:
                violations.append(
                    Violation(
                        "strike_monotonicity",
                        option_type,
                        str(expiration),
                        (float(left.strike), float(right.strike)),
                        float(left.mid - right.mid),
                        "midpoint",
                        "higher-strike put midpoint is below lower-strike put midpoint",
                    )
                )
    return violations


def detect_executable_monotonicity_violations(
    frame: pd.DataFrame,
    *,
    tolerance: float = 1e-8,
) -> list[Violation]:
    """Detect vertical-spread contradictions using executable top-of-book prices."""
    violations: list[Violation] = []

    for (expiration, option_type), group in _group(frame):
        rows = list(group.sort_values("strike").itertuples())
        for left, right in zip(rows, rows[1:], strict=False):
            if option_type == "call":
                # Buy better lower-strike call at ask, short worse higher-strike call at bid.
                credit = float(right.bid - left.ask)
                if credit > tolerance:
                    violations.append(
                        Violation(
                            "strike_monotonicity",
                            option_type,
                            str(expiration),
                            (float(left.strike), float(right.strike)),
                            credit,
                            "bid_ask",
                            (
                                f"buy lower strike at {left.ask:.4f}, "
                                f"sell higher strike at {right.bid:.4f}"
                            ),
                        )
                    )
            else:
                # Buy better higher-strike put at ask, short worse lower-strike put at bid.
                credit = float(left.bid - right.ask)
                if credit > tolerance:
                    violations.append(
                        Violation(
                            "strike_monotonicity",
                            option_type,
                            str(expiration),
                            (float(left.strike), float(right.strike)),
                            credit,
                            "bid_ask",
                            (
                                f"buy higher strike at {right.ask:.4f}, "
                                f"sell lower strike at {left.bid:.4f}"
                            ),
                        )
                    )
    return violations


def detect_butterfly_violations(
    frame: pd.DataFrame,
    *,
    tolerance: float = 1e-8,
) -> list[Violation]:
    violations: list[Violation] = []

    for (expiration, option_type), group in _group(frame):
        rows = list(group.sort_values("strike").itertuples())
        for left, middle, right in zip(rows, rows[1:], rows[2:], strict=False):
            left_gap = float(middle.strike - left.strike)
            right_gap = float(right.strike - middle.strike)
            if not math.isclose(left_gap, right_gap, rel_tol=1e-9, abs_tol=1e-9):
                continue
            curvature = float(left.mid - 2.0 * middle.mid + right.mid)
            if curvature < -tolerance:
                violations.append(
                    Violation(
                        "butterfly_convexity",
                        option_type,
                        str(expiration),
                        (float(left.strike), float(middle.strike), float(right.strike)),
                        -curvature,
                        "midpoint",
                        f"second difference is {curvature:.4f}; expected non-negative",
                    )
                )
    return violations


def detect_executable_butterfly_violations(
    frame: pd.DataFrame,
    *,
    tolerance: float = 1e-8,
) -> list[Violation]:
    violations: list[Violation] = []

    for (expiration, option_type), group in _group(frame):
        rows = list(group.sort_values("strike").itertuples())
        for left, middle, right in zip(rows, rows[1:], rows[2:], strict=False):
            if not math.isclose(
                float(middle.strike - left.strike),
                float(right.strike - middle.strike),
                rel_tol=1e-9,
                abs_tol=1e-9,
            ):
                continue
            # Buy wings at asks and sell two middle contracts at the bid.
            credit = float(2.0 * middle.bid - left.ask - right.ask)
            if credit > tolerance:
                violations.append(
                    Violation(
                        "butterfly_convexity",
                        option_type,
                        str(expiration),
                        (float(left.strike), float(middle.strike), float(right.strike)),
                        credit,
                        "bid_ask",
                        "long wings and short two middle options produce an upfront credit",
                    )
                )
    return violations


def detect_put_call_parity_violations(
    frame: pd.DataFrame,
    *,
    spot: float,
    time: float,
    rate: float,
    dividend_yield: float = 0.0,
    tolerance: float = 0.05,
) -> list[Violation]:
    violations: list[Violation] = []
    calls = frame[frame["option_type"] == "call"]
    puts = frame[frame["option_type"] == "put"]
    merged = calls.merge(
        puts,
        on=["symbol", "expiration", "strike"],
        suffixes=("_call", "_put"),
    )

    for row in merged.itertuples():
        theoretical_difference = spot * math.exp(-dividend_yield * time) - float(
            row.strike
        ) * math.exp(-rate * time)
        observed_difference = float(row.mid_call - row.mid_put)
        error = observed_difference - theoretical_difference
        if abs(error) > tolerance:
            violations.append(
                Violation(
                    "put_call_parity",
                    "call_put_pair",
                    str(row.expiration),
                    (float(row.strike),),
                    abs(error),
                    "midpoint",
                    f"C-P differs from discounted spot-minus-strike by {error:.4f}",
                )
            )

        lower_executable = float(row.bid_call - row.ask_put)
        upper_executable = float(row.ask_call - row.bid_put)
        if theoretical_difference < lower_executable - tolerance:
            violations.append(
                Violation(
                    "put_call_parity",
                    "call_put_pair",
                    str(row.expiration),
                    (float(row.strike),),
                    lower_executable - theoretical_difference,
                    "bid_ask",
                    "call bid minus put ask is above the parity value",
                )
            )
        elif theoretical_difference > upper_executable + tolerance:
            violations.append(
                Violation(
                    "put_call_parity",
                    "call_put_pair",
                    str(row.expiration),
                    (float(row.strike),),
                    theoretical_difference - upper_executable,
                    "bid_ask",
                    "call ask minus put bid is below the parity value",
                )
            )

    return violations

def run_all_checks(
    frame: pd.DataFrame,
    *,
    spot: float | None,
    time: float | None,
    rate: float,
    dividend_yield: float = 0.0,
) -> list[Violation]:
    """Run every check that has the required market assumptions.

    Monotonicity and butterfly checks depend only on the option chain.

    Price-bound and put-call-parity checks also require a trustworthy
    underlying price and a valid time to expiration.
    """

    violations = [
        *detect_monotonicity_violations(frame),
        *detect_executable_monotonicity_violations(frame),
        *detect_butterfly_violations(frame),
        *detect_executable_butterfly_violations(frame),
    ]

    if spot is None or time is None:
        return violations

    return [
        *detect_price_bound_violations(
            frame,
            spot=spot,
            time=time,
            rate=rate,
            dividend_yield=dividend_yield,
        ),
        *detect_executable_price_bound_violations(
            frame,
            spot=spot,
            time=time,
            rate=rate,
            dividend_yield=dividend_yield,
        ),
        *violations,
        *detect_put_call_parity_violations(
            frame,
            spot=spot,
            time=time,
            rate=rate,
            dividend_yield=dividend_yield,
        ),
    ]
def violations_to_frame(violations: list[Violation]) -> pd.DataFrame:
    if not violations:
        return pd.DataFrame(
            columns=[
                "violation_type",
                "option_type",
                "expiration",
                "strikes",
                "magnitude",
                "price_basis",
                "details",
            ]
        )
    return pd.DataFrame(
        [
            {
                "violation_type": item.violation_type,
                "option_type": item.option_type,
                "expiration": item.expiration,
                "strikes": ", ".join(f"{strike:g}" for strike in item.strikes),
                "magnitude": item.magnitude,
                "price_basis": item.price_basis,
                "details": item.details,
            }
            for item in violations
        ]
    )
