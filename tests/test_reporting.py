from arblens.reporting import (
    save_scan_report,
    scan_result_to_frame,
)
from arblens.scanning import (
    ExpirationScanResult,
    SymbolScanResult,
)


def build_result() -> SymbolScanResult:
    return SymbolScanResult(
        symbol="AAPL",
        requested_expirations=(
            "2026-08-07",
            "2026-08-14",
            "2026-08-21",
        ),
        completed_expirations=2,
        failed_expirations=1,
        results=(
            ExpirationScanResult(
                symbol="AAPL",
                expiration="2026-08-07",
                raw_rows=100,
                clean_rows=98,
                quote_issues=2,
                quote_errors=0,
                quote_warnings=2,
                spot_used=220.05,
                time_to_expiration_years=0.02,
                synchronization_passed=True,
                synchronization_reason=("markets synchronized"),
                spot_dependent_checks_skipped=False,
                violation_count=5,
                midpoint_violation_count=4,
                executable_violation_count=1,
            ),
            ExpirationScanResult(
                symbol="AAPL",
                expiration="2026-08-14",
                raw_rows=100,
                clean_rows=100,
                quote_issues=0,
                quote_errors=0,
                quote_warnings=0,
                spot_used=None,
                time_to_expiration_years=0.04,
                synchronization_passed=False,
                synchronization_reason=("timestamps did not match"),
                spot_dependent_checks_skipped=True,
                violation_count=3,
                midpoint_violation_count=3,
                executable_violation_count=0,
            ),
            ExpirationScanResult(
                symbol="AAPL",
                expiration="2026-08-21",
                raw_rows=0,
                clean_rows=0,
                quote_issues=0,
                quote_errors=0,
                quote_warnings=0,
                spot_used=None,
                time_to_expiration_years=None,
                synchronization_passed=None,
                synchronization_reason="scan failed",
                spot_dependent_checks_skipped=True,
                violation_count=0,
                midpoint_violation_count=0,
                executable_violation_count=0,
                error="provider failure",
            ),
        ),
    )


def test_scan_result_to_frame() -> None:
    frame = scan_result_to_frame(build_result())

    assert len(frame) == 3

    assert frame.loc[0, "status"] == ("completed_full")

    assert frame.loc[1, "status"] == ("completed_chain_only")

    assert frame.loc[2, "status"] == "failed"

    assert (
        frame.loc[
            0,
            "executable_violations",
        ]
        == 1
    )


def test_save_scan_report(tmp_path) -> None:
    destination = save_scan_report(
        build_result(),
        tmp_path / "report.csv",
    )

    assert destination.exists()

    contents = destination.read_text(encoding="utf-8")

    assert "completed_full" in contents
    assert "completed_chain_only" in contents
    assert "provider failure" in contents


def test_rejects_non_csv_report_path(
    tmp_path,
) -> None:
    try:
        save_scan_report(
            build_result(),
            tmp_path / "report.txt",
        )

    except ValueError as exc:
        assert ".csv" in str(exc)

    else:
        raise AssertionError("expected ValueError")
