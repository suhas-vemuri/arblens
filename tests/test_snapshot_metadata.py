from datetime import UTC, datetime

from arblens.io import (
    load_snapshot_metadata,
    save_snapshot_metadata,
)


def test_snapshot_metadata_round_trip(
    tmp_path,
) -> None:
    snapshot = tmp_path / "sample.parquet"

    snapshot.touch()

    expected = {
        "symbol": "AAPL",
        "captured_at": datetime(
            2026,
            7,
            30,
            23,
            38,
            tzinfo=UTC,
        ),
        "synchronization_passed": (False),
    }

    metadata_path = save_snapshot_metadata(
        snapshot,
        expected,
    )

    assert metadata_path.name == ("sample.parquet.metadata.json")

    loaded = load_snapshot_metadata(snapshot)

    assert loaded["symbol"] == "AAPL"

    assert loaded["synchronization_passed"] is False

    assert loaded["captured_at"] == ("2026-07-30T23:38:00+00:00")
