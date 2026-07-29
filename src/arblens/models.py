from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class OptionType(StrEnum):
    CALL = "call"
    PUT = "put"


@dataclass(frozen=True, slots=True)
class QuoteIssue:
    row_index: int
    code: str
    message: str
    severity: str = "error"


@dataclass(frozen=True, slots=True)
class Violation:
    violation_type: str
    option_type: str
    expiration: str
    strikes: tuple[float, ...]
    magnitude: float
    price_basis: str
    details: str
    detected_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class OpportunityAssessment:
    """Explain whether a midpoint anomaly survives realistic filters."""

    violation_type: str
    option_type: str
    expiration: str
    strikes: tuple[float, ...]
    midpoint_magnitude: float
    executable_magnitude: float
    survives_bid_ask: bool
    option_contracts: int
    contract_multiplier: int
    gross_edge_per_contract: float
    estimated_transaction_cost: float
    net_edge_per_contract: float
    profitable_after_costs: bool
    status: str
    details: str
