import sqlite3
import unittest

from robinhood_agent.agent import (
    evaluate_performance,
    execute_paper_trade,
    format_performance_evaluation,
    trade_preview,
)
from robinhood_agent.domain import OrderSide
from robinhood_agent.fixtures import nvda_initial_thesis, nvda_watch_profile
from robinhood_agent.providers import FakeHistoricalPriceProvider, FakeMarketDataProvider
from robinhood_agent.storage import AgentRepository, initialize_database


class PerformanceTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        initialize_database(self.connection)
        self.repository = AgentRepository(self.connection)
        self.repository.save_watch_profile(nvda_watch_profile())
        self.repository.save_thesis(nvda_initial_thesis())

    def tearDown(self):
        self.connection.close()

    def test_evaluate_performance_computes_and_persists_snapshot(self):
        buy_preview = trade_preview(
            repository=self.repository,
            ticker="NVDA",
            side=OrderSide.BUY,
            amount=1_285,
            quantity=None,
            market_data_provider=FakeMarketDataProvider(),
        )
        execute_paper_trade(self.repository, buy_preview)

        evaluation = evaluate_performance(
            repository=self.repository,
            ticker="NVDA",
            window="1W",
            price_provider=FakeHistoricalPriceProvider(),
        )
        loaded = self.repository.get_latest_performance_snapshot("NVDA", "1W")

        self.assertEqual(evaluation.position_quantity, 10)
        self.assertEqual(evaluation.snapshot.absolute_return, 0.028)
        self.assertEqual(evaluation.snapshot.benchmark_return, 0.005535)
        self.assertEqual(evaluation.snapshot.max_drawdown, -0.024)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.relative_return, evaluation.snapshot.relative_return)

    def test_format_performance_evaluation_includes_relative_return(self):
        evaluation = evaluate_performance(
            repository=self.repository,
            ticker="NVDA",
            window="1W",
            price_provider=FakeHistoricalPriceProvider(),
        )

        output = format_performance_evaluation(evaluation)

        self.assertIn("NVDA performance 1W", output)
        self.assertIn("Absolute return: 2.80%", output)
        self.assertIn("Benchmark return: 0.55%", output)
        self.assertIn("Relative return: 2.25%", output)
        self.assertIn("Max drawdown: -2.40%", output)

    def test_evaluate_performance_requires_watch_profile(self):
        with self.assertRaises(ValueError):
            evaluate_performance(
                repository=self.repository,
                ticker="MSFT",
                window="1W",
                price_provider=FakeHistoricalPriceProvider(),
            )


if __name__ == "__main__":
    unittest.main()
