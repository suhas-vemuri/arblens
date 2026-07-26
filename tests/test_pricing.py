import math

import pytest

from arblens.pricing import black_scholes_price, implied_volatility


def test_put_call_parity_reference_case() -> None:
    call = black_scholes_price(
        spot=100,
        strike=100,
        time=1,
        rate=0.05,
        volatility=0.2,
        option_type="call",
    )
    put = black_scholes_price(
        spot=100,
        strike=100,
        time=1,
        rate=0.05,
        volatility=0.2,
        option_type="put",
    )
    assert call - put == pytest.approx(100 - 100 * math.exp(-0.05), abs=1e-8)


def test_implied_volatility_recovers_input() -> None:
    market_price = black_scholes_price(
        spot=100,
        strike=105,
        time=0.5,
        rate=0.03,
        volatility=0.32,
        option_type="call",
    )
    recovered = implied_volatility(
        market_price=market_price,
        spot=100,
        strike=105,
        time=0.5,
        rate=0.03,
        option_type="call",
    )
    assert recovered == pytest.approx(0.32, abs=1e-7)
