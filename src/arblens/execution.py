from __future__ import annotations

import pandas as pd

from arblens.models import (
    OpportunityAssessment,
    Violation,
)

OPTION_CONTRACT_COUNTS = {
    "price_bound": 1,
    "strike_monotonicity": 2,
    "butterfly_convexity": 4,
    "put_call_parity": 2,
}

ViolationKey = tuple[
    str,
    str,
    str,
    tuple[float, ...],
]


def _violation_key(
    violation: Violation,
) -> ViolationKey:
    """Create a stable identifier for matching two violations."""
    return (
        violation.violation_type,
        violation.option_type,
        violation.expiration,
        violation.strikes,
    )


def _validate_inputs(
    *,
    contract_multiplier: int,
    commission_per_contract: float,
    fee_per_contract: float,
    minimum_net_edge: float,
) -> None:
    if contract_multiplier <= 0:
        raise ValueError("contract_multiplier must be greater than zero")

    if commission_per_contract < 0:
        raise ValueError("commission_per_contract must be non-negative")

    if fee_per_contract < 0:
        raise ValueError("fee_per_contract must be non-negative")

    if minimum_net_edge < 0:
        raise ValueError("minimum_net_edge must be non-negative")


def assess_opportunities(
    violations: list[Violation],
    *,
    contract_multiplier: int = 100,
    commission_per_contract: float = 0.65,
    fee_per_contract: float = 0.05,
    minimum_net_edge: float = 0.0,
) -> list[OpportunityAssessment]:
    """Evaluate whether anomalies survive spreads and costs."""
    _validate_inputs(
        contract_multiplier=contract_multiplier,
        commission_per_contract=(commission_per_contract),
        fee_per_contract=fee_per_contract,
        minimum_net_edge=minimum_net_edge,
    )

    midpoint_violations = {
        _violation_key(violation): violation
        for violation in violations
        if violation.price_basis == "midpoint"
    }

    executable_violations = {
        _violation_key(violation): violation
        for violation in violations
        if violation.price_basis == "bid_ask"
    }

    all_keys = sorted(set(midpoint_violations) | set(executable_violations))

    assessments: list[OpportunityAssessment] = []

    for key in all_keys:
        midpoint = midpoint_violations.get(key)
        executable = executable_violations.get(key)

        violation_type = key[0]
        option_contracts = OPTION_CONTRACT_COUNTS.get(
            violation_type,
            1,
        )

        midpoint_magnitude = midpoint.magnitude if midpoint is not None else 0.0

        if executable is None:
            assessments.append(
                OpportunityAssessment(
                    violation_type=key[0],
                    option_type=key[1],
                    expiration=key[2],
                    strikes=key[3],
                    midpoint_magnitude=(midpoint_magnitude),
                    executable_magnitude=0.0,
                    survives_bid_ask=False,
                    option_contracts=option_contracts,
                    contract_multiplier=(contract_multiplier),
                    gross_edge_per_contract=0.0,
                    estimated_transaction_cost=0.0,
                    net_edge_per_contract=0.0,
                    profitable_after_costs=False,
                    status="removed_by_spread",
                    details=("Midpoint anomaly did not survive displayed bid/ask prices."),
                )
            )
            continue

        executable_magnitude = executable.magnitude

        gross_edge_per_contract = executable_magnitude * contract_multiplier

        estimated_transaction_cost = option_contracts * (commission_per_contract + fee_per_contract)

        net_edge_per_contract = gross_edge_per_contract - estimated_transaction_cost

        profitable_after_costs = net_edge_per_contract > minimum_net_edge

        if profitable_after_costs:
            status = "passes_cost_filter"
            details = (
                "Displayed bid/ask edge remains above "
                "the required net-edge threshold after "
                "estimated option contract costs."
            )
        else:
            status = "removed_by_costs"
            details = (
                "Displayed bid/ask edge was removed by "
                "estimated option contract costs or did "
                "not exceed the required net-edge threshold."
            )

        assessments.append(
            OpportunityAssessment(
                violation_type=key[0],
                option_type=key[1],
                expiration=key[2],
                strikes=key[3],
                midpoint_magnitude=midpoint_magnitude,
                executable_magnitude=(executable_magnitude),
                survives_bid_ask=True,
                option_contracts=option_contracts,
                contract_multiplier=contract_multiplier,
                gross_edge_per_contract=(gross_edge_per_contract),
                estimated_transaction_cost=(estimated_transaction_cost),
                net_edge_per_contract=(net_edge_per_contract),
                profitable_after_costs=(profitable_after_costs),
                status=status,
                details=details,
            )
        )

    return assessments


def assessments_to_frame(
    assessments: list[OpportunityAssessment],
) -> pd.DataFrame:
    """Convert opportunity assessments into a report table."""
    columns = [
        "violation_type",
        "option_type",
        "expiration",
        "strikes",
        "midpoint_magnitude",
        "executable_magnitude",
        "survives_bid_ask",
        "option_contracts",
        "gross_edge_per_contract",
        "estimated_transaction_cost",
        "net_edge_per_contract",
        "profitable_after_costs",
        "status",
        "details",
    ]

    if not assessments:
        return pd.DataFrame(columns=columns)

    return pd.DataFrame(
        [
            {
                "violation_type": item.violation_type,
                "option_type": item.option_type,
                "expiration": item.expiration,
                "strikes": ", ".join(f"{strike:g}" for strike in item.strikes),
                "midpoint_magnitude": (item.midpoint_magnitude),
                "executable_magnitude": (item.executable_magnitude),
                "survives_bid_ask": (item.survives_bid_ask),
                "option_contracts": (item.option_contracts),
                "gross_edge_per_contract": (item.gross_edge_per_contract),
                "estimated_transaction_cost": (item.estimated_transaction_cost),
                "net_edge_per_contract": (item.net_edge_per_contract),
                "profitable_after_costs": (item.profitable_after_costs),
                "status": item.status,
                "details": item.details,
            }
            for item in assessments
        ],
        columns=columns,
    )
