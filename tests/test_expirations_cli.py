import pandas as pd
import pytest

from arblens.__main__ import main


class FakeExpirationProvider:
    def __init__(
        self,
        expirations: list[str],
        *,
        environment: str = "sandbox",
    ) -> None:
        self.expirations = expirations
        self.environment = environment

    def get_expirations(
        self,
        symbol: str,
    ) -> list[str]:
        assert symbol.strip().upper() == "SPY"
        return self.expirations.copy()

    def get_chain(
        self,
        symbol: str,
        expiration: str,
    ) -> pd.DataFrame:
        raise AssertionError("get_chain should not be called")


def test_expirations_command_lists_dates(
    capsys,
) -> None:
    provider = FakeExpirationProvider(
        [
            "2026-08-07",
            "2026-08-14",
        ]
    )

    exit_code = main(
        [
            "expirations",
            " spy ",
        ],
        provider_factory=lambda: provider,
    )

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Provider environment: sandbox" in output
    assert "Symbol: SPY" in output
    assert "Available expirations: 2" in output
    assert "2026-08-07" in output
    assert "2026-08-14" in output


def test_production_environment_is_blocked(
    capsys,
) -> None:
    provider = FakeExpirationProvider(
        ["2026-08-07"],
        environment="production",
    )

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "expirations",
                "SPY",
            ],
            provider_factory=lambda: provider,
        )

    error_output = capsys.readouterr().err

    assert exc_info.value.code == 2
    assert "--allow-production" in error_output


def test_production_environment_can_be_allowed(
    capsys,
) -> None:
    provider = FakeExpirationProvider(
        ["2026-08-07"],
        environment="production",
    )

    exit_code = main(
        [
            "expirations",
            "SPY",
            "--allow-production",
        ],
        provider_factory=lambda: provider,
    )

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Provider environment: production" in output
    assert "Available expirations: 1" in output
    assert "2026-08-07" in output
