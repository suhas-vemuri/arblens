from __future__ import annotations

import argparse

from arblens.cleaning import clean_quotes
from arblens.detection import run_all_checks, violations_to_frame
from arblens.io import load_chain


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze an option chain with ArbLens")
    parser.add_argument("path", help="CSV or Parquet option-chain file")
    parser.add_argument("--spot", type=float, default=100.0)
    parser.add_argument("--time", type=float, default=30 / 365)
    parser.add_argument("--rate", type=float, default=0.04)
    parser.add_argument("--dividend-yield", type=float, default=0.0)
    args = parser.parse_args()

    raw = load_chain(args.path)
    cleaned, issues = clean_quotes(raw)
    error_count = sum(issue.severity == "error" for issue in issues)
    warning_count = sum(issue.severity == "warning" for issue in issues)
    if cleaned.empty:
        average_spread = 0.0
    else:
        average_spread = float((cleaned["ask"] - cleaned["bid"]).mean())
    violations = run_all_checks(
        cleaned,
        spot=args.spot,
        time=args.time,
        rate=args.rate,
        dividend_yield=args.dividend_yield,
    )

    print(f"Raw rows: {len(raw)}")
    print(f"Clean rows: {len(cleaned)}")
    print(f"Quote issues: {len(issues)}")
    print(f"Quote errors: {error_count}")
    print(f"Quote warnings: {warning_count}")
    print(f"Average bid-ask spread: {average_spread:.4f}")
    print(f"Violations: {len(violations)}")
    print()
    table = violations_to_frame(violations)
    if table.empty:
        print("No violations detected.")
    else:
        print(table.to_string(index=False))


if __name__ == "__main__":
    main()
