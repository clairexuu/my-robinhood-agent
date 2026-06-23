from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Dict, Iterable, List, Optional

from robinhood_agent.domain import ResearchEvent, Severity

from .http import HttpJsonClient


class FinancialModelingPrepProvider:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://financialmodelingprep.com/stable",
        timeout_seconds: float = 30.0,
        client: Optional[HttpJsonClient] = None,
    ):
        if not api_key:
            raise ValueError("api_key is required")
        self.api_key = api_key
        self.client = client or HttpJsonClient(base_url, timeout_seconds=timeout_seconds)

    def fetch_transcripts(self, ticker: str) -> List[ResearchEvent]:
        data = self._get(
            "/earning-call-transcript",
            {
                "symbol": ticker.upper(),
                "limit": "4",
            },
        )
        items = _items(data)
        return [
            _transcript_event(ticker.upper(), item)
            for item in items
            if isinstance(item, dict)
        ]

    def _get(self, path: str, params: Dict[str, str]) -> Any:
        query = dict(params)
        query["apikey"] = self.api_key
        return self.client.get_json_or_list(path, query)


def _items(data: Any) -> Iterable[Any]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        value = data.get("data") or data.get("results") or data.get("transcripts")
        if isinstance(value, list):
            return value
    return []


def _transcript_event(ticker: str, item: Dict[str, Any]) -> ResearchEvent:
    date_value = str(item.get("date") or item.get("quarterDate") or "")
    quarter = item.get("quarter")
    year = item.get("year")
    title = str(item.get("title") or f"{ticker} earnings call transcript")
    if quarter and year:
        title = f"{ticker} Q{quarter} {year} earnings call transcript"
    content = str(item.get("content") or item.get("transcript") or "")
    summary = content[:500].strip() or title
    external_id = str(item.get("id") or f"{ticker}-{date_value}-{quarter}-{year}")
    return ResearchEvent(
        id=f"fmp-transcript-{_stable_id(external_id)}",
        ticker=ticker,
        source="financial_modeling_prep",
        external_id=external_id,
        event_type="earnings_transcript",
        severity=Severity.MEDIUM,
        title=title,
        summary=summary,
        occurred_at=_parse_datetime(date_value),
        raw_url=None,
    )


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


def _stable_id(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()[:24]
