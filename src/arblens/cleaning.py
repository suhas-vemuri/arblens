from __future__ import annotations

from datetime import UTC, datetime
from math import isfinite

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

DEFAULT_MAX_RELATIVE_SPREAD = 1.0


def _parse_finite_float(value: object) -> float | None:
    """Convert a value to a finite float, or return None when conversion fails."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    return number if isfinite(number) else None


def add_midpoint(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["mid"] = (result["bid"] + result["ask"]) / 2.0
    return result


def validate_quotes(
    frame: pd.DataFrame,
    *,
    now: datetime | None = None,
    max_quote_age_seconds: float | None = None,
    max_relative_spread: float | None = DEFAULT_MAX_RELATIVE_SPREAD,
) -> list[QuoteIssue]:
    missing_columns = REQUIRED_COLUMNS - set(frame.columns)
    if missing_columns:
        raise ValueError(f"missing required columns: {sorted(missing_columns)}")

    if max_relative_spread is not None and max_relative_spread < 0:
        raise ValueError("max_relative_spread must be non-negative")

    issues: list[QuoteIssue] = []
    current_time = now or datetime.now(UTC)

    for index, row in frame.iterrows():
        row_index = int(index)

        raw_bid = row["bid"]
        raw_ask = row["ask"]

        bid = _parse_finite_float(raw_bid)
        ask = _parse_finite_float(raw_ask)
        strike = _parse_finite_float(row["strike"])

        option_type = str(row["option_type"]).strip().lower()
        expiration = pd.to_datetime(
            row["expiration"],
            errors="coerce",
            format="mixed",
        )
        if bid is None or ask is None:
            if pd.isna(raw_bid) or pd.isna(raw_ask):
                issues.append(
                    QuoteIssue(
                        row_index,
                        "missing_quote",
                        "bid or ask is missing",
                    )
                )
            else:
                issues.append(
                    QuoteIssue(
                        row_index,
                        "invalid_quote",
                        "bid and ask must be finite numbers",
                    )
                )
        elif bid < 0 or ask <= 0:
            issues.append(
                QuoteIssue(
                    row_index,
                    "invalid_price",
                    "bid must be >= 0 and ask must be > 0",
                )
            )
        elif bid > ask:
            issues.append(
                QuoteIssue(
                    row_index,
                    "crossed_market",
                    "bid is greater than ask",
                )
            )
        elif max_relative_spread is not None:
            midpoint = (bid + ask) / 2.0
            relative_spread = (ask - bid) / midpoint

            if relative_spread > max_relative_spread:
                issues.append(
                    QuoteIssue(
                        row_index,
                        "wide_spread",
                        (
                            f"relative spread is {relative_spread:.1%}; "
                            f"limit is {max_relative_spread:.1%}"
                        ),
                        severity="warning",
                    )
                )

        if strike is None or strike <= 0:
            issues.append(
                QuoteIssue(
                    row_index,
                    "invalid_strike",
                    "strike must be a positive finite number",
                )
            )

        if option_type not in {"call", "put"}:
            issues.append(
                QuoteIssue(
                    row_index,
                    "invalid_option_type",
                    "expected call or put",
                )
            )

        if pd.isna(expiration):
            issues.append(
                QuoteIssue(
                    row_index,
                    "invalid_expiration",
                    "expiration date is invalid",
                )
            )
        if "volume" in frame.columns:
            volume = _parse_finite_float(row["volume"])

            if volume == 0:
                issues.append(
                    QuoteIssue(
                        row_index,
                        "zero_volume",
                        "trading volume is zero",
                        severity="warning",
                    )
                )

        if "open_interest" in frame.columns:
            open_interest = _parse_finite_float(row["open_interest"])

            if open_interest == 0:
                issues.append(
                    QuoteIssue(
                        row_index,
                        "zero_open_interest",
                        "open interest is zero",
                        severity="warning",
                    )
                )
        if max_quote_age_seconds is not None and "quote_timestamp" in frame.columns:
            timestamp = pd.to_datetime(
                row["quote_timestamp"],
                utc=True,
                errors="coerce",
            )

            if pd.isna(timestamp):
                issues.append(
                    QuoteIssue(
                        row_index,
                        "invalid_timestamp",
                        "quote timestamp is invalid",
                        severity="warning",
                    )
                )
            else:
                age = (current_time - timestamp.to_pydatetime()).total_seconds()

                if age > max_quote_age_seconds:
                    issues.append(
                        QuoteIssue(
                            row_index,
                            "stale_quote",
                            f"quote is {age:.1f} seconds old",
                            severity="warning",
                        )
                    )

    normalized_keys = frame[["symbol", "expiration", "option_type", "strike"]].copy()

    normalized_keys["symbol"] = normalized_keys["symbol"].astype(str).str.strip().str.upper()
    normalized_keys["option_type"] = (
        normalized_keys["option_type"].astype(str).str.strip().str.lower()
    )
    normalized_keys["strike"] = pd.to_numeric(
        normalized_keys["strike"],
        errors="coerce",
    )
    normalized_keys["expiration"] = pd.to_datetime(
        normalized_keys["expiration"],
        errors="coerce",
        format="mixed",
    ).dt.strftime("%Y-%m-%d")

    duplicates = normalized_keys.duplicated(
        subset=["symbol", "expiration", "option_type", "strike"],
        keep=False,
    )

    for index in frame.index[duplicates]:
        issues.append(
            QuoteIssue(
                int(index),
                "duplicate_contract",
                "duplicate contract row",
            )
        )

    return issues


def clean_quotes(
    frame: pd.DataFrame,
    *,
    now: datetime | None = None,
    max_quote_age_seconds: float | None = None,
    max_relative_spread: float | None = DEFAULT_MAX_RELATIVE_SPREAD,
) -> tuple[pd.DataFrame, list[QuoteIssue]]:
    """Return an analysis-safe frame and a complete issue log."""
    issues = validate_quotes(
        frame,
        now=now,
        max_quote_age_seconds=max_quote_age_seconds,
        max_relative_spread=max_relative_spread,
    )

    invalid_codes = {
        "missing_quote",
        "invalid_quote",
        "invalid_strike",
        "invalid_price",
        "crossed_market",
        "invalid_option_type",
        "invalid_expiration",
        "duplicate_contract",
    }

    invalid_indices = {issue.row_index for issue in issues if issue.code in invalid_codes}

    cleaned = frame.drop(index=list(invalid_indices)).copy()

    cleaned["symbol"] = cleaned["symbol"].astype(str).str.strip().str.upper()
    cleaned["option_type"] = cleaned["option_type"].astype(str).str.strip().str.lower()

    cleaned["strike"] = pd.to_numeric(cleaned["strike"], errors="coerce")
    cleaned["bid"] = pd.to_numeric(cleaned["bid"], errors="coerce")
    cleaned["ask"] = pd.to_numeric(cleaned["ask"], errors="coerce")

    cleaned["expiration"] = pd.to_datetime(
        cleaned["expiration"],
        errors="coerce",
        format="mixed",
    ).dt.strftime("%Y-%m-%d")

    cleaned = add_midpoint(cleaned)
    cleaned = cleaned.sort_values(["expiration", "option_type", "strike"]).reset_index(drop=True)

    return cleaned, issues
