from __future__ import annotations

from typing import List, Optional

from robinhood_agent.domain import ResearchEvent

from .base import EarningsCalendarProvider, FilingProvider, NewsProvider, TranscriptProvider


class CompositeResearchEventProvider:
    def __init__(
        self,
        news_provider: NewsProvider,
        filing_provider: Optional[FilingProvider] = None,
        earnings_calendar_provider: Optional[EarningsCalendarProvider] = None,
        transcript_provider: Optional[TranscriptProvider] = None,
    ):
        self.news_provider = news_provider
        self.filing_provider = filing_provider
        self.earnings_calendar_provider = earnings_calendar_provider
        self.transcript_provider = transcript_provider

    def fetch_news(self, ticker: str) -> List[ResearchEvent]:
        events = list(self.news_provider.fetch_news(ticker))
        if self.filing_provider is not None:
            events.extend(self.filing_provider.fetch_filings(ticker))
        if self.earnings_calendar_provider is not None:
            events.extend(self.earnings_calendar_provider.fetch_earnings_calendar(ticker))
        if self.transcript_provider is not None:
            events.extend(self.transcript_provider.fetch_transcripts(ticker))
        return sorted(events, key=lambda event: event.occurred_at, reverse=True)
