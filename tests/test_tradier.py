import httpx
import pytest

from arblens.providers.tradier import (
    CHAIN_COLUMNS,
    TradierAPIError,
    TradierProvider,
)


def build_provider(
    handler: httpx.MockTransport,
) -> TradierProvider:
    return TradierProvider(
        token="test-token",
        base_url="https://example.test/v1",
        transport=handler,
    )


def test_missing_token_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "arblens.providers.tradier.load_dotenv",
        lambda: False,
    )
    monkeypatch.delenv(
    	"TRADIER_TOKEN",
    	raising=False,
    )
    monkeypatch.delenv(
    	"TRADIER_ACCESS_TOKEN",
    	raising=False,
    )
    with pytest.raises(
        ValueError,
        match="Tradier token is not configured",
    ):
        TradierProvider()


def test_get_expirations_returns_dates() -> None:
    def handle_request(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == ("/v1/markets/options/expirations")
        assert request.url.params["symbol"] == "SPY"
        assert request.headers["Authorization"] == ("Bearer test-token")

        return httpx.Response(
            200,
            json={
                "expirations": {
                    "date": [
                        "2026-08-07",
                        "2026-08-14",
                    ]
                }
            },
        )

    transport = httpx.MockTransport(handle_request)
    provider = build_provider(transport)

    expirations = provider.get_expirations(" spy ")

    assert expirations == [
        "2026-08-07",
        "2026-08-14",
    ]


def test_get_chain_normalizes_single_option() -> None:
    def handle_request(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.url.path == "/v1/markets/options/chains"
        assert request.url.params["symbol"] == "SPY"
        assert request.url.params["expiration"] == "2026-08-21"
        assert request.url.params["greeks"] == "true"

        return httpx.Response(
            200,
            json={
                "options": {
                    "option": {
                        "symbol": "SPY260821C00500000",
                        "expiration_date": "2026-08-21",
                        "option_type": "call",
                        "strike": 500.0,
                        "bid": 10.20,
                        "ask": 10.40,
                        "bidsize": 15,
                        "asksize": 20,
                        "last": 10.30,
                        "volume": 125,
                        "open_interest": 2500,
                        "trade_date": "2026-07-28T15:30:00Z",
                    }
                }
            },
        )

    transport = httpx.MockTransport(handle_request)
    provider = build_provider(transport)

    frame = provider.get_chain(
        "spy",
        "2026-08-21",
    )

    assert len(frame) == 1
    assert list(frame.columns) == CHAIN_COLUMNS
    assert frame.loc[0, "symbol"] == "SPY"
    assert frame.loc[0, "contract_symbol"] == ("SPY260821C00500000")
    assert frame.loc[0, "option_type"] == "call"
    assert frame.loc[0, "strike"] == 500.0
    assert frame.loc[0, "bid"] == 10.20
    assert frame.loc[0, "ask"] == 10.40
    assert frame.loc[0, "volume"] == 125
    assert frame.loc[0, "open_interest"] == 2500


def test_empty_chain_returns_expected_columns() -> None:
    def handle_request(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "options": None,
            },
        )

    transport = httpx.MockTransport(handle_request)
    provider = build_provider(transport)

    frame = provider.get_chain(
        "SPY",
        "2026-08-21",
    )

    assert frame.empty
    assert list(frame.columns) == CHAIN_COLUMNS


def test_http_error_raises_tradier_error() -> None:
    def handle_request(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            401,
            json={
                "fault": {
                    "faultstring": "Invalid access token",
                }
            },
        )

    transport = httpx.MockTransport(handle_request)
    provider = build_provider(transport)

    with pytest.raises(
        TradierAPIError,
        match="status 401",
    ):
        provider.get_expirations("SPY")


def test_default_environment_is_sandbox(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "arblens.providers.tradier.load_dotenv",
        lambda: False,
    )
    monkeypatch.setenv(
        "TRADIER_ACCESS_TOKEN",
        "test-token",
    )
    monkeypatch.delenv(
        "TRADIER_BASE_URL",
        raising=False,
    )

    provider = TradierProvider()

    assert provider.base_url == ("https://sandbox.tradier.com/v1")
    assert provider.environment == "sandbox"
