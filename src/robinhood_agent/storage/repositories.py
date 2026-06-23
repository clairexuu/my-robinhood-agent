from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from robinhood_agent.domain import (
    OrderSide,
    PaperOrder,
    PaperPosition,
    PerformanceSnapshot,
    ResearchEvent,
    ResearchUpdate,
    Severity,
    ThesisState,
    View,
    WatchProfile,
)
from robinhood_agent.domain.models import datetime_from_text


@dataclass(frozen=True)
class LedgerSummary:
    cash: float
    position: Optional[PaperPosition]


@dataclass(frozen=True)
class LoadedState:
    watch_profile: Optional[WatchProfile]
    thesis: Optional[ThesisState]
    ledger: LedgerSummary
    latest_research_update: Optional[ResearchUpdate]
    latest_performance_snapshot: Optional[PerformanceSnapshot]


class AgentRepository:
    def __init__(self, connection: sqlite3.Connection, initial_cash: float = 100_000.0):
        self.connection = connection
        self.initial_cash = initial_cash

    def save_watch_profile(self, profile: WatchProfile) -> None:
        self.connection.execute(
            """
            INSERT INTO watch_profiles(ticker, benchmark, display_name, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                benchmark = excluded.benchmark,
                display_name = excluded.display_name,
                updated_at = excluded.updated_at
            """,
            (
                profile.ticker,
                profile.benchmark,
                profile.display_name,
                profile.created_at.isoformat(),
                profile.updated_at.isoformat(),
            ),
        )
        self.connection.commit()

    def get_watch_profile(self, ticker: str) -> Optional[WatchProfile]:
        row = self.connection.execute(
            "SELECT * FROM watch_profiles WHERE ticker = ?",
            (ticker.upper(),),
        ).fetchone()
        if row is None:
            return None
        return WatchProfile(
            ticker=row["ticker"],
            benchmark=row["benchmark"],
            display_name=row["display_name"],
            created_at=datetime_from_text(row["created_at"]),
            updated_at=datetime_from_text(row["updated_at"]),
        )

    def save_thesis(self, thesis: ThesisState) -> ThesisState:
        thesis_id = thesis.id or str(uuid4())
        self.connection.execute(
            """
            INSERT INTO thesis_states(
                id, ticker, view, confidence, target_position_pct, horizon,
                core_assumptions_json, risks_json, invalidation_conditions_json, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                thesis_id,
                thesis.ticker,
                thesis.view.value,
                thesis.confidence,
                thesis.target_position_pct,
                thesis.horizon,
                json.dumps(thesis.core_assumptions),
                json.dumps(thesis.risks),
                json.dumps(thesis.invalidation_conditions),
                thesis.updated_at.isoformat(),
            ),
        )
        self.connection.commit()
        if thesis.id:
            return thesis
        return ThesisState(
            id=thesis_id,
            ticker=thesis.ticker,
            view=thesis.view,
            confidence=thesis.confidence,
            target_position_pct=thesis.target_position_pct,
            horizon=thesis.horizon,
            core_assumptions=thesis.core_assumptions,
            risks=thesis.risks,
            invalidation_conditions=thesis.invalidation_conditions,
            updated_at=thesis.updated_at,
        )

    def get_latest_thesis(self, ticker: str) -> Optional[ThesisState]:
        row = self.connection.execute(
            """
            SELECT * FROM thesis_states
            WHERE ticker = ?
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (ticker.upper(),),
        ).fetchone()
        if row is None:
            return None
        return ThesisState(
            id=row["id"],
            ticker=row["ticker"],
            view=View(row["view"]),
            confidence=row["confidence"],
            target_position_pct=row["target_position_pct"],
            horizon=row["horizon"],
            core_assumptions=json.loads(row["core_assumptions_json"]),
            risks=json.loads(row["risks_json"]),
            invalidation_conditions=json.loads(row["invalidation_conditions_json"]),
            updated_at=datetime_from_text(row["updated_at"]),
        )

    def save_research_event(self, event: ResearchEvent) -> bool:
        cursor = self.connection.execute(
            """
            INSERT OR IGNORE INTO research_events(
                id, ticker, source, external_id, event_type, severity,
                title, summary, occurred_at, raw_url
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.id,
                event.ticker,
                event.source,
                event.external_id,
                event.event_type,
                event.severity.value,
                event.title,
                event.summary,
                event.occurred_at.isoformat(),
                event.raw_url,
            ),
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def save_research_update(self, update: ResearchUpdate) -> None:
        self.connection.execute(
            """
            INSERT INTO research_updates(
                id, ticker, thesis_before, thesis_after, key_changes_json,
                view, confidence, suggested_position_pct,
                invalidation_conditions_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                update.id,
                update.ticker,
                update.thesis_before,
                update.thesis_after,
                json.dumps(update.key_changes),
                update.view.value,
                update.confidence,
                update.suggested_position_pct,
                json.dumps(update.invalidation_conditions),
                update.created_at.isoformat(),
            ),
        )
        self.connection.commit()

    def get_latest_research_update(self, ticker: str) -> Optional[ResearchUpdate]:
        row = self.connection.execute(
            """
            SELECT * FROM research_updates
            WHERE ticker = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (ticker.upper(),),
        ).fetchone()
        if row is None:
            return None
        return ResearchUpdate(
            id=row["id"],
            ticker=row["ticker"],
            thesis_before=row["thesis_before"],
            thesis_after=row["thesis_after"],
            key_changes=json.loads(row["key_changes_json"]),
            view=View(row["view"]),
            confidence=row["confidence"],
            suggested_position_pct=row["suggested_position_pct"],
            invalidation_conditions=json.loads(row["invalidation_conditions_json"]),
            created_at=datetime_from_text(row["created_at"]),
        )

    def list_research_updates(self, ticker: str, limit: int = 10) -> List[ResearchUpdate]:
        rows = self.connection.execute(
            """
            SELECT * FROM research_updates
            WHERE ticker = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (ticker.upper(), limit),
        ).fetchall()
        return [
            ResearchUpdate(
                id=row["id"],
                ticker=row["ticker"],
                thesis_before=row["thesis_before"],
                thesis_after=row["thesis_after"],
                key_changes=json.loads(row["key_changes_json"]),
                view=View(row["view"]),
                confidence=row["confidence"],
                suggested_position_pct=row["suggested_position_pct"],
                invalidation_conditions=json.loads(row["invalidation_conditions_json"]),
                created_at=datetime_from_text(row["created_at"]),
            )
            for row in rows
        ]

    def list_research_events(self, ticker: str, limit: int = 10) -> List[ResearchEvent]:
        rows = self.connection.execute(
            """
            SELECT * FROM research_events
            WHERE ticker = ?
            ORDER BY occurred_at DESC
            LIMIT ?
            """,
            (ticker.upper(), limit),
        ).fetchall()
        return [
            ResearchEvent(
                id=row["id"],
                ticker=row["ticker"],
                source=row["source"],
                external_id=row["external_id"],
                event_type=row["event_type"],
                severity=Severity(row["severity"]),
                title=row["title"],
                summary=row["summary"],
                occurred_at=datetime_from_text(row["occurred_at"]),
                raw_url=row["raw_url"],
            )
            for row in rows
        ]

    def record_paper_order(self, order: PaperOrder) -> PaperPosition:
        current = self.get_position(order.ticker)
        current_quantity = current.quantity if current else 0.0
        current_cost = current.average_cost if current else 0.0

        if order.side == OrderSide.BUY:
            total_cost = current_quantity * current_cost + order.quantity * order.price + order.fee
            new_quantity = current_quantity + order.quantity
            new_average_cost = total_cost / new_quantity if new_quantity else 0.0
        elif order.side == OrderSide.SELL:
            if order.quantity > current_quantity:
                raise ValueError("cannot sell more than current paper position")
            new_quantity = current_quantity - order.quantity
            new_average_cost = current_cost if new_quantity else 0.0
        else:
            new_quantity = current_quantity
            new_average_cost = current_cost

        self.connection.execute(
            """
            INSERT INTO paper_orders(
                id, ticker, side, quantity, price, fee, research_update_id, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order.id,
                order.ticker,
                order.side.value,
                order.quantity,
                order.price,
                order.fee,
                order.research_update_id,
                order.created_at.isoformat(),
            ),
        )
        position = PaperPosition(
            ticker=order.ticker,
            quantity=new_quantity,
            average_cost=new_average_cost,
            updated_at=order.created_at,
        )
        self._save_position(position)
        self.connection.commit()
        return position

    def get_position(self, ticker: str) -> Optional[PaperPosition]:
        row = self.connection.execute(
            "SELECT * FROM paper_positions WHERE ticker = ?",
            (ticker.upper(),),
        ).fetchone()
        if row is None:
            return None
        return PaperPosition(
            ticker=row["ticker"],
            quantity=row["quantity"],
            average_cost=row["average_cost"],
            updated_at=datetime_from_text(row["updated_at"]),
        )

    def list_paper_orders(self, ticker: str, limit: int = 10) -> List[PaperOrder]:
        rows = self.connection.execute(
            """
            SELECT * FROM paper_orders
            WHERE ticker = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (ticker.upper(), limit),
        ).fetchall()
        return [
            PaperOrder(
                id=row["id"],
                ticker=row["ticker"],
                side=OrderSide(row["side"]),
                quantity=row["quantity"],
                price=row["price"],
                fee=row["fee"],
                research_update_id=row["research_update_id"],
                created_at=datetime_from_text(row["created_at"]),
            )
            for row in rows
        ]

    def save_performance_snapshot(self, snapshot: PerformanceSnapshot) -> None:
        self.connection.execute(
            """
            INSERT INTO performance_snapshots(
                id, ticker, window, absolute_return, benchmark_return, max_drawdown, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot.id,
                snapshot.ticker,
                snapshot.window,
                snapshot.absolute_return,
                snapshot.benchmark_return,
                snapshot.max_drawdown,
                snapshot.created_at.isoformat(),
            ),
        )
        self.connection.commit()

    def get_latest_performance_snapshot(
        self,
        ticker: str,
        window: str,
    ) -> Optional[PerformanceSnapshot]:
        row = self.connection.execute(
            """
            SELECT * FROM performance_snapshots
            WHERE ticker = ? AND window = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (ticker.upper(), window),
        ).fetchone()
        if row is None:
            return None
        return PerformanceSnapshot(
            id=row["id"],
            ticker=row["ticker"],
            window=row["window"],
            absolute_return=row["absolute_return"],
            benchmark_return=row["benchmark_return"],
            max_drawdown=row["max_drawdown"],
            created_at=datetime_from_text(row["created_at"]),
        )

    def list_performance_snapshots(self, ticker: str, limit: int = 10) -> List[PerformanceSnapshot]:
        rows = self.connection.execute(
            """
            SELECT * FROM performance_snapshots
            WHERE ticker = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (ticker.upper(), limit),
        ).fetchall()
        return [
            PerformanceSnapshot(
                id=row["id"],
                ticker=row["ticker"],
                window=row["window"],
                absolute_return=row["absolute_return"],
                benchmark_return=row["benchmark_return"],
                max_drawdown=row["max_drawdown"],
                created_at=datetime_from_text(row["created_at"]),
            )
            for row in rows
        ]

    def load_state(self, ticker: str) -> LoadedState:
        normalized_ticker = ticker.upper()
        return LoadedState(
            watch_profile=self.get_watch_profile(normalized_ticker),
            thesis=self.get_latest_thesis(normalized_ticker),
            ledger=self.get_ledger_summary(normalized_ticker),
            latest_research_update=self.get_latest_research_update(normalized_ticker),
            latest_performance_snapshot=self.get_latest_performance_snapshot(normalized_ticker, "1W"),
        )

    def get_ledger_summary(self, ticker: str) -> LedgerSummary:
        position = self.get_position(ticker)
        spent = self.connection.execute(
            """
            SELECT COALESCE(SUM(
                CASE
                    WHEN side = 'buy' THEN quantity * price + fee
                    WHEN side = 'sell' THEN -(quantity * price - fee)
                    ELSE 0
                END
            ), 0) AS net_spent
            FROM paper_orders
            WHERE ticker = ?
            """,
            (ticker.upper(),),
        ).fetchone()["net_spent"]
        return LedgerSummary(cash=self.initial_cash - spent, position=position)

    def _save_position(self, position: PaperPosition) -> None:
        self.connection.execute(
            """
            INSERT INTO paper_positions(ticker, quantity, average_cost, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                quantity = excluded.quantity,
                average_cost = excluded.average_cost,
                updated_at = excluded.updated_at
            """,
            (
                position.ticker,
                position.quantity,
                position.average_cost,
                position.updated_at.isoformat(),
            ),
        )


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
