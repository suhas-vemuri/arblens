from datetime import UTC, datetime

from arblens.scan_cli import (
    build_parser,
    default_output_path,
)


def test_parses_maximum_expirations() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "AAPL",
            "--maximum-expirations",
            "3",
            "--allow-production",
        ]
    )

    assert args.symbol == "AAPL"

    assert args.maximum_expirations == 3

    assert args.allow_production is True


def test_parses_multiple_expirations() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "SPY",
            "--expiration",
            "2026-08-07",
            "--expiration",
            "2026-08-14",
        ]
    )

    assert args.expirations == [
        "2026-08-07",
        "2026-08-14",
    ]


def test_builds_timestamped_output_path() -> None:
    path = default_output_path(
        "aapl",
        datetime(
            2026,
            8,
            1,
            15,
            30,
            tzinfo=UTC,
        ),
    )

    assert str(path).replace(
        "\\",
        "/",
    ) == ("data/reports/AAPL_scan_20260801T153000Z.csv")
