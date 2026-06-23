import unittest

from robinhood_agent.providers.sec_edgar import SecEdgarProvider


class FakeJsonClient:
    def __init__(self, data):
        self.data = data

    def get_json(self, path, params=None):
        return self.data[path]

    def get_json_absolute(self, url):
        return self.data[url]


class SecEdgarProviderTests(unittest.TestCase):
    def test_fetch_filings_maps_recent_material_filings(self):
        provider = SecEdgarProvider(
            user_agent="agent@example.test",
            client=FakeJsonClient(
                {
                    "/submissions/CIK0001045810.json": {
                        "filings": {
                            "recent": {
                                "form": ["8-K", "4"],
                                "accessionNumber": ["0001045810-26-000001", "0001045810-26-000002"],
                                "filingDate": ["2026-06-19", "2026-06-18"],
                                "reportDate": ["2026-06-19", "2026-06-18"],
                                "primaryDocument": ["nvda-8k.htm", "xslF345X05/doc.xml"],
                            }
                        }
                    }
                }
            ),
            tickers_client=FakeJsonClient(
                {
                    "https://www.sec.gov/files/company_tickers.json": {
                        "0": {"ticker": "NVDA", "cik_str": 1045810}
                    }
                }
            ),
        )

        events = provider.fetch_filings("NVDA")

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].source, "sec_edgar")
        self.assertEqual(events[0].event_type, "sec_filing")
        self.assertEqual(events[0].severity.value, "high")
        self.assertIn("Archives/edgar/data/1045810", events[0].raw_url)


if __name__ == "__main__":
    unittest.main()
