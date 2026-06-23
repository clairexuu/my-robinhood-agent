from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Union

from robinhood_agent.domain import ResearchEvent, Severity


class JsonNewsProvider:
    def __init__(self, path: Union[str, Path]):
        self.path = Path(path)

    def fetch_news(self, ticker: str) -> List[ResearchEvent]:
        normalized = ticker.upper()
        events = []
        for item in self._read_items():
            if item["ticker"].strip().upper() != normalized:
                continue
            events.append(
                ResearchEvent(
                    id=item["id"],
                    ticker=item["ticker"],
                    source=item["source"],
                    external_id=item.get("external_id"),
                    event_type=item["event_type"],
                    severity=Severity(item["severity"]),
                    title=item["title"],
                    summary=item["summary"],
                    occurred_at=_parse_datetime(item["occurred_at"]),
                    raw_url=item.get("raw_url"),
                )
            )
        return sorted(events, key=lambda event: event.occurred_at)

    def _read_items(self) -> List[dict]:
        if not self.path.exists():
            raise FileNotFoundError(f"JSON news file not found: {self.path}")
        with self.path.open() as handle:
            data = json.load(handle)
        if not isinstance(data, list):
            raise ValueError("JSON news file must contain a list of event objects")
        required = {
            "id",
            "ticker",
            "source",
            "event_type",
            "severity",
            "title",
            "summary",
            "occurred_at",
        }
        for index, item in enumerate(data):
            if not isinstance(item, dict):
                raise ValueError(f"event at index {index} must be an object")
            missing = required - set(item)
            if missing:
                raise ValueError(
                    f"event at index {index} is missing fields: {', '.join(sorted(missing))}"
                )
        return data


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
