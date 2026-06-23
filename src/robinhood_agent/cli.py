from __future__ import annotations

import argparse
import sys
from pathlib import Path

from robinhood_agent.agent import (
    apply_latest_paper_intent,
    execute_paper_trade,
    evaluate_performance,
    event_update,
    format_event_update_result,
    format_full_research_result,
    format_history_report,
    format_history_json,
    format_ledger_summary,
    format_live_order_preview,
    format_paper_trade_result,
    format_paper_intent_application,
    format_performance_evaluation,
    format_trade_preview,
    full_research,
    handle_message,
    load_history,
    preview_live_order,
    quick_status,
    RobinhoodGateConfig,
    trade_preview,
    validate_live_order_confirmation,
)
from robinhood_agent.analysis import OpenAIResponsesLlmClient, StructuredLlmImpactAnalyzer
from robinhood_agent.config import AppSettings, format_doctor_report, load_settings
from robinhood_agent.domain import OrderSide
from robinhood_agent.fixtures import nvda_initial_thesis, nvda_watch_profile
from robinhood_agent.providers import (
    CompositeResearchEventProvider,
    FinancialModelingPrepProvider,
    PolygonProvider,
    SecEdgarProvider,
)
from robinhood_agent.storage import AgentRepository, connect, initialize_database


class ConfigurationError(ValueError):
    pass


def _build_polygon_provider(settings: AppSettings) -> PolygonProvider:
    if not settings.polygon_api_key:
        raise ConfigurationError("POLYGON_API_KEY is required for market/news/calendar data")
    return PolygonProvider(settings.polygon_api_key)


def _build_research_event_provider(
    settings: AppSettings,
    polygon_provider: PolygonProvider,
) -> CompositeResearchEventProvider:
    if not settings.sec_user_agent:
        raise ConfigurationError("SEC_USER_AGENT is required for SEC EDGAR data")
    transcript_provider = (
        FinancialModelingPrepProvider(settings.fmp_api_key)
        if settings.fmp_api_key
        else None
    )
    return CompositeResearchEventProvider(
        news_provider=polygon_provider,
        filing_provider=SecEdgarProvider(settings.sec_user_agent),
        earnings_calendar_provider=polygon_provider,
        transcript_provider=transcript_provider,
    )


def _build_impact_analyzer(settings: AppSettings) -> StructuredLlmImpactAnalyzer:
    if not settings.openai_api_key:
        raise ConfigurationError("OPENAI_API_KEY is required for LLM analysis")
    return StructuredLlmImpactAnalyzer(
        OpenAIResponsesLlmClient(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
    )


def main() -> int:
    try:
        return _main()
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2


def _main() -> int:
    settings = load_settings()
    parser = argparse.ArgumentParser(prog="robinhood-agent")
    parser.add_argument("--db", default=str(settings.db_path), help="Path to the local SQLite database.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-db", help="Initialize the local SQLite database.")
    init_parser.add_argument(
        "--seed-default-nvda",
        action="store_true",
        help="Seed the default NVDA watch profile and starting thesis.",
    )

    subparsers.add_parser("doctor", help="Print local configuration and safety defaults.")

    status_parser = subparsers.add_parser("quick-status", help="Print cached status for a ticker.")
    status_parser.add_argument("ticker", nargs="?", default="NVDA")

    full_parser = subparsers.add_parser(
        "full-research",
        help="Run full research with configured real data and LLM providers.",
    )
    full_parser.add_argument("ticker", nargs="?", default="NVDA")

    event_parser = subparsers.add_parser(
        "event-update",
        help="Process new events and only analyze high-severity changes.",
    )
    event_parser.add_argument("ticker", nargs="?", default="NVDA")

    ledger_parser = subparsers.add_parser("show-ledger", help="Print local paper ledger.")
    ledger_parser.add_argument("ticker", nargs="?", default="NVDA")

    history_parser = subparsers.add_parser("history", help="Print local research and paper audit history.")
    history_parser.add_argument("ticker", nargs="?", default="NVDA")
    history_parser.add_argument(
        "--kind",
        choices=("all", "events", "updates", "orders", "performance"),
        default="all",
    )
    history_parser.add_argument("--limit", type=int, default=10)
    history_parser.add_argument("--format", choices=("text", "json"), default="text")

    preview_parser = subparsers.add_parser(
        "trade-preview",
        help="Preview a local paper trade. This never places a live order.",
    )
    preview_parser.add_argument("ticker")
    preview_parser.add_argument("side", choices=("buy", "sell", "hold"))
    preview_parser.add_argument("--amount", type=float)
    preview_parser.add_argument("--quantity", type=float)
    preview_parser.add_argument("--fee", type=float, default=0.0)

    paper_trade_parser = subparsers.add_parser(
        "paper-trade",
        help="Execute a local paper trade from the preview inputs.",
    )
    paper_trade_parser.add_argument("ticker")
    paper_trade_parser.add_argument("side", choices=("buy", "sell"))
    paper_trade_parser.add_argument("--amount", type=float)
    paper_trade_parser.add_argument("--quantity", type=float)
    paper_trade_parser.add_argument("--fee", type=float, default=0.0)

    apply_intent_parser = subparsers.add_parser(
        "apply-paper-intent",
        help="Execute the latest research target as a local paper order.",
    )
    apply_intent_parser.add_argument("ticker", nargs="?", default="NVDA")

    chat_parser = subparsers.add_parser(
        "chat",
        help="Route a natural-language request to the local agent workflows.",
    )
    chat_parser.add_argument("message")
    chat_parser.add_argument("--default-ticker", default="NVDA")

    live_parser = subparsers.add_parser(
        "live-preview",
        help="Run local Robinhood live-order safety checks. This never places a live order.",
    )
    live_parser.add_argument("ticker")
    live_parser.add_argument("side", choices=("buy", "sell"))
    live_parser.add_argument("--amount", type=float)
    live_parser.add_argument("--quantity", type=float)
    live_parser.add_argument("--account-number", required=True)
    live_parser.add_argument("--allowed-account-number")
    live_parser.add_argument("--enable-live-trading", action="store_true")
    live_parser.add_argument("--confirmation")

    performance_parser = subparsers.add_parser(
        "evaluate-performance",
        help="Compute and persist a local paper performance snapshot.",
    )
    performance_parser.add_argument("ticker", nargs="?", default="NVDA")
    performance_parser.add_argument("--window", default="1W", choices=("1D", "1W", "1M"))

    args = parser.parse_args()
    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if args.command == "doctor":
        doctor_settings = load_settings()
        if args.db:
            doctor_settings = type(doctor_settings)(
                db_path=db_path,
                default_ticker=doctor_settings.default_ticker,
                polygon_api_key=doctor_settings.polygon_api_key,
                fmp_api_key=doctor_settings.fmp_api_key,
                sec_user_agent=doctor_settings.sec_user_agent,
                openai_api_key=doctor_settings.openai_api_key,
                openai_model=doctor_settings.openai_model,
                allowed_account_number=doctor_settings.allowed_account_number,
                live_trading_enabled=doctor_settings.live_trading_enabled,
            )
        print(format_doctor_report(doctor_settings, db_path.exists()))
        return 0

    with connect(db_path) as connection:
        initialize_database(connection)
        repository = AgentRepository(connection)

        if args.command == "init-db":
            if args.seed_default_nvda:
                repository.save_watch_profile(nvda_watch_profile())
                repository.save_thesis(nvda_initial_thesis())
            print(f"Initialized {db_path}")
            return 0

        if args.command == "quick-status":
            print(quick_status(repository, args.ticker))
            return 0

        if args.command == "full-research":
            data_provider = _build_polygon_provider(settings)
            event_provider = _build_research_event_provider(settings, data_provider)
            impact_analyzer = _build_impact_analyzer(settings)
            result = full_research(
                repository=repository,
                ticker=args.ticker,
                market_data_provider=data_provider,
                news_provider=event_provider,
                impact_analyzer=impact_analyzer,
            )
            print(format_full_research_result(result))
            return 0

        if args.command == "event-update":
            data_provider = _build_polygon_provider(settings)
            event_provider = _build_research_event_provider(settings, data_provider)
            impact_analyzer = _build_impact_analyzer(settings)
            result = event_update(
                repository=repository,
                ticker=args.ticker,
                market_data_provider=data_provider,
                news_provider=event_provider,
                impact_analyzer=impact_analyzer,
            )
            print(format_event_update_result(result))
            return 0

        if args.command == "show-ledger":
            state = repository.load_state(args.ticker)
            print(
                format_ledger_summary(
                    args.ticker,
                    state.ledger,
                    state.latest_performance_snapshot,
                )
            )
            return 0

        if args.command == "history":
            report = load_history(
                repository=repository,
                ticker=args.ticker,
                kind=args.kind,
                limit=args.limit,
            )
            if args.format == "json":
                print(format_history_json(report))
            else:
                print(format_history_report(report))
            return 0

        if args.command == "trade-preview":
            preview = trade_preview(
                repository=repository,
                ticker=args.ticker,
                side=OrderSide(args.side),
                amount=args.amount,
                quantity=args.quantity,
                market_data_provider=_build_polygon_provider(settings),
                fee=args.fee,
            )
            print(format_trade_preview(preview))
            return 0

        if args.command == "paper-trade":
            preview = trade_preview(
                repository=repository,
                ticker=args.ticker,
                side=OrderSide(args.side),
                amount=args.amount,
                quantity=args.quantity,
                market_data_provider=_build_polygon_provider(settings),
                fee=args.fee,
            )
            result = execute_paper_trade(repository, preview)
            print(format_paper_trade_result(result))
            return 0

        if args.command == "apply-paper-intent":
            application = apply_latest_paper_intent(
                repository=repository,
                ticker=args.ticker,
                market_data_provider=_build_polygon_provider(settings),
            )
            print(format_paper_intent_application(application))
            return 0

        if args.command == "chat":
            data_provider = _build_polygon_provider(settings)
            print(
                handle_message(
                    repository,
                    args.message,
                    default_ticker=args.default_ticker,
                    market_data_provider=data_provider,
                    news_provider=_build_research_event_provider(settings, data_provider),
                    impact_analyzer=_build_impact_analyzer(settings),
                )
            )
            return 0

        if args.command == "live-preview":
            data_provider = _build_polygon_provider(settings)
            paper_preview = trade_preview(
                repository=repository,
                ticker=args.ticker,
                side=OrderSide(args.side),
                amount=args.amount,
                quantity=args.quantity,
                market_data_provider=data_provider,
            )
            config = RobinhoodGateConfig(
                allowed_account_number=args.allowed_account_number
                or settings.allowed_account_number,
                live_trading_enabled=args.enable_live_trading
                or settings.live_trading_enabled,
            )
            live_preview = preview_live_order(config, paper_preview, args.account_number)
            if args.confirmation:
                live_preview = validate_live_order_confirmation(live_preview, args.confirmation)
            print(format_live_order_preview(live_preview))
            return 0

        if args.command == "evaluate-performance":
            price_provider = _build_polygon_provider(settings)
            evaluation = evaluate_performance(
                repository=repository,
                ticker=args.ticker,
                window=args.window,
                price_provider=price_provider,
            )
            print(format_performance_evaluation(evaluation))
            return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
