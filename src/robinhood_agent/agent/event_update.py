from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from robinhood_agent.analysis import ImpactAnalyzer
from robinhood_agent.domain import ImpactAnalysis, ResearchEvent, ResearchUpdate, Severity, ThesisState
from robinhood_agent.providers import MarketData, MarketDataProvider, NewsProvider
from robinhood_agent.storage import AgentRepository

from .full_research import build_research_update, compute_signals, update_thesis


@dataclass(frozen=True)
class EventUpdateResult:
    ticker: str
    benchmark: str
    market_data: MarketData
    fetched_events: List[ResearchEvent]
    new_events: List[ResearchEvent]
    signals: Dict[str, float]
    triggered_analysis: bool
    impact_analysis: Optional[ImpactAnalysis]
    thesis: ThesisState
    research_update: Optional[ResearchUpdate]


def event_update(
    repository: AgentRepository,
    ticker: str,
    market_data_provider: MarketDataProvider,
    news_provider: NewsProvider,
    impact_analyzer: ImpactAnalyzer,
) -> EventUpdateResult:
    normalized_ticker = ticker.upper()
    loaded = repository.load_state(normalized_ticker)
    if loaded.watch_profile is None:
        raise ValueError(f"{normalized_ticker} has no watch profile")
    if loaded.thesis is None:
        raise ValueError(f"{normalized_ticker} has no thesis state")

    profile = loaded.watch_profile
    prior_thesis = loaded.thesis
    market_data = market_data_provider.fetch_market_data(profile.ticker, profile.benchmark)
    fetched_events = news_provider.fetch_news(profile.ticker)
    new_events = [event for event in fetched_events if repository.save_research_event(event)]
    signals = compute_signals(market_data)

    if not _should_trigger_analysis(new_events):
        return EventUpdateResult(
            ticker=profile.ticker,
            benchmark=profile.benchmark,
            market_data=market_data,
            fetched_events=fetched_events,
            new_events=new_events,
            signals=signals,
            triggered_analysis=False,
            impact_analysis=None,
            thesis=prior_thesis,
            research_update=None,
        )

    impact = impact_analyzer.analyze(prior_thesis, new_events, signals)
    updated_thesis = update_thesis(prior_thesis, impact)
    repository.save_thesis(updated_thesis)
    research_update = build_research_update(prior_thesis, updated_thesis, impact)
    repository.save_research_update(research_update)

    return EventUpdateResult(
        ticker=profile.ticker,
        benchmark=profile.benchmark,
        market_data=market_data,
        fetched_events=fetched_events,
        new_events=new_events,
        signals=signals,
        triggered_analysis=True,
        impact_analysis=impact,
        thesis=updated_thesis,
        research_update=research_update,
    )


def format_event_update_result(result: EventUpdateResult) -> str:
    lines = [
        f"{result.ticker} event update",
        f"Benchmark: {result.benchmark}",
        f"Events fetched: {len(result.fetched_events)}",
        f"New events: {len(result.new_events)}",
        f"Analysis triggered: {'yes' if result.triggered_analysis else 'no'}",
        f"View: {result.thesis.view.value.upper()}",
        f"Confidence: {result.thesis.confidence:.0%}",
    ]
    if result.impact_analysis is not None:
        lines.append(f"Impact severity: {result.impact_analysis.severity.value}")
    if result.research_update is not None:
        lines.append("Key changes:")
        lines.extend(f"- {item}" for item in result.research_update.key_changes)
    return "\n".join(lines)


def _should_trigger_analysis(events: List[ResearchEvent]) -> bool:
    return any(event.severity in {Severity.HIGH, Severity.CRITICAL} for event in events)
