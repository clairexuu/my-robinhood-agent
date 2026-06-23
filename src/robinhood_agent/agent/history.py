from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List

from robinhood_agent.domain import PaperOrder, PerformanceSnapshot, ResearchEvent, ResearchUpdate
from robinhood_agent.storage import AgentRepository


@dataclass(frozen=True)
class HistoryReport:
    ticker: str
    events: List[ResearchEvent]
    updates: List[ResearchUpdate]
    orders: List[PaperOrder]
    performance_snapshots: List[PerformanceSnapshot]


def load_history(
    repository: AgentRepository,
    ticker: str,
    kind: str = "all",
    limit: int = 10,
) -> HistoryReport:
    if limit <= 0:
        raise ValueError("limit must be positive")
    normalized = ticker.upper()
    include_all = kind == "all"
    return HistoryReport(
        ticker=normalized,
        events=repository.list_research_events(normalized, limit) if include_all or kind == "events" else [],
        updates=repository.list_research_updates(normalized, limit) if include_all or kind == "updates" else [],
        orders=repository.list_paper_orders(normalized, limit) if include_all or kind == "orders" else [],
        performance_snapshots=(
            repository.list_performance_snapshots(normalized, limit)
            if include_all or kind == "performance"
            else []
        ),
    )


def format_history_report(report: HistoryReport) -> str:
    lines = [f"{report.ticker} history"]
    if report.events:
        lines.append("Events:")
        lines.extend(
            f"- {event.occurred_at.isoformat()} [{event.severity.value}] {event.title}"
            for event in report.events
        )
    if report.updates:
        lines.append("Research updates:")
        lines.extend(
            f"- {update.created_at.isoformat()} {update.thesis_after}"
            for update in report.updates
        )
    if report.orders:
        lines.append("Paper orders:")
        lines.extend(
            (
                f"- {order.created_at.isoformat()} {order.side.value.upper()} "
                f"{order.quantity:g} @ ${order.price:,.2f}"
                + (f" linked_update={order.research_update_id}" if order.research_update_id else "")
            )
            for order in report.orders
        )
    if report.performance_snapshots:
        lines.append("Performance snapshots:")
        lines.extend(
            (
                f"- {snapshot.created_at.isoformat()} {snapshot.window} "
                f"absolute {snapshot.absolute_return:.2%}, "
                f"relative {snapshot.relative_return:.2%}, "
                f"max drawdown {snapshot.max_drawdown:.2%}"
            )
            for snapshot in report.performance_snapshots
        )
    if len(lines) == 1:
        lines.append("No history found.")
    return "\n".join(lines)


def history_report_to_dict(report: HistoryReport) -> Dict[str, Any]:
    return {
        "ticker": report.ticker,
        "events": [
            {
                "id": event.id,
                "ticker": event.ticker,
                "source": event.source,
                "external_id": event.external_id,
                "event_type": event.event_type,
                "severity": event.severity.value,
                "title": event.title,
                "summary": event.summary,
                "occurred_at": event.occurred_at.isoformat(),
                "raw_url": event.raw_url,
            }
            for event in report.events
        ],
        "research_updates": [
            {
                "id": update.id,
                "ticker": update.ticker,
                "thesis_before": update.thesis_before,
                "thesis_after": update.thesis_after,
                "key_changes": update.key_changes,
                "view": update.view.value,
                "confidence": update.confidence,
                "suggested_position_pct": update.suggested_position_pct,
                "invalidation_conditions": update.invalidation_conditions,
                "created_at": update.created_at.isoformat(),
            }
            for update in report.updates
        ],
        "paper_orders": [
            {
                "id": order.id,
                "ticker": order.ticker,
                "side": order.side.value,
                "quantity": order.quantity,
                "price": order.price,
                "fee": order.fee,
                "research_update_id": order.research_update_id,
                "created_at": order.created_at.isoformat(),
            }
            for order in report.orders
        ],
        "performance_snapshots": [
            {
                "id": snapshot.id,
                "ticker": snapshot.ticker,
                "window": snapshot.window,
                "absolute_return": snapshot.absolute_return,
                "benchmark_return": snapshot.benchmark_return,
                "relative_return": snapshot.relative_return,
                "max_drawdown": snapshot.max_drawdown,
                "created_at": snapshot.created_at.isoformat(),
            }
            for snapshot in report.performance_snapshots
        ],
    }


def format_history_json(report: HistoryReport) -> str:
    return json.dumps(history_report_to_dict(report), indent=2, sort_keys=True)
