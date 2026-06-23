from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from robinhood_agent.domain import OrderSide, PaperOrder, PaperPosition, PerformanceSnapshot
from robinhood_agent.providers import MarketData, MarketDataProvider
from robinhood_agent.storage import AgentRepository, LedgerSummary


@dataclass(frozen=True)
class TradePreview:
    ticker: str
    side: OrderSide
    price: float
    quantity: float
    notional: float
    fee: float
    estimated_cash_after: float
    estimated_quantity_after: float
    allowed: bool
    reason: str


@dataclass(frozen=True)
class PaperTradeResult:
    preview: TradePreview
    order: PaperOrder
    position: PaperPosition
    ledger: LedgerSummary


@dataclass(frozen=True)
class PaperIntentApplication:
    preview: TradePreview
    trade_result: Optional[PaperTradeResult]
    research_update_id: Optional[str]


def trade_preview(
    repository: AgentRepository,
    ticker: str,
    side: OrderSide,
    amount: Optional[float],
    quantity: Optional[float],
    market_data_provider: MarketDataProvider,
    fee: float = 0.0,
) -> TradePreview:
    normalized_ticker = ticker.upper()
    loaded = repository.load_state(normalized_ticker)
    if loaded.watch_profile is None:
        raise ValueError(f"{normalized_ticker} has no watch profile")

    coerced_side = side if isinstance(side, OrderSide) else OrderSide(side)
    market_data = market_data_provider.fetch_market_data(
        loaded.watch_profile.ticker,
        loaded.watch_profile.benchmark,
    )
    price = market_data.latest_price
    if price <= 0:
        raise ValueError("latest price must be positive")
    if amount is None and quantity is None:
        raise ValueError("amount or quantity is required")
    if amount is not None and amount < 0:
        raise ValueError("amount must be non-negative")
    if quantity is not None and quantity < 0:
        raise ValueError("quantity must be non-negative")
    if fee < 0:
        raise ValueError("fee must be non-negative")

    resolved_quantity = quantity if quantity is not None else (amount or 0.0) / price
    notional = resolved_quantity * price
    ledger = loaded.ledger
    current_quantity = ledger.position.quantity if ledger.position else 0.0

    if coerced_side == OrderSide.BUY:
        cash_after = ledger.cash - notional - fee
        quantity_after = current_quantity + resolved_quantity
        allowed = cash_after >= -0.000001
        reason = "paper buy preview" if allowed else "insufficient paper cash"
    elif coerced_side == OrderSide.SELL:
        cash_after = ledger.cash + notional - fee
        quantity_after = current_quantity - resolved_quantity
        allowed = quantity_after >= -0.000001
        reason = "paper sell preview" if allowed else "cannot sell more than current paper position"
    else:
        cash_after = ledger.cash
        quantity_after = current_quantity
        allowed = True
        reason = "hold does not create a paper order"

    return TradePreview(
        ticker=normalized_ticker,
        side=coerced_side,
        price=price,
        quantity=round(resolved_quantity, 8),
        notional=round(notional, 2),
        fee=fee,
        estimated_cash_after=round(cash_after, 2),
        estimated_quantity_after=round(max(0.0, quantity_after), 8),
        allowed=allowed,
        reason=reason,
    )


def build_paper_intent(
    repository: AgentRepository,
    ticker: str,
    target_position_pct: float,
    market_data: MarketData,
    min_trade_notional: float = 1.0,
) -> TradePreview:
    if not 0.0 <= target_position_pct <= 1.0:
        raise ValueError("target_position_pct must be between 0 and 1")
    if market_data.latest_price <= 0:
        raise ValueError("latest price must be positive")
    if min_trade_notional < 0:
        raise ValueError("min_trade_notional must be non-negative")

    normalized_ticker = ticker.upper()
    ledger = repository.get_ledger_summary(normalized_ticker)
    current_quantity = ledger.position.quantity if ledger.position else 0.0
    current_position_value = current_quantity * market_data.latest_price
    total_equity = ledger.cash + current_position_value
    target_position_value = total_equity * target_position_pct
    delta_value = round(target_position_value - current_position_value, 2)

    if abs(delta_value) < min_trade_notional:
        return TradePreview(
            ticker=normalized_ticker,
            side=OrderSide.HOLD,
            price=market_data.latest_price,
            quantity=0.0,
            notional=0.0,
            fee=0.0,
            estimated_cash_after=round(ledger.cash, 2),
            estimated_quantity_after=round(current_quantity, 8),
            allowed=True,
            reason="current paper position is already near target",
        )

    if delta_value > 0:
        quantity = delta_value / market_data.latest_price
        return TradePreview(
            ticker=normalized_ticker,
            side=OrderSide.BUY,
            price=market_data.latest_price,
            quantity=round(quantity, 8),
            notional=round(delta_value, 2),
            fee=0.0,
            estimated_cash_after=round(ledger.cash - delta_value, 2),
            estimated_quantity_after=round(current_quantity + quantity, 8),
            allowed=ledger.cash + 0.000001 >= delta_value,
            reason=(
                "paper rebalance toward target"
                if ledger.cash + 0.000001 >= delta_value
                else "insufficient paper cash"
            ),
        )

    sell_notional = abs(delta_value)
    quantity = sell_notional / market_data.latest_price
    return TradePreview(
        ticker=normalized_ticker,
        side=OrderSide.SELL,
        price=market_data.latest_price,
        quantity=round(quantity, 8),
        notional=round(sell_notional, 2),
        fee=0.0,
        estimated_cash_after=round(ledger.cash + sell_notional, 2),
        estimated_quantity_after=round(max(0.0, current_quantity - quantity), 8),
        allowed=current_quantity + 0.000001 >= quantity,
        reason=(
            "paper rebalance toward target"
            if current_quantity + 0.000001 >= quantity
            else "cannot sell more than current paper position"
        ),
    )


def execute_paper_trade(
    repository: AgentRepository,
    preview: TradePreview,
    research_update_id: Optional[str] = None,
) -> PaperTradeResult:
    if not preview.allowed:
        raise ValueError(preview.reason)
    if preview.side == OrderSide.HOLD:
        raise ValueError("hold preview cannot be executed as an order")

    order = PaperOrder(
        id=str(uuid4()),
        ticker=preview.ticker,
        side=preview.side,
        quantity=preview.quantity,
        price=preview.price,
        fee=preview.fee,
        research_update_id=research_update_id,
        created_at=datetime.now(timezone.utc),
    )
    position = repository.record_paper_order(order)
    ledger = repository.get_ledger_summary(preview.ticker)
    return PaperTradeResult(preview=preview, order=order, position=position, ledger=ledger)


def apply_latest_paper_intent(
    repository: AgentRepository,
    ticker: str,
    market_data_provider: MarketDataProvider,
    min_trade_notional: float = 1.0,
) -> PaperIntentApplication:
    normalized_ticker = ticker.upper()
    state = repository.load_state(normalized_ticker)
    if state.watch_profile is None:
        raise ValueError(f"{normalized_ticker} has no watch profile")
    if state.thesis is None:
        raise ValueError(f"{normalized_ticker} has no thesis state")
    if state.latest_research_update is None:
        raise ValueError(f"{normalized_ticker} has no research update to link a paper order to")

    market_data = market_data_provider.fetch_market_data(
        state.watch_profile.ticker,
        state.watch_profile.benchmark,
    )
    preview = build_paper_intent(
        repository=repository,
        ticker=normalized_ticker,
        target_position_pct=state.thesis.target_position_pct,
        market_data=market_data,
        min_trade_notional=min_trade_notional,
    )

    if preview.side == OrderSide.HOLD:
        return PaperIntentApplication(
            preview=preview,
            trade_result=None,
            research_update_id=state.latest_research_update.id,
        )

    trade_result = execute_paper_trade(
        repository=repository,
        preview=preview,
        research_update_id=state.latest_research_update.id,
    )
    return PaperIntentApplication(
        preview=preview,
        trade_result=trade_result,
        research_update_id=state.latest_research_update.id,
    )


def format_trade_preview(preview: TradePreview) -> str:
    return "\n".join(
        [
            f"{preview.ticker} paper trade preview",
            f"Side: {preview.side.value.upper()}",
            f"Price: ${preview.price:,.2f}",
            f"Quantity: {preview.quantity:g}",
            f"Notional: ${preview.notional:,.2f}",
            f"Estimated cash after: ${preview.estimated_cash_after:,.2f}",
            f"Estimated quantity after: {preview.estimated_quantity_after:g}",
            f"Allowed: {'yes' if preview.allowed else 'no'}",
            f"Reason: {preview.reason}",
            "This is a local paper trade preview, not a live Robinhood order.",
        ]
    )


def format_paper_trade_result(result: PaperTradeResult) -> str:
    return "\n".join(
        [
            f"Recorded local paper order {result.order.id}",
            f"Side: {result.order.side.value.upper()} {result.order.quantity:g} {result.order.ticker}",
            f"Price: ${result.order.price:,.2f}",
            f"Cash: ${result.ledger.cash:,.2f}",
            f"Position: {result.position.quantity:g} shares @ ${result.position.average_cost:,.2f}",
            "No live Robinhood order was placed.",
        ]
    )


def format_paper_intent_application(application: PaperIntentApplication) -> str:
    if application.trade_result is None:
        return "\n".join(
            [
                "Latest paper intent did not create an order.",
                f"Side: {application.preview.side.value.upper()}",
                f"Reason: {application.preview.reason}",
                f"Linked research update: {application.research_update_id}",
                "No live Robinhood order was placed.",
            ]
        )

    result = application.trade_result
    return "\n".join(
        [
            f"Applied latest paper intent from research update {application.research_update_id}",
            f"Recorded local paper order {result.order.id}",
            f"Side: {result.order.side.value.upper()} {result.order.quantity:g} {result.order.ticker}",
            f"Notional: ${result.preview.notional:,.2f}",
            f"Price: ${result.order.price:,.2f}",
            f"Cash: ${result.ledger.cash:,.2f}",
            f"Position: {result.position.quantity:g} shares @ ${result.position.average_cost:,.2f}",
            "No live Robinhood order was placed.",
        ]
    )


def format_ledger_summary(
    ticker: str,
    summary: LedgerSummary,
    latest_performance_snapshot: Optional[PerformanceSnapshot] = None,
) -> str:
    if summary.position is None:
        position = "no position"
    else:
        position = (
            f"{summary.position.quantity:g} shares "
            f"@ ${summary.position.average_cost:,.2f} average cost"
        )
    lines = [
        f"{ticker.upper()} paper ledger",
        f"Cash: ${summary.cash:,.2f}",
        f"Position: {position}",
    ]
    if latest_performance_snapshot is not None:
        snapshot = latest_performance_snapshot
        lines.append(
            "Latest performance: "
            f"{snapshot.window} absolute {snapshot.absolute_return:.2%}, "
            f"relative {snapshot.relative_return:.2%}, "
            f"max drawdown {snapshot.max_drawdown:.2%}"
        )
    return "\n".join(lines)
