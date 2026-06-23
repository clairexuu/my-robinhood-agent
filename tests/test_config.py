import unittest
from unittest.mock import patch
from tempfile import TemporaryDirectory
from pathlib import Path

from robinhood_agent.config import format_doctor_report, load_settings


class ConfigTests(unittest.TestCase):
    def test_load_settings_uses_safe_defaults(self):
        settings = load_settings({})

        self.assertEqual(settings.db_path, Path("var/agent.db"))
        self.assertEqual(settings.default_ticker, "NVDA")
        self.assertIsNone(settings.allowed_account_number)
        self.assertIsNone(settings.polygon_api_key)
        self.assertIsNone(settings.fmp_api_key)
        self.assertIsNone(settings.sec_user_agent)
        self.assertIsNone(settings.openai_api_key)
        self.assertEqual(settings.openai_model, "gpt-5.5")
        self.assertFalse(settings.live_trading_enabled)
        self.assertFalse(settings.robinhood_gate_config.live_trading_enabled)

    def test_load_settings_reads_environment_values(self):
        settings = load_settings(
            {
                "ROBINHOOD_AGENT_DB": "/tmp/agent.db",
                "ROBINHOOD_AGENT_DEFAULT_TICKER": "msft",
                "POLYGON_API_KEY": "polygon-key",
                "FMP_API_KEY": "fmp-key",
                "SEC_USER_AGENT": "agent@example.test",
                "OPENAI_API_KEY": "openai-key",
                "OPENAI_MODEL": "gpt-5.5-mini",
                "ROBINHOOD_ALLOWED_ACCOUNT_NUMBER": " RH123 ",
                "ROBINHOOD_LIVE_TRADING_ENABLED": "true",
            }
        )

        self.assertEqual(settings.db_path, Path("/tmp/agent.db"))
        self.assertEqual(settings.default_ticker, "MSFT")
        self.assertEqual(settings.polygon_api_key, "polygon-key")
        self.assertEqual(settings.fmp_api_key, "fmp-key")
        self.assertEqual(settings.sec_user_agent, "agent@example.test")
        self.assertEqual(settings.openai_api_key, "openai-key")
        self.assertEqual(settings.openai_model, "gpt-5.5-mini")
        self.assertEqual(settings.allowed_account_number, "RH123")
        self.assertTrue(settings.live_trading_enabled)

    def test_load_settings_reads_env_file(self):
        with TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "POLYGON_API_KEY=polygon-from-file",
                        "FMP_API_KEY=fmp-from-file",
                        "SEC_USER_AGENT=agent@example.test",
                        "OPENAI_API_KEY='openai-from-file'",
                        'OPENAI_MODEL="gpt-5.5-mini"',
                        "ROBINHOOD_AGENT_DEFAULT_TICKER=msft",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict("os.environ", {}, clear=True):
                settings = load_settings(env_file=env_path)

        self.assertEqual(settings.polygon_api_key, "polygon-from-file")
        self.assertEqual(settings.fmp_api_key, "fmp-from-file")
        self.assertEqual(settings.sec_user_agent, "agent@example.test")
        self.assertEqual(settings.openai_api_key, "openai-from-file")
        self.assertEqual(settings.openai_model, "gpt-5.5-mini")
        self.assertEqual(settings.default_ticker, "MSFT")

    def test_format_doctor_report_shows_safety_defaults(self):
        settings = load_settings({})

        report = format_doctor_report(settings, db_exists=False)

        self.assertIn("Robinhood agent doctor", report)
        self.assertIn("DB exists: no", report)
        self.assertIn("Polygon", report)
        self.assertIn("SEC EDGAR", report)
        self.assertIn("Financial Modeling Prep", report)
        self.assertIn("OpenAI gpt-5.5", report)
        self.assertIn("Live trading: disabled", report)
        self.assertIn("Allowed account: <not configured>", report)
        self.assertIn("not implemented", report)


if __name__ == "__main__":
    unittest.main()
