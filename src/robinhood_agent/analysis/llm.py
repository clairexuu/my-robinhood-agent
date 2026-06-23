from __future__ import annotations

import json
from urllib import error, request
from typing import Dict, List, Protocol

from robinhood_agent.domain import ImpactAnalysis, ResearchEvent, Severity, ThesisState


class LlmClient(Protocol):
    def complete(self, prompt: str) -> str:
        ...


class LlmOutputError(ValueError):
    pass


class StaticJsonLlmClient:
    def __init__(self, response: str):
        self.response = response
        self.prompts: List[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


class OpenAIResponsesLlmClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 60.0,
    ):
        if not api_key:
            raise ValueError("api_key is required")
        if not model:
            raise ValueError("model is required")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def complete(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "You are an investment research assistant. Return only JSON "
                        "matching the requested schema. Do not provide financial advice "
                        "as a directive; analyze thesis impact from supplied facts."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "impact_analysis",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "changes_thesis": {"type": "boolean"},
                            "severity": {
                                "type": "string",
                                "enum": ["low", "medium", "high", "critical"],
                            },
                            "key_points": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "thesis_delta": {"type": "string"},
                            "confidence_delta": {
                                "type": "number",
                                "minimum": -1,
                                "maximum": 1,
                            },
                            "risk_updates": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "invalidation_updates": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": [
                            "changes_thesis",
                            "severity",
                            "key_points",
                            "thesis_delta",
                            "confidence_delta",
                            "risk_updates",
                            "invalidation_updates",
                        ],
                    },
                }
            },
        }
        body = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            f"{self.base_url}/responses",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LlmOutputError(f"OpenAI request failed: {exc.code} {detail}") from exc
        except error.URLError as exc:
            raise LlmOutputError(f"OpenAI request failed: {exc.reason}") from exc

        return _extract_response_text(data)


class StructuredLlmImpactAnalyzer:
    def __init__(self, client: LlmClient):
        self.client = client

    def analyze(
        self,
        thesis: ThesisState,
        events: List[ResearchEvent],
        signals: Dict[str, float],
    ) -> ImpactAnalysis:
        prompt = build_impact_prompt(thesis, events, signals)
        raw_response = self.client.complete(prompt)
        return parse_impact_analysis(raw_response)


def build_impact_prompt(
    thesis: ThesisState,
    events: List[ResearchEvent],
    signals: Dict[str, float],
) -> str:
    event_lines = "\n".join(
        [
            (
                f"- [{event.severity.value}] {event.title}: {event.summary} "
                f"(source={event.source}, occurred_at={event.occurred_at.isoformat()})"
            )
            for event in events
        ]
    )
    signal_lines = "\n".join(
        [f"- {key}: {value}" for key, value in sorted(signals.items())]
    )
    return (
        "You are analyzing whether new research events change an investment thesis.\n"
        "Do not invent missing facts. Separate facts from inference. Return JSON only.\n\n"
        "Required JSON schema:\n"
        "{\n"
        '  "changes_thesis": boolean,\n'
        '  "severity": "low" | "medium" | "high" | "critical",\n'
        '  "key_points": string[],\n'
        '  "thesis_delta": string,\n'
        '  "confidence_delta": number between -1 and 1,\n'
        '  "risk_updates": string[],\n'
        '  "invalidation_updates": string[]\n'
        "}\n\n"
        f"Ticker: {thesis.ticker}\n"
        f"Current view: {thesis.view.value}\n"
        f"Current confidence: {thesis.confidence}\n"
        f"Target position pct: {thesis.target_position_pct}\n"
        f"Horizon: {thesis.horizon}\n"
        f"Core assumptions: {json.dumps(thesis.core_assumptions)}\n"
        f"Risks: {json.dumps(thesis.risks)}\n"
        f"Invalidation conditions: {json.dumps(thesis.invalidation_conditions)}\n\n"
        "Events:\n"
        f"{event_lines or '- none'}\n\n"
        "Signals:\n"
        f"{signal_lines or '- none'}\n"
    )


def parse_impact_analysis(raw_response: str) -> ImpactAnalysis:
    try:
        data = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise LlmOutputError(f"LLM output was not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise LlmOutputError("LLM output JSON must be an object")

    required = {
        "changes_thesis",
        "severity",
        "key_points",
        "thesis_delta",
        "confidence_delta",
        "risk_updates",
        "invalidation_updates",
    }
    missing = required - set(data)
    if missing:
        raise LlmOutputError(f"LLM output missing fields: {', '.join(sorted(missing))}")

    if not isinstance(data["changes_thesis"], bool):
        raise LlmOutputError("changes_thesis must be a boolean")
    _require_string_list(data["key_points"], "key_points")
    _require_string_list(data["risk_updates"], "risk_updates")
    _require_string_list(data["invalidation_updates"], "invalidation_updates")

    try:
        severity = Severity(data["severity"])
    except ValueError as exc:
        raise LlmOutputError("severity must be low, medium, high, or critical") from exc

    try:
        confidence_delta = float(data["confidence_delta"])
    except (TypeError, ValueError) as exc:
        raise LlmOutputError("confidence_delta must be numeric") from exc

    try:
        return ImpactAnalysis(
            changes_thesis=data["changes_thesis"],
            severity=severity,
            key_points=data["key_points"],
            thesis_delta=data["thesis_delta"],
            confidence_delta=confidence_delta,
            risk_updates=data["risk_updates"],
            invalidation_updates=data["invalidation_updates"],
        )
    except (TypeError, ValueError) as exc:
        raise LlmOutputError(f"LLM output failed schema validation: {exc}") from exc


def _require_string_list(value: object, field_name: str) -> None:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise LlmOutputError(f"{field_name} must be a list of strings")


def _extract_response_text(data: object) -> str:
    if not isinstance(data, dict):
        raise LlmOutputError("OpenAI response must be a JSON object")
    output_text = data.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    output = data.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    return text

    raise LlmOutputError("OpenAI response did not include output text")
