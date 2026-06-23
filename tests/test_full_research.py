import sqlite3
import unittest

from robinhood_agent.agent import format_full_research_result, full_research
from robinhood_agent.analysis import FakeImpactAnalyzer
from robinhood_agent.fixtures import nvda_initial_thesis, nvda_watch_profile
from robinhood_agent.providers import FakeMarketDataProvider, FakeNewsProvider
from robinhood_agent.storage import AgentRepository, initialize_database


class FullResearchTests(unittest.TestCase):
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

    def test_full_research_updates_thesis_and_persists_update(self):
        result = full_research(
            repository=self.repository,
            ticker="nvda",
            market_data_provider=FakeMarketDataProvider(),
            news_provider=FakeNewsProvider(),
            impact_analyzer=FakeImpactAnalyzer(),
        )

        loaded = self.repository.load_state("NVDA")

        self.assertEqual(result.inserted_event_count, 1)
        self.assertEqual(result.impact_analysis.severity.value, "high")
        self.assertEqual(loaded.thesis.confidence, 0.60)
        self.assertEqual(loaded.latest_research_update.confidence, 0.60)
        self.assertEqual(result.paper_intent.notional, 10_000)
        self.assertEqual(result.paper_intent.side.value, "buy")
        self.assertIn("Confidence changed", loaded.latest_research_update.key_changes[-1])

    def test_full_research_dedupes_repeated_fake_news(self):
        full_research(
            repository=self.repository,
            ticker="NVDA",
            market_data_provider=FakeMarketDataProvider(),
            news_provider=FakeNewsProvider(),
            impact_analyzer=FakeImpactAnalyzer(),
        )
        result = full_research(
            repository=self.repository,
            ticker="NVDA",
            market_data_provider=FakeMarketDataProvider(),
            news_provider=FakeNewsProvider(),
            impact_analyzer=FakeImpactAnalyzer(),
        )

        event_count = self.connection.execute("SELECT COUNT(*) AS count FROM research_events").fetchone()[
            "count"
        ]

        self.assertEqual(result.inserted_event_count, 0)
        self.assertEqual(event_count, 1)

    def test_full_research_output_contains_operational_summary(self):
        result = full_research(
            repository=self.repository,
            ticker="NVDA",
            market_data_provider=FakeMarketDataProvider(),
            news_provider=FakeNewsProvider(),
            impact_analyzer=FakeImpactAnalyzer(),
        )

        output = format_full_research_result(result)

        self.assertIn("NVDA full research", output)
        self.assertIn("Events processed: 1 (1 new)", output)
        self.assertIn("Impact severity: high", output)
        self.assertIn("Paper intent: BUY", output)
        self.assertIn("not a live Robinhood order", output)


if __name__ == "__main__":
    unittest.main()
