from datetime import UTC, datetime

import httpx

from arblens.providers.tradier import (
    TradierProvider,
)


def test_chain_uses_newest_timestamp() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "options": {
                    "option": {
                        "symbol": ("SPY260821C00500000"),
                        "expiration_date": ("2026-08-21"),
                        "option_type": "call",
                        "strike": 500,
                        "bid": 10.2,
                        "ask": 10.4,
                        "bid_date": (1784923200000),
                        "ask_date": (1784923210000),
                        "trade_date": (1784920000000),
                    }
                }
            },
        )

    provider = TradierProvider(
        token="test",
        base_url=("https://sandbox.tradier.com/v1"),
        transport=httpx.MockTransport(handler),
    )

    frame = provider.get_chain(
        "SPY",
        "2026-08-21",
    )

    expected_timestamp = datetime.fromtimestamp(
        1784923210,
        tz=UTC,
    )

    assert (
        frame.loc[
            0,
            "quote_timestamp",
        ]
        == expected_timestamp
    )
