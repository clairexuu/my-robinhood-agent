from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Protocol

from robinhood_agent.domain import ResearchEvent


@dataclass(frozen=True)
class MarketData:
    ticker: str
    benchmark: str
    latest_price: float
    previous_close: float
    benchmark_latest_price: float
    benchmark_previous_close: float
    volume: int
    average_volume: int

    @property
    def price_change_pct(self) -> float:
        if self.previous_close == 0:
            return 0.0
        return (self.latest_price - self.previous_close) / self.previous_close

    @property
    def benchmark_change_pct(self) -> float:
        if self.benchmark_previous_close == 0:
            return 0.0
        return (self.benchmark_latest_price - self.benchmark_previous_close) / self.benchmark_previous_close

    @property
    def relative_change_pct(self) -> float:
        return self.price_change_pct - self.benchmark_change_pct


class MarketDataProvider(Protocol):
    def fetch_market_data(self, ticker: str, benchmark: str) -> MarketData:
        ...


class NewsProvider(Protocol):
    def fetch_news(self, ticker: str) -> List[ResearchEvent]:
        ...


class FilingProvider(Protocol):
    def fetch_filings(self, ticker: str) -> List[ResearchEvent]:
        ...


class EarningsCalendarProvider(Protocol):
    def fetch_earnings_calendar(self, ticker: str) -> List[ResearchEvent]:
        ...


class TranscriptProvider(Protocol):
    def fetch_transcripts(self, ticker: str) -> List[ResearchEvent]:
        ...


@dataclass(frozen=True)
class PricePoint:
    occurred_at: datetime
    close: float

    def __post_init__(self) -> None:
        if self.close <= 0:
            raise ValueError("close must be positive")


class HistoricalPriceProvider(Protocol):
    def fetch_price_history(self, ticker: str, window: str) -> List[PricePoint]:
        ...
