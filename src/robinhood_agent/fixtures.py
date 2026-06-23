from __future__ import annotations

from datetime import datetime, timezone

from .domain import ThesisState, View, WatchProfile


def nvda_watch_profile() -> WatchProfile:
    now = datetime.now(timezone.utc)
    return WatchProfile(
        ticker="NVDA",
        benchmark="SPY",
        display_name="Nvidia",
        created_at=now,
        updated_at=now,
    )


def nvda_initial_thesis() -> ThesisState:
    now = datetime.now(timezone.utc)
    return ThesisState(
        id="fixture-nvda-thesis",
        ticker="NVDA",
        view=View.HOLD,
        confidence=0.55,
        target_position_pct=0.10,
        horizon="3-6 months",
        core_assumptions=[
            "AI accelerator demand remains the primary revenue driver.",
            "Data center growth can offset cyclical gaming softness.",
        ],
        risks=[
            "Valuation compression if growth expectations reset lower.",
            "Supply constraints or margin pressure in data center products.",
        ],
        invalidation_conditions=[
            "Data center growth materially decelerates for two consecutive quarters.",
            "Gross margin guidance falls meaningfully below management's prior range.",
        ],
        updated_at=now,
    )
