from __future__ import annotations

from typing import Dict, List, Protocol

from robinhood_agent.domain import ImpactAnalysis, ResearchEvent, ThesisState


class ImpactAnalyzer(Protocol):
    def analyze(
        self,
        thesis: ThesisState,
        events: List[ResearchEvent],
        signals: Dict[str, float],
    ) -> ImpactAnalysis:
        ...
