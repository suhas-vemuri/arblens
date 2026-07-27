from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from arblens.pricing import black_scholes_price  # noqa: E402


def main() -> None:
    spot = 100.0
    rate = 0.04
    time = 30 / 365
    volatility = 0.24
    expiration = (date.today() + timedelta(days=30)).isoformat()
    rows = []

    for option_type in ("call", "put"):
        for strike in (90.0, 95.0, 100.0, 105.0, 110.0):
            fair = black_scholes_price(
                spot=spot,
                strike=strike,
                time=time,
                rate=rate,
                volatility=volatility,
                option_type=option_type,
            )
            spread = max(0.10, fair * 0.05)
            bid = max(0.01, fair - spread / 2)
            ask = fair + spread / 2
            rows.append(
                {
                    "symbol": "DEMO",
                    "expiration": expiration,
                    "option_type": option_type,
                    "strike": strike,
                    "bid": round(bid, 4),
                    "ask": round(ask, 4),
                    "volume": int(500 - abs(strike - spot) * 20),
                    "open_interest": int(2000 - abs(strike - spot) * 60),
                }
            )

    frame = pd.DataFrame(rows)

    # Deliberately create a wide-spread midpoint distortion at the 105 call.
    # This should trigger midpoint checks without necessarily creating a clean
    # executable bid/ask arbitrage.
    mask = (frame["option_type"] == "call") & (frame["strike"] == 105.0)
    frame.loc[mask, "bid"] = 0.35
    frame.loc[mask, "ask"] = 6.15

    destination = PROJECT_ROOT / "data" / "sample_chain.csv"
    destination.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(destination, index=False)
    print(f"Wrote {destination}")


if __name__ == "__main__":
    main()
