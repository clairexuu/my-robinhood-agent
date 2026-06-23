from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

from robinhood_agent.domain import ResearchEvent, Severity

from .base import MarketData, PricePoint


class FakeMarketDataProvider:
    def fetch_market_data(self, ticker: str, benchmark: str) -> MarketData:
        return MarketData(
            ticker=ticker.upper(),
            benchmark=benchmark.upper(),
            latest_price=128.50,
            previous_close=125.00,
            benchmark_latest_price=545.00,
            benchmark_previous_close=542.00,
            volume=58_000_000,
            average_volume=42_000_000,
        )


class FakeNewsProvider:
    def fetch_news(self, ticker: str) -> List[ResearchEvent]:
        normalized = ticker.upper()
        return [
            ResearchEvent(
                id=f"fake-news-{normalized}-datacenter-demand",
                ticker=normalized,
                source="fake_news",
                external_id=f"{normalized}-datacenter-demand",
                event_type="news",
                severity=Severity.HIGH,
                title=f"{normalized} data center demand remains firm",
                summary=(
                    "Channel checks suggest continued demand for AI accelerators, "
                    "with near-term supply still tight."
                ),
                occurred_at=datetime.now(timezone.utc),
                raw_url=None,
            )
        ]


class FakeLowSeverityNewsProvider:
    def fetch_news(self, ticker: str) -> List[ResearchEvent]:
        normalized = ticker.upper()
        return [
            ResearchEvent(
                id=f"fake-news-{normalized}-minor-note",
                ticker=normalized,
                source="fake_news",
                external_id=f"{normalized}-minor-note",
                event_type="news",
                severity=Severity.LOW,
                title=f"{normalized} minor product note",
                summary="A routine product update was published with no obvious thesis impact.",
                occurred_at=datetime.now(timezone.utc),
                raw_url=None,
            )
        ]


class FakeHistoricalPriceProvider:
    def fetch_price_history(self, ticker: str, window: str) -> List[PricePoint]:
        now = datetime.now(timezone.utc)
        normalized = ticker.upper()
        if normalized == "SPY":
            closes = [542.0, 543.5, 545.0]
        else:
            closes = [125.0, 122.0, 128.5]
        return [
            PricePoint(occurred_at=now - timedelta(days=len(closes) - index - 1), close=close)
            for index, close in enumerate(closes)
        ]
