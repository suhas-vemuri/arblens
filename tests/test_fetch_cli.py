import pandas as pd
import pytest

from arblens.__main__ import main
from arblens.io import load_chain


class FakeProvider:
    """Return controlled data without contacting Tradier."""

    environment = "sandbox"

    def __init__(
        self,
        frame: pd.DataFrame,
        *,
        expirations: list[str] | None = None,
    ) -> None:
        self.frame = frame
        self.expirations = expirations or ["2026-08-21"]

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
        assert symbol.strip().upper() == "SPY"
        assert expiration == "2026-08-21"

        return self.frame.copy()


def test_fetch_command_saves_csv_snapshot(
    tmp_path,
    capsys,
) -> None:
    frame = pd.DataFrame(
        [
            {
                "symbol": "SPY",
                "contract_symbol": ("SPY260821C00500000"),
                "expiration": "2026-08-21",
                "option_type": "call",
                "strike": 500.0,
                "bid": 10.20,
                "ask": 10.40,
                "volume": 125,
                "open_interest": 2500,
            }
        ]
    )

    exit_code = main(
        [
            "fetch",
            "SPY",
            "--expiration",
            "2026-08-21",
            "--output-dir",
            str(tmp_path),
            "--format",
            "csv",
        ],
        provider_factory=lambda: FakeProvider(frame),
    )

    output = capsys.readouterr().out
    snapshots = list(tmp_path.glob("SPY_2026-08-21_*.csv"))

    assert exit_code == 0
    assert len(snapshots) == 1
    assert "Provider environment: sandbox" in output
    assert "Fetched contracts: 1" in output
    assert "Snapshot saved:" in output

    loaded = load_chain(snapshots[0])

    assert len(loaded) == 1
    assert loaded.loc[0, "symbol"] == "SPY"
    assert loaded.loc[0, "strike"] == 500.0


def test_fetch_command_skips_empty_snapshot(
    tmp_path,
    capsys,
) -> None:
    exit_code = main(
        [
            "fetch",
            "SPY",
            "--expiration",
            "2026-08-21",
            "--output-dir",
            str(tmp_path),
        ],
        provider_factory=lambda: FakeProvider(pd.DataFrame()),
    )

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Fetched contracts: 0" in output
    assert "snapshot was not saved" in output
    assert list(tmp_path.iterdir()) == []


def test_fetch_rejects_unavailable_expiration(
    tmp_path,
    capsys,
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "fetch",
                "SPY",
                "--expiration",
                "2026-08-28",
                "--output-dir",
                str(tmp_path),
            ],
            provider_factory=lambda: FakeProvider(
                pd.DataFrame(),
                expirations=["2026-08-21"],
            ),
        )

    error_output = capsys.readouterr().err

    assert exc_info.value.code == 2
    assert ("expiration 2026-08-28 is not available for SPY") in error_output
    assert list(tmp_path.iterdir()) == []
