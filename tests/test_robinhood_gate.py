import sqlite3
import unittest

from robinhood_agent.agent import (
    RobinhoodGateConfig,
    format_live_order_preview,
    preview_live_order,
    trade_preview,
    validate_live_order_confirmation,
)
from robinhood_agent.domain import OrderSide
from robinhood_agent.fixtures import nvda_initial_thesis, nvda_watch_profile
from robinhood_agent.providers import FakeMarketDataProvider
from robinhood_agent.storage import AgentRepository, initialize_database


class RobinhoodGateTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        initialize_database(self.connection)
        self.repository = AgentRepository(self.connection)
        self.repository.save_watch_profile(nvda_watch_profile())
        self.repository.save_thesis(nvda_initial_thesis())
        self.paper_preview = trade_preview(
            repository=self.repository,
            ticker="NVDA",
            side=OrderSide.BUY,
            amount=1_000,
            quantity=None,
            market_data_provider=FakeMarketDataProvider(),
        )

    def tearDown(self):
        self.connection.close()

    def test_live_preview_is_disabled_by_default(self):
        preview = preview_live_order(
            RobinhoodGateConfig(),
            self.paper_preview,
            account_number="RH123",
        )

        self.assertFalse(preview.allowed)
        self.assertEqual(preview.reason, "live trading is disabled")
        self.assertIn("No live Robinhood order was placed", format_live_order_preview(preview))

    def test_live_preview_requires_configured_account(self):
        preview = preview_live_order(
            RobinhoodGateConfig(live_trading_enabled=True),
            self.paper_preview,
            account_number="RH123",
        )

        self.assertFalse(preview.allowed)
        self.assertEqual(preview.reason, "allowed account number is not configured")

    def test_live_preview_rejects_account_mismatch(self):
        preview = preview_live_order(
            RobinhoodGateConfig(allowed_account_number="RH999", live_trading_enabled=True),
            self.paper_preview,
            account_number="RH123",
        )

        self.assertFalse(preview.allowed)
        self.assertEqual(preview.reason, "account number does not match configured account")

    def test_live_preview_rejects_blocked_paper_preview(self):
        blocked_paper_preview = trade_preview(
            repository=self.repository,
            ticker="NVDA",
            side=OrderSide.SELL,
            amount=None,
            quantity=1,
            market_data_provider=FakeMarketDataProvider(),
        )

        preview = preview_live_order(
            RobinhoodGateConfig(allowed_account_number="RH123", live_trading_enabled=True),
            blocked_paper_preview,
            account_number="RH123",
        )

        self.assertFalse(preview.allowed)
        self.assertIn("cannot sell more", preview.reason)

    def test_live_preview_can_pass_local_gate_but_not_place_order(self):
        preview = preview_live_order(
            RobinhoodGateConfig(allowed_account_number="RH123", live_trading_enabled=True),
            self.paper_preview,
            account_number="RH123",
        )

        self.assertTrue(preview.allowed)
        self.assertIn("human confirmation still required", preview.reason)

    def test_confirmation_requires_ticker_side_account_and_size(self):
        preview = preview_live_order(
            RobinhoodGateConfig(allowed_account_number="RH123", live_trading_enabled=True),
            self.paper_preview,
            account_number="RH123",
        )

        rejected = validate_live_order_confirmation(preview, "CONFIRM NVDA BUY RH123")
        accepted = validate_live_order_confirmation(
            preview,
            "CONFIRM NVDA BUY 1000.0 RH123",
        )

        self.assertFalse(rejected.allowed)
        self.assertIn("notional or quantity", rejected.reason)
        self.assertTrue(accepted.allowed)
        self.assertIn("not implemented", accepted.reason)


if __name__ == "__main__":
    unittest.main()
