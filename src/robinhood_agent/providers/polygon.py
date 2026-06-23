from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from typing import Any, Dict, Iterable, List, Optional

from robinhood_agent.domain import ResearchEvent, Severity

from .base import MarketData, PricePoint
from .http import HttpJsonClient


class PolygonProvider:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.polygon.io",
        timeout_seconds: float = 30.0,
        client: Optional[HttpJsonClient] = None,
    ):
        if not api_key:
            raise ValueError("api_key is required")
        self.api_key = api_key
        self.client = client or HttpJsonClient(base_url, timeout_seconds=timeout_seconds)

    def fetch_market_data(self, ticker: str, benchmark: str) -> MarketData:
        quote = self._latest_snapshot(ticker)
        benchmark_quote = self._latest_snapshot(benchmark)
        bars = self._daily_bars(ticker, days=30)
        latest_bar = bars[-1]
        prior_bar = bars[-2] if len(bars) >= 2 else latest_bar
        benchmark_bars = self._daily_bars(benchmark, days=5)
        latest_benchmark_bar = benchmark_bars[-1]
        prior_benchmark_bar = benchmark_bars[-2] if len(benchmark_bars) >= 2 else latest_benchmark_bar
        average_volume = int(sum(bar["volume"] for bar in bars) / len(bars)) if bars else 0
        return MarketData(
            ticker=ticker.upper(),
            benchmark=benchmark.upper(),
            latest_price=quote or latest_bar["close"],
            previous_close=prior_bar["close"],
            benchmark_latest_price=benchmark_quote or latest_benchmark_bar["close"],
            benchmark_previous_close=prior_benchmark_bar["close"],
            volume=int(latest_bar["volume"]),
            average_volume=average_volume,
        )

    def fetch_news(self, ticker: str) -> List[ResearchEvent]:
        data = self._get(
            "/v2/reference/news",
            {
                "ticker": ticker.upper(),
                "order": "desc",
                "sort": "published_utc",
                "limit": "20",
            },
        )
        return [
            _news_event(ticker.upper(), item)
            for item in _results(data)
            if isinstance(item, dict)
        ]

    def fetch_earnings_calendar(self, ticker: str) -> List[ResearchEvent]:
        data = self._get(
            "/vX/reference/ticker_events",
            {
                "ticker": ticker.upper(),
                "types": "earnings",
                "limit": "10",
            },
        )
        return [
            _calendar_event(ticker.upper(), item)
            for item in _results(data)
            if isinstance(item, dict)
        ]

    def fetch_price_history(self, ticker: str, window: str) -> List[PricePoint]:
        days = {"1D": 3, "1W": 10, "1M": 35}.get(window, 10)
        bars = self._daily_bars(ticker, days=days)
        points = [
            PricePoint(
                occurred_at=datetime.fromtimestamp(bar["timestamp"] / 1000, tz=timezone.utc),
                close=bar["close"],
            )
            for bar in bars
        ]
        if len(points) < 2:
            raise ValueError(f"Polygon returned insufficient price history for {ticker}")
        return points

    def _latest_snapshot(self, ticker: str) -> Optional[float]:
        try:
            data = self._get(f"/v2/snapshot/locale/us/markets/stocks/tickers/{ticker.upper()}", {})
        except ValueError:
            return None
        ticker_data = data.get("ticker")
        if not isinstance(ticker_data, dict):
            return None
        day = ticker_data.get("day")
        if isinstance(day, dict):
            close = _optional_float(day.get("c"))
            if close is not None:
                return close
        last_trade = ticker_data.get("lastTrade")
        if isinstance(last_trade, dict):
            return _optional_float(last_trade.get("p"))
        return None

    def _daily_bars(self, ticker: str, days: int) -> List[Dict[str, float]]:
        end = date.today()
        start = end - timedelta(days=max(days * 3, 10))
        data = self._get(
            f"/v2/aggs/ticker/{ticker.upper()}/range/1/day/{start.isoformat()}/{end.isoformat()}",
            {
                "adjusted": "true",
                "sort": "asc",
                "limit": str(max(days * 2, 10)),
            },
        )
        bars = []
        for item in _results(data):
            if not isinstance(item, dict):
                continue
            close = _optional_float(item.get("c"))
            volume = _optional_float(item.get("v"))
            timestamp = _optional_float(item.get("t"))
            if close is None or volume is None or timestamp is None:
                continue
            bars.append({"close": close, "volume": volume, "timestamp": timestamp})
        if not bars:
            raise ValueError(f"Polygon returned no daily bars for {ticker}")
        return bars[-days:]

    def _get(self, path: str, params: Dict[str, str]) -> Dict[str, Any]:
        query = dict(params)
        query["apiKey"] = self.api_key
        data = self.client.get_json(path, query)
        status = str(data.get("status", "")).upper()
        if status in {"ERROR", "AUTH_ERROR"}:
            raise ValueError(f"Polygon error: {data.get('error') or data.get('message')}")
        return data


def _news_event(ticker: str, item: Dict[str, Any]) -> ResearchEvent:
    title = str(item.get("title") or "Untitled Polygon news item")
    summary = str(item.get("description") or title)
    published_at = _parse_datetime(str(item.get("published_utc") or ""))
    url = item.get("article_url")
    external_id = str(item.get("id") or url or f"{ticker}-{published_at.isoformat()}-{title}")
    return ResearchEvent(
        id=f"polygon-news-{_stable_id(external_id)}",
        ticker=ticker,
        source="polygon_news",
        external_id=external_id,
        event_type="news",
        severity=_news_severity(item),
        title=title,
        summary=summary,
        occurred_at=published_at,
        raw_url=str(url) if url else None,
    )


def _calendar_event(ticker: str, item: Dict[str, Any]) -> ResearchEvent:
    event_id = str(item.get("id") or item.get("event_id") or item)
    event_type = str(item.get("type") or item.get("event_type") or "earnings")
    title = str(item.get("title") or f"{ticker} {event_type}")
    summary = str(item.get("description") or item.get("notes") or title)
    occurred_at = _parse_reference_event_time(item)
    return ResearchEvent(
        id=f"polygon-calendar-{_stable_id(event_id)}",
        ticker=ticker,
        source="polygon_reference",
        external_id=event_id,
        event_type="earnings_calendar",
        severity=Severity.MEDIUM,
        title=title,
        summary=summary,
        occurred_at=occurred_at,
        raw_url=None,
    )


def _results(data: Dict[str, Any]) -> Iterable[Any]:
    results = data.get("results", [])
    return results if isinstance(results, list) else []


def _news_severity(item: Dict[str, Any]) -> Severity:
    insights = item.get("insights")
    if isinstance(insights, list) and insights:
        sentiments = {
            str(insight.get("sentiment", "")).lower()
            for insight in insights
            if isinstance(insight, dict)
        }
        if {"positive", "negative"} & sentiments:
            return Severity.MEDIUM
    return Severity.LOW


def _parse_reference_event_time(item: Dict[str, Any]) -> datetime:
    for key in ("event_date", "date", "start_date", "timestamp"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return _parse_datetime(value)
    return datetime.now(timezone.utc)


def _parse_datetime(value: str) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(f"{value}T00:00:00+00:00")
        except ValueError:
            return datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _optional_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _stable_id(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()[:24]
