from arblens.repeat_cli import build_parser


def test_parses_repeat_arguments() -> None:
    args = build_parser().parse_args(
        [
            "data/watchlists/starter.txt",
            "--runs",
            "3",
            "--interval-seconds",
            "10",
            "--allow-production",
        ]
    )
    assert args.runs == 3
    assert args.interval_seconds == 10
    assert args.allow_production is True
