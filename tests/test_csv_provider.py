import unittest
from pathlib import Path

from robinhood_agent.providers import CsvPriceProvider


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "prices.csv"


class CsvProviderTests(unittest.TestCase):
    def test_fetch_market_data_uses_latest_two_rows(self):
        provider = CsvPriceProvider(FIXTURE_PATH)

        market_data = provider.fetch_market_data("NVDA", "SPY")

        self.assertEqual(market_data.latest_price, 126.0)
        self.assertEqual(market_data.previous_close, 123.0)
        self.assertEqual(market_data.benchmark_latest_price, 543.0)
        self.assertEqual(market_data.benchmark_previous_close, 542.0)
        self.assertEqual(market_data.volume, 44_000_000)
        self.assertEqual(market_data.average_volume, 42_000_000)
        self.assertAlmostEqual(market_data.price_change_pct, 0.0243902439)

    def test_fetch_price_history_respects_window(self):
        provider = CsvPriceProvider(FIXTURE_PATH)

        one_day = provider.fetch_price_history("NVDA", "1D")
        one_week = provider.fetch_price_history("NVDA", "1W")

        self.assertEqual([point.close for point in one_day], [123.0, 126.0])
        self.assertEqual([point.close for point in one_week], [120.0, 121.0, 119.0, 123.0, 126.0])

    def test_fetch_price_history_requires_enough_rows(self):
        provider = CsvPriceProvider(FIXTURE_PATH)

        with self.assertRaises(ValueError):
            provider.fetch_price_history("MSFT", "1D")

    def test_missing_csv_file_raises_file_not_found(self):
        provider = CsvPriceProvider(Path(__file__).parent / "fixtures" / "missing.csv")

        with self.assertRaises(FileNotFoundError):
            provider.fetch_market_data("NVDA", "SPY")


if __name__ == "__main__":
    unittest.main()
