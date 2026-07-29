import pytest

from arblens.execution import (
    assess_opportunities,
    assessments_to_frame,
)
from arblens.models import Violation


def make_violation(
    price_basis: str,
    magnitude: float,
    *,
    violation_type: str = "strike_monotonicity",
    strikes: tuple[float, ...] = (100.0, 105.0),
) -> Violation:
    return Violation(
        violation_type=violation_type,
        option_type="call",
        expiration="2026-12-18",
        strikes=strikes,
        magnitude=magnitude,
        price_basis=price_basis,
        details="test violation",
    )


def test_midpoint_anomaly_removed_by_spread() -> None:
    assessments = assess_opportunities(
        [
            make_violation(
                "midpoint",
                0.30,
            )
        ]
    )

    assessment = assessments[0]

    assert assessment.survives_bid_ask is False
    assert assessment.status == "removed_by_spread"
    assert assessment.gross_edge_per_contract == 0.0
    assert assessment.net_edge_per_contract == 0.0


def test_costs_reduce_executable_edge() -> None:
    assessments = assess_opportunities(
        [
            make_violation(
                "midpoint",
                0.30,
            ),
            make_violation(
                "bid_ask",
                0.08,
            ),
        ],
        contract_multiplier=100,
        commission_per_contract=0.65,
        fee_per_contract=0.05,
    )

    assessment = assessments[0]

    assert assessment.survives_bid_ask is True
    assert assessment.option_contracts == 2
    assert assessment.gross_edge_per_contract == (pytest.approx(8.00))
    assert assessment.estimated_transaction_cost == (pytest.approx(1.40))
    assert assessment.net_edge_per_contract == (pytest.approx(6.60))
    assert assessment.profitable_after_costs is True
    assert assessment.status == "passes_cost_filter"


def test_minimum_net_edge_can_reject_small_trade() -> None:
    assessments = assess_opportunities(
        [
            make_violation(
                "midpoint",
                0.30,
            ),
            make_violation(
                "bid_ask",
                0.08,
            ),
        ],
        minimum_net_edge=7.00,
    )

    assessment = assessments[0]

    assert assessment.net_edge_per_contract == (pytest.approx(6.60))
    assert assessment.profitable_after_costs is False
    assert assessment.status == "removed_by_costs"


def test_butterfly_uses_four_option_contracts() -> None:
    assessments = assess_opportunities(
        [
            make_violation(
                "midpoint",
                0.20,
                violation_type="butterfly_convexity",
                strikes=(100.0, 105.0, 110.0),
            ),
            make_violation(
                "bid_ask",
                0.04,
                violation_type="butterfly_convexity",
                strikes=(100.0, 105.0, 110.0),
            ),
        ]
    )

    assessment = assessments[0]
    frame = assessments_to_frame(assessments)

    assert assessment.option_contracts == 4
    assert assessment.gross_edge_per_contract == (pytest.approx(4.00))
    assert assessment.estimated_transaction_cost == (pytest.approx(2.80))
    assert assessment.net_edge_per_contract == (pytest.approx(1.20))
    assert frame.loc[0, "status"] == ("passes_cost_filter")


def test_negative_cost_assumption_raises() -> None:
    with pytest.raises(
        ValueError,
        match="commission_per_contract",
    ):
        assess_opportunities(
            [],
            commission_per_contract=-0.01,
        )
