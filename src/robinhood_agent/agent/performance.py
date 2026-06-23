from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List
from uuid import uuid4

from robinhood_agent.domain import PerformanceSnapshot
from robinhood_agent.providers import HistoricalPriceProvider, PricePoint
from robinhood_agent.storage import AgentRepository


@dataclass(frozen=True)
class PerformanceEvaluation:
    snapshot: PerformanceSnapshot
    position_quantity: float
    start_price: float
    end_price: float
    benchmark_start_price: float
    benchmark_end_price: float


def evaluate_performance(
    repository: AgentRepository,
    ticker: str,
    window: str,
    price_provider: HistoricalPriceProvider,
) -> PerformanceEvaluation:
    normalized_ticker = ticker.upper()
    loaded = repository.load_state(normalized_ticker)
    if loaded.watch_profile is None:
        raise ValueError(f"{normalized_ticker} has no watch profile")

    position_quantity = loaded.ledger.position.quantity if loaded.ledger.position else 0.0
    ticker_prices = price_provider.fetch_price_history(normalized_ticker, window)
    benchmark_prices = price_provider.fetch_price_history(loaded.watch_profile.benchmark, window)
    _require_enough_prices(ticker_prices, normalized_ticker)
    _require_enough_prices(benchmark_prices, loaded.watch_profile.benchmark)

    absolute_return = _simple_return(ticker_prices)
    benchmark_return = _simple_return(benchmark_prices)
    snapshot = PerformanceSnapshot(
        id=str(uuid4()),
        ticker=normalized_ticker,
        window=window,
        absolute_return=round(absolute_return, 6),
        benchmark_return=round(benchmark_return, 6),
        max_drawdown=round(_max_drawdown(ticker_prices), 6),
        created_at=datetime.now(timezone.utc),
    )
    repository.save_performance_snapshot(snapshot)

    return PerformanceEvaluation(
        snapshot=snapshot,
        position_quantity=position_quantity,
        start_price=ticker_prices[0].close,
        end_price=ticker_prices[-1].close,
        benchmark_start_price=benchmark_prices[0].close,
        benchmark_end_price=benchmark_prices[-1].close,
    )


def format_performance_evaluation(evaluation: PerformanceEvaluation) -> str:
    snapshot = evaluation.snapshot
    return "\n".join(
        [
            f"{snapshot.ticker} performance {snapshot.window}",
            f"Position quantity: {evaluation.position_quantity:g}",
            f"Price: ${evaluation.start_price:,.2f} -> ${evaluation.end_price:,.2f}",
            (
                "Benchmark price: "
                f"${evaluation.benchmark_start_price:,.2f} -> "
                f"${evaluation.benchmark_end_price:,.2f}"
            ),
            f"Absolute return: {snapshot.absolute_return:.2%}",
            f"Benchmark return: {snapshot.benchmark_return:.2%}",
            f"Relative return: {snapshot.relative_return:.2%}",
            f"Max drawdown: {snapshot.max_drawdown:.2%}",
        ]
    )


def _require_enough_prices(prices: List[PricePoint], ticker: str) -> None:
    if len(prices) < 2:
        raise ValueError(f"{ticker} needs at least two price points")


def _simple_return(prices: List[PricePoint]) -> float:
    return prices[-1].close / prices[0].close - 1.0


def _max_drawdown(prices: List[PricePoint]) -> float:
    peak = prices[0].close
    max_drawdown = 0.0
    for point in prices:
        peak = max(peak, point.close)
        drawdown = point.close / peak - 1.0
        max_drawdown = min(max_drawdown, drawdown)
    return max_drawdown
