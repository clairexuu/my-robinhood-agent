from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Optional, Union

from robinhood_agent.agent import RobinhoodGateConfig


DEFAULT_DB_PATH = "var/agent.db"
DEFAULT_ENV_PATH = ".env"


@dataclass(frozen=True)
class AppSettings:
    db_path: Path
    default_ticker: str
    polygon_api_key: Optional[str]
    fmp_api_key: Optional[str]
    sec_user_agent: Optional[str]
    openai_api_key: Optional[str]
    openai_model: str
    allowed_account_number: Optional[str]
    live_trading_enabled: bool

    @property
    def robinhood_gate_config(self) -> RobinhoodGateConfig:
        return RobinhoodGateConfig(
            allowed_account_number=self.allowed_account_number,
            live_trading_enabled=self.live_trading_enabled,
        )


def load_settings(
    env: Optional[Mapping[str, str]] = None,
    env_file: Union[Path, str] = DEFAULT_ENV_PATH,
) -> AppSettings:
    values: Mapping[str, str]
    if env is not None:
        values = env
    else:
        file_values = _read_env_file(Path(env_file))
        values = {**file_values, **os.environ}
    return AppSettings(
        db_path=Path(values.get("ROBINHOOD_AGENT_DB", DEFAULT_DB_PATH)),
        default_ticker=values.get("ROBINHOOD_AGENT_DEFAULT_TICKER", "NVDA").upper(),
        polygon_api_key=_empty_to_none(values.get("POLYGON_API_KEY")),
        fmp_api_key=_empty_to_none(values.get("FMP_API_KEY")),
        sec_user_agent=_empty_to_none(values.get("SEC_USER_AGENT")),
        openai_api_key=_empty_to_none(values.get("OPENAI_API_KEY")),
        openai_model=values.get("OPENAI_MODEL", "gpt-5.5").strip() or "gpt-5.5",
        allowed_account_number=_empty_to_none(values.get("ROBINHOOD_ALLOWED_ACCOUNT_NUMBER")),
        live_trading_enabled=_env_bool(values.get("ROBINHOOD_LIVE_TRADING_ENABLED")),
    )


def format_doctor_report(settings: AppSettings, db_exists: bool) -> str:
    live_status = "enabled" if settings.live_trading_enabled else "disabled"
    account_status = settings.allowed_account_number or "<not configured>"
    polygon_status = "configured" if settings.polygon_api_key else "<missing POLYGON_API_KEY>"
    sec_status = "configured" if settings.sec_user_agent else "<missing SEC_USER_AGENT>"
    fmp_status = "configured" if settings.fmp_api_key else "optional <missing FMP_API_KEY>"
    llm_status = "configured" if settings.openai_api_key else "<missing OPENAI_API_KEY>"
    return "\n".join(
        [
            "Robinhood agent doctor",
            f"DB path: {settings.db_path}",
            f"DB exists: {'yes' if db_exists else 'no'}",
            f"Default ticker: {settings.default_ticker}",
            f"Market/news/calendar: Polygon ({polygon_status})",
            f"Official filings: SEC EDGAR ({sec_status})",
            f"Transcripts: Financial Modeling Prep ({fmp_status})",
            f"LLM: OpenAI {settings.openai_model} ({llm_status})",
            f"Live trading: {live_status}",
            f"Allowed account: {account_status}",
            "Safety: live order placement is not implemented in this MVP.",
        ]
    )


def _env_bool(value: Optional[str]) -> bool:
    return (value or "").lower() in {"1", "true", "yes", "on"}


def _empty_to_none(value: Optional[str]) -> Optional[str]:
    if value is None or not value.strip():
        return None
    return value.strip()


def _read_env_file(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    values: Dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        values[key] = _strip_env_value(value.strip())
    return values


def _strip_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
