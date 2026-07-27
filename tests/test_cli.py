from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_cli_reports_average_bid_ask_spread() -> None:
    project_root = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "arblens",
            str(project_root / "data" / "sample_chain.csv"),
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "Average bid-ask spread: 0.7987" in result.stdout
    assert "Quote errors: 0" in result.stdout
    assert "Quote warnings: 1" in result.stdout
