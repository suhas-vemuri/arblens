from datetime import UTC, datetime

import pandas as pd
import pytest

from arblens.io import (
    build_snapshot_path,
    load_chain,
    save_timestamped_snapshot,
)


def test_build_snapshot_path_uses_utc_timestamp(
    tmp_path,
) -> None:
    captured_at = datetime(
        2026,
        7,
        28,
        17,
        30,
        tzinfo=UTC,
    )

    path = build_snapshot_path(
        " spy ",
        "2026-08-21",
        captured_at=captured_at,
        directory=tmp_path,
        file_format="pq",
    )

    assert path == (tmp_path / "SPY_2026-08-21_20260728T173000Z.parquet")


def test_save_and_reload_timestamped_csv(
    tmp_path,
) -> None:
    frame = pd.DataFrame(
        [
            {
                "symbol": "SPY",
                "expiration": "2026-08-21",
                "option_type": "call",
                "strike": 500.0,
                "bid": 10.20,
                "ask": 10.40,
            }
        ]
    )

    captured_at = datetime(
        2026,
        7,
        28,
        17,
        30,
        tzinfo=UTC,
    )

    path = save_timestamped_snapshot(
        frame,
        "SPY",
        "2026-08-21",
        captured_at=captured_at,
        directory=tmp_path,
        file_format="csv",
    )

    loaded = load_chain(path)

    assert path.exists()
    pd.testing.assert_frame_equal(
        loaded,
        frame,
    )


def test_invalid_snapshot_expiration_raises(
    tmp_path,
) -> None:
    with pytest.raises(
        ValueError,
        match="expiration must be an ISO date",
    ):
        build_snapshot_path(
            "SPY",
            "not-a-date",
            directory=tmp_path,
        )
