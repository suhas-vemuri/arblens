from __future__ import annotations

import math

from scipy.optimize import brentq
from scipy.stats import norm


def _validate_inputs(spot: float, strike: float, time: float, volatility: float) -> None:
    if spot <= 0:
        raise ValueError("spot must be positive")
    if strike <= 0:
        raise ValueError("strike must be positive")
    if time < 0:
        raise ValueError("time must be non-negative")
    if volatility < 0:
        raise ValueError("volatility must be non-negative")


def intrinsic_value(spot: float, strike: float, option_type: str) -> float:
    if option_type == "call":
        return max(spot - strike, 0.0)
    if option_type == "put":
        return max(strike - spot, 0.0)
    raise ValueError("option_type must be 'call' or 'put'")


def black_scholes_price(
    *,
    spot: float,
    strike: float,
    time: float,
    rate: float,
    volatility: float,
    option_type: str,
    dividend_yield: float = 0.0,
) -> float:
    """Return a European Black–Scholes option value per underlying unit."""
    _validate_inputs(spot, strike, time, volatility)

    if time == 0:
        return intrinsic_value(spot, strike, option_type)

    if volatility == 0:
        forward_spot = spot * math.exp(-dividend_yield * time)
        discounted_strike = strike * math.exp(-rate * time)
        if option_type == "call":
            return max(forward_spot - discounted_strike, 0.0)
        if option_type == "put":
            return max(discounted_strike - forward_spot, 0.0)
        raise ValueError("option_type must be 'call' or 'put'")

    sqrt_t = math.sqrt(time)
    d1 = (math.log(spot / strike) + (rate - dividend_yield + 0.5 * volatility**2) * time) / (
        volatility * sqrt_t
    )
    d2 = d1 - volatility * sqrt_t

    discounted_spot = spot * math.exp(-dividend_yield * time)
    discounted_strike = strike * math.exp(-rate * time)

    if option_type == "call":
        return discounted_spot * norm.cdf(d1) - discounted_strike * norm.cdf(d2)
    if option_type == "put":
        return discounted_strike * norm.cdf(-d2) - discounted_spot * norm.cdf(-d1)
    raise ValueError("option_type must be 'call' or 'put'")


def implied_volatility(
    *,
    market_price: float,
    spot: float,
    strike: float,
    time: float,
    rate: float,
    option_type: str,
    dividend_yield: float = 0.0,
    lower_vol: float = 1e-6,
    upper_vol: float = 5.0,
) -> float:
    """Invert Black–Scholes with Brent's method.

    Raises ValueError when the observed price lies outside no-arbitrage bounds or
    no root can be bracketed.
    """
    if market_price < 0:
        raise ValueError("market_price must be non-negative")
    if time <= 0:
        raise ValueError("time must be positive for implied-volatility inversion")

    def objective(vol: float) -> float:
        return (
            black_scholes_price(
                spot=spot,
                strike=strike,
                time=time,
                rate=rate,
                volatility=vol,
                option_type=option_type,
                dividend_yield=dividend_yield,
            )
            - market_price
        )

    low_value = objective(lower_vol)
    high_value = objective(upper_vol)
    if low_value == 0:
        return lower_vol
    if high_value == 0:
        return upper_vol
    if low_value * high_value > 0:
        raise ValueError("market price does not produce a bracketed implied volatility")

    return float(brentq(objective, lower_vol, upper_vol, maxiter=200, xtol=1e-10))


def european_price_bounds(
    *,
    spot: float,
    strike: float,
    time: float,
    rate: float,
    option_type: str,
    dividend_yield: float = 0.0,
) -> tuple[float, float]:
    discounted_spot = spot * math.exp(-dividend_yield * time)
    discounted_strike = strike * math.exp(-rate * time)

    if option_type == "call":
        return max(discounted_spot - discounted_strike, 0.0), discounted_spot
    if option_type == "put":
        return max(discounted_strike - discounted_spot, 0.0), discounted_strike
    raise ValueError("option_type must be 'call' or 'put'")
