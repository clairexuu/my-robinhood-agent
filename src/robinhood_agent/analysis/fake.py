from __future__ import annotations

from typing import Dict, List

from robinhood_agent.domain import ImpactAnalysis, ResearchEvent, Severity, ThesisState


class FakeImpactAnalyzer:
    def analyze(
        self,
        thesis: ThesisState,
        events: List[ResearchEvent],
        signals: Dict[str, float],
    ) -> ImpactAnalysis:
        max_severity = _max_severity(events)
        changes_thesis = max_severity in {Severity.HIGH, Severity.CRITICAL}
        price_change = signals.get("price_change_pct", 0.0)

        return ImpactAnalysis(
            changes_thesis=changes_thesis,
            severity=max_severity,
            key_points=[
                f"Processed {len(events)} event(s).",
                f"Latest price move was {price_change:.2%}.",
            ],
            thesis_delta=(
                "Important event supports the existing thesis."
                if changes_thesis
                else "No material thesis change from low-severity events."
            ),
            confidence_delta=0.05 if changes_thesis and price_change >= 0 else 0.0,
            risk_updates=[],
            invalidation_updates=[],
        )


def _max_severity(events: List[ResearchEvent]) -> Severity:
    rank = {
        Severity.LOW: 0,
        Severity.MEDIUM: 1,
        Severity.HIGH: 2,
        Severity.CRITICAL: 3,
    }
    if not events:
        return Severity.LOW
    return max((event.severity for event in events), key=lambda severity: rank[severity])
