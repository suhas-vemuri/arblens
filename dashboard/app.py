# ruff: noqa: E402, E501
from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"

for item in (PROJECT_ROOT, SRC_ROOT):
    item_text = str(item)
    if item_text not in sys.path:
        sys.path.insert(0, item_text)

from arblens.liquidity import LiquidityFilter
from arblens.providers.tradier import TradierAPIError, TradierProvider
from arblens.ranking import opportunities_to_frame
from arblens.reporting import watchlist_result_to_frame
from arblens.watchlist import scan_watchlist
from dashboard.helpers import (
    MAX_WATCHLIST_SYMBOLS,
    build_elimination_frame,
    calculate_metrics,
    demo_rankings,
    demo_summary,
    parse_symbols,
    readable_check_name,
)
from dashboard.styles import APP_CSS, PLOTLY_LAYOUT

st.set_page_config(
    page_title="arblens",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(APP_CSS, unsafe_allow_html=True)


QUANT_METHODS = [
    {
        "title": "Put-call parity",
        "plain_name": "Are matching calls and puts priced consistently?",
        "summary": (
            "Put-call parity compares a call and a put with the same ticker, strike, "
            "and expiration. It also uses the stock price, time remaining, interest "
            "rate, and dividend assumptions."
        ),
        "checks": [
            (
                "A call, a put, shares of stock, and cash can be combined into "
                "positions with equivalent future payoffs."
            ),
            ("Equivalent positions should have consistent prices at the same moment."),
            (
                "ArbLens checks midpoint prices first, then repeats the test using "
                "actual bid prices for sells and ask prices for buys."
            ),
        ],
        "example": (
            "Suppose a stock trades at $100. A $100 call and a $100 put both expire "
            "in 30 days. If the call is much more expensive than the put and the "
            "difference cannot be explained by the stock price or financing, the "
            "relationship may violate parity."
        ),
        "implementation": [
            "Open the same expiration for the call and put.",
            "Use the same strike for both options.",
            "Compare the call price, put price, stock price, and discounted strike.",
            (
                "If one side is overpriced, the educational trade structure may "
                "combine a call, a put, stock, and cash or financing."
            ),
            (
                "The exact buy and sell directions depend on which side of the "
                "parity equation is expensive."
            ),
        ],
        "trade_structure": (
            "A parity position may require a call, a put, shares of the underlying "
            "stock, and a financing or cash component. The exact direction depends "
            "on which side of the relationship is relatively overpriced."
        ),
        "why": (
            "This tests economically equivalent positions rather than looking at "
            "one option in isolation."
        ),
        "impact": (
            "It can detect relative pricing inconsistencies while the bid-ask recheck "
            "removes signals that exist only at midpoint."
        ),
    },
    {
        "title": "Strike monotonicity",
        "plain_name": "Do option prices move correctly as strikes increase?",
        "summary": (
            "Strike monotonicity checks the ordering of option prices across strikes "
            "for the same option type and expiration."
        ),
        "checks": [
            (
                "A lower-strike call should generally be worth at least as much as a "
                "higher-strike call."
            ),
            (
                "A higher-strike put should generally be worth at least as much as a "
                "lower-strike put."
            ),
            "ArbLens compares neighboring strikes throughout the chain.",
        ],
        "example": (
            "Imagine a $100 call costs $4 while a $105 call costs $5. The $100 call "
            "gives the owner the right to buy the stock at a better price, so it "
            "should not cost less than the $105 call."
        ),
        "implementation": [
            "Choose one expiration and one option type: calls or puts.",
            "Compare two neighboring strikes.",
            (
                "For calls, check that price does not rise as strike rises. For puts, "
                "check that price does not fall as strike rises."
            ),
            (
                "A brokerage implementation is usually represented as a vertical "
                "spread with one lower-strike option and one higher-strike option."
            ),
            (
                "Use one multi-leg limit order and verify that the live debit or "
                "credit still reflects the detected violation."
            ),
        ],
        "trade_structure": (
            "This relationship is commonly represented with a vertical spread: one "
            "option is bought and another of the same type and expiration is sold at "
            "a different strike."
        ),
        "why": (
            "Incorrect strike ordering can imply that one spread is priced in a way "
            "that conflicts with its possible payoff."
        ),
        "impact": (
            "ArbLens can compare every neighboring strike automatically instead of "
            "requiring manual inspection of the entire option chain."
        ),
    },
    {
        "title": "Butterfly convexity",
        "plain_name": "Does the option-price curve have a valid shape?",
        "summary": (
            "Butterfly convexity checks three equally spaced strikes to confirm that "
            "the option-price curve does not bend in an impossible direction."
        ),
        "checks": [
            "A lower strike, middle strike, and higher strike are selected.",
            "The spacing between the three strikes must be equal.",
            (
                "ArbLens calculates the second price difference. Under standard "
                "no-arbitrage assumptions, the butterfly value should not be negative."
            ),
        ],
        "example": (
            "For calls at strikes $95, $100, and $105, a butterfly buys one $95 call, "
            "sells two $100 calls, and buys one $105 call. Its expiration payoff "
            "cannot be negative. A market price implying that you are paid to own a "
            "non-negative-payoff position would be inconsistent."
        ),
        "implementation": [
            "Choose one expiration and one option type.",
            "Select three equally spaced strikes, such as $95, $100, and $105.",
            "Buy one lower-strike option.",
            "Sell two middle-strike options.",
            "Buy one higher-strike option.",
            (
                "Enter all four contracts as one butterfly limit order and verify "
                "that the live net price still preserves the detected edge."
            ),
        ],
        "trade_structure": (
            "The classic structure uses four contracts: buy one lower-strike option, "
            "sell two middle-strike options, and buy one higher-strike option. All "
            "legs use the same option type and expiration."
        ),
        "why": ("Convexity is a core property of a valid option-price surface across strikes."),
        "impact": (
            "The test finds broken curvature across many strike triplets and then "
            "checks whether the finding survives executable bid and ask prices."
        ),
    },
    {
        "title": "European price bounds",
        "plain_name": "Is each option inside its basic theoretical limits?",
        "summary": (
            "Price-bound tests confirm that an option is not below its theoretical "
            "floor or above its theoretical ceiling."
        ),
        "checks": [
            (
                "A call should not exceed the stock price under the standard "
                "assumptions used by the project."
            ),
            ("A put should not exceed the appropriately discounted strike value."),
            ("Calls and puts should stay above their discounted intrinsic-value floors."),
        ],
        "example": (
            "If a stock costs $100, a call giving the right to buy that stock should "
            "not cost $105. Buying the stock itself would be cheaper and would provide "
            "more ownership rights."
        ),
        "implementation": [
            "Identify whether the option violated an upper bound or lower bound.",
            "Confirm the stock price, strike, expiration, and interest-rate inputs.",
            (
                "A possible educational implementation can combine the option with "
                "stock or cash to reproduce the same payoff more cheaply."
            ),
            (
                "The exact brokerage legs depend on which bound failed and whether "
                "the option was relatively too cheap or too expensive."
            ),
        ],
        "trade_structure": (
            "A price-bound relationship can involve buying the relatively underpriced "
            "asset and selling the relatively overpriced equivalent. The exact legs "
            "depend on whether an upper or lower bound was violated."
        ),
        "why": (
            "These are basic financial sanity checks that identify impossible or malformed prices."
        ),
        "impact": (
            "They prevent obvious quote problems from dominating the later ranking "
            "and execution analysis."
        ),
    },
    {
        "title": "Liquidity screening",
        "plain_name": "Could a trader realistically enter and exit the contracts?",
        "summary": (
            "Liquidity screening removes contracts that may look attractive "
            "mathematically but may be too thin or expensive to trade."
        ),
        "checks": [
            "The contract must have a positive bid when that filter is enabled.",
            "The bid-ask spread must stay below the selected relative limit.",
            "Session volume must meet the selected minimum.",
            "Open interest must meet the selected minimum.",
        ],
        "example": (
            "An option may show a bid of $0.10 and an ask of $2.00. Its midpoint is "
            "$1.05, but that midpoint is not necessarily a price at which a trade "
            "could actually occur."
        ),
        "implementation": [
            "Check that every required option leg has a positive bid.",
            "Review the bid-ask spread for every leg.",
            "Check current volume and open interest.",
            (
                "Avoid relying on a midpoint when the spread is wide or the contract "
                "has little trading activity."
            ),
            (
                "Treat liquidity as a pass-or-fail quality condition before thinking "
                "about any brokerage order."
            ),
        ],
        "trade_structure": (
            "Liquidity screening is not a strategy. It is a quality gate that every "
            "candidate must pass before ArbLens treats it as realistically executable."
        ),
        "why": (
            "Low-liquidity contracts often have stale quotes, large spreads, and poor "
            "fills that create false arbitrage signals."
        ),
        "impact": (
            "ArbLens records how many contracts are removed so the user can understand "
            "how the research universe was reduced."
        ),
    },
    {
        "title": "Bid-ask execution reality",
        "plain_name": "Does the opportunity survive prices a trader could actually use?",
        "summary": (
            "Execution analysis repeats the mathematical checks using displayed bid "
            "prices for sales and ask prices for purchases."
        ),
        "checks": [
            "Every purchased option is valued at its ask.",
            "Every sold option is valued at its bid.",
            "The executable result is compared with the midpoint-based result.",
        ],
        "example": (
            "A two-leg spread may appear to earn $0.20 using midpoint prices. After "
            "buying at the ask and selling at the bid, that same spread may become a "
            "$0.05 loss."
        ),
        "implementation": [
            "List every option leg and whether it must be bought or sold.",
            "Use the ask for each buy leg.",
            "Use the bid for each sell leg.",
            "Add the leg prices together to calculate the executable package price.",
            (
                "Enter the position as one multi-leg limit order rather than filling "
                "legs separately when the brokerage supports it."
            ),
        ],
        "trade_structure": (
            "A possible position would normally be entered as one multi-leg limit "
            "order. ArbLens cannot guarantee that displayed prices will remain "
            "available or that every leg will fill."
        ),
        "why": ("Midpoints are estimates. They are not guaranteed transaction prices."),
        "impact": (
            "This separates theoretical midpoint anomalies from findings that remain "
            "inconsistent at displayed executable prices."
        ),
    },
    {
        "title": "Cost-adjusted net edge",
        "plain_name": "How much modeled value remains after trading costs?",
        "summary": (
            "Net edge estimates the amount remaining after converting the executable "
            "price difference to a standard contract and subtracting estimated fees."
        ),
        "checks": [
            "ArbLens begins with the executable per-share pricing difference.",
            (
                "A standard U.S. equity-option contract generally represents 100 "
                "shares, so the per-share difference is multiplied by 100."
            ),
            "Estimated commission and fee costs are deducted for every contract leg.",
        ],
        "example": (
            "Assume an executable difference of $0.08 per share. That equals $8.00 "
            "for one standard contract. If modeled transaction costs total $2.60, "
            "the modeled net edge is $5.40 per contract."
        ),
        "implementation": [
            "Calculate the executable package edge using asks for buys and bids for sells.",
            "Multiply the per-share edge by the contract multiplier, usually 100.",
            "Add the modeled commission and fee cost for every leg.",
            "Subtract total costs from gross edge.",
            (
                "Recheck the number using the brokerage's live order preview because "
                "quotes and fees may differ from the model."
            ),
        ],
        "trade_structure": (
            "A candidate should only be considered when the complete multi-leg order "
            "can be entered near the calculated price and the live edge remains "
            "positive after the brokerage's current fees."
        ),
        "why": (
            "Small price differences often disappear after commissions, exchange "
            "fees, spread costs, and slippage."
        ),
        "impact": (
            "The final ranking favors findings that survive both bid-ask execution "
            "and estimated costs."
        ),
    },
    {
        "title": "Time synchronization",
        "plain_name": "Were all compared prices observed at nearly the same time?",
        "summary": (
            "Time synchronization checks whether the stock quote and option quotes "
            "come from a sufficiently similar market window."
        ),
        "checks": [
            "The timestamp attached to the underlying stock quote.",
            "The representative timestamps attached to the option chain.",
            "The maximum allowed time difference between those observations.",
        ],
        "example": (
            "After the market closes, the displayed stock quote may reflect a later "
            "update while some option quotes remain from an earlier time. Combining "
            "them can create a parity violation that never existed simultaneously."
        ),
        "implementation": [
            "Read the timestamp of the stock quote.",
            "Read the option quote timestamps.",
            "Compare the difference with the allowed tolerance.",
            ("Do not run spot-dependent checks when the timestamps are too far apart."),
        ],
        "trade_structure": (
            "This stage does not create a position. It decides whether spot-dependent "
            "tests have sufficiently synchronized information to run safely."
        ),
        "why": (
            "Static-arbitrage relationships assume that every compared price "
            "describes the same market moment."
        ),
        "impact": (
            "When synchronization fails, ArbLens skips the affected spot-dependent "
            "checks rather than silently producing an unreliable result."
        ),
    },
]


ANALYSIS_TIMELINE = [
    (
        "Data pull",
        "Downloads option chains, available expirations, and the underlying quote.",
        "Every later check starts from a timestamped market snapshot.",
    ),
    (
        "Quote cleaning",
        "Removes missing, duplicated, invalid, locked, and crossed quote records.",
        "Bad rows can distort every mathematical relationship in the option chain.",
    ),
    (
        "Liquidity filter",
        "Applies bid, spread, volume, and open-interest requirements.",
        "The remaining contracts are more suitable for realistic execution analysis.",
    ),
    (
        "Time synchronization",
        "Compares stock and option timestamps before spot-dependent tests.",
        "Mismatched data is skipped rather than used to create false violations.",
    ),
    (
        "No-arbitrage tests",
        "Runs price bounds, parity, monotonicity, and butterfly convexity.",
        "These tests search for contradictions in option pricing relationships.",
    ),
    (
        "Execution and costs",
        "Re-tests findings at bid and ask prices and subtracts modeled fees.",
        "This removes signals that exist only at midpoint or disappear after costs.",
    ),
    (
        "Ranking and reporting",
        "Orders the remaining findings and saves reproducible reports.",
        "The strongest modeled results appear first while eliminations remain visible.",
    ),
]


def plain_markdown(value: object) -> str:
    """Render financial text without inline-code or math highlighting."""
    return str(value).replace("`", "").replace("$", r"\$")


def header() -> None:
    st.markdown(
        """
        <div class="brand">
            <div class="mark"></div>
            <div class="word">arblens</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Options-market integrity and static-arbitrage research platform")


def secret_value(name: str) -> str | None:
    environment_value = os.getenv(name)
    if environment_value:
        return environment_value

    try:
        value = st.secrets.get(name)
    except (FileNotFoundError, KeyError):
        return None

    return str(value) if value else None


def tradier_configured() -> bool:
    return bool(secret_value("TRADIER_TOKEN") or secret_value("TRADIER_ACCESS_TOKEN"))


def create_provider() -> TradierProvider:
    return TradierProvider(
        token=secret_value("TRADIER_TOKEN"),
        base_url=secret_value("TRADIER_BASE_URL"),
    )


def run_live_scan(
    symbols: list[str],
    max_expirations: int,
    minimum_volume: int,
    minimum_open_interest: int,
    maximum_relative_spread: float,
    minimum_net_edge: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    provider = create_provider()

    result = scan_watchlist(
        provider,
        symbols,
        maximum_expirations=max_expirations,
        captured_at=datetime.now(UTC),
        liquidity_filter=LiquidityFilter(
            minimum_volume=minimum_volume,
            minimum_open_interest=minimum_open_interest,
            maximum_relative_spread=maximum_relative_spread,
        ),
        minimum_net_edge=minimum_net_edge,
    )

    return (
        watchlist_result_to_frame(result),
        opportunities_to_frame(result),
    )


def render_metrics(summary: pd.DataFrame) -> None:
    metrics = calculate_metrics(summary)

    first_row = st.columns(4)
    first_row[0].metric(
        "Violations found",
        f"{metrics.violations_found:,}",
        help=("Mathematical relationships that failed at midpoint or displayed bid-ask prices."),
    )
    first_row[1].metric(
        "Contracts after filters",
        f"{metrics.liquid_contracts:,}",
        help="Contracts remaining after quote and liquidity screening.",
    )
    first_row[2].metric(
        "Opportunities after costs",
        f"{metrics.opportunities_after_costs:,}",
        help=(
            "Executable findings with a positive modeled edge after estimated transaction costs."
        ),
    )
    first_row[3].metric(
        "Symbols scanned",
        f"{metrics.symbols_scanned:,}",
        help="The number of unique tickers analyzed.",
    )

    sync_rate = (
        metrics.synchronized_expirations / metrics.expirations_scanned
        if metrics.expirations_scanned
        else 0
    )

    second_row = st.columns(4)
    second_row[0].metric(
        "Raw contracts",
        f"{metrics.raw_contracts:,}",
        help="All contracts returned before quote and liquidity filtering.",
    )
    second_row[1].metric(
        "Expirations scanned",
        f"{metrics.expirations_scanned:,}",
        help="The total ticker-expiration combinations analyzed.",
    )
    second_row[2].metric(
        "Executable violations",
        f"{metrics.executable_violations:,}",
        help="Violations that remain after using bids for sells and asks for buys.",
    )
    second_row[3].metric(
        "Synchronized chains",
        f"{sync_rate:.0%}",
        help="The share of expiration chains with sufficiently aligned timestamps.",
    )


def render_analysis_timeline(summary: pd.DataFrame) -> None:
    st.subheader("Analysis timeline")
    st.caption("Open a stage to see exactly what ArbLens did and why it matters.")

    metrics = calculate_metrics(summary)

    for number, (title, action, reason) in enumerate(
        ANALYSIS_TIMELINE,
        start=1,
    ):
        with st.expander(
            f"{number}. {title}",
            expanded=number == 1,
        ):
            st.markdown(f"**What it did:** {action}")
            st.markdown(f"**Why it matters:** {reason}")

            if number == 3:
                removed = int(
                    summary.get(
                        "liquidity_removed_rows",
                        pd.Series(dtype=float),
                    )
                    .fillna(0)
                    .sum()
                )
                st.markdown(
                    f"**This scan:** removed {removed:,} contracts through the liquidity rules."
                )

            if number == 4:
                st.markdown(
                    f"**This scan:** {metrics.synchronized_expirations:,} of "
                    f"{metrics.expirations_scanned:,} expiration chains "
                    "were synchronized."
                )

            if number == 5:
                st.markdown(
                    f"**This scan:** detected {metrics.violations_found:,} "
                    "total no-arbitrage rule violations."
                )

            if number == 6:
                st.markdown(
                    f"**This scan:** {metrics.executable_violations:,} "
                    "findings survived displayed bid and ask prices, and "
                    f"{metrics.opportunities_after_costs:,} remained "
                    "positive after modeled costs."
                )


def render_quant_methods() -> None:
    st.subheader("Quant Methods Used")
    st.caption(
        "Open each method for the financial rule, a beginner example, "
        "implementation steps, and an explanation of how it improves ArbLens."
    )

    for method in QUANT_METHODS:
        with st.expander(f"{method['title']} — {method['plain_name']}"):
            st.markdown("### " + plain_markdown(method["summary"]))

            st.markdown("#### What the method checks")
            for item in method["checks"]:
                st.markdown("- " + plain_markdown(item))

            st.markdown("#### Beginner example")
            st.markdown(plain_markdown(method["example"]))

            st.markdown("#### How the method is implemented")
            for number, item in enumerate(method["implementation"], start=1):
                st.markdown(f"{number}. " + plain_markdown(item))

            st.markdown("#### Related trade structure")
            st.markdown(plain_markdown(method["trade_structure"]))

            left, right = st.columns(2)

            with left:
                st.markdown("#### Why the method matters")
                st.markdown(plain_markdown(method["why"]))

            with right:
                st.markdown("#### How it improves ArbLens")
                st.markdown(plain_markdown(method["impact"]))


def opportunity_help_text() -> dict[str, str]:
    return {
        "rank": (
            "The order after ArbLens ranks findings. Rank 1 has the strongest "
            "modeled result under the selected settings."
        ),
        "symbol": "The stock or ETF whose option chain produced the finding.",
        "analysis": "The quantitative pricing relationship that was violated.",
        "option_type": ("Whether calls, puts, or a matched call-put pair were involved."),
        "expiration": "The date on which the option contracts expire.",
        "strikes": "The exercise price or prices used by the relationship.",
        "midpoint": ("The original violation using the midpoint between bid and ask."),
        "executable": ("The edge remaining after buys use asks and sells use bids."),
        "gross": (
            "Executable edge per share multiplied by the standard contract multiplier, usually 100."
        ),
        "cost": "Estimated transaction costs across the required option legs.",
        "net": (
            "Gross modeled edge minus estimated transaction costs. "
            "Formula: executable edge per share × 100 − estimated costs."
        ),
        "persistence": ("The number of repeated scans in which a similar finding appeared."),
        "status": ("The outcome after execution-price and transaction-cost filters."),
    }


def describe_trade_structure(analysis: str) -> str:
    descriptions = {
        "Put-call parity": (
            "A parity position may combine a call, a put, shares of stock, and "
            "cash or financing. The exact direction depends on which side of "
            "the relationship is relatively overpriced."
        ),
        "Strike monotonicity": (
            "This is usually represented as a vertical spread using two calls "
            "or two puts with the same expiration and different strikes."
        ),
        "Butterfly convexity": (
            "A standard butterfly buys one lower-strike option, sells two "
            "middle-strike options, and buys one higher-strike option."
        ),
        "European price bounds": (
            "This can require combining an option with stock or cash. The exact "
            "position depends on whether an upper or lower bound failed."
        ),
    }

    return descriptions.get(
        analysis,
        (
            "The complete position depends on the quantitative relationship "
            "and the detailed option legs produced by the detector."
        ),
    )


def method_implementation(analysis: str) -> list[str]:
    for method in QUANT_METHODS:
        if method["title"] == analysis:
            return list(method["implementation"])

    return [
        "Review the complete option legs produced by the detector.",
        "Confirm current bids, asks, expiration, strikes, and quantities.",
        "Use one multi-leg limit order when supported.",
        "Recalculate the live net edge before considering submission.",
    ]


def safe_number(row: pd.Series, key: str, default: float = 0.0) -> float:
    value = row.get(key, default)
    if pd.isna(value):
        return default
    return float(value)


def edge_components(row: pd.Series) -> dict[str, float]:
    executable = safe_number(row, "executable_magnitude")
    gross = safe_number(
        row,
        "gross_edge_per_contract",
        executable * 100,
    )
    costs = safe_number(row, "estimated_transaction_cost")
    net = safe_number(
        row,
        "net_edge_per_contract",
        gross - costs,
    )

    return {
        "executable": executable,
        "gross": gross,
        "costs": costs,
        "net": net,
    }


def execution_checklist(row: pd.Series) -> list[str]:
    analysis = str(row.get("analysis", "detected relationship"))
    expiration = str(row.get("expiration", "not available"))
    strikes = str(row.get("strikes", "not available"))

    return [
        (f"Open the option chain for the displayed ticker and expiration: {expiration}."),
        f"Locate the displayed strike or strikes: {strikes}.",
        (
            f"Confirm that the {analysis} relationship is still present using "
            "the brokerage's current quotes."
        ),
        (
            "Use current ask prices for option legs being purchased and current "
            "bid prices for option legs being sold."
        ),
        (
            "When supported, enter all required legs together as one multi-leg "
            "limit order rather than filling them separately."
        ),
        (
            "Use the brokerage order preview to recalculate the full position "
            "price, commissions, regulatory fees, and buying-power use."
        ),
        (
            "Do not treat the dashboard as an order ticket. Do not submit when "
            "required sides or quantities are missing, or when live net edge is "
            "zero or negative."
        ),
    ]


def prepare_rankings(rankings: pd.DataFrame) -> pd.DataFrame:
    display = rankings.copy()

    if "violation_type" in display.columns:
        display["analysis"] = display["violation_type"].map(readable_check_name)

    if "rank" not in display.columns:
        display = display.reset_index(drop=True)
        display["rank"] = range(1, len(display) + 1)

    return display


def render_opportunity_rows(display: pd.DataFrame) -> None:
    st.markdown("### Ranked results and implementation")

    for index, row in display.iterrows():
        rank = int(row.get("rank", index + 1))
        ticker = str(row.get("symbol", "Unknown"))
        analysis = str(row.get("analysis", "Quant method"))
        expiration = str(row.get("expiration", "Unknown"))
        strikes = str(row.get("strikes", "Unknown"))
        net_edge = safe_number(row, "net_edge_per_contract")

        with st.container(border=True):
            columns = st.columns([0.45, 0.8, 1.45, 1.15, 1.0, 0.9])

            columns[0].markdown(f"**#{rank}**")
            columns[1].markdown(f"**{ticker}**")
            columns[2].markdown(analysis)
            columns[3].markdown(expiration)
            columns[4].markdown(f"Strike(s): {strikes}")

            if columns[5].button(
                "View implementation",
                key=f"implementation_{index}",
                use_container_width=True,
            ):
                st.session_state["selected_opportunity_index"] = index

            st.caption(f"Modeled net edge per contract: ${net_edge:,.2f}")


def render_selected_opportunity(display: pd.DataFrame) -> None:
    if "selected_opportunity_index" not in st.session_state:
        st.session_state["selected_opportunity_index"] = display.index[0]

    selected_index = st.session_state["selected_opportunity_index"]

    if selected_index not in display.index:
        selected_index = display.index[0]
        st.session_state["selected_opportunity_index"] = selected_index

    row = display.loc[selected_index]
    analysis = str(row.get("analysis", "Detected relationship"))
    components = edge_components(row)

    st.markdown("### Selected opportunity explanation")

    summary_columns = st.columns(4)
    summary_columns[0].metric(
        "Executable edge per share",
        f"${components['executable']:,.4f}",
        help=("The pricing difference after purchases use asks and sales use bids."),
    )
    summary_columns[1].metric(
        "Gross edge per contract",
        f"${components['gross']:,.2f}",
        help=("Executable edge per share multiplied by the contract multiplier, usually 100."),
    )
    summary_columns[2].metric(
        "Estimated costs",
        f"${components['costs']:,.2f}",
        help="Modeled commissions and fees for the required option legs.",
    )
    summary_columns[3].metric(
        "Modeled net edge",
        f"${components['net']:,.2f}",
        help=("Gross edge per contract minus estimated transaction costs."),
    )

    st.markdown("#### Edge calculation")
    st.markdown(
        plain_markdown(
            f"{components['executable']:,.4f} × 100 = "
            f"${components['gross']:,.2f} gross edge per contract"
        )
    )
    st.markdown(
        plain_markdown(
            f"${components['gross']:,.2f} − ${components['costs']:,.2f} = "
            f"${components['net']:,.2f} modeled net edge per contract"
        )
    )

    left, right = st.columns(2)

    with left:
        st.markdown("#### What ArbLens detected")
        st.write(f"ArbLens detected a possible **{analysis}** pricing relationship.")

        st.markdown("#### Related position structure")
        st.markdown(plain_markdown(describe_trade_structure(analysis)))

        st.markdown("#### Method-specific implementation")
        for number, instruction in enumerate(
            method_implementation(analysis),
            start=1,
        ):
            st.markdown(f"{number}. " + plain_markdown(instruction))

    with right:
        st.markdown("#### Educational brokerage checklist")
        for number, instruction in enumerate(
            execution_checklist(row),
            start=1,
        ):
            st.markdown(f"{number}. " + plain_markdown(instruction))

    st.caption(
        "ArbLens identifies and ranks pricing relationships; it is not a "
        "brokerage order ticket. An exact order requires complete leg sides, "
        "quantities, contract symbols, current quotes, a target limit price, "
        "and a current brokerage risk preview."
    )


def render_top_opportunities(rankings: pd.DataFrame) -> None:
    st.subheader("Top opportunities")
    st.caption(
        "Results are ranked after liquidity, synchronization, bid-ask execution, "
        "and modeled cost checks. Hover over table headers for definitions."
    )

    if rankings.empty:
        st.write(
            "No findings survived every filter. This is a valid result and often "
            "means the safeguards removed weak or non-executable signals."
        )
        return

    display = prepare_rankings(rankings)
    help_text = opportunity_help_text()

    columns = [
        column
        for column in [
            "rank",
            "symbol",
            "analysis",
            "option_type",
            "expiration",
            "strikes",
            "midpoint_magnitude",
            "executable_magnitude",
            "gross_edge_per_contract",
            "estimated_transaction_cost",
            "net_edge_per_contract",
            "persistence_count",
            "status",
        ]
        if column in display.columns
    ]

    st.dataframe(
        display[columns],
        use_container_width=True,
        hide_index=True,
        column_config={
            "rank": st.column_config.NumberColumn(
                "Rank",
                help=help_text["rank"],
                format="%d",
            ),
            "symbol": st.column_config.TextColumn(
                "Ticker",
                help=help_text["symbol"],
            ),
            "analysis": st.column_config.TextColumn(
                "Quant Method",
                help=help_text["analysis"],
            ),
            "option_type": st.column_config.TextColumn(
                "Option Type",
                help=help_text["option_type"],
            ),
            "expiration": st.column_config.TextColumn(
                "Expiration Date",
                help=help_text["expiration"],
            ),
            "strikes": st.column_config.TextColumn(
                "Strike Price(s)",
                help=help_text["strikes"],
            ),
            "midpoint_magnitude": st.column_config.NumberColumn(
                "Midpoint Violation",
                help=help_text["midpoint"],
                format="$%.4f",
            ),
            "executable_magnitude": st.column_config.NumberColumn(
                "Executable Edge / Share",
                help=help_text["executable"],
                format="$%.4f",
            ),
            "gross_edge_per_contract": st.column_config.NumberColumn(
                "Gross Edge / Contract",
                help=help_text["gross"],
                format="$%.2f",
            ),
            "estimated_transaction_cost": st.column_config.NumberColumn(
                "Estimated Costs",
                help=help_text["cost"],
                format="$%.2f",
            ),
            "net_edge_per_contract": st.column_config.NumberColumn(
                "Modeled Net Edge / Contract",
                help=help_text["net"],
                format="$%.2f",
            ),
            "persistence_count": st.column_config.NumberColumn(
                "Times Detected",
                help=help_text["persistence"],
                format="%d",
            ),
            "status": st.column_config.TextColumn(
                "Final Result",
                help=help_text["status"],
            ),
        },
    )

    render_opportunity_rows(display)
    render_selected_opportunity(display)


def render_ticker_context(
    summary: pd.DataFrame,
    symbols: list[str],
) -> None:
    st.subheader("Ticker analysis")

    selected_symbol = (
        st.segmented_control(
            "Selected ticker",
            options=symbols,
            default=symbols[0],
            label_visibility="collapsed",
        )
        or symbols[0]
    )

    selected = summary[summary["symbol"] == selected_symbol].copy()

    if selected.empty:
        st.write("No expiration rows are available for this ticker.")
        return

    figure = go.Figure()
    figure.add_bar(
        x=selected["expiration"],
        y=selected["raw_rows"],
        name="Raw contracts",
        marker_color="#666666",
    )
    figure.add_bar(
        x=selected["expiration"],
        y=selected["liquid_rows"],
        name="After filters",
        marker_color="#d2d2d2",
    )
    figure.update_layout(
        barmode="group",
        title=f"{selected_symbol} contracts by expiration",
        **PLOTLY_LAYOUT,
    )
    st.plotly_chart(figure, use_container_width=True)


def render_elimination_funnel(summary: pd.DataFrame) -> None:
    st.subheader("Filter and elimination breakdown")

    elimination = build_elimination_frame(summary)

    figure = go.Figure(
        go.Funnel(
            y=elimination["stage"],
            x=elimination["remaining"],
            textinfo="value+percent initial",
            marker={
                "color": [
                    "#e2e2e2",
                    "#bbbbbb",
                    "#929292",
                    "#6f6f6f",
                    "#505050",
                    "#303030",
                ]
            },
            connector={"line": {"color": "#737373"}},
        )
    )
    figure.update_layout(**PLOTLY_LAYOUT)
    st.plotly_chart(figure, use_container_width=True)

    with st.expander("How to read this funnel"):
        st.write(
            "Each level shows what remains after another quality check. A large "
            "drop is not automatically a problem. It often means ArbLens removed "
            "weak, stale, or non-executable data before ranking results."
        )


def render_about() -> None:
    st.markdown("---")
    st.subheader("What arblens does")
    st.write(
        "arblens is an options-market integrity and static-arbitrage research "
        "platform. It downloads option chains, removes unreliable quotes, "
        "filters weak liquidity, checks timestamp alignment, applies "
        "no-arbitrage rules, tests findings at displayed bid and ask prices, "
        "subtracts estimated costs, and ranks the remaining results."
    )
    st.caption(
        "Educational research demo only. It does not place orders, guarantee "
        "fills, or provide investment advice."
    )


def main() -> None:
    header()

    with st.container(border=True):
        control_columns = st.columns([2.1, 0.65, 0.9, 0.8, 0.85, 0.75])

        ticker_text = control_columns[0].text_input(
            "Watchlist / tickers",
            value=st.session_state.get(
                "ticker_text",
                "AAPL, MSFT, SPY, QQQ, NVDA",
            ),
            help=(
                f"Enter up to {MAX_WATCHLIST_SYMBOLS} ticker symbols, "
                "separated by commas. ArbLens runs the selected filters and "
                "quant methods across each ticker."
            ),
        )

        maximum_expirations = control_columns[1].number_input(
            "Max expirations",
            min_value=1,
            max_value=6,
            value=2,
            step=1,
            help=(
                "The maximum number of expiration dates analyzed for each ticker. "
                "More expirations increase coverage but also increase API calls and "
                "scan time."
            ),
        )

        mode = control_columns[2].selectbox(
            "Mode",
            ["Demo mode", "Live Tradier"],
            help=(
                "Demo mode uses stable educational data so the portfolio always "
                "works. Live Tradier mode uses current market data through the "
                "private Tradier token."
            ),
        )

        minimum_volume = control_columns[3].number_input(
            "Minimum volume",
            min_value=0,
            value=1,
            step=1,
            help=(
                "Volume is the number of contracts traded during the current "
                "session. Raising this minimum removes less-active contracts and "
                "can reduce false signals."
            ),
        )

        minimum_open_interest = control_columns[4].number_input(
            "Minimum open interest",
            min_value=0,
            value=1,
            step=1,
            help=(
                "Open interest is the number of contracts that remain open across "
                "market participants. Raising this minimum focuses the scan on "
                "contracts with more established participation."
            ),
        )

        maximum_spread_percent = control_columns[5].number_input(
            "Max spread %",
            min_value=1,
            max_value=200,
            value=25,
            step=1,
            help=(
                "The bid-ask spread is the difference between the best sell price "
                "and best buy price. This setting removes contracts whose spread is "
                "too large relative to midpoint, helping ArbLens avoid unrealistic "
                "execution assumptions."
            ),
        )

        with st.expander("Advanced execution and cost settings"):
            advanced_columns = st.columns(3)

            minimum_net_edge = advanced_columns[0].number_input(
                "Minimum net edge ($ per contract)",
                min_value=0.0,
                value=0.0,
                step=0.5,
                help=(
                    "The smallest modeled dollar amount that must remain after "
                    "the executable edge is multiplied by the contract multiplier "
                    "and estimated transaction costs are subtracted."
                ),
            )

            advanced_columns[1].caption(
                "Live mode limits symbols and expirations to protect API usage."
            )
            advanced_columns[2].caption(
                "Spot-dependent checks are skipped when timestamps do not synchronize."
            )

        run_scan = st.button(
            "▶ Run scan",
            type="primary",
            use_container_width=True,
        )

    try:
        symbols = parse_symbols(ticker_text)
    except ValueError as error:
        st.error(str(error))
        return

    live_requested = mode == "Live Tradier"

    if live_requested and not tradier_configured():
        st.write(
            "Live mode needs TRADIER_TOKEN in the local environment or "
            "Streamlit secrets. Demo mode remains available."
        )

    should_scan = run_scan or "summary" not in st.session_state

    if should_scan:
        with st.spinner("Running the ArbLens analysis pipeline..."):
            try:
                if live_requested and tradier_configured():
                    summary, rankings = run_live_scan(
                        symbols,
                        int(maximum_expirations),
                        int(minimum_volume),
                        int(minimum_open_interest),
                        float(maximum_spread_percent) / 100,
                        float(minimum_net_edge),
                    )
                    demo_mode = False
                else:
                    summary = demo_summary(
                        symbols,
                        int(maximum_expirations),
                    )
                    rankings = demo_rankings(symbols)
                    demo_mode = True

                st.session_state["summary"] = summary
                st.session_state["rankings"] = rankings
                st.session_state["symbols"] = symbols
                st.session_state["demo_mode"] = demo_mode
                st.session_state["ticker_text"] = ticker_text
                st.session_state["last_scan"] = datetime.now(UTC).isoformat()

            except (TradierAPIError, RuntimeError, ValueError) as error:
                st.error(
                    f"The scan could not be completed with the selected settings. Details: {error}"
                )
                return

    summary = st.session_state["summary"]
    rankings = st.session_state["rankings"]
    symbols = st.session_state["symbols"]
    demo_mode = st.session_state["demo_mode"]

    mode_label = "Demo data" if demo_mode else "Live Tradier analysis"
    st.caption(f"{mode_label} • Last scan: {st.session_state.get('last_scan', 'not available')}")

    render_metrics(summary)

    analysis_columns = st.columns([1.05, 1.35])

    with analysis_columns[0]:
        render_ticker_context(summary, symbols)

    with analysis_columns[1]:
        render_analysis_timeline(summary)

    render_quant_methods()

    result_columns = st.columns([0.9, 1.4])

    with result_columns[0]:
        render_elimination_funnel(summary)

    with result_columns[1]:
        render_top_opportunities(rankings)

    export_columns = [column for column in rankings.columns if column != "details"]
    export_data = rankings[export_columns].to_csv(index=False).encode("utf-8")

    st.download_button(
        "Download ranked results CSV",
        data=export_data,
        file_name="arblens_ranked_results.csv",
        mime="text/csv",
    )

    render_about()


if __name__ == "__main__":
    main()
