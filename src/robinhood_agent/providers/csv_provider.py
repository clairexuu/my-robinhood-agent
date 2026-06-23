from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Union

from .base import MarketData, PricePoint


@dataclass(frozen=True)
class CsvPriceRow:
    ticker: str
    occurred_at: datetime
    close: float
    volume: int


class CsvPriceProvider:
    def __init__(self, path: Union[str, Path]):
        self.path = Path(path)

    def fetch_market_data(self, ticker: str, benchmark: str) -> MarketData:
        ticker_rows = self._rows_for(ticker)
        benchmark_rows = self._rows_for(benchmark)
        if len(ticker_rows) < 2:
            raise ValueError(f"{ticker.upper()} needs at least two CSV price rows")
        if len(benchmark_rows) < 2:
            raise ValueError(f"{benchmark.upper()} needs at least two CSV price rows")

        latest = ticker_rows[-1]
        previous = ticker_rows[-2]
        benchmark_latest = benchmark_rows[-1]
        benchmark_previous = benchmark_rows[-2]
        average_volume = round(sum(row.volume for row in ticker_rows) / len(ticker_rows))

        return MarketData(
            ticker=ticker.upper(),
            benchmark=benchmark.upper(),
            latest_price=latest.close,
            previous_close=previous.close,
            benchmark_latest_price=benchmark_latest.close,
            benchmark_previous_close=benchmark_previous.close,
            volume=latest.volume,
            average_volume=average_volume,
        )

    def fetch_price_history(self, ticker: str, window: str) -> List[PricePoint]:
        rows = self._rows_for(ticker)
        count = _window_to_count(window)
        selected = rows[-count:] if count else rows
        if len(selected) < 2:
            raise ValueError(f"{ticker.upper()} needs at least two CSV price rows for {window}")
        return [
            PricePoint(occurred_at=row.occurred_at, close=row.close)
            for row in selected
        ]

    def _rows_for(self, ticker: str) -> List[CsvPriceRow]:
        normalized = ticker.upper()
        rows = self._read_rows().get(normalized, [])
        return sorted(rows, key=lambda row: row.occurred_at)

    def _read_rows(self) -> Dict[str, List[CsvPriceRow]]:
        if not self.path.exists():
            raise FileNotFoundError(f"CSV price file not found: {self.path}")

        grouped: Dict[str, List[CsvPriceRow]] = {}
        with self.path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            required = {"ticker", "date", "close", "volume"}
            missing = required - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"CSV price file is missing columns: {', '.join(sorted(missing))}")
            for row in reader:
                price_row = CsvPriceRow(
                    ticker=row["ticker"].strip().upper(),
                    occurred_at=_parse_date(row["date"]),
                    close=float(row["close"]),
                    volume=int(row["volume"]),
                )
                grouped.setdefault(price_row.ticker, []).append(price_row)
        return grouped


def _parse_date(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.strip())
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _window_to_count(window: str) -> int:
    normalized = window.upper()
    if normalized == "1D":
        return 2
    if normalized == "1W":
        return 5
    if normalized == "1M":
        return 22
    return 0
