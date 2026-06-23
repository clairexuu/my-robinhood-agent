import unittest
from pathlib import Path

from robinhood_agent.providers import JsonNewsProvider


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "news.json"


class JsonProviderTests(unittest.TestCase):
    def test_fetch_news_filters_by_ticker_and_sorts_by_time(self):
        provider = JsonNewsProvider(FIXTURE_PATH)

        events = provider.fetch_news("NVDA")

        self.assertEqual([event.id for event in events], ["json-news-nvda-low", "json-news-nvda-critical"])
        self.assertEqual(events[0].severity.value, "low")
        self.assertEqual(events[1].severity.value, "critical")
        self.assertIsNotNone(events[0].occurred_at.tzinfo)

    def test_missing_json_file_raises_file_not_found(self):
        provider = JsonNewsProvider(Path(__file__).parent / "fixtures" / "missing-news.json")

        with self.assertRaises(FileNotFoundError):
            provider.fetch_news("NVDA")


if __name__ == "__main__":
    unittest.main()
