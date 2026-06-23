import unittest
from datetime import datetime, timezone

from robinhood_agent.domain import ResearchEvent, Severity
from robinhood_agent.providers import CompositeResearchEventProvider


def utc_datetime(year, month, day):
    return datetime(year, month, day, tzinfo=timezone.utc)


def event(event_id, source, occurred_at):
    return ResearchEvent(
        id=event_id,
        ticker="NVDA",
        source=source,
        external_id=event_id,
        event_type=source,
        severity=Severity.LOW,
        title=source,
        summary=source,
        occurred_at=occurred_at,
    )


class NewsSource:
    def fetch_news(self, ticker):
        return [event("news", "news", utc_datetime(2026, 6, 19))]


class FilingSource:
    def fetch_filings(self, ticker):
        return [event("filing", "filing", utc_datetime(2026, 6, 18))]


class CalendarSource:
    def fetch_earnings_calendar(self, ticker):
        return [event("calendar", "calendar", utc_datetime(2026, 8, 20))]


class TranscriptSource:
    def fetch_transcripts(self, ticker):
        return [event("transcript", "transcript", utc_datetime(2026, 5, 20))]


class CompositeResearchEventProviderTests(unittest.TestCase):
    def test_fetch_news_combines_and_sorts_all_research_events(self):
        provider = CompositeResearchEventProvider(
            news_provider=NewsSource(),
            filing_provider=FilingSource(),
            earnings_calendar_provider=CalendarSource(),
            transcript_provider=TranscriptSource(),
        )

        events = provider.fetch_news("NVDA")

        self.assertEqual(
            [item.id for item in events],
            ["calendar", "news", "filing", "transcript"],
        )


if __name__ == "__main__":
    unittest.main()
