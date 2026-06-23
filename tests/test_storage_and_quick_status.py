import sqlite3
import unittest
from datetime import datetime, timezone

from robinhood_agent.agent import evaluate_performance, quick_status
from robinhood_agent.domain import OrderSide, PaperOrder
from robinhood_agent.fixtures import nvda_initial_thesis, nvda_watch_profile
from robinhood_agent.providers import FakeHistoricalPriceProvider
from robinhood_agent.storage import AgentRepository, initialize_database


class StorageAndQuickStatusTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        initialize_database(self.connection)
        self.repository = AgentRepository(self.connection)

    def tearDown(self):
        self.connection.close()

    def test_load_state_returns_empty_state_for_unknown_ticker(self):
        state = self.repository.load_state("NVDA")

        self.assertIsNone(state.watch_profile)
        self.assertIsNone(state.thesis)
        self.assertIsNone(state.ledger.position)
        self.assertEqual(state.ledger.cash, 100_000.0)

    def test_can_save_and_load_latest_thesis(self):
        self.repository.save_watch_profile(nvda_watch_profile())
        self.repository.save_thesis(nvda_initial_thesis())

        state = self.repository.load_state("nvda")

        self.assertEqual(state.watch_profile.ticker, "NVDA")
        self.assertEqual(state.thesis.view.value, "hold")
        self.assertIn("Data center", state.thesis.core_assumptions[1])

    def test_paper_order_updates_position_and_cash(self):
        self.repository.save_watch_profile(nvda_watch_profile())
        order = PaperOrder(
            id="order-1",
            ticker="NVDA",
            side=OrderSide.BUY,
            quantity=2,
            price=100,
            fee=1,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        position = self.repository.record_paper_order(order)
        summary = self.repository.get_ledger_summary("NVDA")

        self.assertEqual(position.quantity, 2)
        self.assertEqual(position.average_cost, 100.5)
        self.assertEqual(summary.cash, 99_799.0)

    def test_quick_status_formats_cached_state_without_external_calls(self):
        self.repository.save_watch_profile(nvda_watch_profile())
        self.repository.save_thesis(nvda_initial_thesis())

        output = quick_status(self.repository, "nvda")

        self.assertIn("NVDA quick status", output)
        self.assertIn("View: HOLD", output)
        self.assertIn("Benchmark: SPY", output)
        self.assertIn("Paper ledger", output)

    def test_quick_status_includes_latest_performance_snapshot(self):
        self.repository.save_watch_profile(nvda_watch_profile())
        self.repository.save_thesis(nvda_initial_thesis())
        evaluate_performance(
            repository=self.repository,
            ticker="NVDA",
            window="1W",
            price_provider=FakeHistoricalPriceProvider(),
        )

        state = self.repository.load_state("NVDA")
        output = quick_status(self.repository, "NVDA")

        self.assertIsNotNone(state.latest_performance_snapshot)
        self.assertIn("Latest performance: 1W absolute 2.80%", output)
        self.assertIn("relative 2.25%", output)


if __name__ == "__main__":
    unittest.main()
