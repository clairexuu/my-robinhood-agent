import unittest
from datetime import datetime, timezone

from robinhood_agent.domain import ThesisState, View


class DomainModelTests(unittest.TestCase):
    def test_thesis_requires_timezone_aware_datetime(self):
        with self.assertRaises(ValueError):
            ThesisState(
                ticker="NVDA",
                view=View.HOLD,
                confidence=0.5,
                target_position_pct=0.1,
                horizon="3 months",
                core_assumptions=["Demand remains strong."],
                risks=["Valuation risk."],
                invalidation_conditions=["Growth slows."],
                updated_at=datetime(2026, 1, 1),
            )

    def test_thesis_rejects_missing_invalidation_conditions(self):
        with self.assertRaises(ValueError):
            ThesisState(
                ticker="nvda",
                view="hold",
                confidence=0.5,
                target_position_pct=0.1,
                horizon="3 months",
                core_assumptions=["Demand remains strong."],
                risks=["Valuation risk."],
                invalidation_conditions=[],
                updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )

    def test_thesis_normalizes_ticker_and_view(self):
        thesis = ThesisState(
            ticker="nvda",
            view="buy",
            confidence=0.7,
            target_position_pct=0.2,
            horizon="3 months",
            core_assumptions=["Demand remains strong."],
            risks=["Valuation risk."],
            invalidation_conditions=["Growth slows."],
            updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        self.assertEqual(thesis.ticker, "NVDA")
        self.assertEqual(thesis.view, View.BUY)


if __name__ == "__main__":
    unittest.main()
