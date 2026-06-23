from __future__ import annotations

from robinhood_agent.storage import AgentRepository, LoadedState


def quick_status(repository: AgentRepository, ticker: str) -> str:
    return format_quick_status(ticker.upper(), repository.load_state(ticker))


def format_quick_status(ticker: str, state: LoadedState) -> str:
    if state.watch_profile is None:
        return f"{ticker}: no watch profile found. Run setup before requesting status."

    lines = [f"{ticker} quick status", f"Benchmark: {state.watch_profile.benchmark}"]

    if state.thesis is None:
        lines.append("Thesis: no thesis recorded yet.")
    else:
        thesis = state.thesis
        lines.extend(
            [
                f"View: {thesis.view.value.upper()}",
                f"Confidence: {thesis.confidence:.0%}",
                f"Target position: {thesis.target_position_pct:.0%}",
                f"Horizon: {thesis.horizon}",
                "Invalidation conditions:",
            ]
        )
        lines.extend(f"- {item}" for item in thesis.invalidation_conditions)

    position = state.ledger.position
    if position is None:
        lines.append(f"Paper ledger: ${state.ledger.cash:,.2f} cash, no position.")
    else:
        lines.append(
            "Paper ledger: "
            f"${state.ledger.cash:,.2f} cash, "
            f"{position.quantity:g} shares @ ${position.average_cost:,.2f} avg cost."
        )

    if state.latest_research_update is not None:
        update = state.latest_research_update
        lines.append(f"Latest update: {update.thesis_after}")

    if state.latest_performance_snapshot is not None:
        snapshot = state.latest_performance_snapshot
        lines.append(
            "Latest performance: "
            f"{snapshot.window} absolute {snapshot.absolute_return:.2%}, "
            f"relative {snapshot.relative_return:.2%}, "
            f"max drawdown {snapshot.max_drawdown:.2%}."
        )

    return "\n".join(lines)
