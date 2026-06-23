from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from robinhood_agent.domain import OrderSide

from .paper_ledger import TradePreview


@dataclass(frozen=True)
class RobinhoodGateConfig:
    allowed_account_number: Optional[str] = None
    live_trading_enabled: bool = False


@dataclass(frozen=True)
class LiveOrderPreview:
    ticker: str
    side: OrderSide
    quantity: float
    notional: float
    account_number: str
    allowed: bool
    reason: str


def preview_live_order(
    config: RobinhoodGateConfig,
    paper_preview: TradePreview,
    account_number: str,
) -> LiveOrderPreview:
    account = account_number.strip()
    if not config.live_trading_enabled:
        return _blocked(config, paper_preview, account, "live trading is disabled")
    if not config.allowed_account_number:
        return _blocked(config, paper_preview, account, "allowed account number is not configured")
    if account != config.allowed_account_number:
        return _blocked(config, paper_preview, account, "account number does not match configured account")
    if not paper_preview.allowed:
        return _blocked(config, paper_preview, account, paper_preview.reason)
    if paper_preview.side == OrderSide.HOLD:
        return _blocked(config, paper_preview, account, "hold preview cannot become a live order")

    return LiveOrderPreview(
        ticker=paper_preview.ticker,
        side=paper_preview.side,
        quantity=paper_preview.quantity,
        notional=paper_preview.notional,
        account_number=account,
        allowed=True,
        reason="live order preview passed local safety gate; human confirmation still required",
    )


def validate_live_order_confirmation(
    preview: LiveOrderPreview,
    confirmation_text: str,
) -> LiveOrderPreview:
    if not preview.allowed:
        return preview

    normalized = confirmation_text.upper()
    required_fragments = [
        preview.ticker.upper(),
        preview.side.value.upper(),
        preview.account_number.upper(),
    ]
    missing = [fragment for fragment in required_fragments if fragment not in normalized]
    if str(round(preview.notional, 2)) not in normalized and str(round(preview.quantity, 8)) not in normalized:
        missing.append("notional or quantity")
    if missing:
        return LiveOrderPreview(
            ticker=preview.ticker,
            side=preview.side,
            quantity=preview.quantity,
            notional=preview.notional,
            account_number=preview.account_number,
            allowed=False,
            reason="confirmation text is missing: " + ", ".join(missing),
        )

    return LiveOrderPreview(
        ticker=preview.ticker,
        side=preview.side,
        quantity=preview.quantity,
        notional=preview.notional,
        account_number=preview.account_number,
        allowed=True,
        reason="human confirmation accepted; live placement is not implemented in this MVP",
    )


def format_live_order_preview(preview: LiveOrderPreview) -> str:
    return "\n".join(
        [
            f"{preview.ticker} live order safety preview",
            f"Side: {preview.side.value.upper()}",
            f"Quantity: {preview.quantity:g}",
            f"Notional: ${preview.notional:,.2f}",
            f"Account: {preview.account_number or '<missing>'}",
            f"Allowed: {'yes' if preview.allowed else 'no'}",
            f"Reason: {preview.reason}",
            "No live Robinhood order was placed.",
        ]
    )


def _blocked(
    config: RobinhoodGateConfig,
    paper_preview: TradePreview,
    account_number: str,
    reason: str,
) -> LiveOrderPreview:
    return LiveOrderPreview(
        ticker=paper_preview.ticker,
        side=paper_preview.side,
        quantity=paper_preview.quantity,
        notional=paper_preview.notional,
        account_number=account_number or config.allowed_account_number or "",
        allowed=False,
        reason=reason,
    )
