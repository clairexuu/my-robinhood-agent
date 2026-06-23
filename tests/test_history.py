import sqlite3
import unittest
import json

from robinhood_agent.agent import (
    apply_latest_paper_intent,
    evaluate_performance,
    format_history_json,
    format_history_report,
    history_report_to_dict,
    full_research,
    load_history,
)
from robinhood_agent.analysis import FakeImpactAnalyzer
from robinhood_agent.fixtures import nvda_initial_thesis, nvda_watch_profile
from robinhood_agent.providers import FakeHistoricalPriceProvider, FakeMarketDataProvider, FakeNewsProvider
from robinhood_agent.storage import AgentRepository, initialize_database


class HistoryTests(unittest.TestCase):
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

    def _populate_history(self):
        full_research(
            repository=self.repository,
            ticker="NVDA",
            market_data_provider=FakeMarketDataProvider(),
            news_provider=FakeNewsProvider(),
            impact_analyzer=FakeImpactAnalyzer(),
        )
        apply_latest_paper_intent(
            repository=self.repository,
            ticker="NVDA",
            market_data_provider=FakeMarketDataProvider(),
        )
        evaluate_performance(
            repository=self.repository,
            ticker="NVDA",
            window="1W",
            price_provider=FakeHistoricalPriceProvider(),
        )

    def test_load_history_returns_all_audit_sections(self):
        self._populate_history()

        report = load_history(self.repository, "NVDA")

        self.assertEqual(len(report.events), 1)
        self.assertEqual(len(report.updates), 1)
        self.assertEqual(len(report.orders), 1)
        self.assertEqual(len(report.performance_snapshots), 1)
        self.assertEqual(report.orders[0].research_update_id, report.updates[0].id)

    def test_load_history_filters_by_kind(self):
        self._populate_history()

        report = load_history(self.repository, "NVDA", kind="orders")

        self.assertEqual(len(report.events), 0)
        self.assertEqual(len(report.updates), 0)
        self.assertEqual(len(report.orders), 1)
        self.assertEqual(len(report.performance_snapshots), 0)

    def test_format_history_report_prints_sections(self):
        self._populate_history()

        output = format_history_report(load_history(self.repository, "NVDA"))

        self.assertIn("NVDA history", output)
        self.assertIn("Events:", output)
        self.assertIn("Research updates:", output)
        self.assertIn("Paper orders:", output)
        self.assertIn("Performance snapshots:", output)
        self.assertIn("linked_update=", output)

    def test_history_report_to_dict_preserves_audit_fields(self):
        self._populate_history()

        data = history_report_to_dict(load_history(self.repository, "NVDA"))

        self.assertEqual(data["ticker"], "NVDA")
        self.assertEqual(data["events"][0]["severity"], "high")
        self.assertEqual(data["research_updates"][0]["view"], "hold")
        self.assertEqual(
            data["paper_orders"][0]["research_update_id"],
            data["research_updates"][0]["id"],
        )
        self.assertIn("relative_return", data["performance_snapshots"][0])

    def test_format_history_json_outputs_parseable_json(self):
        self._populate_history()

        payload = format_history_json(load_history(self.repository, "NVDA"))
        data = json.loads(payload)

        self.assertEqual(data["ticker"], "NVDA")
        self.assertEqual(len(data["paper_orders"]), 1)

    def test_format_history_report_handles_empty_history(self):
        output = format_history_report(load_history(self.repository, "NVDA"))

        self.assertIn("No history found.", output)

    def test_load_history_rejects_non_positive_limit(self):
        with self.assertRaises(ValueError):
            load_history(self.repository, "NVDA", limit=0)


if __name__ == "__main__":
    unittest.main()
