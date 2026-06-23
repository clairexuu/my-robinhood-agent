from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List
from uuid import uuid4

from robinhood_agent.analysis import ImpactAnalyzer
from robinhood_agent.domain import ImpactAnalysis, ResearchEvent, ResearchUpdate, ThesisState
from robinhood_agent.providers import MarketData, MarketDataProvider, NewsProvider
from robinhood_agent.storage import AgentRepository

from .paper_ledger import TradePreview, build_paper_intent


@dataclass(frozen=True)
class FullResearchResult:
    ticker: str
    benchmark: str
    market_data: MarketData
    events: List[ResearchEvent]
    signals: Dict[str, float]
    impact_analysis: ImpactAnalysis
    thesis: ThesisState
    research_update: ResearchUpdate
    paper_intent: TradePreview
    inserted_event_count: int


def full_research(
    repository: AgentRepository,
    ticker: str,
    market_data_provider: MarketDataProvider,
    news_provider: NewsProvider,
    impact_analyzer: ImpactAnalyzer,
) -> FullResearchResult:
    normalized_ticker = ticker.upper()
    loaded = repository.load_state(normalized_ticker)
    if loaded.watch_profile is None:
        raise ValueError(f"{normalized_ticker} has no watch profile")
    if loaded.thesis is None:
        raise ValueError(f"{normalized_ticker} has no thesis state")

    profile = loaded.watch_profile
    prior_thesis = loaded.thesis

    market_data = market_data_provider.fetch_market_data(profile.ticker, profile.benchmark)
    events = news_provider.fetch_news(profile.ticker)
    inserted_count = sum(1 for event in events if repository.save_research_event(event))
    signals = compute_signals(market_data)
    impact = impact_analyzer.analyze(prior_thesis, events, signals)
    updated_thesis = update_thesis(prior_thesis, impact)
    repository.save_thesis(updated_thesis)

    research_update = build_research_update(prior_thesis, updated_thesis, impact)
    repository.save_research_update(research_update)
    paper_intent = build_paper_intent(
        repository=repository,
        ticker=profile.ticker,
        target_position_pct=updated_thesis.target_position_pct,
        market_data=market_data,
    )

    return FullResearchResult(
        ticker=profile.ticker,
        benchmark=profile.benchmark,
        market_data=market_data,
        events=events,
        signals=signals,
        impact_analysis=impact,
        thesis=updated_thesis,
        research_update=research_update,
        paper_intent=paper_intent,
        inserted_event_count=inserted_count,
    )


def compute_signals(market_data: MarketData) -> Dict[str, float]:
    return {
        "price_change_pct": market_data.price_change_pct,
        "benchmark_change_pct": market_data.benchmark_change_pct,
        "relative_change_pct": market_data.relative_change_pct,
        "volume_ratio": (
            market_data.volume / market_data.average_volume
            if market_data.average_volume
            else 0.0
        ),
    }


def update_thesis(prior: ThesisState, impact: ImpactAnalysis) -> ThesisState:
    confidence = round(min(1.0, max(0.0, prior.confidence + impact.confidence_delta)), 4)
    risks = _append_unique(prior.risks, impact.risk_updates)
    invalidation_conditions = _append_unique(
        prior.invalidation_conditions,
        impact.invalidation_updates,
    )

    return ThesisState(
        id=str(uuid4()),
        ticker=prior.ticker,
        view=prior.view,
        confidence=confidence,
        target_position_pct=prior.target_position_pct,
        horizon=prior.horizon,
        core_assumptions=prior.core_assumptions,
        risks=risks,
        invalidation_conditions=invalidation_conditions,
        updated_at=datetime.now(timezone.utc),
    )


def build_research_update(
    prior: ThesisState,
    updated: ThesisState,
    impact: ImpactAnalysis,
) -> ResearchUpdate:
    key_changes = list(impact.key_points)
    if updated.confidence != prior.confidence:
        key_changes.append(
            f"Confidence changed from {prior.confidence:.0%} to {updated.confidence:.0%}."
        )
    if not key_changes:
        key_changes.append("No material changes.")

    return ResearchUpdate(
        id=str(uuid4()),
        ticker=updated.ticker,
        thesis_before=f"{prior.view.value} at {prior.confidence:.0%} confidence",
        thesis_after=f"{updated.view.value} at {updated.confidence:.0%} confidence",
        key_changes=key_changes,
        view=updated.view,
        confidence=updated.confidence,
        suggested_position_pct=updated.target_position_pct,
        invalidation_conditions=updated.invalidation_conditions,
        created_at=datetime.now(timezone.utc),
    )


def format_full_research_result(result: FullResearchResult) -> str:
    lines = [
        f"{result.ticker} full research",
        f"Benchmark: {result.benchmark}",
        (
            "Market: "
            f"${result.market_data.latest_price:,.2f} "
            f"({result.signals['price_change_pct']:.2%}), "
            f"relative {result.signals['relative_change_pct']:.2%}"
        ),
        f"Events processed: {len(result.events)} ({result.inserted_event_count} new)",
        f"Impact severity: {result.impact_analysis.severity.value}",
        f"Thesis changed: {'yes' if result.impact_analysis.changes_thesis else 'no'}",
        f"View: {result.thesis.view.value.upper()}",
        f"Confidence: {result.thesis.confidence:.0%}",
        f"Target position: {result.thesis.target_position_pct:.0%}",
        (
            "Paper intent: "
            f"{result.paper_intent.side.value.upper()} "
            f"${result.paper_intent.notional:,.2f} "
            f"({result.paper_intent.quantity:g} shares), "
            f"allowed: {'yes' if result.paper_intent.allowed else 'no'}"
        ),
        "Paper intent is a local simulation preview, not a live Robinhood order.",
        "Key changes:",
    ]
    lines.extend(f"- {item}" for item in result.research_update.key_changes)
    return "\n".join(lines)


def _append_unique(existing: List[str], additions: List[str]) -> List[str]:
    result = list(existing)
    for item in additions:
        if item not in result:
            result.append(item)
    return result
