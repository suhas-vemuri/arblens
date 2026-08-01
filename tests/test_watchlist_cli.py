from datetime import UTC, datetime

from arblens.watchlist_cli import build_parser, default_output_path, default_ranking_path


def test_parses_watchlist_arguments() -> None:
    args = build_parser().parse_args(
        [
            "data/watchlists/starter.txt",
            "--maximum-expirations",
            "3",
            "--minimum-volume",
            "5",
            "--allow-production",
        ]
    )
    assert args.maximum_expirations == 3
    assert args.minimum_volume == 5
    assert args.allow_production is True


def test_builds_report_paths() -> None:
    captured_at = datetime(2026, 8, 1, 15, 30, tzinfo=UTC)
    assert (
        str(default_output_path(captured_at))
        .replace("\\", "/")
        .endswith("watchlist_scan_20260801T153000Z.csv")
    )
    assert (
        str(default_ranking_path(captured_at))
        .replace("\\", "/")
        .endswith("watchlist_ranked_20260801T153000Z.csv")
    )
