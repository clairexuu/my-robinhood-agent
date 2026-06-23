import unittest

from robinhood_agent.providers.polygon import PolygonProvider


class FakePolygonProvider(PolygonProvider):
    def __init__(self):
        super().__init__("test-key")

    def _get(self, path, params):
        if path.startswith("/v2/snapshot"):
            return {"ticker": {"day": {"c": 126.0}}}
        if path.startswith("/v2/aggs/ticker/NVDA"):
            return {
                "results": [
                    {"c": 120.0, "v": 1000, "t": 1781740800000},
                    {"c": 126.0, "v": 2000, "t": 1781827200000},
                ]
            }
        if path.startswith("/v2/aggs/ticker/SPY"):
            return {
                "results": [
                    {"c": 540.0, "v": 3000, "t": 1781740800000},
                    {"c": 543.0, "v": 3200, "t": 1781827200000},
                ]
            }
        if path == "/v2/reference/news":
            return {
                "results": [
                    {
                        "id": "news-1",
                        "title": "NVDA announces product update",
                        "description": "Product update summary.",
                        "published_utc": "2026-06-19T14:30:00Z",
                        "article_url": "https://example.test/news",
                        "insights": [{"ticker": "NVDA", "sentiment": "positive"}],
                    }
                ]
            }
        if path == "/vX/reference/ticker_events":
            return {
                "results": [
                    {
                        "id": "earnings-1",
                        "type": "earnings",
                        "title": "NVDA earnings",
                        "description": "Expected earnings release.",
                        "event_date": "2026-08-20",
                    }
                ]
            }
        raise AssertionError(f"unexpected request {path} {params}")


class PolygonProviderTests(unittest.TestCase):
    def test_fetch_market_data_maps_snapshot_and_bars(self):
        data = FakePolygonProvider().fetch_market_data("NVDA", "SPY")

        self.assertEqual(data.latest_price, 126.0)
        self.assertEqual(data.previous_close, 120.0)
        self.assertEqual(data.benchmark_previous_close, 540.0)
        self.assertEqual(data.average_volume, 1500)

    def test_fetch_news_maps_polygon_news_to_events(self):
        events = FakePolygonProvider().fetch_news("NVDA")

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].source, "polygon_news")
        self.assertEqual(events[0].event_type, "news")
        self.assertEqual(events[0].severity.value, "medium")

    def test_fetch_earnings_calendar_maps_reference_events(self):
        events = FakePolygonProvider().fetch_earnings_calendar("NVDA")

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].source, "polygon_reference")
        self.assertEqual(events[0].event_type, "earnings_calendar")

    def test_fetch_price_history_maps_aggregate_bars(self):
        points = FakePolygonProvider().fetch_price_history("NVDA", "1W")

        self.assertEqual(len(points), 2)
        self.assertEqual(points[-1].close, 126.0)


if __name__ == "__main__":
    unittest.main()
