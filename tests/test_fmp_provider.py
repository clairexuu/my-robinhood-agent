import unittest

from robinhood_agent.providers.fmp import FinancialModelingPrepProvider


class FakeFmpClient:
    def get_json_or_list(self, path, params=None):
        self.path = path
        self.params = params
        return [
            {
                "symbol": "NVDA",
                "quarter": 1,
                "year": 2026,
                "date": "2026-05-20 17:00:00",
                "content": "Management discussed data center demand and supply constraints.",
            }
        ]


class FinancialModelingPrepProviderTests(unittest.TestCase):
    def test_fetch_transcripts_maps_fmp_response(self):
        client = FakeFmpClient()
        provider = FinancialModelingPrepProvider("test-key", client=client)

        events = provider.fetch_transcripts("NVDA")

        self.assertEqual(client.path, "/earning-call-transcript")
        self.assertEqual(client.params["symbol"], "NVDA")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].source, "financial_modeling_prep")
        self.assertEqual(events[0].event_type, "earnings_transcript")
        self.assertIn("data center demand", events[0].summary)


if __name__ == "__main__":
    unittest.main()
