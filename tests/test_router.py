import sqlite3
import unittest

from robinhood_agent.agent import handle_message, route_message
from robinhood_agent.analysis import FakeImpactAnalyzer
from robinhood_agent.domain import OrderSide
from robinhood_agent.fixtures import nvda_initial_thesis, nvda_watch_profile
from robinhood_agent.providers import FakeMarketDataProvider, FakeNewsProvider
from robinhood_agent.storage import AgentRepository, initialize_database


class RouterTests(unittest.TestCase):
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

    def test_routes_quick_status_chinese_request(self):
        routed = route_message("现在 NVDA 怎么样")

        self.assertEqual(routed.intent, "quick_status")
        self.assertEqual(routed.ticker, "NVDA")

    def test_routes_full_research_request(self):
        routed = route_message("完整刷新一下 NVDA 研究")

        self.assertEqual(routed.intent, "full_research")
        self.assertEqual(routed.ticker, "NVDA")

    def test_routes_event_update_request(self):
        routed = route_message("NVDA 有什么新事件")

        self.assertEqual(routed.intent, "event_update")

    def test_routes_ledger_request(self):
        routed = route_message("看一下 NVDA 账本和持仓")

        self.assertEqual(routed.intent, "show_ledger")

    def test_routes_trade_preview_by_amount(self):
        routed = route_message("如果买 1000 美元 NVDA 会怎样")

        self.assertEqual(routed.intent, "trade_preview")
        self.assertEqual(routed.side, OrderSide.BUY)
        self.assertEqual(routed.amount, 1000)
        self.assertIsNone(routed.quantity)

    def test_routes_trade_preview_by_quantity(self):
        routed = route_message("sell 3 shares NVDA")

        self.assertEqual(routed.intent, "trade_preview")
        self.assertEqual(routed.side, OrderSide.SELL)
        self.assertEqual(routed.quantity, 3)

    def test_unknown_request_asks_for_clarification(self):
        routed = route_message("随便聊聊")

        self.assertTrue(routed.needs_clarification)
        self.assertEqual(routed.intent, "clarify")

    def test_handle_message_runs_quick_status(self):
        output = handle_message(self.repository, "现在 NVDA 怎么样")

        self.assertIn("NVDA quick status", output)
        self.assertIn("View: HOLD", output)

    def test_handle_message_runs_trade_preview_without_execution(self):
        output = handle_message(
            self.repository,
            "如果买 1000 美元 NVDA 会怎样",
            market_data_provider=FakeMarketDataProvider(),
        )
        ledger = self.repository.get_ledger_summary("NVDA")

        self.assertIn("NVDA paper trade preview", output)
        self.assertIn("not a live Robinhood order", output)
        self.assertIsNone(ledger.position)
        self.assertEqual(ledger.cash, 100_000)

    def test_handle_message_runs_full_research(self):
        output = handle_message(
            self.repository,
            "完整刷新一下 NVDA 研究",
            market_data_provider=FakeMarketDataProvider(),
            news_provider=FakeNewsProvider(),
            impact_analyzer=FakeImpactAnalyzer(),
        )

        self.assertIn("NVDA full research", output)
        self.assertIn("Paper intent", output)


if __name__ == "__main__":
    unittest.main()
