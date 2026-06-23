import sqlite3
import unittest

from robinhood_agent.agent import (
    apply_latest_paper_intent,
    build_paper_intent,
    evaluate_performance,
    execute_paper_trade,
    full_research,
    format_paper_intent_application,
    format_ledger_summary,
    format_trade_preview,
    trade_preview,
)
from robinhood_agent.analysis import FakeImpactAnalyzer
from robinhood_agent.domain import OrderSide
from robinhood_agent.fixtures import nvda_initial_thesis, nvda_watch_profile
from robinhood_agent.providers import FakeHistoricalPriceProvider, FakeMarketDataProvider, FakeNewsProvider
from robinhood_agent.storage import AgentRepository, initialize_database


class PaperLedgerTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        initialize_database(self.connection)
        self.repository = AgentRepository(self.connection)
        self.repository.save_watch_profile(nvda_watch_profile())
        self.repository.save_thesis(nvda_initial_thesis())
        self.market_data_provider = FakeMarketDataProvider()

    def tearDown(self):
        self.connection.close()

    def test_trade_preview_by_amount_uses_latest_price(self):
        preview = trade_preview(
            repository=self.repository,
            ticker="NVDA",
            side=OrderSide.BUY,
            amount=1_285,
            quantity=None,
            market_data_provider=self.market_data_provider,
        )

        self.assertTrue(preview.allowed)
        self.assertEqual(preview.quantity, 10)
        self.assertEqual(preview.notional, 1_285)
        self.assertEqual(preview.estimated_cash_after, 98_715)
        self.assertIn("not a live Robinhood order", format_trade_preview(preview))

    def test_execute_buy_updates_cash_position_and_order_history(self):
        preview = trade_preview(
            repository=self.repository,
            ticker="NVDA",
            side=OrderSide.BUY,
            amount=1_285,
            quantity=None,
            market_data_provider=self.market_data_provider,
            fee=1,
        )

        result = execute_paper_trade(self.repository, preview)
        orders = self.repository.list_paper_orders("NVDA")

        self.assertEqual(result.position.quantity, 10)
        self.assertEqual(result.position.average_cost, 128.6)
        self.assertEqual(result.ledger.cash, 98_714)
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].side, OrderSide.BUY)

    def test_sell_preview_and_execution_reduces_position(self):
        buy_preview = trade_preview(
            repository=self.repository,
            ticker="NVDA",
            side=OrderSide.BUY,
            amount=1_285,
            quantity=None,
            market_data_provider=self.market_data_provider,
        )
        execute_paper_trade(self.repository, buy_preview)

        sell_preview = trade_preview(
            repository=self.repository,
            ticker="NVDA",
            side=OrderSide.SELL,
            amount=None,
            quantity=4,
            market_data_provider=self.market_data_provider,
        )
        result = execute_paper_trade(self.repository, sell_preview)

        self.assertTrue(sell_preview.allowed)
        self.assertEqual(result.position.quantity, 6)
        self.assertEqual(result.ledger.cash, 99_229)

    def test_oversell_preview_is_not_allowed_and_cannot_execute(self):
        preview = trade_preview(
            repository=self.repository,
            ticker="NVDA",
            side=OrderSide.SELL,
            amount=None,
            quantity=1,
            market_data_provider=self.market_data_provider,
        )

        self.assertFalse(preview.allowed)
        self.assertIn("cannot sell more", preview.reason)
        with self.assertRaises(ValueError):
            execute_paper_trade(self.repository, preview)

    def test_format_ledger_summary_for_empty_and_populated_position(self):
        empty_output = format_ledger_summary("NVDA", self.repository.get_ledger_summary("NVDA"))
        preview = trade_preview(
            repository=self.repository,
            ticker="NVDA",
            side=OrderSide.BUY,
            amount=1_285,
            quantity=None,
            market_data_provider=self.market_data_provider,
        )
        execute_paper_trade(self.repository, preview)
        populated_output = format_ledger_summary("NVDA", self.repository.get_ledger_summary("NVDA"))

        self.assertIn("no position", empty_output)
        self.assertIn("10 shares", populated_output)

    def test_format_ledger_summary_includes_latest_performance_when_provided(self):
        evaluation = evaluate_performance(
            repository=self.repository,
            ticker="NVDA",
            window="1W",
            price_provider=FakeHistoricalPriceProvider(),
        )

        output = format_ledger_summary(
            "NVDA",
            self.repository.get_ledger_summary("NVDA"),
            evaluation.snapshot,
        )

        self.assertIn("Latest performance: 1W absolute 2.80%", output)
        self.assertIn("max drawdown -2.40%", output)

    def test_paper_intent_recommends_buy_when_below_target(self):
        market_data = self.market_data_provider.fetch_market_data("NVDA", "SPY")

        intent = build_paper_intent(
            repository=self.repository,
            ticker="NVDA",
            target_position_pct=0.10,
            market_data=market_data,
        )

        self.assertEqual(intent.side, OrderSide.BUY)
        self.assertEqual(intent.notional, 10_000)
        self.assertTrue(intent.allowed)
        self.assertEqual(intent.estimated_cash_after, 90_000)

    def test_paper_intent_recommends_hold_when_near_target(self):
        buy_preview = trade_preview(
            repository=self.repository,
            ticker="NVDA",
            side=OrderSide.BUY,
            amount=10_000,
            quantity=None,
            market_data_provider=self.market_data_provider,
        )
        execute_paper_trade(self.repository, buy_preview)
        market_data = self.market_data_provider.fetch_market_data("NVDA", "SPY")

        intent = build_paper_intent(
            repository=self.repository,
            ticker="NVDA",
            target_position_pct=0.10,
            market_data=market_data,
        )

        self.assertEqual(intent.side, OrderSide.HOLD)
        self.assertEqual(intent.notional, 0)
        self.assertTrue(intent.allowed)

    def test_paper_intent_recommends_sell_when_above_target(self):
        buy_preview = trade_preview(
            repository=self.repository,
            ticker="NVDA",
            side=OrderSide.BUY,
            amount=20_000,
            quantity=None,
            market_data_provider=self.market_data_provider,
        )
        execute_paper_trade(self.repository, buy_preview)
        market_data = self.market_data_provider.fetch_market_data("NVDA", "SPY")

        intent = build_paper_intent(
            repository=self.repository,
            ticker="NVDA",
            target_position_pct=0.10,
            market_data=market_data,
        )

        self.assertEqual(intent.side, OrderSide.SELL)
        self.assertEqual(intent.notional, 10_000)
        self.assertTrue(intent.allowed)

    def test_apply_latest_paper_intent_requires_research_update(self):
        with self.assertRaises(ValueError):
            apply_latest_paper_intent(
                repository=self.repository,
                ticker="NVDA",
                market_data_provider=self.market_data_provider,
            )

    def test_apply_latest_paper_intent_executes_and_links_order_to_research_update(self):
        research_result = full_research(
            repository=self.repository,
            ticker="NVDA",
            market_data_provider=self.market_data_provider,
            news_provider=FakeNewsProvider(),
            impact_analyzer=FakeImpactAnalyzer(),
        )

        application = apply_latest_paper_intent(
            repository=self.repository,
            ticker="NVDA",
            market_data_provider=self.market_data_provider,
        )
        orders = self.repository.list_paper_orders("NVDA")

        self.assertIsNotNone(application.trade_result)
        self.assertEqual(application.research_update_id, research_result.research_update.id)
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].research_update_id, research_result.research_update.id)
        self.assertIn("Applied latest paper intent", format_paper_intent_application(application))

    def test_apply_latest_paper_intent_hold_does_not_create_order(self):
        full_research(
            repository=self.repository,
            ticker="NVDA",
            market_data_provider=self.market_data_provider,
            news_provider=FakeNewsProvider(),
            impact_analyzer=FakeImpactAnalyzer(),
        )
        preview = trade_preview(
            repository=self.repository,
            ticker="NVDA",
            side=OrderSide.BUY,
            amount=10_000,
            quantity=None,
            market_data_provider=self.market_data_provider,
        )
        execute_paper_trade(self.repository, preview)

        application = apply_latest_paper_intent(
            repository=self.repository,
            ticker="NVDA",
            market_data_provider=self.market_data_provider,
        )

        self.assertIsNone(application.trade_result)
        self.assertEqual(application.preview.side, OrderSide.HOLD)
        self.assertEqual(len(self.repository.list_paper_orders("NVDA")), 1)


if __name__ == "__main__":
    unittest.main()
