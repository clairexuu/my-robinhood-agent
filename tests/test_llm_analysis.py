import json
import unittest
from pathlib import Path

from robinhood_agent.analysis import (
    LlmOutputError,
    OpenAIResponsesLlmClient,
    StaticJsonLlmClient,
    StructuredLlmImpactAnalyzer,
    build_impact_prompt,
    parse_impact_analysis,
)
from robinhood_agent.fixtures import nvda_initial_thesis
from robinhood_agent.providers import JsonNewsProvider


VALID_RESPONSE = json.dumps(
    {
        "changes_thesis": True,
        "severity": "high",
        "key_points": ["Supply update supports the current thesis."],
        "thesis_delta": "Confidence increases modestly.",
        "confidence_delta": 0.05,
        "risk_updates": ["Supply concentration remains a risk."],
        "invalidation_updates": ["Supply update reverses within one quarter."],
    }
)


class LlmAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.thesis = nvda_initial_thesis()
        self.events = JsonNewsProvider(Path(__file__).parent / "fixtures" / "news.json").fetch_news("NVDA")
        self.signals = {"price_change_pct": 0.024, "relative_change_pct": 0.022}

    def test_build_impact_prompt_contains_core_inputs_and_schema(self):
        prompt = build_impact_prompt(self.thesis, self.events, self.signals)

        self.assertIn("Required JSON schema", prompt)
        self.assertIn("Ticker: NVDA", prompt)
        self.assertIn("NVDA publishes routine developer update", prompt)
        self.assertIn("price_change_pct", prompt)
        self.assertIn("Do not invent missing facts", prompt)

    def test_parse_impact_analysis_accepts_valid_json(self):
        analysis = parse_impact_analysis(VALID_RESPONSE)

        self.assertTrue(analysis.changes_thesis)
        self.assertEqual(analysis.severity.value, "high")
        self.assertEqual(analysis.confidence_delta, 0.05)
        self.assertIn("Supply concentration", analysis.risk_updates[0])

    def test_parse_impact_analysis_rejects_invalid_json(self):
        with self.assertRaises(LlmOutputError):
            parse_impact_analysis("not json")

    def test_parse_impact_analysis_rejects_missing_fields(self):
        with self.assertRaises(LlmOutputError):
            parse_impact_analysis(json.dumps({"changes_thesis": True}))

    def test_parse_impact_analysis_rejects_bad_severity(self):
        data = json.loads(VALID_RESPONSE)
        data["severity"] = "urgent"

        with self.assertRaises(LlmOutputError):
            parse_impact_analysis(json.dumps(data))

    def test_parse_impact_analysis_rejects_bad_list_type(self):
        data = json.loads(VALID_RESPONSE)
        data["key_points"] = "not a list"

        with self.assertRaises(LlmOutputError):
            parse_impact_analysis(json.dumps(data))

    def test_structured_llm_impact_analyzer_calls_client_and_parses_output(self):
        client = StaticJsonLlmClient(VALID_RESPONSE)
        analyzer = StructuredLlmImpactAnalyzer(client)

        analysis = analyzer.analyze(self.thesis, self.events, self.signals)

        self.assertEqual(analysis.severity.value, "high")
        self.assertEqual(len(client.prompts), 1)
        self.assertIn("NVDA", client.prompts[0])

    def test_openai_client_extracts_output_text(self):
        client = OpenAIResponsesLlmClient(api_key="test-key", model="gpt-test")
        response = {
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": VALID_RESPONSE,
                        }
                    ]
                }
            ]
        }

        from robinhood_agent.analysis.llm import _extract_response_text

        self.assertEqual(_extract_response_text(response), VALID_RESPONSE)


if __name__ == "__main__":
    unittest.main()
