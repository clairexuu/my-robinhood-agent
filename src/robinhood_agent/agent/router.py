from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from robinhood_agent.analysis import ImpactAnalyzer
from robinhood_agent.domain import OrderSide
from robinhood_agent.providers import MarketDataProvider, NewsProvider
from robinhood_agent.storage import AgentRepository

from .event_update import event_update, format_event_update_result
from .full_research import format_full_research_result, full_research
from .paper_ledger import format_ledger_summary, format_trade_preview, trade_preview
from .quick_status import quick_status


@dataclass(frozen=True)
class RoutedIntent:
    intent: str
    ticker: str
    side: Optional[OrderSide] = None
    amount: Optional[float] = None
    quantity: Optional[float] = None
    needs_clarification: bool = False
    clarification: Optional[str] = None


def route_message(message: str, default_ticker: str = "NVDA") -> RoutedIntent:
    text = message.strip()
    if not text:
        return _clarify(default_ticker, "Please ask for status, research, events, ledger, or a trade preview.")

    lowered = text.lower()
    ticker = _extract_ticker(text) or default_ticker.upper()

    if _contains_any(lowered, ["完整", "刷新", "full research", "deep research", "重新研究"]):
        return RoutedIntent(intent="full_research", ticker=ticker)

    if _contains_any(lowered, ["新事件", "事件", "新闻", "event", "update", "发生了什么"]):
        return RoutedIntent(intent="event_update", ticker=ticker)

    if _contains_any(lowered, ["账本", "持仓", "ledger", "position", "pnl", "现金"]):
        return RoutedIntent(intent="show_ledger", ticker=ticker)

    if _contains_any(lowered, ["如果买", "如果卖", "买", "卖", "buy", "sell", "trade preview", "preview"]):
        side = _extract_side(lowered)
        amount = _extract_amount(lowered)
        quantity = _extract_quantity(lowered)
        if side is None:
            return _clarify(ticker, "Do you want to preview a buy or sell?")
        if amount is None and quantity is None:
            return _clarify(ticker, "Please include an amount or quantity for the trade preview.")
        return RoutedIntent(
            intent="trade_preview",
            ticker=ticker,
            side=side,
            amount=amount,
            quantity=quantity,
        )

    if _contains_any(lowered, ["状态", "怎么样", "现在", "quick", "status", "thesis", "观点"]):
        return RoutedIntent(intent="quick_status", ticker=ticker)

    return _clarify(ticker, "I did not recognize that request. Try asking for status, full research, events, ledger, or a trade preview.")


def handle_message(
    repository: AgentRepository,
    message: str,
    default_ticker: str = "NVDA",
    market_data_provider: Optional[MarketDataProvider] = None,
    news_provider: Optional[NewsProvider] = None,
    impact_analyzer: Optional[ImpactAnalyzer] = None,
) -> str:
    routed = route_message(message, default_ticker=default_ticker)
    if routed.needs_clarification:
        return routed.clarification or "Please clarify your request."

    if routed.intent == "quick_status":
        return quick_status(repository, routed.ticker)

    if routed.intent == "full_research":
        if market_data_provider is None or news_provider is None or impact_analyzer is None:
            return "Full research requires configured market data, news, and LLM providers."
        result = full_research(
            repository=repository,
            ticker=routed.ticker,
            market_data_provider=market_data_provider,
            news_provider=news_provider,
            impact_analyzer=impact_analyzer,
        )
        return format_full_research_result(result)

    if routed.intent == "event_update":
        if market_data_provider is None or news_provider is None or impact_analyzer is None:
            return "Event update requires configured market data, news, and LLM providers."
        result = event_update(
            repository=repository,
            ticker=routed.ticker,
            market_data_provider=market_data_provider,
            news_provider=news_provider,
            impact_analyzer=impact_analyzer,
        )
        return format_event_update_result(result)

    if routed.intent == "show_ledger":
        state = repository.load_state(routed.ticker)
        return format_ledger_summary(
            routed.ticker,
            state.ledger,
            state.latest_performance_snapshot,
        )

    if routed.intent == "trade_preview":
        if routed.side is None:
            return "Do you want to preview a buy or sell?"
        if market_data_provider is None:
            return "Trade preview requires a configured market data provider."
        preview = trade_preview(
            repository=repository,
            ticker=routed.ticker,
            side=routed.side,
            amount=routed.amount,
            quantity=routed.quantity,
            market_data_provider=market_data_provider,
        )
        return format_trade_preview(preview)

    return "I did not recognize that request."


def _clarify(ticker: str, message: str) -> RoutedIntent:
    return RoutedIntent(
        intent="clarify",
        ticker=ticker.upper(),
        needs_clarification=True,
        clarification=message,
    )


def _contains_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def _extract_ticker(text: str) -> Optional[str]:
    upper_tokens = re.findall(r"\b[A-Z]{1,5}\b", text)
    ignored = {"BUY", "SELL", "HOLD", "USD", "CLI", "API", "FULL"}
    for token in upper_tokens:
        if token not in ignored:
            return token
    lower = text.lower()
    if "英伟达" in text or "nvidia" in lower:
        return "NVDA"
    if "spy" in lower:
        return "SPY"
    return None


def _extract_side(text: str) -> Optional[OrderSide]:
    if "买" in text or "buy" in text:
        return OrderSide.BUY
    if "卖" in text or "sell" in text:
        return OrderSide.SELL
    return None


def _extract_amount(text: str) -> Optional[float]:
    dollar_match = re.search(r"\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(美元|usd|dollars?)", text)
    if dollar_match:
        return float(dollar_match.group(1).replace(",", ""))
    amount_match = re.search(r"(?:amount|金额)\s*[:=]?\s*\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)", text)
    if amount_match:
        return float(amount_match.group(1).replace(",", ""))
    buy_sell_amount = re.search(r"(?:买|卖|buy|sell)\s*\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)", text)
    if buy_sell_amount and not _looks_like_share_quantity(text, buy_sell_amount.end()):
        return float(buy_sell_amount.group(1).replace(",", ""))
    return None


def _extract_quantity(text: str) -> Optional[float]:
    quantity_match = re.search(r"([0-9][0-9,]*(?:\.[0-9]+)?)\s*(股|shares?|share)", text)
    if quantity_match:
        return float(quantity_match.group(1).replace(",", ""))
    explicit_match = re.search(r"(?:quantity|数量)\s*[:=]?\s*([0-9][0-9,]*(?:\.[0-9]+)?)", text)
    if explicit_match:
        return float(explicit_match.group(1).replace(",", ""))
    return None


def _looks_like_share_quantity(text: str, start: int) -> bool:
    return bool(re.match(r"\s*(股|shares?|share)", text[start:]))
