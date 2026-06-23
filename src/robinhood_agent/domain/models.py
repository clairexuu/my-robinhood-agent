from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class View(str, Enum):
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass(frozen=True)
class ImpactAnalysis:
    changes_thesis: bool
    severity: Severity
    key_points: List[str]
    thesis_delta: str
    confidence_delta: float
    risk_updates: List[str]
    invalidation_updates: List[str]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "severity",
            _coerce_enum(Severity, self.severity, "severity"),
        )
        object.__setattr__(self, "key_points", _coerce_str_list(self.key_points, "key_points"))
        object.__setattr__(self, "risk_updates", _coerce_str_list(self.risk_updates, "risk_updates"))
        object.__setattr__(
            self,
            "invalidation_updates",
            _coerce_str_list(self.invalidation_updates, "invalidation_updates"),
        )
        if not self.thesis_delta.strip():
            raise ValueError("thesis_delta is required")
        require_range(self.confidence_delta, "confidence_delta", -1.0, 1.0)


def require_timezone_aware(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


def require_range(value: float, field_name: str, low: float, high: float) -> float:
    if not low <= value <= high:
        raise ValueError(f"{field_name} must be between {low} and {high}")
    return value


def _coerce_enum(enum_type: type[Enum], value: Any, field_name: str) -> Enum:
    try:
        return value if isinstance(value, enum_type) else enum_type(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise ValueError(f"{field_name} must be one of: {allowed}") from exc


def _coerce_str_list(value: List[str], field_name: str) -> List[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError(f"{field_name} must be a list of strings")
    return list(value)


def _datetime_to_text(value: datetime) -> str:
    return value.isoformat()


def datetime_from_text(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return require_timezone_aware(parsed, "datetime")


@dataclass(frozen=True)
class WatchProfile:
    ticker: str
    benchmark: str = "SPY"
    display_name: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        ticker = self.ticker.strip().upper()
        benchmark = self.benchmark.strip().upper()
        if not ticker:
            raise ValueError("ticker is required")
        if not benchmark:
            raise ValueError("benchmark is required")
        object.__setattr__(self, "ticker", ticker)
        object.__setattr__(self, "benchmark", benchmark)
        require_timezone_aware(self.created_at, "created_at")
        require_timezone_aware(self.updated_at, "updated_at")


@dataclass(frozen=True)
class ThesisState:
    ticker: str
    view: View
    confidence: float
    target_position_pct: float
    horizon: str
    core_assumptions: List[str]
    risks: List[str]
    invalidation_conditions: List[str]
    updated_at: datetime
    id: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "ticker", self.ticker.strip().upper())
        object.__setattr__(self, "view", _coerce_enum(View, self.view, "view"))
        require_range(self.confidence, "confidence", 0.0, 1.0)
        require_range(self.target_position_pct, "target_position_pct", 0.0, 1.0)
        if not self.horizon.strip():
            raise ValueError("horizon is required")
        object.__setattr__(self, "core_assumptions", _coerce_str_list(self.core_assumptions, "core_assumptions"))
        object.__setattr__(self, "risks", _coerce_str_list(self.risks, "risks"))
        invalidation_conditions = _coerce_str_list(
            self.invalidation_conditions, "invalidation_conditions"
        )
        if not invalidation_conditions:
            raise ValueError("invalidation_conditions is required")
        object.__setattr__(self, "invalidation_conditions", invalidation_conditions)
        require_timezone_aware(self.updated_at, "updated_at")


@dataclass(frozen=True)
class ResearchEvent:
    id: str
    ticker: str
    source: str
    event_type: str
    severity: Severity
    title: str
    summary: str
    occurred_at: datetime
    raw_url: Optional[str] = None
    external_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("id is required")
        object.__setattr__(self, "ticker", self.ticker.strip().upper())
        object.__setattr__(self, "severity", _coerce_enum(Severity, self.severity, "severity"))
        for field_name in ("source", "event_type", "title", "summary"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} is required")
        require_timezone_aware(self.occurred_at, "occurred_at")


@dataclass(frozen=True)
class ResearchUpdate:
    id: str
    ticker: str
    thesis_before: str
    thesis_after: str
    key_changes: List[str]
    view: View
    confidence: float
    suggested_position_pct: float
    invalidation_conditions: List[str]
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("id is required")
        object.__setattr__(self, "ticker", self.ticker.strip().upper())
        object.__setattr__(self, "view", _coerce_enum(View, self.view, "view"))
        object.__setattr__(self, "key_changes", _coerce_str_list(self.key_changes, "key_changes"))
        object.__setattr__(
            self,
            "invalidation_conditions",
            _coerce_str_list(self.invalidation_conditions, "invalidation_conditions"),
        )
        require_range(self.confidence, "confidence", 0.0, 1.0)
        require_range(self.suggested_position_pct, "suggested_position_pct", 0.0, 1.0)
        require_timezone_aware(self.created_at, "created_at")


@dataclass(frozen=True)
class PaperOrder:
    id: str
    ticker: str
    side: OrderSide
    quantity: float
    price: float
    fee: float
    created_at: datetime
    research_update_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("id is required")
        object.__setattr__(self, "ticker", self.ticker.strip().upper())
        object.__setattr__(self, "side", _coerce_enum(OrderSide, self.side, "side"))
        if self.quantity < 0:
            raise ValueError("quantity must be non-negative")
        if self.price < 0:
            raise ValueError("price must be non-negative")
        if self.fee < 0:
            raise ValueError("fee must be non-negative")
        require_timezone_aware(self.created_at, "created_at")


@dataclass(frozen=True)
class PaperPosition:
    ticker: str
    quantity: float
    average_cost: float
    updated_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "ticker", self.ticker.strip().upper())
        if self.quantity < 0:
            raise ValueError("quantity must be non-negative")
        if self.average_cost < 0:
            raise ValueError("average_cost must be non-negative")
        require_timezone_aware(self.updated_at, "updated_at")


@dataclass(frozen=True)
class PerformanceSnapshot:
    id: str
    ticker: str
    window: str
    absolute_return: float
    benchmark_return: float
    max_drawdown: float
    created_at: datetime

    @property
    def relative_return(self) -> float:
        return self.absolute_return - self.benchmark_return

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("id is required")
        object.__setattr__(self, "ticker", self.ticker.strip().upper())
        if not self.window.strip():
            raise ValueError("window is required")
        require_timezone_aware(self.created_at, "created_at")


def thesis_to_record(thesis: ThesisState) -> Dict[str, Any]:
    return {
        "id": thesis.id,
        "ticker": thesis.ticker,
        "view": thesis.view.value,
        "confidence": thesis.confidence,
        "target_position_pct": thesis.target_position_pct,
        "horizon": thesis.horizon,
        "core_assumptions": thesis.core_assumptions,
        "risks": thesis.risks,
        "invalidation_conditions": thesis.invalidation_conditions,
        "updated_at": _datetime_to_text(thesis.updated_at),
    }
