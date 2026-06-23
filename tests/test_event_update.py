import sqlite3
import unittest
from pathlib import Path

from robinhood_agent.agent import event_update, format_event_update_result
from robinhood_agent.analysis import FakeImpactAnalyzer
from robinhood_agent.fixtures import nvda_initial_thesis, nvda_watch_profile
from robinhood_agent.providers import (
    FakeLowSeverityNewsProvider,
    FakeMarketDataProvider,
    FakeNewsProvider,
    JsonNewsProvider,
)
from robinhood_agent.storage import AgentRepository, initialize_database


class CountingImpactAnalyzer(FakeImpactAnalyzer):
    def __init__(self):
        self.call_count = 0

    def analyze(self, thesis, events, signals):
        self.call_count += 1
        return super().analyze(thesis, events, signals)


class EventUpdateTests(unittest.TestCase):
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

    def test_low_severity_event_is_recorded_without_analysis(self):
        analyzer = CountingImpactAnalyzer()

        result = event_update(
            repository=self.repository,
            ticker="NVDA",
            market_data_provider=FakeMarketDataProvider(),
            news_provider=FakeLowSeverityNewsProvider(),
            impact_analyzer=analyzer,
        )

        loaded = self.repository.load_state("NVDA")
        update_count = self.connection.execute("SELECT COUNT(*) AS count FROM research_updates").fetchone()[
            "count"
        ]

        self.assertFalse(result.triggered_analysis)
        self.assertEqual(analyzer.call_count, 0)
        self.assertEqual(len(result.new_events), 1)
        self.assertEqual(loaded.thesis.confidence, 0.55)
        self.assertIsNone(loaded.latest_research_update)
        self.assertEqual(update_count, 0)

    def test_high_severity_new_event_triggers_analysis_and_thesis_update(self):
        analyzer = CountingImpactAnalyzer()

        result = event_update(
            repository=self.repository,
            ticker="NVDA",
            market_data_provider=FakeMarketDataProvider(),
            news_provider=FakeNewsProvider(),
            impact_analyzer=analyzer,
        )

        loaded = self.repository.load_state("NVDA")

        self.assertTrue(result.triggered_analysis)
        self.assertEqual(analyzer.call_count, 1)
        self.assertEqual(len(result.new_events), 1)
        self.assertEqual(loaded.thesis.confidence, 0.60)
        self.assertIsNotNone(loaded.latest_research_update)

    def test_duplicate_high_severity_event_does_not_retrigger_analysis(self):
        analyzer = CountingImpactAnalyzer()
        event_update(
            repository=self.repository,
            ticker="NVDA",
            market_data_provider=FakeMarketDataProvider(),
            news_provider=FakeNewsProvider(),
            impact_analyzer=analyzer,
        )

        second_result = event_update(
            repository=self.repository,
            ticker="NVDA",
            market_data_provider=FakeMarketDataProvider(),
            news_provider=FakeNewsProvider(),
            impact_analyzer=analyzer,
        )

        loaded = self.repository.load_state("NVDA")

        self.assertFalse(second_result.triggered_analysis)
        self.assertEqual(analyzer.call_count, 1)
        self.assertEqual(len(second_result.new_events), 0)
        self.assertEqual(loaded.thesis.confidence, 0.60)

    def test_event_update_output_reports_skip_or_trigger(self):
        result = event_update(
            repository=self.repository,
            ticker="NVDA",
            market_data_provider=FakeMarketDataProvider(),
            news_provider=FakeLowSeverityNewsProvider(),
            impact_analyzer=CountingImpactAnalyzer(),
        )

        output = format_event_update_result(result)

        self.assertIn("NVDA event update", output)
        self.assertIn("New events: 1", output)
        self.assertIn("Analysis triggered: no", output)

    def test_event_update_can_use_json_news_provider(self):
        analyzer = CountingImpactAnalyzer()

        result = event_update(
            repository=self.repository,
            ticker="NVDA",
            market_data_provider=FakeMarketDataProvider(),
            news_provider=JsonNewsProvider(Path(__file__).parent / "fixtures" / "news.json"),
            impact_analyzer=analyzer,
        )

        self.assertTrue(result.triggered_analysis)
        self.assertEqual(len(result.new_events), 2)
        self.assertEqual(analyzer.call_count, 1)
        self.assertEqual(result.impact_analysis.severity.value, "critical")


if __name__ == "__main__":
    unittest.main()
