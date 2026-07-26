from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from arblens.models import QuoteIssue

REQUIRED_COLUMNS = {
    "symbol",
    "expiration",
    "option_type",
    "strike",
    "bid",
    "ask",
}


def add_midpoint(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["mid"] = (result["bid"] + result["ask"]) / 2.0
    return result


def validate_quotes(
    frame: pd.DataFrame,
    *,
    now: datetime | None = None,
    max_quote_age_seconds: float | None = None,
) -> list[QuoteIssue]:
    missing_columns = REQUIRED_COLUMNS - set(frame.columns)
    if missing_columns:
        raise ValueError(f"missing required columns: {sorted(missing_columns)}")

    issues: list[QuoteIssue] = []
    current_time = now or datetime.now(timezone.utc)

    for index, row in frame.iterrows():
        bid = row["bid"]
        ask = row["ask"]
        strike = row["strike"]
        option_type = str(row["option_type"]).lower()

        if pd.isna(bid) or pd.isna(ask):
            issues.append(QuoteIssue(index, "missing_quote", "bid or ask is missing"))
            continue
        if strike <= 0:
            issues.append(QuoteIssue(index, "invalid_strike", "strike must be positive"))
        if bid < 0 or ask <= 0:
            issues.append(QuoteIssue(index, "invalid_price", "bid must be >= 0 and ask > 0"))
        if bid > ask:
            issues.append(QuoteIssue(index, "crossed_market", "bid is greater than ask"))
        if option_type not in {"call", "put"}:
            issues.append(QuoteIssue(index, "invalid_option_type", "expected call or put"))

        if max_quote_age_seconds is not None and "quote_timestamp" in frame.columns:
            timestamp = pd.to_datetime(row["quote_timestamp"], utc=True, errors="coerce")
            if pd.isna(timestamp):
                issues.append(QuoteIssue(index, "invalid_timestamp", "quote timestamp is invalid"))
            else:
                age = (current_time - timestamp.to_pydatetime()).total_seconds()
                if age > max_quote_age_seconds:
                    issues.append(
                        QuoteIssue(
                            index,
                            "stale_quote",
                            f"quote is {age:.1f} seconds old",
                            severity="warning",
                        )
                    )

    duplicates = frame.duplicated(
        subset=["symbol", "expiration", "option_type", "strike"], keep=False
    )
    for index in frame.index[duplicates]:
        issues.append(QuoteIssue(int(index), "duplicate_contract", "duplicate contract row"))

    return issues


def clean_quotes(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[QuoteIssue]]:
    """Return an analysis-safe frame and a complete issue log.

    Version 0.1 removes rows with structurally invalid quotes. Staleness is logged
    separately by callers because historical replay intentionally uses older quotes.
    """
    issues = validate_quotes(frame)
    invalid_indices = {
        issue.row_index
        for issue in issues
        if issue.code
        in {
            "missing_quote",
            "invalid_strike",
            "invalid_price",
            "crossed_market",
            "invalid_option_type",
            "duplicate_contract",
        }
    }
    cleaned = frame.drop(index=list(invalid_indices)).copy()
    cleaned["option_type"] = cleaned["option_type"].str.lower()
    cleaned = add_midpoint(cleaned)
    cleaned = cleaned.sort_values(["expiration", "option_type", "strike"]).reset_index(drop=True)
    return cleaned, issues
